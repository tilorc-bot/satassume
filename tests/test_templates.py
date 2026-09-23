"""Soundness tests for :mod:`satassume.templates`.

The key test substitutes concrete numbers for the symbols of many template
instantiations and checks, under the old assumption system's truth values
of the atoms (``value.is_<pred>``; ``None`` is "unknown"), that no emitted
formula evaluates to ``False`` in Kleene three-valued logic.  A formula that
is ``False`` under a partial assignment is false under every completion, so
this catches every violation the oracle can see.
"""
from __future__ import annotations

from itertools import product

import pytest

sympy = pytest.importorskip("sympy")

from sympy import (
    Abs,
    Add,
    Catalan,
    Dummy,
    EulerGamma,
    Float,
    GoldenRatio,
    I,
    Integer,
    Mul,
    Pow,
    Rational,
    S,
    Symbol,
    TribonacciConstant,
    Wild,
    acos,
    acot,
    asin,
    atan,
    ceiling,
    conjugate,
    cos,
    cosh,
    exp,
    factorial,
    floor,
    im,
    log,
    nan,
    oo,
    pi,
    re,
    sign,
    sin,
    sinh,
    sqrt,
    tan,
    tanh,
    zoo,
)
from sympy import E as _E
from sympy.calculus.accumulationbounds import AccumBounds

from satassume.formula import (
    And,
    Equivalent,
    Exclusive,
    Formula,
    Implies,
    Not,
    Or,
    P,
    atoms_of,
)
from satassume.templates import registry
from satassume.templates._common import VOCAB

x, y, z, w = (Symbol(n) for n in "xyzw")

# ---------------------------------------------------------------------------
# three-valued evaluation
# ---------------------------------------------------------------------------


def k_and(values):
    if any(v is False for v in values):
        return False
    if all(v is True for v in values):
        return True
    return None


def k_or(values):
    if any(v is True for v in values):
        return True
    if all(v is False for v in values):
        return False
    return None


def k_not(v):
    return None if v is None else (not v)


def evaluate(f, valuation):
    """Kleene evaluation of ``f``; ``valuation(atom) -> True/False/None``."""
    if f is True or f is False:
        return f
    if isinstance(f, P):
        return valuation(f)
    if isinstance(f, And):
        return k_and([evaluate(a, valuation) for a in f.args])
    if isinstance(f, Or):
        return k_or([evaluate(a, valuation) for a in f.args])
    if isinstance(f, Not):
        return k_not(evaluate(f.args[0], valuation))
    if isinstance(f, Implies):
        a, b = f.args
        return k_or([k_not(evaluate(a, valuation)), evaluate(b, valuation)])
    if isinstance(f, Equivalent):
        vals = [evaluate(a, valuation) for a in f.args]
        if any(v is None for v in vals):
            return None
        return all(v == vals[0] for v in vals)
    if isinstance(f, Exclusive):
        vals = [evaluate(a, valuation) for a in f.args]
        t = vals.count(True)
        u = vals.count(None)
        if t >= 2:
            return False
        if t + u <= 1:
            return True
        return None
    raise TypeError(f"unknown formula {f!r}")


def test_evaluator_basics():
    a, b = P('p', 1), P('p', 2)
    val = {a: True, b: None}.get
    assert evaluate(Implies(a, b), val) is None
    assert evaluate(Implies(b, a), val) is True
    assert evaluate(Or(Not(a), b), val) is None
    assert evaluate(And(a, Not(a)), val) is False
    assert evaluate(Equivalent(a, b), val) is None
    assert evaluate(Exclusive(a, b), val) is None
    assert evaluate(Exclusive(a, a), val) is False
    assert evaluate(Exclusive(b, b), val) is None
    assert evaluate(Exclusive(Not(a), b), val) is True


# ---------------------------------------------------------------------------
# the oracle
# ---------------------------------------------------------------------------


def oracle(value, pred):
    """Old-system truth value of ``pred`` for the concrete ``value``."""
    if isinstance(value, AccumBounds):
        return None
    return getattr(value, 'is_' + pred, None)


POOL = [Integer(-3), Integer(-2), Integer(-1), Rational(-1, 2), Integer(0),
        Rational(1, 2), Integer(1), Integer(2), Integer(3), Integer(4),
        Integer(6), sqrt(2), -sqrt(2), pi, _E, I, -I, 2*I, 1 + I, -1 + I,
        oo, -oo, zoo, Float(1.5), Float(-2.0), Float(0.0), Rational(3, 2),
        Rational(-9, 4), Rational(7, 3), -pi, 2*pi, 1/pi, sqrt(3)*I, oo*I,
        -oo*I, 2 - 3*I, pi*I, 1 - sqrt(2), Integer(9), Integer(-4)]
