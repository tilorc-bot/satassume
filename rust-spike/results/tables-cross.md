## Crossing costs, ns per call: median over rounds 1 to 6 (range), net of the empty loop for Python-side rows

### (a) Python into Rust

| call | PyO3 full API | PyO3 abi3-py39 | same call to a Python function |
|---|---:|---:|---:|
| no args, returns None | 14.5 (14.1 to 14.8) | 16.1 (15.8 to 16.4) | 10.3 (9.7 to 10.7) |
| one int in, one out | 27.4 (26.9 to 27.7) | 54.9 (53.8 to 55.1) | 12.5 (11.8 to 13.1) |
| 132 bytes by reference, Option<bool> out | 26.8 (25.9 to 27.1) | 52.2 (50.8 to 52.3) |  |
| 267 bytes, same | 39.7 (38.3 to 40.8) | 63.6 (62.7 to 64.6) |  |
| 538 bytes, same | 68.4 (66.4 to 69.5) | 91.9 (90.9 to 92.9) |  |
| 267 bytes, method on a #[pyclass] | 40.5 (39.8 to 41.3) | 68.5 (67.9 to 70.0) | 12.5 (12.0 to 13.3) |

### (b) Rust into Python

| call | PyO3 full API | PyO3 abi3-py39 | same call from Python, net of its loop |
|---|---:|---:|---:|
| `f()` returning None | 15.5 (15.1 to 15.6) | 16.1 (15.8 to 16.4) | 10.3 (9.6 to 10.7) |
| `f(i)`: int out, int back, converted | 29.3 (28.9 to 30.7) | 47.1 (46.0 to 47.1) | 12.4 (11.8 to 12.8) |
| `f(o)`: object out, None/bool back | 17.1 (17.0 to 17.5) | 34.5 (33.7 to 34.7) | 12.2 (11.6 to 13.9) |
| `o.m(i)` by interned name | 37.1 (36.8 to 37.8) | 80.1 (77.9 to 81.9) | 14.0 (13.3 to 14.6) |
| `f(i)`, lock taken and released per call | 76.5 (75.0 to 76.9) | 96.8 (95.2 to 97.6) |  |
| `f(i)` through raw `PyObject_Vectorcall` | 27.1 (26.8 to 27.4) | n/a | |

### (c) SymPy objects, called from Rust and from Python

**dev**: 249,497 outermost hash entries seen, 249,497 kept (510 distinct objects, 449 distinct by ==); 3,376 eq entries, 538 identical. Top types: Symbol 120,589, Zero 30,776, Mul 29,240, Add 17,780, Pow 12,814.

| operation, warm | from Rust | from Rust, abi3 | from Python, net of loop | Rust minus Python |
|---|---:|---:|---:|---:|
| hash(o) | 39.6 (38.9 to 40.4) | 39.5 (38.7 to 39.6) | 53.4 | -13.8 |
| a == b | 119.9 (117.1 to 120.5) | 118.9 (117.1 to 119.4) | 124.4 | -4.5 |
| id from a Python dict: d[o] | 51.0 (49.7 to 52.3) | 52.8 (51.9 to 53.5) | 50.5 | +0.5 |
| o.args, handle on each element | 75.9 (73.9 to 77.7) | 81.5 (79.5 to 83.4) | 104.5 | -28.6 |
| o.is_number as bool | 396.1 (386.4 to 405.0) | 399.0 (388.6 to 404.6) | 409.1 | -13.0 |
| first hash of an object (_mhash cleared) | 323.5 (312.5 to 327.2) | 316.4 (308.7 to 321.2) | 355.4 | -31.9 |

**fuzz**: 5,048,969 outermost hash entries seen, 296,998 kept (1,836 distinct objects, 1,397 distinct by ==); 158,321 eq entries, 14,824 identical. Top types: Symbol 129,270, Add 68,481, Zero 42,253, Mul 26,864, AppliedBinaryRelation 8,847.

