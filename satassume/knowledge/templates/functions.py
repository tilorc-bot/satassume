"""Structural templates for elementary functions.

Only statements that are theorems about the function's *value* under
SymPy's conventions are emitted (``log(0) = zoo``, ``acot(0) = pi/2``,
``atan(oo) = pi/2``, ``factorial(-1) = zoo``, principal branches, ...).
Transcendence facts follow from the Lindemann-Weierstrass theorem.
Predicates the rule base derives from the emitted ones (``positive`` from
``extended_positive & finite``, ``irrational`` from ``real & !rational``,
...) are not repeated.

Rules are index-based specs (see :mod:`._common`): the argument is index
0 and the node index 1.  A row ``(x_premises, conclusion)`` uses ``pred`` or
``(pred, False)`` for a premise on the argument and likewise for a
conclusion on the node.
"""
from __future__ import annotations

from collections import Counter

from sympy import S
from sympy.core.add import Add
from sympy.functions.elementary.integers import ceiling, floor

from ...sat.formula import Not, P
from ._common import (
    Rules,
    const_key,
    facts,
    pattern_key,
)
from .core import ipi_rules, ipi_split, pi_split

X, N = 0, 1
#: Slot of ``s`` in the template of ``exp(I*pi*c*s)``.
M = 2


def _x(spec):
    return (X, spec, True) if isinstance(spec, str) else (X, spec[0], spec[1])


def _n(spec):
    return (N, spec, True) if isinstance(spec, str) else (N, spec[0], spec[1])


def _table(R, rows):
    for prem, concl in rows:
        R.rule([_x(p) for p in prem], _n(concl))


def _equiv(R, cond, preds):
    """``cond -> (pred(node) <-> pred(arg))`` for each pred."""
    for pred in preds:
        R.equiv(cond, (N, pred, True), (X, pred, True))


def _unary(tag, gen, slots=None, units=None):
    """Template for a unary function: ``gen(R, c)`` fills ``R`` (``c`` is the
    constant argument or ``None``).  ``slots(x)`` may supply extra objects
    the rules refer to by index 2, 3, ... (``arg - 1`` for log); ``units(c,
    expr)`` may supply unit facts for a constant argument ``c``.  A node
    with another number of arguments gets no facts: ``log(x, b,
    evaluate=False)`` is ``log(x)/log(b)``, not ``log(x)`` (#191)."""
    def template(expr):
        if len(expr.args) != 1:
            return None
        x = expr.args[0]
        consts = {}
        key = [tag, None]
        if x.is_Atom and x.is_number:
            consts[X] = x
            key[1] = const_key(x)
        objs = [x, expr]
        if slots is not None:
            for obj in slots(x):
                i = len(objs)
                objs.append(obj)
                if obj.is_Atom and obj.is_number:
                    consts[i] = obj
                    key.append(const_key(obj))
                else:
                    key.append(None)

        def build():
            R = Rules()
            gen(R, consts.get(X))
            return R.rules

        out = facts(tuple(key), build, consts, tuple(objs), N)
        if units is not None and X in consts:
            return [out, *units(x, expr)]
        return out
    template.__name__ = tag + '_templates'
    # the module of the rules registers it (TemplateRegistry.register
    # tells a declared module's templates by their module)
    template.__module__ = gen.__module__
    return template


def shifted(x, c):
    """``x + c`` for a number ``c``, as a slot object."""
    # ``x + c`` rebuilds a sum from its terms: Add(y, -y, 1, evaluate=False)
    # - 1 is 0, but the argument is nan at y = oo (#184); a sum whose terms
    # rebuild to the same terms (in any order) is safe
    if x.is_Add:
        t = Add(*x.args)
        if not (t.is_Add and Counter(t.args) == Counter(x.args)):
            return Add(x, c, evaluate=False)
    return x + c


# ---------------------------------------------------------------------------
# exp: exp(I*pi*c*s); the rows of exp and log are in .exp_log
# ---------------------------------------------------------------------------

