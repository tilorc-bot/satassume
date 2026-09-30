"""Soundness verification of relational ``ask`` (theories, guards, links).

Differential fuzzing of :func:`satassume.sympy_api.ask` against concrete
models.  Queries mix unary predicates (``Q.positive``, ``Q.real``,
``Q.zero``, ``Q.integer``, ``Q.nonzero``, ``Q.negative``), relations
(``Q.lt/le/gt/ge/eq/ne``, the Relationals ``<`` ... ``Ne`` and
``Q.is_true(rel)``) and Boolean connectives over two or three symbols with
linear (sometimes bilinear) terms.  A definite answer must agree with every
concrete point where the assumptions hold; ``ValueError`` (inconsistent
assumptions) must not be raised when some point satisfies them.

The oracle evaluates atoms at a point itself; it never calls the engine or
SymPy's ``ask``:

* symbols take rational values and some non-real (``I``, ``1 + I``) and
  infinite (``oo``, ``-oo``, ``zoo``) ones, optionally also ``nan``;
* unary predicates follow SymPy's new-assumption meaning (``real`` is finite
  real, ``nonzero`` is real and not zero, ...);
* order relations are over the extended reals and assert that their
  sides are extended reals (``satassume.relations``, "Meaning"):
  ``a < b`` is compared when both sides are finite reals or ``oo``/``-oo``,
  and is false when a side is no extended real (non-real, ``zoo``,
  ``nan``); a value whose extended-realness SymPy cannot tell leaves it
  free.  ``a <= b`` is ``extended_real(a) & extended_real(b) & ~(b < a)``
  (not the plain negation of the reversed ``<``);
* ``Eq`` compares values and is False on ``nan`` (``Eq(nan, nan)``, so
  ``Q.eq(x - z, y - z)`` is False at ``x = y = z = oo``); structurally
  identical values are equal, and values the oracle cannot classify are
  free.

The fuzzer with an undefined function (``test_fuzz_eq_nan``) draws terms
such as ``f(x)*z``, ``x - z`` and ``f(1)*f(y)`` and checks the answers
against random models: symbol values from ``0, 1, -1, oo, -oo, zoo, I``
and ``nan``, and ``f`` and ``g`` random tables from values to values, so
that ``nan`` arises from ``0*oo``, ``oo - oo`` and the functions themselves.

Set ``VERIFY_FUZZ_EXAMPLES`` to raise the example count of the default
fuzzers (default 60), and ``VERIFY_SLOW=1`` to run the slow 2000-example
fuzzer (marked ``slow``).
"""
from __future__ import annotations

import itertools
import os

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from sympy import (Eq, Ge, Gt, I, Le, Lt, Ne, Q, Rational, S, Symbol,
                   Function, nan, oo, symbols, zoo)
from sympy.logic.boolalg import And, Equivalent, Implies, Not, Or

from satassume.engine import Engine
from satassume.sympy_api import ask

N_EXAMPLES = int(os.environ.get("VERIFY_FUZZ_EXAMPLES", "60"))
SLOW = os.environ.get("VERIFY_SLOW") == "1"
FUZZ = settings(max_examples=N_EXAMPLES, deadline=None,
                suppress_health_check=[HealthCheck.too_slow,
                                       HealthCheck.data_too_large,
                                       HealthCheck.filter_too_much])

X, Y, Z = symbols("x y z")
SYMS = (X, Y, Z)
UNARY = ("positive", "real", "zero", "integer", "nonzero", "negative")
RELS = ("lt", "le", "gt", "ge", "eq", "ne")
REL_CLASS = {"lt": Lt, "le": Le, "gt": Gt, "ge": Ge, "eq": Eq, "ne": Ne}

VALUES_2 = [S(-2), S(-1), S.Zero, Rational(1, 2), S.One, S(2), Rational(-1, 3),
            S(3), I, 1 + I, oo, -oo, zoo]
VALUES_3 = [S(-1), S.Zero, Rational(1, 2), S.One, S(2), I, oo, -oo, zoo]