| operation, warm | from Rust | from Rust, abi3 | from Python, net of loop | Rust minus Python |
|---|---:|---:|---:|---:|
| hash(o) | 45.0 (44.1 to 46.4) | 45.1 (44.7 to 45.4) | 61.0 | -16.0 |
| a == b | 170.6 (167.2 to 172.8) | 170.8 (169.7 to 173.3) | 175.0 | -4.4 |
| id from a Python dict: d[o] | 76.6 (75.1 to 78.6) | 78.8 (77.9 to 79.8) | 77.4 | -0.7 |
| o.args, handle on each element | 75.0 (73.8 to 76.0) | 81.5 (78.9 to 82.4) | 99.5 | -24.5 |
| o.is_number as bool | 204.5 (199.0 to 205.3) | 207.1 (202.7 to 208.5) | 208.0 | -3.5 |
| first hash of an object (_mhash cleared) | 315.6 (303.0 to 326.5) | 316.7 (310.7 to 334.3) | 348.0 | -32.4 |

Charges used: per ask low 16.9 ns (callback minus the same call in Python), high 80.1 ns (gross abi3 method call, which also counts entry time the calibrated ask already holds). Per public solver call 14.9 to 54.9 ns, per theory hook 16.9 to 47.1 ns, per query 16.6 to 68.5 ns.

Base (live pass) medians from the three batches, s: dev ceiling 0.578, k 0.533, this batch 0.531; fuzz ceiling 8.133, k 8.094, this batch 8.084.

Digests in this batch: [('dev', '31cd0945c07f02a6'), ('fuzz', '173502b6ef285ad6')]; runs 60.

## Inputs

| | class | S1 low | S1 high | enc q | s, solver | s, drift low | Rust solver | r at S1 high | r at S1 low | asks | crossing low | crossing high | hash+eq of asks low / high |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | whole pass | 12.4% | 25.2% | 0.92% | 33.2% | 30.7% | 2.58% | 44.1% | 54.4% | 282,918 | 0.90% | 4.28% | 8% / 41% |
| dev | None | 12.1% | 23.8% | 0.75% | 35.6% | 31.1% | 2.84% | 45.1% | 52.3% | 151,079 | 0.81% | 3.85% | 9% / 41% |
| dev | definite | 12.6% | 27.2% | 1.22% | 29.8% | 29.8% | 2.20% | 43.0% | 57.6% | 131,839 | 1.04% | 4.92% | 6% / 41% |
| fuzz | whole pass | 8.3% | 26.8% | 0.39% | 32.7% | 32.6% | 2.18% | 40.6% | 59.0% | 5,946,572 | 1.24% | 5.89% | 15% / 47% |
| fuzz | None | 7.7% | 25.4% | 0.37% | 33.2% | 33.0% | 2.19% | 41.6% | 59.1% | 4,815,493 | 1.20% | 5.71% | 15% / 47% |
| fuzz | definite | 11.5% | 33.7% | 0.53% | 30.2% | 30.1% | 2.10% | 36.2% | 58.3% | 1,131,079 | 1.44% | 6.83% | 12% / 47% |

## Overall speedup, low to high, against k_r (the assumed factor on moved code outside the SAT solver)

### As the code stands

