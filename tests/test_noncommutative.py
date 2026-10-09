"""Products, powers, sums and function applications with non-commutative
arguments (issue #47).

``commutative`` is a property of the *value*: numbers (and ``oo``, ``zoo``)
are commutative, a non-commutative symbol stands for a value that is not a
number.  A product with a non-commutative factor can still be a number
(``0*A == 0``, ``A*A**-1 == 1``, ``A**2 == 1`` for a reflection) and zero
without a zero factor (``A*B == 0`` for nilpotent ``A = B``).  Likewise a
sum or a function of non-numbers can be a number (``A - B == 0`` for
``B = A``, ``f(A) == 0`` for ``f = 0``).

The model check below evaluates template formulas and ``ask`` answers in a
concrete model: commutative symbols are complex numbers, non-commutative
symbols are 2x2 matrices that are not multiples of the identity, and a
value that is ``c`` times the identity is the number ``c``.  An undefined
function ranges over a few maps that send numbers to numbers, ``Abs`` is
the Frobenius norm on matrices.
"""
from __future__ import annotations

from itertools import product

import pytest

sympy = pytest.importorskip("sympy")

from sympy import (
    Abs,
    Add,
    Function,
    I,
    Integer,
    Matrix,
    Mul,
    Pow,
    Q,
    Rational,
    S,
    Symbol,
    eye,
    oo,
    sin,
    sqrt,
)
from sympy.core.function import AppliedUndef
from test_templates import evaluate

from satassume import DictCache, Engine
from satassume.sat.formula import atoms_of
from satassume.sympy_api import ask
from satassume.knowledge.templates import registry

A = Symbol('A', commutative=False)
B = Symbol('B', commutative=False)
x, y = Symbol('x'), Symbol('y')
f = Function('f')


def fresh():
    return Engine(cache=DictCache())


# ---------------------------------------------------------------------------
# the reproductions of #47
# ---------------------------------------------------------------------------

def test_zero_factor_with_noncommutative_factor():
    # x*A is 0 at x = 0: never False (SymPy's ask says True)
    assert ask(Q.zero(x*A), Q.zero(x), fresh()) is not False
    assert ask(Q.zero(x*A*B), Q.zero(x), fresh()) is not False
    assert ask(Q.commutative(x*A), Q.zero(x), fresh()) is not False
    assert ask(Q.zero(x*A), True, fresh()) is None
    assert ask(Q.zero(x), True, fresh()) is None


def test_inverse_of_noncommutative():
    # non-commutative arguments are out of scope (#62): None, and in the
    # assumptions an opaque atom (no inconsistency from Q.positive(1/A))
    assert ask(Q.positive(1/A), True, fresh()) is None
    assert ask(Q.finite(A), True, fresh()) is None
    assert ask(Q.finite(A), Q.positive(1/A), fresh()) is None


def test_zero_divisors():
    # A*B == 0 and A**2 == 0 for nilpotent A = B; A**2 == 1 for a reflection
    for q in (Q.zero(A*B), Q.zero(A**2), Q.zero(x*A*B), Q.positive(A**2),
              Q.positive(A*B), Q.zero(2*A*B)):
        assert ask(q, True, fresh()) is None, q
    # out of scope (#62), though the templates decide them (False)
    assert ask(Q.zero(2*A), True, fresh()) is None
    assert ask(Q.zero(x*A), ~Q.zero(x) & Q.complex(x), fresh()) is None
    assert ask(Q.commutative(2*A), True, fresh()) is None
    assert ask(Q.zero(A), True, fresh()) is None


def test_no_leak_into_later_queries():
    """The sequence of #47 in one engine: every answer as in a fresh one."""
    seq = [
        (Q.positive(1/A), True),
        (Q.zero(x*A), True),
        (Q.zero(x), True),
        (Q.zero(x), Q.zero(x)),
        (Q.positive(1/(x*A)), True),
        (Q.finite(x), True),
        (Q.finite(A), True),
        (Q.zero(x*A), Q.zero(x)),
        (Q.zero(x), True),
        (Q.zero(A*B), True),
        (Q.zero(x*A*B), Q.zero(x)),
        (Q.zero(y), True),
        (Q.finite(y), True),
    ]
    eng = fresh()
    for q, a in seq:
        assert ask(q, a, eng) == ask(q, a, fresh()), (q, a)
    assert ask(Q.zero(x), True, eng) is None
    assert ask(Q.finite(x), True, eng) is None
    assert ask(Q.finite(A), True, eng) is None
    assert ask(Q.zero(x), Q.zero(x), eng) is True


# ---------------------------------------------------------------------------
# sums and function applications
# ---------------------------------------------------------------------------

