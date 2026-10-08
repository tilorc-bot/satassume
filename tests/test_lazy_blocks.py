"""Lazy per-node rule blocks (engine.Session.lazy_blocks): a node's rule block
is registered only when a model of the clauses so far violates it (or on
escalation, or eagerly when a theory / the transfer is bound).  The answers
must be those of eager registration: definite answers, None, and the
inconsistency of the assumptions (ValueError), in fresh and reused engines,
context-free (Engine.is_) and with relations (theories attached)."""
import pytest
from sympy import (Q, symbols, S, I, pi, oo, Rational, Abs, exp, log, sqrt, sin,
                   floor, And, Or, Not)

import satassume.engine as engine_mod
from satassume.engine import Engine
from satassume.solver import Solver
from satassume.sympy_api import ask

x, y, z, t = symbols("x y z t")
n, m = symbols("n m")

QUERIES = [
    # (proposition, assumptions)
    (Q.positive(x * y), Q.positive(x) & Q.positive(y)),
    (Q.positive(x + y), Q.positive(x) & Q.nonnegative(y)),
    (Q.nonnegative(x**2), Q.real(x)),
    (Q.even(n * m), Q.even(n) & Q.integer(m)),
    (Q.odd(n + m), Q.odd(n) & Q.even(m)),
    (Q.prime(n), Q.composite(n)),
    (Q.composite(n * m), Q.prime(n) & Q.prime(m)),
    (Q.real(x + I * y), Q.real(x) & Q.real(y) & Q.nonzero(y)),
    (Q.imaginary(I * x), Q.real(x) & Q.nonzero(x)),
    (Q.finite(exp(x)), Q.real(x)),
    (Q.positive(exp(x)), Q.real(x)),
    (Q.negative(log(x)), Q.positive(x) & Q.lt(x, 1)),
    (Q.zero(x * y), Q.zero(x) | Q.zero(y)),
    (Q.nonzero(x), Q.positive(x) | Q.negative(x)),
    (Q.extended_positive(x + y), Q.positive_infinite(x) & Q.real(y)),
    (Q.integer(floor(x)), Q.real(x)),
    (Q.rational(sqrt(n)), Q.prime(n)),
    (Q.irrational(pi * x), Q.rational(x) & Q.nonzero(x)),
    (Q.positive(Abs(x) + 1), True),
    (Q.real(sin(x)), Q.real(x)),
    (Q.integer(x * y * z * t * n * m), Q.integer(x) & Q.integer(y) & Q.integer(z)
     & Q.integer(t) & Q.integer(n) & Q.integer(m)),
    # inconsistent assumptions (ValueError) and consistency through blocks
    (Q.positive(x), Q.positive(x) & Q.negative(x)),
    (Q.real(x), Q.prime(x) & Q.negative(x)),
    (Q.zero(x), Q.even(x) & Q.odd(x)),
    (Q.integer(x), Q.positive_infinite(x) & Q.finite(x)),
    (Q.positive(y), Q.imaginary(x) & Q.real(x) & Q.positive(y)),
    # relations (theory / transfer bound)
    (Q.gt(x, z), Q.gt(x, y) & Q.gt(y, z)),
    (Q.positive(x), Q.gt(x, y) & Q.positive(y)),
    (Q.ge(x**2, 0), Q.real(x)),
    (Q.lt(x, y), Q.positive(x) & Q.eq(y, x + 1)),
    (Q.integer(x + y), Q.eq(x, 2) & Q.integer(y)),
    (Q.positive(x), Q.eq(x, y) & Q.positive(y)),
    (Q.zero(x), Q.ge(x, 0) & Q.le(x, 0) & Q.real(x)),
    # context-free (Engine.is_)
    (Q.positive(pi + 1), True),
    (Q.irrational(sqrt(2) + 1), True),
    (Q.even(S(4)), True),
    (Q.extended_negative(-oo), True),
    (Q.positive(x**2 + 1), True),
    (Q.complex(x * y), True),
    (Q.algebraic(Rational(1, 3) + I), True),
]


def _answer(prop, asm, eng):
    try:
        return ask(prop, asm, engine=eng)
    except ValueError:
        return "ValueError"


def _answers(lazy, reuse, monkeypatch):
    monkeypatch.setattr(engine_mod, "_LAZY", lazy)
    eng = Engine() if reuse else None
    out = []
    for prop, asm in QUERIES:
        out.append(_answer(prop, asm, eng if reuse else Engine()))
        if reuse:
            # session reuse: the negation and the same query again
            out.append(_answer(Not(prop), asm, eng))
            out.append(_answer(prop, asm, eng))
    return out


@pytest.mark.parametrize("reuse", [False, True])
def test_lazy_blocks_answer_as_eager(reuse, monkeypatch):
    eager = _answers(False, reuse, monkeypatch)
    lazy = _answers(True, reuse, monkeypatch)
    assert lazy == eager


def test_lazy_blocks_are_not_registered_when_unused(monkeypatch):
    calls = []
    orig = Solver.register_block

    def counting(self, base, mentions=0):
        calls.append(base)
        return orig(self, base, mentions)

    monkeypatch.setattr(Solver, "register_block", counting)
    counts = {}
    for lazy in (False, True):
        monkeypatch.setattr(engine_mod, "_LAZY", lazy)
        del calls[:]
        assert ask(Q.positive(x * y), Q.positive(x) & Q.positive(y), engine=Engine()) is True
        counts[lazy] = len(calls)
    assert counts[True] < counts[False]


def test_lazy_block_registered_when_violated(monkeypatch):
    # the open answer needs the blocks: positive(x) & prime(x) has no model
    # with x negative, so only the block of x proves these
    monkeypatch.setattr(engine_mod, "_LAZY", True)
    eng = Engine()
    assert ask(Q.negative(x), Q.prime(x), engine=eng) is False
    assert ask(Q.integer(x + 1), Q.prime(x), engine=eng) is True
    assert ask(Q.odd(x), Q.prime(x) & Q.gt(x, 2), engine=eng) is None
    with pytest.raises(ValueError):
        ask(Q.real(x), Q.prime(x) & Q.imaginary(x), engine=eng)