| | class | k_r=1 | k_r=1.5 | k_r=2 | k_r=3 | k_r=5 | k_r=10 | k_r=15 | k_r=inf | k_r for 2x |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | whole pass | 1.32-1.42 | 1.63-1.92 | 1.85-2.32 | 2.15-2.94 | 2.46-3.74 | 2.76-4.69 | 2.87-5.13 | 3.14-6.30 | 1.59 to 2.43 |
| dev | None | 1.33-1.47 | 1.66-1.98 | 1.90-2.39 | 2.21-3.01 | 2.55-3.81 | 2.89-4.77 | 3.02-5.20 | 3.32-6.35 | 1.53 to 2.27 |
| dev | definite | 1.29-1.36 | 1.59-1.84 | 1.79-2.24 | 2.06-2.85 | 2.33-3.66 | 2.59-4.63 | 2.69-5.08 | 2.91-6.31 | 1.69 to 2.74 |
| fuzz | whole pass | 1.32-1.41 | 1.61-1.96 | 1.81-2.43 | 2.07-3.19 | 2.33-4.25 | 2.57-5.68 | 2.66-6.39 | 2.87-8.53 | 1.54 to 2.69 |
| fuzz | None | 1.34-1.42 | 1.64-1.98 | 1.85-2.46 | 2.12-3.25 | 2.40-4.36 | 2.67-5.88 | 2.77-6.65 | 3.00-9.01 | 1.52 to 2.49 |
| fuzz | definite | 1.27-1.36 | 1.50-1.86 | 1.65-2.26 | 1.83-2.90 | 2.01-3.75 | 2.16-4.79 | 2.22-5.28 | 2.35-6.65 | 1.67 to 4.91 |

### Integer ids for hash and equality

| | class | k_r=1 | k_r=1.5 | k_r=2 | k_r=3 | k_r=5 | k_r=10 | k_r=15 | k_r=inf | k_r for 2x |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | whole pass | 1.44-1.51 | 1.94-1.95 | 2.27-2.37 | 2.72-3.01 | 3.24-3.85 | 3.78-4.87 | 4.00-5.34 | 4.53-6.62 | 1.56 to 1.58 |
| dev | None | 1.49-1.51 | 1.95-2.01 | 2.28-2.43 | 2.75-3.08 | 3.30-3.93 | 3.87-4.94 | 4.11-5.41 | 4.69-6.67 | 1.49 to 1.57 |
| dev | definite | 1.38-1.52 | 1.87-1.94 | 2.25-2.28 | 2.68-2.92 | 3.17-3.76 | 3.67-4.81 | 3.87-5.29 | 4.35-6.65 | 1.59 to 1.65 |
| fuzz | whole pass | 1.45-1.64 | 2.02-2.11 | 2.47-2.52 | 2.96-3.36 | 3.53-4.56 | 4.12-6.25 | 4.37-7.12 | 4.95-9.89 | 1.36 to 1.48 |
| fuzz | None | 1.46-1.65 | 2.04-2.13 | 2.50-2.56 | 3.03-3.42 | 3.64-4.69 | 4.28-6.48 | 4.55-7.43 | 5.21-10.51 | 1.35 to 1.46 |
| fuzz | definite | 1.40-1.63 | 1.92-2.03 | 2.31-2.35 | 2.68-3.05 | 3.08-4.00 | 3.47-5.21 | 3.62-5.80 | 3.96-7.48 | 1.46 to 1.59 |

## Sensitivity, on the low end (S1 high)