# symbols with old-style assumptions and the values they may take
OLD_SYMBOLS = [
    (Symbol("p", positive=True), [Rational(1, 2), S.One, S(2)]),
    (Symbol("n", integer=True), [S(-1), S.Zero, S.One, S(2)]),
    (Symbol("r", real=True), [S(-1), S.Zero, Rational(1, 2), S(2)]),
    (Symbol("e", extended_real=True), [S(-1), S.Zero, S.One, oo, -oo]),
    (Symbol("c", complex=True), [S.Zero, S.One, I, 1 + I, S(-1)]),
    (Symbol("q", nonnegative=True), [S.Zero, Rational(1, 2), S(2)]),
    (Symbol("k", extended_positive=True), [S.One, S(2), oo]),
    (Symbol("f", finite=True), [S.Zero, S.One, I, S(-2)]),
    (Symbol("i", imaginary=True), [I, -2 * I]),
    (Symbol("m", negative=True, integer=True), [S(-1), S(-2)]),
    (Symbol("w", nonzero=True), [S(-1), Rational(1, 2), S(3)]),
]


# --------------------------------------------------------------------------
# concrete oracle
# --------------------------------------------------------------------------

def _kind(v):
    if v is S.NaN:
        return "nan"
    if v.is_Rational:
        return "rat"
    if v in (S.Infinity, S.NegativeInfinity):
        return "inf"
    if v is S.ComplexInfinity:
        return "zoo"
    if v.is_number and v.is_finite and v.is_real is False:
        return "cplx"
    if v.is_number and v.is_finite and v.is_real:
        return "realnum"
    return "other"


def _unary(pred, v):
    k = _kind(v)
    if k == "nan":
        return False
    if k == "other":
        # e.g. oo + I: every predicate here implies a finite real
        return False if (v.is_finite is False or v.is_real is False) else None
    real = k in ("rat", "realnum")
    if pred == "real":
        return real
    if not real:
        return False
    return {"positive": v > 0, "negative": v < 0, "zero": v == 0,
            "nonzero": v != 0, "integer": v.is_integer}[pred] == True  # noqa: E712


def _ext(v):
    """Is the value ``v`` an extended real (None: unknown)?"""
    k = _kind(v)
    if k in ("rat", "realnum", "inf"):
        return True
    if k in ("nan", "zoo", "cplx"):
        return False
    return v.is_extended_real


def _lt(a, b):
    ea, eb = _ext(a), _ext(b)
    if ea is False or eb is False:
        return False
    if ea and eb:
        return bool(a < b)
    return None


def _eq(a, b):
    ka, kb = _kind(a), _kind(b)
    if ka == "nan" or kb == "nan":
        return False                  # Eq(nan, nan) is False
    if a == b:
        return True
    if ka == "other" or kb == "other":
        return None
    return bool(a == b)


# formula AST: ("u", pred, term) | ("r", op, a, b, style) | ("not", f)
#              | (op, f, g) for op in and/or/imp/eqv

def _atom_key(op, a, b):
    """(normalised atom, negated) for ``lt``/``gt``/``eq``/``ne``; for
    ``le``/``ge`` the triple of atoms ``(lt(b, a), ext(a), ext(b))`` of
    ``a <= b`` (``ge``: swapped) and None."""
    if op == "lt":
        return ("lt", a, b), False
    if op == "gt":
        return ("lt", b, a), False
    if op in ("le", "ge"):
        if op == "ge":
            a, b = b, a
        return (("lt", b, a), ("ext", a), ("ext", b)), None
    a, b = sorted((a, b), key=lambda e: e.sort_key())
    return ("eq", a, b), op == "ne"


def _atoms(f, acc):
    if f[0] == "u":
        acc.add(f)
    elif f[0] == "r":
        key, neg = _atom_key(f[1], f[2], f[3])
        if neg is None:
            acc.update(key)
        else:
            acc.add(key)
    else:
        for g in f[1:]:
            _atoms(g, acc)
    return acc


def _eval(f, env):
    tag = f[0]
    if tag == "u":
        return env[f]
    if tag == "r":
        key, neg = _atom_key(f[1], f[2], f[3])
        if neg is None:
            lt, ea, eb = key
            return env[ea] and env[eb] and not env[lt]
        return env[key] != neg
    if tag == "not":
        return not _eval(f[1], env)
    a, b = _eval(f[1], env), _eval(f[2], env)
    return {"and": a and b, "or": a or b, "imp": (not a) or b, "eqv": a == b}[tag]


