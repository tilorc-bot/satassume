# Handoff: sa-port-15 to the next EUF port session (issue 323)

**Component 2 isn't done, and nothing is on `rust-slice`, so 0 of the 32 modules have been added by this port yet.** Handed off at the 150k context note, not on a blocker. The brief's terms still apply: `~/.local/state/agent/briefs/sa-port-15-20261107T082814Z.txt`. Clone `~/dev/sa-port-15`, branch `port/2`. Job output: `~/sa-rust-ids-work/sa-port-15/` (below, `$O`). Build sha256 starts 08912bb0cfb7: the crate is unchanged, and the sa-port-7 jobs used the same file.

## Decide first: the mixed suite's 3 failures

`SLICE_SUITE_SHUFFLE=1 SLICE_EUF=rust`, `$O/suite-mixed/`, this clone: **5 failed, 6,079 passed, 23 skipped, 18 xfailed**, 6,125 ids, against pure Python's 1 / 6,083 (`port-census/pr328-check/suite-python`). 4 outcomes moved, passed to failed:

| Test | Failure |
|---|---|
| `tests/test_solver_real_theories.py::test_real_theories_match_fresh_solvers[euf]` | `AttributeError: 'EUFTheory' object has no attribute '_lims'`, `tests/real_theory_fuzz.py:259` |
| `...match_fresh_solvers[both]` | same |
| `tests/test_verify_integration.py::test_theory_levels_match_the_solver_after_ask` | same, `tests/test_verify_integration.py:97` |
| `tests/test_wide_derived.py::test_wide_derived_or_against_or_is_fast[nor-or]` | wall clock, 2.23 s against `< 2.0` |

The fifth failure is the one that didn't move: `test_performance_smoke_300_vars`, which also failed in the Python base run.

**The `_lims` three are a gap, not a pass and not shown to be a wrong answer.** They read a private the crate's class doesn't have (known difference 5). `run_seed` stops at that line, so **the real-theory answer comparison in `match_fresh_solvers` doesn't get through on Rust EUF**, and that's the test this mode was meant to reach. Don't edit the tests. Options: a read-only level count on the crate's class, or a named shim in `rust_plugin.py`, as with `_n_conflicts`. Whichever you pick, name it in the report and read what those tests then do. Not raised with the planner yet.

**The 77 and the 46 in this run, by id:** 120 of 123 passed; the rest are in the table above. Passing here doesn't show a test read an EUF answer, since most of them may never build an EUF theory; that wasn't counted. Nothing else in the run moved.

## Results so far

| Run | Where | Result |
|---|---|---|
| Suite, Rust solver and Rust EUF | sa-port-7's run on cf1345e's source, read here (`$O/suite-rust-read`, `suite-rust-report.md`); `SLICE_SUITE_SHUFFLE=1`, `-n 4` | **5,959 / 77 / 46 plus 2 failures**, base 5,961 / 77 / 46. By id: 6,125 on both, none added or gone, same 77, same 46, 2 moved |
| Fresh engine, memos cleared | sa-port-11's `fresh/`, `cmp` here; repeated with the counter in `$O/handlers/` | dev 1,985 and fuzz 3,000 byte-identical, py against rust, each across hash seeds 0 and 1. A sample of orders |
| `run_live.sh`, final build | `$O/live/`, this clone | **All 8 comparisons MATCH, final build:** dev 1,985 queries, 918 sessions; fuzz 3,000 queries, 3,133 sessions. Finished 09:51 UTC, `summary.txt` |
| API fuzz, 35-61 | `$O/mut-api/summary.txt` | 27 of 27 caught, base 0 differences. API fuzzer only |
| Mutants on the real engine, dev | `$O/mut/table.md` | Below. Fuzz columns not run |

### The 2 wall-clock failures: not settled

`test_wide_derived_or_against_or_is_fast[nor-or]` (2.19 s; 2.23 s in the mixed run) and `test_wide_pattern_builds_are_fast[extended_positive-Add]` (4.85 s, not reproduced). They stay failures in the numbers. Alternating 5 rounds alone at load about 54 (`$O/wide/`): Rust EUF 5 of 5 pass; Python EUF on the Rust solver 3 of 5, its failures being sibling params `[or-or]` 3.5 s and `[nor-nor]` 2.9 s. That leans to load, but isn't timing evidence. **Unexplained:** `extended_positive-Add` took 0.05-0.13 s alone and 4.85 s in the suite, more than load seems to account for. **Next:** a full suite from this clone, which is also the first with the handler counter on Rust, then the same tests on the quiet lease on pareto1.

### Mutants, dev only

Scored on 42 builds, `$O/mut/m*` (2, 5, 6, 7, 9, the 10 no-catch, 35-61). All built, all sites matched, all files distinct, base `no` on both.

- **35-61, dev state: 12 of 27** (35, 36, 37, 38, 42, 43, 46, 48, 51, 54, 56, 60). **Answers: 3 of those** (37, 38, 51).
- **Not caught on dev: 15** (39, 40, 41, 44, 45, 47, 49, 50, 52, 53, 55, 57, 58, 59, 61). Fuzz may catch them. Anything still uncaught is a finding: report it, don't drop it.
- **2, 5, 6, 7, 9 and the 10 (11, 26, 33, 34, 27, 29, 31, 17, 18, 32): 0 caught on dev.** Fuzz columns and the boundary suite column are still to run.

## What's left, in order