| | class | row | k_r=1 | k_r=3 | k_r=5 | k_r=10 | k_r for 2x |
|---|---|---|---:|---:|---:|---:|---:|
| dev | whole pass | as it stands, the low end itself | 1.32 | 2.15 | 2.46 | 2.76 | 2.43 |
| dev | whole pass | ids, the low end itself | 1.51 | 2.72 | 3.24 | 3.78 | 1.58 |
| dev | whole pass | as it stands, solver k halved in live use | 1.28 | 2.04 | 2.32 | 2.59 | 2.80 |
| dev | whole pass | as it stands, solver share at the live timers' figure | 1.56 | 2.31 | 2.56 | 2.78 | 1.83 |
| dev | whole pass | as it stands, per ask 200 ns | 1.21 | 1.89 | 2.12 | 2.34 | 3.75 |
| dev | whole pass | as it stands, per ask 500 ns | 1.02 | 1.45 | 1.59 | 1.70 | inf |
| dev | whole pass | ids, only P.__hash__ goes | 1.38 | 2.32 | 2.69 | 3.06 | 2.04 |
| dev | whole pass | ids, per other ask 500 ns | 1.48 | 2.61 | 3.09 | 3.58 | 1.67 |
| dev | whole pass | SymPy-reading functions stay in Python (S4), each call at the high charge | 1.39 | 1.91 | 2.07 | 2.20 | 3.90 |
| dev | whole pass | solver only in Rust, rest Python (no assumed factor) | 1.38 | 1.38 | 1.38 | 1.38 | inf |
| dev | None | as it stands, the low end itself | 1.33 | 2.21 | 2.55 | 2.89 | 2.27 |
| dev | None | ids, the low end itself | 1.51 | 2.75 | 3.30 | 3.87 | 1.57 |
| dev | None | as it stands, solver k halved in live use | 1.29 | 2.10 | 2.40 | 2.69 | 2.60 |
| dev | None | as it stands, per ask 200 ns | 1.23 | 1.96 | 2.23 | 2.48 | 3.20 |
| dev | None | as it stands, per ask 500 ns | 1.05 | 1.53 | 1.69 | 1.83 | inf |
| dev | None | ids, only P.__hash__ goes | 1.39 | 2.38 | 2.78 | 3.18 | 1.96 |
| dev | None | ids, per other ask 500 ns | 1.47 | 2.65 | 3.15 | 3.68 | 1.65 |
| dev | None | SymPy-reading functions stay in Python (S4), each call at the high charge | 1.39 | 1.86 | 2.00 | 2.11 | 5.08 |
| dev | None | solver only in Rust, rest Python (no assumed factor) | 1.39 | 1.39 | 1.39 | 1.39 | inf |
| dev | definite | as it stands, the low end itself | 1.29 | 2.06 | 2.33 | 2.59 | 2.74 |
| dev | definite | ids, the low end itself | 1.52 | 2.68 | 3.17 | 3.67 | 1.59 |
| dev | definite | as it stands, solver k halved in live use | 1.26 | 1.97 | 2.22 | 2.45 | 3.19 |
| dev | definite | as it stands, per ask 200 ns | 1.18 | 1.79 | 1.99 | 2.18 | 5.14 |
| dev | definite | as it stands, per ask 500 ns | 0.97 | 1.35 | 1.46 | 1.56 | inf |
| dev | definite | ids, only P.__hash__ goes | 1.37 | 2.25 | 2.58 | 2.90 | 2.17 |
| dev | definite | ids, per other ask 500 ns | 1.48 | 2.57 | 3.01 | 3.46 | 1.69 |
| dev | definite | SymPy-reading functions stay in Python (S4), each call at the high charge | 1.37 | 2.00 | 2.20 | 2.38 | 3.00 |
| dev | definite | solver only in Rust, rest Python (no assumed factor) | 1.37 | 1.37 | 1.37 | 1.37 | inf |
| | | | | | | | |
| fuzz | whole pass | as it stands, the low end itself | 1.32 | 2.07 | 2.33 | 2.57 | 2.69 |
| fuzz | whole pass | ids, the low end itself | 1.64 | 2.96 | 3.53 | 4.12 | 1.36 |
| fuzz | whole pass | as it stands, solver k halved in live use | 1.29 | 1.98 | 2.21 | 2.43 | 3.13 |
| fuzz | whole pass | as it stands, solver share at the live timers' figure | 1.58 | 2.23 | 2.43 | 2.60 | 1.92 |
| fuzz | whole pass | as it stands, per ask 200 ns | 1.19 | 1.75 | 1.93 | 2.09 | 6.43 |
| fuzz | whole pass | as it stands, per ask 500 ns | 0.94 | 1.26 | 1.35 | 1.43 | inf |
| fuzz | whole pass | ids, only P.__hash__ goes | 1.42 | 2.30 | 2.63 | 2.94 | 2.02 |
| fuzz | whole pass | ids, per other ask 500 ns | 1.59 | 2.79 | 3.28 | 3.79 | 1.47 |
| fuzz | whole pass | SymPy-reading functions stay in Python (S4), each call at the high charge | 1.43 | 2.28 | 2.59 | 2.88 | 2.04 |
| fuzz | whole pass | solver only in Rust, rest Python (no assumed factor) | 1.42 | 1.42 | 1.42 | 1.42 | inf |
| fuzz | None | as it stands, the low end itself | 1.34 | 2.12 | 2.40 | 2.67 | 2.49 |
| fuzz | None | ids, the low end itself | 1.65 | 3.03 | 3.64 | 4.28 | 1.35 |
| fuzz | None | as it stands, solver k halved in live use | 1.30 | 2.03 | 2.28 | 2.52 | 2.86 |
| fuzz | None | as it stands, per ask 200 ns | 1.20 | 1.80 | 1.99 | 2.17 | 5.09 |
| fuzz | None | as it stands, per ask 500 ns | 0.95 | 1.30 | 1.40 | 1.48 | inf |
| fuzz | None | ids, only P.__hash__ goes | 1.43 | 2.36 | 2.71 | 3.06 | 1.94 |
| fuzz | None | ids, per other ask 500 ns | 1.59 | 2.85 | 3.38 | 3.93 | 1.45 |
| fuzz | None | SymPy-reading functions stay in Python (S4), each call at the high charge | 1.44 | 2.34 | 2.67 | 2.99 | 1.95 |
| fuzz | None | solver only in Rust, rest Python (no assumed factor) | 1.43 | 1.43 | 1.43 | 1.43 | inf |
| fuzz | definite | as it stands, the low end itself | 1.27 | 1.83 | 2.01 | 2.16 | 4.91 |
| fuzz | definite | ids, the low end itself | 1.63 | 2.68 | 3.08 | 3.47 | 1.46 |
| fuzz | definite | as it stands, solver k halved in live use | 1.24 | 1.76 | 1.92 | 2.07 | 6.85 |
| fuzz | definite | as it stands, per ask 200 ns | 1.12 | 1.54 | 1.66 | 1.77 | inf |
| fuzz | definite | as it stands, per ask 500 ns | 0.87 | 1.11 | 1.17 | 1.22 | inf |
| fuzz | definite | ids, only P.__hash__ goes | 1.37 | 2.05 | 2.27 | 2.48 | 2.74 |
| fuzz | definite | ids, per other ask 500 ns | 1.56 | 2.51 | 2.86 | 3.19 | 1.62 |
| fuzz | definite | SymPy-reading functions stay in Python (S4), each call at the high charge | 1.38 | 2.04 | 2.25 | 2.45 | 2.79 |
| fuzz | definite | solver only in Rust, rest Python (no assumed factor) | 1.37 | 1.37 | 1.37 | 1.37 | inf |
| | | | | | | | |

