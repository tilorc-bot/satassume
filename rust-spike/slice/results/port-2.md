# Component 2, EUF core: landing report (issue 323)

`theories/euf/euf.py` runs in Rust in the real engine; `euf_adapter.py` stays Python and calls it. **This adds 1 of the 32 runtime modules.** Python stays the default and the reference; the backend stays optional. No heuristics added. Held to the planner's landing bar; what it moved is listed under "Not run".

Landing source: `port/2` rebased on `rust-slice`. Build on pareto1 (x86_64), sha256 starts 67c2ba94894e. Output: `~/sp23/out/` on pareto1, `~/sa-rust-ids-work/sa-port-23/` on orion.

## The bar

| # | Item | Result |
|---|---|---|
| 1 | Suite by id, Rust solver and Rust EUF, shuffled, `-n 8`, pareto1 | **5,961 / 77 / 46**, base 5,961 / 77 / 46. 6,125 ids, none added or gone, **0 outcomes moved** against `port-census/pr328-check/suite-rust`. The base rows are from orion |
| 2 | Fresh engine, memos cleared, dev 1,985 and fuzz 3,000 | Answers and state **byte-identical**, py against rust, at hash seeds 0 and 1. Rust also identical across the two seeds. 0 quiet firings on all |
| 3 | Planted bugs through that comparison | **4 of 4 caught**, table below |
| 4 | Quiet firings on Rust, that suite run | **39 rows, 2 tests**, below. 1 is a finding |
| 5 | Known differences | Below, each with its cause |

**The 5,961 by firing, on Rust:** 5,960 with no firing, 1 with a firing (`test_ci_stream_reports_only_what_replays`). Python's counter wasn't read for this split.

S's standing: S's gate is met except for the 46 named stub failures, one cause. They stay listed in number 3, and the crate is unchanged for them. The `_n_conflicts` view in `rust_plugin.py` isn't a port: it's a test-plugin shim, and moved 64 tests.

### Planted bugs through fresh

Against Python, seed 0. Each run prints the sha it loaded. The unmutated rebuild has the landing build's sha and 0 differences on both workloads.

| Mutant | dev: differ / answers | fuzz: differ / answers | Quiet firings, dev / fuzz |
|---|---:|---:|---:|
| 35 (state only) | 121 / 0 | 1,248 / 0 | 0 / 0 |
| 37 | 30 / 2 | 552 / 3 | 0 / 0 |
| 51 | 2 / 2 | 27 / 27 | 0 / 0 |
| 62, third level lost | 216 / 162 | 2,813 / 2,699 | 110 / 2,086 |

**A void first run, fixed:** the first pass of these showed 0 differences on all four, because `fresh.py --so` let `backend.py`'s path entry load the unmutated build. `fresh.py` now imports the mutant first and exits if it loaded another file. **Any earlier control run with `fresh.py --so` on a tree before this fix should be treated as void.** `live.py` always had this guard; plain fresh runs without `--so` aren't affected.

### Quiet firings

| Test | Outcome | Rows | Site, type, text | Reading |
|---|---|---:|---|---|
| `tests/test_invariants.py::test_ci_stream_reports_only_what_replays` | passed | 34, 4 | `_consistent`, AttributeError, `'Solver' object has no attribute '_ok'`, `'_rb_clauses'` | The named needs-internals case. Its drop patch fails on Rust, and the test still passes |
| `tests/test_transfer.py::test_protocol_on_fuzz` | failed, as on the base's Rust run; passes on Python | 1 | `Engine._build_context`, RuntimeError, `Already mutably borrowed` | **Finding** |

**The finding:** a theory hook that reads the crate's solver during a call into it raises, where Python allows it. Here the test harness calls `s.nvars()` from `check` (`tests/theory_harness.py:242`) while Rust holds the solver's mutable borrow. Smallest case, `borrow_small.py`: Python returns True with 3 reads, the crate raises with 0.
- It didn't hide a wrong answer here: the handler swallowed the first raise, the same read then raised unguarded at `solver.entails`, and the test failed.
- Measured, not proved: 0 firings of this kind on fresh dev and fuzz, and the rest of the suite has none.
- It is the first firing the boundary column shows: 1 row on every build, base included, in `test_protocol_on_fuzz`.

### Known differences

