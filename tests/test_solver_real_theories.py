"""The long-lived solver with the real LRA and EUF theories against fresh
solvers (``real_theory_fuzz``), and the regression behind it.

``REAL_THEORY_SEEDS`` (default 150) seeds per mode; the review of the
held-levels change ran 3,400 per mode with no mismatch and no weaker
``implied``.
"""
from __future__ import annotations

import os

import pytest

import real_theory_fuzz as rtf
from satassume.lra import LRATheory, constraint
from satassume.solver import Solver

SEEDS = int(os.environ.get("REAL_THEORY_SEEDS", "150"))


@pytest.mark.parametrize("mode", ["lra", "euf", "both"])
def test_real_theories_match_fresh_solvers(mode):
    rtf.MISSES.clear()
    for seed in range(SEEDS):
        rtf.run_seed(seed, mode)            # raises Mismatch on a wrong answer
    assert not rtf.MISSES, f"implied weaker than a fresh solver at {rtf.MISSES[:5]}"


def test_implication_of_a_new_ground_atom_is_made_at_root():
    """An LRA atom that is false by itself (``0 <= -1``) is implied false
    when registered.  The implication must be made at root: delivered under
    an assumption level it is dropped at the next pop, and with held levels
    no later search relearns it."""
    def build():
        s = Solver()
        t = LRATheory()
        s.attach_theory(t)
        s.ensure_vars(2)
        s.register_atom(t, 1, constraint({"x": 1}, "<=", 0))
        s.register_atom(t, 2, constraint({}, "<=", -1))
        return s

    live = build()
    live.implied([1])
    live.solve([1])
    assert set(build().implied([-1])) <= set(live.implied([-1]))
    assert live.value(2) is False
