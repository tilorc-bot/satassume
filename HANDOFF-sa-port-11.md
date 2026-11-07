# Handoff: sa-port-11 to the next EUF port session (issue 323)

**Component 2 isn't done, and nothing is on `rust-slice`.** Rust EUF has now run real queries and matches Python. `run_live` was on a build one commit older than the current one; the suite and fresh engine are on the current one. Read the brief first: `~/.local/state/agent/briefs/sa-port-11-20261107T074613Z.txt`. Its terms still apply. Work only in `~/dev/sa-port-7`, branch `port/2`. Job output goes under `~/sa-rust-ids-work/sa-port-11/` (or your own session's directory for new runs). Handed off at the 150k context note, not because of a blocker.

## Results so far (orion; `tree.txt` confirms this clone)

| Run | Build | Result | Output |
|---|---|---|---|
| `run_live.sh`, dev: 1,985 queries, 918 sessions | **9d75640, before the fix below** | 0 answer, end-state or call-stream differences, all 4 comparisons MATCH | `live/summary.txt` |
| `run_live.sh`, fuzz: 3,000 queries, 3,133 sessions | **9d75640, before the fix below** | Same, all 4 MATCH. `answers_sha` 173502b6ef285ad6 (dev 31cd0945c07f02a6) | `live/summary.txt` |
| `euf_fuzz.py`, plain heads, 600 seeds, 90,000 ops | a3181a8 | 0 differences | `fuzz/plain.txt`, with what it reached |
| `euf_fuzz.py`, SymPy heads, 200 seeds, 24,000 ops | a3181a8, before `explain` was aimed at equal pairs | 0 differences | `fuzz/sympy.txt` |
| `euf_fuzz.py --unbounded`, 400 seeds | a3181a8 | **5 differ: known difference 1 below** | `fuzz/unbounded.txt` |

**Rerun `run_live.sh` on the final build.** The fix changes keys only for heads that compare equal, which I expect doesn't reach the engine, but that's unchecked. And no mutant has run yet, so nothing shows these MATCH lines would fail on a broken EUF.

## The 11 failing ids: checked by id

All 11 are in the base's numbers, against `port-census/pr328-check/suite-rust/classes.json`: **5 in the 77** (`_val`: `test_solver_congruence_unsat_and_sat`, `test_solver_transitivity_unsat`, `test_solver_values`, `test_perf_through_solver_chain`, `test_perf_through_solver_disjunctive_chain`) and **6 in the 46** (4 `Already mutably borrowed`, plus the 2 ExceptionGroups). The ExceptionGroups' sub-exceptions were read, and match on base, Rust EUF and Python EUF: `test_dpll_t_matches_enumeration` has `_trail_lim`, `_val`, borrow; `test_every_full_assignment_through_solver` has `_val`, borrow. So they aren't EUF's. **Equally, they never read an EUF answer on the Rust solver, so they aren't evidence for it.** That's why `SLICE_EUF=rust` exists (below).

## Finished after the first report, build a3181a8 (sha256 starts 08912bb0cfb7)

**Suite** (`suite-rust/`, `suite-report.md`; `SLICE_SUITE_SHUFFLE=1`, `-n 4`, load 37-51): **5,959 / 77 / 46, plus 2 other failures**, against the base's 5,961 / 77 / 46. By id against `port-census/pr328-check/suite-rust`: 6,125 ids on both, none gone or added, the 77 and the 46 are the same ids, and exactly 2 outcomes moved, passed to failed, both wall-clock asserts:
- `tests/test_wide_derived.py::test_wide_derived_or_against_or_is_fast[nor-or]`: 2.19 s against `< 2.0`
- `tests/test_wide_derived.py::test_wide_pattern_builds_are_fast[extended_positive-Add]`: 4.85 s against `< 4.0`

Alone, the two passed 3 of 3 with Rust EUF, 3 of 3 with Python EUF on the Rust solver, and 2 of 2 on pure Python, at load about 50. So they point at load, but **that's not shown**: passing alone isn't a speed comparison, and they stay in the numbers as failures until a full suite run passes them. A quieter rerun, or the timing lease, settles it. `test_performance_smoke_300_vars` passed. The Python rows are `pr328-check/suite-python`, reused: `git diff 2d00bea -- satassume tests` is empty.

