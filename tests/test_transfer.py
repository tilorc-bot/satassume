"""Predicate transfer across equal terms (satassume.transfer) end to end,
the engine option for uninterpreted relations, and the theory protocol of
TransferTheory (theory_harness.Recorder) on the transfer fuzz."""
import pytest
from sympy import Function, Q, Rational, S, Symbol, symbols, pi

from satassume.engine import DictCache, Engine
from satassume.relations import Relations
from theory_harness import Recorder, ask_with, check_protocol

x, y, z = symbols("x y z")
f = Function("f")


def eng(**kw):
    return Engine(cache=DictCache(), **kw)


# the plan's section 3 table, rows of layer 2.2, and neighbours
TARGETS = [
    (Q.positive(y), Q.eq(x, y) & Q.positive(x), True),
    (Q.positive(f(y)), Q.eq(x, y) & Q.positive(f(x)), True),
    (Q.prime(x), Q.eq(x, 2), True),
    (Q.integer(y), Q.eq(x, y) & Q.even(x), True),
    (Q.even(z), Q.eq(x, y) & Q.eq(y, z) & Q.even(x), True),
    (Q.real(x), Q.eq(x, pi / 2), True),
    (Q.zero(x), Q.eq(x, Rational(1, 2)), False),
    (Q.prime(x), Q.eq(x, y) & Q.prime(y), True),
    (Q.real(x), Q.eq(x, y) & Q.real(y), True),
    (Q.imaginary(x), Q.eq(x, y) & Q.imaginary(y), True),
    (Q.eq(x, y), Q.prime(x) & Q.noninteger(y), False),
    (Q.ne(x, y), Q.prime(x) & Q.noninteger(y), True),
    (Q.eq(x, 2), Q.odd(x), False),
    (Q.eq(f(x), f(y)), Q.eq(x, y), True),
    (Q.odd(f(y)), Q.eq(x, y) & Q.even(f(x)), False),
    (Q.positive(x), Q.eq(x, y) & Q.ne(y, z), None),
    (Q.prime(x), Q.ne(x, y) & Q.prime(y), None),
]


@pytest.mark.parametrize("prop,assum,want", TARGETS, ids=[f"{p}|{a}" for p, a, _ in TARGETS])
def test_transfer_answers(prop, assum, want):
    assert ask_with(eng(), prop, assum) == want


@pytest.mark.parametrize("prop,assum,want", TARGETS[:4], ids=[f"{p}|{a}" for p, a, _ in TARGETS[:4]])
def test_transfer_off(prop, assum, want):
    assert ask_with(eng(transfer=False), prop, assum) is None


def test_inconsistent_under_equality():
    e = eng()
    assert ask_with(e, Q.real(x), Q.eq(x, y) & Q.prime(x) & Q.noninteger(y)) == "inconsistent"
    assert ask_with(e, Q.real(x), Q.eq(x, 2) & Q.odd(x)) == "inconsistent"
    assert ask_with(e, Q.real(x), Q.eq(x, y) & Q.eq(f(x), 1) & Q.zero(f(y))) == "inconsistent"


def test_reused_session_and_cache_stay_contextual():
    """Facts transferred under assumptions never reach the fact cache."""
    e = eng()
    assert ask_with(e, Q.prime(x), Q.eq(x, 2)) is True
    assert ask_with(e, Q.positive(y), Q.eq(x, y) & Q.positive(x)) is True
    assert ask_with(e, Q.prime(x), Q.eq(x, 2)) is True
    assert ask_with(e, Q.prime(x)) is None
    assert ask_with(e, Q.positive(y)) is None
    assert ask_with(e, Q.prime(x), Q.eq(x, 3)) is True
    assert ask_with(e, Q.prime(x), Q.eq(x, 4)) is False


def test_no_equality_no_transfer():
    """Sessions without an equality atom (links' eq(e, 0) do not count)
    never engage the transfer theory."""
    e = eng()
    ask_with(e, Q.positive(x), Q.lt(0, x) & Q.real(x))
    ask_with(e, Q.positive(x + 1), Q.positive(x))
    for s, _ in e._context_sessions.values():
        assert s.xfer is None
        assert not any(type(t).__name__ == "TransferTheory" for t in s.solver.theories())
    ask_with(e, Q.positive(y), Q.eq(x, y) & Q.positive(x))
    assert any(s.xfer is not None for s, _ in e._context_sessions.values())


def test_uninterpreted_option():
    a = Q.positive(x) & Q.lt(x, pi)          # LRA cannot read pi as a bound
    assert ask_with(eng(), Q.positive(x), a) is None
    assert ask_with(eng(uninterpreted="free"), Q.positive(x), a) is True
    bad = Q.positive(x) & Q.negative(x) & Q.lt(x, pi)
    assert ask_with(eng(), Q.real(x), bad) is None
    assert ask_with(eng(uninterpreted="free"), Q.real(x), bad) == "inconsistent"
    with pytest.raises(ValueError):
        Engine(uninterpreted="maybe")


# ----------------------------------------------------------------------
# protocol: every TransferTheory of the fuzz wrapped in a Recorder
# ----------------------------------------------------------------------

def test_protocol_on_fuzz(monkeypatch):
    import satassume.transfer as tr
    import test_transfer_fuzz as fz

    recs = []
    inner_cls = tr.TransferTheory

    def factory(euf):
        r = Recorder(inner_cls(euf))
        recs.append(r)
        return r

    orig = Relations._engage_transfer

    def engage(self):
        orig(self)
        if isinstance(self.xfer, Recorder):
            self.xfer.solver = self.session.solver

    monkeypatch.setattr(tr, "TransferTheory", factory)
    monkeypatch.setattr(Relations, "_engage_transfer", engage)
    for seed in range(40):
        fz.run_seed(seed, "euf" if seed % 2 else "lra")
    assert recs
    kinds = {}
    for r in recs:
        for k, v in check_protocol(r).items():
            kinds[k] = kinds.get(k, 0) + v
    assert kinds.get("propagate") and kinds.get("assert") and kinds.get("pop")