def _worlds(fs, point):
    atoms = sorted(set().union(*(_atoms(f, set()) for f in fs)), key=str)
    fixed, free = {}, []
    for at in atoms:
        if at[0] == "u":
            v = _unary(at[1], S(at[2]).xreplace(point))
        elif at[0] == "ext":
            v = _ext(S(at[1]).subs(point))
        else:
            a, b = S(at[1]).subs(point), S(at[2]).subs(point)
            v = _lt(a, b) if at[0] == "lt" else _eq(a, b)
        if v is None:
            free.append(at)
        else:
            fixed[at] = v
    for bits in itertools.product((False, True), repeat=len(free)):
        env = dict(fixed)
        env.update(zip(free, bits))
        yield env


def _points(domains):
    syms = list(domains)
    for vals in itertools.product(*(domains[s] for s in syms)):
        yield dict(zip(syms, vals))


def refute(prop, assum, answer, domains):
    """A point (and atom values) where ``assum`` holds and ``prop`` differs
    from ``answer`` (``"inconsistent"``: where ``assum`` holds), or None."""
    for point in _points(domains):
        for env in _worlds([prop, assum], point):
            if not _eval(assum, env):
                continue
            if answer == "inconsistent" or _eval(prop, env) != answer:
                return point, env
    return None


def to_sympy(f):
    tag = f[0]
    if tag == "u":
        return getattr(Q, f[1])(f[2])
    if tag == "r":
        _, op, a, b, style = f
        if style == "Q":
            return getattr(Q, op)(a, b)
        rel = REL_CLASS[op](a, b)
        return Q.is_true(rel) if style == "is_true" else rel
    if tag == "not":
        return Not(to_sympy(f[1]))
    cls = {"and": And, "or": Or, "imp": Implies, "eqv": Equivalent}[tag]
    return cls(to_sympy(f[1]), to_sympy(f[2]))


# --------------------------------------------------------------------------
# strategies
# --------------------------------------------------------------------------

COEFFS = [0, 0, 1, 1, -1, 2, -2, Rational(1, 2)]


@st.composite
def terms(draw, syms, nonlinear=True):
    t = S(draw(st.sampled_from([0, 0, 0, 1, -1, 2])))
    for s in syms:
        t += draw(st.sampled_from(COEFFS)) * s
    if nonlinear and draw(st.integers(0, 9)) == 0:
        t += draw(st.sampled_from(syms)) * draw(st.sampled_from(syms))
    if t.is_number:
        t += draw(st.sampled_from(syms))
    return t


@st.composite
def relations(draw, syms, nonlinear=False):
    op = draw(st.sampled_from(RELS))
    a, b = draw(terms(syms, nonlinear)), draw(terms(syms, nonlinear))
    style = draw(st.sampled_from(["Q", "Q", "rel", "is_true"]))
    if style != "Q":
        try:
            r = REL_CLASS[op](a, b)
        except TypeError:            # SymPy refuses x < y for non-real x
            r = S.true
        if r in (S.true, S.false):
            style = "Q"
    return ("r", op, a, b, style)


@st.composite
def unaries(draw, syms):
    return ("u", draw(st.sampled_from(UNARY)), draw(terms(syms, False)))


def formulas(syms, depth):
    atom = st.one_of(relations(syms, True), unaries(syms))
    if depth == 0:
        return atom
    sub = formulas(syms, depth - 1)
    return st.one_of(
        atom,
        st.tuples(st.just("not"), sub),
        st.tuples(st.sampled_from(["and", "or", "imp", "eqv"]), sub, sub))


@st.composite
def queries(draw, syms):
    """(proposition, assumptions): assumptions are a conjunction of a few
    relations and unary facts (sometimes a disjunction or a negation) plus
    optional realness facts on the symbols; the proposition is one atom or
    a small combination."""
    parts = []
    for _ in range(draw(st.integers(1, 3))):
        g = draw(st.one_of(relations(syms), relations(syms), unaries(syms)))
        if draw(st.integers(0, 6)) == 0:
            g = ("or", g, draw(relations(syms)))
        if draw(st.integers(0, 9)) == 0:
            g = ("not", g)
        parts.append(g)
    for s in syms:
        fact = draw(st.sampled_from([None, None, "real", "real", "integer", "positive"]))
        if fact:
            parts.append(("u", fact, s))
    assum = parts[0]
    for g in parts[1:]:
        assum = ("and", assum, g)
    prop = draw(st.one_of(relations(syms, True), unaries(syms), formulas(syms, 1)))
    return prop, assum