Solver-only high end, crossings net of a Python call: dev whole pass 1.44x; dev None 1.48x; dev definite 1.38x; fuzz whole pass 1.43x; fuzz None 1.44x; fuzz definite 1.39x.

## Worked example: dev, whole pass, as the code stands, k_r = 5, low end

S1 high 0.252 + crossing (282,918 asks x 80.1 ns + 1115 calls x 68.5 ns) / 0.531 s = 0.0428 + Rust solver 0.0238 + r/k_r 0.441/5 = 0.0883, total 0.4069, speedup 2.46x

## Sampled split of a pass, by the innermost satassume frame

In the boundary with no SymPy frame on the stack, as a share of all samples, median over rounds 1 to 6. Shares, not times.

| code | dev | dev None | dev definite | fuzz | fuzz None | fuzz definite |
|---|---:|---:|---:|---:|---:|---:|
| SAT solver: k covers this | 37.0% | 39.2% | 34.1% | 37.0% | 37.6% | 33.4% |
| LRA: tableau, bounds, adapter | 10.6% | 10.6% | 11.1% | 17.8% | 18.3% | 14.7% |
| SymPy on the stack, inside | 9.6% | 8.3% | 11.3% | 12.1% | 11.7% | 14.2% |
| Relations | 5.7% | 5.4% | 6.3% | 10.4% | 10.0% | 12.0% |
| Session | 9.0% | 8.7% | 8.7% | 7.9% | 7.8% | 8.1% |
| EUF | 1.7% | 1.7% | 1.8% | 4.1% | 4.2% | 3.3% |
| outside the boundary | 8.0% | 7.1% | 9.0% | 3.6% | 3.3% | 5.6% |
| Engine and other engine.py | 4.5% | 4.5% | 4.2% | 2.0% | 2.0% | 2.2% |
| transfer | 0.4% | 0.3% | 0.4% | 1.6% | 1.6% | 1.4% |
| knowledge: templates, rules | 8.5% | 8.3% | 8.4% | 1.3% | 1.2% | 1.6% |
| other sat/: theory dispatch, EqualitySharing, formula | 1.3% | 0.9% | 1.9% | 1.1% | 1.0% | 1.6% |
| LRA: constfield | 2.8% | 3.0% | 2.2% | 0.6% | 0.6% | 0.6% |
| other satassume | 1.2% | 1.3% | 0.9% | 0.5% | 0.5% | 0.6% |

