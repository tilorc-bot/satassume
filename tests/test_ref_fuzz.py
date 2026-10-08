"""Differential fuzz against the reference: the CI slice of ``harness/reffuzz.py``.

Each random query is answered by ``ask`` on a fresh engine, twice on an
engine reused across a stream, and by ``ask_ref`` (the specification).
The slice is deterministic (fixed seeds, a few seconds); every finding
fails it, except the accepted differences in ``harness.reffuzz.KNOWN``,
which ``test_known_differences`` pins exactly.

Longer runs (see docs/testing.md):

* ``REFFUZZ_SEEDS=0-19 REFFUZZ_N=3000 pytest tests/test_ref_fuzz.py``
  widens this slice (both generators);
* ``python -m harness.reffuzz --seeds 0-9 -n 3000 [--inconsistent]``
  is the command line (``--out`` / ``--diff`` for cross-version diffs).
"""
import os

import pytest

from harness import reffuzz as R


def _seeds():
    spec = os.environ.get("REFFUZZ_SEEDS")
    return list(R._seeds(spec)) if spec else [0, 1]


N = int(os.environ.get("REFFUZZ_N", "150"))


@pytest.mark.parametrize("seed", _seeds())
@pytest.mark.parametrize("gen", sorted(R.GENERATORS))
def test_engine_agrees_with_reference(gen, seed):
    stats, found = R.run(seed, N, gen=gen)
    assert stats["n"] == N
    assert not found, "\n".join("%s %s | %s | %s" % (k, r, p, a) for k, p, a, r in found)


@pytest.mark.parametrize("p,a,eng,ref,why", R.KNOWN, ids=[k[4][:30] + str(i) for i, k in enumerate(R.KNOWN)])
def test_known_differences(p, a, eng, ref, why):
    """Each accepted difference still reads exactly as recorded.  If a change
    makes the engine agree with ``ask_ref`` here, drop the entry from
    ``KNOWN``; if it changes the difference, update it and say why."""
    P, A = R.parse(p), R.parse(a)
    (e, s1, s2, rr), = R.answer([(P, A)])
    assert (e, s1, s2, rr) == (eng, eng, eng, ref)
    assert R.classify(e, s1, s2, rr), "no longer a difference: drop it from KNOWN"
