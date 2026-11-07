# Component 3, transfer core: landing report (issue 323)

`theories/transfer.py`, `EqualitySharing` and `P` run in Rust in the real engine. **This adds 1 of the 32 runtime modules: `transfer.py`.** `EqualitySharing` and `P` run on Rust, but their modules aren't counted: `sat/formula.py` still holds `Formula` and its subclasses on Python, and `sat/theory.py` is mostly protocols. Python stays the default and the reference; the backend stays optional. No heuristics added.

**`rust` mode now means Rust EUF, Rust LRA and Rust transfer together.** The rebases onto component 2 (e5dd23f) and 1a (69639da) both conflicted and both changed what runs. Results from earlier source don't count here. `SLICE_EUF=py` wasn't needed to separate the components, because nothing differed.

Landing source: `port/3-landing-3` at 3173eca, on `rust-slice` 69639da; only this report and the inventory row come after it. Build on pareto1 (x86_64), sha256 starts d5aeb11c0bd9, the same file on both hosts. Fresh and suite ran on pareto0, controls on pareto1. Output: `~/sp19/out38/` on each host; suite rows and `split.jsonl` in `~/sa-rust-ids-work/sa-port-38/s1/` on orion.

## The bar

| # | Item | Result |
|---|---|---|
| 1 | Suite by id, Rust solver, EUF, LRA and transfer, shuffled, `-n 6` | **5,961 / 77 / 46** (123 failed), base 5,961 / 77 / 46. 6,125 ids, none added or gone, **0 outcomes changed** against `port-census/pr328-check/suite-rust`. 23 skipped, 18 xfailed. The base rows are from orion |
| 2 | Fresh engine, memos cleared, dev 1,985 and fuzz 3,000 | Answers and state **byte-identical**, py against rust and py against shadow, seeds 0 and 1. Also on `transfer:1:300`, `transfer2:7:1500` and `corpus`: 10 of 10 pairs, all exits 0. Rust is identical across seeds on the four workloads compared (dev, fuzz, `transfer2:7:1500`, `corpus`) |
| 3 | Planted bugs through that comparison | **6 of 8 caught, including 4 ordinary bugs**, table below. The unmutated rebuild reads clean on every column |
| 4 | Quiet firings on Rust, that suite run | **39 rows, 2 tests**, both already named. **0 findings** |
| 5 | Known differences | Below, each with its cause |

**The 5,961 by firing, on Rust:** 5,960 with no Rust-only firing, 1 with one (`test_ci_stream_reports_only_what_replays`). 0 fire the same on Python, and 0 fire only on Python.

S's standing: S's gate is met except for the 46 named stub failures, one cause. They stay listed in number 3, and the crate is unchanged for them. The `_n_conflicts` view in `rust_plugin.py` isn't a port: it's a test-plugin shim, and moved 64 tests.

### Changed outcomes and open items

- **`tests/test_constfield.py::test_powers_are_refused_quickly`** passed on this run. It failed on 1e36724's run, at 0.641 s against a 0.5 s limit. Alone on orion at load 11 it passed 3 of 3 on each backend, on e7207af: the call took about 0.06 s on Rust and 0.33 s on Python. That doesn't show what caused the old failure; load stays a candidate. It isn't a changed outcome on this source.
- **`tests/test_solver.py::test_performance_smoke_300_vars`** on Python: failed in the base's rows, passed here. It asserts wall clock, and the base's rows are from orion, this run from pareto0. On Rust it's unchanged.
- **Python's suite:** 6,084 passed, 0 failed, 23 skipped, 18 xfailed. Only that one id moved.
- **Failure text of the 123:** the 59 kinds are the same, normalised for numbers. One id's text moved: a Hypothesis `ExceptionGroup`, in the first 150 characters. That compares the failures' start, not their full text.
- **LRA sessions against 1a's run:** 45,109 sessions and 2,675 moved here, 45,358 and 2,697 there, in 239 tests on both. 14 ids differ, and those listed are fuzz tests, plus `test_inconsistent_set_raises`. Hypothesis's draws between runs are a candidate, not a shown cause. These are session counts, not answers; no outcome moved.

### Planted bugs through fresh

Against Python, on this source. `@` is the first query that differs; `q` is that row's quiet firings.

| Mutant | Bug | rust, dev | rust, `transfer:1:300` |
|---|---|---|---|
| base | unmutated | no | no |
| p03 | `register_atom`: control variables not skipped | answer@1709 state@1709 q=12 | answer@0 state@0 q=12 |
| t05 | `why`: full and polar swapped | state@1710 | answer@76 state@0 q=7 |
| w01 | `transfer_wanted`: an eq atom says False | answer@1721 state@1709 | answer@2 state@1 |
| w02 | `transfer_wanted`: eq atoms ignored | answer@1721 state@1709 | answer@2 state@1 |
| p06 | planted raise: `check` raises ValueError | answer@1709 state@1709 q=50 | answer@0 state@0 q=239 |
| p07 | planted raise: `propagate` raises RuntimeError on any lemma | answer@1710 state@1710 | answer@1 state@0 q=264 |
| t42 | `check`: conflict test inverted | **no** | **no** |
| t43 | `check`: no selector in the conflict | **no** | **no** |

