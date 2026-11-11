rows 28, digest mismatches 0, rounds per cell [7]

### dev
| tree | Rust median s (min-max, n) | samples | all-D share | Group D s | vs 146 | rust | glue | python | callback | sympy<-rust |
|---|---|---|---|---|---|---|---|---|---|---|
| 50f1421 | 0.767 (0.763-0.977, 7) | 7,779 | 25.0% | 0.191 | +0.033 | 0.080 | 0.043 | 0.357 | 0.071 | 0.021 |
| 42fd78e | 0.763 (0.754-0.938, 7) | 7,720 | 24.8% | 0.190 | +0.032 | 0.082 | 0.044 | 0.355 | 0.071 | 0.020 |

D by Rust module, s (dev): | tree | compile_loop | term | relations_core | lib.rs | entry | session | constfield | solver | context | adapters | session_glue | query |
| 50f1421 | 0.027 | 0.025 | 0.020 | 0.014 | 0.012 | 0.011 | 0.009 | 0.008 | 0.007 | 0.007 | 0.006 | 0.006 |
| 42fd78e | 0.027 | 0.024 | 0.019 | 0.014 | 0.011 | 0.009 | 0.010 | 0.008 | 0.007 | 0.007 | 0.006 | 0.006 |

### fuzz
| tree | Rust median s (min-max, n) | samples | all-D share | Group D s | vs 146 | rust | glue | python | callback | sympy<-rust |
|---|---|---|---|---|---|---|---|---|---|---|
| 50f1421 | 6.536 (6.480-7.179, 7) | 19,937 | 33.5% | 2.191 | +0.201 | 1.009 | 0.514 | 1.312 | 1.114 | 0.372 |
| 42fd78e | 6.451 (6.413-10.549, 7) | 19,570 | 34.2% | 2.205 | +0.215 | 1.012 | 0.522 | 1.274 | 1.042 | 0.372 |

D by Rust module, s (fuzz): | tree | relations_core | compile_loop | lib.rs | adapters | session | constfield | relkeys | term | solver | formula_py | entry | discovery |
| 50f1421 | 0.358 | 0.236 | 0.203 | 0.222 | 0.161 | 0.131 | 0.108 | 0.084 | 0.083 | 0.073 | 0.072 | 0.064 |
| 42fd78e | 0.353 | 0.234 | 0.230 | 0.204 | 0.160 | 0.127 | 0.121 | 0.095 | 0.087 | 0.076 | 0.072 | 0.055 |