1. **Unbounded re-entry stops at a different depth:** about 213 terms on Python, about 1,011 on the crate, because Python uses about 5 frames a merge and the crate 1. Both raise RecursionError, in different states. Smallest case: seed 1350, 10 ops, `euf_fuzz.py --unbounded --start 1000 --seeds 400`. No listener re-entered on 1,757 merges in earlier measured runs.
2. A literal past i32 raises OverflowError, as the crate's solver does. Left out of the fuzz.
3. `explain` with a negative id: Python walks raw negative ids, the crate normalises. Left out of the fuzz.
4. `members[r]` returns a new list, not an alias. Not tested.
5. Private fields don't exist on the crate's class, except the new read-only `_lims`.
6. `fxhash` feature: not built with `euf.rs`.
7. A hook reading the solver during a call raises: the finding above.

## `_lims`

A read-only `#[getter(_lims)]` on the crate's class, returning Rust's own marks. Not a shim. Before the rebase, on f09ef78's build, orion: mixed suite 1 failed / 6,083 passed, 0 moved against pure Python, all 3 `_lims` tests pass.

Those tests compare Rust with a fresh Rust solver, so they can't see an answer that is consistently wrong. `rtf_compare.py` puts the test's own dump against Python's: 150 seeds, euf 3,645 and both 3,397 answers, byte-identical; 12,228 level reads on Rust, 4,828 on an open level.

## Mutants

Scored before the rebase and the `TermId` alias, 44 builds on pareto1, base `no` throughout. Quiet firings were counted on the engine columns.

**35-61 (27):** real engine 15 (dev answers 37, 38, 51; dev state adds 35, 36, 42, 43, 46, 48, 54, 56, 60; fuzz state adds 40, 44, 59). Real-theory dump adds 41, 45, 47, 49. Boundary suite adds 39.

**Caught by none of these, 7, resting on the API fuzzer alone, which caught all 27 on an older build:**
- 50 `pop: propq survives`
- 52 `pop: applications indexed again in trail order`
- 53 `pop: atoms indexed again in trail order`
- 55 `assert: a repeated conflict check is dropped`
- 57 `term: arity isn't part of a head's key`
- 58 `handles: one namespace for constants, heads and values`
- 61 `on_merge: a raise is swallowed`

None of the 7 fired a quiet handler on the engine columns, so the handler isn't hiding them. The workloads don't reach them.

**Solver 2, 5, 6, 7, 9:** 0 on every engine, real-theory and suite column. 9 is caught by the nested driver only.

**The 10 boundary mutants with no real-engine catch:** real engine still 0 of 10, suite column 0 of 10. The nested driver, not the real engine, catches 17, 18, 27, 29, 31, 32. **Nothing here catches 11, 26, 33, 34.**

## Handle

`Handle` in `euf.rs` is now an alias of `crate::term::TermId`. The numbers still come from `euf_py::Handles`, per theory and not from a query's `TermTable`, since EUF has no table yet. They mean only "the same object", as `TERMS-INTERFACE.md` allows.

## Counts and kept on Python

- **SymPy construction:** 0 for EUF by reading, not a count. The crate holds objects and hashes them, and builds none.
- **Callback counts:** sa-port-11's `fresh/{dev,fuzz}-counts.json`, on an older build. Not repeated on the landing source.
- **Kept on Python:** EUF adds no query-level exclusions. Sum, Product, Integral, queries under a non-default registry, and R9 `enclose` stay as the planner ruled.
- **Shared files changed:** `lib.rs` (2 `mod` lines, 1 `add_to` call), `rust_plugin.py` (`SLICE_EUF=rust`), `backend.py`, `state.py`, `live.py`, `fresh.py`, `mutate_slice.py`, `mutate_live.py`, `mutate_boundary.py`. New: `euf_fuzz.py`, `build_mutants.py`, `rtf_compare.py`, `rtf_column.py`, `borrow_small.py`.

## Not run, or not read

Moved by the landing bar to before any backend PR:
- The mutant 2, 5, 6, 7, 9 rerun's open result and the boundary rescore on the landing source. The columns above are pre-rebase.
- The suite split with Python's counter, history and seed reruns, forced moves, the native path, and timing. **No timing was taken.**
- The public-API version of `test_incremental_matches_fresh`, due by the engine port.

Started on the landing source and **not read at landing**, detached on pareto1 under `~/sp23/out/final/`: Python and mixed suites with the counter, `run_live`, the real-theory compare, 3 mutant builds, `run_history.sh`.

Follow-up: **the wall-clock family wasn't run** (`test_wide_derived_or_against_or_is_fast[nor-or]`, `test_wide_pattern_builds_are_fast[extended_positive-Add]`, `test_performance_smoke_300_vars`). None moved in the suite above. `extended_positive-Add`'s 4.85 s in one earlier suite stays unexplained.

Also not done: a test for what `_lims` returns beyond its length, since the tests read only its length and whether it's empty.
