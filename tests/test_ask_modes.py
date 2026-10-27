"""The answer modes of issue #317: ``check_consistency=False`` (no search
made only to show the assumptions consistent) and ``true_only`` (True or
None, no search for a False).

Every True or False of a mode must be an entailment of the assumptions;
with consistent assumptions ``true_only`` returns True exactly where the
full answer is True, and the unchecked modes the full answer or None.
"""
import itertools
import random

import pytest

from satassume.sat.solver import Solver

from test_solver import _entailed, _load, _models, _random_3sat

MODES = [(c, w) for c in (True, False) for w in (None, True, False)]


def _brute(clauses, nvars, assumptions, lits):
    """The full answer for the conjunction of ``lits``: True, False, None,
    or "inconsistent"."""
    models = _models(clauses, nvars, assumptions)
    if not models:
        return "inconsistent"
    if all(l in _entailed(models, nvars) for l in lits):
        return True
    if not any(all((m[abs(l) - 1] if l > 0 else not m[abs(l) - 1]) for l in lits)
               for m in models):
        return False
    return None


def _check(full, got, check, want):
    if full == "inconsistent":
        if check:
            assert got == "raise"
        # unchecked: any answer is vacuously entailed, or a raise
        return
    assert got != "raise"
    # the full answer, or None; the other answer than ``want`` only when
    # propagation settled it (free); a wanted answer always
    assert got is full or got is None
    if want is None or full is want:
        assert got is full


@pytest.mark.parametrize("seed", range(40))
def test_entails_modes_vs_bruteforce(seed):
    """Solver.entails and entails_all in every mode, on one solver per
    formula reused across queries (the incremental state is part of what
    is checked), against brute force."""
    rng = random.Random(seed)
    nvars = rng.randint(3, 7)
    clauses = _random_3sat(rng, nvars, rng.randint(2, 3 * nvars), k=rng.randint(2, 3))
    if not _models(clauses, nvars):
        return
    s, _ = _load(clauses)
    for _ in range(40):
        assumptions = [v if rng.random() < 0.5 else -v
                       for v in rng.sample(range(1, nvars + 1), rng.randint(0, 3))]
        lits = [v if rng.random() < 0.5 else -v
                for v in rng.sample(range(1, nvars + 1), rng.randint(1, 3))]
        full = _brute(clauses, nvars, assumptions, lits)
        check, want = rng.choice(MODES)
        try:
            if len(lits) == 1 and rng.random() < 0.5:
                got = s.entails(lits[0], assumptions, check=check, want=want)
            else:
                got = s.entails_all(lits, assumptions, check=check, want=want)
        except ValueError:
            got = "raise"
        _check(full, got, check, want)


# --- through sympy_api.ask -------------------------------------------------

sympy = pytest.importorskip("sympy")
from sympy import Q, Symbol, symbols  # noqa: E402

from satassume.engine import Engine  # noqa: E402
from satassume.sympy_api import ask  # noqa: E402

x, y, z = symbols("x y z")

QUERIES = [
    (Q.real(x), Q.positive(x)),
    (Q.positive(x), Q.negative(x)),
    (Q.positive(x), Q.real(x)),
    (Q.nonzero(x), Q.positive(x)),           # a derived predicate (an Or)
    (Q.nonzero(x), Q.zero(x)),
    (Q.nonzero(x), Q.real(x)),
    (Q.positive(x + y), Q.positive(x) & Q.positive(y)),
    (Q.negative(x + y), Q.positive(x) & Q.positive(y)),
    (Q.even(x * y), Q.even(x) & Q.integer(y)),
    (Q.odd(x * y), Q.even(x) & Q.integer(y)),
    (Q.positive(x) | Q.negative(x), Q.nonzero(x)),
    (Q.positive(x) & Q.real(y), Q.positive(x) & Q.negative(y)),
    (Q.positive(x), Q.positive(x) & Q.real(z)),     # split by relevance
    (Q.positive(x), Q.positive(x) & Q.positive(z) & Q.negative(z)),
    (Q.real(y), Q.positive(x) & Q.negative(x)),
    (Q.gt(x, y), Q.gt(x, z) & Q.gt(z, y)),
    (Q.lt(x, y), Q.gt(x, z) & Q.gt(z, y)),
    (Q.positive(-1), Q.positive(x)),
    (Q.positive(2), Q.positive(x) & Q.negative(x)),  # constants never raise
]


def _ask(p, a, **kw):
    try:
        return ask(p, a, engine=Engine(), **kw)
    except ValueError:
        return "raise"


@pytest.mark.parametrize("p,a", QUERIES)
def test_ask_modes(p, a):
    full = _ask(p, a)
    assert _ask(p, a, true_only=True) == (True if full is True else
                                         "raise" if full == "raise" else None)
    for kw in ({"check_consistency": False},
               {"check_consistency": False, "true_only": True}):
        got = _ask(p, a, **kw)
        if full == "raise":
            assert got in ("raise", True, False, None)
            continue
        expect = None if kw.get("true_only") and full is not True else full
        assert got is expect, (kw, got, full)


def test_defaults_unchanged():
    """The defaults are the full answer, memoized under the same key."""
    eng = Engine()
    assert ask(Q.positive(x), Q.negative(x), engine=eng) is False
    assert ask(Q.positive(x), Q.negative(x), engine=eng,
               check_consistency=True, true_only=False) is False
    assert eng.stats["cache_hits"] == 1
    # a mode has its own memo entries: never the full answer's False
    assert ask(Q.positive(x), Q.negative(x), engine=eng, true_only=True) is None
    assert ask(Q.positive(x), Q.negative(x), engine=eng) is False


def test_inconsistent_sets():
    """Checked modes raise as the default does; unchecked ones do not run
    the set's check (no set_checks) and do not read its memo."""
    a = Q.positive(x) & Q.negative(x) & Q.real(y)
    eng = Engine()
    for kw in ({}, {"true_only": True}):
        with pytest.raises(ValueError):
            ask(Q.real(y), a, engine=eng, **kw)
    eng = Engine()
    assert ask(Q.real(y), a, engine=eng, check_consistency=False) is True
    assert eng.stats["set_checks"] == 0 and eng.stats["consistency_checks"] == 0


def test_unchecked_skips_set_check():
    eng = Engine()
    ask(Q.positive(x + y), Q.positive(x) & Q.positive(y), engine=eng)
    assert eng.stats["set_checks"] == 1
    eng = Engine()
    assert ask(Q.positive(x + y), Q.positive(x) & Q.positive(y), engine=eng,
               check_consistency=False) is True
    assert eng.stats["set_checks"] == 0 and eng.stats["plain_sets"] == 1


def test_true_only_skips_false_search():
    """No search for a False: the query that needs one under the full
    answer makes fewer solver calls."""
    p, a = Q.positive(x * y), Q.real(x) & Q.real(y)

    def solves(**kw):
        from satassume.sat import solver as mod
        n = [0]
        orig = mod.Solver._solve

        def counted(self, *args):
            n[0] += 1
            return orig(self, *args)
        mod.Solver._solve = counted
        try:
            r = ask(p, a, engine=Engine(), **kw)
        finally:
            mod.Solver._solve = orig
        return r, n[0]
    full, n_full = solves()
    only, n_only = solves(true_only=True)
    assert full is None and only is None
    assert n_only < n_full
