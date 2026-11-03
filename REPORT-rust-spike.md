# Rust spike: crossing cost and overall estimate for `ask` (issue 323)

Against main `9bafaa5`. **This is an estimate from combined measurements. No combined system was built or run**: shares from
`REPORT-rust-ceiling.md`, k from `rust-spike/RESULT-k.md` and the crossing costs below are added together.

## Result

**What has been measured does not clear 2x. The overall number clears it only if an assumed factor holds.** Rust on the SAT
solver alone, with everything else left in Python, gives 1.37x to 1.48x, because the solver is only about a third of a pass.
Everything above that depends on k_r, the speedup of the moved code outside the solver. k_r has not been measured.

| whole pass | dev | fuzz 424242 |
|---|---:|---:|
| Solver only in Rust, rest in Python (no assumed factor) | 1.38x to 1.44x | 1.42x to 1.43x |
| As the code stands, k_r = 1 (moved, no faster) | 1.32x to 1.42x | 1.32x to 1.41x |
| As the code stands, k_r = 5 (assumed) | 2.46x to 3.74x | 2.33x to 4.25x |
| As the code stands, k_r needed for 2x | 1.59 to 2.43 | 1.54 to 2.69 |
| Integer ids, k_r = 1 | 1.44x to 1.51x | 1.45x to 1.64x |
| Integer ids, k_r = 5 (assumed) | 3.24x to 3.85x | 3.53x to 4.56x |
| Integer ids, k_r needed for 2x | 1.56 to 1.58 | 1.36 to 1.48 |

By answer, low to high across each cell. The hardest class is definite answers on fuzz as the code stands, whose low end needs
k_r = 4.91 and only reaches 2.01x at k_r = 5.

**As the code stands**

|  | class | k_r=1 | k_r=2 | k_r=3 | k_r=5 | k_r=15 | k_r for 2x |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dev | whole pass | 1.32-1.42 | 1.85-2.32 | 2.15-2.94 | 2.46-3.74 | 2.87-5.13 | 1.59 to 2.43 |
| dev | None | 1.33-1.47 | 1.90-2.39 | 2.21-3.01 | 2.55-3.81 | 3.02-5.20 | 1.53 to 2.27 |
| dev | definite | 1.29-1.36 | 1.79-2.24 | 2.06-2.85 | 2.33-3.66 | 2.69-5.08 | 1.69 to 2.74 |
| fuzz | whole pass | 1.32-1.41 | 1.81-2.43 | 2.07-3.19 | 2.33-4.25 | 2.66-6.39 | 1.54 to 2.69 |
| fuzz | None | 1.34-1.42 | 1.85-2.46 | 2.12-3.25 | 2.40-4.36 | 2.77-6.65 | 1.52 to 2.49 |
| fuzz | definite | 1.27-1.36 | 1.65-2.26 | 1.83-2.90 | 2.01-3.75 | 2.22-5.28 | 1.67 to 4.91 |

**Integer ids for hash and equality**

|  | class | k_r=1 | k_r=2 | k_r=3 | k_r=5 | k_r=15 | k_r for 2x |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dev | whole pass | 1.44-1.51 | 2.27-2.37 | 2.72-3.01 | 3.24-3.85 | 4.00-5.34 | 1.56 to 1.58 |
| dev | None | 1.49-1.51 | 2.28-2.43 | 2.75-3.08 | 3.30-3.93 | 4.11-5.41 | 1.49 to 1.57 |
| dev | definite | 1.38-1.52 | 2.25-2.28 | 2.68-2.92 | 3.17-3.76 | 3.87-5.29 | 1.59 to 1.65 |
| fuzz | whole pass | 1.45-1.64 | 2.47-2.52 | 2.96-3.36 | 3.53-4.56 | 4.37-7.12 | 1.36 to 1.48 |
| fuzz | None | 1.46-1.65 | 2.50-2.56 | 3.03-3.42 | 3.64-4.69 | 4.55-7.43 | 1.35 to 1.46 |
| fuzz | definite | 1.40-1.63 | 2.31-2.35 | 2.68-3.05 | 3.08-4.00 | 3.62-5.80 | 1.46 to 1.59 |

Three things to take from this:

- **Crossing is cheap in a tight loop.** One query's call costs 27 to 92 ns, against about 2.7 ms per query on fuzz. A callback
  costs 15 to 37 ns (16 to 80 ns on `abi3`). `hash` and `==` from Rust on real SymPy objects take 40 to 45 ns and 120 to 171 ns,
  no more than the same calls from Python. All the asks together cost 0.8% to 6.8% of a pass. The 200 ns the ceiling report
  assumed is about 2.5x the highest charge measured here.
