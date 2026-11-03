# Rust spike: k_lra for the LRA core (issue 323)

**A first honest port of the LRA core is 16.6x faster on dev and 22.1x faster on fuzz 424242, with identical results and state
on every call.** But the rational sessions it covers are only 4.3% of a dev pass and 13.4% of a fuzz pass, so most of what's
outside the SAT solver is still unmeasured. Sessions with constants take more of a dev pass (7.2%) than the rational ones do.

| | dev | fuzz 424242 |
|---|---:|---:|
| **k_lra, first port, net of dispatch** | **16.6** (16.4 to 16.8) | **22.1** (22.0 to 22.5) |
| k_lra, first port, raw | 17.2 (16.9 to 17.4) | 22.7 (22.6 to 23.1) |
| k_lra, tuning: Fx hash | 18.7 (18.4 to 19.1) | 27.0 (26.3 to 27.4) |
| k_lra, tuning: Fx hash, fat LTO, one codegen unit, panic=abort | 38.5 (36.8 to 40.6), see Limits | 28.7 (28.6 to 29.3) |
| Results and state, 6,680 / 441,346 calls | identical | identical |

Values are medians of per-round ratios over six rounds, with the range in brackets. This is a replay of `LRATheory` calls alone
and **not an overall speedup**. The whole-pass figures below add shares measured separately; nothing timed the combined system.

## The three things asked for

### 1. Sessions with constants

They are outside the measured boundary. **I did not measure them in Rust and did not apply k_lra to them: they are part of
k_rest in the whole-pass tables.** Shares are of the live pass, from `record_lra.py --timers`, and count time inside `LRATheory`
methods only.

| | class | rational sessions (c) | sessions with constants |
|---|---|---:|---:|
| dev | whole pass | 4.3% | 7.2% |
| dev | None | 3.2% | 8.1% |
| dev | definite | 6.0% | 5.9% |
| fuzz | whole pass | 13.4% | 4.0% |
| fuzz | None | 14.0% | 4.1% |
| fuzz | definite | 10.5% | 3.7% |

### 2. The factor the remaining moved code must reach for 2x (k_rest)

**The denominator is positive in every cell below, so 2x is arithmetically reachable everywhere in this model.** That only says
the model has room; it doesn't say the remaining code can reach these factors. Each cell runs from the low end of the speedup to
its high end. k_lra is the first port's, by class. "Definite" means not None, as in `combine.py`, so fuzz's includes the 207
other answers.

| | class | as it stands | as it stands, constants stay in Python | integer ids | integer ids, constants stay in Python |
|---|---|---:|---:|---:|---:|
| dev | whole pass | 2.23 to 1.48 | 3.05 to 1.61 | 1.44 to 1.44 | 1.59 to 1.56 |
| dev | None | 2.13 to 1.44 | 2.91 to 1.58 | 1.47 to 1.41 | 1.65 to 1.53 |
| dev | definite | 2.42 to 1.53 | 3.32 to 1.64 | 1.39 to 1.49 | 1.50 to 1.59 |
| fuzz | whole pass | 1.87 to 1.21 | 2.21 to 1.23 | 0.93 to 1.16 | 0.92 to 1.18 |
| fuzz | None | 1.71 to 1.18 | 1.96 to 1.20 | 0.91 to 1.13 | 0.90 to 1.15 |
| fuzz | definite | 3.74 to 1.39 | 6.91 to 1.43 | 1.06 to 1.32 | 1.07 to 1.36 |

The "stay in Python" columns put the constants share at factor 1 and apply k_rest to what's left. They aren't a measurement of
what constants sessions would do. A factor below 1 means that code could run slower than it does in Python and the model would
still reach 2x.

The asked-for figure is the "as it stands" and "integer ids" columns. The worst cell is fuzz definite as the code stands: 3.74,
or 6.91 if constants stay in Python.

### 3. Where identical search order depends on Python implementation details

- **`_dirty`, a real dependency.** `propagate` iterates a `set[int]`, and the order of its results follows from that. Python
  doesn't define that order; it comes from CPython's table, its probing and its resizing. The port copies CPython 3.12's
  algorithm (`PySet`). Mutant 7, which uses first-added order instead, changes results on 1 dev call and 8 fuzz calls.
