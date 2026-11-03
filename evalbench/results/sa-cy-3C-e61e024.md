# sa-cy-3C-e61e024

**Verdict: PASS, faster (dev 1.33x*, dev None 1.35x*, held-out stream 1.37x*, held-out None 1.39x*, ho-battery 1.29x*, fuzz 1.34x*, corpus 1.36x*, fork ask 1.18x*; * = beyond A/A noise)**

Candidate: `/home/tilo/dev/sa-cy` at `e61e024` (MEASUREMENT: timed as arm 6 of the final A/B (FINAL-READOUT.md); untyped compiled reference there = #320 276dab1 C (0b157b9 + file closing))

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

| workload | metric | tree | base median s | cand median s | speedup | per-round ratio cand/base |
|---|---|---|---|---|---|---|
| dev | seconds | final-320C-276dab1 | 0.531 | 0.444 | **1.195x** | 0.833..0.841 (7) |
| dev | seconds | final-321-3a7b03a | 0.531 | 0.487 | **1.091x** | 0.915..0.919 (7) |
| dev | seconds | final-lra-320C-03ddfb0 | 0.531 | 0.349 | **1.522x** | 0.654..0.719 (7) |
| dev | seconds | final-merge321-320C-a300007 | 0.531 | 0.410 | **1.296x** | 0.771..0.777 (7) |
| dev | seconds | sa-cy-3C-e61e024 | 0.531 | 0.398 | **1.331x** | 0.747..0.755 (7) |
| dev | none_s | final-320C-276dab1 | 0.315 | 0.262 | **1.207x** | 0.825..0.833 (7) |
| dev | none_s | final-321-3a7b03a | 0.315 | 0.280 | **1.123x** | 0.889..0.893 (7) |
| dev | none_s | final-lra-320C-03ddfb0 | 0.315 | 0.194 | **1.624x** | 0.613..0.654 (7) |
| dev | none_s | final-merge321-320C-a300007 | 0.315 | 0.235 | **1.340x** | 0.744..0.750 (7) |
| dev | none_s | sa-cy-3C-e61e024 | 0.315 | 0.233 | **1.350x** | 0.737..0.747 (7) |
| dev | def_s | final-320C-276dab1 | 0.215 | 0.182 | **1.184x** | 0.841..0.853 (7) |
| dev | def_s | final-321-3a7b03a | 0.215 | 0.206 | **1.045x** | 0.952..0.960 (7) |
| dev | def_s | final-lra-320C-03ddfb0 | 0.215 | 0.155 | **1.393x** | 0.715..0.814 (7) |
| dev | def_s | final-merge321-320C-a300007 | 0.215 | 0.175 | **1.235x** | 0.807..0.816 (7) |
| dev | def_s | sa-cy-3C-e61e024 | 0.215 | 0.165 | **1.305x** | 0.757..0.770 (7) |
| ho-stream | seconds | final-320C-276dab1 | 2.997 | 2.457 | **1.220x** | 0.815..0.824 (7) |
| ho-stream | seconds | final-321-3a7b03a | 2.997 | 2.847 | **1.054x** | 0.946..0.956 (7) |
| ho-stream | seconds | final-lra-320C-03ddfb0 | 2.997 | 1.826 | **1.636x** | 0.603..0.615 (7) |
| ho-stream | seconds | final-merge321-320C-a300007 | 2.997 | 2.351 | **1.275x** | 0.778..0.792 (7) |
| ho-stream | seconds | sa-cy-3C-e61e024 | 2.997 | 2.190 | **1.372x** | 0.726..0.748 (7) |
| ho-stream | none_s | final-320C-276dab1 | 1.936 | 1.578 | **1.226x** | 0.809..0.819 (7) |
| ho-stream | none_s | final-321-3a7b03a | 1.936 | 1.822 | **1.063x** | 0.937..0.948 (7) |
| ho-stream | none_s | final-lra-320C-03ddfb0 | 1.936 | 1.124 | **1.716x** | 0.575..0.586 (7) |
| ho-stream | none_s | final-merge321-320C-a300007 | 1.936 | 1.496 | **1.294x** | 0.766..0.780 (7) |
| ho-stream | none_s | sa-cy-3C-e61e024 | 1.936 | 1.397 | **1.389x** | 0.718..0.733 (7) |
| ho-stream | def_s | final-320C-276dab1 | 1.047 | 0.866 | **1.209x** | 0.823..0.830 (7) |
| ho-stream | def_s | final-321-3a7b03a | 1.047 | 1.011 | **1.038x** | 0.961..0.971 (7) |
| ho-stream | def_s | final-lra-320C-03ddfb0 | 1.047 | 0.688 | **1.517x** | 0.650..0.678 (7) |
| ho-stream | def_s | final-merge321-320C-a300007 | 1.047 | 0.840 | **1.244x** | 0.797..0.811 (7) |
| ho-stream | def_s | sa-cy-3C-e61e024 | 1.047 | 0.780 | **1.347x** | 0.739..0.774 (7) |
| ho-battery | seconds | final-320C-276dab1 | 0.630 | 0.531 | **1.186x** | 0.839..0.849 (7) |
| ho-battery | seconds | final-321-3a7b03a | 0.630 | 0.616 | **1.025x** | 0.971..0.981 (7) |
| ho-battery | seconds | final-lra-320C-03ddfb0 | 0.630 | 0.478 | **1.318x** | 0.750..0.762 (7) |
| ho-battery | seconds | final-merge321-320C-a300007 | 0.630 | 0.521 | **1.210x** | 0.822..0.897 (7) |
| ho-battery | seconds | sa-cy-3C-e61e024 | 0.630 | 0.488 | **1.291x** | 0.772..0.782 (7) |
| ho-battery | none_s | final-320C-276dab1 | 0.440 | 0.370 | **1.189x** | 0.837..0.846 (7) |
| ho-battery | none_s | final-321-3a7b03a | 0.440 | 0.429 | **1.029x** | 0.969..0.977 (7) |
| ho-battery | none_s | final-lra-320C-03ddfb0 | 0.440 | 0.335 | **1.314x** | 0.753..0.765 (7) |
| ho-battery | none_s | final-merge321-320C-a300007 | 0.440 | 0.362 | **1.217x** | 0.818..0.837 (7) |
| ho-battery | none_s | sa-cy-3C-e61e024 | 0.440 | 0.339 | **1.297x** | 0.769..0.779 (7) |
| ho-battery | def_s | final-320C-276dab1 | 0.187 | 0.158 | **1.182x** | 0.843..0.855 (7) |
| ho-battery | def_s | final-321-3a7b03a | 0.187 | 0.184 | **1.021x** | 0.975..0.988 (7) |
| ho-battery | def_s | final-lra-320C-03ddfb0 | 0.187 | 0.140 | **1.335x** | 0.740..0.767 (7) |
| ho-battery | def_s | final-merge321-320C-a300007 | 0.187 | 0.157 | **1.195x** | 0.831..1.038 (7) |
| ho-battery | def_s | sa-cy-3C-e61e024 | 0.187 | 0.146 | **1.279x** | 0.777..0.786 (7) |
| final-fuzz | seconds | final-320C-276dab1 | 8.046 | 6.563 | **1.228x** | 0.808..0.825 (7) |
| final-fuzz | seconds | final-321-3a7b03a | 8.046 | 8.042 | **1.004x** | 0.980..1.007 (7) |
| final-fuzz | seconds | final-lra-320C-03ddfb0 | 8.046 | 6.771 | **1.190x** | 0.830..0.847 (7) |
| final-fuzz | seconds | final-merge321-320C-a300007 | 8.046 | 6.584 | **1.221x** | 0.802..0.826 (7) |
| final-fuzz | seconds | sa-cy-3C-e61e024 | 8.046 | 5.970 | **1.348x** | 0.730..0.752 (7) |
| final-fuzz | none_s | final-320C-276dab1 | 6.691 | 5.454 | **1.230x** | 0.807..0.825 (7) |
| final-fuzz | none_s | final-321-3a7b03a | 6.691 | 6.688 | **1.003x** | 0.980..1.007 (7) |
| final-fuzz | none_s | final-lra-320C-03ddfb0 | 6.691 | 5.635 | **1.188x** | 0.830..0.848 (7) |
| final-fuzz | none_s | final-merge321-320C-a300007 | 6.691 | 5.456 | **1.225x** | 0.799..0.823 (7) |
| final-fuzz | none_s | sa-cy-3C-e61e024 | 6.691 | 4.951 | **1.352x** | 0.727..0.750 (7) |
| final-fuzz | def_s | final-320C-276dab1 | 1.133 | 0.916 | **1.234x** | 0.800..0.817 (7) |
| final-fuzz | def_s | final-321-3a7b03a | 1.133 | 1.130 | **1.009x** | 0.980..1.003 (7) |
| final-fuzz | def_s | final-lra-320C-03ddfb0 | 1.133 | 0.939 | **1.208x** | 0.821..0.838 (7) |
| final-fuzz | def_s | final-merge321-320C-a300007 | 1.133 | 0.935 | **1.213x** | 0.812..0.836 (7) |
| final-fuzz | def_s | sa-cy-3C-e61e024 | 1.133 | 0.838 | **1.351x** | 0.730..0.749 (7) |
| ho-fuzz | seconds | final-320C-276dab1 | 7.902 | 6.547 | **1.212x** | 0.818..0.832 (7) |
| ho-fuzz | seconds | final-321-3a7b03a | 7.902 | 7.952 | **0.994x** | 0.989..1.017 (7) |
| ho-fuzz | seconds | final-lra-320C-03ddfb0 | 7.902 | 6.714 | **1.177x** | 0.839..0.859 (7) |
| ho-fuzz | seconds | final-merge321-320C-a300007 | 7.902 | 6.486 | **1.219x** | 0.814..0.822 (7) |
| ho-fuzz | seconds | sa-cy-3C-e61e024 | 7.902 | 5.926 | **1.335x** | 0.737..0.755 (7) |
| ho-fuzz | none_s | final-320C-276dab1 | 6.637 | 5.502 | **1.210x** | 0.819..0.832 (7) |
| ho-fuzz | none_s | final-321-3a7b03a | 6.637 | 6.678 | **0.994x** | 0.989..1.017 (7) |
| ho-fuzz | none_s | final-lra-320C-03ddfb0 | 6.637 | 5.654 | **1.173x** | 0.841..0.862 (7) |
| ho-fuzz | none_s | final-merge321-320C-a300007 | 6.637 | 5.452 | **1.218x** | 0.814..0.823 (7) |
| ho-fuzz | none_s | sa-cy-3C-e61e024 | 6.637 | 4.967 | **1.337x** | 0.736..0.753 (7) |
| ho-fuzz | def_s | final-320C-276dab1 | 1.038 | 0.843 | **1.230x** | 0.805..0.823 (7) |
| ho-fuzz | def_s | final-321-3a7b03a | 1.038 | 1.044 | **0.997x** | 0.989..1.017 (7) |
| ho-fuzz | def_s | final-lra-320C-03ddfb0 | 1.038 | 0.858 | **1.214x** | 0.818..0.835 (7) |
| ho-fuzz | def_s | final-merge321-320C-a300007 | 1.038 | 0.837 | **1.240x** | 0.800..0.811 (7) |
| ho-fuzz | def_s | sa-cy-3C-e61e024 | 1.038 | 0.769 | **1.350x** | 0.727..0.750 (7) |
| corpus | seconds | final-320C-276dab1 | 0.536 | 0.445 | **1.207x** | 0.826..0.839 (7) |
| corpus | seconds | final-321-3a7b03a | 0.536 | 0.543 | **0.987x** | 1.010..1.021 (7) |
| corpus | seconds | final-lra-320C-03ddfb0 | 0.536 | 0.461 | **1.161x** | 0.851..0.912 (7) |
| corpus | seconds | final-merge321-320C-a300007 | 0.536 | 0.451 | **1.187x** | 0.838..0.851 (7) |
| corpus | seconds | sa-cy-3C-e61e024 | 0.536 | 0.393 | **1.361x** | 0.732..0.790 (7) |
| corpus | none_s | final-320C-276dab1 | 0.279 | 0.228 | **1.227x** | 0.812..0.821 (7) |
| corpus | none_s | final-321-3a7b03a | 0.279 | 0.283 | **0.983x** | 1.011..1.022 (7) |
| corpus | none_s | final-lra-320C-03ddfb0 | 0.279 | 0.236 | **1.182x** | 0.837..0.874 (7) |
| corpus | none_s | final-merge321-320C-a300007 | 0.279 | 0.234 | **1.190x** | 0.836..0.854 (7) |
| corpus | none_s | sa-cy-3C-e61e024 | 0.279 | 0.197 | **1.415x** | 0.705..0.728 (7) |
| corpus | def_s | final-320C-276dab1 | 0.256 | 0.216 | **1.184x** | 0.840..0.858 (7) |
| corpus | def_s | final-321-3a7b03a | 0.256 | 0.259 | **0.988x** | 1.008..1.020 (7) |
| corpus | def_s | final-lra-320C-03ddfb0 | 0.256 | 0.224 | **1.140x** | 0.867..0.953 (7) |
| corpus | def_s | final-merge321-320C-a300007 | 0.256 | 0.216 | **1.183x** | 0.840..0.851 (7) |
| corpus | def_s | sa-cy-3C-e61e024 | 0.256 | 0.195 | **1.309x** | 0.761..0.857 (7) |
| fork-battery | ask_s | final-320C-276dab1 | 0.771 | 0.692 | **1.115x** | 0.894..0.936 (7) |
| fork-battery | ask_s | final-321-3a7b03a | 0.771 | 0.746 | **1.030x** | 0.924..1.016 (7) |
| fork-battery | ask_s | final-lra-320C-03ddfb0 | 0.771 | 0.609 | **1.270x** | 0.752..0.826 (7) |
| fork-battery | ask_s | final-merge321-320C-a300007 | 0.771 | 0.669 | **1.156x** | 0.862..0.910 (7) |
| fork-battery | ask_s | sa-cy-3C-e61e024 | 0.771 | 0.655 | **1.181x** | 0.808..0.888 (7) |
| fork-battery | ask_none_s | final-320C-276dab1 | 0.497 | 0.447 | **1.112x** | 0.894..0.946 (7) |
| fork-battery | ask_none_s | final-321-3a7b03a | 0.497 | 0.483 | **1.030x** | 0.916..1.029 (7) |
| fork-battery | ask_none_s | final-lra-320C-03ddfb0 | 0.497 | 0.394 | **1.264x** | 0.746..0.836 (7) |
| fork-battery | ask_none_s | final-merge321-320C-a300007 | 0.497 | 0.433 | **1.153x** | 0.862..0.921 (7) |
| fork-battery | ask_none_s | sa-cy-3C-e61e024 | 0.497 | 0.423 | **1.177x** | 0.800..0.898 (7) |
| fork-battery | refine_s | final-320C-276dab1 | 1.234 | 1.165 | **1.062x** | 0.936..0.967 (7) |
| fork-battery | refine_s | final-321-3a7b03a | 1.234 | 1.213 | **1.016x** | 0.953..1.009 (7) |
| fork-battery | refine_s | final-lra-320C-03ddfb0 | 1.234 | 1.086 | **1.140x** | 0.853..0.905 (7) |
| fork-battery | refine_s | final-merge321-320C-a300007 | 1.234 | 1.143 | **1.082x** | 0.918..0.951 (7) |
| fork-battery | refine_s | sa-cy-3C-e61e024 | 1.234 | 1.129 | **1.097x** | 0.884..0.938 (7) |

Noise floor (A/A, baseline vs itself, BASELINE.md): see there; treat |speedup - 1| below the A/A spread as no change.

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

Phases on dev, instrumented (s, orion, indicative): build 0.276 (base 0.279), engine 0.139 (base 0.135), escalate 0.034 (base 0.056), front 0.051 (base 0.050), prepare 0.147 (base 0.151), propagate 0.028 (base 0.036), search 0.078 (base 0.108)

The stream is satassume's home ground (its corpus was recorded from the same SymPy tests).