def _exp_ipi(gen):
    """Template for ``exp`` given the generator of its rows (``.wiring``);
    for ``x == I*pi*c*s`` (``c`` rational) the value is also a root of
    unity or on the unit circle, described in terms of ``s``
    (:func:`~.core.ipi_rules`)."""
    def template(expr):
        x = expr.args[0]
        consts = {}
        objs = [x, expr]
        ipi = None
        if x.is_Atom and x.is_number:
            consts[X] = x
            key = ('exp', const_key(x))
        else:
            split = ipi_split(x)
            if split is not None:
                c, s_ = split
                ipi = (c, s_ is not None)
                if s_ is not None:
                    objs.append(s_)
                    if s_.is_Atom and s_.is_number:
                        consts[M] = s_
            key = ('exp', None, ipi, const_key(objs[M]) if M in consts else None)

        def build():
            R = Rules()
            gen(R, consts.get(X))
            if ipi is not None:
                c, has_s = ipi
                ipi_rules(R.rule, c, M if has_s else None, N)
            return R.rules

        return facts(key, build, consts, tuple(objs), N)
    template.__name__ = 'exp_templates'
    template.__module__ = gen.__module__
    return template


# ---------------------------------------------------------------------------
# re and im of floor / ceiling; the rows of floor, ceiling and factorial are
# in .integer_funcs, those of re and im in .complex_parts
# ---------------------------------------------------------------------------

def _parts_of_round_rules():
    # slots: 0 the argument y of floor/ceiling, 1 floor(y), 2 re(...) or im(...)
    R = Rules()
    R.rule([(0, 'finite', True)], (2, 'integer', True))
    return R.rules


def parts_of_round_templates(expr):
    """``re`` and ``im`` of ``floor(y)`` or ``ceiling(y)`` for finite ``y``
    are integers: SymPy rounds each part (``floor(y) = floor(re(y)) +
    I*floor(im(y))``), so the value is a Gaussian integer.  The vocabulary
    has no Gaussian-integer predicate, hence the rule looks through one
    level of structure.  Registered for ``re`` and ``im`` after their rows
    (``wiring.AFTER_ROWS``)."""
    r = expr.args[0]
    if not isinstance(r, (floor, ceiling)):
        return None
    y = r.args[0]
    consts = {0: y} if y.is_Atom and y.is_number else {}
    key = ('parts_of_round', const_key(y) if consts else None)
    return facts(key, _parts_of_round_rules, consts, (y, r, expr), 2)


# ---------------------------------------------------------------------------
# trigonometric: sin(pi*c*s), cos(pi*c*s), and asin(c), acos(c) for a
# number c (wiring.UNIT_INTERVAL); the rows of sin, cos, tan, cot, sec and
# csc are in .trig, those of the inverse functions in .inverse
# ---------------------------------------------------------------------------

_TRANSCENDENTAL = (('algebraic', ('zero', False)), 'transcendental')

#: Slot of ``s`` in the templates of ``sin(pi*c*s)`` and ``cos(pi*c*s)``.
PS = 2


def _pi_trig_rules(R, cos_, c, has_s):
    """Rules for ``N == sin(pi*c*s)`` (``cos_``: ``cos(pi*c*s)``), ``c``
    rational, ``s`` in slot ``PS`` (``has_s`` False: ``s == 1``).  The
    value is algebraic for a rational ``c*s``; for a number ``c`` its sign
    is that of ``sin(pi*r)`` with ``r == c mod 2`` (``c + 1/2`` for cos)."""
    if not has_s:
        R.rule([], (N, 'algebraic', True))
        r = (c + S.Half if cos_ else c) % 2  # sympy-boundary: c Rational
        if r.is_integer:  # sympy-boundary: r Rational
            R.rule([], (N, 'zero', True))
        else:
            if r.q == 2:
                R.rule([], (N, 'odd', True))  # sin(pi/2) == 1
            R.rule([], (N, 'positive' if r < 1 else 'negative', True))
        return
    R.rule([(PS, 'rational', True)], (N, 'algebraic', True))
    integer = c.is_integer  # sympy-boundary: c Rational
    half = not integer and c.q == 2
    if not cos_:
        if integer:
            R.rule([(PS, 'integer', True)], (N, 'zero', True))
        elif half:
            R.rule([(PS, 'even', True)], (N, 'zero', True))
            R.rule([(PS, 'odd', True)], (N, 'odd', True))
        return
    if integer:
        R.rule([(PS, 'integer', True)], (N, 'odd', True))
        if c.p % 2 == 0:
            R.rule([(PS, 'integer', True)], (N, 'positive', True))
        else:
            R.rule([(PS, 'even', True)], (N, 'positive', True))
            R.rule([(PS, 'odd', True)], (N, 'negative', True))
    elif half:
        R.rule([(PS, 'odd', True)], (N, 'zero', True))
        R.rule([(PS, 'even', True)], (N, 'odd', True))


