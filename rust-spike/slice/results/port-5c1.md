# Step 5c1: Session's discovery in Rust (issue 323)

## What moved
`Session.ensure`, `discover`, `_discover`, `incomplete` and `escalate` (engine.py:772-850, 73 lines) run in `solver_rs/src/discovery.rs` over the session's own Python containers, wrapped by `session_live.py` `_DISC_METHODS`; `SLICE_DISC=py` keeps Python's. Callbacks to Python: `_flush`, `_compile`, `_emit_pattern`, `_compile_pending` and `Session._visit` (by `core.visit`); those are 5c2. No module newly counts whole (relations.py at 5c5, Session at 5c6, engine.py at 5c10).

## SHAs
Tested 7fc958d (suite, live, plants, suite plants; pareto1, `.so` sha256 d4694666…). eb90992 adds only `test_discovery_core.py`, which neither the suite nor live imports; it passed on orion at eb90992 (10 passed). Landed: the rebase on rust-slice de8bd3a brought no incoming diff. Rows: pareto1 `~/sp19/sa-rust-ids-work/sa-port-96/` (`sum.txt`, `commands.txt`), by `rust-spike/slice/p1/bar.sh`, its first full run; it ran every phase without a fix. Not run: `seed1` (SEED1 unset).

## The bar
1. **Suite by id against sa-port-91's rows (rust-slice de8bd3a):** 5,959 passed, 125 failed, 23 skipped, 18 xfailed, 6,125 ids. New 0, gone 0, changed outcome 0. Passed: 5,958 with no firing, 1 with a firing (`test_ci_stream_reports_only_what_replays`). S's standing: its gate is met except for the 46 named stub failures, one cause. `test_equality_sharing_is_needed_and_works` stays failing and unedited.
2. **Fresh dev and fuzz:** answers and state MATCH, four comparisons each, control MATCH. Answers' shas unchanged: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6; 0 Python solvers made on Rust.
3. **Plants:** below; each moved method has a plant some workload, the suite or the direct test catches.
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as base: `_consistent` AttributeError 34 `_ok` + 4 `_rb_clauses` in `test_ci_stream_reports_only_what_replays` (named needs-internals case), `Engine._build_context` "Already mutably borrowed" 1 in `test_protocol_on_fuzz` (the 46-stub cause). `caught` rows per id same as base. **Quiet catches at engine.py:1906: 1** (`complete_check`, in the suite, as on base); 0 on dev and fuzz (handler files 0 rows, 12 files; 16 plant files 0 rows). TermFault 0.
5. **Known differences in answers or read state:** none. `Session.base` under Rust has no `__iter__` (read by key and length only); nothing in the tree iterates it (unchanged from 5a).

## Plants (fired on dev / fuzz; caught by)
| plant | method | dev | fuzz | caught by |
|---|---|--:|--:|---|
| drop-ensure-demand | ensure | 5,222 DIFFER | 84,724 DIFFER | dev, fuzz, direct |
| drop-discover-flush | discover | 1,582 DIFFER | 15,972 DIFFER | dev, fuzz, direct |
| drop-discover-visit | _discover | 0 | 0 | suite (38 changed outcomes), direct |
| incomplete-never | incomplete | 714 DIFFER | 4,636 DIFFER | dev, fuzz, direct |
| drop-esc-pattern | escalate | 856 DIFFER | 10,620 DIFFER | dev, fuzz, direct |
| drop-esc-deferred | escalate | 99 DIFFER | 0 | dev, direct |
| drop-esc-compile | escalate | 0 | 0 | suite (3 changed outcomes), direct |
| truncated-never | escalate | 0 | 0 | direct only (suite: fired, no change) |

**Void on the workloads (fired 0, so their MATCH means nothing):** drop-discover-visit, drop-esc-compile, truncated-never on both; drop-esc-deferred on fuzz. The engine passes `escalate` no budget, so `truncated` can't be set from a query (test_budget_cone.py:88 says the same). `drop-discover-flush` MATCHed on dev's first 200 queries (sa-port-93), but DIFFERs on the full workloads. On full dev and fuzz, `discover`'s `_flush` never meets a new node; it meets new custom atoms in 676 of 3,259 dev calls and 16,750 of 58,720 fuzz calls (Python probe on orion), and dropping those is what's caught.

## Direct test
`test_discovery_core.py`: 63 cases on forged state, Python against Rust in separate processes, recording returns, every `add_clause` and `add_internal`, `base`, `frontier`, `deferred`, `pending`, `pending_c`, `demand`, `truncated`, `incomplete` and the solver digest per step. New nodes are compiled straight into the table for `_flush`, a vocabulary function registered for `Add` parks formulas in `pending`, `log`/`gamma`/`x**y` fill `deferred`, and `escalate` runs at budgets 0-12, 20, 40, None. All 63 match; each of the 8 plants fires and moves 3-43 cases.

## Patches
By rg, no test in `tests/` patches a moved method.

## Not run
Moved to "before any backend PR", none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control, the boundary rescore and suite column, the final drop score and its lost rows, the suite split with Python's counter, `order:_rows`' evidence (not caught meanwhile), the `_forms` guard test, history and seed reruns (seed1 not run), forced moves, the native path, timing.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- **Speed not measured.**
- The public-API `test_incremental_matches_fresh` family is still owed: planner's go is a test-only step before 5c7 (pure Python first, adds only, a Python failure is a finding against main).
- Fuzz history for PR 328 and the censuses on the base stay open; section 8's limits still stand.
- The `_n_conflicts` view in `rust_plugin.py` isn't a port: a test-plugin shim, with the 64 tests it moved.
- `test_performance_smoke_300_vars`: no changed outcome on pareto1.
- No evaluator asked for.
