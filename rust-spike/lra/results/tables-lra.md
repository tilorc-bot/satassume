## Replay, seconds, medians over six rounds

| | class | py | pyempty | rs | rsfx | rslto | rsempty |
|---|---|---:|---:|---:|---:|---:|---:|
| dev | whole pass | 0.01717 | 0.00157 | 0.00099 | 0.00089 | 0.00046 | 0.00006 |
| dev | None | 0.00744 | 0.00080 | 0.00031 | 0.00063 | 0.00022 | 0.00003 |
| dev | definite | 0.00972 | 0.00077 | 0.00069 | 0.00026 | 0.00024 | 0.00003 |
| fuzz | whole pass | 0.82093 | 0.06469 | 0.03583 | 0.02995 | 0.02803 | 0.00195 |
| fuzz | None | 0.72269 | 0.05759 | 0.03133 | 0.02614 | 0.02451 | 0.00174 |
| fuzz | definite | 0.09824 | 0.00709 | 0.00451 | 0.00380 | 0.00353 | 0.00021 |

## k_lra, median of per-round ratios (range)

| | class | first port (rs), net | raw | fxhash, net | fxhash + LTO, net |
|---|---|---:|---:|---:|---:|
| dev | whole pass | **16.6** (16.4 to 16.8) | 17.2 (16.9 to 17.4) | 18.7 (18.4 to 19.1) | 38.5 (36.8 to 40.6) |
| dev | None | **23.9** (10.2 to 26.0) | 24.2 (10.9 to 24.9) | 11.2 (10.8 to 31.2) | 34.6 (31.4 to 38.5) |
| dev | definite | **13.5** (12.8 to 31.9) | 14.1 (13.7 to 31.3) | 38.5 (14.5 to 38.8) | 42.2 (41.5 to 43.1) |
| fuzz | whole pass | **22.1** (22.0 to 22.5) | 22.7 (22.6 to 23.1) | 27.0 (26.3 to 27.4) | 28.7 (28.6 to 29.3) |
| fuzz | None | **22.3** (22.1 to 22.7) | 22.9 (22.7 to 23.3) | 27.3 (26.5 to 27.7) | 28.9 (28.8 to 29.5) |
| fuzz | definite | **21.0** (20.9 to 21.3) | 21.6 (21.5 to 21.9) | 25.4 (24.5 to 25.8) | 27.2 (27.1 to 27.9) |

## Shares of the live pass, from `record_lra.py --timers`, medians (range)

| | class | class s | rational sessions | sessions with constants | replay py net / base |
|---|---|---:|---:|---:|---:|
| dev | whole pass | 0.546 | 4.3% (4.3 to 4.4) | 7.2% (7.2 to 7.3) | 2.9% |
| dev | None | 0.324 | 3.2% (3.2 to 3.2) | 8.1% (8.1 to 8.2) | 2.1% |
| dev | definite | 0.222 | 6.0% (6.0 to 6.1) | 5.9% (5.8 to 5.9) | 4.1% |
| fuzz | whole pass | 8.471 | 13.4% (13.2 to 13.5) | 4.0% (4.0 to 4.1) | 9.4% |
| fuzz | None | 7.106 | 14.0% (13.8 to 14.0) | 4.1% (4.1 to 4.1) | 9.9% |
| fuzz | definite | 1.365 | 10.5% (10.3 to 10.5) | 3.7% (3.6 to 3.7) | 6.9% |

Constants sessions are outside k_lra: their time is in r - c, so k_rest has to cover them.


## Whole-pass model, As the code stands: k = 12.9 / 15.2, k_lra first port by class; c = rational sessions; constants in k_rest

