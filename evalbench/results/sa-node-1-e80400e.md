# sa-node-1-e80400e

**Verdict: PASS, mixed (dev 1.10x*, dev None 1.13x*, held-out stream 1.04x*, held-out None 1.05x*, ho-battery 1.02x, fuzz 1.00x, corpus 0.97x*, fork ask 1.04x; * = beyond A/A noise)**

Candidate: `/home/tilo/dev/sa-node` at `e80400e` (shared theory-free contextual sessions per (set, scope, expr), SHARED_MAX=4; submitted by forward-chain-3b)

Commits over 9bafaa5:
```
e80400e engine: reuse a theory-free contextual session for the next query about the same expression
94b820e HANDOFF-sa-node-1: bound and build plan
```

```
satassume/engine.py | 96 ++++++++++++++++++++++++++++++++++++++++++++++++++---
 1 file changed, 92 insertions(+), 4 deletions(-)
```

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
| tests_own | pass | 2 failed, 6081 passed, 23 skipped, 18 xfailed, 6 warnings in 620.81s (0:10:20) |
| tests_base_on_cand | pass | 1 failed, 6082 passed, 23 skipped, 18 xfailed, 6 warnings in 291.02s (0:04:51) |

tests_own: expected design change, failure approved by forward-chain-3b (not a gate failure): `tests.test_engine::test_contextual_queries_build_and_discard`

tests_base_on_cand: expected design change, failure approved by forward-chain-3b (not a gate failure): `tests.test_engine::test_contextual_queries_build_and_discard`

tests_own: failed under xdist on loaded orion but passed on a serial rerun (wall-clock-limit tests; not counted): `tests.test_solver::test_performance_smoke_300_vars`

## Time (pareto1, pinned, alternating cold processes; speedup = base/cand, paired by round)

| workload | metric | tree | base median s | cand median s | speedup | per-round ratio cand/base |
|---|---|---|---|---|---|---|
| dev | seconds | sa-node-1-e80400e | 0.526 | 0.481 | **1.097x** | 0.859..0.922 (5) |
| dev | none_s | sa-node-1-e80400e | 0.313 | 0.277 | **1.129x** | 0.833..0.888 (5) |
| dev | def_s | sa-node-1-e80400e | 0.213 | 0.203 | **1.053x** | 0.897..0.972 (5) |
| ho-stream | seconds | sa-node-1-e80400e | 2.974 | 2.848 | **1.043x** | 0.951..0.969 (5) |
| ho-stream | none_s | sa-node-1-e80400e | 1.920 | 1.832 | **1.047x** | 0.948..0.967 (5) |
| ho-stream | def_s | sa-node-1-e80400e | 1.039 | 1.001 | **1.038x** | 0.956..0.970 (5) |
| ho-battery | seconds | sa-node-1-e80400e | 0.626 | 0.616 | **1.017x** | 0.982..0.984 (5) |
| ho-battery | none_s | sa-node-1-e80400e | 0.437 | 0.429 | **1.020x** | 0.977..0.981 (5) |
| ho-battery | def_s | sa-node-1-e80400e | 0.185 | 0.183 | **1.012x** | 0.987..0.992 (5) |
| ho-fuzz | seconds | sa-node-1-e80400e | 7.889 | 7.860 | **1.001x** | 0.992..1.004 (5) |
| ho-fuzz | none_s | sa-node-1-e80400e | 6.623 | 6.620 | **0.997x** | 0.995..1.006 (5) |
| ho-fuzz | def_s | sa-node-1-e80400e | 1.033 | 1.012 | **1.018x** | 0.975..0.987 (5) |
| corpus | seconds | sa-node-1-e80400e | 0.528 | 0.546 | **0.973x** | 1.026..1.036 (5) |
| corpus | none_s | sa-node-1-e80400e | 0.275 | 0.285 | **0.966x** | 1.029..1.040 (5) |
| corpus | def_s | sa-node-1-e80400e | 0.252 | 0.259 | **0.977x** | 1.018..1.031 (5) |
| fork-battery | ask_s | sa-node-1-e80400e | 0.763 | 0.738 | **1.042x** | 0.925..1.004 (5) |
| fork-battery | ask_none_s | sa-node-1-e80400e | 0.492 | 0.478 | **1.039x** | 0.920..1.017 (5) |
| fork-battery | refine_s | sa-node-1-e80400e | 1.224 | 1.201 | **1.025x** | 0.950..1.003 (5) |

Noise floor (A/A, baseline vs itself, BASELINE.md): see there; treat |speedup - 1| below the A/A spread as no change.

## Counters (deterministic; cand vs base, delta)

| counter | dev | ho-stream | ho-battery | ho-fuzz | corpus |
|---|---|---|---|---|---|
| context_builds | 500 (-333) | 2704 (-1181) | 431 (-72) | 2937 (-1) | 1033 (-28) |
| set_checks | 500 (-333) | 2704 (-1181) | 431 (-72) | 2937 (-1) | 1033 (-28) |
| sessions | 585 (-333) | 3153 (-1181) | 486 (-72) | 3148 (-1) | 1788 (-28) |
| queries | 883 | 4311 | 587 | 3035 | 1798 |
| escalations | 197 (-118) | 1368 (-418) | 184 (-30) | 2605 (-1) | 675 (-3) |
| searches | 474 (-1) | 2604 | 328 | 2649 | 709 |
| relevant | 583 | 2695 | 213 | 1238 | 569 |
| consistency_checks | 64 | 150 | 43 | 324 | 78 |
| cache_hits | 1248 | 10198 | 939 | 685 | 918 |
| solver_conflicts | 247 (-10) | 1686 (-9) | 203 | 7720 | 87 |
| solver_decisions | 5115 (-2623) | 34588 (-9080) | 4767 (-560) | 106568 (-10) | 12811 (-95) |
| solver_propagations | 39384 (-14034) | 274004 (-44853) | 53067 (-3628) | 790853 (-54) | 54409 (-271) |
| solver_clauses | 36460 (-15309) | 257244 (-50767) | 46391 (-5086) | 663052 (-30) | 58890 (-208) |
| solver_vars | 28883 (-12331) | 191079 (-44245) | 36419 (-3978) | 361038 (-29) | 60941 (-604) |

Phases on dev, instrumented (s, orion, indicative): build 0.252 (base 0.279), engine 0.151 (base 0.135), escalate 0.035 (base 0.056), front 0.049 (base 0.050), prepare 0.142 (base 0.151), propagate 0.034 (base 0.036), search 0.102 (base 0.108)

The stream is satassume's home ground (its corpus was recorded from the same SymPy tests).
