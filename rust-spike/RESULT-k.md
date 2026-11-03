# Rust spike: k for the SAT solver core (issue 323)

**A first honest port is 12.9x faster on dev and 15.2x faster on fuzz 424242, with the same search order on every call.**
That is the low end of the issue's 10x-50x, and well above the roughly 3x break-even for its 2x line. Tuning adds little:
the most I tried reaches 14.1x and 16.0x. The solver's share of a pass is about a third.

This covers the solver alone, replayed. It includes no crossing cost and no theory work, so **it is not an overall
speedup**. Both are for the next step.

| | dev | fuzz 424242 |
|---|---:|---:|
| Python replay, net of dispatch and tape | 0.1771 s | 2.6475 s |
| Rust replay, same | 0.0137 s | 0.1741 s |
| **k, first port** | **12.9** (12.8 to 13.2) | **15.2** (14.9 to 15.3) |
| k, first port, raw (nothing subtracted) | 13.3 (13.2 to 13.6) | 15.6 (15.3 to 15.7) |
| Solver's share of the live pass, from the replay | 33.2% | 32.6% |
| Search order | identical | identical |

The k values are medians of per-round ratios over six rounds, with the range in brackets. An earlier full batch gave net k
12.9 and 15.0, so the result repeats.

## Method

- **Machine.** Pinned on pareto1 (i5-13600T), under `machine run --quiet`, `bench-container`, `BENCH_CPU=2`, image
  `sa-eval-bench:1`, Python 3.12. The solver is the one at 9bafaa5.
- **Runs.** A cold process per run, one pass per process, `PYTHONHASHSEED=0`. Seven rounds, round 0 a warmup, medians over
  rounds 1 to 6. Modes rotate one place each round. `base` (`tools-rust/rc.py base`) runs in the same rotation. All its
  runs gave the known digests, dev `31cd0945c07f02a6` and fuzz `173502b6ef285ad6`.
- **Replay.** Both replays read `{dev,fuzz}.trace` and decode everything before the clock starts. Python uses the real
  `Solver` with `gc.collect(); gc.freeze()` before the pass and the collector on, as in `base`. Theories are tapes of the
  recorded answers, and a hook call that doesn't match the tape stops the replay.
- **Port.** `replay/src/solver.rs` and `block.rs`, written once from `solver.py`. It uses safe Rust with bounds checks on,
  no crates, and `cargo build --release` on rustc 1.98.1. Binaries are built in `sa-cy-build:1`, which has the same glibc as
  the bench image.
- **What "net" subtracts.** The dispatch loop (`pyempty`, `rsempty`), and what a tape body costs beyond a plain method call.
  So Python's plain call to a theory stays in the solver's time, and the call that enters each solver method is subtracted.

Rebuild the tables with `analyze_k.py results/pinned-k.raw` and `analyze_byop.py results/pinned-byop.raw`. The traces stay
on pareto1 (`~/sa-rust-spike/traces`, 32 MB). Two recordings are byte-identical.

## Timings

| run, median of rounds 1 to 6 | dev s | fuzz s |
|---|---:|---:|
| `base`, the live pass | 0.5328 | 8.0939 |
| Python replay | 0.1832 | 2.7527 |
| Python replay, collector off | 0.1836 | 2.7192 |
| Python empty dispatch | 0.0056 | 0.0837 |
| Python tape hooks / the same calls to a no-op | 0.0013 / 0.0008 | 0.0452 / 0.0237 |
| Rust replay, first port | 0.01375 | 0.1763 |
| Rust empty dispatch | 0.00001 | 0.00015 |
| Rust tape walk | 0.00006 | 0.00206 |

**k by kind of query**, raw:

| | dev | fuzz |
|---|---:|---:|
| None answers | 13.0 | 15.7 |
| Definite answers | 13.9 | 14.9 |

**Tuning**, each row net and against the same Python time:

| build | dev k | fuzz k |
|---|---:|---:|
| First port: release profile, SipHash memos | 12.9 | 15.2 |
| Memos on a multiplicative hash | 13.2 | 15.5 |
| That, plus fat LTO, one codegen unit, `panic=abort` | 14.1 | 16.0 |

## Share of a pass

The replay gives 33.2% on dev and 32.6% on fuzz. `record.py --timers` is a second estimate from the live pass, and it
brackets that figure, because its wrappers inflate it by an amount I can only bound:

| solver minus theories, live | dev | fuzz |
|---|---:|---:|
| As timed | 0.2312 s, 43.4% | 3.6996 s, 45.8% |
| Minus all the time the timers added to the run | 0.174 s, 32.6% | 2.50 s, 30.9% |

The replay cannot show cache effects from running beside SymPy, or collector passes over solver objects in the live heap.
Either would make the live share higher than the replay's. The collector costs at most about 1% in the replay, which is
near the noise.

## Search order

**No difference, on either workload.** Every public call returned the same result, and the counters match after every
query. The same holds on x86-64 with Python 3.12 and on orion's aarch64 port build. The final binaries were rechecked
(`results/check-final.txt`).

| checked | dev | fuzz 424242 |
|---|---:|---:|
| Public calls, result CRC identical | 46,214 | 687,993 |
| Queries, all counters identical (Python, Rust, recording) | 1,985 | 3,000 |
| Decisions | 7,738 | 105,266 |
| Conflicts | 257 | 7,797 |
| Propagations | 53,418 | 800,527 |
| Ring hits | 135 | 26 |
| Theory hooks on tape, in order, with arguments | 16,088 | 584,495 |