POOL_MEDIUM = [Integer(-2), Integer(-1), Rational(-1, 2), Integer(0),
               Rational(1, 2), Integer(1), Integer(2), Integer(3), sqrt(2), pi,
               I, 1 + I, oo, -oo, zoo]
POOL_SMALL = [Integer(-2), Integer(0), Rational(1, 2), Integer(2), Integer(3),
              sqrt(2), I, oo]
POOL_TINY = [Integer(-1), Integer(0), Integer(2), I, oo]


def pool_for(nsyms):
    return {1: POOL, 2: POOL_MEDIUM, 3: POOL_SMALL}.get(nsyms, POOL_TINY)


def make_valuation(assignment):
    """Atom valuation under ``assignment`` (symbol -> concrete value)."""
    cache = {}

    def valuation(atom):
        if atom not in cache:
            try:
                v = atom.expr.xreplace(assignment)
            except Exception:  # an evaluation SymPy cannot do
                v = None
            cache[atom] = None if v is None else oracle(v, atom.pred)
        return cache[atom]

    return valuation


def check_sound(expr):
    """Check every template formula of ``expr`` against concrete values."""
    facts = registry.facts_for(expr)
    assert facts, f"no templates fired for {expr!r}"
    syms = sorted(expr.free_symbols, key=lambda s: s.name)
    pool = pool_for(len(syms))
    failures = []
    for values in product(pool, repeat=len(syms)):
        assignment = dict(zip(syms, values))
        valuation = make_valuation(assignment)
        for f in facts:
            if evaluate(f, valuation) is False:
                detail = {a: valuation(a) for a in atoms_of(f)}
                failures.append((assignment, f, detail))
    assert not failures, "\n".join(
        f"{expr!r} with {a}: {f!r}\n    atoms: {d}" for a, f, d in failures[:20])


# ---------------------------------------------------------------------------
# sample instantiations
# ---------------------------------------------------------------------------

def unevaluated(cls, *args):
    return cls(*args, evaluate=False)


ADD_SAMPLES = [
    x + y, x + 1, x - 1, x + 2, x + Rational(1, 2), x + y + z, x + y + 1,
    x + y + z + w, x + I, x + pi, x + oo, x - oo, x + sqrt(2), x + 2*I,
    x + y*I, unevaluated(Add, x, y, z, w, 1), unevaluated(Add, 1, 2, x),
    x + y + oo, x + y - oo, x + y + I, x + y + z + 1, unevaluated(Add, 2, 2),
    unevaluated(Add, oo, -oo), unevaluated(Add, 1, I),
]
MUL_SAMPLES = [
    x*y, 2*x, -x, x/2, -x/2, 3*x/2, Rational(-3, 2)*x, x*y*z, 2*x*y,
    -x*y, x*y*z*w, I*x, I*x*y, pi*x, sqrt(2)*x, oo*x, -oo*x, zoo*x, x*y/2,
    unevaluated(Mul, x, y, z, w, 2), unevaluated(Mul, 2, 3, x),
    Float(2.5)*x, Float(-1.5)*x, x*(1 + I), 4*x, -x*y*z, sqrt(2)*x, I*x*y*z,
    unevaluated(Mul, I, 1 + I), unevaluated(Mul, 2, 3),
]
POW_SAMPLES = [
    x**2, x**3, x**4, x**-1, x**-2, x**-3, sqrt(x), 1/sqrt(x),
    x**Rational(3, 2), x**Rational(1, 3), x**Rational(-1, 3),
    x**Rational(2, 3), x**y, 2**x, 3**x, (-1)**x, (-2)**x, I**x, pi**x,
    sqrt(2)**x, Rational(1, 2)**x, unevaluated(Pow, _E, x),
    unevaluated(Pow, x, x), x**pi, x**sqrt(2), x**I, x**(1 + I), 0**x,
    unevaluated(Pow, 1, x), (-I)**x, x**oo, x**-oo, oo**x, (-oo)**x, zoo**x,
    unevaluated(Pow, x, 0), unevaluated(Pow, x, 1), x**(-y), x**(2*y),
    unevaluated(Pow, x, 2), unevaluated(Pow, x, Rational(1, 2)),
    unevaluated(Pow, x, -1),
]
FUNCTION_SAMPLES = [
    exp(x), log(x), Abs(x), re(x), im(x), sign(x), conjugate(x), floor(x),
    ceiling(x), factorial(x), sin(x), cos(x), tan(x), sinh(x), cosh(x),
    tanh(x), asin(x), acos(x), atan(x), acot(x),
    exp(2*x), log(x + 1), Abs(x*y), sin(x + y), atan(x*y),
]


