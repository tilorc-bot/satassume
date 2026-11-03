# sa-lrashare-1-4f9d931 (MEASUREMENT ONLY, no verdict)

SHARE_THEORY=True (4f9d931) vs the same tree with the switch off (7205480 = fbb484f + switch) vs 9bafaa5.
Timing: pareto1, one pinned bench-container invocation, 3 trees alternating, cold processes, 5 rounds + 1 warm-up (2026-11-03 09:11-09:16 UTC).
No answer gates were run by the evaluator (the worker reports 0 differences on its own runs).

## Time (speedup = base/cand, median of per-round paired ratios; range = per-round cand/base)

| workload | metric | tree | base median s | cand median s | speedup (median paired) | ratio range | rounds |
|---|---|---|---|---|---|---|---|
| dev | seconds | sa-lrashare-1-4f9d931 | 0.526 | 0.409 | 1.279x | 0.778..0.833 | 5 |
| dev | seconds | sa-lrashare-1-7205480 | 0.526 | 0.477 | 1.098x | 0.900..0.917 | 5 |
| dev | none_s | sa-lrashare-1-4f9d931 | 0.312 | 0.232 | 1.343x | 0.741..0.767 | 5 |
| dev | none_s | sa-lrashare-1-7205480 | 0.312 | 0.275 | 1.130x | 0.874..0.892 | 5 |
| dev | def_s | sa-lrashare-1-4f9d931 | 0.213 | 0.177 | 1.198x | 0.830..0.930 | 5 |
| dev | def_s | sa-lrashare-1-7205480 | 0.213 | 0.201 | 1.054x | 0.938..0.955 | 5 |
| ho-stream | seconds | sa-lrashare-1-4f9d931 | 2.984 | 2.180 | 1.372x | 0.729..0.735 | 5 |
| ho-stream | seconds | sa-lrashare-1-7205480 | 2.984 | 2.833 | 1.051x | 0.946..0.955 | 5 |
| ho-stream | none_s | sa-lrashare-1-4f9d931 | 1.927 | 1.363 | 1.416x | 0.706..0.711 | 5 |
| ho-stream | none_s | sa-lrashare-1-7205480 | 1.927 | 1.819 | 1.057x | 0.941..0.951 | 5 |
| ho-stream | def_s | sa-lrashare-1-4f9d931 | 1.042 | 0.801 | 1.302x | 0.767..0.774 | 5 |
| ho-stream | def_s | sa-lrashare-1-7205480 | 1.042 | 0.999 | 1.042x | 0.955..0.963 | 5 |
| ho-battery | seconds | sa-lrashare-1-4f9d931 | 0.626 | 0.559 | 1.124x | 0.884..0.895 | 5 |
| ho-battery | seconds | sa-lrashare-1-7205480 | 0.626 | 0.610 | 1.025x | 0.973..0.981 | 5 |
| ho-battery | none_s | sa-lrashare-1-4f9d931 | 0.437 | 0.394 | 1.114x | 0.893..0.903 | 5 |
| ho-battery | none_s | sa-lrashare-1-7205480 | 0.437 | 0.425 | 1.027x | 0.971..0.980 | 5 |
| ho-battery | def_s | sa-lrashare-1-4f9d931 | 0.186 | 0.162 | 1.149x | 0.863..0.874 | 5 |
| ho-battery | def_s | sa-lrashare-1-7205480 | 0.186 | 0.181 | 1.020x | 0.976..0.983 | 5 |
| ho-fuzz | seconds | sa-lrashare-1-4f9d931 | 7.847 | 8.095 | 0.971x | 1.027..1.035 | 5 |
| ho-fuzz | seconds | sa-lrashare-1-7205480 | 7.847 | 7.946 | 0.989x | 1.005..1.013 | 5 |
| ho-fuzz | none_s | sa-lrashare-1-4f9d931 | 6.593 | 6.832 | 0.967x | 1.031..1.040 | 5 |
| ho-fuzz | none_s | sa-lrashare-1-7205480 | 6.593 | 6.684 | 0.988x | 1.006..1.014 | 5 |
| ho-fuzz | def_s | sa-lrashare-1-4f9d931 | 1.029 | 1.034 | 0.994x | 1.002..1.009 | 5 |
| ho-fuzz | def_s | sa-lrashare-1-7205480 | 1.029 | 1.033 | 0.995x | 1.000..1.006 | 5 |
| corpus | seconds | sa-lrashare-1-4f9d931 | 0.530 | 0.543 | 0.974x | 1.020..1.031 | 5 |
| corpus | seconds | sa-lrashare-1-7205480 | 0.530 | 0.545 | 0.973x | 1.021..1.034 | 5 |
| corpus | none_s | sa-lrashare-1-4f9d931 | 0.276 | 0.284 | 0.970x | 1.023..1.035 | 5 |
| corpus | none_s | sa-lrashare-1-7205480 | 0.276 | 0.285 | 0.968x | 1.025..1.041 | 5 |
| corpus | def_s | sa-lrashare-1-4f9d931 | 0.253 | 0.259 | 0.978x | 1.017..1.028 | 5 |
| corpus | def_s | sa-lrashare-1-7205480 | 0.253 | 0.258 | 0.979x | 1.016..1.027 | 5 |
| fork-battery | ask_s | sa-lrashare-1-4f9d931 | 0.771 | 0.671 | 1.149x | 0.833..0.940 | 5 |
| fork-battery | ask_s | sa-lrashare-1-7205480 | 0.771 | 0.740 | 1.045x | 0.921..1.003 | 5 |
| fork-battery | ask_none_s | sa-lrashare-1-4f9d931 | 0.497 | 0.434 | 1.146x | 0.827..0.946 | 5 |
| fork-battery | ask_none_s | sa-lrashare-1-7205480 | 0.497 | 0.479 | 1.040x | 0.916..1.016 | 5 |
| fork-battery | refine_s | sa-lrashare-1-4f9d931 | 1.235 | 1.139 | 1.084x | 0.896..0.972 | 5 |
| fork-battery | refine_s | sa-lrashare-1-7205480 | 1.235 | 1.208 | 1.025x | 0.952..1.003 | 5 |

