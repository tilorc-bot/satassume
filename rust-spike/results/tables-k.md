
## dev

| run | median s | range s |
|---|---:|---:|
| base (live pass) | 0.5328 | 0.5249 to 0.5364 |
| py | 0.18323 | 0.18 to 0.1849 |
| pynogc | 0.18363 | 0.1794 to 0.2132 |
| pyempty | 0.00557 | 0.005493 to 0.005726 |
| rs | 0.01375 | 0.01352 to 0.01385 |
| rsfx | 0.01336 | 0.0132 to 0.01357 |
| rslto | 0.01258 | 0.01252 to 0.01284 |
| rsempty | 0.00001 | 1.052e-05 to 1.075e-05 |
| pytape: tape / plain (16088 hooks) | 0.00129 / 0.00077 | |
| rstape | 0.000063 | 6.16e-05 to 6.594e-05 |

| | Python s | Rust s | k, median of per-round ratios | range |
|---|---:|---:|---:|---:|
| first port: raw | 0.1832 | 0.0137 | **13.3** | 13.2 to 13.6 |
| first port: without dispatch and tape bodies | 0.1771 | 0.0137 | **12.9** | 12.8 to 13.2 |
| tuned, memos on a multiplicative hash: net | 0.1771 | 0.0133 | **13.2** | 13.1 to 13.6 |
| tuned, that + fat LTO, 1 CGU, panic=abort: net | 0.1771 | 0.0125 | **14.1** | 13.8 to 14.3 |
| None queries, raw | 0.1164 | 0.0090 | **13.0** | 12.8 to 13.3 |
| definite queries, raw | 0.0667 | 0.0048 | **13.9** | 13.9 to 14.1 |

| share of a pass | s | of base, median per round |
|---|---:|---:|
| replay net of dispatch and tape | 0.1771 | 33.2% |
| replay raw | 0.1832 | 34.3% |
| live timers: solver minus theories (includes wrapper cost) | 0.2312 | 43.4% |
| live timers: run time, against base | 0.5902 | 1.109x |
| live timers: theories, for scale | 0.0744 | 14.0% |

Cycle collector in the Python replay (timed vs nogc, same round): -0.3%.

## fuzz

| run | median s | range s |
|---|---:|---:|
| base (live pass) | 8.0939 | 7.992 to 8.162 |
| py | 2.75274 | 2.696 to 2.768 |
| pynogc | 2.71924 | 2.665 to 2.737 |
| pyempty | 0.08373 | 0.08362 to 0.0842 |
| rs | 0.17632 | 0.1759 to 0.1787 |
| rsfx | 0.17329 | 0.173 to 0.1752 |
| rslto | 0.16685 | 0.1666 to 0.1679 |
| rsempty | 0.00015 | 0.0001456 to 0.0001457 |
| pytape: tape / plain (584495 hooks) | 0.04522 / 0.02374 | |
| rstape | 0.002062 | 0.002021 to 0.002087 |

| | Python s | Rust s | k, median of per-round ratios | range |
|---|---:|---:|---:|---:|
| first port: raw | 2.7527 | 0.1763 | **15.6** | 15.3 to 15.7 |
| first port: without dispatch and tape bodies | 2.6475 | 0.1741 | **15.2** | 14.9 to 15.3 |
| tuned, memos on a multiplicative hash: net | 2.6475 | 0.1711 | **15.5** | 15.2 to 15.6 |
| tuned, that + fat LTO, 1 CGU, panic=abort: net | 2.6475 | 0.1646 | **16.0** | 15.7 to 16.2 |
| None queries, raw | 2.3339 | 0.1483 | **15.7** | 15.4 to 15.8 |
| definite queries, raw | 0.4188 | 0.0280 | **14.9** | 14.6 to 15.2 |

| share of a pass | s | of base, median per round |
|---|---:|---:|
| replay net of dispatch and tape | 2.6475 | 32.6% |
| replay raw | 2.7527 | 33.9% |
| live timers: solver minus theories (includes wrapper cost) | 3.6996 | 45.8% |
| live timers: run time, against base | 9.2951 | 1.151x |
| live timers: theories, for scale | 1.9107 | 23.6% |

Cycle collector in the Python replay (timed vs nogc, same round): 1.1%.