**Fresh engine, memos cleared** (`fresh/`, `fresh.py`): identical line for line, answers and digests, for dev 1,985 and fuzz 3,000: py against rust at seed 0 and at seed 1, py and rust each across seeds 0 and 1, and counted against uncounted. Only 2 seeds, so a sample of orders.

**The digests do hold EUF:** a check on the first 400 dev queries found all 18 fields in every session with an EUF theory, non-empty. **But EUF's reach is modest:** 18 of 489 sessions in that sample.

**Crossings** (`fresh/{dev,fuzz}-counts.json`), Rust run, fresh engine. `rep` and `members` count attribute reads, not item reads through a view:

| | dev, 1,985 queries | fuzz, 3,000 queries |
|---|---:|---:|
| Theories made | 222 | 3,192 |
| `term` / `value` | 665 / 384 | 16,017 / 10,685 |
| `register_atom` | 588 | 12,973 |
| `assert_lit` | 1,250 | 33,116 |
| `check` / `propagate` | 446 / 4,444 | 8,081 / 147,772 |
| `push_level` / `pop_level` | 3,666 / 3,242 | 119,828 / 111,394 |
| `on_merge` | 35 | 1,728 |
| `explain` | 13 | 5,570 |
| `rep` / `members` reads | 1,397 / 1,522 | 89,439 / 89,232 |

dev's 35 merges and 13 explains are thin, so fuzz carries most of the real-engine evidence.

`fresh.py` replaces `port-census/seed_state.py` for this: that one digests Python's solver only, has no EUF fields, and imports `state` from `~/dev/sa-port`.

## What's left, in order

1. **Settle the 2 wall-clock failures** above, by rerunning the suite on the final build. Any move by id gets explained. Whether any test reads EUF privates: none showed up as a failure, and the 77 and 46 are unchanged.
2. **Mixed mode, not run yet:** `SLICE_EUF=rust bash run_suite.sh DIR python`: Rust EUF on Python's solver. It's the only run where the 11, and whichever of the 77 and 46 reach EUF, read a Rust EUF answer. Compare with the Python rows by id. Run at least `tests/test_euf*.py tests/test_transfer*`, preferably everything.
3. **Mutants.** 27 added at the end of `mutate_slice.py`'s `M`, numbers 35 to 61, each site checked to match exactly once. **None has been built or scored.** The scratch-copy build does pick up `euf.rs` and `euf_py.rs`, since it copies the crate and writes `src/<file>`. `mutate_live.py WORK ~/sa-rust-ids-work/sa-port-11/live --only 2,5,6,7,9,11,17,18,26,27,29,31,32,33,34,35,...,61 --checks ...`, then `euf_fuzz.py --so WORK/mK` on the same builds for the API column. Fuzz state took about 20 minutes per build at this load, so score dev-ans, dev-state and fuzz-ans first, then fuzz-state only on what's left, using `--resume`. Then `mutate_boundary.py` with `--suite tests/test_euf.py tests/test_euf_adapter.py tests/test_euf_fuzz.py tests/test_transfer*.py`: that's the boundary suite column nobody has run. State how many of the 10 no-real-engine-catch mutants (11, 26, 33, 34, 27, 29, 31, 17, 18, 32) now get a catch. Those are solver and boundary mutants, so they may well still not be caught; say so if that's the result. Anything uncaught in 35-61 is a finding: report it, don't drop it. `run5_harness.sh`, `run-audit.sh` and `run6_counts.sh` still have the old path; fix them before use.
4. **History:** `run_history.sh`, then `historycmp.py`. Also rerun `run_live.sh` on the final build, with the same check on tree.txt.
5. **Handle swap.** Not done, and I'd leave it. `Handle` in `euf.rs:21` is the minimal handle to name in the report. `TERMS-INTERFACE.md` on `port/D0` (456b07b, algebra at 1c0d989) says in "Until a consumer has a table" that EUF can stay on opaque `u32`s. A swap now is a rename, and a misleading one: these numbers come from a per-theory dict keyed per namespace and arity, so they aren't indexes into a query's table, and `(c, 1)` and `(v, 1.0)` get different numbers though `==` agrees. A real swap comes with `TermTable` in the adapter (component 4). **Still open, raise it:** the interface says no id survives a top-level query; how long a session's theory lives against that hasn't been checked.
6. Timing on a quiet lease on pareto1, reported only. Then rebase on `origin/rust-slice`, rerun the suite if others' source came in, push without force, and report with the SHA.

