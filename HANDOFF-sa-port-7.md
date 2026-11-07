# Handoff: sa-port-7 to the next EUF port session (issue 323)

**Component 2 isn't done, and nothing is on `rust-slice`.** The port is written and wired on `port/2`, and has only had a smoke run. Read the brief first: `~/.local/state/agent/briefs/sa-port-7-20261107T073352Z.txt`. Its terms still apply. Work only in `~/dev/sa-port-7`; job output goes under `~/sa-rust-ids-work/sa-port-7/`.

## What exists

- `solver_rs/src/euf.rs`: all of `euf.py`, in the same order, with no pyo3.
- `solver_rs/src/euf_py.rs`: `sa_solver.EUFTheory`, plus live `rep` and `members` views for `transfer.py`.
- `backend.py` and `rust_plugin.py` put it behind `EUFAdapter` and behind a test's own `EUFTheory` import. `SLICE_EUF=py` keeps Python's EUF on the Rust solver, for comparison.
- `state.py` and `live.py`: session digests now include all 18 EUF fields on both backends. Old recorded digests won't compare, so regenerate the Python reference.
- `satassume/` is unchanged. `lib.rs` changes only by `mod euf; mod euf_py;` and one `add_to` call.

**The design point to keep:** `Euf::union` returns the merge, and `PyEuf::process` calls `on_merge` with no borrow held. So a listener can re-enter and sees the state Python shows at that point. Never hold `core` across a call into Python, including hash, eq and repr. That's why the class is frozen with a `RefCell`.

## What has run (orion, `tree.txt` confirms this clone)

| Run | Result | Output |
|---|---|---|
| `test_euf`, `test_euf_adapter`, `test_euf_fuzz`, Rust solver and Rust EUF | 11 failed, 132 passed, 2 xfailed | `smoke/` |
| `test_euf`, `test_euf_fuzz`, Rust solver and Python EUF | 11 failed, 61 passed, 2 xfailed; **the same 11 ids** | `smoke-euf-py/` |
| One scripted session, Python EUF against the crate: results, repr, 18 state fields | identical | not saved |

**The 11:** 7 in `test_euf.py`, 4 in `test_euf_fuzz.py`. 5 are `'Solver' object has no attribute '_val'` and 4 are `Already mutably borrowed`. The other 2 are ExceptionGroups, and I didn't read those. They fail the same way without the Rust EUF, so nothing points at the port, but **I haven't checked them by id against the base's 77 and 46.** Do that first.

**Not run:** no engine workload and no real query has run on Rust EUF. That means no `run_live`, fresh-engine comparison, history run, full suite, mutants, counts or timing. `tests/test_transfer*` hasn't run either, so the `rep`/`members` surface has only had the scripted session. Don't read the smoke run as evidence for any "held to" item.

## What's left, in order

1. **Handle: decide and swap.** sa-port-5 published it after the core was built: `port/D0` at f153b66, `TERMS-INTERFACE.md`, `solver_rs/src/term/mod.rs`. The brief says to use it if it's there. Suggested fit: `Key::Const` and `Key::Value` take `TermId`, `Key::Head` takes `ClassId`, about 10 lines. Check that `port/D0` is still current, then cherry-pick or rebase. `Handles` (the Python dict) stays until `TermTable` exists. **Open point to raise:** the interface says no id survives a top-level query, and a dict-backed id is per theory. Check that against how long a session's theory lives before relying on it.
2. **API differential fuzz, new file `euf_fuzz.py`.** Random op sequences on Python's class and the crate: `term`, `value`, atoms, assert, check, propagate, explain, push and pop, comparing `state.diff` after every op. Include a listener that reads `rep`, `members` and `explain`, one that re-enters `term`, and one that raises. Include a repeated assert, whose pop raises KeyError in Python.
3. `sh rust-spike/slice/run_live.sh ~/sa-rust-ids-work/sa-port-7/live`: dev and fuzz, answers and state. Report any difference with its smallest case; don't reclassify it. It starts 5 processes per workload, so check orion's load first.
4. Fresh engine with memos cleared (`seed_state.py`, see `results/pr328-check.md`), then `run_history.sh`.
5. Full suite on both backends, with `SLICE_SUITE_SHUFFLE=1` and `PYTEST_N="-n 4"` or less, then `suite_report.py`. Compare by id against 5,961 / 77 / 46. **`tests/` builds EUF directly, so tests can move between numbers.** Explain each move.
6. Planted bugs: add EUF mutants to `mutate_slice.py`'s `M` (check that its scratch-copy build picks up the two new files). Rerun 2, 5, 6, 7, 9 on these paths. Run the boundary suite column. State how many of the 10 no-real-engine-catch mutants (11, 26, 33, 34, 27, 29, 31, 17, 18, 32) now get a catch. Solver mutants may well still not be caught by live runs, since EUF changes the theory and not the solver; say so if that's the result. `run5_harness.sh`, `run-audit.sh` and `run6_counts.sh` still have the old path: fix them before using them.
7. Counts: `term`/`value` calls (hash and eq on SymPy objects), `on_merge` calls, `rep`/`members`/`explain` crossings, solver hooks into EUF. SymPy construction should be 0 for EUF, but that comes from reading, not a count. Kept on Python, by reason.
8. Timing on a quiet lease on pareto1, reported only. Then rebase, push to `rust-slice` without force, and report with the SHA, the three numbers and the module count. **"The 32 runtime modules" isn't defined in the inventory** (rg found no such list); ask the architect or derive it from section 2, and say which.