- **Sorted order wasn't told apart from the table on these traces.** Mutant 6 (ascending variable) is not caught. A variable id
  at or above the table size wraps around and breaks that match, and on these small tableaus that never showed in a result. So
  the traces don't show that `PySet` is needed beyond small ids, and they barely test its collision and resize paths; I didn't
  count how often those ran.
- **What it means for two engines.** For the same search order, one of two things has to hold. Either Rust carries a copy of a
  CPython internal, which is only correct for the CPython versions whose set behaviour matches and which a CPython change could
  silently break, since the Python engine's order would move with no change in satassume. Or Python's `_dirty` gets an order the
  language defines, which changes Python's own search order wherever that order differs from today's: on these traces, not at
  all if sorted, and on 9 calls if first-added. I measured results only on the recorded calls, not the effect of a changed order
  on the search that follows. The two engines would then need a check like this one to stay in step.
- **Row dict order: language-defined, not an implementation detail, and not tested here.** Conflict literal order follows row
  insertion order, so the port keeps rows in order. Mutant 4 (new row reversed) is not caught on either workload, so these traces
  don't confirm that the port gets this right in general. The largest row at a pivot had 2 entries, which is likely why.
- **`_cols`, no dependency seen.** It's also a set, but each row's update is independent. Mutant 8 (reversed column in a pivot) is
  not caught, as expected.
- **Outside this boundary.** The order of `terms` in a payload comes from the adapter and SymPy. The recording fixes it, so this
  replay can't test it. Any engine that builds its own payloads would have to reproduce it.

## Method

- **Boundary.** Inside: `LRATheory` public calls on rational sessions (tableau, bounds, branch and bound, models). Outside:
  `lra_adapter`, `lra_bounds`, `constfield`, `lra_cert`, and every session where `_fields` was ever set.
- **Machine.** Pinned on pareto1 under `machine run --quiet`, `bench-container`, `BENCH_CPU=2`, image `sa-eval-bench:1`, Python
  3.12, `PYTHONHASHSEED=0`. Seven rounds, round 0 a warmup, modes rotating, a cold process per run. All `base` and `timers` runs
  gave the known digests (dev `31cd0945c07f02a6`, fuzz `173502b6ef285ad6`).
- **Replay.** Both sides decode the trace before the clock starts. Python uses the real `LRATheory` at 9bafaa5. "Net" subtracts
  the dispatch loop (`pyempty`, `rsempty`). Term keys are ints in both replays.
- **Port.** `lra/port/src/lra.rs` and `rat.rs`, written from `lra.py`, with no `unsafe`, rustc 1.98.1. Crates: num-bigint 0.4.8,
  num-integer 0.1.47, num-traits 0.2.19. Built in `sa-cy-build:1`, as `rs` with `cargo build --release`.
- **Whole-pass arithmetic.** `1 / (S + X + R + c/k_lra + (r - c)/k_rest)` with `combine.py`'s S, X, R and r, so k = 12.9 / 15.2,
  low and high as that report has them. `k_rest = (r - c) / (0.5 - S - X - R - c/k_lra)`.

Rebuild the tables with `lra/analyze_lra.py lra/results/pinned-lra.raw`. Check output is `lra/results/check-lra.txt`. The traces
stay on pareto1 (`~/sa-rust-bench/lra/traces`, 9 MB).

## Tables

Replay seconds, by class, and the full whole-pass model (speedup at k_rest = 1, 3, 5, 10, inf) are in
`lra/results/tables-lra.md`. Whole pass only:

| | k_rest=1 | 3 | 5 | 10 | inf |
|---|---:|---:|---:|---:|---:|
| dev, as it stands | 1.39-1.51 | 2.20-3.05 | 2.49-3.82 | 2.77-4.73 | 3.11-6.19 |
| dev, integer ids | 1.53-1.61 | 2.81-3.12 | 3.30-3.94 | 3.80-4.91 | 4.48-6.51 |
| fuzz, as it stands | 1.60-1.73 | 2.25-3.64 | 2.44-4.66 | 2.62-5.92 | 2.82-8.11 |
| fuzz, integer ids | 1.78-2.08 | 3.35-3.86 | 3.81-5.04 | 4.25-6.55 | 4.81-9.33 |

