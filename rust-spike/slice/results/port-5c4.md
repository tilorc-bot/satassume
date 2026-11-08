# Step 5c4: the rest of `Relations` in Rust (issue 323)

## What moved
`Relations.__init__`, `enqueue`, `note_formula`, `process`, `_link_later`, `wants_transfer` and `_share` (relations.py:777-979, 1516-1598) now run in `solver_rs/src/relations_core.rs` ("step 5c4"). `session_live.py` wires them through `_REL_METHODS`, and `SLICE_REL=py` keeps Python's versions. The instance's containers stay Python's. Other methods are called by name, so patches on them are honoured. sa-port-115 read 5509fba against the Python lines and found no difference. Counters: `rel:init` .. `rel:share`. Counted callbacks: `rel:cb_note_sides`, `cb_eq_links`, `cb_atom_selector` and `cb_atom_var`, plus 5c5's `cb_constant_term`.

**relations.py doesn't count whole.** 31 of `Relations`' 36 methods run in Rust. Five stay on Python and are called back: `_note_sides`, `_eq_links`, `_atom_selector` and `_atom_var` (counted, `rel:cb_*`), and `_adapter`, which C2b's `_interpret`/`_link` call. port-ownership.md:76-77 gives these five to 5c4 as "called back", so they're still owed. Recommendation: 5c5, which owns relations.py's module functions, takes them too, so relations.py can count whole there. Session counts whole at 5c6 and engine.py at 5c10.