Standing rulings for the report are in the brief: S's standing wording, the `_n_conflicts` shim and its 64 tests, and the mutant statement.

## Differences from Python that I know of

All are at the API edge, and none has been shown to reach the engine. Report them, or fix the first.

- `term(head, None)` returns the constant; Python raises TypeError (`euf_py.rs:149`). **Easy fix: not done.**
- A literal past i32 raises OverflowError, as the crate's solver does.
- Negative term ids are normalised up front in `find`, `equal` and `explain`. Python indexes from the end, and `_explain` then walks those raw negative ids.
- `members[r]` returns a new list, not an alias. By reading, `transfer.py` keeps an item only within one hook, and nothing merges during it. Not tested.
- One `Handles` dict covers the c, h and v namespaces, where Python has one tuple-keyed dict. They could differ only if `==` on heads isn't transitive, and could change the `keys` text only if a Float and a Rational compare equal. **Neither is checked in this SymPy.**
- `EqAtom` stays the Python class, since `euf_adapter` builds it. The crate imports it per theory.
- Private fields (`_keys`, `_trail`, ...) don't exist on the crate's class. By rg, no test in `test_euf*`, `test_transfer*`, `real_theory_fuzz` or `theory_harness` reads `.rep`, `.members` or `on_merge`; the wider suite isn't checked for EUF privates.
- `fxhash` feature: not built with `euf.rs`.

The solver still reaches EUF through the Python methods (`lib.rs`'s `PyTheory`), so the hook mutants stay on the path. Direct Rust dispatch is the obvious speed step, and it's left out on "something that works first".

## File:line map

Start from `HANDOFF-sa-port-1.md`'s map.

| Topic | Where (`rust-spike/slice/`) |
|---|---|
| Handle, keys | `solver_rs/src/euf.rs:21`, `:25` |
| Union, undo, explain | `euf.rs:233`, `:333`, `:377` |
| `_apply`, `_index_app` | `euf.rs:165`, `:175` |
| Assert, propagate, pop | `euf.rs:434`, `:475`, `:514`, `:555` |
| Handles, class | `solver_rs/src/euf_py.rs:18`, `:46` |
| `_process` driver, `term`, `register_atom`, `dump` | `euf_py.rs:67`, `:150`, `:202`, `:281` |
| Views | `euf_py.rs:353`, `:398` |
| State dump, Python side | `state.py:127`, `:136`, `:181` |
| Wiring | `backend.py:34`, `:38`; `rust_plugin.py:72`; `live.py:279`, `:285-299` |
| Python reference | `satassume/theories/euf/euf.py`; adapter `euf_adapter.py:105`, `:206`, `:243` |
| Transfer's reads | `satassume/theories/transfer.py:135`, `:144`, `:196`, `:248`, `:269`, `:301`, `:373`, `:409`, `:437`, `:494` |
| Mutants | `mutate_slice.py:28`; `mutate_live.py`; `mutate_boundary.py`; `mutants_joined.py` |
| Suite | `run_suite.sh`, `suite_report.py`; how it was last run: `results/pr328-check.md` |
