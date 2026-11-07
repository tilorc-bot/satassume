# Handoff: sa-port-8 to the next session on component 1a (issue 323)

**A first version runs, and it is not held to the step's checks yet.** Nothing went to `rust-slice`. The code is on `port/1a` in `~/dev/sa-port-6`, at 872cef1 plus this file. I stopped at the context note, about 16 minutes in.

Read first: the brief `~/.local/state/agent/briefs/sa-port-8-20261107T073935Z.txt`, whose terms still apply, and the planner's ruling `~/dev/architect/briefs/addenda/sa-port-1a-transfer-ruling.txt`. **Carry that ruling into any later handoff.** `HANDOFF-sa-port-6.md`'s gap table and traps are still useful, but its "refusal" list is overruled (below).

## What actually ran

| Run | Result | What it does and doesn't show |
|---|---|---|
| `tests/test_lra*.py`, Rust solver and LRA on Rust, `-n 4`, no shuffle (`~/sa-rust-ids-work/sa-port-8/lra1/pytest.log`) | 1,868 passed, 43 failed, 1 skipped | All 43 are in the base's list (`port-census/pr328-check/suite-lists.md`): 40 `test_random_cnf_repeated_queries`, plus `test_fuzz_entails_and_implied`, `test_fuzz_solve_against_enumeration`, `test_solver_finds_the_only_consistent_assignment`. **Checked by name and family count, not by an id-by-id diff.** It ran before the group counters existed, so **how many of those tests stayed on Rust and how many moved is unknown.** Many have constants and may have moved. |
| `live.py dev`, py and rust, `--limit 150`, entry check | MATCH, 0 differences | **Shows nothing about LRA:** 24 sessions, `theory_classes` empty, no theory attached in any of them. `state.lra_text` and `lra_of` have therefore **never run on an LRA session**; expect to fix them. |
| `cargo check` of the replay crate in `lra/port` | compiles | The replay check itself wasn't run, and its recorded results predate ascending `_dirty`. |
| `build_solver.sh` | builds | Three dead-code warnings (`lra.rs:62`, `:307`, `rat.rs:119`). |

**Running when I stopped:** `run_live.sh` on full dev and fuzz, started 07:55 UTC, output `~/sa-rust-ids-work/sa-port-8/live1/`, log `live1.log`. `summary.txt` is written last. **No result yet.** Don't run `build_solver.sh` until it ends: the `.so` is copied into the tree these processes loaded from, and later processes (fuzz) load it fresh. If you must rebuild first, kill the run and restart it. It's also the first time real sessions reach `lra_of`, so read the `.err` files first: a crash there means the state code is wrong, not the port.

**Not run at all:** the full suite (no three numbers), `real_theory_fuzz`, `test_solver_real_theories`, history and hash seeds, any mutant, the boundary suite column, any transfer test, any timing. Through `ask()`, I have **not yet seen one session on the Rust core**. Modules now running in the real engine because of this: unestablished, report 0 until live1 shows otherwise.

## What's built

- **Core (`lra.rs`):** `_dirty` is a `BTreeSet`, walked ascending; `PySet` is gone. Added `eager`, `branched_rational`, `reg_order`, `touch`, and `check(budget)`, with the budget read from `lra.BRANCH_BUDGET` per check.
- **`LRA_MUT` 6 and 7 are redefined:** 6 is descending, 7 is first-added order. Neither has been run.
- **Binding (`lra_py.rs`):** `LraCore`, with term ids in Rust and `dump()` for the state.
- **`lra_backend.py`:** a subclass of the Python `LRATheory`, same name. Once moved, its `__dict__` holds real Python state and each hook calls the base class.
- **Patch points:** `backend.install()`, `rust_plugin.py`, `live.py`. `SLICE_LRA=python` keeps LRA on Python with the solver on Rust.
- **Native path:** not built. Each hook is a Python method calling Rust, so nothing can be said yet about the boundary's cost or its shape for siblings.

## The planner's six conditions, and where each stands

| # | Condition | Status |
|---|---|---|
| 1 | Moves only on payload shape | By construction: `_Move` is raised only for an `Element` coefficient, constant or offset. **Reasons recorded: `constant coefficient`, `constant`, `constant offset`.** |
| 2 | Move at every call index, including level > 0; compare answers and full theory state to session end | **Not started.** Plan: a test-only subclass that calls `_move("forced")` when `core.calls == N`, for each N. The backend carries no such hook. |
| 3 | Drop or corrupt each dump field, including `_ONE`/`_ZERO` identity and insertion order; each caught by the real-engine path or named as not caught | **Not started.** `_rows`' outer order, `_cols` and `_forms` are compared sorted, on the claim that order there has no effect (`lra.rs:4-8`). That claim is a reading, so a planted bug there may need naming as not caught. |
| 4 | A failed transfer raises | `_move` builds the state before writing anything and lets exceptions go up. **Untested.** |
| 5 | Three groups, moved count beside any speed number | `state.lra_of` returns `rust`, `python` or `moved:REASON:CALL:LEVEL`; `live.py` totals them, `livecmp.py` counts them by leading word. **Unexercised.** `rust_plugin.py` records per-test `lra` counts. |
| 6 | Other refusals ported as raising the same exceptions; transfer deleted by 1b; name what keeps it alive | The raising cases are in `register_atom`, `_register`, `_pairs` and `LraCore.pop_level`, each written to leave Python's state behind. **No test covers them directly yet.** The planner's question "what would keep it alive" hasn't been looked at. |