## Differences from Python

**Found and fixed in a3181a8:**
- One `Handles` dict across namespaces: a difference, not just a risk. Smallest case: `term(1.0)` then `value(1)`, keys read `1=v:1` on Python and `1=v:1.0` on the crate; also `0.5` against `Float(0.5)` in this SymPy. Handles now use `_keys`' own tuples.
- `term(head, None)` now raises TypeError, as Python does.

**Known and still there. Report them:**
1. **Unbounded re-entry stops at a different depth.** A listener that re-enters `term` and keeps merging hits Python's recursion limit at about 213 terms on Python and about 1,011 on the crate, because Python has about 5 frames a merge and the crate has 1. Both raise RecursionError, in different states. Smallest shrunk case: seed 1350, 10 ops; `euf_fuzz.py --unbounded --start 1000 --seeds 400`. Bounded re-entry (40 calls, the default) shows no difference. By reading, `transfer._merged` (`transfer.py:196`) only appends to two lists, and it's the one listener `satassume/` sets, so the engine doesn't reach this.
2. A literal past i32 raises OverflowError, as the crate's solver does. Left out of the fuzz.
3. `explain` with a negative id: Python walks raw negative ids in `_explain`; the crate normalises. Left out of the fuzz. `find` with a negative id is in it, and matches.
4. `members[r]` returns a new list, not an alias. By reading, `transfer.py` keeps one only within a hook. Not tested.
5. Private fields don't exist on the crate's class.
6. `fxhash` feature: not built with `euf.rs`.

## History independence, by reading only

`euf.rs` and `euf_py.rs` have no statics or thread-locals (rg). `Map` is only looked up and never iterated, except `keys` in `dump`, which sorts. `Handles` is per theory. The run-level check is `fresh/` across seeds, and `run_history.sh`.

## For the report

- **The 32 modules:** section 2's port and split rows, counted by file, come to exactly 32. Before this port, 1 decides real queries, `sat/solver.py` (`sat/theory.py` and `sat/formula.py` are still Python, by section 2's note; check this if a sibling has landed). **This port adds 1, `theories/euf/euf.py`**, once it's on `rust-slice`. `euf_adapter.py` stays Python, as the brief says.
- **Shared files changed:** `rust_plugin.py` (`SLICE_EUF=rust`, plus the earlier switch), `backend.py`, `state.py`, `live.py`, `mutate_slice.py`; `lib.rs` by `mod euf; mod euf_py;` and one `add_to` call. New: `euf_fuzz.py`, `fresh.py`.
- **Kept on Python:** EUF adds no query-level exclusions. Queries kept on Python stay as the planner ruled.
- **SymPy construction:** 0 for EUF comes from reading, not a count. The crate holds objects and hashes them, and builds none.
- The standing wording for S, the `_n_conflicts` shim and its 64 tests, and the mutant statement are in the brief.

## File:line map

Start from `HANDOFF-sa-port-7.md`'s map, which is still right for `euf.rs`. In `euf_py.rs`, lines moved down about 30 from a3181a8's `Handles` change.

| Topic | Where (`rust-spike/slice/`) |
|---|---|
| Handles, keyed as `_keys` | `solver_rs/src/euf_py.rs:18`; `Args` just below |
| API fuzz: ops, listeners, reach | `euf_fuzz.py`: `run_op`, `attach`, `tally`; `REENTER_CALLS` for the bound |
| Fresh engine, counts | `fresh.py`; `--counts` is rust only |
| Mixed mode | `rust_plugin.py`, the `SLICE_EUF == "rust"` block above `_init` |
| EUF mutants | `mutate_slice.py`, `M[35:]` |
| Base rows | `~/sa-rust-ids-work/port-census/pr328-check/suite-{rust,python}` |
