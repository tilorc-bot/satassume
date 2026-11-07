"""rtf_compare.py py|rust MODE N OUT: tests/real_theory_fuzz.py's seeds on one EUF, writing its ANS dump and counts.

real_theory_fuzz compares each answer with a fresh solver of the same class, so on Rust EUF it is Rust against Rust.
Comparing the dumps of a py run and a rust run is what puts Rust against Python. SLICE_SO names the build.
Counts: the level reads the test makes on Rust, and how many saw an open level.
"""
import json
import os
import sys

which, mode, n, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "..", "tests"))
reads = {"all": 0, "open": 0}
if which == "rust":
    sys.path.insert(0, os.environ.get("SLICE_SO") or here)
    import sa_solver
    import satassume.theories.euf.euf as _euf

    class EUFTheory(sa_solver.EUFTheory):
        @property
        def _lims(self):
            v = sa_solver.EUFTheory._lims.__get__(self)
            reads["all"] += 1
            reads["open"] += bool(v)
            return v

    _euf.EUFTheory = EUFTheory

import real_theory_fuzz as rtf

assert (rtf.EUFTheory.__module__ == "__main__") == (which == "rust"), rtf.EUFTheory
bad = []
raised = []
for seed in range(n):
    try:
        rtf.run_seed(seed, mode)
    except rtf.Mismatch as e:
        bad.append((seed, repr(e.args[0][1])[:300]))
    except Exception as e:
        raised.append((seed, type(e).__name__, str(e)[:300]))
with open(out, "w") as f:
    for a in rtf.ANS:
        f.write(repr(a) + "\n")
kinds = {}
for a in rtf.ANS:
    k = f"{a[2]}:{'None' if a[3] is None else (a[3] if isinstance(a[3], bool) else 'set')}"
    kinds[k] = kinds.get(k, 0) + 1
print(json.dumps({"which": which, "mode": mode, "seeds": n, "answers": len(rtf.ANS), "kinds": kinds, "level_reads": reads,
                  "mismatches": bad[:5], "n_mismatch": len(bad), "raised": raised[:5], "n_raised": len(raised),
                  "misses": len(rtf.MISSES)}))
