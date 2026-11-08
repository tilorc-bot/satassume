# Step 6g(a): the registry's per-node dispatch, `_applied_to_nan` and atoms' no-query path on Rust (issue 323)

Tested source **e5c78e9** (port/6g rebased on rust-slice 2ee0c8c, 5c5's landing; rows pareto1
`~/sp19/sa-rust-ids-work/sa-port-123/`, sum.txt, .so 279dda0b). Base suite rows: 5c5's (`sa-port-122/bar-5c5/suite`).
Earlier bar on 7113e58 over 7e2ece0 (`sa-port-121/`) had the same suite and MATCH results; two runs on f91e99d and 4ff6c22
were stopped for code changes and for 5c5's landing (executed code: relations_core.rs, session.rs, session_live.py).

**Code.** `term/dispatch.rs` (`Dispatch`): `clauses_for` (registry.py:226), the class walk of `templates_for` (:194, MRO,
`_redefines` :62, lazy `_load` :141 called back and counted, import-time by ruling), `_split` (:265),
`_applied_to_nan`/`_may_be_nan` (templates/__init__.py:142-172), and `templates_for` for conversion's class rows
(convert.py:247 via `convert.TEMPLATES_FOR`). `knowledge_live.install_dispatch()` binds `registry.clauses_for`, so
`Engine.__init__` takes Rust's bound method; with lra on, 5c5's Rust `with_closed_units` wraps it. Atoms with no query on
the stack (`Engine` used directly) are read as derived nodes on Rust (`<kind>:no-query`, was `py:no-query`). Templates are
still called back by name per node, each counted `registry:python:<qualname>`, until 6g(b)/(c).

**Module count (count rule): 9 of 32**, was 7: registry.py and templates/__init__.py now count whole. Call trace
(sys.setprofile over both files after 50 warm queries, on the core, opaque, f6, value and rootof workloads): `clauses_for`,
`templates_for`, `_split`, `_applied_to_nan` 0 calls (`templates_for` was 21k-67k per workload through convert.py:247 before
e5c78e9). Still run: `_load`/`_covers`/`register` (lazy loading of a template module, import-time by the count rule) and
`_may_be_nan` from convert.py:300 (conversion, its only runtime reader). Named exceptions: a class with a user template or
a non-default registry goes whole to Python's `TemplateRegistry.clauses_for` (`registry:python:user`, ruled); `facts_for`
runs only on the non-default path. Footnote kept: realroots and `value_units` are wired, and neither dev nor fuzz reaches
them (6f's workloads do).

**The parts ruling's three conditions**
1. User registrations: `register` stays Python. dispatch_direct.py registers a user template and checks the user path is
   taken (`registry:python:user` 3) with Python's answer; plant `dispatch-user-off` is caught there (BAD 1). Void on the
   suite (no outcome changes) and on every workload (fired 0): workloads don't register.
2. Epoch: `sync_epoch` empties memo and class cache when `EPOCH[0]` moves, for `clauses_for` and `templates_for`.
   dispatch_direct registers a template after a query and re-asks: matches Python. Plant `dispatch-ignores-epoch`: caught by
   dispatch_direct (BAD 3) and by the suite (6 outcomes, test_registry_versioning x2, test_templates, test_total_templates,
   test_totality x2); 0 fired on dev, fuzz and the five workloads.
3. Same lookup: the class walk is Python's (MRO, `_redefines`/own facts), with classes keyed under `==` as `_mro_cache`
   (the ordering_of_classes case, `Function('f')` across `clear_cache()`, is in dispatch_direct). Plant
   `dispatch-redefines-off`: caught by dispatch_direct (BAD 2) and the suite (test_s10_override::test_reproducers); fires 1
   on f6 and value with answers unchanged.

**Bar** (on e5c78e9)
1. Suite by id against 5c5's rows: 5,958 passed / 126 failed / 23 skipped / 18 xfailed, 6,125 ids; new 0, gone 0, changed
   0. Passed with no firing 5,957, with a firing 1 (`test_ci_stream_reports_only_what_replays`). S's standing: S's gate is
   met except for the 46 named stub failures, one cause. 419 step tests pass; dispatch_direct exit 0 (27 nodes, 6 opaque).
2. Dev (1,985) and fuzz (3,000): answers and end state MATCH, py vs rust, traced vs untraced, Python control. Workloads,
   whole engine Python against Rust: f6, value, rootof, core and **opaque** (new, 2,546 queries) MATCH. lra-on path:
   dev, fuzz and the workloads run lra on, so `clause_templates` is 5c5's Rust `with_closed_units` over Rust's dispatch;
   all MATCH, and 5c5's plant `with-closed-skip` fires and is caught (DIFFER) on dev 231, fuzz 326, core 134, f6 510,
   opaque 27.
3. Plants: `dispatch-opaque-off` fires 274 on the opaque workload, caught (DIFFER; 0 elsewhere).
   `knowledge-no-query-drop` is void on the workloads (they always have a query), caught by the suite (146 failed against
   126) and by test_knowledge_value_units.py::test_no_query_plant_is_caught. The other three as in 1-3 above;
   `knowledge-value-multigamma-drop` control fires 10 on value, DIFFER. The suite's plant counter reads 0 for these plants
   (they count in knowledge COUNTS, not the suite's counter); the changed outcomes show they ran.
4. Quiet handlers (suite): 39 rows in 2 tests, multiset same as base (34 `_ok` + 4 `_rb_clauses` in `_consistent`;
   1 "Already mutably borrowed" at `_build_context`, the 46-stub cause). TermFault 0. 0 handler rows on dev, fuzz and the
   workloads.
5. Differences: none in answers, state or suite outcomes.

**Reached:** dispatch (`registry:rust`) on every workload; opaque only by the opaque workload (220) and dispatch_direct;
epoch and user path by the suite and dispatch_direct only (an ask stream doesn't register); no-query by the suite
(core:no-query 38,060, symbol 721, constant 217, value 14).

**Kept on Python with reason:** `_rows_runtime`'s I/-I values (read once per process when Pow's generator is built, not
per query; I is algebraic and rows' constants are independent generators, so not exact without a reduction step) and
Floats (SymPy's precision semantics, the planner's default). Queries under a non-default registry; `enclose`.

**Owed before any backend PR (unchanged from port-6f.md):** `scaffold:rebuilt:f6` and `scaffold:mismatch` until 0; the
NotImplementedError and hook re-entry contract notes; the items in OWED-satassume-rust.md. `_n_conflicts` in rust_plugin.py
is a test-plugin shim (64 tests), not a port.

**Not run:** seed1, history, forced moves, the native path, timing; the mutant 2/5/6/7/9 rerun, the boundary rescore and
suite column, order:_rows evidence (not caught meanwhile), the `_forms` guard test; dispatch-opaque-off on the suite.
No evaluator asked for.