| | class | c | r low-high | k_lra | k_rest=1 | 3 | 5 | 10 | inf | k_rest for 2x, low end | high end | same, LTO k_lra |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | whole pass | 4.3% | 44.1-54.4% | 16.6 | 1.39-1.51 | 2.20-3.05 | 2.49-3.82 | 2.77-4.73 | 3.11-6.19 | 2.23 | 1.48 | 2.21 to 1.47 |
| dev | None | 3.2% | 45.1-52.3% | 23.9 | 1.38-1.54 | 2.26-3.10 | 2.59-3.89 | 2.90-4.81 | 3.30-6.29 | 2.13 | 1.44 | 2.12 to 1.44 |
| dev | definite | 6.0% | 43.0-57.6% | 13.5 | 1.39-1.47 | 2.12-2.99 | 2.37-3.76 | 2.60-4.66 | 2.88-6.14 | 2.42 | 1.53 | 2.38 to 1.51 |
| fuzz | whole pass | 13.4% | 40.6-59.0% | 22.1 | 1.60-1.73 | 2.25-3.64 | 2.44-4.66 | 2.62-5.92 | 2.82-8.11 | 1.87 | 1.21 | 1.85 to 1.20 |
| fuzz | None | 14.0% | 41.6-59.1% | 22.3 | 1.63-1.76 | 2.32-3.74 | 2.54-4.82 | 2.73-6.16 | 2.95-8.53 | 1.71 | 1.18 | 1.70 to 1.17 |
| fuzz | definite | 10.5% | 36.2-58.3% | 21.0 | 1.45-1.58 | 1.93-3.18 | 2.07-3.98 | 2.19-4.92 | 2.32-6.44 | 3.74 | 1.39 | 3.68 to 1.38 |

## Whole-pass model, Integer ids: k = 12.9 / 15.2, k_lra first port by class; c = rational sessions; constants in k_rest

| | class | c | r low-high | k_lra | k_rest=1 | 3 | 5 | 10 | inf | k_rest for 2x, low end | high end | same, LTO k_lra |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | whole pass | 4.3% | 44.1-54.4% | 16.6 | 1.53-1.61 | 2.81-3.12 | 3.30-3.94 | 3.80-4.91 | 4.48-6.51 | 1.44 | 1.44 | 1.43 to 1.44 |
| dev | None | 3.2% | 45.1-52.3% | 23.9 | 1.56-1.58 | 2.82-3.17 | 3.35-4.01 | 3.90-4.99 | 4.66-6.61 | 1.47 | 1.41 | 1.47 to 1.41 |
| dev | definite | 6.0% | 43.0-57.6% | 13.5 | 1.49-1.66 | 2.80-3.06 | 3.25-3.88 | 3.69-4.84 | 4.27-6.45 | 1.39 | 1.49 | 1.37 to 1.48 |
| fuzz | whole pass | 13.4% | 40.6-59.0% | 22.1 | 1.78-2.08 | 3.35-3.86 | 3.81-5.04 | 4.25-6.55 | 4.81-9.33 | 0.93 | 1.16 | 0.93 to 1.16 |
| fuzz | None | 14.0% | 41.6-59.1% | 22.3 | 1.81-2.11 | 3.45-3.97 | 3.95-5.22 | 4.43-6.82 | 5.05-9.85 | 0.91 | 1.13 | 0.91 to 1.13 |
| fuzz | definite | 10.5% | 36.2-58.3% | 21.0 | 1.62-1.94 | 2.91-3.36 | 3.24-4.27 | 3.53-5.36 | 3.89-7.21 | 1.06 | 1.32 | 1.06 to 1.32 |

## k_rest for 2x, low end to high end, three ways

Earlier k_r: one factor on all of r, from combine.py. Constants in k_rest: as above. Constants stay in Python: their share at factor 1, k_rest on the remainder.

| | class | as it stands: earlier k_r | constants in k_rest | constants stay in Python | ids: earlier k_r | constants in k_rest | constants stay in Python |
|---|---|---:|---:|---:|---:|---:|---:|
| dev | whole pass | 2.43 to 1.59 | 2.23 to 1.48 | 3.05 to 1.61 | 1.58 to 1.56 | 1.44 to 1.44 | 1.59 to 1.56 |
| dev | None | 2.27 to 1.53 | 2.13 to 1.44 | 2.91 to 1.58 | 1.57 to 1.49 | 1.47 to 1.41 | 1.65 to 1.53 |
| dev | definite | 2.74 to 1.69 | 2.42 to 1.53 | 3.32 to 1.64 | 1.59 to 1.65 | 1.39 to 1.49 | 1.50 to 1.59 |
| fuzz | whole pass | 2.69 to 1.54 | 1.87 to 1.21 | 2.21 to 1.23 | 1.36 to 1.48 | 0.93 to 1.16 | 0.92 to 1.18 |
| fuzz | None | 2.49 to 1.52 | 1.71 to 1.18 | 1.96 to 1.20 | 1.35 to 1.46 | 0.91 to 1.13 | 0.90 to 1.15 |
| fuzz | definite | 4.91 to 1.67 | 3.74 to 1.39 | 6.91 to 1.43 | 1.46 to 1.59 | 1.06 to 1.32 | 1.07 to 1.36 |
