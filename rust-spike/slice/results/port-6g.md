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

# Step 6g(b): wiring's rows families on Rust (issue 323)

Tested source **7e730df** (port/6g rebased on rust-slice 4dd2ed9, adapters B+C1's landing; rows pareto1
`~/sp19/sa-rust-ids-work/sa-port-145/`, sum.txt, .so 8fb500cf). Base suite rows: adapters' (`sa-port-140/bar-BC2/suite`).
Two rebases: onto bb3df19 (5c7-tests: live.py, zero_wl.py, a suite test; one conflict in live.py's workload tuple, both
kept) and onto 4dd2ed9 (adapters: Rust source, live paths, bar.sh), so the bar ran whole on the merged tree. The landing
rebase brought only docs (HANDOFF-sa-port-149.md, results/port-adapters.md, port-ownership.md/.tsv).

**Code.** `term/rows_tpl.rs` (`RowsTpl`, from Dispatch's class entry, `registry:rust:<name>`): wiring.py's `any_arity`
(Max, Min, Piecewise through `piecewise_values`, `leave_out_wide`'s `_clauses`), `product` (Mul), `addition` (Add, with
`_imag_templates`), `power` (`pow_call`/`pow_build`), `rows_block`, `rules_for`, `matches`, `expand`/`_placements`/
`_allowed`/`_instances`, `wide_formulas`. Called back by name and counted `rows:python:<name>` (`wiring_fn`): the core
functions (`_half_split`, `_bound_split`, `_recip_templates`, `_imag_split`, `_imag_templates`, `_mul_factor_sets`,
`_quotient_templates`, `_exp_arg`, `ipi_split`, `_unit_angle`, `ipi_rules`, `irrational_root`, `_unit_power_units`,
`_pow_bound_templates`), `constant_value`, `const_value` (named callback); scaffolding `rows:python:Mul`/`Add`/`Integer`.
Hidden-gap workload `knowledge_wiring_wl.py` (`live.py wiring`, 6,512 queries): dev, fuzz and the other workloads have no
Max/Min/Piecewise node and no node of more than 32 arguments.

**Module count (count rule): 12 of 32, unchanged.** wiring.py doesn't count yet. Call trace on 7e730df
(registry_count.py --trace wiring.py,core.py,functions.py, pass 1; `~/sa-rust-ids-work/sa-port-145/trace/` on orion):
wiring.py's own code per query on dev (1,985 queries): `_attributed.<locals>.template` (wiring.py:189) 6 and the `_unary`
slot lambdas (:147-148, called from functions.py) 31 + 33; f6: 24, 134, 167. On the wiring workload, none of wiring.py's
code runs per query: its rows run on Rust. core.py still runs per query through knowledge_core_live's shells
(`_half_split`, `_bound_split`, `_imag_split`, `irrational_root`, `_unit_power_units`) and engine-called templates
(`_half_templates`, `_bound_templates`, `ipi_split`); functions.py's templates (`_unary`, `_pi_trig`, `_exp_ipi`,
`_cosh_shift`, `nary`, `parts_of_round_templates`) per query. All three are 6g(c)'s. registry_count showed "5 raised" on
core and "2 raised" on f6 in both passes; same on 493cefc's code (sa-port-144); not looked into.