## Counters (deterministic, orion): base / off (7205480) / on (4f9d931)

| counter | dev | ho-stream | ho-battery | ho-fuzz | corpus |
|---|---|---|---|---|---|
| context_builds | 833 / 500 / 435 | 3885 / 2704 / 2161 | 503 / 431 / 367 | 2938 / 2937 / 2937 | 1061 / 1033 / 1032 |
| set_checks | 833 / 500 / 435 | 3885 / 2704 / 2161 | 503 / 431 / 367 | 2938 / 2937 / 2937 | 1061 / 1033 / 1032 |
| sessions | 918 / 585 / 520 | 4334 / 3153 / 2610 | 558 / 486 / 422 | 3149 / 3148 / 3148 | 1816 / 1788 / 1787 |
| escalations | 315 / 197 / 178 | 1786 / 1368 / 1190 | 214 / 184 / 159 | 2606 / 2605 / 2605 | 678 / 675 / 675 |
| searches | 475 / 474 / 466 | 2604 / 2604 / 2559 | 328 / 328 / 323 | 2649 / 2649 / 2649 | 709 / 709 / 709 |
| solver_decisions | 7738 / 5115 / 4171 | 43668 / 34588 / 26501 | 5327 / 4767 / 4209 | 106578 / 106568 / 106566 | 12906 / 12811 / 12785 |
| solver_conflicts | 257 / 247 / 157 | 1695 / 1686 / 944 | 203 / 203 / 161 | 7720 / 7720 / 7718 | 87 / 87 / 86 |
| solver_propagations | 53418 / 39384 / 29959 | 318857 / 274004 / 197713 | 56695 / 53067 / 45586 | 790907 / 790853 / 790778 | 54680 / 54409 / 54334 |

The stream is satassume's home ground (its corpus was recorded from the same SymPy tests).