# --------------------------------------------------------------------------
# the check
# --------------------------------------------------------------------------

_shared = Engine()


def check(prop, assum, domains, engine=None):
    sp, sa = to_sympy(prop), to_sympy(assum)
    if sp in (S.true, S.false) or sa in (S.true, S.false):
        return None
    try:
        r = ask(sp, sa, engine=engine or _shared)
    except ValueError:
        r = "inconsistent"
    if r is None:
        return None
    cx = refute(prop, assum, r, domains)
    assert cx is None, (
        f"ask({sp}, {sa}) = {r} but the point {cx[0]} satisfies the "
        f"assumptions and refutes it (atom values {cx[1]})")
    return r


@st.composite
def plain_cases(draw):
    k = draw(st.sampled_from([1, 2, 2, 3]))
    syms = SYMS[:k]
    values = VALUES_2 if k < 3 else VALUES_3
    prop, assum = draw(queries(syms))
    return prop, assum, {s: values for s in syms}, draw(st.booleans())


@st.composite
def old_symbol_cases(draw):
    picks = draw(st.lists(st.sampled_from(OLD_SYMBOLS), min_size=1, max_size=2,
                          unique_by=lambda p: p[0]))
    domains = dict(picks)
    if draw(st.booleans()):
        domains[X] = [S(-1), S.Zero, Rational(1, 2), S(2), I, oo, -oo, zoo]
    syms = tuple(domains)
    prop, assum = draw(queries(syms))
    return prop, assum, domains, draw(st.booleans())


@FUZZ
@given(plain_cases())
def test_fuzz_plain_symbols(case):
    prop, assum, domains, fresh = case
    check(prop, assum, domains, Engine() if fresh else None)


@FUZZ
@given(old_symbol_cases())
def test_fuzz_old_style_symbols(case):
    prop, assum, domains, fresh = case
    check(prop, assum, domains, Engine() if fresh else None)


@FUZZ
@given(plain_cases())
def test_fuzz_symbols_may_be_nan(case):
    prop, assum, domains, fresh = case
    domains = {s: list(v) + [nan] for s, v in domains.items()}
    check(prop, assum, domains, Engine() if fresh else None)


@pytest.mark.slow
@pytest.mark.skipif(not SLOW, reason="slow soundness fuzzer: set VERIFY_SLOW=1")
@settings(max_examples=2000, deadline=None,
          suppress_health_check=list(HealthCheck))
@given(st.one_of(plain_cases(), old_symbol_cases()))
def test_fuzz_slow(case):
    prop, assum, domains, fresh = case
    check(prop, assum, domains, Engine() if fresh else None)


# --------------------------------------------------------------------------
# hand-picked edge cases (soundness only: None is always accepted)
# --------------------------------------------------------------------------

x, y, z = X, Y, Z
_EDGE = [
    # the guard: cancelling terms, infinite and non-real arguments
    (("r", "lt", x, x + 1, "Q"), ("u", "real", y)),
    (("r", "lt", x, x + 1, "Q"), ("r", "lt", x, y, "Q")),
    (("r", "lt", x, x, "Q"), ("u", "real", x)),
    (("r", "le", x, x, "Q"), ("r", "eq", x, y, "Q")),
    (("or", ("r", "le", x, y, "Q"), ("r", "gt", x, y, "Q")), ("u", "real", z)),
    (("r", "lt", x, 1, "Q"), ("r", "lt", x, 0, "Q")),
    (("r", "gt", x * y, 0, "Q"),
     ("and", ("u", "positive", x), ("u", "positive", y))),
    (("r", "lt", x * x, 0, "Q"), ("u", "real", x)),
    # unary links
    (("u", "positive", x), ("r", "gt", x, 0, "Q")),
    (("u", "positive", x), ("and", ("r", "gt", x, 0, "Q"), ("u", "real", x))),
    (("u", "nonzero", x), ("r", "lt", x, 0, "Q")),
    (("u", "zero", y), ("and", ("u", "zero", x), ("r", "eq", x, y, "Q"))),
    (("r", "gt", x, 0, "Q"), ("and", ("r", "eq", x, y, "Q"), ("u", "zero", y))),
    (("u", "real", x), ("r", "lt", x, 0, "Q")),
    (("r", "lt", 2 * x, 1, "Q"), ("u", "negative", x)),
    # equality sharing between EUF and LRA
    (("r", "eq", x + 1, y + 1, "Q"), ("r", "eq", x, y, "Q")),
    (("r", "eq", x, y, "Q"), ("r", "eq", x + 1, y + 1, "Q")),
    (("r", "eq", x, y, "Q"),
     ("and", ("r", "le", x, y, "Q"), ("r", "ge", x, y, "Q"))),
    (("r", "eq", x, y, "Q"),
     ("and", ("u", "zero", x - y), ("and", ("u", "real", x), ("u", "real", y)))),
    (("r", "eq", x, 1, "Q"), ("r", "eq", x * x, 1, "Q")),
    # Relationals and Q.is_true
    (("r", "lt", x, y, "is_true"), ("r", "lt", x, y, "Q")),
    (("r", "ne", x, y, "rel"), ("r", "lt", x, y, "rel")),
]


