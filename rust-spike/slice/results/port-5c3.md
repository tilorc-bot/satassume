# Step 5c3: Session's queries in Rust (issue 323)

## What moved
`Session.query_lit`, `prepare_query`, `emit` (engine.py:506-544), `query_literal`, `_query_all` (:852-935), `literal_of`, `_relations`, `_ensure_atoms` and `_ensure_twins` (:1155-1220) run in `solver_rs/src/query.rs` (388 lines). They're wrapped by `session_live.py` `_install_queries`, and `SLICE_QUERY=py` keeps Python's. Session and solver methods are called by name. Counters: `ses:query_lit` .. `ses:ensure_twins` (session.rs NAMES).

No module newly counts whole: relations.py at 5c5, Session at 5c6, engine.py at 5c10. **Formula callbacks:** query.rs reads `.pred`/`.expr` and calls `atoms_of`/`formula_literal`/`basis_lits`/`_glue_of` back. These stay counted callbacks, and the boundary conversion stays with the formula step after 5c.

## SHAs
Tested f308ebc: port/5c3 rebased on 5c2's tested source 26460b5, which sits on 6e. Rows are on pareto1 at `~/sp19/sa-rust-ids-work/sa-port-109/bar-5c3/` (`sum.txt`, `commands.txt`), `.so` sha256 6cc1141f…, base 5c2's suite rows (`sa-port-109/bar-5c2/suite`).