## Differences and shims to name in the report

- **Known difference, deliberate and untested:** a non-int literal, or one outside i32, raises on Rust and doesn't on Python (`1.0` hits the dict in Python). The solver only passes i32 ints, so the engine can't reach this.
- **Test shim:** `__getattr__` answers private field reads from a fresh Python copy (`_view`). `counts["views"]` counts them.
- **Test shim, and not a port:** `certified`, `certified_with` and `_certificate` answer from that copy. **`lra_cert` isn't ported and doesn't count.** Its reach is still only by reading: under `if fields` in `_branch`. Check it by running, as the brief asks. Note `rational_values` also goes through views, one per field read.
- **Raises rather than falling back:** a write to a private state field on a live core raises `AttributeError`. I found no such write by rg in `test_lra*`, `test_switched_glue` or `test_transfer`; the rest of `tests/` wasn't searched.
- **Unchecked risk:** a test calling a private *method* (`t._simplex()`) runs the Python code over views, and any mutation is silently lost. That's a quiet wrong answer in a test, not an engine path. Run `rg '\._(simplex|check|branch|implied|int_verdict|pivot|update|assert_kind|set_upper|set_lower)\(' tests/`, and make those methods raise on a live core if any turn up.
- **The `_n_conflicts` view** stays named as a test-plugin shim with its 64 tests, per the ruling.

## A change to a shared tool

`live.py`'s `_hook` now skips a hook call made by the same object from inside its own hook. Python's `_check` calls `self.push_level()` and Rust's core can't show that, so the streams would otherwise differ. **This applies to both backends, so the Python stream changes as well: its digests can't be compared with recordings made before this commit, and the stream checks a little less on Python than it did.** Say so in the report. Sibling ports get this change when they rebase.

Other shared files touched, also to name: `backend.py`, `rust_plugin.py`, `state.py`, `livecmp.py`, `solver_rs/Cargo.toml` (new dependencies), `solver_rs/src/lib.rs`.

## Order from here

1. Read `live1`: `.err` files, then `summary.txt`, then `lra_groups` in the `.tot` files. Any difference gets its smallest case.
2. The `_dirty` test the brief asks for: Rust's order against Python's on a case where the order changes the output, plus `LRA_MUT` 6 and 7 caught by it. Needs `--features mutants` on the crate.
3. Transfer at every call index (condition 2), with its own theory-state comparison.
4. `real_theory_fuzz`, `test_solver_real_theories`. Then `run_suite.sh WORK rust` and `python`, with `SLICE_SUITE_SHUFFLE=1` and `PYTEST_N="-n 3"` as in the last check, then `suite_report.py`, compared by id with 5,961 / 77 / 46. Sum `lra` over the rows for the groups.
5. `run_history.sh`, `historycmp.py`, hash seeds.
6. Dump-field mutants (condition 3). Solver mutants 2, 5, 6, 7, 9 through `mutate_live.py`. Boundary mutants through `mutate_boundary.py`, including `--suite`, and the 10 with no real-engine catch (11, 26, 33, 34; 27, 29, 31; 17, 18, 32). New mutants in payload conversion, term ids and model rendering. **Note the solver's mutants 6 and 7 aren't `LRA_MUT` 6 and 7.**
7. Native path, then timing on a quiet pareto1 lease, with the moved count beside the numbers.
8. Rebase on `origin/rust-slice`, push without force, report.

ENV TRAP still applies: after sourcing `env.sh`, set `PYTHONPATH=$PWD:$W/sympy:$W/shim`. `run_live.sh`, `run_history.sh` and `run_suite.sh` handle this themselves. Job output goes under `~/sa-rust-ids-work/sa-port-8/` (or your own session's directory).

## File:line map (at 872cef1)

| Topic | Where |
|---|---|
| Subclass, attribute traps | `slice/lra_backend.py:62`, `:78`, `:87` |
| Read properties, certificate shim | `lra_backend.py:97-125` |
| Hooks | `lra_backend.py:134-167` |
| Payload conversion | `lra_backend.py:175` `_register`, `:212` `_touch`, `:219` `_pairs`, `:243` `_forget`, `:41` `_once` |
| State, view, transfer | `lra_backend.py:253` `_state`, `:260` identity, `:293` `_view`, `:301` `_move`; install `:313` |
| Binding | `slice/solver_rs/src/lra_py.rs:89` new, `:106` register, `:133` check, `:208` dump |
| Core changes | `lra/port/src/lra.rs:134` `Dirty`, `:333` touch, `:420` reg_order, `:728` branched, `:964` check, `:1042` propagate, `:1057` mutants 6, 7 |
| Theory state, groups | `slice/state.py:143` `lra_text`, `:173` `lra_of` |
| Live harness | `slice/live.py:192` hook filter, `:299` and `:315` install, `:381` groups; `slice/livecmp.py` `lra_diff` |
| Install points | `slice/backend.py:46`; `slice/rust_plugin.py:70` |
| Python theory | `theories/lra/lra.py:339` class, `:545` register, `:553` assert, `:599` propagate, `:917` branch, `:1176` check |
| Earlier maps | `HANDOFF-sa-port-6.md`, `HANDOFF-sa-port-1.md` |
