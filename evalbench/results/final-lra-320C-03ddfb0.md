# final-lra-320C-03ddfb0

**Verdict: FAIL (gates: tests_own (1), tests_base_on_cand (2))**

Candidate: `/home/tilo/dev/sa-eval` at `03ddfb0` (final readout, gates only (C built))

Commits over 9bafaa5:
```
03ddfb0 Merge commit '276dab1' into HEAD
276dab1 setup.py, test_compiled_build: close the files they read
4f9d931 MEASUREMENT ONLY, not for a PR: SHARE_THEORY = True
7205480 tests: the theory-sessions-not-kept test pins SHARE_THEORY off
e5ca30d engine: SHARE_THEORY, an off-by-default switch that also shares theory sessions (measurement only)
fbb484f engine: key shared sessions on (set, expression), compute the scope only on a hit
f91f207 shared sessions: query-order, fork and planted-bug tests; docs
0b157b9 Optional compiled build: Cython on 18 unchanged modules
e80400e engine: reuse a theory-free contextual session for the next query about the same expression
94b820e HANDOFF-sa-node-1: bound and build plan
4d8eee4 solver: keep the model-mask shift a Python int when compiled
```

```
satassume/engine.py     | 151 ++++++++++++++++++++++++++++++++++++++++++------
 satassume/sat/solver.py |   3 +-
 2 files changed, 136 insertions(+), 18 deletions(-)
```

Build on orion: `SATASSUME_CYTHON=1 /home/tilo/dev/sa-cy/.bvenv/bin/python setup.py build_ext --inplace -j 8`

Build on pareto1: `None`

Modules load on orion from: `['/home/tilo/dev/sa-eval/cands/final-lra-320C-03ddfb0/satassume/sat/solver.cpython-312-aarch64-linux-gnu.so', '/home/tilo/dev/sa-eval/cands/final-lra-320C-03ddfb0/satassume/engine.cpython-312-aarch64-linux-gnu.so']`  

## Gates: FAIL

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
| tests_own | FAIL | 1 failed, 6097 passed, 23 skipped, 18 xfailed, 16 warnings in 265.10s (0:04:25) |
| tests_base_on_cand | FAIL | 2 failed, 6081 passed, 23 skipped, 18 xfailed, 6 warnings in 242.86s (0:04:02) |

### tests_own: differences

* tests.test_set_verdict::test_one_set_check_per_query

### tests_base_on_cand: differences

* tests.test_engine::test_contextual_queries_build_and_discard
* tests.test_set_verdict::test_one_set_check_per_query

## Time (pareto1, pinned, alternating cold processes; speedup = base/cand, paired by round)

(not run)

## Counters (deterministic; cand vs base, delta)

| counter | dev | ho-stream | ho-battery | ho-fuzz | corpus |
|---|---|---|---|---|---|
| context_builds | 435 (-398) | 2161 (-1724) | 367 (-136) | 2937 (-1) | 1032 (-29) |
| set_checks | 435 (-398) | 2161 (-1724) | 367 (-136) | 2937 (-1) | 1032 (-29) |
| sessions | 520 (-398) | 2610 (-1724) | 422 (-136) | 3148 (-1) | 1787 (-29) |
| queries | 883 | 4311 | 587 | 3035 | 1798 |
| escalations | 178 (-137) | 1190 (-596) | 159 (-55) | 2605 (-1) | 675 (-3) |
| searches | 466 (-9) | 2559 (-45) | 323 (-5) | 2649 | 709 |
| relevant | 583 | 2695 | 213 | 1238 | 569 |
| consistency_checks | 64 | 150 | 43 | 324 | 78 |
| cache_hits | 1172 (-76) | 9749 (-449) | 846 (-93) | 685 | 918 |
| solver_conflicts | 157 (-100) | 944 (-751) | 161 (-42) | 7718 (-2) | 86 (-1) |
| solver_decisions | 4171 (-3567) | 26501 (-17167) | 4209 (-1118) | 106566 (-12) | 12785 (-121) |
| solver_propagations | 29959 (-23459) | 197713 (-121144) | 45586 (-11109) | 790778 (-129) | 54334 (-346) |
| solver_clauses | 28598 (-23171) | 188760 (-119251) | 40226 (-11251) | 663003 (-79) | 58840 (-258) |
| solver_vars | 23581 (-17633) | 144897 (-90427) | 31431 (-8966) | 361017 (-50) | 60886 (-659) |

Phases on dev, instrumented (s, orion, indicative): build 0.204 (base 0.279), engine 0.160 (base 0.135), escalate 0.024 (base 0.056), front 0.049 (base 0.050), prepare 0.118 (base 0.151), propagate 0.029 (base 0.036), search 0.074 (base 0.108)

The stream is satassume's home ground (its corpus was recorded from the same SymPy tests).