def test_sums_of_noncommutative_terms():
    # A - B is 0 at B = A, A + B is 2 at A = diag(1, 0), B = diag(1, 2)
    for q in (Q.zero(A - B), Q.zero(A + B), Q.commutative(A + B), Q.commutative(A - B),
              Q.real(A - B), Q.zero(x*A - x*B), Q.zero(A*B - B*A), Q.zero(A + B + x)):
        assert ask(q, True, fresh()) is None, q
    assert ask(Q.zero(A + B), Q.zero(x), fresh()) is None
    # out of scope (#62), though the templates decide them (False)
    assert ask(Q.zero(A + 1), True, fresh()) is None
    assert ask(Q.commutative(A + 1), True, fresh()) is None
    assert ask(Q.commutative(x + A), Q.finite(x), fresh()) is None
    assert ask(Q.zero(x + A), True, fresh()) is None
    assert ask(Q.finite(x + A), Q.infinite(x), fresh()) is None
    # an opaque assumption says nothing about x
    assert ask(Q.zero(x), Q.zero(x + A), fresh()) is None
    assert ask(Q.commutative(x + y), True, fresh()) is True


def test_functions_of_noncommutative_arguments():
    g = Function('g', commutative=False)
    for q in (Q.zero(f(A)), Q.commutative(f(A)), Q.zero(f(A, x)), Q.zero(sin(A)),
              Q.positive(f(A)), Q.commutative(g(x)), Q.zero(g(x))):
        assert ask(q, True, fresh()) is None, q
    # out of scope (#62), though the templates decide them
    assert ask(Q.extended_real(Abs(A)), True, fresh()) is None
    assert ask(Q.extended_nonnegative(Abs(A)), True, fresh()) is None
    assert ask(Q.zero(Abs(A)), True, fresh()) is None
    assert ask(Q.finite(A), Q.real(Abs(A)), fresh()) is None
    # functions of numbers are numbers
    assert ask(Q.commutative(f(x)), True, fresh()) is True
    assert ask(Q.commutative(f(x, 2)), True, fresh()) is True
    assert ask(Q.commutative(sin(x)), True, fresh()) is True


def test_no_leak_from_sums_and_functions():
    eng = fresh()
    for q in (Q.zero(A - B), Q.zero(f(A)), Q.real(Abs(A)), Q.zero(A + x), Q.zero(A + B + x)):
        assert ask(q, True, eng) == ask(q, True, fresh()), q
    assert ask(Q.finite(A), True, eng) is None
    assert ask(Q.zero(x), True, eng) is None
    # out of scope even when assumed (#62): the assumption is opaque, the
    # proposition is not
    assert ask(Q.zero(A - B), Q.zero(A - B), eng) is None


# ---------------------------------------------------------------------------
# non-commutative arguments are out of scope (#62, D4)
# ---------------------------------------------------------------------------

def test_issue_62_noncommutative_out_of_scope():
    from sympy import im, log, re, sign
    from satassume.sympy_api import out_of_scope
    # items 1-3 of #62: the templates are about numbers, A may be a matrix
    assert ask(Q.zero(re(A) + I*im(A) - A), Q.finite(A), fresh()) is None
    assert ask(Q.zero(sign(A) - A), True, fresh()) is None
    assert ask(Q.zero(A - sign(A)*Abs(A)), True, fresh()) is None
    assert ask(Q.finite(log(A)), Q.finite(A), fresh()) is None
    # re(A) claims to be commutative: the whole tree is walked
    assert re(A).is_commutative is True
    assert ask(Q.real(re(A)), True, fresh()) is None
    # the predicate commutative itself (SymPy answers False there)
    assert ask(Q.commutative(A), True, fresh()) is None
    assert ask(Q.commutative(A), Q.commutative(A), fresh()) is None
    assert out_of_scope(Q.commutative(A)) == "matrix"
    assert out_of_scope(Q.zero(re(A))) == "matrix"
    # a non-commutative function application
    g = Function('g', commutative=False)
    assert out_of_scope(Q.zero(g(x) + 1)) == "matrix"
    # commutative ones stay in scope
    assert out_of_scope(Q.zero(re(x))) is None
    assert ask(Q.commutative(x), True, fresh()) is True


def test_noncommutative_assumption_does_not_sink():
    """A non-commutative conjunct is an opaque atom in the assumptions."""
    from sympy import re
    assert ask(Q.real(x), Q.positive(x) & Q.finite(A), fresh()) is True
    assert ask(Q.real(x), Q.positive(x) & Q.zero(re(A) - A), fresh()) is True
    assert ask(Q.real(x), Q.positive(x) & ~Q.commutative(A), fresh()) is True
    with pytest.raises(ValueError):
        ask(Q.real(x), Q.finite(A) & ~Q.finite(A), fresh())