dev, moved code outside the solver, samples with the leaf in another file: fractions.py 303, <string> 124, <frozen abc> 70, <frozen importlib._bootstrap> 34, <frozen importlib._bootstrap_external> 14, __init__.py 4, ast.py 3, crossing.py 2 (of 555).

fuzz, moved code outside the solver, samples with the leaf in another file: fractions.py 7669, <string> 2566, <frozen abc> 1580, <frozen importlib._bootstrap> 655, __init__.py 122, <frozen importlib._bootstrap_external> 11, crossing.py 5, ast.py 1 (of 12609).

dev, largest functions in moved code outside the solver, share of all samples: engine.py:Session._emit_pattern 1.6%, engine.py:_split 1.4%, knowledge/templates/_common.py:_unsubsumed 0.9%, engine.py:Session._compile_patterns 0.9%, theories/lra/lra.py:LRATheory._simplex 0.9%, engine.py:Session.ensure 0.8%, knowledge/rules.py:expand_clause 0.8%, engine.py:Session.emit 0.8%, sat/formula.py:atoms_of 0.8%, engine.py:Session._discover 0.6%, theories/lra/lra.py:LRATheory._var_of_form 0.6%, engine.py:want_of 0.6%, knowledge/templates/_common.py:Pattern.__init__ 0.6%, relations.py:relation_atom 0.5%, theories/lra/lra.py:LRATheory._lin 0.5%, theories/lra/lra.py:LRATheory._register_atom 0.5%.

dev, Fraction and ABC checks under moved code: 5.8% of all samples; <string> (generated dataclass methods): 1.9%; import machinery: 0.7%.

fuzz, largest functions in moved code outside the solver, share of all samples: theories/lra/lra.py:LRATheory._simplex 1.6%, engine.py:Session.emit 1.5%, engine.py:Session._emit_pattern 1.2%, theories/lra/lra.py:LRATheory._register_atom 1.1%, relations.py:Relations._interpret 1.1%, theories/lra/lra.py:LRATheory._var_of_form 1.0%, engine.py:Session.ensure 0.9%, theories/lra/lra.py:LRATheory._branch 0.9%, relations.py:Relations._order_infinite 0.9%, theories/lra/lra.py:LRATheory._concrete 0.8%, relations.py:relation_atom 0.8%, theories/euf/euf.py:EUFTheory.pop_level 0.8%, theories/lra/lra.py:LRATheory._pivot_and_update 0.7%, theories/lra/lra.py:LRATheory.propagate 0.7%, sat/formula.py:atoms_of 0.7%, engine.py:Session._discover 0.6%.

fuzz, Fraction and ABC checks under moved code: 9.4% of all samples; <string> (generated dataclass methods): 2.6%; import machinery: 0.7%.

