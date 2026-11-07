# Handoff sa-rust-16: S step 3 is done (issue 323, branch rust-slice)

No job is running. Next is step 4, in another session: the whole-suite and history gate.

## Read first
`rust-spike/slice/results/step3-live.md`: counts, mutant table, reach, re-entry, limits.

## For step 4
- **Decide what "suite with the backend on" means, and say so.** `backend.install()` covers `engine.Solver` and `ref.Solver` only, so the 19 test files that import `Solver` from `satassume.sat.solver` by name (rg) stay on Python. Install it from a pytest plugin under `rust-spike/` (`pytest -p`), since `satassume` and `tests/` can't change. To go further, patch `SV.Solver` too, before collection. Then expect failures that aren't answer differences: `test_lra_integers`, `test_solver_incremental`, `test_solver`, `theory_harness` and `test_transfer` read private attributes, and `test_solver.py:962-980` uses provenance, which raises NotImplementedError in Rust. Sort those from real ones and list them.
- **Re-entry:** 0 of 1,276,418 hook calls on the workloads. The suite is the first run of `tests/`' own theories. The planner's ruling stands: a gate failure unless only test stubs do it.
- **Restarts and `reduce_db`:** 0 on dev and fuzz. Measure whether the suite reaches them with real theories, and the same for the 5 unreached mutant paths. To do that, patch `eprintln!` at the sites as step 3 did; the conditions are in the results file's probe table.
- **Boundary mutants, plan section 4:** batch flush order, swapped callback order, a dropped theory result, a stale handle after a nested session. Add them to `M` in `mutate_slice.py`, and `mutate_live.py` picks them up. There's no batching in the crate, so batch flush order may need arguing as not applicable. Sites below.
- B to E are unfixed and didn't occur. Check they stay so under the suite.
- Pass rule holds as written, leaning on the API fuzzer for 2, 5, 6, 7, 9. The planner may want to look at that; it's in the report.

## The 6 history runs, and what exists
| # | Run | Tool |
|---|---|---|
| 1 | Shuffled order, state, including dev query 873 | `live.py --shuffle N`; `livecmp.py` compares by query number. Exists, not run |
| 2 | Fork per query | Not built. `live.py --only Q` is one query in a fresh process, but it costs an import per query. A fork after import is the way |
| 3 | Same query twice in one process | Not built: `order` in `live.py main` |
| 4 | Hash seeds 0, 1, 2 | `run_live.sh` sources `env.sh`, which sets the seed to 0. Needs a seed argument |
| 5 | `test_history.py`, harness presets, random order | Plugin above; presets at `harness/state.py:153`, flags at `harness/__main__.py:111-137` |
| 6 | Sessions created and dropped; no `static` | `backend_created`, `backend_dropped` in `--check raw` totals (918 of 918, 3,133 of 3,133). Grep: no `static` item in the crate, only `'static` lifetimes |

## Running the tools
From ~/dev/sa-rust on orion: `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH SA_EVAL_DATA PYTHONHASHSEED`.
- `sh rust-spike/slice/build_solver.sh`: build `sa_solver.so`. It's git-ignored; rebuild after any crate change.
- `sh rust-spike/slice/run_live.sh WORK`: 11 minutes in the background on orion, 5 processes at a time. Writes `summary.txt` last, and each run's `.jsonl`, `.tot` and `.err`. Every comparison must read MATCH.
- `$PY rust-spike/slice/mutate_live.py WORK REF --jobs 6 --timeout 1500`: 17 minutes. REF is a `run_live.sh` WORK. The unmutated row must read "no".
- `$PY rust-spike/slice/mutate_slice.py WORK --sessions 1500 --step1 300 --seed 1 --jobs 4 --timeout 600 --triage 120 --shrink 60`: 3 minutes.
- First difference: `live.py WL MODE OUT --only Q --detail Q:FILE` on both backends gives one JSON line per event, with the whole dump after each solver call; `state.diff` names the field. It ran identically on both backends on dev query 1914 (1,118 events). If `--only` doesn't reproduce a difference, drop `--only`: `--detail` works in a whole pass.

## File:line map for step 4 (lines at this head)
- `rust-spike/slice/backend.py:25` `make`, `:34` `install`.
- `rust-spike/slice/live.py`: `:84` `Stream`, `:132` `_entry` (solver calls and the re-entry count), `:174` `wrap_hooks`, `:185` `_hook`, `:237` `main`, `:274` plain, `:277` raw.
- `rust-spike/slice/mutate_live.py`: `CHECKS` at the top, `compare`, `score`, `main`. `mutate_slice.py:28` `M`.
- Boundary mutant sites in `solver_rs/src/lib.rs`: `:37` `run`, `:74` `conflict_of`, `:89` `PyProps`, `:138` `impl Theory for PyTheory`, `:148` `assert_lit`, `:154` `check`, `:180` `propagate`, `:189` `decide`.
- `solver_rs/src/solver.rs`: `:1441` `theory_sync`, `:1601` `theory_check`, `:1858` `search`, `:1926` `solve_int`, `:372` `bump_clause`, `:926` `_mention` pending, `:1552` theory unit reason, `:2041` `_fill` growth, `:2102` ring clause.
- Tests: `tests/conftest.py`, `pyproject.toml:44` pytest config, `tests/test_history.py:107` module state inventory, `:193` `_plant`, `:314` `:327` `:339` profiles, `:410` CI profiles at both levels. `harness/invariants.py:51` imports `Solver`. `tests/real_theory_fuzz.py:19`, `tests/test_solver_real_theories.py:16` drive real theories directly.
- Engine solver sites: `satassume/engine.py:92,311`, `satassume/ref.py:80,217`; `engine.py:2227,2235` `release`.