@pytest.mark.parametrize("prop, assum", _EDGE)
def test_edge_cases_are_sound(prop, assum):
    syms = sorted(set().union(*(to_sympy(f).free_symbols for f in (prop, assum))),
                  key=str)
    check(prop, assum, {s: VALUES_2 for s in syms}, Engine())


def test_non_rational_numbers_do_not_crash():
    xr = Symbol("xr", real=True)
    f = Function("f")
    for p, a in [
        (Q.le(oo, oo), True), (Q.lt(-oo, xr), True), (Q.eq(xr, oo), Q.positive(xr)),
        (Q.lt(xr, 0.1), Q.gt(xr, Rational(1, 10))), (Q.eq(xr, 0.5), Q.eq(xr, S.Half)),
        (Q.eq(1.0, 1), True), (Q.eq(S.NaN, S.NaN), True), (Q.eq(xr, S.NaN), True),
        (Q.lt(S.ImaginaryUnit, 1), True), (Q.eq(zoo, zoo), True),
        (Q.eq(f(xr), f(1)), Q.eq(xr, 1)), (Q.lt(xr + oo, 1), True),
    ]:
        ask(p, a, engine=Engine())   # any answer; must not raise


# --------------------------------------------------------------------------
# eq on terms that may be nan: congruence and reflexivity
# --------------------------------------------------------------------------

F, G = Function("f"), Function("g")
NAN_SYMBOL_VALUES = [S.Zero, S.One, S.NegativeOne, oo, -oo, zoo, I, nan]
NAN_F_VALUES = [S.Zero, S.One, S(2), oo, -oo, zoo, I, nan]
N_MODELS = 300


def _value(t, point, table, rng):
    """The value of ``t`` in the model ``point`` (symbols) and ``table``
    (``f`` and ``g``, filled lazily from ``rng``); SymPy's arithmetic gives nan."""
    if t.is_Symbol:
        return point[t]
    if t.is_Number:
        return t
    if t.func in (F, G):
        key = (t.func, _value(t.args[0], point, table, rng))
        if key not in table:
            table[key] = rng.choice(NAN_F_VALUES)
        return table[key]
    return t.func(*[_value(a, point, table, rng) for a in t.args])


def _nan_models(syms, seed):
    import random
    rng = random.Random(seed)
    for k in range(N_MODELS):
        point = {s: rng.choice(NAN_SYMBOL_VALUES) for s in syms}
        yield point, {}, rng


def _nan_atom(at, point, table, rng):
    if at[0] == "u":
        return _unary(at[1], _value(S(at[2]), point, table, rng))
    if at[0] == "ext":
        return _ext(_value(S(at[1]), point, table, rng))
    a = _value(S(at[1]), point, table, rng)
    b = _value(S(at[2]), point, table, rng)
    return _lt(a, b) if at[0] == "lt" else _eq(a, b)


def refute_nan(prop, assum, answer, syms, seed):
    """A model where ``assum`` holds and ``prop`` differs from ``answer``.
    A model with an atom the oracle cannot decide (``oo - I`` against
    ``oo``) is skipped: leaving such atoms free, independently of each
    other, could give an assignment no values have."""
    atoms = sorted(_atoms(prop, set()) | _atoms(assum, set()), key=str)
    for point, table, rng in _nan_models(syms, seed):
        env = {}
        for at in atoms:
            v = _nan_atom(at, point, table, rng)
            if v is None:
                break
            env[at] = v
        else:
            if not _eval(assum, env):
                continue
            if answer == "inconsistent" or _eval(prop, env) != answer:
                return point, table, env
    return None