- **t42 and t43 aren't caught through the engine.** The API fuzz catches both. They sit on the conflict path below.
- **The first controls run was void:** it stopped at build because the copied crate couldn't find `lra.rs`, and it has no rows. The rerun has the rows above, with the same module source. `mutate_transfer.py` needs `lra/port/src` beside its work directory until that's fixed; the job script does it.

### Counters, shown firing

- **Fresh's quiet counter** reads empty on every `.tot` on all 10 pairs (0 catches). It fires on a planted raise on this source: p06, q=50 on dev and q=239 on `transfer:1:300`; p07, q=264.
- **The suite's `handler_count`** fired at both sites on both backends on this source, one planted raise each (`suite_plant_handlers.py`).
- **Rust really ran:** 215,721 Rust terms made and 0 Python ones in the suite's rows. `transfer_fresh.py` exits if `P` wasn't swapped.

### Quiet firings on Rust

| Test | Outcome | Rows | Site, type, text | Reading |
|---|---|---:|---|---|
| `tests/test_invariants.py::test_ci_stream_reports_only_what_replays` | passed | 34, 4 | `_consistent`, AttributeError, `'Solver' object has no attribute '_ok'`, `'_rb_clauses'` | The named needs-internals case |
| `tests/test_transfer.py::test_protocol_on_fuzz` | failed, as on the base's Rust run | 1 | `Engine._build_context`, RuntimeError, `Already mutably borrowed` | The named 46-stub cause, `tests/theory_harness.py:242` |

### Known differences

**`P`'s 9 differences, causes shown by running them** on older source (`sa-port-28/smoke/p_cause.py`), not rerun here:
- `is_dataclass` False, `__dict__` AttributeError: fixed slots, no instance dict, no `__dataclass_fields__`.
- 6 pickle rows: Python's bytes rebuild with no arguments and then BUILD a dict. Protocols 0, 1: `object.__new__(P) is not safe`. 2 to 5: `P.__new__() missing 2 required positional arguments`. Rust's bytes load on both classes. Saved streams hold no `P`: the copy of `stream.pkl` matching 94db857d9d5d has 0 occurrences of "satassume" in its bytes, read without loading, and likewise `battery-stream` and `gate2-stream`.
- A subclass with a `pred` property: Python's frozen init writes through the property and raises; Rust's `__new__` writes its slot, so it builds and the property wins on read.

**`transfer_wanted`'s fix stays named.** An earlier build differed from Python on 50 of 60 fixed cases, the smallest `[P("lt","ab"), P("lt","ba")]`, Python False and Rust True. Fixed; `HANDOFF-sa-port-25.md`, Found 1. Python's result on `[P("lt",(1,2)), P("lt",(2,1)), P("lt",(1,2,3))]` depends on hash order.

**`pyset.rs` is tied to CPython 3.12's set order,** which it reproduces for iteration. Another CPython could change it. `transfer_fuzz.py` checks it against real sets.

## Named gaps

- **`check()`'s conflict path isn't reached by the engine.** On this source `transfer.py:463` ran 3,234 times on `transfer2:7:1500`, 2,017 on fuzz, 70 on dev, 40 on `corpus`; `:464` ran 0 times on all four. `_spread`'s `:382` ran 0 times too. Not shown unreachable. By the architect's ruling this doesn't block.
- **Mutants, on older source.** m2's survivors t20 t29 t30 t32 t34 t35 t47 t57 p04 aren't argued equivalent. Their rerun on `transfer2:7:1500` and fuzz, on 1e36724, caught none. m3: **all 12 `P` mutants have no engine catch**; the API catches them.

## Counts and kept on Python

- **Kept on Python with reason:** Sum, Product, Integral, non-default registries and `enclose`, per the rulings. Not exercised separately by this run.
- **Fresh's counters:** "sympy built" reads 0 on dev, fuzz, `transfer2:7:1500` and `corpus`, seed 0. That isn't the `--sympy` count, which wasn't run.
- `P` is GC-tracked and `transfer_wanted` builds a real set. Neither has been timed.

## Not run

**Before any backend PR, not run on this source:** the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the boundary rescore and suite column (10 of the 25 boundary mutants have no real-engine catch as last stated); the final drop score and its lost rows; `order:_rows`' evidence (not caught meanwhile); the `_forms` guard test; history and seed reruns beyond the two fresh seeds; forced moves; the native path; timing.

**Also not run:** `run_live.sh` and `run_history.sh` on this source; the mutants beyond the 8 controls; counts with `--sympy`; speed; a public-API version of `test_incremental_matches_fresh`, which the rulings place during the engine port at the latest. The `shadow` column ran only in fresh, not the suite.

The suite split used a Python run from the same source, though the bar no longer requires it.

**Backend PR list:** a hook re-entering the solver is allowed on Python and raises on Rust. Through `_build_context` it would become a quiet unknown, not an error. Name it in the Rust backend's contract. PR 328, or its order, must be on main first.