**Plants** (each run on dev, fuzz and the 9 workloads against this run's Python; fired / caught on):

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
| rows-block-key-n (odd n keyed as n-1) | dev 85, fuzz 1151, core 116, f6 689, loop 63, wiring 435, zero 15 | |
| rows-rules-for-shape | dev 143, fuzz 15, core 150, f6 170, loop 35, opaque 3, rootof 29, value 29, wiring 111, zero 3 | |
| rows-of-constant-skip | dev 15, core 25, f6 24, wiring 13 | fuzz 6, loop 3, others 1-2 |
| rows-matches-constant | dev 37, core 186, loop 29, wiring 148 | f6 8, opaque 8 |
| rows-matches-coefficient (new) | dev 104, core 78, f6 104, loop 26, rootof 26, value 26, wiring 78 | |
| rows-expand-drop-last | dev 38, fuzz 28, core 88, f6 50, loop 10, rootof 1, value 150, wiring 60, zero 7 | opaque 5 |
| rows-placements-first | every workload (dev 722 ... value 2404, wiring 555) | |
| rows-instances-others | every workload but scope (dev 50 ... wiring 31) | |
| rows-count-flip | dev 256, fuzz 136, core 660, f6 380, loop 60, rootof 8, value 604, wiring 224, zero 36 | opaque 24 |
| rows-clauses-concl-only (new) | wiring 1792 (end state and stream, 1,246 queries; answers same) | |
| rows-wide-drop | wiring 6 | |
| rows-piecewise-last | wiring 1 | |
| rows-mul-sets-first | dev 17, core 133, f6 56, loop 2, wiring 9 | |
| rows-add-bound-skip | dev 31, fuzz 45, core 120, f6 10, loop 4, opaque 8, wiring 6, zero 1 | |
| rows-pow-key-same | wiring 1 | core 2 |
| rows-pow-times-skip | dev 3, core 96, loop 3, wiring 12 | |
| rows-pow-irrational-skip | core 16, wiring 2 | |
| rows-pow-ipi-skip | core 14, wiring 3 | |
| rows-pow-unit-drop | core 33, wiring 3 | |
| rows-pow-of-constant-skip | dev 16, core 312, loop 8, opaque 4, wiring 62 | f6 4 |
| common-wide-drop (6d) | wiring 3 | |
| rows-pow-head-any | **void**: 0 everywhere | |

- Replaced in 7e730df because they could not catch anything: `rows-block-key-n` keyed every node with n + 1, a uniform
  shift (no two keys could meet); `rows-allowed-coefficient` planted `_allowed`'s 'coefficient' pick, which no compiled
  row has (all 26 'coefficient' items are shapes), replaced by `rows-matches-coefficient`; `rows-clauses-one` dropped
  conclusions from `_clauses`: a conclusion has at most 2 clauses and a static check over Max/Min/Piecewise rules of 1-32
  arguments (no constant, and 2, -1, 0 at each position) found no decision at MAX_EXPAND that moves, replaced by
  `rows-clauses-concl-only`.
- `rows-pow-head-any` is void by construction: a power rule with shape ('head', 'exp') also names the inner term
  (`terms_of`), which exists only when the base is `exp`, so the head check is always met where it is reached
  (wiring.py's own check is redundant in the same way; a Python removal candidate, not a port item).
- 6d's `common-equiv-one` and `common-ge2-drop` fire 0 on all 11 runs: `Rules.equiv` and `ge2_alternatives` have no
  runtime caller on Rust's path (rows_tpl.rs calls neither; table.py's only runtime caller is core.ipi_rules, which on
  Rust is `sa_solver.core_ipi_rules`). By the planner's ruling they are Python removal candidates, not port items; their
  code keeps the "unreached by any workload; common_direct.py only" footnote. `common-wide-drop` is now caught on wiring.
- The parts ruling's three 6g(a) conditions still hold: `dispatch-ignores-epoch` (suite: 9 outcomes changed),
  `dispatch-redefines-off` (suite: 1; fires 1 on f6 and value, MATCH, as in 6g(a)), `dispatch-user-off` (void on the
  suite and workloads as before; caught by `dispatch_direct.py dispatch-user-off` on 7e730df on orion, BAD 1).
  `knowledge-no-query-drop`: suite 20 changed.
- lra-on path (5c5's Rust `with_closed_units` over the dispatch): all runs MATCH with lra on; `with-closed-skip` caught on
  dev 231, fuzz 326, core 134, f6 510, opaque 27, wiring 28.

**Bar** (on 7e730df)
1. Suite by id against adapters' rows: 5,992 passed / 126 failed / 23 skipped / 18 xfailed, 6,159 ids; new 0, gone 0,
   changed 0. Passed with no firing 5,991, with a firing 1 (`test_ci_stream_reports_only_what_replays`). S's standing:
   S's gate is met except for the 46 named stub failures, one cause. 625 step tests pass (18 files); direct scripts:
   relations_direct, dispatch_direct (27 nodes, 6 opaque, BAD 0) and common_direct exit 0, each of 6d's 13
   common_direct plants exit 1.
2. Dev (1,985) and fuzz (3,000): answers and end state MATCH, py vs rust, traced vs untraced, Python control. Workloads
   f6, value, rootof, core, opaque, scope, loop, zero and **wiring** (new, 6,512): MATCH, each with a Python control.
3. Plants: table above; every rows plant but the void one is caught, 15 of them on dev or fuzz too.
4. Quiet handlers (suite): 39 rows in 2 tests, multiset same as base (34 `_ok` + 4 `_rb_clauses` in `_consistent`;
   1 "Already mutably borrowed" at `_build_context`, the 46-stub cause). TermFault 0. 0 handler rows on dev, fuzz and
   the workloads (the plant runs of rows-block-key-n have 1 and 16, its TemplateKeyError).
5. Differences: none in answers, state or suite outcomes.

Kept shares (Rust vs Python, unchanged against base): out-of-scope dev 24/1,985 (1.21%), 0 elsewhere; refused f6 13/2,902,
opaque 7/2,546, value 15/3,742 (Floats), wiring 1/6,512 (lra: a callback on a derived term), 0 elsewhere.

**Reached on Rust, by workload:** Max/Min/Piecewise rows, `rows:wide`, `wide_formulas`, `_clauses`, `piecewise_values`,
`_imag_templates`, `common:wide`: wiring only. product/addition/power rows: dev, core, f6 and wiring.

**Kept on Python with reason:** `_rows_runtime`'s I/-I values (read once per process when Pow's generator is built, not
per query; I is algebraic and rows' constants are independent generators, so not exact without a reduction step) and
Floats (SymPy's precision semantics, the planner's default). Queries under a non-default registry; `enclose`.

**Owed before any backend PR:** `scaffold:rebuilt:f6` and `scaffold:mismatch` until 0, now with `rows:python:Mul`/`Add`/
`Integer` (rows scaffolding); the NotImplementedError and hook re-entry contract notes; the items in
OWED-satassume-rust.md; 6d's pattern-key-type/const-key-type/max-cache-off replacements. `_n_conflicts` in
rust_plugin.py is a test-plugin shim (64 tests), not a port.

**Not run:** seed1, history, forced moves, the native path, timing; the mutant 2/5/6/7/9 rerun, the boundary rescore and
suite column, order:_rows evidence (not caught meanwhile), the `_forms` guard test; the rows plants on the suite.
No evaluator asked for.

# Step 6g(c1): the Add family's core splits straight from the query's table (issue 323)

Tested source **85f4d87** (port/6g on rust-slice 9c8d981, adapters C2's report; rows pareto1
`~/sp19/sa-rust-ids-work/sa-port-157/`, sum.txt, .so fa1fe0f3). Base suite rows: C2b's (`sa-port-153/bar-C2b/suite`).
Landed **53c5b64 + this report** on rust-slice: the landing rebase brought nothing (rust-slice still 9c8d981); tested..landing
adds only HANDOFF-sa-port-157.md and this file, outside the push guard.

**Code.** rows_tpl.rs's Addition family computes `_half_split`, `_bound_split` and `_imag_split` from the query's
TermTable (tcore.rs `core_half_split`/`core_bound_split`/`core_imag_split`; `RowsTpl::split`, `direct_split`, `QIds`;
common.rs `Common::query`), counted `rows:rust:NAME`. It falls back to knowledge_core_live.py's shell, counted
`rows:python:NAME`, wherever the shell does more than read input ids: no query or a kept one, an arg that isn't an input
term of its own class (the shell's `core:derived:NAME`), a derived result id, or a product rest (`kept_product`
scaffolding). The direct path has its own shadow: Rust hands each result to knowledge_core_live `shadow_split` (py_fns
`_shadow_split`), which runs Python's split and compares (`shadow:direct:NAME`). knowledge_core_wl.py gained 64
`I*x + c*I*y` rows (gaps ruling), so the imag split is reached.

**Module count (count rule): 13 of 32, unchanged.** core.py still runs per query (trace orion
`~/sa-rust-ids-work/sa-port-157/rc-core.txt`, `rc-dev.txt`, `rc.sh OUT WL core.py,wiring.py,functions.py`, pass 1):
`_bound_split` from knowledge_core_live 69 on core (the derived-arg fallback), `_bound_templates` from engine 120 on core,
`_half_templates` 86 and `_bound_templates` 10 on dev; functions.py's `_unary` templates on core; wiring.py's
`template.<lambda>` 9 on dev. Counted against STATUS.md's "Counted modules".

**Direct-split counts** (rows:rust / rows:python / the shell's core:derived, half; bound; imag):
dev 45/20/3; 47/18/3; 54/11/3. fuzz 139/34/24 each. core 66/72/69; 69/69/69; 69/69/69. f6 144/32/6; 170/6/6; 170/6/6.
value 172/0/0 each. cert 17/0/0 each. wiring 8/5/4; 9/4/4; 9/4/4. loop 8/6/5 each. opaque 1/7/7 each. zero 10/11/0 each.
rootof, scope 0. rows:python exceeds core:derived by the shell's other fallbacks (no or kept query, derived result,
product rest), which the shell doesn't count as derived.
**Shadow** (test_knowledge_core_shapes, 10/10 on 85f4d87, run per case on orion): shadow:direct `_half_split` 5,
`_bound_split` 5 (2 non-empty), `_imag_split` 5 (1 non-empty); shadow:mismatch 0.

**Plants** (each run on dev, fuzz and the 10 workloads against this run's Python; fired / caught on):

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
| rows-half-parity (new) | dev 29, fuzz 83, core 16 | cert 10, f6 27, wiring 2 |
| rows-bound-coeff-one (new) | dev 5, fuzz 34, core 39, f6 1, wiring 2, zero 1 | |
| rows-imag-drop-last (new) | core 8, wiring 4 | |
| rows-block-key-n | dev 85, fuzz 1151, core 154, f6 689, loop 63, wiring 435, zero 15 | |
| rows-rules-for-shape | every workload but scope (dev 143 ... cert 33, wiring 111) | |
| rows-of-constant-skip | dev 15, core 29, f6 24, wiring 13 | fuzz 6, cert 11, others 1-3 |
| rows-matches-constant | dev 37, core 186, loop 29, wiring 148 | f6 8, opaque 8 |
| rows-matches-coefficient | dev 104, core 104, f6 104, loop 26, rootof 26, value 26, wiring 78 | |
| rows-expand-drop-last | dev 38, fuzz 28, cert 15, core 99, f6 50, loop 10, rootof 1, value 150, wiring 60, zero 7 | opaque 5 |
| rows-placements-first | every workload but scope (dev 722 ... value 2404) | |
| rows-instances-others | every workload but scope (dev 50 ... value 299) | |
| rows-count-flip | dev 256, fuzz 136, core 740, f6 380, loop 60, rootof 8, value 604, wiring 224, zero 36 | cert 104, opaque 24 |
| rows-clauses-concl-only | wiring 1792 | |
| rows-wide-drop | wiring 6 | |
| rows-piecewise-last | wiring 1 | |
| rows-mul-sets-first | dev 17, core 141, f6 56, loop 2, wiring 9 | |
| rows-add-bound-skip | dev 31, fuzz 45, core 120, f6 10, loop 4, opaque 8, wiring 6, zero 1 | |
| rows-pow-key-same | wiring 1 | core 2 |
| rows-pow-times-skip | dev 3, core 96, loop 3, wiring 12 | |
| rows-pow-irrational-skip | core 16, wiring 2 | |
| rows-pow-ipi-skip | core 14, wiring 3 | |
| rows-pow-unit-drop | core 33, wiring 3 | |
| rows-pow-of-constant-skip | dev 16, core 312, loop 8, opaque 4, wiring 62 | f6 4 |
| common-wide-drop (6d) | wiring 3 | |
| with-closed-skip (lra-on) | dev 231, fuzz 326, cert 168, core 134, f6 510, opaque 27, wiring 28 | |
| rows-pow-head-any | **void** by construction (6g(b)): 0 everywhere | |

- rows-imag-drop-last's reach is the core workload's 64 new rows (fired 8, caught, as on orion) and wiring (4, caught).
- The parts ruling's three 6g(a) conditions still hold: `dispatch-ignores-epoch` (suite: 14 outcomes changed),
  `dispatch-redefines-off` (suite: 1; fires 1 on f6 and value, MATCH, as before), `dispatch-user-off` (void on the suite
  and workloads as before; caught by `dispatch_direct.py dispatch-user-off` on 85f4d87's source on orion, BAD 1, plain
  BAD 0). `knowledge-no-query-drop`: suite 20 changed.
- lra-on path (5c5's Rust `with_closed_units` over the dispatch): all runs MATCH with lra on; with-closed-skip caught (table).
- **equiv-one and ge2-drop (planner's precision):** pure Python never calls `Rules.equiv` per query: it has no caller in
  satassume/ (table.py:151-153 writes an equiv row's two rules itself). `ge2_alternatives` is called only from
  table.py:141 (`_premise_alternatives`) for a row with an `int>=2` premise (`Row._ge2`, table.py:70), and no table in
  satassume has one (`rg "GE2|int>=2" satassume` hits only table.py). So both are Python removal candidates, not port
  items; their code keeps the "unreached by any workload; common_direct.py only" footnote.

**Bar** (on 85f4d87)
1. Suite by id against C2b's rows: 5,992 passed / 126 failed / 23 skipped / 18 xfailed, 6,159 ids; new 0, gone 0,
   changed 0. Passed with no firing 5,991, with a firing 1 (`test_ci_stream_reports_only_what_replays`). S's standing:
   S's gate is met except for the 46 named stub failures, one cause. 627 step tests pass (19 files); direct scripts:
   relations_direct, dispatch_direct and common_direct exit 0, each of 6d's 13 common_direct plants exit 1.
2. Dev (1,985) and fuzz (3,000): answers and end state MATCH, py vs rust, traced vs untraced, Python control. Workloads
   f6, value, rootof, core (1,636), opaque, scope, loop, zero, wiring and cert: MATCH, each with a Python control.
3. Plants: table above; every rows plant but the void one is caught, rows-imag-drop-last on core and wiring.
4. Quiet handlers (suite): 39 rows in 2 tests, multiset same as base (34 `_ok` + 4 `_rb_clauses` in `_consistent`;
   1 "Already mutably borrowed" at `_build_context`, the 46-stub cause). TermFault 0.
5. Differences: none in answers, state or suite outcomes.

Kept shares (Rust run, against base, unchanged): out-of-scope dev 24/1,985 (1.21%), 0 elsewhere; refused f6 13/2,902
(Float 10, lra callback on a derived term 1, scaffold mismatch 2), opaque 7/2,546 (infinity/nan/Float), value 15/3,742
(Float), wiring 1/6,512 (lra), 0 elsewhere. The engine's `except Exception` at the complete check: 0 TermFault, 0
handler rows outside the suite's named ones.

**Kept on Python with reason:** `_rows_runtime`'s I/-I values (read once per process when Pow's generator is built, not
per query; not exact in rows' field without a reduction step) and Floats (SymPy's precision semantics, the planner's
default). Queries under a non-default registry; `enclose`.

**Owed before any backend PR:** `scaffold:rebuilt:f6` (90 on f6 this run) and `scaffold:mismatch` until 0, with
`rows:python:Mul`/`Add`/`Integer` (rows scaffolding; core: Add 96, Mul 96, Integer 740; dev: Add 6, Mul 3, Integer 256);
the NotImplementedError and hook re-entry contract notes; the items in OWED-satassume-rust.md; 6d's
pattern-key-type/const-key-type/max-cache-off replacements. `_n_conflicts` in rust_plugin.py is a test-plugin shim
(64 tests), not a port.

**Not run:** seed1, history, forced moves, the native path, timing; the mutant 2/5/6/7/9 rerun, the boundary rescore and
suite column, order:_rows evidence (not caught meanwhile), the `_forms` guard test; the rows plants on the suite.
No evaluator asked for.

# Step 6g(c2): the Product family's `_mul_factor_sets` and `_quotient_templates` from the query's table (issue 323)

Source **14b76fd** (sa-port-161, port/6g over 30f3309), **landed as one stack with the Element._new step** (planner's
stack ruling, 8 Nov ~11:10): cherry-picked clean onto Element._new (9139a9b + d0965f3) over rust-slice 17442af (5c7) as
**f1e4a74**, the tested source. One full bar, **S1**, on f1e4a74 (pareto1 `~/sp19/sa-rust-ids-work/sa-port-167/bar-S1/`,
`sum.txt`, end markers written by the job; .so 43dea1a1…), base suite rows 5c7's (`sa-port-158/bar-5c7b/suite`). Landed
by `PUSH=1 bar.sh land f1e4a74` with this report (sa-port-169); incoming diff at landing **none** (rust-slice still
17442af). The five bar items, the shared config and Element._new's own plant table are in results/port-elemnew.md; this
section keeps 6g(c2)'s evidence and plant table apart, as the stack ruling asks. S1 equals base on every item, so no
bisect ran and c2's solo bar wasn't used (its `done.txt` was written by its own job on pareto1 at 11:11:09Z, the second
of its `sum` phase, not by hand).

**Code.** rows_tpl.rs's Product family calls `RowsTpl::split` for `_mul_factor_sets` and `_quotient_templates`;
`direct_split` takes the Mul itself (a 1-tuple to `QIds::ids`) and returns `(result, shown)`, then `direct_rows` (product
pair) and `direct_add` (c1's three Add splits). `_mul_factor_sets` direct: `core_mul_factor_sets`; any ct set goes to the
shell (its rest is the Mul's other >= 2 factors, `kept_product`), and the (c, I, pi, s) set only when s is an input Mul
(`q.one`), else the shell. `_quotient_templates` direct: `core_quotient_shape`, objects by `q.obj`, then `Common::facts`
with the shell's key `('mul_quot', const_key(a) or None)`, consts `{0: a}` when a is an Atom and `core_is_number`,
objects `(a, v, t, expr)`, node 3; gen is core's `_quotient_rules` (knowledge_core_live's Rust rules). Shadow: the shape
`(a, v, t)` or None, compared by knowledge_core_live `shadow_split` with `_quotient_shape_py`. py.rs `core_pq`
pub(crate). Plants rows-mul-ipi-drop and rows-quot-swap. test_knowledge_core_shapes: new case `core-quotient-rules`
(`Q.integer(x*y**-1)`, odd x, even y).

**Module count (count rule): 13 of 32, unchanged**, against STATUS.md's "Counted modules" (lines 11-17; list in
port-elemnew.md). core.py still runs per query (orion retrace on f1e4a74, `~/sa-rust-ids-work/sa-port-167/c2/rc-core.txt`,
`rc-dev.txt`, `rc.sh OUT WL core.py,wiring.py,functions.py`, pass 1): on dev `_half_templates` 29, `_bound_templates` 31,
`_bound_split`/`_half_split`/`_imag_split` from knowledge_core_live 3 each, `irrational_root` 4; functions.py's `_unary`
templates 31, wiring.py's `template.<lambda>` 31. `_mul_factor_sets` and `_quotient_templates` themselves appear in the
retrace only under `[kept:out-of-scope]` (2 each on dev).

**Direct-split counts** (S1 knowledge.json, rows:rust / rows:python, `_mul_factor_sets`; `_quotient_templates`; before =
5c7's bar, all rows:python): dev 46/36; 63/19 (before 0/82; 0/82). fuzz 7/2; 7/2 (before 0/9; 0/9). cert 11/0; 11/0
(before 0/11; 0/11). core 72/158; 184/46. f6 25/65; 81/9. wiring 9/13; 16/6. loop 7/6; 8/5. zero 4/7; 4/7. rootof 368/0
each. value 318/0 each. opaque 1/0 each. scope, budget 0 (scope's 4/4 shell calls don't go through rows). rows:python is
the shell (`core:_mul_factor_sets`/`core:_quotient_templates` equal it on every workload): ct sets and derived s go there
by design; `core:derived:` is 0 for these two.
**Shadow** (test_knowledge_core_shapes 11/11 on f1e4a74, orion, `~/sa-rust-ids-work/sa-port-167/c2/shadow.txt`, tree.txt
shows sa-port-19 imported): shadow:direct `_mul_factor_sets` 10 (10 non-empty), `_quotient_templates` 11 (1 non-empty,
`core-quotient-rules`); c1's three 5/5/5 as before; **shadow:mismatch 0**.

**Plants, this step** (S1; each on dev, fuzz and the 11 workloads against this run's Python; fired / caught on):

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
| **rows-quot-swap (new)** | dev 4, core 44, f6 1 | wiring 1 |
| **rows-mul-ipi-drop (new)** | **void**: 0 on all 13 workloads (reason below) | |
| rows-half-parity | dev 29, fuzz 83, core 16 | cert 10, f6 27, wiring 2 |
| rows-bound-coeff-one | dev 5, fuzz 34, core 39, f6 1, wiring 2, zero 1 | |
| rows-imag-drop-last | core 8, wiring 4 | |
| rows-block-key-n | dev 85, fuzz 1,151, budget 7, core 154, f6 689, loop 63, wiring 435, zero 15 | |
| rows-rules-for-shape | every workload but budget and scope (dev 143 ... cert 33, wiring 111) | |
| rows-of-constant-skip | dev 15, core 29, f6 24, wiring 13 | fuzz 6, cert 11, others 1-3 |
| rows-matches-constant | dev 37, core 186, loop 29, wiring 148 | f6 8, opaque 8 |
| rows-matches-coefficient | dev 104, core 104, f6 104, loop 26, rootof 26, value 26, wiring 78 | |
| rows-expand-drop-last | dev 38, fuzz 28, budget 10, cert 15, core 99, f6 50, loop 10, rootof 1, value 150, wiring 60, zero 7 | opaque 5 |
| rows-placements-first | every workload but scope (dev 722 ... value 2,404) | |
| rows-instances-others | every workload but scope (dev 50 ... value 299) | |
| rows-count-flip | dev 256, fuzz 136, core 740, f6 380, loop 60, rootof 8, value 604, wiring 224, zero 36 | budget 40, cert 104, opaque 24 |
| rows-clauses-concl-only | wiring 1,792 | |
| rows-wide-drop | budget 22, wiring 6 | |
| rows-piecewise-last | wiring 1 | |
| rows-mul-sets-first | dev 17, core 141, f6 56, loop 2, wiring 9 | |
| rows-add-bound-skip | dev 31, fuzz 45, core 120, f6 10, loop 4, opaque 8, wiring 6, zero 1 | |
| rows-pow-key-same | wiring 1 | core 2 |
| rows-pow-times-skip | dev 3, core 96, loop 3, wiring 12 | |
| rows-pow-irrational-skip | core 16, wiring 2 | |
| rows-pow-ipi-skip | core 14, wiring 3 | |
| rows-pow-unit-drop | core 33, wiring 3 | |
| rows-pow-of-constant-skip | dev 16, core 312, loop 8, opaque 4, wiring 62 | f6 4 |
| common-wide-drop (6d) | budget 38, wiring 3 | |
| with-closed-skip (lra-on) | dev 231, fuzz 326, cert 168, core 134, f6 510, opaque 27, wiring 28 | |
| rows-pow-head-any | **void** by construction (6g(b)): 0 everywhere | |

- **rows-quot-swap** is caught on dev, core and f6 (core: as on sa-port-161's orion run, fired 44, answers DIFFER).
- **rows-mul-ipi-drop is void, with its reason:** it drops the (c, I, pi, s) set of the direct `_mul_factor_sets`, which
  the direct path builds only when s is an input Mul. On every workload s is derived (e.g. `x*y` of `I*pi*x*y`), so
  that set goes to the shell and the plant's line never runs (fired 0 on all 13; 0 on core and dev on orion too). The
  direct path then returns only `[expr.args]` on these workloads. No workload reaches that branch yet; per the reached-code
  ruling it counts as not reached until one does.
- **The parts ruling's three 6g(a) conditions still hold** (S1's suite plants): `dispatch-ignores-epoch` suite 12
  outcomes changed (`test_registry_versioning.py` x2, `test_templates.py` x1, `test_transfer*.py` x9), 0 on workloads;
  `dispatch-redefines-off` suite 1 changed (`test_s10_override.py::test_reproducers`), fires 1 on f6 and value, MATCH,
  as before; `dispatch-user-off` void on the suite and workloads as before (its catch is `dispatch_direct.py
  dispatch-user-off`, c1's evidence). `knowledge-no-query-drop`: suite 25 changed (c1's bar: 20; S1's base includes 5c7).
  Every suite plant run kept the handler multiset equal to base.

**Kept shares, bar items 1, 2, 4, 5:** in port-elemnew.md (S1, all equal to base). **Kept on Python with reason**, as
c1: `_rows_runtime`'s I/-I values and Floats; queries under a non-default registry; `enclose`.

**Owed before any backend PR:** `scaffold:rebuilt:f6` (45 on f6 in S1, as c1's bar rows and F2) and `scaffold:mismatch`
(2 on f6) until 0, with `rows:python:Mul`/`Add`/`Integer` (core 96/96/740; dev 3/6/256); a workload whose s is an input
Mul for the (c, I, pi, s) direct set (rows-mul-ipi-drop's reach); the rest as c1.

**Not run:** as in port-elemnew.md (history, forced moves, the native path, timing, the mutant rerun, the boundary rescore
and suite column, order:_rows evidence, the `_forms` guard test); the rows plants on the suite. No evaluator asked for.


# Steps 6g(c3), 6g(c4), 6g(c5): the Pow family's splits, `constant_value`, and the Addition template builders from the query's table, landed as one stack (issue 323)

**One stack, three steps** (planner's 6g(c3)-(c5) stack go, 8 Nov ~14:00). Built by sa-port-163 (c3), sa-port-164 (c4,
c5's Rust) and sa-port-172 (c5's Python, the stack); rebased and barred by sa-port-175, landed by sa-port-190 (sa-port-187 filled the report).

**Tested source: af63d20** on rust-slice 4215655 (5c10b): c3 46006f1 + 438e081, c4 2fafc05 + bfb60c5, c5 3f4cdc8 +
e64ec78, plus af63d20 (results/ only: the predecessor's handoff and this report's draft). **Landed** by `PUSH=1 bar.sh
land af63d20` with this report (results/ only on top); incoming diff at landing: none (rust-slice still at 4215655, the tested base; `bar.sh land` rebase "up to date"; landing source = af63d20 plus results/ only).

How it got there (each rebase brought guarded source the bar executes, so each got a full bar, as the rebase rule asks):
1. **0643e9c** on 3611952 (5c8): full bar `~/sp19/sa-rust-ids-work/sa-port-172/bar-6g-c3c5/` (exit 0 16:54:03Z),
   equal to base (5c8's rows) and to S1's rows on every item.
2. **d0374e9** on 2d12e81 (5c9a-c, 18 guarded files): its bar was stopped in its plants phase when rust-slice moved again
   (sa-port-175/bar-6g-c3c5r, partial, not used).
3. **2c2990c** on 67d108d (5c10a: session.rs, relations_core.rs, factcache.rs, term_live.py, session_live.py,
   memo_check.py, lib.rs, test_factcache_core.py): full bar `~/sp19/sa-rust-ids-work/sa-port-175/bar-6g-c3c5r2/`
   (exit 0 20:38:37Z, .so 909bacbd…), base 5c10a's rows: equal to base on every item (numbers as below).
4. **af63d20** on 4215655 (5c10b). Incoming diff 67d108d..4215655: handler_count.py, memo_check.py, session_live.py,
   solver_rs/src/{context.rs (new), engmemo.rs, lib.rs, relations_core.rs, session.rs}, test_context_core.py, plus
   results/ (port-5c10b.md, HANDOFF-sa-port-184.md, port-ownership.md/.tsv); 931 insertions, 18 deletions. The guard named
   the nine source files, all executed by the bar, so a **full bar ran on af63d20**: pareto1
   `~/sp19/sa-rust-ids-work/sa-port-187/bar-6g-c3c5r3/` (end.txt `exit 0 2026-11-08T23:13:26Z`, written by the job; .so b95d665c…), config =
   bar-6g-c3c5r2's plus 5c10b's test_context_core.py, base suite rows 5c10b's (`sa-port-186/bar-5c10b/suite`), kept-share base (KEPT_BASE)
   bar-6g-c3c5r2. Orion short check before it: build OK, 116 passed (shapes, context, rows, engmemo, factcache, procmemo).

Completeness (checked on the bar's files before reading it): suite rows for all 6,159 ids; 13 workload comparisons (dev,
fuzz and 11 WLS), each with its Python control, plus seed1 on dev and fuzz; 56 plants x 13 workloads = 728 plant rows;
7 suite-plant runs; handler rows for the suite, live, extra and plant runs; every phase exit 0. Each step's plant table is
kept apart below, as the stack ruling asks.

## The bar (on af63d20)
1. **Suite by id against 5c10b's rows: 5,991 passed, 127 failed, 23 skipped, 18 xfailed, 6,159 ids; new 0, gone 0, changed outcome 0.** Passed split by firing: 5,990 with no handler firing, 1 with a firing (`tests/test_invariants.py::test_ci_stream_reports_only_what_replays`, the named needs-internals case). Against the 2c2990c bar's rows:
   new 0, gone 0, changed 0, handler multiset equal (bar_sum.py against bar-6g-c3c5r2/suite, pareto1 `sa-port-187/sum-vs-r2.txt`). Against the first stack bar (0643e9c, 5c8 base): the one changed id is
   `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` passed -> failed, the
   **known id()-reuse failure** (below), failed in the 5c10a and 5c10b base rows too. S's standing: S's gate is met except
   for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz: answers and state MATCH** (answers_sha dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6; end, stream
   and lra diffs 0; Rust made 0 Python solvers), Python-vs-Python controls MATCH, traced-vs-untraced end states MATCH,
   seed1 MATCH. All 11 WLS MATCH with controls: f6 2,902, value 3,742, rootof 5,187, core 1,636, opaque 2,546, scope
   169, loop 420, zero 854, wiring 6,512, cert 61, budget 28 queries. The **lra-on path MATCH** (with_closed_units, the
   6g(a)/5c5 meeting point), with **with-closed-skip caught** on dev, fuzz, cert, core, f6, opaque and wiring.
3. **Plants:** every plant caught before is still caught, on the same workloads: the per-plant sets of workloads where it
   fires and where it's caught equal the first stack bar's for all 56 plants (awk over sum.txt's plant table, pareto1 `sa-port-187/plantagg-bar-6g-c3c5r3.txt`, equal line for line to `sa-port-175/plantagg-bar-6g-c3c5r2.txt`; the same awk reproduces the r2 file exactly). Per-step tables below.
   rows_tpl.rs PLANTS still caught as on S1; rows-pow-head-any void by construction (6g(b)).
4. **Quiet handler firings on Rust:** suite 39 rows in 2 tests, multiset equal to 5c10b's base and to bar-6g-c3c5r2's: 34 `_consistent` AttributeError (`'Solver' object has no attribute '_ok'`) and 4 (`... '_rb_clauses'`) in `test_ci_stream_reports_only_what_replays` (the named needs-internals case); 1 `Engine._build_context` RuntimeError `Already mutably borrowed` in `test_protocol_on_fuzz` (the named 46-stub cause, tests/theory_harness.py:242). No other firing: live, seed1 and the 11 WLS handler files have 0 rows; plant runs fire only where the plant itself raises (ad-kind-swap dev 2 / fuzz 315, rows-block-key-n 1 / 16), as on bar-6g-c3c5r2. TermFault 0; ids whose caught rows differ from base 0.
5. **Known differences:** none in answers or read state. Kept shares per reason equal base on every workload
   (against KEPT_BASE bar-6g-c3c5r2, 0 pairs differing; against 5c10b's own bar, 12 pairs on the workloads it ran, 0 differing, pareto1 `sa-port-187/sum-kept-vs-5c10b.txt`): out-of-scope dev 24/1,985 (1.21%), 0 elsewhere; refused f6 13/2,902 (Float 10), opaque 7/2,546, value
   15/3,742 (Float), wiring 1/6,512 (a callback on a derived term). No rise.

**The parts ruling's three 6g(a) conditions still hold.** Suite plants (against this run's suite): dispatch-ignores-epoch 9 changed ids (test_registry_versioning's `test_splits_are_keyed_on_the_registry` and `test_template_registration_clears` among them), dispatch-redefines-off 1 (`test_s10_override.py::test_reproducers`), dispatch-user-off 0 (caught directly, below), elem-eq-flip 1, knowledge-no-query-drop 23 (2c2990c: 21, 18 shared; the set varies with worker order too), union-skip-overlap 2, within-no-link 0 (void on workloads and suite since 5c7, port-5c7.md).
`dispatch-ignores-epoch`'s changed ids differ from run to run (0643e9c: 18, with test_unrelated_relation/test_verify_*;
2c2990c: 17, with test_transfer_fuzz x12; af63d20: 9): which test meets a stale dispatch entry depends on what ran before it in the
same xdist worker. Direct, on orion on af63d20 (`~/sa-rust-ids-work/sa-port-187/dispatch-direct-af63d20.txt`):
`dispatch_direct.py` plain exit 0 (user path 2, BAD 0); **dispatch-user-off caught** (user path 0, BAD 1, exit 1);
dispatch-ignores-epoch caught (BAD 3); dispatch-redefines-off caught (BAD 2). direct.txt (the bar's) equals S1's:
dispatch_direct exit 0, common_direct plain exit 0, 13 common plants exit 1.

**Shadow (test_knowledge_core_shapes, 23 cases, orion on af63d20, `~/sa-rust-ids-work/sa-port-187/shadow-af63d20.txt`):
shadow:mismatch 0, answers equal.** shadow:direct per name: `_half_split` 10, `_bound_split` 10, `_imag_split` 10,
`_mul_factor_sets` 18, `_quotient_templates` 20; c3: `_exp_arg` 17, `_unit_angle` 16, `ipi_split` 3, `irrational_root`
16, `_unit_power_units` 2, `_pow_bound_templates` 14, `ipi_rules` 2; c4: `constant_value` 60; c5: `_half_templates` 1,
`_bound_templates` 7, `_recip_templates` 7, `_imag_templates` 2.

## 6g(c3): the Pow family's seven splits direct

**Code** (46006f1, plant fix 438e081). rows_tpl.rs's Pow family computes `_exp_arg`, `_unit_angle`, `ipi_split`,
`irrational_root`, `_unit_power_units`, `_pow_bound_templates` and `ipi_rules` from the query's table through
`RowsTpl::split` / `direct_rows`, with tcore.rs's `ipi_rules` (:597). Each falls back to the shell (`rows:python:NAME`)
for no or a kept query, a derived argument or result, a product rest (`kept_product`), or a non-Rational exponent in
`_unit_power_units` (the shell's counted `as_real_imag` fallback). The shadow compares each result through
knowledge_core_live `shadow_split`. test_knowledge_core_shapes: seven DIRECT entries, six cases.

**Direct split** (rows:rust / rows:python on the af63d20 bar; before = S1's bar, all on Python; rust + python equals
before on every workload): 
- `_exp_arg`: dev 8/0; core 276/0; f6 1/0; loop 7/0; opaque 17/0; wiring 29/0
- `_unit_angle`: dev 8/0; core 276/0; f6 1/0; loop 7/0; opaque 17/0; wiring 27/0
- `ipi_split`: core 54/1; wiring 4/0
- `irrational_root`: dev 5/0; core 80/0; f6 1/0; loop 3/0; opaque 1/0; wiring 24/0
- `_unit_power_units`: core 18/15; wiring 3/0
- `_pow_bound_templates`: dev 8/0; core 243/0; f6 1/0; loop 4/3; opaque 17/0; wiring 24/0
- `ipi_rules`: core 14/0; wiring 3/0

**Plants, c3** (af63d20 bar: dev, fuzz and the 11 workloads, each against this run's Python; fired on the workloads
named, 0 on the rest):

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
| rows-exp-arg-none | wiring 2 |  |
| rows-unit-angle-shift | core 33, wiring 5 |  |
| rows-ipi-split-shift | core 54, wiring 3 |  |
| rows-irrational-false | core 16, wiring 2 |  |
| rows-unit-power-drop-last | core 18, wiring 3 |  |
| rows-pow-bound-drop-last | core 144, wiring 1 |  |
| rows-ipi-rules-drop-last | core 14, wiring 3 |  |

- **c3's -neg pair, replaced in this stack:** rows-unit-angle-neg and rows-ipi-split-neg fired (orion: core 33/54, wiring
  5/3) and MATCHed everywhere: negation keeps the parity, denominator and half-oddness that the rules read, so both were
  void by construction. Replaced in both lists (438e081) by rows-unit-angle-shift and rows-ipi-split-shift (plus 1, which
  flips parity); both are caught on core and wiring (table), 0 on dev and f6, whose queries don't reach these splits.
- rows-exp-arg-none is caught on wiring only (2); the other five c3 plants on core and wiring. dev and f6 fire 0 for
  all seven (their queries have no Pow of these shapes with an input exponent).
- **Moved items reached:** all seven splits are reached on core and wiring; `_exp_arg`, `_unit_angle`, `irrational_root`
  and `_pow_bound_templates` also on dev, f6, loop and opaque (counts above).

## 6g(c4): `constant_value` direct

**Code** (2fafc05, shapes cases bfb60c5). `RowsTpl::constant_value` / `direct_constant_value`: a Rational constant and
the compiled rows' seven texts are computed in Rust (`rows:rust:constant_value`); a Float, infinity or nan, `1/number` at
0, or another text goes to `_rows_runtime.constant_value` (`rows:python:constant_value`), counted by reason
(`rows:kept:constant_value:Float`, `:other`). Shadow: `shadow_split('constant_value', ...)` against
`_rows_runtime.constant_value`. Shapes cases: a Rational exponent's and a Rational base's compiled constants.

**Direct split:** 
- `constant_value`: dev 27/0; fuzz 6/0; cert 11/0; core 336/1; f6 24/0; loop 10/0; opaque 5/0; wiring 72/0; zero 2/0

**Plants, c4:**

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
| rows-constant-value-neg | dev 27, core 336, f6 24, wiring 72 | fuzz 6, cert 11, loop 10, opaque 5, zero 2 |

- **`rows:kept:constant_value:Float` counts 0 on every bar workload** (the f6/value/opaque Float queries are refused
  earlier, `refused:algebra: Float`, before rows run). Not a false zero: it fires on crafted queries (on 0643e9c's build:
  `Q.positive(0.5**x)` with x real: `rows:kept:constant_value:Float` 2, `rows:python:constant_value` 2, answers equal;
  `~/sa-rust-ids-work/sa-port-175/keptfire.txt`). **Floats stay on Python** (planner's default: SymPy's precision
  semantics).

## 6g(c5): the Addition template builders direct

**Code** (3f4cdc8 Rust, e64ec78 Python). `RowsTpl::add_tpl` / `add_tpl_parts`: `_half_templates`, `_bound_templates`,
`_recip_templates` and `_imag_templates` build the same facts key, consts, objects and node in Rust and hand
`Common::facts` a Rust generator (tcore.rs `half_rules` :228, `bound_rules` :252, `recip_rules` :274, `imag_rules` :299),
counted `rows:rust:NAME` (a call that returns no template counts too). A kept query, and `_imag_templates` with every `x`
a number (an Add of numbers, built with SymPy's arithmetic: `rows:kept:_imag_templates:number`, then
`rows:python:_imag_templates`), go to Python. knowledge_core_live: `ADD_TPL` (:31) and `_add_tpl_py` (:443), core's
builder run with `facts` captured, compared in `shadow_split` (:464) as (key, consts, objs, node, rules). Shapes cases:
`Q.integer(x/2 + y/2)` odd x, y; `Q.positive(1 + 2*x)` integer nonnegative x; `Q.positive(2 + 3/y)` positive y;
`Q.imaginary(I*x + I*y)` positive x, y.

**Direct split:** 
- `_half_templates`: dev 29/0; fuzz 73/0; cert 10/0; core 32/0; f6 26/0; opaque 4/0; wiring 1/0
- `_bound_templates`: dev 31/0; fuzz 45/0; core 120/0; f6 10/0; loop 4/0; opaque 8/0; wiring 6/0; zero 1/0
- `_recip_templates`: dev 31/0; fuzz 45/0; core 120/0; f6 10/0; loop 4/0; opaque 8/0; wiring 6/0; zero 1/0
- `_imag_templates`: core 8/0; wiring 4/0

**Plants, c5:**

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
| rows-half-tpl-flip | dev 29, fuzz 73, core 32, f6 26, opaque 4 | cert 10, wiring 1 |
| rows-bound-tpl-neg | dev 31, fuzz 45, core 120, f6 10, loop 4, opaque 8, wiring 6, zero 1 |  |
| rows-recip-tpl-neg | **void** on workloads: 0 on all 13 |  |
| rows-imag-tpl-sign | core 8, wiring 4 |  |

- **rows-recip-tpl-neg is void on every workload, with its reach:** it fires 0 on all 13 bar workloads and on orion's
  core, dev, f6 and wiring. `rows:rust:_recip_templates` counts every call (it equals `_bound_templates` on each
  workload, since core calls both on each bound split), but the plant's line runs only when `u` is `1/v` with `v` not a
  number, and no workload has a term `c0 + c1/v`. Its one reach is the shapes case `rows-recip-tpl-neg`
  (`Q.positive(2 + 3/y)`), where it **is caught** by the shadow: plain passes, planted fails with `shadow:mismatch` on
  `core:_recip_templates` (`~/sa-rust-ids-work/sa-port-175/plantshape-c5.txt`; the other three c5 plants are caught the
  same way there). Per the reached-code ruling the recip branch counts as not reached by a workload until one brings
  `c0 + c1/v`; it goes on the owed list with rows-mul-ipi-drop's reach.
- **`rows:kept:_imag_templates:number` counts 0 on every bar workload.** Not a false zero: `Q.imaginary(I*pi + I*E)` and
  `Q.imaginary(2*I + 3*I)` (unevaluated) each count 1 with `rows:python:_imag_templates` 1, answers equal (keptfire.txt).
  **I/-I values stay on Python** in `_rows_runtime` (this path builds them with SymPy's arithmetic; planner's ruling).

## The rest, for all three steps

**Module count (count rule): 14 of 32, unchanged.** Orion retrace on af63d20 (`rc.sh OUT WL
core.py,wiring.py,functions.py,registry.py`, pass 1 `[query]` lines; `~/sa-rust-ids-work/sa-port-187/rc-{dev,f6,core,wiring}.txt`):
- core.py still runs per query: `_bound_split`/`_half_split`/`_imag_split` from the knowledge_core_live shell for
  derived terms (dev 3 each, f6 6, core 69, wiring 4), `_coeff_term` (dev 1, f6 6, core 87, wiring 4), `_imag_term`
  (dev 8, f6 12, core 138, wiring 8), `ipi_split`/`pi_split` from functions.py's `_pi_trig` (dev 2/3, f6 130/100, core
  111/48, wiring 2/0), and `_unit_power_units` core 15 (the shell's fallback). So core.py doesn't count yet.
- wiring.py still runs per query on dev and f6: `_attributed.<locals>.template` (dev 6, f6 24) and
  `template.<locals>.<lambda>` (dev 31, f6 134), so it doesn't count yet.
- registry.py: no `[query]` line on the four (`_covers` and `_load` only at no-query), as before.
c3-c5 removed `_half_templates`, `_bound_templates`, `irrational_root` and the other moved splits from the per-query
trace (S1's retrace had `_half_templates` 29 and `_bound_templates` 31 on dev). Next, the 6e/6f shells (`_pi_trig` with
the plain `_unary` first) take `ipi_split`/`pi_split` off core's per-query list.

**Direct-split counts explained:** rows:rust:NAME + rows:python:NAME equals S1's rows:python:NAME (the shell, before) on
every workload for all twelve moved names. The Python remainder is: `ipi_split` core 1 and `_pow_bound_templates` loop 3
(derived argument or result; `core:derived:_pow_bound_templates` loop 3), `_unit_power_units` core 15 (the shell's own
fallback: a non-Rational exponent or e outside the table), `constant_value` core 1 (`1/number` at 0:
`rows:constant_value:python:Zero:1/number` 1). `core:derived` totals (dev 9, fuzz 72, core 207, f6 18, loop 18, opaque
21, wiring 12) are c1's three Add splits on derived terms and the loop 3 above.

**Rows scaffolding, owed before any backend PR until 0:** `scaffold:rebuilt` dev 29, fuzz 305, f6 45, opaque 15, value
221, zero 28 (`scaffold:rebuilt:f6` 45 as on S1); `scaffold:mismatch` f6 2; `rows:python:Mul`/`Add`/`Integer` core
96/96/740, dev 3/6/256, wiring 12/8/224, loop 3/6/60. Also owed: rows-mul-ipi-drop's reach (a workload whose s is an input
Mul; void on all 13 here, as on S1), rows-recip-tpl-neg's reach (`c0 + c1/v`), and the rest of the backend-PR list as c1.

**Kept on Python with reason:** `_rows_runtime`'s I/-I values (c5: `rows:kept:_imag_templates:number`) and Floats (c4:
`rows:kept:constant_value:Float`), both 0 on workloads and shown to fire (not false zeros); queries under a non-default
registry; `enclose`; `const_value` (named callback; `rows:python:const_value` dev 256, fuzz 136, core 740, f6 380).

**equiv-one and ge2-drop (precision ruling):** unchanged from 6g(c1): pure Python never calls `Rules.equiv` per query (no
caller in satassume/; table.py:153 writes an equiv row's two rules itself) and calls `ge2_alternatives` only from
table.py:141 for an `int>=2` premise, which no table has. So both are Python removal candidates, not port items;
common_direct.py catches both (exit 1).

**Known id()-reuse failure, owed:** `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`
fails on Rust from 5c10a (67d108d) on: reused object ids, a test artifact (sa-port-185, report a28c548: 50 of 50 fail
under Rust at 67d108d, a keep-alive variant passes 50 of 50). Test not edited. It is failed in the base rows too (5c10a's
and 5c10b's), so it isn't a changed outcome here.

**Not run:** moved to "before any backend PR", none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control;
the boundary rescore and suite column; the final drop score and its lost rows; the suite split with Python's counter;
`order:_rows`' evidence (not caught meanwhile); the `_forms` guard test; history reruns (seed1 was run); forced moves;
the native path; timing. The rows plants on the suite. **Speed not measured.** Mutants 2, 5, 6, 7, 9 still rest on the
API fuzzer alone; 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run. The
`_n_conflicts` view in rust_plugin.py is a test-plugin shim (64 tests). No evaluator asked for.