@pytest.mark.parametrize("expr", ADD_SAMPLES, ids=str)
def test_add_sound(expr):
    check_sound(expr)


@pytest.mark.parametrize("expr", MUL_SAMPLES, ids=str)
def test_mul_sound(expr):
    check_sound(expr)


@pytest.mark.parametrize("expr", POW_SAMPLES, ids=str)
def test_pow_sound(expr):
    check_sound(expr)


@pytest.mark.parametrize("expr", FUNCTION_SAMPLES, ids=str)
def test_functions_sound(expr):
    check_sound(expr)


# ---------------------------------------------------------------------------
# atoms
# ---------------------------------------------------------------------------

CONSTANTS = [Integer(0), Integer(1), Integer(-1), Integer(2), Integer(-2),
             Integer(7), Integer(9), Rational(1, 2), Rational(-3, 2),
             Float(1.5), Float(0.0), pi, _E, GoldenRatio, EulerGamma, Catalan,
             TribonacciConstant, I, oo, -oo, zoo, nan]


@pytest.mark.parametrize("c", CONSTANTS, ids=str)
def test_constant_units_match_oracle(c):
    facts = registry.facts_for(c)
    for f in facts:
        atom = f if isinstance(f, P) else f.args[0]
        assert isinstance(atom, P) and atom.expr is c
        assert atom.pred in VOCAB
        truth = isinstance(f, P)
        got = oracle(c, atom.pred)
        if got is not None:
            assert got == truth, (c, f)
    if c is not nan:
        assert facts
    preds = {(f if isinstance(f, P) else f.args[0]).pred for f in facts}
    assert 'commutative' in preds


def test_signed_infinity_units():
    assert P('positive_infinite', oo) in registry.facts_for(oo)
    assert P('negative_infinite', -oo) in registry.facts_for(-oo)
    assert Not(P('positive_infinite', zoo)) in registry.facts_for(zoo)
    assert Not(P('positive_infinite', Integer(2))) in registry.facts_for(Integer(2))


@pytest.mark.parametrize("cls", [Symbol, Dummy])
def test_symbol_units(cls):
    s = cls('s', positive=True)
    facts = set(registry.facts_for(s))
    assert P('positive', s) in facts
    assert P('real', s) in facts
    assert Not(P('zero', s)) in facts
    for f in facts:
        atom = f if isinstance(f, P) else f.args[0]
        assert atom.expr is s and atom.pred in VOCAB
    # facts agree with the old system on the symbol itself
    for f in facts:
        atom = f if isinstance(f, P) else f.args[0]
        assert getattr(s, 'is_' + atom.pred) is isinstance(f, P)
    plain = cls('t')
    assert registry.facts_for(plain) == [P('commutative', plain)]
    nc = cls('A', commutative=False)
    assert Not(P('commutative', nc)) in registry.facts_for(nc)
    assert Not(P('real', nc)) in registry.facts_for(nc)


def test_wild_units():
    facts = registry.facts_for(Wild('w'))
    assert facts == [P('commutative', Wild('w'))]


def test_other_leaves_emit_nothing():
    from sympy import Tuple
    assert registry.facts_for(Tuple()) == []
    assert registry.facts_for(S.true) == []


# ---------------------------------------------------------------------------
# structure
# ---------------------------------------------------------------------------

ALL_SAMPLES = ADD_SAMPLES + MUL_SAMPLES + POW_SAMPLES + FUNCTION_SAMPLES


def _atom_nodes(f):
    return {a.expr for a in atoms_of(f)}


@pytest.mark.parametrize("expr", ALL_SAMPLES, ids=str)
def test_atoms_are_node_or_direct_args(expr):
    allowed = {expr, *expr.args}
    for f in registry.facts_for(expr):
        assert isinstance(f, (P, Formula)), f
        for a in atoms_of(f):
            assert a.pred in VOCAB, (expr, a)
            assert a.expr in allowed, (expr, f, a)