# ---------------------------------------------------------------------------
# commutative opaque terms (templates.atoms.structural_commutative)
# ---------------------------------------------------------------------------

def test_opaque_commutative_terms():
    """Terms no template relates to their arguments are commutative when
    SymPy's structural ``is_commutative`` says so, so the rules for
    commutative factors still apply to them."""
    from sympy import (Derivative, Determinant, Function, Integral, MatrixSymbol,
                       Max, Min, Piecewise, Sum, Trace)
    t = Symbol('t')
    f = Function('f')
    M = MatrixSymbol('M', 2, 2)
    g, h = Max(x, y), Min(x, y)
    I1, S1 = Integral(f(t), (t, 0, x)), Sum(f(t), (t, 0, x))
    for e in (g, h, I1, S1, Derivative(f(x), x), Piecewise((x, y > 0), (1, True)),
              Trace(M), Determinant(M), M[0, 0]):
        assert ask(Q.commutative(e), True, fresh()) is True, e
        if (e**2).is_Pow:  # Piecewise(...)**2 is a Piecewise
            assert ask(Q.zero(e**2), ~Q.zero(e), fresh()) is False, e
        assert ask(Q.zero(x*e), ~Q.zero(x) & ~Q.zero(e), fresh()) is False, e
    assert ask(Q.zero(g**2), ~Q.zero(g), fresh()) is False
    assert ask(Q.zero(g*h), ~Q.zero(g) & ~Q.zero(h), fresh()) is False
    assert ask(Q.zero(I1**2), ~Q.zero(I1), fresh()) is False
    assert ask(Q.zero(I1*S1), ~Q.zero(I1) & ~Q.zero(S1), fresh()) is False


def test_opaque_terms_with_noncommutative_ingredients():
    """``is_commutative`` alone is not trusted: these claim True from their
    commutative expression, but their values (``A``, ``x*A``) are not."""
    from sympy import Integral, Subs, Sum
    t, n = Symbol('t'), Symbol('n', integer=True)
    for e in (Subs(x, x, A), Integral(x, (t, 0, A)), Sum(x, (n, 0, A))):
        assert e.is_commutative is True
        assert registry.facts_for(e) == [], e
        assert ask(Q.commutative(e), True, fresh()) is None, e
        assert ask(Q.zero(e**2), ~Q.zero(e), fresh()) is None, e
    # no negative fact from ``is_commutative`` False
    assert ask(Q.commutative(Integral(A, (t, 0, x))), True, fresh()) is None


# ---------------------------------------------------------------------------
# model check
# ---------------------------------------------------------------------------

SCALARS = [Integer(0), Integer(1), Integer(-2), Rational(1, 2), I, oo]
MATRICES = [
    Matrix([[0, 1], [0, 0]]),      # nilpotent
    Matrix([[0, 0], [1, 0]]),      # nilpotent, N*N.T is a projector
    Matrix([[0, 1], [1, 0]]),      # reflection: squares to 1
    Matrix([[1, 0], [0, 2]]),
    Matrix([[1, 0], [0, 0]]),      # projector
    Matrix([[1, 1], [0, 1]]),
    Matrix([[1, 0], [0, -1]]),     # reflection
]

PREDS = ('zero', 'commutative', 'finite', 'infinite', 'positive', 'negative',
         'real', 'complex', 'integer', 'nonzero', 'imaginary', 'extended_real')

#: A value is ``(c, M)``: the number ``c`` (SymPy arithmetic, ``0*oo`` is
#: nan) times the matrix ``M``, which is None or not a multiple of the
#: identity.  None: undefined (nan, the inverse of a singular matrix).
UNDEFINED = None
#: A sum of a non-number and one infinite value (``oo + A``): infinite, not
#: finite and not zero, everything else unknown.
INFINITE = 'infinite'

#: Interpretations of an undefined function: each sends numbers to numbers.
FUNCTIONS = {
    'first': lambda vs: vs[0],
    'zero': lambda vs: (S.Zero, None),
    'det': lambda vs: _make(vs[0][0]**2 * (1 if vs[0][1] is None else vs[0][1].det()), None),
    'square': lambda vs: _make(vs[0][0]**2, None if vs[0][1] is None else vs[0][1]**2),
}


def _make(c, m):
    if c is S.NaN:
        return UNDEFINED
    if m is not None:
        d = m[0, 0]
        if m == d * eye(2):
            return _make(c * d, None)
        if c.is_zero:
            return (S.Zero, None)
    return (c, m)