`implied` returns the whole trail, so trail order is compared too, at each of its 2,524 and 11,681 calls.

**Matching costs no measured speed, but what it forbids can't be measured here.** The port has no code that exists only to
match. The obvious speedup it rules out is blocker literals, which change watch order. A replay that diverges stops at once,
because the tapes are only valid on the recorded path, so that variant can't run. Instead, this bounds it: the Rust run spends
17% (dev) and 21% (fuzz) of its time inside `prop()`. Even if all of that vanished, k would reach about 15.6 and 19.3.

### What this does not establish

- **Query answers were not recomputed.** The engine above the solver doesn't run in the replay. What matches is every solver
  result those answers were built from.
- **The theories did not run.** The tapes prove each theory would see the same `assert_lit`, `propagate`, `check` and `decide`
  calls in the same order. `push_level` and `pop_level` are only compared as counts per query, so their position among the
  other hooks is unchecked. That matters for LRA's step budget if the theories are ever ported.
- **Paths the traces never reach.** There are 0 restarts and 0 DB reductions. `_reduce_db` and the restart path are ported
  but untested here.
- **Small search.** Fuzz averages about 2.6 conflicts per query. A workload with more search could give a different k.

### How sensitive the check is

I broke the port in ten ways on purpose (`mutate.py`). Five were caught:

| mutation | dev | fuzz |
|---|---|---|
| Level sort ties flipped (ascending, then reversed) | caught | caught |
| No `var_inc` decay | caught | caught |
| `_n_decisions` not counted when the pick returns -1 | caught | caught |
| `explain`: last best wins instead of first | no | caught |
| A watch moved early to a true third literal | no | caught |
| `_mention`: pending blocks in reverse order | no | no |
| Ring: None counted as false in a clause | no | no |
| `_fill`: no growth past the model's end | no | no |
| `_learn`: clause bumped after joining `_learnts` | no | no |
| Theory unit reason marked learnt | no | no |

**So these traces do not test those last five behaviours.** Either the path isn't reached or the difference changes nothing
here; I didn't separate the two. The port follows the Python on all five by reading, not by test, and a real backend would
need targeted tests for them.

The check did find one real port bug: my first `_fill` truncated the model at the end of the block, which showed up as a
missed ring hit at dev query 188. It was fixed before any timing.

## Where the time goes

Per public method on fuzz, from a separate pinned batch. It adds a clock pair per call, so it is rough: 2.85 s against
2.75 s for Python and 0.214 s against 0.176 s for Rust. Dev is in `results/tables-byop.md`.

| method | calls | Python s | Rust s | k |
|---|---:|---:|---:|---:|
| `entails` | 2,271 | 0.781 | 0.042 | 18.6 |
| `add_clause` | 316,135 | 0.656 | 0.046 | 14.3 |
| `add_internal` | 33,176 | 0.286 | 0.031 | 9.3 |
| `solve` | 2,859 | 0.251 | 0.014 | 18.4 |
| `ensure_vars` | 128,990 | 0.183 | 0.014 | 13.5 |
| `implied` | 11,681 | 0.158 | 0.010 | 15.3 |
| `register_atom` | 94,780 | 0.130 | 0.006 | 23.9 |
| `register_block` | 16,493 | 0.108 | 0.013 | 8.2 |
| new + drop | 3,133 | 0.066 | 0.017 | 3.9 |

No single loop sets k. Much of the time is bookkeeping and small allocations, which is why k sits near 15 rather than
higher. The lowest row is building and freeing solvers, because the port frees one small `Vec` per clause and per watch list.
A flat clause arena is the obvious next tuning. It wouldn't change search order, and I didn't try it.

## Differences from the Python

None of these changes behaviour, as far as the check can show:

- Clauses live in one `Vec`, with `u32` handles.
- `_mvals`, `_mdict` and `_tmodels` are gone, because nothing in the trace reads them. There is no provenance.
- `_tmap` is per variable rather than a dict.
- Duplicate-literal merging is a linear scan. `_mention`'s `pend` is a list, which keeps insertion order.
- Memos are unbounded. `flags`, `lits_of` and `values_of` are computed directly.
- Model sets are `u128`, and the port panics past 128 models. The engine's block has 44; Python's limit is 65,536. A real
  backend needs a wider set.

## Counts for the crossing step

Not measured here. These calls would cross a boundary if the theories stayed in Python and the caller did too:

| | dev | fuzz |
|---|---:|---:|
| Public solver calls | 46,214 | 687,993 |
| Theory hooks on tape | 16,088 | 584,495 |
| `push_level` + `pop_level` | 14,157 | 542,373 |
| `register_atom` (one theory call each) | 3,285 | 94,780 |

## Files

| what | where |
|---|---|
| Port and replay | `replay/` |
| Python replay | `replay_py.py` |
| Batch, build and check scripts | `run-k.sh`, `build-pareto.sh`, `check-pareto.sh` |
| Mutation check | `mutate.py` |
| Reported batch | `results/pinned-k.raw`, `results/tables-k.md` |
| Earlier full batch, for repeatability | `results/pinned-k-batch1.raw`, `results/tables-k-batch1.md` |
| Per-method batch | `results/pinned-byop.raw`, `results/tables-byop.md` |

The earlier batch used binaries from before the `prof` feature was added, which changed line numbers in panic locations. The
reported batch uses the committed source; its hashes are in `results/check-final.txt`.