def test_facts_for_x_plus_y_shape():
    facts = registry.facts_for(x + y)
    assert facts
    for f in facts:
        for a in atoms_of(f):
            assert a.expr in {x + y, x, y}
            assert a.pred in VOCAB
    # facts are about the node, not just unit facts about args
    assert any(P('real', x + y) in atoms_of(f) for f in facts)


def test_registry_mro_and_ordering():
    from satassume.templates.registry import TemplateRegistry

    class Base:
        pass

    class Mid(Base):
        pass

    class Leaf(Mid):
        pass

    reg = TemplateRegistry()

    @reg.register(Base)
    def base_t(e):
        return P('base', e)

    @reg.register(Leaf, Mid)
    def leaf_t(e):
        yield P('leaf', e)
        yield None
        yield True  # dropped

    leaf = Leaf()
    assert reg.facts_for(leaf) == [P('leaf', leaf), P('leaf', leaf), P('base', leaf)]
    mid = Mid()
    assert reg.facts_for(mid) == [P('leaf', mid), P('base', mid)]
    base = Base()
    assert reg.facts_for(base) == [P('base', base)]
    assert reg.facts_for(object()) == []


def test_specific_expectations():
    """A few spot checks that the important rules are actually present."""
    from satassume.compile import VarTable, compile_formula

    def clauses_of(expr):
        table = VarTable()
        out = []
        for f in registry.facts_for(expr):
            compile_formula(f, table, out.append)
        return table, out

    # Every template compiles, and to plain clauses (no Tseitin variables).
    for expr in ALL_SAMPLES:
        table, _ = clauses_of(expr)
        assert table.naux == 0, (expr, [f for f in registry.facts_for(expr)
                                        if not isinstance(f, (P, Implies, Or, Not))])

    # Constant arguments are resolved statically: premises about ``-1`` or
    # ``2`` do not appear in the clauses.
    facts = registry.facts_for(-x)
    assert Implies(P('extended_positive', x), P('extended_negative', -x)) in facts
    assert Implies(P('negative', -x), P('positive', x)) in facts
    assert Implies(P('integer', -x), P('integer', x)) in facts
    facts = registry.facts_for(x**2)
    assert Implies(P('nonzero', x), P('positive', x**2)) in facts
    assert Implies(P('integer', x), P('integer', x**2)) in facts
    facts = registry.facts_for(x + 1)
    assert Implies(P('extended_nonnegative', x), P('extended_positive', x + 1)) in facts
    assert Implies(P('odd', x), P('even', x + 1)) in facts
    assert Implies(P('integer', x + 1), P('integer', x)) in facts
    facts = registry.facts_for(x/2)
    assert Implies(And(P('integer', x), P('integer', x/2)), P('even', x)) in facts
    for f in registry.facts_for(x + 1) + registry.facts_for(2*x) + registry.facts_for(x**2):
        for a in atoms_of(f):
            # only atoms the old system cannot decide statically survive
            assert not a.expr.is_Number or oracle(a.expr, a.pred) is None, f
    facts = registry.facts_for(exp(x))
    assert Implies(P('real', x), P('positive', exp(x))) in facts
    facts = registry.facts_for(x + y)
    assert Implies(And(P('infinite', x), Not(P('negative_infinite', x)),
                       Not(P('negative_infinite', y))), P('infinite', x + y)) in facts
    assert Implies(And(P('extended_nonzero', x), P('imaginary', y)),
                   Not(P('imaginary', x + y))) in facts
    facts = registry.facts_for(x + oo)
    assert Implies(P('real', x), P('extended_positive', x + oo)) in facts
    assert Implies(Not(P('negative_infinite', x)), P('infinite', x + oo)) in facts
    facts = registry.facts_for(I*x)
    assert Implies(And(P('complex', x), P('extended_real', I*x)),
                   Or(P('imaginary', x), P('zero', x))) in facts
    assert Implies(And(P('complex', x), P('imaginary', I*x)), P('real', x)) in facts
    assert Implies(P('real', x), Or(P('imaginary', I*x), P('zero', I*x))) in facts
    facts = registry.facts_for(4*x)
    assert Implies(P('integer', x), Not(P('prime', 4*x))) in facts
    facts = registry.facts_for(sqrt(2)*x)
    assert Implies(And(P('irrational', sqrt(2)), P('rational', x), Not(P('zero', x))),
                   P('irrational', sqrt(2)*x)) in facts
    facts = registry.facts_for(Abs(x))
    assert P('extended_nonnegative', Abs(x)) in facts
