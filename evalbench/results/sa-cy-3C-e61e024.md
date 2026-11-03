# sa-cy-3C-e61e024

**Verdict: gates PASS (no timing)**

Candidate: `/home/tilo/dev/sa-cy` at `e61e024` (final readout, gates only (C built))

Commits over 9bafaa5:
```
e61e024 solver.pxd: typed Solver attributes and hot-loop locals (measurement build)
0b157b9 Optional compiled build: Cython on 18 unchanged modules
4d8eee4 solver: keep the model-mask shift a Python int when compiled
```

```
satassume/sat/solver.pxd | 64 ++++++++++++++++++++++++++++++++++++++++++++++++
 satassume/sat/solver.py  |  3 ++-
 2 files changed, 66 insertions(+), 1 deletion(-)
```

Build on orion: `CPPFLAGS=-DCYTHON_USE_TYPE_SPECS=1 SATASSUME_CYTHON=1 /home/tilo/dev/sa-cy/.bvenv/bin/python setup.py build_ext --inplace --force -j 8`

Build on pareto1: `None`

Modules load on orion from: `['/home/tilo/dev/sa-eval/cands/sa-cy-3C-e61e024/satassume/sat/solver.cpython-312-aarch64-linux-gnu.so', '/home/tilo/dev/sa-eval/cands/sa-cy-3C-e61e024/satassume/engine.cpython-312-aarch64-linux-gnu.so']`  

## Gates: PASS

| check | result | detail |
|---|---|---|
| stream | pass | 0 of 16232 differ |
| battery | pass | 0 of 16386 differ |
| corpus | pass | 0 of 2863 differ |
| ho-fuzz | pass | 0 of 3000 differ |
| fork-battery | pass | 0 of 103 differ |
| stream-unique | pass | 0 of 8393 differ |
| stream-shuffled | pass | 0 of 8393 differ |
| forkq (fresh process per query) | pass | 0 of 8393 differ |
| tests_own | pass | 6085 passed, 23 skipped, 18 xfailed, 6 warnings in 230.57s (0:03:50) |
| tests_base_on_cand | pass | 6083 passed, 23 skipped, 18 xfailed, 6 warnings in 213.91s (0:03:33) |

## Time (pareto1, pinned, alternating cold processes; speedup = base/cand, paired by round)

(not run)

## Counters (deterministic; cand vs base, delta)

| counter | dev | ho-stream | ho-battery | ho-fuzz | corpus |
|---|---|---|---|---|---|
| context_builds | 833 | 3885 | 503 | 2938 | 1061 |
| set_checks | 833 | 3885 | 503 | 2938 | 1061 |
| sessions | 918 | 4334 | 558 | 3149 | 1816 |
| queries | 883 | 4311 | 587 | 3035 | 1798 |
| escalations | 315 | 1786 | 214 | 2606 | 678 |
| searches | 475 | 2604 | 328 | 2649 | 709 |
| relevant | 583 | 2695 | 213 | 1238 | 569 |
| consistency_checks | 64 | 150 | 43 | 324 | 78 |
| cache_hits | 1248 | 10198 | 939 | 685 | 918 |
| solver_conflicts | 257 | 1695 | 203 | 7720 | 87 |
| solver_decisions | 7738 | 43668 | 5327 | 106578 | 12906 |
| solver_propagations | 53418 | 318857 | 56695 | 790907 | 54680 |
| solver_clauses | 51769 | 308011 | 51477 | 663082 | 59098 |
| solver_vars | 41214 | 235324 | 40397 | 361067 | 61545 |

Phases on dev, instrumented (s, orion, indicative): build 0.273 (base 0.279), engine 0.139 (base 0.135), escalate 0.034 (base 0.056), front 0.051 (base 0.050), prepare 0.143 (base 0.151), propagate 0.028 (base 0.036), search 0.078 (base 0.108)

The stream is satassume's home ground (its corpus was recorded from the same SymPy tests).