1. **Fuzz columns.** The reference `$O/live/fuzz-py.jsonl` is complete. `cd rust-spike/slice; . ~/sa-rust-ids-work/env.sh; export PYTHONPATH=$HOME/dev/sa-port-15:$W/sympy:$W/shim; nice -n 10 $PY mutate_live.py $O/mut $O/live --only 2,5,6,7,9,11,17,18,26,27,29,31,32,33,34,35,...,61 --checks fuzz-ans,fuzz-state --jobs 4 --resume`. Score `fuzz-ans` first and `fuzz-state` only on what's left; `fuzz-state` took about 20 minutes a build at this load. `--resume` keeps the dev cells in `results.jsonl`.
2. **Boundary suite column:** `mutate_boundary.py $O/mut $O/boundary --only ... --suite tests/test_euf.py tests/test_euf_adapter.py tests/test_euf_fuzz.py tests/test_transfer*.py` (`$O/mut` holds `base` and `mK`). State the column, and how many of the 10 now get a catch.
3. **The `_lims` decision** above, then rerun the mixed suite.
4. **Full suite from this clone with the counter:** `SLICE_SUITE_SHUFFLE=1 PYTEST_N="-n 4" bash rust-spike/slice/run_suite.sh $O/suite-rust rust -p handler_count`. Compare: `$PY $O/suite_diff.py $O/suite-rust ~/sa-rust-ids-work/port-census/pr328-check/suite-rust`.
5. **History:** `run_history.sh`, `historycmp.py`. **Crossing counts:** sa-port-11's `fresh/{dev,fuzz}-counts.json` are on this build, in its handoff's table.
6. **Timing, reported only**, quiet lease on pareto1. Then rebase on `origin/rust-slice`, rerun the suite if others' source came in, push without force, report the SHA. 1 of the 32 counts only then.

## Open points, measured

`euf_points.py`, warm engine, workload order; `$O/points/`. Python and Rust rows are identical.

| | dev | fuzz | `same`, built to repeat one assumption set |
|---|---:|---:|---:|
| Theories | 198 | 3,018 | 6 |
| Used in more than one top-level query | 0 | 0 | 0 |
| Handles handed out again in a later query | 0 | 0 | 0 |
| Merges heard | 33 | 1,724 | 28 |
| Calls on a theory during a listener | 0 | 0 | 0 |
| Same, with a planted `find` in the listener (control) | 33 | 1,724 | not run |
| Listeners seen | `TransferTheory._merged` only | same | same |

- **Lifetime against "no id survives a top-level query":** none crossed in these runs. By reading, `_build_context` makes a fresh session per contextual query, and `_context_sessions` (`engine.py:1367`) is declared but `rg` finds no other use. Measured on these workloads, not proved. The `rep` and `members` reads aren't watched on Python.
- **Re-entry:** `_merged` (`transfer.py:196`) appends to two plain lists (`:126`, `:135`). None re-entered on 1,757 merges. **The seed 1350 difference stays reported as a difference** (recursion limit at about 213 terms on Python, about 1,011 on the crate); this shows only that the engine didn't reach it.
- **Handle:** the minimal `Handle` stays (`euf.rs:21`), for the reason in sa-port-11's handoff.

## The architect's question: quiet handlers

`handler_count.py`, `sys.monitoring`, counts `except Exception` at `engine.py:1906` (`_build_context`) and `sympy_api.py:1107` (`_consistent`, sa-port-19 is reading it).

| Run | Firings |
|---|---:|
| Fresh engine, dev and fuzz, Rust EUF and Python | **0 at both sites, on all four**; the `.tsv` matches the uncounted run |
| Mixed suite, 6,125 tests | **0 rows; treat as unconfirmed.** The counter's self-test (`$O/handlers/selftest.py`) ran outside pytest, and I didn't show it fires under `-p handler_count`. Check that first: plant a raise in one test run |
| Rust solver and Rust EUF suite | **Not run with the counter**: step 4 |
| Mutants | **Not counted.** A mutant raising in the complete check could be swallowed there, which matters for the 15 uncaught on dev |

The self-test shows the concern is real: the planted raise gave 1 row, and the answer stayed `True`.

## Report wording still owed

S's standing, the `_n_conflicts` shim and its 64 tests, kept-on-Python list, SymPy construction 0 by reading, not a count, and the differences list: all in `HANDOFF-sa-port-11.md`, "Differences from Python" and "For the report". Add `_lims` to its item 5.

## File:line map

| Topic | Where |
|---|---|
| Mixed mode switch | `rust-spike/slice/rust_plugin.py:79` |
| `_lims` readers | `tests/real_theory_fuzz.py:259`, `tests/test_verify_integration.py:97`, `:100` |
| Levels on the crate | `rust-spike/slice/solver_rs/src/euf_py.rs:285` (`push_level`), `:289` (`pop_level`) |
| Handler counter | `rust-spike/slice/handler_count.py`; `fresh.py --handlers FILE`; `-p handler_count` in a suite run, writes `handlers.PID.jsonl` |
| Open-point tool | `rust-spike/slice/euf_points.py` |
| Build all mutants one at a time, then score with `--resume` | `$O/build_mutants.py` |
| Suite diff by id | `$O/suite_diff.py` |
| Everything older | `HANDOFF-sa-port-11.md`'s map, then `HANDOFF-sa-port-7.md` and `HANDOFF-sa-port-1.md` |