def _pi_trig(tag, gen, cos_, split_=pi_split, plain=None):
    """Template for ``sin``, ``cos`` or ``cosh``: :func:`_unary`, and for an argument
    ``pi*c*s`` (:func:`~.core.pi_split`) also :func:`_pi_trig_rules`.
    ``cosh`` passes :func:`~.core.ipi_split` (``cosh(I*pi*c*s) ==
    cos(pi*c*s)``) and its own ``plain`` template."""
    if plain is None:
        plain = _unary(tag, gen)

    def template(expr):
        split = split_(expr.args[0]) if len(expr.args) == 1 else None
        if split is None:
            return plain(expr)
        c, s_ = split
        objs = [expr.args[0], expr]
        consts = {}
        if s_ is not None:
            objs.append(s_)
            if s_.is_Atom and s_.is_number:
                consts[PS] = s_
        key = (tag, None, 'pi', c, s_ is not None, const_key(s_) if consts else None)

        def build():
            R = Rules()
            gen(R, None)
            _pi_trig_rules(R, cos_, c, s_ is not None)
            return R.rules

        return facts(key, build, consts, tuple(objs), N)
    template.__name__ = tag + '_templates'
    template.__module__ = gen.__module__
    return template


def _in_unit_interval_units(kind):
    """Unit facts for ``asin(c)``/``acos(c)`` with a rational or float ``c``
    (exact comparisons): real on [-1, 1], else ``+-pi/2 -+ I*acosh|c|``
    or ``I*acosh(c)`` / ``pi - I*acosh|c|``."""
    def units(c, expr):
        if not (c.is_Rational or c.is_Float):
            return []
        out = [P('finite', expr), P('complex', expr)]
        if -1 <= c <= 1:
            out.append(P('real', expr))
            if kind == 'acos':
                out.append(P('positive' if c < 1 else 'zero', expr))
            else:
                out.append(P('positive' if c > 0 else 'negative' if c < 0 else 'zero', expr))
        else:
            out.append(Not(P('extended_real', expr)))
            if kind == 'acos' and c > 1:
                out.append(P('imaginary', expr))
            else:
                out.append(Not(P('imaginary', expr)))
        return out
    return units


# ---------------------------------------------------------------------------
# hyperbolic: cosh(I*pi*c*s) and cosh(r + I*pi*c*s); the rows of sinh,
# cosh, tanh, coth, sech and csch are in .hyperbolic
# ---------------------------------------------------------------------------

#: Slots of the ``cosh(r + I*pi*c*s)`` template: ``r`` and ``s``.
CR, CS = 2, 3