## SHAs
Tested **b8dda68**: port/5c4 on rust-slice d14628d (5c3's landing). Rows are on pareto1 at `~/sp19/sa-rust-ids-work/sa-port-115/bar-5c4/` (`sum.txt`, `commands.txt`). The `.so`'s sha256 is 0648c290…, and the base is 5c3's suite rows (`sa-port-109/bar-5c3/suite`). The landing source is the commit carrying this file. Between it and b8dda68 are only HANDOFF-sa-port-115.md and this report: docs, which no run executes. rust-slice hadn't moved when this was written. If it moves before the push, `bar.sh land` prints the incoming diff and the rebase rule applies.

## The bar (sa-port-115/bar-5c4)
1. **Suite by id against 5c3's rows:** 5,958 passed, 126 failed, 23 skipped, 18 xfailed, 6,125 ids. New 0, gone 0, changed outcome 0. Passed: 5,957 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`). S's standing: S's gate is met except for the 46 named stub failures, one cause. `suite_report.py` against `pr328-check/suite-python` splits the 126 into 78 needs internals, 46 re-entry and 2 kept-on-Python. The two kept-on-Python are `test_split_beyond_the_certificate_bound_counts_as_exhausted` (port-1b.md) and `test_comparison_detects_a_wrong_row` (port-6e.md), both the same on base. `test_performance_smoke_300_vars` passed on Rust on pareto1. It's listed as failed in those Python rows from orion.
2. **Fresh dev, fuzz and loop:** answers and state MATCH. Dev and fuzz each have four comparisons, and loop has Python against Rust. Every control MATCHes. Answers are unchanged: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, loop 09238b2537e54383. Rust runs made 0 Python solvers.
3. **Plants:** see the table below. All 7 are caught on dev and fuzz, and all 7 by the direct test.
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as base:
   - `_consistent` AttributeError: 34 on `_ok` and 4 on `_rb_clauses` (the named needs-internals case);
   - `Engine._build_context` "Already mutably borrowed": 1, in `test_protocol_on_fuzz` (the 46-stub cause).

   `caught` rows per id match base. **Quiet catches at engine.py:1906: 1**, in the suite, as on base. There are 0 on dev, fuzz and loop: the 13 handler files have 0 rows, and so do the 14 dev/fuzz plant files and the loop plant files. TermFault 0.
5. **Known differences in answers or read state:** none. Tests: 482 passed (5c3's ten files, with the re-pointed sharing tests), and `relations_direct.py` exited 0.

## Plants (fired; D = DIFFER)
| plant | method | dev | fuzz | loop | caught by |
|---|---|--:|--:|--:|---|
| drop-init-engage | __init__ | 35 D | 911 D | 0 | dev, fuzz, direct |
| drop-enqueue | enqueue | 1,187 D | 21,333 D | 0 | dev, fuzz, direct |
| drop-note-top | note_formula | 458 D | 5,463 D | 0 | dev, fuzz, direct |
| drop-proc-eq-links | process | 35 D | 890 D | 0 | dev, fuzz, direct |
| drop-link-later | _link_later | 375 D | 9,421 D | 0 | dev, fuzz, direct |
| wants-never | wants_transfer | 355 D | 6,230 D | 0 | dev, fuzz, direct |
| drop-share | _share | 506 D | 8,009 D | 0 | dev, fuzz, direct |

**Void (fired 0, so the MATCH means nothing):** all 7 on loop, which reaches no `Relations` method (`rel:*` 0). Dev and fuzz catch each one. The suite wasn't run under a plant: `SUITE_PLANTS=zero` picks plants that fired 0 on both dev and fuzz, and none did. `test_relations_core.py` `test_dropped_clause_is_seen` has each of the 7 fire and move a case.

## Reached (rel: counters; dev / fuzz / loop / suite)
| method | dev | fuzz | loop | suite |
|---|--:|--:|--:|--:|
| __init__ | 198 | 3,018 | 0 | 27,657 |
| enqueue | 1,501 | 36,397 | 0 | 349,424 |
| note_formula | 393 | 5,564 | 0 | 52,629 |
| process | 393 | 5,564 | 0 | 52,628 |
| _link_later | 914 | 17,762 | 0 | 154,866 |
| wants_transfer | 352 | 6,088 | 0 | 40,265 |
| _share | 506 | 8,009 | 0 | 68,070 |
| callbacks: _note_sides / _eq_links / _atom_selector / _atom_var | 38 / 35 / 35 / 138 | 888 / 888 / 888 / 2,445 | 0 | 34,510 / 32,758 / 32,758 / 63,667 |

All 7 are reached on both dev and fuzz, so no new workload was needed.

## The re-pointing of `test_equality_sharing_is_needed_and_works`
Only the way the clause is turned off changes. `test_relations_core.py::test_sharing_is_needed_and_works` keeps the suite test's two assertions on dummy specs (on: True, off: None). It turns the clause off with `skip-share` on Rust and the suite test's own patches on Python. It also adds the real-specs case: True with `_trichotomy` off, and None with both off. Python, Rust and `SLICE_REL=py` give the same answers.

`test_sharing_case_fails_without_sharing` removes sharing from the start and gets None on both backends: Python by a `_share` patch, Rust by the test-only plant `drop-share-tri` (drop-share plus trichotomy off, since only one plant is on at a time).

`tests/test_relations.py` is unedited. On Rust it still fails, with the **named needs-internals status**: `suite_report.py` `PATCHED` reads "patch on moved _share/_trichotomy; replaced by test_relations_core.py::test_sharing_is_needed_and_works", and the run above shows it under that reason (test_relations: 1). rust_plugin.py has no such list, so `PATCHED` is where the status lives.

## The four fired-but-uncaught 5c3 plants, classified
None of these is on 5c4's bar. They were classified by reading and by Python probes.
- **drop-prep-twins: unreached in a way that matters.** It fires on the guard (dev 734, fuzz 693, loop 244), but no workload enters the branch that allocates twins: drop-twins-var, inside it, fires 0 on all three. A workload is owed: a query whose glue has a zero twin (zero(n) with n under an AppliedUndef). test_query_core.py catches the plant on forged state.
- **drop-twins-var: redundant, on the first reading.** The probe (6 queries with zero twins) gives the same answers with `var(atom)` skipped. At `Relations.process` the twin is already allocated in all calls but one, because eq(t, 0) is also t's link atom (`_link`). The direct test catches it on state: test_query_core.py `ensure_twins:*`, Python against Rust. It's a Python removal candidate, to check with a Python suite run, since the one unallocated call depends on order.
- **drop-lo-memo: speed-only.** `formula_literal` re-derives the same literal through `table.var`/`dvar`, so no state moves. A replacement wrong-value plant (another key's entry) is owed and not written.
- **drop-lo-discover: redundant on dev and fuzz.** On dev, all 44 skips are followed in the same `literal_of` by `Relations.process`, whose loop starts with `discover()`. On fuzz, all 1,957 skips are. With relations None the discover is needed, and no workload reaches that case. It's a Python removal candidate.

## Owed-list additions
- drop-twins-var and drop-lo-discover: Python removal candidates, each to check with Python's own runs.
- drop-lo-memo: a wrong-value plant (stale or other-key entry) that a workload catches.
- drop-prep-twins: a workload with a zero twin under an AppliedUndef.
- `Relations._note_sides`, `_eq_links`, `_atom_selector`, `_atom_var` and `_adapter` are still called back (port-ownership.md:76-77). Recommended for 5c5.
- Already listed and unchanged: the real-EUF sharing case for tests/test_relations.py, a held Python PR candidate.

## Not run
Moved to "before any backend PR", and none quoted as met:
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

Also not run: the suite under any of the 7 plants (`zero` selected none).

Other notes:
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- The public-API `test_incremental_matches_fresh` family is still owed: a test-only step before 5c7 (pure Python first, adds only, and a Python failure is a finding against main).