def _add(vs):
    if all(m is None for _, m in vs):
        return _make(Add(*(c for c, _ in vs)), None)
    infinite = [c for c, _ in vs if c.is_infinite]
    if not infinite:
        total = sum(((c * (eye(2) if m is None else m)) for c, m in vs), Matrix.zeros(2, 2))
        return _make(S.One, total)
    return INFINITE if len(infinite) == 1 else UNDEFINED


def _abs(v):
    c, m = v
    if m is None:
        return _make(Abs(c), None)
    return _make(Abs(c) * sqrt(sum(Abs(e)**2 for e in m)), None)


def value(expr, point):
    if expr in point:
        v = point[expr]
        return (S.One, v) if isinstance(v, Matrix) else (v, None)
    if expr.is_Number or expr is I:
        return (expr, None)
    if isinstance(expr, (Add, AppliedUndef, Abs)):
        vs = [value(a, point) for a in expr.args]
        if any(v is UNDEFINED or v is INFINITE for v in vs):
            return UNDEFINED
        if isinstance(expr, Add):
            return _add(vs)
        if isinstance(expr, Abs):
            return _abs(vs[0])
        return FUNCTIONS[point[expr.func]](vs)
    if isinstance(expr, Mul):
        c, m = S.One, None
        for a in expr.args:
            v = value(a, point)
            if v is UNDEFINED or v is INFINITE:
                return UNDEFINED
            c = c * v[0]
            m = v[1] if m is None else m if v[1] is None else m * v[1]
            if _make(c, m) is UNDEFINED:
                return UNDEFINED
        return _make(c, m)
    if isinstance(expr, Pow):
        b, e = expr.args
        v = value(b, point)
        if v is UNDEFINED or v is INFINITE:
            return UNDEFINED
        c, m = v
        if m is None:
            return _make(Pow(c, e), None)
        if not e.is_Integer or (e < 0 and m.det() == 0):
            return UNDEFINED
        return _make(Pow(c, e), m ** int(e))
    raise NotImplementedError(expr)


def truth(v, pred):
    """Value of ``pred`` at the value ``v`` (None: unknown)."""
    if v is INFINITE:
        return {'infinite': True, 'finite': False, 'zero': False}.get(pred)
    c, m = v
    if m is None:
        return getattr(c, 'is_' + pred, None)
    # a non-number: finite unless the coefficient is infinite
    if pred in ('finite', 'infinite'):
        return (pred == 'infinite') == bool(c.is_infinite)
    return False


def samples():
    exprs = [x*A, x*A*B, x*y*A, 2*A, -A, I*A, 2*A*B, A*B, B*A, A*B*A, x*A*B*A,
             A**2, A**-1, A**-2, x*A**2, x*A**-1, A*B**-1,
             Mul(x, A, B, evaluate=False), (x*A)**-1, 1/(x*A), oo*A, oo*A*B, x*y*A*B]
    sums = [A + B, A - B, x + A, x - A, A + 1, oo + A, A + B + x, x*A + B, x*A - x*B,
            A*B - B*A, A**2 - B, x + y + A, A + B + x + y, oo*A + B, A*B + x*A]
    functions = [f(A), f(x*A), f(A - B), f(A + x), f(A, x), f(A) + x, x*f(A), f(A)*f(B),
                 f(f(A)), Abs(A), Abs(A - B), Abs(x*A), Abs(A) + x]
    return exprs + sums + functions


def points(expr):
    syms = sorted(expr.free_symbols, key=lambda s: s.name)
    funcs = sorted({a.func for a in expr.atoms(AppliedUndef)}, key=str)
    pools = [MATRICES if not s.is_commutative else SCALARS for s in syms]
    pools += [FUNCTIONS] * len(funcs)
    for vals in product(*pools):
        yield dict(zip(syms + funcs, vals))


def node_values(point):
    cache = {}

    def valuation(atom):
        if atom not in cache:
            v = value(atom.expr, point)
            cache[atom] = None if v is UNDEFINED else truth(v, atom.pred)
        return cache[atom]
    return valuation


@pytest.mark.parametrize('expr', samples(), ids=str)
def test_templates_sound_for_noncommutative_factors(expr):
    """Every formula the templates emit for ``expr`` (and its subterms)
    holds at every point of the matrix model."""
    nodes = [expr, *(a for a in expr.args if not a.is_Atom)]
    nodes += [b for a in nodes[1:] for b in a.args if not b.is_Atom]
    facts = [f for n in nodes for f in registry.facts_for(n)]
    failures = []
    for point in points(expr):
        valuation = node_values(point)
        for f in facts:
            if evaluate(f, valuation) is False:
                failures.append((point, f, {a: valuation(a) for a in atoms_of(f)}))
    assert not failures, "\n".join(f"{p}: {f!r}\n    {d}" for p, f, d in failures[:10])


