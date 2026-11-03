# sa-node-2-fbb484f

**Verdict: PASS, mixed (dev 1.09x*, dev None 1.12x*, held-out stream 1.05x*, held-out None 1.06x*, ho-battery 1.03x*, fuzz 0.99x, corpus 0.98x*, fork ask 1.03x*; * = beyond A/A noise)**

Candidate: `/home/tilo/dev/sa-node` at `fbb484f` (3-tree A/B (base, fbb484f, a1b0285) in one invocation; test failure approved by forward-chain-3b)

Commits over 9bafaa5:
```
fbb484f engine: key shared sessions on (set, expression), compute the scope only on a hit
f91f207 shared sessions: query-order, fork and planted-bug tests; docs
e80400e engine: reuse a theory-free contextual session for the next query about the same expression
94b820e HANDOFF-sa-node-1: bound and build plan
```

```
satassume/engine.py | 134 +++++++++++++++++++++++++++++++++++++++++++++-------
 1 file changed, 117 insertions(+), 17 deletions(-)
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
| tests_own | pass | 1 failed, 6093 passed, 23 skipped, 18 xfailed, 16 warnings in 378.26s (0:06:18) |
| tests_base_on_cand | pass | 2 failed, 6081 passed, 23 skipped, 18 xfailed, 6 warnings in 438.45s (0:07:18) |

tests_base_on_cand: expected design change, failure approved by forward-chain-3b (not a gate failure): `tests.test_engine::test_contextual_queries_build_and_discard`

tests_own: failed under xdist on loaded orion but passed on a serial rerun (wall-clock-limit tests; not counted): `tests.test_constfield::test_powers_are_refused_quickly`

tests_base_on_cand: failed under xdist on loaded orion but passed on a serial rerun (wall-clock-limit tests; not counted): `tests.test_solver::test_performance_smoke_300_vars`

## Time (pareto1, pinned, alternating cold processes; speedup = base/cand, paired by round)

| workload | metric | tree | base median s | cand median s | speedup | per-round ratio cand/base |
|---|---|---|---|---|---|---|
| dev | seconds | sa-node-2-a1b0285 | 0.526 | 0.489 | **1.090x** | 0.913..0.987 (5) |
| dev | seconds | sa-node-2-fbb484f | 0.526 | 0.482 | **1.090x** | 0.903..0.919 (5) |
| dev | none_s | sa-node-2-a1b0285 | 0.313 | 0.282 | **1.123x** | 0.889..0.988 (5) |
| dev | none_s | sa-node-2-fbb484f | 0.313 | 0.278 | **1.123x** | 0.879..0.893 (5) |
| dev | def_s | sa-node-2-a1b0285 | 0.213 | 0.206 | **1.044x** | 0.947..0.985 (5) |
| dev | def_s | sa-node-2-fbb484f | 0.213 | 0.203 | **1.046x** | 0.937..0.957 (5) |
| ho-stream | seconds | sa-node-2-a1b0285 | 2.983 | 2.855 | **1.047x** | 0.947..0.962 (5) |
| ho-stream | seconds | sa-node-2-fbb484f | 2.983 | 2.845 | **1.052x** | 0.947..0.961 (5) |
| ho-stream | none_s | sa-node-2-a1b0285 | 1.927 | 1.828 | **1.057x** | 0.939..0.953 (5) |
| ho-stream | none_s | sa-node-2-fbb484f | 1.927 | 1.828 | **1.057x** | 0.942..0.955 (5) |
| ho-stream | def_s | sa-node-2-a1b0285 | 1.042 | 1.012 | **1.031x** | 0.961..0.977 (5) |
| ho-stream | def_s | sa-node-2-fbb484f | 1.042 | 1.002 | **1.042x** | 0.956..0.971 (5) |
| ho-battery | seconds | sa-node-2-a1b0285 | 0.628 | 0.615 | **1.025x** | 0.974..0.983 (5) |
| ho-battery | seconds | sa-node-2-fbb484f | 0.628 | 0.614 | **1.027x** | 0.972..0.977 (5) |
| ho-battery | none_s | sa-node-2-a1b0285 | 0.439 | 0.429 | **1.028x** | 0.972..0.980 (5) |
| ho-battery | none_s | sa-node-2-fbb484f | 0.439 | 0.427 | **1.029x** | 0.971..0.973 (5) |
| ho-battery | def_s | sa-node-2-a1b0285 | 0.186 | 0.183 | **1.019x** | 0.979..0.989 (5) |
| ho-battery | def_s | sa-node-2-fbb484f | 0.186 | 0.183 | **1.021x** | 0.972..0.985 (5) |
| ho-fuzz | seconds | sa-node-2-a1b0285 | 7.880 | 7.921 | **0.993x** | 0.999..1.015 (5) |
| ho-fuzz | seconds | sa-node-2-fbb484f | 7.880 | 7.941 | **0.995x** | 1.003..1.013 (5) |
| ho-fuzz | none_s | sa-node-2-a1b0285 | 6.621 | 6.654 | **0.993x** | 1.000..1.016 (5) |
| ho-fuzz | none_s | sa-node-2-fbb484f | 6.621 | 6.677 | **0.993x** | 1.004..1.014 (5) |
| ho-fuzz | def_s | sa-node-2-a1b0285 | 1.032 | 1.037 | **0.995x** | 0.999..1.014 (5) |
| ho-fuzz | def_s | sa-node-2-fbb484f | 1.032 | 1.033 | **1.002x** | 0.995..1.008 (5) |
| corpus | seconds | sa-node-2-a1b0285 | 0.536 | 0.540 | **0.988x** | 1.006..1.023 (5) |
| corpus | seconds | sa-node-2-fbb484f | 0.536 | 0.547 | **0.977x** | 1.017..1.088 (5) |
| corpus | none_s | sa-node-2-a1b0285 | 0.280 | 0.282 | **0.987x** | 1.005..1.025 (5) |
| corpus | none_s | sa-node-2-fbb484f | 0.280 | 0.286 | **0.973x** | 1.020..1.086 (5) |
| corpus | def_s | sa-node-2-a1b0285 | 0.255 | 0.257 | **0.989x** | 1.007..1.021 (5) |
| corpus | def_s | sa-node-2-fbb484f | 0.255 | 0.259 | **0.980x** | 1.013..1.090 (5) |
| fork-battery | ask_s | sa-node-2-a1b0285 | 0.770 | 0.744 | **1.034x** | 0.963..0.969 (5) |
| fork-battery | ask_s | sa-node-2-fbb484f | 0.770 | 0.744 | **1.035x** | 0.960..0.996 (5) |
| fork-battery | ask_none_s | sa-node-2-a1b0285 | 0.497 | 0.482 | **1.032x** | 0.965..0.973 (5) |
| fork-battery | ask_none_s | sa-node-2-fbb484f | 0.497 | 0.481 | **1.031x** | 0.963..1.000 (5) |
| fork-battery | refine_s | sa-node-2-a1b0285 | 1.238 | 1.208 | **1.023x** | 0.971..0.979 (5) |
| fork-battery | refine_s | sa-node-2-fbb484f | 1.238 | 1.215 | **1.020x** | 0.976..1.007 (5) |

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

Phases on dev, instrumented (s, orion, indicative): build 0.810 (base 0.279), engine 0.439 (base 0.135), escalate 0.108 (base 0.056), front 0.143 (base 0.050), prepare 0.441 (base 0.151), propagate 0.107 (base 0.036), search 0.330 (base 0.108)

The stream is satassume's home ground (its corpus was recorded from the same SymPy tests).