def _cosh_shift_rules(R, c, has_s):
    """``N == cosh(r + I*pi*c*s) == (-1)**(c*s)*cosh(r)`` (``c`` integer;
    ``has_s`` False: ``s == 1``) for an integer ``c*s``: positive for a real
    ``r`` and an even ``c*s``, negative for an odd one; real for an
    imaginary ``r`` (``cosh(I*t) == cos(t)``)."""
    if not has_s:
        integer, alts = [], [([], c.p % 2 == 0)]
    else:
        integer = [(CS, 'integer', True)]
        alts = [(integer, True)] if c.p % 2 == 0 else \
            [([(CS, 'even', True)], True), ([(CS, 'odd', True)], False)]
    for cond, even in alts:
        if even:
            R.rule([*cond, (CR, 'real', True)], (N, 'positive', True))
        else:
            # the argument is then not real; the premise keeps the block
            # total (the blocks below do not relate it to r)
            R.rule([*cond, (CR, 'real', True), (X, 'extended_real', False)],
                   (N, 'negative', True))
    R.rule([*integer, (CR, 'imaginary', True)], (N, 'real', True))


def _cosh_shift_split(arg):
    """``arg == r + I*pi*c*s`` with an integer ``c`` (the first such term of
    an ``Add``): ``(r, c, s)``, ``s`` None when there are no other factors;
    else None.  ``r`` must rebuild from the other terms (no cancellation:
    ``Add(y, -y, 2*I*pi*n, evaluate=False)`` is nan at ``y = oo``, #184)."""
    if not arg.is_Add:
        return None
    terms = list(arg.args)
    for i, t in enumerate(terms):
        split = ipi_split(t)
        if split is None or not split[0].is_integer:  # sympy-boundary: c Rational
            continue
        others = terms[:i] + terms[i + 1:]
        r = others[0] if len(others) == 1 else Add(*others)
        if len(others) > 1 and not (r.is_Add and Counter(r.args) == Counter(others)):
            return None
        return r, split[0], split[1]
    return None


def _cosh_shift(gen):
    """Template for ``cosh`` given the generator of its rows (``.wiring``):
    :func:`_unary`, for ``cosh(r + I*pi*c*s)`` also :func:`_cosh_shift_rules`
    (on ``r``: a ``cosh(r)`` slot with the facts of the node would not be
    total, the blocks below do not relate it to the argument)."""
    plain = _unary('cosh', gen)

    def template(expr):
        split = _cosh_shift_split(expr.args[0]) if len(expr.args) == 1 else None
        if split is None:
            return plain(expr)
        r, c, s_ = split
        objs = [expr.args[0], expr, r]
        if s_ is not None:
            objs.append(s_)
        consts = {i: obj for i, obj in enumerate(objs)
                  if i >= CR and obj.is_Atom and obj.is_number}
        key = ('cosh', None, 'shift', c, s_ is not None,
               *(const_key(consts[i]) if i in consts else None for i in (CR, CS)))

        def build():
            R = Rules()
            gen(R, None)
            _cosh_shift_rules(R, c, s_ is not None)
            return R.rules

        return facts(key, build, consts, tuple(objs), N)
    template.__name__ = 'cosh_templates'
    template.__module__ = gen.__module__
    return template


def nary(tag, gen, slots=None, arity=None):
    """Template for a function of fixed arity: ``gen(R, n)`` fills ``R``
    with rules over the arguments ``0 .. n-1``, the node ``n`` and the
    objects ``slots(args)`` from ``n + 1`` on.  With ``arity`` (a number,
    or a tuple of them), a node with another number of arguments gets no
    facts (``gen`` holds for those numbers only: the rows of
    :func:`._rows.rules`)."""
    arities = arity if isinstance(arity, tuple) else (arity,)

    def template(expr):
        args = expr.args
        if arity is not None and len(args) not in arities:
            return None
        objs = (*args, expr) + (tuple(slots(args)) if slots is not None else ())
        consts = {k: o for k, o in enumerate(objs)
                  if k != len(args) and o.is_Atom and o.is_number}
        n = len(args)

        def build():
            R = Rules()
            gen(R, n)
            return R.rules

        # keyed on the arity too: two arities can give as many objects
        # (LambertW(x, k) and a three-argument node built around the check)
        return facts(pattern_key((tag, n), len(objs), consts), build, consts, objs, n)
    template.__name__ = tag + '_templates'
    # the module of the rules registers it (TemplateRegistry.register
    # tells a declared module's templates by their module)
    template.__module__ = gen.__module__
    return template