- **Integer ids take the risk out of the crossing.** As the code stands, 200 ns per ask live would keep definite fuzz answers
  below 2x at the low end at any k_r, and whole-pass fuzz would need k_r = 6.4. With ids, even 500 ns on each remaining ask needs
  only k_r = 1.47 to 1.67. A warm hash from Rust measured 3.1x to 3.6x below its live calibrated cost, so a tight loop cannot rule
  out a 200 ns live charge.
- **The size of the result is now set by k_r.** 41% to 59% of a whole pass is moved code that k doesn't cover. Rows below 2x are in
  [Sensitivity](#sensitivity).

**What this doesn't settle:** k_r on any part of that code; the live cost of a crossing beside running Python; that id equality
matches `==` everywhere; and every limit in [Limits](#limits), including the ones carried over from the k measurement.

## Crossing costs

Pinned as below. Medians over six rounds, with the range over rounds. PyO3 0.30.1 on CPython 3.12, in two builds: the full API,
and `abi3-py39`, where one wheel per platform serves every CPython version.

**Binding.** PyO3, because nothing below it is much cheaper: a raw `PyObject_Vectorcall` takes 27.1 ns where PyO3's call takes
29.3 ns. Any binding ends at the same C call, so the choice that shows up in the numbers is full API or `abi3`, not PyO3 or
something else. `abi3` adds up to about 43 ns on calls that convert ints or look up a method by name, and nothing measurable on
`hash` and `==`. cffi and others were not measured.

### (a) Python into Rust

| call | PyO3 full API | PyO3 abi3-py39 | same call to a Python function |
|---|---:|---:|---:|
| no args, returns None | 14.5 (14.1 to 14.8) | 16.1 (15.8 to 16.4) | 10.3 (9.7 to 10.7) |
| one int in, one out | 27.4 (26.9 to 27.7) | 54.9 (53.8 to 55.1) | 12.5 (11.8 to 13.1) |
| 132 bytes by reference, Option<bool> out | 26.8 (25.9 to 27.1) | 52.2 (50.8 to 52.3) |  |
| 267 bytes, same | 39.7 (38.3 to 40.8) | 63.6 (62.7 to 64.6) |  |
| 538 bytes, same | 68.4 (66.4 to 69.5) | 91.9 (90.9 to 92.9) |  |
| 267 bytes, method on a #[pyclass] | 40.5 (39.8 to 41.3) | 68.5 (67.9 to 70.0) | 12.5 (12.0 to 13.3) |

Fuzz makes 3,296 boundary calls. At the worst row that is 0.3 ms of an 8 s pass, about 0.004%.

### (b) Rust into Python

| call | PyO3 full API | PyO3 abi3-py39 | same call from Python, net of its loop |
|---|---:|---:|---:|
| `f()` returning None | 15.5 (15.1 to 15.6) | 16.1 (15.8 to 16.4) | 10.3 (9.6 to 10.7) |
| `f(i)`: int out, int back, converted | 29.3 (28.9 to 30.7) | 47.1 (46.0 to 47.1) | 12.4 (11.8 to 12.8) |
| `f(o)`: object out, None/bool back | 17.1 (17.0 to 17.5) | 34.5 (33.7 to 34.7) | 12.2 (11.6 to 13.9) |
| `o.m(i)` by interned name | 37.1 (36.8 to 37.8) | 80.1 (77.9 to 81.9) | 14.0 (13.3 to 14.6) |
| `f(i)`, lock taken and released per call | 76.5 (75.0 to 76.9) | 96.8 (95.2 to 97.6) |  |
| `f(i)` through raw `PyObject_Vectorcall` | 27.1 (26.8 to 27.4) | n/a | |

Rust holds the interpreter lock across the loop in every row but one. Releasing it and taking it back for each callback adds
about 47 to 50 ns.

### (c) SymPy objects, called from Rust and from Python

The objects are the real receivers: a live pass with `sys.monitoring` on SymPy's `__hash__` and `__eq__`, keeping outermost
entries inside the boundary (every hash on dev, every 17th on fuzz, all eq). The timing runs after the pass, so hashes are warm.

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

- **Rust is no slower than Python here.** `hash(o)` from Python pays for the global lookup and the builtin call; Rust goes
  straight to `PyObject_Hash`. A dict lookup in a loop is the same on both sides, within a nanosecond.
- **Few objects carry the hashes.** The 249,497 dev hashes land on 510 distinct objects, 449 distinct by `==`. The fuzz sample of
  296,998 lands on 1,836 and 1,397. The fuzz counts are from every 17th hash, so the full set is larger. So an id table stays
  small on these workloads, and about 60% of the hash samples are `Symbol`s and singletons.
- **Counts reproduce.** The hash entries match the ceiling report exactly. The eq entries (3,376 and 158,321) match its per-caller
  data for `__eq__`; its "eq" row (3,726 and 172,391) also includes other functions.
- **Warm floor against live cost.** 249,497 x 39.6 ns is 9.9 ms, 1.9% of dev, and 5,048,969 x 45.0 ns is 227 ms, 2.8% of fuzz. The
  ceiling report's calibrated figures are 6.3% and 8.7%. This estimate keeps the calibrated figure for the high S and the sampler
  for the low S, so it doesn't take the loop's optimistic number.

## The arithmetic

For a class of queries, each term a share of that class's Python time:

    speedup = 1 / (S + X + R + r / k_r)

| term | meaning | source |
|---|---|---|
| S | what stays in Python: outside the boundary, encoding the query, the SymPy asks | ceiling report S1, low and high |
| X | crossings: one call per boundary call, one callback per ask, ids | (a), (b), (c) x counts in the ceiling report |
| R | the solver in Rust: Rust replay time / live pass | `RESULT-k.md` raw runs (k 12.9 and 15.2) |
| r | moved code outside the solver: 1 - S1 - s, where s is the solver's Python share | subtraction, checked by sampling below |
| k_r | the factor on r | **assumed** |

**As the code stands**, every SymPy ask is a callback. **Integer ids:** hash and eq asks are gone from S; other asks remain
callbacks, and ids are looked up in a Python dict at (c)'s cost.

**Low and high of each cell:**

| | low end | high end |
|---|---|---|
| S | S1 high, calibrated | S1 low, corrected sampler |
| Per ask | 80.1 ns, the gross `abi3` method call. This also counts entry time the calibrated ask already holds | 16.9 ns, a callback minus the same call in Python |
| Per query | 68.5 ns (`abi3` method) | 16.6 to 29.4 ns, net of a Python call |
| s | Over the largest base of the three batches | Over the base of the k batch |
| Ids, added lookups | Two per other ask, plus a first hash for each node in `enc cl` | Lookup and first hash for each node in `enc cl` |
| Hash and eq removed, share of asks | Calibrated, 41% and 47% | Corrected sampler, 6% to 15% |

The corrected sampler moves thin calls to their callers, which puts hash time in r. So at small k_r, ids on S1 low is below ids
on S1 high, and each cell shows the smaller first. The class split of calibrated hash and eq uses the whole-pass fraction,
because that data has no class split. The solver and S1 are from different batches: dev's base was 0.578 s in the ceiling batch
and 0.533 s and 0.531 s in the k batch and this one, while fuzz stayed at 8.13, 8.09 and 8.08 s. So dev's S1 is a share of a
slower batch, and s is shown both ways.

| | class | S1 low | S1 high | enc q | s, solver | s, drift low | Rust solver | r at S1 high | r at S1 low | asks | crossing low | crossing high | hash+eq of asks low / high |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | whole pass | 12.4% | 25.2% | 0.92% | 33.2% | 30.7% | 2.58% | 44.1% | 54.4% | 282,918 | 0.90% | 4.28% | 8% / 41% |
| dev | None | 12.1% | 23.8% | 0.75% | 35.6% | 31.1% | 2.84% | 45.1% | 52.3% | 151,079 | 0.81% | 3.85% | 9% / 41% |
| dev | definite | 12.6% | 27.2% | 1.22% | 29.8% | 29.8% | 2.20% | 43.0% | 57.6% | 131,839 | 1.04% | 4.92% | 6% / 41% |
| fuzz | whole pass | 8.3% | 26.8% | 0.39% | 32.7% | 32.6% | 2.18% | 40.6% | 59.0% | 5,946,572 | 1.24% | 5.89% | 15% / 47% |
| fuzz | None | 7.7% | 25.4% | 0.37% | 33.2% | 33.0% | 2.19% | 41.6% | 59.1% | 4,815,493 | 1.20% | 5.71% | 15% / 47% |
| fuzz | definite | 11.5% | 33.7% | 0.53% | 30.2% | 30.1% | 2.10% | 36.2% | 58.3% | 1,131,079 | 1.44% | 6.83% | 12% / 47% |

**Worked example, dev, whole pass, as the code stands, k_r = 5, low end.** S1 high 0.252 + crossing (282,918 asks x 80.1 ns + 1115 calls x 68.5 ns) / 0.531 s = 0.0428 + Rust solver 0.0238 + r/k_r 0.441/5 = 0.0883, total 0.4069, speedup 2.46x

## Overall tables

**As the code stands**

| | class | k_r=1 | k_r=1.5 | k_r=2 | k_r=3 | k_r=5 | k_r=10 | k_r=15 | k_r=inf | k_r for 2x |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | whole pass | 1.32-1.42 | 1.63-1.92 | 1.85-2.32 | 2.15-2.94 | 2.46-3.74 | 2.76-4.69 | 2.87-5.13 | 3.14-6.30 | 1.59 to 2.43 |
| dev | None | 1.33-1.47 | 1.66-1.98 | 1.90-2.39 | 2.21-3.01 | 2.55-3.81 | 2.89-4.77 | 3.02-5.20 | 3.32-6.35 | 1.53 to 2.27 |
| dev | definite | 1.29-1.36 | 1.59-1.84 | 1.79-2.24 | 2.06-2.85 | 2.33-3.66 | 2.59-4.63 | 2.69-5.08 | 2.91-6.31 | 1.69 to 2.74 |
| fuzz | whole pass | 1.32-1.41 | 1.61-1.96 | 1.81-2.43 | 2.07-3.19 | 2.33-4.25 | 2.57-5.68 | 2.66-6.39 | 2.87-8.53 | 1.54 to 2.69 |
| fuzz | None | 1.34-1.42 | 1.64-1.98 | 1.85-2.46 | 2.12-3.25 | 2.40-4.36 | 2.67-5.88 | 2.77-6.65 | 3.00-9.01 | 1.52 to 2.49 |
| fuzz | definite | 1.27-1.36 | 1.50-1.86 | 1.65-2.26 | 1.83-2.90 | 2.01-3.75 | 2.16-4.79 | 2.22-5.28 | 2.35-6.65 | 1.67 to 4.91 |

**Integer ids for hash and equality**

| | class | k_r=1 | k_r=1.5 | k_r=2 | k_r=3 | k_r=5 | k_r=10 | k_r=15 | k_r=inf | k_r for 2x |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | whole pass | 1.44-1.51 | 1.94-1.95 | 2.27-2.37 | 2.72-3.01 | 3.24-3.85 | 3.78-4.87 | 4.00-5.34 | 4.53-6.62 | 1.56 to 1.58 |
| dev | None | 1.49-1.51 | 1.95-2.01 | 2.28-2.43 | 2.75-3.08 | 3.30-3.93 | 3.87-4.94 | 4.11-5.41 | 4.69-6.67 | 1.49 to 1.57 |
| dev | definite | 1.38-1.52 | 1.87-1.94 | 2.25-2.28 | 2.68-2.92 | 3.17-3.76 | 3.67-4.81 | 3.87-5.29 | 4.35-6.65 | 1.59 to 1.65 |
| fuzz | whole pass | 1.45-1.64 | 2.02-2.11 | 2.47-2.52 | 2.96-3.36 | 3.53-4.56 | 4.12-6.25 | 4.37-7.12 | 4.95-9.89 | 1.36 to 1.48 |
| fuzz | None | 1.46-1.65 | 2.04-2.13 | 2.50-2.56 | 3.03-3.42 | 3.64-4.69 | 4.28-6.48 | 4.55-7.43 | 5.21-10.51 | 1.35 to 1.46 |
| fuzz | definite | 1.40-1.63 | 1.92-2.03 | 2.31-2.35 | 2.68-3.05 | 3.08-4.00 | 3.47-5.21 | 3.62-5.80 | 3.96-7.48 | 1.46 to 1.59 |

## What k doesn't cover

k was measured on the SAT solver core with the theories on tape. A live pass, sampled in this batch by the innermost `satassume`
frame:

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

Medians don't sum exactly to 100%. The sampler is the same kind the ceiling report calls biased towards thin callees; it gives
the solver 37.0%, against the replay's 33% and the live timers' 31% to 46%, and its r of 45% and 47% falls inside the 41% to 59%
that subtraction gives. So treat these as proportions.

- **Theories.** LRA is the largest part of r: 13.4% of dev, 18.4% of fuzz. Relations is 5.7% and 10.4%, EUF 1.7% and 4.1%, transfer
  0.4% and 1.6%. None of them ran in the replay; only their hooks' answers did.
- **Session and Engine.** Session is 9.0% and 7.9%, the rest of `engine.py` 4.5% and 2.0%. On dev, the knowledge layer is another
  8.5%, against 1.3% on fuzz.
- **Memos.** They aren't a separate line; they sit inside Session, Relations and the adapters. They show up as hash asks instead:
  `Session.ensure` 6.3% and `Session.node` 5.1% of fuzz's hash asks, `lra_adapter._memoized` 3.4%, `EUFAdapter.interned` 2.2%. The
  estimate assumes they hit as often in Rust and that their keys are SymPy objects (as it stands) or ids. The answer and conversion
  memos stay in Python and are already in S.
- **Named parts inside r.** `Fraction` and its ABC checks are 5.8% of dev and 9.4% of fuzz, under LRA. Generated dataclass methods
  are 1.9% and 2.6%, and import machinery called during queries is 0.7% on both. No single function exceeds 1.6%.
- **SymPy-reading code.** Part of r reads SymPy objects step by step (`relation_read`, `euf_read`, `lra_read`, templates, struct; 26
  thousand calls on dev and 469 thousand on fuzz). Its Rust version would be mostly crossings, so k_r there may be low. The S4 row
  below keeps it in Python.

**What the estimate assumes:** one k_r on all of r, and additive shares, with no gain or loss from running beside each other. Since
r divides by a harmonic mean, the slowest large piece sets k_r. These are arithmetic examples on fuzz's composition, not predictions:

| assumed | k_r | as the code stands, low end | ids, low end |
|---|---:|---:|---:|
| Everything in r at 2x | 2.0 | 1.81x | 2.47x |
| LRA at 1.5x, the rest at 15x | 3.3 | about 2.1x | about 3.1x |
| Relations, Session and EUF at 1.5x, the rest at 15x | 2.85 | about 2.0x | about 2.9x |
| Everything in r at the solver's 15x | 15 | 2.66x | 4.37x |

The solver is integer arrays, the kind of code Rust gains most on. r is dicts, tuples and rationals, so 15x should not be read
across. Some parts could go the other way, since `Fraction` is slow; no measurement here decides that.

## Sensitivity

On the low end. Whole pass, and the hardest class; all classes are in `rust-spike/results/tables-cross.md`.

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
| fuzz | definite | as it stands, the low end itself | 1.27 | 1.83 | 2.01 | 2.16 | 4.91 |
| fuzz | definite | ids, the low end itself | 1.63 | 2.68 | 3.08 | 3.47 | 1.46 |
| fuzz | definite | as it stands, solver k halved in live use | 1.24 | 1.76 | 1.92 | 2.07 | 6.85 |
| fuzz | definite | as it stands, per ask 200 ns | 1.12 | 1.54 | 1.66 | 1.77 | inf |
| fuzz | definite | as it stands, per ask 500 ns | 0.87 | 1.11 | 1.17 | 1.22 | inf |
| fuzz | definite | ids, only P.__hash__ goes | 1.37 | 2.05 | 2.27 | 2.48 | 2.74 |
| fuzz | definite | ids, per other ask 500 ns | 1.56 | 2.51 | 2.86 | 3.19 | 1.62 |
| fuzz | definite | SymPy-reading functions stay in Python (S4), each call at the high charge | 1.38 | 2.04 | 2.25 | 2.45 | 2.79 |
| fuzz | definite | solver only in Rust, rest Python (no assumed factor) | 1.37 | 1.37 | 1.37 | 1.37 | inf |

**Below 2x:**

- Solver only in Rust: always, at 1.37x to 1.48x. Its limit is 1 / (1 - s), about 1.5x.
- k_r = 1: always, in both cases (1.27x to 1.65x).
- As the code stands, at the low end: k_r under 2.43 (dev), 2.69 (fuzz) and 4.91 (definite fuzz).
- As the code stands, at 200 ns per ask live: k_r under 3.75 (dev) and 6.43 (fuzz). Definite fuzz never reaches 2x.
- As the code stands, at 500 ns per ask: never, on the low end.
- SymPy-reading functions left in Python: k_r under 3.90 (dev), 2.04 (fuzz), 2.79 (definite fuzz).
- Ids: k_r under 1.35 to 1.65. If only `P.__hash__` goes, k_r under about 2.0 (definite fuzz 2.74).

A solver k halved in live use moves the requirement by about 0.4 to 2 (2.43 to 2.80, 2.69 to 3.13, and 4.91 to 6.85). Taking the live
timers' larger solver share instead lowers it, to 1.83 and 1.92.

## Method

- **Machine.** Pinned on pareto1 (i5-13600T), `machine run --quiet`, `bench-container`, `BENCH_CPU=2`, image `sa-eval-bench:1`,
  Python 3.12. Modules built once in `sa-cy-build:1` with rustc 1.98.1, `--release`, no LTO.
- **Runs.** A cold process per run, `PYTHONHASHSEED=0`, seven rounds with round 0 a warmup, medians over rounds 1 to 6. Runs rotate
  one place each round: `micro`, `base`, `real`, `samp`, `microabi3`, `realabi3`, on dev and fuzz where they use a workload. Inside
  a process, every test runs once per repeat, in turn, for eight repeats with the first dropped. `gc.collect(); gc.freeze()` runs
  before the timed part.
- **Answers.** All 56 runs with a pass, warmup included, gave the known digests, dev `31cd0945c07f02a6` and fuzz `173502b6ef285ad6`.
- **Timing.** Rust loops time themselves with their arguments already held in Rust. Python rows are net of an empty loop. In (a),
  bytes come in by reference with no copy, and the function reads every byte.
- **Sizes.** The 132, 267 and 538 bytes are the ceiling report's encoded query (dev, fuzz) and fuzz's `cl` encoding.
- **Rebuild.** `python3 rust-spike/cross/combine.py` rebuilds `rust-spike/results/tables-cross.md`. Module hashes: full API
  `d263bfddab0c8db7`, `abi3` `3636398edb012490`.

Tilo's constraint: nothing measured here changes SymPy or needs anything from it beyond `hash`, `==` and attribute reads. An id table
built this way is a Python dict over the existing `__hash__` and `__eq__`.

## Limits

**This estimate**

- Nothing combined was run. Additivity is assumed: no cache effects from switching between Rust and Python, and no change in
  collector work when moved code stops allocating Python objects.
- Crossing costs are tight loops on warm objects. In a live pass, the Rust and Python sides would run on colder caches, and that is
  why 200 ns and 500 ns are shown.
- Ids are assumed equal to `==` wherever the code compares. Interning through a dict gives the partition dicts already use, but
  direct `==` calls, `==` between types and object lifetime in the table weren't tested. Answers were not checked under ids.
- Not charged: Rust decoding a query; exceptions crossing the boundary; keeping Rust-held handles out of Python's collector, which
  can't see cycles through them; memory.
- These workloads barely use custom predicates: 24 and 0 calls into registered user code on dev, 0 and 0 on fuzz. Each would be a
  callback with a body of unknown cost.
- CPython 3.12 on one x86-64 machine, two workloads. Free-threaded Python wasn't measured.

**Carried over from `RESULT-k.md`** (they apply to the k used here)

- **Query answers were not recomputed.** The engine above the solver doesn't run in the replay. What matches is every solver result
  those answers were built from.
- **The theories did not run.** The tapes prove each would see the same `assert_lit`, `propagate`, `check` and `decide` calls in the
  same order. `push_level` and `pop_level` are only compared as counts per query, so their position is unchecked, which matters for
  LRA's step budget if the theories are ported.
- **Untested paths.** The traces have 0 restarts and 0 DB reductions. `_reduce_db` and the restart path are ported but not exercised.
- **5 of 10 port mutations weren't caught by the traces:** `_mention` pending blocks in reverse order, ring counting None as false in
  a clause, `_fill` with no growth past the model's end, `_learn` bumping a clause after it joins `_learnts`, and a theory unit reason
  marked learnt. The port follows the Python on these by reading, not by test.
- **Model sets.** They are `u128`, and the port panics past 128 models. The engine's block has 44; Python's limit is 65,536. A real
  backend needs a wider set.
- **Small search.** Fuzz averages about 2.6 conflicts per query. A workload with more search could give a different k.

## Files

| what | where |
|---|---|
| Crate and harness | `rust-spike/cross/` (`src/lib.rs`, `crossing.py`, `run-cross.sh`, `build.sh`) |
| Combining script | `rust-spike/cross/combine.py` |
| Raw batch | `rust-spike/results/pinned-cross.raw` |
| All tables, all classes | `rust-spike/results/tables-cross.md` |
