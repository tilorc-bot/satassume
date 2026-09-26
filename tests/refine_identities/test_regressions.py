"""The per-bug regressions of ``regressions.py``, each in both identity modes
and under each backend its row names."""
from __future__ import annotations

import re
from contextlib import nullcontext

import pytest

from satrefine import refine
from satrefine.identities.compat import backend
from satrefine.identities.core import driver

from regressions import CASES, Case, holds

MODES = {"generated": driver.tables, "live": driver.live}


def _params():
    for number, case in enumerate(CASES):
        for mode in sorted(MODES):
            for ask_backend in case.backends or (None,):
                name = re.sub(r"\W+", "_", case.bug).strip("_")
                yield pytest.param(case, mode, ask_backend,
                                   id=f"{number:03d}-{name}-{mode}" + (f"-{ask_backend}" if ask_backend else ""))


@pytest.mark.parametrize("case, mode, ask_backend", list(_params()))
def test_regression(case: Case, mode: str, ask_backend: str | None):
    with backend.using(ask_backend) if ask_backend else nullcontext(), MODES[mode]():
        result = refine(case.expr, case.assumptions)
    assert holds(case, result), f"{case.bug}: {case.reason}\n  refine({case.expr}, {case.assumptions}) = {result}"


def test_rows_are_distinct():
    keys = [(c.expr, c.assumptions) for c in CASES]
    assert len(set(keys)) == len(keys)
