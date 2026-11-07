# Component 3, transfer core: landing report (issue 323)

`theories/transfer.py`, `EqualitySharing` and `P` run in Rust in the real engine. **This adds 1 of the 32 runtime modules: `transfer.py`.** `EqualitySharing` and `P` run on Rust, but their modules aren't counted: `sat/formula.py` still holds `Formula` and its subclasses on Python, and `sat/theory.py` is mostly protocols. Python stays the default and the reference; the backend stays optional. No heuristics added.

**`rust` mode now means Rust EUF, Rust LRA and Rust transfer together.** The rebases onto component 2 (e5dd23f) and 1a (69639da) both conflicted and both changed what runs. Results from earlier source don't count here. Every run below is on f9eb6de.

**Lazy reads (6827bf7): the rebase had no conflict.** Both sides touch only `quiet_fire.py`, the same file on both, and the inventory. This crate uses `term::TermId` and `term::offline`, not the `term/table.rs` and `term/algebra.rs` code lazy reads changed, and by that report nothing consumes conversion yet. That's by reading; the runs below are on the combined source. `SLICE_EUF=py` wasn't needed to separate the components, because nothing differed.

**Atoms (dc3f15d): the crate did change, 415 lines in `term/knowledge.rs`, `mod.rs`, `py.rs` and `table.rs`, and the runs below include them.** One tool conflicted: both sides added `suite_split.py`. `rust-slice`'s stays unchanged, and this branch's is `suite_split_named.py`.

**Tested source: `port/3-landing-5` at f9eb6de, on `rust-slice` dc3f15d. Landed on dfa7b45 (atoms whole, `port-6b.md`) without a full rerun, under the planner's rule:** a rebase needs one only if the incoming diff changes code the run executes.

- **Incoming diff, f9eb6de's tree to dfa7b45's:** 7 files, `HANDOFF-sa-port-45.md`, `knowledge_fresh.py`, `knowledge_live.py`, `knowledge_value_wl.py`, `mutate_knowledge.py`, `results/port-6b.md`, `test_knowledge_value_units.py`. 0 diff lines in `solver_rs`, `convert.py`, `lra`, `satassume` and `tests`.
- **What `rust` mode reaches:** after `backend.install()`, `convert`, `knowledge_live`, `term_shadow` and `lazy_reads` aren't loaded. **The crate's `term/` is reached:** `lib.rs` calls `term::py::register` at import, and `TermId` and `term::offline` come from `term/`. So rust mode does run some of `term/`, including `py.rs`, which changed from 6827bf7 to dc3f15d. Those changes are in f9eb6de, so the runs below include them, and none comes after it.
- **Short check on the landing tree, orion, seed 0:** build; `transfer:1:300` byte-identical for py, rust and shadow; fresh dev byte-identical for py and rust, 1,985 queries, 3,332 sessions, 0 quiet catches.

Build on pareto1 (x86_64), sha256 starts bf4cf6d6ce78, the same file on both hosts. Fresh and suite ran on pareto0, controls and history on pareto1. Output: `~/sp19/out38/` on each host; suite rows and `split.jsonl` in `~/sa-rust-ids-work/sa-port-38/s1/` on orion.

## The bar

| # | Item | Result |
|---|---|---|
| 1 | Suite by id, Rust solver, EUF, LRA and transfer, shuffled, `-n 6` | **5,961 / 77 / 46** (123 failed), base 5,961 / 77 / 46. 6,125 ids, none added or gone, **0 outcomes changed** against `port-census/pr328-check/suite-rust`. 23 skipped, 18 xfailed. The base rows are from orion |
| 2 | Fresh engine, memos cleared, dev 1,985 and fuzz 3,000 | Answers and state **byte-identical**, py against rust and py against shadow, seeds 0 and 1. Also on `transfer:1:300`, `transfer2:7:1500` and `corpus`: 10 of 10 pairs, all exits 0. Rust is identical across the two seeds on all five |
| 3 | Planted bugs through that comparison | **6 of 8 caught, including 4 ordinary bugs**, table below. The unmutated rebuild reads clean on every column |
| 4 | Quiet firings on Rust, that suite run | **39 rows, 2 tests**, both already named. **0 findings** |
| 5 | Known differences | Below, each with its cause |
| + | History and seeds, because the rebase brought other components into the crate | Rust against Python: **0 answers, 0 messages, 0 end states, 0 streams, 0 session counts differ** in all 14 runs. Below |

**The 5,961 by firing, on Rust:** 5,960 with no Rust-only firing, 1 with one (`test_ci_stream_reports_only_what_replays`). 0 fire the same on Python, and 0 fire only on Python.

S's standing: S's gate is met except for the 46 named stub failures, one cause. They stay listed in number 3, and the crate is unchanged for them. The `_n_conflicts` view in `rust_plugin.py` isn't a port: it's a test-plugin shim, and moved 64 tests.

