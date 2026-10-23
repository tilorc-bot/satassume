"""No fact of the rows is lost without a visible change to
``tests/_rows_baseline.py`` (#249).

The rows (``satassume/knowledge/templates/<family>.py``) were shown to
entail exactly the legacy generators they replaced, plus the facts they
added (the equivalence tests, removed with the legacy copies).  Their
clauses then are frozen in ``tests/_rows_baseline.py``: for every function
and number of arguments, the clauses over the basis that its registered
template gives for the node ``head(x0, ..., x(n-1))`` of plain symbols,
each slot named by its object (``x0``, ``x0 - 1``, the node); for ``Pow``,
whose rows have shapes (``templates/power.py``, #294), those of one node of
each shape and of constants that decide the rows of a constant
(:func:`pow_nodes`); for ``Max``, ``Min`` and ``Piecewise``, whose rows have
a star (``templates/selection.py``, #299), those of nodes of 1 to 5 values
and of a constant value (:func:`selection_nodes`); for ``Mul`` (rows with a
star and of a coefficient, ``templates/mul.py``), those of products of 2 to
7 factors, of a coefficient and a factor, and of two of SymPy's products
(:func:`mul_nodes`); for ``Add`` (rows with a star, ``templates/add.py``),
those of sums of 2 to 7 terms, of a constant and a term, and of the sums
of a special shape (:func:`add_nodes`).  This test
checks that the current templates, with the rule base on each slot, entail
every frozen clause, so a row dropped or weakened by mistake fails here;
``tests/test_rows_numeric.py`` checks that each rule is true, which this
does not.

A fact removed on purpose is removed from the baseline too:

    python tests/test_rows_baseline.py --write

and the diff of ``tests/_rows_baseline.py`` shows which clauses are gone.
Added facts need no new baseline (it is only the floor); writing one
records them.
"""
import os
import pprint
import sys

import pytest

pytest.importorskip("sympy")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sympy import (  # noqa: E402
    Add, Basic, E, Float, Function, GoldenRatio, I, Mul, Piecewise, Pow, Rational, S, Symbol, exp,
    oo, pi, zoo,
)
from sympy.functions.elementary.piecewise import ExprCondPair  # noqa: E402

from _rows_templates import compiled, rows_templates  # noqa: E402
from satassume.knowledge.rules import BASIS, BASIS_INDEX, RULE_CLAUSES  # noqa: E402
from satassume.knowledge.templates import ROW_FAMILIES  # noqa: E402
from satassume.knowledge.templates._compiled_rows import FAMILIES  # noqa: E402
from satassume.knowledge.templates.wiring import _declared  # noqa: E402
from satassume.sat.solver import Solver  # noqa: E402

OUT = os.path.join(HERE, "_rows_baseline.py")

HEADER = '''"""The clauses of the rows' templates, frozen (#249): written by
``python tests/test_rows_baseline.py --write``; read by
``tests/test_rows_baseline.py``, which checks the current templates still
entail them.  Do not edit by hand.

``BASELINE``: ``((family, function name, n, slots, clauses), ...)``: the
slots named by their objects for the node ``head(x0, ..., x(n-1))`` (for
``Pow``, ``Max``, ``Min``, ``Piecewise``, ``Mul`` and ``Add``, ``n`` is the text
of the node), and each clause a tuple of literals ``(slot, basis predicate,
negated)``.
"""
'''


def _node(h, n):
    args = [Symbol(f'x{i}') for i in range(n)]
    try:
        return h(*args, evaluate=False)
    except TypeError:
        # betainc_regularized.__new__ takes no keyword
        return Function.__new__(h, *args, evaluate=False)


def pow_nodes(head=Pow):
    """The nodes of ``Pow`` whose clauses are frozen: a rule of its rows
    with a shape is about the nodes of that shape only, and a rule about a
    constant (``number``) gets its terms (``Abs(number) - 1``, ``number/2``)
    decided at the constant.  So: ``x0**x1``, ``x0**x0``, the numbers of
    the shapes (``x0**-1``, ``x0**1``, ``E**x1``, ``(-1)**x1``, ``1**x1``,
    ``I**x1``, ``(-I)**x1``), ``exp(x2)**x1``, constant bases (``|b|`` above
    and below 1, negative, algebraic irrational, transcendental) and
    constant exponents (``k/2``, ``1/q``, ``-1/q``, 2 and 0 mod 4, 2 or
    more, algebraic irrational, the infinities), each unevaluated."""
    x0, x1, x2 = Symbol('x0'), Symbol('x1'), Symbol('x2')
    bases = (E, S.NegativeOne, S.One, I, -I, exp(x2), S(2), S(-2), S(3), S.Half, -S.Half,
             Rational(3, 2), Rational(-3, 2), GoldenRatio, pi)
    exps = (S.NegativeOne, S.One, S(2), S(-2), S(3), S(4), S(6), S.Half, -S.Half,
            Rational(3, 2), Rational(1, 3), Rational(-1, 3), Rational(2, 3), GoldenRatio, pi,
            oo, -oo)
    return (Pow(x0, x1, evaluate=False), Pow(x0, x0, evaluate=False),
            *(Pow(b, x1, evaluate=False) for b in bases),
            *(Pow(x0, e, evaluate=False) for e in exps))


