rows 28, digest mismatches 0, rounds per cell [7]

### dev
| tree | Rust median s (min-max, n) | samples | all-D share | Group D s | vs 146 | rust | glue | python | callback | sympy<-rust |
|---|---|---|---|---|---|---|---|---|---|---|
| 6a461f2 | 0.766 (0.760-0.768, 7) | 7,841 | 24.2% | 0.185 | +0.027 | 0.080 | 0.045 | 0.008 | 0.424 | 0.023 |
| d25b1a7 | 0.764 (0.760-0.769, 7) | 7,768 | 24.6% | 0.188 | +0.030 | 0.079 | 0.041 | 0.010 | 0.419 | 0.025 |

D by Rust module, s (dev): | tree | compile_loop | term | relations_core | lib.rs | entry | constfield | session | context | solver | session_glue | adapters | query |
| 6a461f2 | 0.028 | 0.020 | 0.018 | 0.014 | 0.010 | 0.009 | 0.010 | 0.007 | 0.007 | 0.006 | 0.007 | 0.006 |
| d25b1a7 | 0.029 | 0.021 | 0.018 | 0.014 | 0.010 | 0.011 | 0.009 | 0.008 | 0.007 | 0.007 | 0.007 | 0.006 |

### fuzz
| tree | Rust median s (min-max, n) | samples | all-D share | Group D s | vs 146 | rust | glue | python | callback | sympy<-rust |
|---|---|---|---|---|---|---|---|---|---|---|
| 6a461f2 | 6.463 (6.428-6.520, 7) | 19,550 | 33.7% | 2.178 | +0.188 | 0.986 | 0.536 | 0.027 | 2.328 | 0.382 |
| d25b1a7 | 6.402 (6.381-6.440, 7) | 19,452 | 33.9% | 2.172 | +0.182 | 0.999 | 0.507 | 0.028 | 2.286 | 0.384 |

D by Rust module, s (fuzz): | tree | relations_core | compile_loop | lib.rs | adapters | session | constfield | relkeys | term | solver | formula_py | entry | discovery |
| 6a461f2 | 0.374 | 0.228 | 0.209 | 0.204 | 0.166 | 0.117 | 0.104 | 0.089 | 0.086 | 0.073 | 0.073 | 0.065 |
| d25b1a7 | 0.345 | 0.217 | 0.215 | 0.210 | 0.142 | 0.120 | 0.108 | 0.091 | 0.091 | 0.086 | 0.072 | 0.067 |