@st.composite
def nan_terms(draw):
    base = st.sampled_from([X, Y, Z, F(X), F(Y), F(S.One), G(S.One), S.Zero, S.One])
    t = draw(base)
    for _ in range(draw(st.integers(0, 2))):
        op = draw(st.sampled_from(["add", "sub", "mul", "f"]))
        u = draw(base)
        t = {"add": lambda: t + u, "sub": lambda: t - u, "mul": lambda: t * u,
             "f": lambda: F(t)}[op]()
    return t


@st.composite
def nan_cases(draw):
    """Assumptions: equalities (often ``x = y``), disequalities and unary
    facts; the proposition: an equality of two terms, often one term with
    ``x`` and ``y`` swapped (congruence) or twice the same (reflexivity)."""
    parts = [("r", "eq", X, Y, "Q")] if draw(st.booleans()) else []
    for _ in range(draw(st.integers(0, 2))):
        kind = draw(st.sampled_from(["eq", "ne", "u"]))
        if kind == "u":
            parts.append(("u", draw(st.sampled_from(["real", "zero", "positive"])),
                          draw(nan_terms())))
        else:
            parts.append(("r", kind, draw(nan_terms()), draw(nan_terms()), "Q"))
    if not parts:
        parts.append(("r", "eq", draw(nan_terms()), draw(nan_terms()), "Q"))
    assum = parts[0]
    for g in parts[1:]:
        assum = ("and", assum, g)
    t = draw(nan_terms())
    shape = draw(st.sampled_from(["swap", "swap", "same", "any"]))
    if shape == "swap":
        u = t.xreplace({X: Y, Y: X})
    elif shape == "same":
        u = t
    else:
        u = draw(nan_terms())
    prop = ("r", draw(st.sampled_from(["eq", "ne"])), t, u, "Q")
    if draw(st.integers(0, 3)) == 0:
        prop = ("or", prop, ("r", "eq", draw(nan_terms()), draw(nan_terms()), "Q"))
    return prop, assum, draw(st.integers(0, 2**31)), draw(st.booleans())


def check_nan(prop, assum, seed, engine=None):
    sp, sa = to_sympy(prop), to_sympy(assum)
    if sp in (S.true, S.false) or sa in (S.true, S.false):
        return None
    try:
        r = ask(sp, sa, engine=engine or _shared)
    except ValueError:
        r = "inconsistent"
    if r is None:
        return None
    cx = refute_nan(prop, assum, r, (X, Y, Z), seed)
    assert cx is None, (
        f"ask({sp}, {sa}) = {r} but the model {cx[0]}, f = {cx[1]} satisfies "
        f"the assumptions and refutes it (atom values {cx[2]})")
    return r


@FUZZ
@given(nan_cases())
def test_fuzz_eq_nan(case):
    prop, assum, seed, fresh = case
    check_nan(prop, assum, seed, Engine() if fresh else None)


_NAN_EDGE = [
    # the reported case: f(1)*g(1) is nan at f(1) = 0, g(1) = oo
    (("r", "eq", X + F(S.One) * G(S.One), Y + F(S.One) * G(S.One)), ("r", "eq", X, Y, "Q")),
    (("r", "eq", X, X), ("u", "zero", Z)),
    (("r", "eq", F(X), F(X)), ("u", "zero", Z)),
    (("r", "ne", F(X), F(X)), ("u", "zero", Z)),
    (("r", "eq", F(X), F(Y)), ("r", "eq", X, Y, "Q")),
    (("r", "eq", X - Z, Y - Z), ("r", "eq", X, Y, "Q")),
    (("r", "eq", X * Z, Y * Z), ("r", "eq", X, Y, "Q")),
    (("r", "eq", X - Z, Y - Z), ("and", ("r", "eq", X, Y, "Q"), ("u", "real", Z))),
]


@pytest.mark.parametrize("prop, assum", _NAN_EDGE)
def test_eq_nan_edge_cases(prop, assum):
    prop = prop if len(prop) == 5 else prop + ("Q",)
    for seed in range(3):
        check_nan(prop, assum, seed, Engine())