def selection_nodes(head):
    """The nodes of ``Max``, ``Min`` or ``Piecewise`` whose clauses are
    frozen: of 1 to 5 values (wiring leaves out the negations of the
    derived conjunctions from 3 or 5 values), and of two values one of
    which is a constant (``2``, ``-1``, ``1/2``, ``pi``, ``oo``, ``-oo``), each
    with every value kept (a node of one value built with ``Basic.__new__``;
    a ``Piecewise`` has the conditions ``y0 > 0``, ... and a final
    ``True``)."""
    xs = [Symbol(f'x{i}') for i in range(5)]

    def node(values):
        if head is Piecewise:
            return Basic.__new__(Piecewise, *(ExprCondPair(v, Symbol(f'y{i}') > 0)
                                              for i, v in enumerate(values[:-1])),
                                 ExprCondPair(values[-1], S.true))
        return Basic.__new__(head, *values)
    return (*(node(xs[:n]) for n in range(1, 6)),
            *(node([xs[0], c]) for c in (S(2), S.NegativeOne, S.Half, pi, oo, -oo)))


def mul_nodes(head=Mul):
    """The nodes of ``Mul`` whose clauses are frozen: of 2 to 7 factors
    (around the limits ``at_most`` 2, 4 and 6), a coefficient and a factor
    (a positive, a negative, a rational, half an odd integer, a float,
    ``-1``, an infinity, and ``pi``, which is no coefficient), each with
    every factor kept (``evaluate=False``), and SymPy's ``3*x0*x1`` (with the
    block of its factor set ``(3, x0*x1)``) and ``x0/x1**2`` (with
    ``a/v**k``), ``I*pi*x0/3`` (with the factor set of ``I*pi*c*s``); and of
    12 and 32 factors (up to the ``at_most=32`` of the rows that past it are
    one formula, which is not frozen here), so that a narrower row is seen
    (a node of one factor, which SymPy does not build or print, is in
    ``tests/test_mul_rows.py``)."""
    xs = [Symbol(f'x{i}') for i in range(32)]
    coefficients = (S(2), S(-3), S.Half, Rational(-3, 2), Float(2.5), S.NegativeOne, oo, pi)
    return (*(head(*xs[:n], evaluate=False) for n in range(2, 8)),
            *(head(c, xs[0], evaluate=False) for c in coefficients),
            3*xs[0]*xs[1], xs[0]/xs[1]**2, I*pi*xs[0]/3,
            *(head(*xs[:n], evaluate=False) for n in (12, 32)))


def add_nodes(head=Add):
    """The nodes of ``Add`` whose clauses are frozen: of 2 to 7 terms
    (around the limits ``at_most`` 3 and 6), a constant and a term (an
    integer, a rational, a float, ``pi``, ``I``, ``oo``, ``-oo``, ``zoo``),
    each with every term kept (``evaluate=False``), and SymPy's sums of a
    special shape (half-integer coefficients, ``c0 + c1*u``, ``c0 +
    c1/v``, ``I*(c_1*x_1 + ...)``); and of 12 and 32 terms (up to the
    ``at_most=32`` of the rows that past it are one formula, which is not
    frozen here), and ``oo`` and 5 or 6 terms (around the ``at_most=6`` of
    the rows of a constant), so that a narrower row is seen (a node of one
    term, which SymPy does not build or print, is in
    ``tests/test_add_rows.py``)."""
    xs = [Symbol(f'x{i}') for i in range(32)]
    constants = (S(2), S(-3), S.Half, Float(2.5), pi, I, oo, -oo, zoo)
    return (*(head(*xs[:n], evaluate=False) for n in range(2, 8)),
            *(head(c, xs[0], evaluate=False) for c in constants),
            xs[0]/2 + xs[1]/2 + S.Half, 2*xs[0] + 3, 1 + 2/xs[0], I*xs[0] - 2*I*xs[1] + I,
            *(head(*xs[:n], evaluate=False) for n in (12, 32)),
            *(head(oo, *xs[:n], evaluate=False) for n in (5, 6)))


#: the families whose rows have shapes or a star, each with the nodes of
#: its baseline
SHAPED = {'power': pow_nodes, 'selection': selection_nodes, 'mul': mul_nodes, 'add': add_nodes}


def functions():
    """``(family, name, head, n, node)`` for each function of the compiled
    rows and each number ``n`` of its arguments, ``node`` the node of
    plain symbols; for a family of :data:`SHAPED`, for each of its nodes,
    ``n`` the text of the node.  ``head`` and ``node`` are None where this
    SymPy lacks the function (``owens_t`` before SymPy 1.15)."""
    declared = {}
    for family, fns in ROW_FAMILIES:
        for fn in fns:
            name = fn.rpartition(':')[2] if isinstance(fn, str) else fn.__name__
            declared[family, name] = _declared(fn)
    out = []
    for family, fns in FAMILIES:
        for name, _, _, specs, *_ in fns:
            head = declared[family, name]
            if family in SHAPED:
                out += [(family, name, head, str(e), e) for e in SHAPED[family](head)]
            else:
                out += [(family, name, head, n, head and _node(head, n)) for n, _ in specs]
    return out


