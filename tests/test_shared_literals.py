"""Shared literals in template patterns (``Pattern.eclauses``).

A template rule that expands to ``MIN_SHARED`` or more clauses over the
basis (an Add's ``~negative_infinite(x_i)`` premises) is emitted with one
literal per distributing derived literal, the node's definitional variable
of that literal (``engine.Session._shared_lit``), with only the variable ->
definition direction.  The emitted clauses must say exactly what the
expanded ones say, and answers must not change.
"""
import pytest
from sympy import Add, And, oo, symbols
from sympy.assumptions import Q

from satassume.rules import NPRED, RULE_INSTANTIATED, SHARED, cnf_of
from satassume.solver import Solver
from satassume.sympy_api import ask
from satassume.templates import _common as C, core


def _var(k, i):
    return k * NPRED + i + 1


def _pattern(gen, n):
    return C.Pattern(C.resolve(getattr(core, f'_{gen}_rules')(n, {}), {}), n)


def _ext(lits, nslots):
    """A slot-space clause as solver literals; a shared literal of slot k is
    a variable after all slot variables."""
    out = []
    for k, i, neg in lits:
        if i < NPRED:
            v = _var(k, i)
        else:
            v = nslots * NPRED + k * len(SHARED) + (i - NPRED) + 1
        out.append(-v if neg else v)
    return out


def _defs(nslots, both):
    """The shared variables' definitions: v -> the definition (and the
    converse if ``both``)."""
    out = []
    for k in range(nslots):
        for j, (pred, pos) in enumerate(SHARED):
            v = nslots * NPRED + k * len(SHARED) + j + 1
            units = [c[0] for c in cnf_of(pred, pos)]
            lits = [_var(k, abs(l) - 1) * (1 if l > 0 else -1) for l in units]
            out.extend([-v, l] for l in lits)
            if both:
                out.append([v] + [-l for l in lits])
    return out


def _entails(clauses, tests, nvars):
    s = Solver()
    s.ensure_vars(nvars)
    for c in clauses:
        s.add_clause(c)
    return all(not s.solve([-l for l in t]) for t in tests)


@pytest.mark.parametrize('gen,n', [('add', 2), ('add', 3), ('add', 4), ('add', 5),
                                   ('mul', 2), ('mul', 3)])
def test_eclauses_equivalent_to_clauses(gen, n):
    pat = _pattern(gen, n)
    nslots = n + 1
    nvars = nslots * NPRED + nslots * len(SHARED)
    base = [[_var(k, abs(l) - 1) * (1 if l > 0 else -1) for l in c]
            for k in range(nslots) for c in RULE_INSTANTIATED]
    full = [_ext(l, nslots) for l, _, _ in pat.clauses]
    emitted = [_ext(l, nslots) for l, _, _ in pat.eclauses]
    # the emitted clauses with the one-way definitions give every clause ...
    assert _entails(base + emitted + _defs(nslots, False), full, nvars)
    # ... and say nothing more (the variable may be read as its definition)
    assert _entails(base + full + _defs(nslots, True), emitted, nvars)


def test_shared_literals_shrink_sums():
    for n in (3, 4):
        pat = _pattern('add', n)
        assert pat.eclauses is not pat.clauses
        size = lambda cls: sum(len(l) for l, _, _ in cls)
        assert size(pat.eclauses) < 0.7 * size(pat.clauses)
    # a pattern whose rules all expand to few clauses is emitted as is
    pat = _pattern('mul', 2)
    assert pat.eclauses is pat.clauses


@pytest.mark.parametrize('n', range(2, 9))
def test_infinite_sums(n):
    xs = symbols(f'x0:{n}')
    s = Add(*xs)
    real = [Q.real(x) for x in xs[1:]]
    if n <= core.MAX_ONEOUT:      # infinite sums: up to MAX_ONEOUT terms
        assert ask(Q.positive_infinite(s), And(Q.positive_infinite(xs[0]), *real)) is True
        assert ask(Q.negative_infinite(s), And(Q.negative_infinite(xs[0]), *real)) is True
        assert ask(Q.finite(s), And(Q.positive_infinite(xs[0]), *real)) is False
    # extended reals without -oo (or without +oo) sum to an extended real
    for inf in (Q.negative_infinite, Q.positive_infinite):
        a = And(*[Q.extended_real(x) & ~inf(x) for x in xs])
        assert ask(Q.extended_real(s), a) is True
    a = And(Q.positive_infinite(xs[0]), Q.negative_infinite(xs[1]), *[Q.real(x) for x in xs[2:]])
    assert ask(Q.extended_real(s), a) is None
    assert ask(Q.extended_real(oo + xs[0]), Q.real(xs[0])) is True
