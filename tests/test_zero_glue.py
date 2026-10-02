"""``Q.zero(t)`` is the equality ``t = 0`` for the relation glue (nightly
family A, ``relations.glue_atoms``): the ``zero`` and ``eq`` spellings
answer alike, in the set and in the proposition, and a relation unrelated
to the query adds nothing to a set whose glue a ``zero`` atom switches on.
Each answer below is the correct one (``t = 0`` pointwise)."""
import pytest
from sympy import Abs, Function, Q, Symbol, sqrt, symbols

from satassume.engine import DictCache, Engine
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