def clauses(family, head, node):
    """``(slots, clauses)`` the template of ``head``'s rows gives for
    ``node``."""
    cs, _ = compiled(rows_templates((head,), family), node)
    slots, out = [], set()
    for c in cs:
        names = [None if o is None else str(o) for o in c.objs]
        for name in names:
            # no slot for one Pow's template leaves empty
            if name is not None and name not in slots:
                slots.append(name)
        for lits, _, _ in c.pattern.clauses:
            out.add(tuple(sorted((slots.index(names[k]), BASIS[i], neg) for k, i, neg in lits)))
    return tuple(slots), tuple(sorted(out))


def lost(slots, frozen, current_slots, current):
    """The clauses of ``frozen`` (over ``slots``) that ``current`` (over
    ``current_slots``) with the rule base on each slot does not entail.  A
    slot the current template no longer has is a fresh one."""
    names = list(current_slots) + [s for s in slots if s not in current_slots]
    where = [names.index(s) for s in slots]

    def var(k, p):
        return k * len(BASIS) + BASIS_INDEX[p] + 1
    s = Solver()
    for k in range(len(names)):
        for cl in RULE_CLAUSES:
            s.add_clause([(1 if l > 0 else -1) * (k * len(BASIS) + abs(l)) for l in cl])
    for cl in current:
        s.add_clause([-var(k, p) if neg else var(k, p) for k, p, neg in cl])
    # a clause is entailed when its negation is unsatisfiable
    return [cl for cl in frozen
            if s.solve([var(where[k], p) if neg else -var(where[k], p) for k, p, neg in cl])]


def baseline():
    return tuple((family, name, n, *clauses(family, head, node))
                 for family, name, head, n, node in functions() if head is not None)


def _frozen():
    try:
        from _rows_baseline import BASELINE
    except ImportError:
        # not written yet (--write): every function is missing from it
        return ()
    return BASELINE


def _id(e):
    return f"{e[1]}/{e[2]}"


@pytest.mark.parametrize("entry", _frozen(), ids=_id)
def test_the_rows_entail_the_baseline(entry):
    family, name, n, slots, frozen = entry
    head, node = {(f, nm, k): (h, e) for f, nm, h, k, e in functions()}.get((family, name, n),
                                                                           (None, None))
    if head is None:
        pytest.skip(f"{name} is not in this SymPy")
    current_slots, current = clauses(family, head, node)
    gone = lost(slots, frozen, current_slots, current)
    assert not gone, (f"{name}/{n} no longer gives {len(gone)} clause(s) of tests/_rows_baseline.py "
                      f"over {slots}: {gone[:5]}; if on purpose, run "
                      "python tests/test_rows_baseline.py --write")


def test_every_function_of_the_rows_is_in_the_baseline():
    # a function added to the rows needs a baseline written (--write)
    frozen = {(e[0], e[1], e[2]) for e in _frozen()}
    assert {(f, nm, n) for f, nm, h, n, _ in functions() if h is not None} <= frozen


def test_the_nodes_of_pow_have_its_shapes():
    # each shape of Pow's rows and each premise on a constant is decided by
    # some node of the baseline (an entry of its own)
    from satassume.knowledge.templates import wiring
    from satassume.knowledge.templates._rows import generator
    [(name, arity, terms, specs)] = dict(FAMILIES)['power']
    rules = generator(name, arity, terms, specs, 'power').specs[2]
    nodes = pow_nodes()
    assert len({str(e) for e in nodes}) == len(nodes)
    for shape in {r[2] for r in rules if len(r) > 2}:
        assert any(wiring.matches(shape, e.args, {i for i, a in enumerate(e.args)
                                                  if a.is_Atom and a.is_number})
                   for e in nodes), shape


def test_a_lost_clause_is_reported():
    from sympy import sin
    slots, current = clauses("trig", sin, _node(sin, 1))
    assert slots == ('x0', 'sin(x0)')
    # zero(x0) -> zero(sin(x0)) is entailed, zero(x0) -> extended_positive(sin(x0)) is not
    zero = ((0, 'zero', True), (1, 'zero', False))
    positive = ((0, 'zero', True), (1, 'extended_positive', False))
    assert lost(slots, (zero, positive), slots, current) == [positive]
    # nor anything about a slot the current template lacks
    assert lost(('x0', 'x0 - 1'), (((1, 'zero', True), (0, 'zero', False)),), slots, current)


def main(argv):
    if "--write" in argv:
        # a function this SymPy lacks gets compile_rows.py's stand-in, so
        # the baseline is the same on every SymPy
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
        from compile_rows import stand_ins
        stand_ins(ROW_FAMILIES)
    text = HEADER + "\nBASELINE = " + pprint.pformat(baseline(), width=99) + "\n"
    if "--write" in argv:
        with open(OUT, "w") as f:
            f.write(text)
    else:
        print(__doc__)


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(HERE))
    main(sys.argv[1:])
