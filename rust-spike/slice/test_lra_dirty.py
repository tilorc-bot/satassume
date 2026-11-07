"""PR 328's order for `_dirty` on the Rust core: `LRATheory.propagate` walks it ascending by variable index.

`python test_lra_dirty.py`, or under pytest. Python's theory and the Rust core get the same calls, and `propagate`'s
output has to match in order, and match the order written out here. Assertions on the variables go 1, 2, 0, so ascending,
descending and first-added all give different output: `LRA_MUT=6` (descending) and `LRA_MUT=7` (first added), on a build
with `--features mutants`, each have to fail this. SLICE_SO picks that build, as in `lra_backend.py`.
"""
import os
import sys
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.append(HERE)
import lra_backend  # noqa: E402
import sa_solver  # noqa: E402

# Checked, because a planted bug passes quietly on the wrong build.
if os.environ.get("SLICE_SO"):
    assert os.path.dirname(os.path.abspath(sa_solver.__file__)) == os.path.abspath(os.environ["SLICE_SO"]), \
        sa_solver.__file__


def le(term, rhs):
    return (((term, F(1)),), F(rhs), False, False)


def session(cls):
    """Three variables, each with `v <= 1` and `v <= 2`; `v <= 1` asserted on 1, 2, 0. Returns propagate's output."""
    t = cls()
    tight, loose = {}, {}
    lit = 0
    for name in "xyz":
        lit += 1
        tight[name] = lit
        t.register_atom(lit, le(name, 1))
        lit += 1
        loose[name] = lit
        t.register_atom(lit, le(name, 2))
    t.propagate()
    for name in "yzx":
        t.assert_lit(tight[name])
    return t.propagate(), [loose[n] for n in "xyz"], [tight[n] for n in "xyz"]


def norm(out):
    return [(lit, list(why)) for lit, why in out]


def test_dirty_walks_ascending():
    from satassume.theories.lra.lra import LRATheory as Py
    py, loose, tight = session(Py)
    rs, _, _ = session(lra_backend.LRATheory)
    assert norm(rs) == norm(py)
    assert [lit for lit, _ in rs] == loose, f"not ascending: {[lit for lit, _ in rs]} against {loose}"
    assert [sorted(why) for _, why in rs] == [sorted([loose[i], -tight[i]]) for i in range(3)]


if __name__ == "__main__":
    test_dirty_walks_ascending()
    print("ok")
