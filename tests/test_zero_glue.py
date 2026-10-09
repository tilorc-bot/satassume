"""``Q.zero(t)`` is the equality ``t = 0`` for the relation glue when
``t`` is under an application of the set or the query (nightly family A,
``relations.zero_twins``): the ``zero`` and ``eq`` spellings answer alike,
in the set and in the proposition, and a relation unrelated to the query
adds nothing to a set whose glue a ``zero`` atom switches on.  Outside the
condition the spellings agree without the twin.  Each answer below is the
correct one (``t = 0`` pointwise)."""
import pytest
from sympy import Abs, Function, Q, Symbol, sqrt, symbols

from satassume.engine import DictCache, Engine
from satassume.sat.formula import P
from satassume.relations import relation_atom, zero_twins
from satassume.sympy_api import ask

g = Function("g")
n = Symbol("n", integer=True)
y = Symbol("y", real=True)
u, v, x, w = symbols("u v x w")
t = 7 * y / 2 + sqrt(2)

CONFIGS = {"default": {}, "whole": {"relevance": False}, "notransfer": {"transfer": False}}


def _ask(p, s, cfg):
    try:
        return ask(p, s, Engine(cache=DictCache(), **CONFIGS[cfg]))
    except Exception as ex:          # noqa: BLE001 (compared as an outcome)
        return type(ex).__name__


# name: (proposition, set with zero(t), the set with eq(t, 0), {config: answer})
SETS = {
    # G1: congruence g(n, 1) = g(0, 1), then transfer of composite
    "G1": (Q.composite(g(n, 1)), Q.zero(n) & Q.composite(g(0, 1)),
           Q.eq(n, 0) & Q.composite(g(0, 1)),
           {"default": True, "whole": True, "notransfer": None}),
    # G2: links and congruence alone (also without transfer)
    "G2": (Q.nonzero(g(t, t)), Q.zero(g(0, 0)) & Q.zero(t),
           Q.eq(g(0, 0), 0) & Q.eq(t, 0),
           {"default": False, "whole": False, "notransfer": False}),
    "G2-unary": (Q.zero(g(y)), Q.zero(y) & Q.zero(g(0)), Q.eq(y, 0) & Q.zero(g(0)),
                 {"default": True, "whole": True, "notransfer": True}),
    # G3
    "G3": (Q.zero(g(Abs(g(y)))), Q.zero(y) & ~Q.finite(g(Abs(g(0)))),
           Q.eq(y, 0) & ~Q.finite(g(Abs(g(0)))),
           {"default": False, "whole": False, "notransfer": False}),
    # G4, G5: transfer needed
    "G4": (Q.transcendental(g(y)), Q.zero(y) & Q.algebraic(g(0)),
           Q.eq(y, 0) & Q.algebraic(g(0)),
           {"default": False, "whole": False, "notransfer": None}),
    "G5": (Q.integer(g(g(y))), Q.zero(y) & Q.integer(g(g(0)) + 2),
           Q.eq(y, 0) & Q.integer(g(g(0)) + 2),
           {"default": True, "whole": True, "notransfer": None}),
}


@pytest.mark.parametrize("cfg", list(CONFIGS))
@pytest.mark.parametrize("name", list(SETS))
def test_zero_in_the_set_is_an_equality(name, cfg):
    p, zs, es, want = SETS[name]
    assert _ask(p, zs, cfg) == _ask(p, es, cfg) == want[cfg]


@pytest.mark.parametrize("cfg", list(CONFIGS))
@pytest.mark.parametrize("name", ["G1", "G3"])
def test_unrelated_relation_adds_nothing(name, cfg):
    # I2: with the glue on through zero(t), Q.eq(u, v) has nothing to add
    p, zs, _es, want = SETS[name]
    assert _ask(p, zs & Q.eq(u, v), cfg) == _ask(p, zs, cfg) == want[cfg]