def _assumption(point, syms):
    """Facts of the scalar symbols at ``point`` (``None``: no assumption)."""
    parts = []
    for s in syms:
        v = point[s]
        if isinstance(v, str):
            continue
        if isinstance(v, Matrix):
            continue
        parts.append(Q.zero(s) if v == 0 else Q.nonzero(s) if v.is_real else
                     Q.positive_infinite(s) if v is oo else Q.imaginary(s))
    return None if not parts else parts[0] if len(parts) == 1 else sympy.And(*parts)


def test_ask_sound_for_noncommutative_factors():
    """``ask`` in one shared engine (so that cached facts carry over from
    query to query) never contradicts the matrix model."""
    eng = fresh()
    answers = {}
    failures = []
    for expr in samples():
        syms = sorted(expr.free_symbols, key=lambda s: s.name)
        for point in points(expr):
            v = value(expr, point)
            if v is UNDEFINED:
                continue
            for a in (True, _assumption(point, syms)):
                if a is None:
                    continue
                for pred in PREDS:
                    q = getattr(Q, pred)(expr)
                    key = (q, a)
                    if key not in answers:
                        try:
                            answers[key] = ask(q, a, eng)
                        except ValueError:
                            answers[key] = 'inconsistent'
                    got, want = answers[key], truth(v, pred)
                    if got == 'inconsistent' or (got is not None and want is not None
                                                 and got != want):
                        failures.append((expr, point, a, pred, got, want))
    assert not failures, "\n".join(map(str, failures[:20]))
    # and nothing about plain symbols leaked from these queries
    for pred in ('zero', 'finite', 'nonzero', 'complex'):
        assert ask(getattr(Q, pred)(x), True, eng) is None


# ``commutative`` is true by definition (rules.DEFINITIONS): the rule base
# and the templates assume numbers.  The Engine, used directly, answers
# None about a term with a non-commutative subterm (sympy_api keeps such
# terms out of scope before), and a function registered for
# ``commutative`` is refused.
def test_engine_is_none_on_noncommutative_terms():
    from sympy import Symbol
    from satassume.engine import Engine
    A = Symbol("A", commutative=False)
    x = Symbol("x")
    e = Engine()
    assert e.is_(A, "commutative") is None
    assert e.is_many(A, ["commutative", "zero"]) == [None, None]
    assert e.is_(x, "commutative") is True


def test_engine_ask_none_on_noncommutative_terms():
    from sympy import Symbol
    from satassume.engine import Engine
    from satassume.sat.formula import And as FAnd, Not as FNot, P
    A, B = Symbol("A", commutative=False), Symbol("B", commutative=False)
    e = Engine()
    # A*B can be zero without a zero factor (nilpotent matrices)
    assert e.ask(P("zero", A * B), FAnd(FNot(P("zero", A)), FNot(P("zero", B)))) is None
    assert e.ask(P("commutative", A)) is None
    assert e.ask(FNot(P("commutative", A))) is None



def test_engine_verdict_unknown_on_noncommutative_terms():
    # verdict is gated like is_/ask: a set about a non-commutative term is
    # UNKNOWN (main: CONSISTENT; without the gate, INCONSISTENT)
    from sympy import Symbol
    from satassume.engine import CONSISTENT, INCONSISTENT, UNKNOWN, Engine
    from satassume.sat.formula import And as FAnd, Not as FNot, P
    A, B = Symbol("A", commutative=False), Symbol("B", commutative=False)
    x = Symbol("x")
    e = Engine()
    nilpotent = FAnd(FNot(P("zero", A)), FNot(P("zero", B)), P("zero", A * B))
    assert e.verdict(nilpotent) is UNKNOWN
    assert e.verdict(FNot(P("commutative", A))) is UNKNOWN
    assert e.verdict(P("commutative", A)) is UNKNOWN
    # and ask under such a set answers None, never a raise
    assert e.ask(P("zero", A), nilpotent) is None
    # commutative terms are unaffected
    assert e.verdict(FNot(P("commutative", x))) is INCONSISTENT
    assert e.verdict(P("positive", x)) is CONSISTENT

def test_register_commutative_is_refused():
    from sympy import Symbol
    from satassume.knowledge.extensions import Extensions
    from satassume.sat.formula import P
    with pytest.raises(ValueError, match="by definition"):
        Extensions().register("commutative", Symbol)(lambda s: P("commutative", s))
