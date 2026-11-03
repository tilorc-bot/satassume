
## dev

| run | median s | range s |
|---|---:|---:|
| base (live pass) | 0.5306 | 0.5258 to 0.5372 |
| py | 0.18235 | 0.1808 to 0.185 |
| pynogc | 0.18252 | 0.1804 to 0.1845 |
| pyempty | 0.00552 | 0.005496 to 0.00582 |
| rs | 0.01381 | 0.01352 to 0.01388 |
| rsfx | 0.01337 | 0.01321 to 0.01356 |
| rslto | 0.01263 | 0.01255 to 0.01289 |
| rsempty | 0.00001 | 1.05e-05 to 1.076e-05 |
| pytape: tape / plain (16088 hooks) | 0.00128 / 0.00077 | |
| rstape | 0.000064 | 6.216e-05 to 6.494e-05 |

| | Python s | Rust s | k, median of per-round ratios | range |
|---|---:|---:|---:|---:|
| first port: raw | 0.1824 | 0.0138 | **13.3** | 13.1 to 13.5 |
| first port: without dispatch and tape bodies | 0.1762 | 0.0137 | **12.9** | 12.8 to 13.1 |
| tuned, memos on a multiplicative hash: net | 0.1762 | 0.0133 | **13.3** | 13.1 to 13.6 |
| tuned, that + fat LTO, 1 CGU, panic=abort: net | 0.1762 | 0.0126 | **14.1** | 13.8 to 14.3 |
| None queries, raw | 0.1159 | 0.0090 | **13.0** | 12.8 to 13.2 |
| definite queries, raw | 0.0664 | 0.0048 | **14.0** | 13.7 to 14.1 |

| share of a pass | s | of base, median per round |
|---|---:|---:|
| replay net of dispatch and tape | 0.1762 | 33.2% |
| replay raw | 0.1824 | 34.4% |
| live timers: solver minus theories (includes wrapper cost) | 0.2306 | 43.3% |
| live timers: run time, against base | 0.5889 | 1.108x |
| live timers: theories, for scale | 0.0743 | 14.0% |

Cycle collector in the Python replay (timed vs nogc, same round): 0.4%.

## fuzz

| run | median s | range s |
|---|---:|---:|
| base (live pass) | 8.0340 | 7.988 to 8.11 |
| py | 2.72684 | 2.713 to 2.787 |
| pynogc | 2.72724 | 2.673 to 2.752 |
| pyempty | 0.08378 | 0.08353 to 0.08504 |
| rs | 0.17629 | 0.176 to 0.1773 |
| rsfx | 0.17330 | 0.173 to 0.1849 |
| rslto | 0.16691 | 0.1666 to 0.1676 |
| rsempty | 0.00015 | 0.0001456 to 0.0001458 |
| pytape: tape / plain (584495 hooks) | 0.04503 / 0.02366 | |
| rstape | 0.002044 | 0.002019 to 0.002091 |

| | Python s | Rust s | k, median of per-round ratios | range |
|---|---:|---:|---:|---:|
| first port: raw | 2.7268 | 0.1763 | **15.4** | 15.4 to 15.8 |
| first port: without dispatch and tape bodies | 2.6215 | 0.1741 | **15.0** | 15.0 to 15.4 |
| tuned, memos on a multiplicative hash: net | 2.6215 | 0.1711 | **15.3** | 14.3 to 15.5 |
| tuned, that + fat LTO, 1 CGU, panic=abort: net | 2.6215 | 0.1647 | **15.9** | 15.8 to 16.3 |
| None queries, raw | 2.3119 | 0.1483 | **15.5** | 15.5 to 15.9 |
| definite queries, raw | 0.4149 | 0.0280 | **14.8** | 14.8 to 15.4 |

| share of a pass | s | of base, median per round |
|---|---:|---:|
| replay net of dispatch and tape | 2.6215 | 32.7% |
| replay raw | 2.7268 | 34.0% |
| live timers: solver minus theories (includes wrapper cost) | 3.6930 | 45.9% |
| live timers: run time, against base | 9.2657 | 1.151x |
| live timers: theories, for scale | 1.9089 | 23.7% |

Cycle collector in the Python replay (timed vs nogc, same round): 0.6%.