Python replay net of dispatch, then Rust, whole pass: dev 0.0156 s and 0.00093 s, fuzz 0.756 s and 0.0339 s (differences of
medians, so they differ slightly from the per-round ratios above).

## Comparison

- **With the earlier single factor on all of r.** On fuzz the split lowers the factor needed at the low end from 2.69 to 1.87 as
  the code stands, and from 1.36 to 0.93 with integer ids. On dev it lowers it from 2.43 to 2.23 and from 1.58 to 1.44, less
  because c is small there. Full figures are in `tables-lra.md`.
- **With the solver.** k_lra is above the solver's 12.9 / 15.2. That's a comparison of two separate replays.
- **Replay against live.** Python's replay is 2.9% of a dev pass and 9.4% of a fuzz pass, while the live timers give 4.3% and
  13.4%. The live figure includes hashing SymPy keys and the timers' own cost, and I didn't split those. c uses the live figure and
  assumes all of it shrinks by k_lra. If that gap didn't shrink at all, fuzz whole pass at the low end would go from 1.87 to about
  2.5 (worked by hand).

## Mutants

`LRA_MUT=n` on `rsmut`, a separate binary. Without a mutant, `rsmut` gives no mismatches on either workload.

| mutant | dev | fuzz |
|---|---|---|
| 1 pivot order (largest leaving variable) | not caught | caught, 5,420 calls |
| 2 budget off by one | caught, 369 | caught, 11,766 |
| 3 pivot arithmetic (no inverse) | caught, 1 | no answer in 60 s |
| 4 new row reversed | **not caught** | **not caught** |
| 5 `rat.rs` floor truncates toward zero | not caught | caught, 8,418 |
| 6 `_dirty` in ascending order | **not caught** | **not caught** |
| 7 `_dirty` in first-added order | caught, 1 | caught, 8 |
| 8 column reversed in a pivot (expected to change nothing) | not caught | not caught |
| 9 entering variable largest | caught, 478 | caught, 48,689 |

Mutants 4 and 6 are real gaps: the order they change is not exercised by these traces.

## Limits

- **Tiny problems, small numbers.** On both workloads every counted arithmetic result fits in i32 and BigInt never ran (6,954 and
  353,167 results). Direct returns such as `mul` by zero, `neg` and `inv` aren't counted. The largest row at a pivot had 2 entries,
  the largest column 6, and the most variables 8; those are sampled at pivots only. So k_lra measures small-int rationals on small
  tableaus and says nothing about large ones.
- **The first port already has an arithmetic fast path.** `Rat` is i64 over i64 with i128 intermediates, falling back to BigInt.
  I count that as the port's design rather than a tuning, but it's probably a large part of the gain and I didn't measure a port
  without it.
- **Dev's Rust pass is under 1 ms, and one lump distorts it.** Between binaries and rounds, about 0.4 ms moves between dev's
  classes: `rs` None ranges from 10.2x to 26.0x while the whole pass stays at 16.4x to 16.8x. I didn't find the cause. Use dev's
  whole-pass figure rather than its by-class k_lra. **Don't read dev's 38.5x as what tuning buys**: it may only be the absence of
  that lump in the LTO binary, and fuzz's 28.7x is the better figure. The effect on k_rest is small because c/k_lra is under 0.4% of
  a dev pass.
- **Tuning and SymPy use.** Under Tilo's constraint, the Fx hash and LTO are internal to the build. `panic=abort` isn't separated
  out in the tuned figure, and it would stop a panic in an extension from becoming a Python exception, so that part may not carry
  over.
- **No crossing charged for the theory calls.** `register_atom` and the other calls take ints here. X in the whole-pass model is
  `combine.py`'s; I added no cost for handing payloads across.
- **Where c sits.** I took the `LRATheory` methods to be in r, not S, from `coarse.py`'s lists of adapter and `constfield` readers.
  I didn't check every list.
- **Two workloads.** Coverage is what dev and fuzz 424242 reach: 91 and 2,423 rational sessions. Nothing here tests constants
  sessions, the adapter, or any other workload.