### Changed outcomes and open items

- **`tests/test_constfield.py::test_powers_are_refused_quickly`** passed on this run, and on 3173eca's and 8313292's. It failed on 1e36724's run, at 0.641 s against a 0.5 s limit. Alone on orion at load 11 it passed 3 of 3 on each backend, on e7207af: the call took about 0.06 s on Rust and 0.33 s on Python. That doesn't show what caused the old failure; load stays a candidate. It isn't a changed outcome on this source.
- **`tests/test_solver.py::test_performance_smoke_300_vars`** on Python: failed in the base's rows, passed here. It asserts wall clock, and the base's rows are from orion, this run from pareto0. On Rust it's unchanged.
- **Python's suite:** 6,084 passed, 0 failed, 23 skipped, 18 xfailed. Only that one id moved.
- **Failure text of the 123:** 59 kinds here and in the base, normalised for numbers. One id's text moved, in the first 150 characters: `test_fuzz_entails_and_implied`. That compares the failures' start, not their full text.
- **LRA sessions against 1a's run:** 46,636 sessions and 2,705 moved here, 45,358 and 2,697 there, in 239 tests on both. 15 ids differ: fuzz tests, plus `test_random_ask_matches_oracle`, `test_non_real_and_infinite_arguments` and `test_inconsistent_set_raises[p2-a2]`. Hypothesis's draws and shuffled order are candidates, not shown causes. These are session counts, not answers; no outcome moved.

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
- **Workaround, tool not fixed:** `mutate_transfer.py`'s copied crate can't find `lra.rs` through `lib.rs`'s relative `#[path]`. `mut38.sh` copies `lra/port/src` beside the work directory. One run on 69639da stopped at build with no rows because of this. `mutate_slice` has the same gap, reported by sa-port-39; neither it nor `mutate_live.py` was used here.

### History and seeds

`run_history.sh` and `historycmp.py`, `~/sp19/out38/hist/cmp.txt`, dev and fuzz, both backends: recorded, shuffle twice, fork, twice in a row, seeds 1 and 2.

- Answer digests across all 12 runs that keep the recorded query list: dev `31cd0945c07f02a6`, fuzz `173502b6ef285ad6`, the same as in `port-1a.md`. Runs that differ or didn't finish: 0.
- Rust totals: 0 re-entry, 0 entry raises, 0 Python solvers made.
- Answers move in no run. State against recorded moves the same on both backends: under shuffle 335 and 358 on dev, 86 and 91 on fuzz; under fork 1,549 and 2,981.
- `done.txt`: 28 rows, all rc=0.

### Counters, shown firing

- **Fresh's quiet counter** reads empty on every `.tot` on all 10 pairs (0 catches). It fires on a planted raise on this source: p06, q=50 on dev and q=239 on `transfer:1:300`; p07, q=264.
- **The suite's `handler_count`** fired at both sites on both backends on this source, one planted raise each (`suite_plant_handlers.py`).
- **Rust really ran:** 217,640 Rust terms made and 0 Python ones in the suite's rows. `transfer_fresh.py` exits if `P` wasn't swapped.

### Quiet firings on Rust

| Test | Outcome | Rows | Site, type, text | Reading |
|---|---|---:|---|---|
| `tests/test_invariants.py::test_ci_stream_reports_only_what_replays` | passed | 34, 4 | `_consistent`, AttributeError, `'Solver' object has no attribute '_ok'`, `'_rb_clauses'` | The named needs-internals case |
| `tests/test_transfer.py::test_protocol_on_fuzz` | failed, as on the base's Rust run | 1 | `Engine._build_context`, RuntimeError, `Already mutably borrowed` | The named 46-stub cause, `tests/theory_harness.py:242` |

### Known differences

**`P`'s 9 differences, causes shown by running them** (`sa-port-28/smoke/p_cause.py`, rerun on the landing tree's build, same results):
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

**Before any backend PR, not run on this source:** the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the boundary rescore and suite column (10 of the 25 boundary mutants have no real-engine catch as last stated); the final drop score and its lost rows; `order:_rows`' evidence (not caught meanwhile); the `_forms` guard test; forced moves; the native path; timing.

**Also not run:** `run_live.sh` on this source; the mutants beyond the 8 controls; counts with `--sympy`; speed; a public-API version of `test_incremental_matches_fresh`, which the rulings place during the engine port at the latest. The `shadow` column ran only in fresh and the controls, not the suite.

The suite split used a Python run from the same source, though the bar no longer requires it.

**Backend PR list:** a hook re-entering the solver is allowed on Python and raises on Rust. Through `_build_context` it would become a quiet unknown, not an error. Name it in the Rust backend's contract. PR 328, or its order, must be on main first.