@pytest.mark.parametrize("cfg", list(CONFIGS))
def test_zero_in_the_proposition_is_an_equality(cfg):
    s = Q.zero(y) & ~Q.finite(g(0))
    assert _ask(Q.zero(g(y)), s, cfg) is False
    assert _ask(Q.eq(g(y), 0), s, cfg) is False
    # the proposition's own zero(n) switches the glue on
    assert _ask(Q.composite(g(n, 1)) | ~Q.zero(n), Q.composite(g(0, 1)), cfg) == \
        _ask(Q.composite(g(n, 1)) | Q.ne(n, 0), Q.composite(g(0, 1)), cfg) == \
        (None if cfg == "notransfer" else True)


@pytest.mark.parametrize("cfg", list(CONFIGS))
def test_not_zero_is_ne(cfg):
    # ~zero(t) reads as ne(t, 0); nonzero (real and not zero) has no twin
    assert _ask(Q.positive(x), ~Q.zero(x) & Q.nonnegative(x), cfg) == \
        _ask(Q.positive(x), Q.ne(x, 0) & Q.nonnegative(x), cfg) is True
    assert _ask(Q.zero(g(x)), ~Q.zero(x) & Q.zero(g(0)), cfg) is None


@pytest.mark.parametrize("cfg", list(CONFIGS))
def test_set_verdict_is_the_whole_sets(cfg):
    # the glue connects the components through the class of 0, so a set
    # with zero(t) is checked whole, as its eq spelling is
    zs = Q.zero(x) & Q.positive(g(x)) & Q.zero(w) & Q.negative(g(w))
    es = Q.eq(x, 0) & Q.positive(g(x)) & Q.eq(w, 0) & Q.negative(g(w))
    assert _ask(Q.real(x), zs, cfg) == _ask(Q.real(x), es, cfg) == "ValueError"


@pytest.mark.parametrize("cfg", list(CONFIGS))
def test_zero_and_application_in_different_formulas(cfg):
    # zero(n) in the proposition, g(n, 1) in the set: the query's twin
    s = ~Q.composite(g(n, 1)) & Q.composite(g(0, 1))
    want = None if cfg == "notransfer" else True
    assert _ask(~Q.zero(n), s, cfg) == _ask(Q.ne(n, 0), s, cfg) == want


def test_the_condition():
    z = symbols("z")
    zx, zy = P("zero", x), P("zero", y)
    tx, ty = relation_atom("eq", x, 0), relation_atom("eq", y, 0)
    assert zero_twins((zx, P("positive", y - x))) == []
    assert zero_twins((zx, P("positive", g(Abs(x) + 1)))) == [tx]
    assert zero_twins((zx, zy, P("zero", g(y)))) == [ty]
    assert zero_twins((zx,), (P("finite", g(z, x)),)) == [tx]
    assert zero_twins((P("finite", g(z, x)),), (zx,)) == [tx]
    assert zero_twins((P("zero", g(0)),)) == []
    # a relation's sides count
    assert zero_twins((zx, relation_atom("lt", g(x), u))) == [tx]


# zero(x) with no application over x: the twin is not read, and the two
# spellings agree all the same (relations, "Zero is an equality")
OUTSIDE = [
    (Q.real(y), lambda z: z & Q.positive(y - x) & Q.negative(y)),
    (Q.positive(y), lambda z: z & Q.positive(y - x)),
    (Q.positive(y), lambda z: z & Q.positive(y + x)),
    (Q.even(y), lambda z: z & Q.eq(y, x)),
    (Q.integer(y), lambda z: z & Q.eq(y, x + 1)),
    (Q.lt(y, 1), lambda z: z & Q.lt(y, x + 1)),
    (Q.zero(u), lambda z: z & Q.eq(u, x * v)),
    (Q.zero(y), lambda z: z & Q.zero(x - y)),
    (Q.ge(y, 0), lambda z: z & Q.ge(y, x)),
]


@pytest.mark.parametrize("cfg", list(CONFIGS))
@pytest.mark.parametrize("i", range(len(OUTSIDE)))
def test_outside_the_condition_the_spellings_agree(i, cfg):
    p, mk = OUTSIDE[i]
    assert _ask(p, mk(Q.zero(x)), cfg) == _ask(p, mk(Q.eq(x, 0)), cfg)