The landing source is port/5c3 rebased on rust-slice 1313445 (5c2's landing). The incoming diff, 26460b5..1313445, is `results/port-5c2.md` and `results/port-5c2a.md` only: docs, not executed by any run. So by the rebase rule there was no rerun; it was rebuilt and checked on orion.

sa-port-108's earlier bar (tested 3ffccb1, before 6e, base sa-port-99) gave the same plant table and suite numbers.

## The bar (sa-port-109/bar-5c3)
1. **Suite by id against 5c2's rows:** 5,958 passed, 126 failed, 23 skipped, 18 xfailed, 6,125 ids. New 0, gone 0, changed outcome 0. Passed: 5,957 with no firing, 1 with a firing (`test_ci_stream_reports_only_what_replays`). S's standing: its gate is met except for the 46 named stub failures, one cause. `test_equality_sharing_is_needed_and_works` stays failing and unedited.
2. **Fresh dev, fuzz and loop:** answers and state MATCH. Dev and fuzz each have four comparisons, and loop has Python against Rust; every control MATCHes. Answers: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, loop 09238b2537e54383, unchanged. Rust runs made 0 Python solvers.
3. **Plants:** below. 9 of 12 are caught by a workload, and all 12 by the direct test.
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as base: `_consistent` AttributeError 34 `_ok` + 4 `_rb_clauses` (named needs-internals case), and `Engine._build_context` "Already mutably borrowed" 1 in `test_protocol_on_fuzz` (the 46-stub cause). `caught` rows per id are the same as base. **Quiet catches at engine.py:1906: 1**, in the suite, as on base. 0 on dev, fuzz and loop: the 13 handler files have 0 rows, and so do the 24 dev/fuzz plant files and the loop plant files. TermFault 0.
5. **Known differences in answers or read state:** none. Tests: 473 passed (the 5c TESTS, `test_query_core.py`, 6e's three); `relations_direct.py` exit 0.

## Plants (fired; D = DIFFER)
| plant | method | dev | fuzz | loop | caught by |
|---|---|--:|--:|--:|---|
| query-lit-tuple | query_lit | 31 D | 0 | 0 | dev, direct |
| drop-prep-twins | prepare_query | 734 | 693 | 244 | **direct only** |
| drop-prep-rel | prepare_query | 153 D | 674 D | 0 | dev, fuzz, direct |
| drop-emit | emit | 3,045 D | 16,866 D | 560 D | dev, fuzz, loop, direct |
| drop-ql-mention | query_literal | 1,051 D | 6,937 D | 475 D | dev, fuzz, loop, direct |
| ql-skip-consistent | query_literal | 212 D | 82 D | 14 D | dev, fuzz, loop, direct |
| drop-qa-mention | _query_all | 706 D | 1,038 D | 556 D | dev, fuzz, loop, direct |
| drop-lo-memo | literal_of | 44 | 1,957 | 0 | **direct only** |
| drop-lo-discover | literal_of | 44 | 1,957 | 0 | **direct only** |
| drop-rel-process | _relations | 393 D | 5,762 D | 0 | dev, fuzz, direct |
| drop-ea-ensure | _ensure_atoms | 1,325 D | 4,868 D | 316 D | dev, fuzz, loop, direct |
| drop-twins-var | _ensure_twins | 0 | 0 | 0 | **direct only** (suite: fired 2,381, 0 changed) |

**Void (fired 0, so the MATCH means nothing):**
- drop-twins-var on all three workloads. It needs a zero twin, which takes an `AppliedUndef` such as `f(x - y)` (`relations._under_apps`).
- query-lit-tuple on fuzz and loop.
- drop-prep-rel, drop-lo-memo, drop-lo-discover and drop-rel-process on loop.

**Fired but not caught by any workload:** drop-prep-twins, drop-lo-memo and drop-lo-discover. On dev, fuzz and loop they fire without changing answers or state.

`test_query_core.py` catches all four "direct only" plants. Its 13 cases on forged state, Python against Rust in separate processes, include an `AppliedUndef` for zero twins and a forged aux `d` with `[-d, q]` so that `mention` changes an answer (solver.py:1243). All match Python, and each of the 12 plants fires and moves a case (`test_each_plant_fires_and_is_seen`). The suite was run with drop-twins-var only (SUITE_PLANTS=zero); it fired there and changed no outcome.

## Reached (ses: counters; dev / fuzz / loop / suite)
| method | dev | fuzz | loop | suite |
|---|--:|--:|--:|--:|
| query_lit | 839 | 867 | 384 | 229,742 |
| prepare_query | 776 | 2,605 | 244 | 32,542 |
| emit | 3,045 | 16,638 | 560 | 3,308,554 |
| query_literal | 1,673 | 7,974 | 1,024 | 549,892 |
| _query_all | 667 | 1,037 | 552 | 177,940 |
| literal_of | 44 | 1,957 | 0 | 24,712 |
| _relations | 393 | 5,564 | 0 | 52,562 |
| _ensure_atoms | 877 | 4,909 | 244 | 61,329 |
| _ensure_twins | 1,611 | 5,602 | 488 | 69,442 |

All 9 are reached on both dev and fuzz, so no new workload was needed. The direct test reaches all 9 too.

## Patches
By rg, no test in `tests/` patches a moved method. The offline tools-rust/coarse.py:133 sets `Session.prepare_query` at class level. It's offline and not ported.

## Not run
Moved to "before any backend PR", none quoted as met:
- the mutant 2, 5, 6, 7, 9 rerun and mutlive's control;
- the boundary rescore and suite column;
- the final drop score and its lost rows;
- the suite split with Python's counter;
- `order:_rows`' evidence (not caught meanwhile);
- the `_forms` guard test;
- history and seed reruns (seed1 not run);
- forced moves;
- the native path;
- timing.

Also not run: the suite under drop-prep-twins, drop-lo-memo and drop-lo-discover. They fired on dev and fuzz, so `zero` left them out.

Other notes:
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- The public-API `test_incremental_matches_fresh` family is still owed: a test-only step before 5c7 (pure Python first, adds only, a Python failure is a finding against main).
- `test_equality_sharing_is_needed_and_works` gets re-pointed at 5c4, through `_share` (a `skip-share` plant plus a test in test_relations_core.py; the Python test stays unedited). 5c3 doesn't touch `_share`.