@pytest.mark.parametrize("cfg", list(CONFIGS))
@pytest.mark.parametrize("p, s", [
    (Q.zero(x), Q.eq(x, y) & Q.zero(y)),
    (Q.zero(x), Q.le(x, 0) & Q.ge(x, 0)),
    (~Q.zero(x), Q.lt(x, y) & Q.zero(y)),
    (Q.zero(x) | Q.zero(y), Q.eq(x * y, 0)),
    (Q.zero(n), Q.lt(n, 1) & Q.gt(n, -1)),
])
def test_outside_the_condition_in_the_proposition(p, s, cfg):
    e = {Q.zero(x): Q.eq(x, 0), ~Q.zero(x): Q.ne(x, 0), Q.zero(n): Q.eq(n, 0),
         Q.zero(x) | Q.zero(y): Q.eq(x, 0) | Q.eq(y, 0)}[p]
    assert _ask(p, s, cfg) == _ask(e, s, cfg)


@pytest.mark.xfail(strict=True, reason="known: zero(s) on a sum bounded only by its "
                   "terms' facts does not switch LRA on (relations, 'Zero is an equality')")
@pytest.mark.parametrize("cfg", list(CONFIGS))
def test_outside_the_condition_a_bounded_sum(cfg):
    k = Symbol("k")
    s = Q.integer(k) & Q.integer(x) & Q.negative(k) & Q.positive(x)
    assert _ask(Q.zero(k - x + 1), s, cfg) == _ask(Q.eq(k - x + 1, 0), s, cfg) is False


# warm (one engine, prefix answered first) vs fresh, mixing zero sets and
# eq / order queries
WARM = {
    "zero-set-eq-queries": (Q.zero(n) & Q.composite(g(0, 1)),
                            [Q.eq(u, v), Q.lt(n, 1), Q.eq(n, 0)], Q.composite(g(n, 1))),
    "zero-query-then-plain": (Q.composite(g(0, 1)) & Q.integer(n),
                              [Q.zero(n), Q.composite(g(n, 1)) | ~Q.zero(n)],
                              Q.composite(g(n, 1))),
    "eq-query-then-zero-query": (Q.composite(g(0, 1)) & Q.integer(n),
                                 [Q.eq(n, 0), Q.ge(n, 0)], Q.composite(g(n, 1)) | ~Q.zero(n)),
    "order-set-zero-prefix": (Q.lt(n, 1) & Q.gt(n, -1) & Q.composite(g(0, 1)),
                              [Q.zero(n), Q.zero(g(n, 1))], Q.composite(g(n, 1))),
    "plain-set-zero-prefix": (Q.positive(y) & ~Q.finite(g(0)),
                              [Q.zero(y), Q.zero(g(y)) | ~Q.zero(y)], Q.zero(g(y))),
    "zero-or-set": ((Q.zero(y) | Q.positive(y)) & ~Q.finite(g(0)),
                    [Q.eq(y, 0), Q.zero(y)], Q.zero(g(y))),
    # the query's twin of a set's zero(n) (g(n, 1) only in the prefix)
    "query-twin-prefix": (Q.zero(n) & Q.composite(g(0, 1)) & Q.positive(u - v),
                          [Q.composite(g(n, 1)), Q.zero(g(n, 1) - g(0, 1))],
                          Q.positive(u - v + n)),
    "query-twin-then-plain": (Q.zero(n) & Q.composite(g(0, 1)),
                              [Q.composite(g(n, 1)), Q.prime(g(n, 1))],
                              Q.composite(g(0, 1) + n)),
    "set-app-zero-prefix": (~Q.composite(g(n, 1)) & Q.composite(g(0, 1)),
                            [~Q.zero(n), Q.eq(n, 0)], Q.positive(n) | Q.negative(n)),
}


@pytest.mark.parametrize("cfg", list(CONFIGS))
@pytest.mark.parametrize("name", list(WARM))
def test_warm_answers_as_fresh(name, cfg):
    s, prefix, p = WARM[name]
    e = Engine(cache=DictCache(), **CONFIGS[cfg])
    for q in prefix:
        try:
            ask(q, s, e)
        except Exception:            # noqa: BLE001
            pass
    try:
        warm = ask(p, s, e)
    except Exception as ex:          # noqa: BLE001
        warm = type(ex).__name__
    assert warm == _ask(p, s, cfg)
