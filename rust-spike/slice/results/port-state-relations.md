# State step, part 2, sub-part (i): the `ad:cbm_noid` fallback (issue 323)

Sub-part (i) landed. Sub-parts (ii) (the transfer sites) and (iii) (Relations' dicts and term_live's callbacks) were not
started: they are handed off (`~/dev/architect/briefs/NEXT-port-state-relations.txt`). This step's measurements of their
readers are below so the next session doesn't redo them. Work by sa-port-200.

## What moved
- **The cause of scope's 4 `ad:cbm_noid` calls at a8a4bae.** All 4 are glue's `link_objects` asking the adapter's
  `integer_form` for a **plain Python `int` side (`1`)**. term_live `term_id` has no row for something that isn't `Basic`
  (`term:unknown:integer_form:int`), so the slot went back to Python. Python's `integer_form` (lra_adapter.py :400) returns
  None on its first line, `if not isinstance(e, Expr) ...: return None`. The traced run is
  `~/sa-rust-ids-work/sa-port-200/q0/scope.err`, by site: `link` 127, `relation_atom` 12, `key` 4 and `integer_form` 4, every
  one `int 1`. The first three are term_live's own `term_id` sites, not the adapter's.
- **The port:** adapters.rs `Reader.integer_form` gives that answer natively. A side that isn't an `Expr` is None, decided by
  its type, with no row and no call into Python. lra_live's `integer_form` does the same (lra_live.py, before `_query()`), so
  the two stay line for line.
- **Why not "an id in the query's table", as the brief's step 4 words it:** giving the int a row would be the wrong port. The
  table would read it as `Integer(1)` and return a form `(Integral((), 1), [])`, not None. Plant 256 does exactly that. No
  workload sees the difference, because an int's form has no opaque terms (see Plants), but it would be a different answer.
- **Counter** 337 `ad:lra_not_expr` (session.rs NAMES 338). **Plant** 256 `ad-lra-not-expr` (relations_core.rs; session_live
  `_REL_STATE_PLANTS`).
- **Shared-file change, kept minimal:** the plant id is widened from u8 to u16 (relations_core.rs `PLANT` is `AtomicU16`, the
  plant consts are u16, `planted`/`plant_on` take u16; query.rs `head`'s argument). The u8 space ended at 255, and the brief
  gives this part 256-279 and 6i 280-319. `PyTermTable.number` is made pub(crate) for the plant.
- **Tooling:** pycalls.py's `PYCALLS_FILE` takes several paths joined by ':' and files each name as `file.py:name`.
- **Test:** test_lra_slot.py gains a direct `not_expr` case: on a live query, `LRAAdapter.integer_form(1)` is None and
  `ad:cbm_noid` doesn't move. `ad:lra_not_expr` joins the counters that must fire, and `ad-lra-not-expr` joins PLANTS (it
  must fire and move a case). Result: 7 passed, 1 skipped (`ad-lra-slot-stale`, void by construction, as before).

## SHAs
- Base: rust-slice a8a4bae. Tested: **8ee1fac** (1352986 for the change, then the pycalls.py commit). Landed: **8ee1fac**
  plus this report's commit (results/ only, outside bar.sh's push guard).
- Incoming diff: **empty.** `bar.sh land 8ee1fac` (no PUSH) at 11:14Z found origin/rust-slice still at a8a4bae, "Current
  branch port/state-relations is up to date", so the landing source equals the tested source.

## The bar (pareto1, `~/sp19/sa-rust-ids-work/sa-port-200/bar-state-relations-i` on 8ee1fac)
Run 10:40Z-11:13Z under shared lease 888a197f, which was released after 33m (exit 0). Every phase exited 0; seed1 was not
run. `.so` sha256 e90a64ae…. Base suite rows: `sa-port-198/bar-state-memoized-r2/suite`. Summary copied to
`~/sa-rust-ids-work/sa-port-200/bar/sum.txt`, counters to `.../bar/counts.txt`.
1. **Suite by id:** 5,991 passed, 127 failed, 23 skipped (plus 18 xfailed), over 6,159 ids. **Against base: new 0, gone 0,
   changed outcome 0.** Passed splits into 5,990 with no handler firing and 1 with a firing:
   `tests/test_invariants.py::test_ci_stream_reports_only_what_replays`, the named case.
2. **Fresh dev and fuzz: answers and state MATCH** (Rust against Python, traced and untraced; Python against Python as the
   control). dev answers_sha 31cd0945c07f02a6, fuzz 173502b6ef285ad6. loop, zero, cert, scope and budget all MATCH.
3. **Plants caught:** `ad-lra-pair-swap` (dev, fuzz, cert, scope, zero) and `ad-lra-kind-key` (dev, fuzz, cert, scope, zero)
   are caught by the live comparison. `ad-lra-not-expr` is caught by test_lra_slot.py (tests phase: 687 passed, 4 skipped,
   exit 0).
4. **Quiet handler firings on Rust: the handler multiset is the same as base.** 39 rows in 2 tests:
   - 34 × `_consistent` AttributeError `'Solver' object has no attribute '_ok'`, in test_ci_stream_reports_only_what_replays;
   - 4 × `_consistent` AttributeError `_rb_clauses`, in the same test;
   - 1 × `Engine._build_context` RuntimeError "Already mutably borrowed", in test_protocol_on_fuzz (the named 46-stub cause).

   **engine.py:1906's catches (`ctx:caught`): 0 on all seven workloads.** TermFault in pytest.log: 0. The live and extra
   handler files have 0 rows.
5. **Known differences in answers or read state: none.**

## Plants
| plant | fired (dev / fuzz / scope / other) | caught by | note |
|---|---|---|---|
| `ad-lra-not-expr` (256) | 0 / 0 / 4 / 0 | test_lra_slot.py `not_expr` (direct) | **void on every workload**: scope MATCHes under it, since an int's form has no opaque terms and `link_objects`' set is unchanged. Suite: fired 0 (SUITE_PLANTS `zero` ran it: 0 new, 0 gone, 0 changed) |
| `ad-lra-pair-swap` (255) | 450 / 47,256 / 68 | live: dev, fuzz, cert, scope, zero DIFFER | part 1's, rerun |
| `ad-lra-kind-key` (251) | 1,418 / 41,888 / 623 | live: dev, fuzz, cert, scope, zero DIFFER | part 1's, rerun |
| `ad-lra-flag-key` (253) | 5,475 / 164,954 / 2,472 | test_lra_slot.py | part 1's; void on workloads (no flag flip inside a query) |
| `ad-lra-patch-guard` (254) | 5,508 / 164,954 / 2,472 | test_lra_slot.py | part 1's; void on workloads (no patch) |
| `ad-lra-slot-stale` (252) | 1,135 / 59,037 / 366 | none: void by construction | named in test_lra_slot.py ELSEWHERE |

Plants 257-279 are unused (sub-parts (ii) and (iii)).

## `ad:cbm_noid` and `integer_form` per workload, before (a8a4bae) and after (8ee1fac)
`integer_form` is the per-query Python call count into lra_adapter.py `integer_form` on converted queries (pycalls.py,
`~/sa-rust-ids-work/sa-port-200/pyc/{base,cand}`). The counters come from the same runs' session reports, and the after
column was checked again against the bar's.

| workload | cbm_noid before → after | `integer_form` on converted queries, before → after | `ad:lra_not_expr` after |
|---|---|---|---|
| dev | 0 → 0 | 0 → 0 (4 calls, all `kept:out-of-scope`, on both) | 0 |
| fuzz | 0 → 0 | 0 → 0 | 0 |
| zero | 0 → 0 | 0 → 0 | 0 |
| loop | 0 → 0 | 0 → 0 | 0 |
| scope | **4 → 0** | **4 → 0** | 4 |
| budget | 0 → 0 | 0 → 0 | 0 |
| cert | 0 → 0 | 0 → 0 | 0 |

**The lra_adapter.py check the noid ruling sets.** On 8ee1fac, the only lra_adapter.py functions that run on a converted
query on any of the seven workloads are `relation`, ruled conversion. Everything else runs only on kept queries (dev 33
`_memoized`, all kept:out-of-scope) or at import (`<module>`, `_Unhandled`, `LRAAdapter`). **Nothing claimed:** the count is
the planner's to apply.

## Group-D relations-path samples
**Not run** for (i). The change runs only on scope's 4 calls: dev and fuzz have `ad:lra_not_expr` 0, and their per-query call
counts into lra_adapter.py, relations.py, term_live.py and session_live.py are equal, base to candidate, function by function.
So dev and fuzz run the same path as on a8a4bae. Group-D before and after is owed to (ii)/(iii), which move the relations
path.

## Readers for (ii) and (iii), measured (step 1, all three sub-parts)
Per-query Python calls on converted queries (pycalls.py, all four files in one pass). Base and candidate are equal except
scope's lra_adapter.py, down 4 (`integer_form`), and term_live.py, down 28 (term_id's `integer_form` site and what it
called).

| workload (queries) | session_live.py | term_live.py | relations.py | term_live `_relation_atom` | term_live `_under_apps` | session_live `_rel_m` | session_live `_rel_process` |
|---|--:|--:|--:|--:|--:|--:|--:|
| dev (1,985) | 155,292 | 89,888 | 27 | 5,565 | 8,642 | 8,818 | 392 |
| fuzz (3,000) | 2,010,015 | 1,649,685 | 1,697 | 190,710 | 6,690 | 201,589 | 5,564 |
| zero (854) | 384,922 | 359,774 | 2 | 22,248 | 40,716 | 38,194 | 1,097 |
| loop (420) | 56,450 | 13,501 | 0 | 0 | 2,361 | 0 | 0 |
| scope (169) | 51,292 | 25,244 | 1,343 | 2,181 | 576 | 3,821 | 268 |
| budget (28) | 20,221 | 5,432 | 0 | 108 | 0 | 0 | 0 |
| cert (61) | 26,427 | 19,432 | 72 | 2,583 | 51 | 2,256 | 122 |

- **The three transfer sites as Python methods:** `Relations._engage_transfer`, `sync_transfer` and `_xswitch` run **0
  times** on every workload (relations_core.rs has them: `engage_transfer` :1635, `xswitch` :1750, `sync_transfer` :1768).
  What (ii) owns is that the Rust versions still read and write `Session.xfer`, `Session.solver` and the Relations fields
  (`xfer`, `_xadapter`, `xfer_sel`, `_xside`...) as Python attributes.
- **relations.py on converted queries, by function:** `glue_objects` (dev 27, fuzz 1,697, zero 2, scope 13, cert 72: term_live
  :720 sends a non-eq atom to Python's `glue_objects`). On scope only: also `with_closed_units` 518, `relation_atom` 397,
  `_is_number` 392, `_under_apps` 11, `_key` 8 and `_structural_subterms` 4. The counts are equal on a8a4bae.

## Module count (STATUS "Counted modules", 14 of 32)
**14 of 32, unchanged.** lra_adapter.py: nothing claimed (above).
- **relations.py** is on STATUS's list (adapters B+C1 4dd2ed9). **Finding for the planner:** at a8a4bae and 8ee1fac alike,
  relations.py's own Python runs on converted queries: `glue_objects` on five workloads (from term_live.py :720's non-eq
  branch, `py(atom, specs, memo)`), and scope's six functions above. I didn't recount; this is to check against the count
  rule.
- **engine.py** stays out for the reasons port-5c10d.md :165-177 gives by line. Among them are the three relations.py sites,
  which this part didn't move (relations_core.rs :1665-1666 still sets `rel.xfer` and `s.xfer`; query.rs :116-117,
  context.rs :269-271, compile_loop.rs :98/:383 and session_glue.rs :37-68 read and write `s.solver` and `s.xfer`).
  Session.xfer and Session.solver stay with part 3 (they didn't come free here).

## Which moved items are reached, and by what
- `Reader.integer_form`'s not-an-Expr branch: scope only (4). The suite doesn't reach it (plant fired 0 across 7 files).
  test_lra_slot.py's `not_expr` case reaches it directly.
- Nothing else moved.

## Per-call `getattr` guards added in the adapter slots
**0 added.** The `Expr` class is looked up once per process (`PyOnceLock`, adapters.rs `EXPR`). The branch adds one
`isinstance` per `integer_form` slot miss and no `getattr`.

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
Out-of-scope: dev 24/1,985 (1.21%), every other workload 0. Refused: 0 everywhere. No other named exception. All equal to
base.

## Fallbacks to Python inside ported code (planner's fallback-reporting ruling)
`ad:cbm_noid`: **0 on all seven workloads** (scope 4 → 0). dispatch.rs:242 (`registry:python`) and rows_tpl.rs (`rows:python`),
per template, from the bar's knowledge files (`fbcounts.py`). **Every count equals the state-memoized bar's**:
- dev: 126 (`_load` 68, `_unary.<locals>.template` 31, `symbol_units` 15, `constant_units` 12) / 625 (`Integer` 256,
  `const_value` 256, `_mul_factor_sets` 36, `_half_split` 20, `_quotient_templates` 19, `_bound_split` 18, `_imag_split` 11,
  `Add` 6, `Mul` 3);
- fuzz: 38 (`_load` 30, `constant_units` 6, `symbol_units` 2) / 378 (`Integer` 136, `const_value` 136, `_bound_split`,
  `_half_split`, `_imag_split` 34 each, `_mul_factor_sets` 2, `_quotient_templates` 2);
- zero: 43 / 119; loop: 31 / 161; cert: 24 / 208; scope: 26 (`_load`) / 0; budget: 469 (`symbol_units` 450, `_load` 19) / 80.
  Per-template splits are as in port-state-memoized.md's table, and the full rows are in
  `~/sa-rust-ids-work/sa-port-200/bar/counts.txt`.
- `registry:kept`: dev 4 (`add_rows_templates` 2, `mul_rows_templates` 2), 0 elsewhere.

## State: each container this step touches
| container | decision | inventory row |
|---|---|---|
| the adapter's per-query slot (`LraQuery`) | unchanged (Rust-native since part 1). A not-an-Expr answer is stored and exported like any other entry | tsv "state: LraAdapter slot" |
| Relations' dicts, Session.xfer/solver | **not moved** (sub-parts (ii)/(iii), handed off) | INVENTORY-state.md :172-187, :302-311 |

**Snapshot digest at the switch:** test_lra_slot.py's slot digest equals lra_live's (`same_digest` true, in the bar's tests
phase and on orion). Its queries have no int side, so the not-an-Expr branch adds no entries there. The test's `not_expr`
case checks that branch directly, and the bar's live state comparison MATCHes on all seven workloads, scope included.

## Not run
Moved to "before any backend PR", none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the boundary
rescore and suite column; the final drop score and its lost rows; the suite split with Python's counter; `order:_rows`'
evidence (not caught meanwhile); the `_forms` guard test; history and seed reruns (seed1 not run); forced moves; the native
path; timing.
Also not run: the group-D samples (above); sub-parts (ii) and (iii), with their plants, read-only views and snapshot export.

Other notes:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
- `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`: the known id()-reuse
  failure (a28c548), unedited.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the
  boundary suite column wasn't run.
- **Speed not measured.**

# State step, part 2, sub-part (ii): the transfer sites (issue 323), LANDED 9e10f0d

Work by sa-port-202 (code) and sa-port-205 (checks, bar). The planner said to stack it with 6i(a), so (ii) is barred on top of
sa-port-204's tested b11b5a2 (no shared files). 204 landed b11b5a2 unchanged (693fef9 = b11b5a2 + its results/ commit), and
sa-port-207 landed (ii) right after, at 13:47Z 9 Nov (week 88%).

## What moved
session.rs `SessionCore` holds `solver` (copied at TableView.bind), `session_xfer` (Session.xfer) and a per-Relations record of
`xfer`/`xfer_sel`/`_xadapter`. relations_core.rs's transfer sites (engage_transfer, transfer_terms, xswitch, sync_transfer,
congruent, rel_process, every `Cx::solver` user), query.rs/context.rs's s.xfer and session_glue.rs's five xfer_sel reads all
use the core. Python reads go through views (session_live.py `_xfer_get`, `_rel_xview`), and its writes go to the counted
record methods (`set_xfer_rel`, `set_xfer_field`). Session.solver still has a Python copy for its other 13 Rust sites and its
Python readers (part 3). Counters 338-343 xf:*, plants 257-262 xf-*, test_xfer_core.py (new).

## SHAs
Tested **997a54f** (port/state-relations-stack: b38add7 = 19d5d04's code + 202's handoff, on 6i(a) b11b5a2, on rust-slice
c3d0999). **Landed 9e10f0d** on rust-slice (bar.sh land 997a54f, guard diff empty). Incoming diff (b11b5a2..693fef9):
rust-spike/slice/results/port-6i-a.md only (213 lines added), no code, so no rerun (rebase rule).

## The bar (pareto1 `~/sp19/sa-rust-ids-work/sa-port-205/bar-state-relations-ii`, 12:05Z-13:27Z, every phase exit 0, seed1 not run)
.so sha256 8255530b…. Base rows: sa-port-200's bar-state-relations-i/suite.
1. **Suite by id:** 5,991 passed (5,990 with no firing, 1 with a firing: test_ci_stream_reports_only_what_replays, the named
   case), 127 failed, 23 skipped, 18 xfailed, over 6,159 ids. **New 0, gone 0, changed 0.** Tests phase: 693 passed, 4
   skipped.
2. **dev and fuzz: answers and state MATCH** (traced and untraced; Python-Python control MATCH), dev 31cd0945c07f02a6, fuzz
   173502b6ef285ad6. loop, zero, cert, scope and budget all MATCH.
3. **Plants caught:** xf-solver-fresh on dev, fuzz, budget, cert, loop, scope and zero; xf-sel-none on dev, fuzz and zero;
   ad-lra-kind-key and ad-lra-pair-swap as before; xf-rel-view-none on the suite (test_scope.py::test_glue_and_transfer_exist_
   from_construction and test_switched_glue.py::test_set_glue_at_the_root fail under it). Void on the workloads, and caught
   directly by test_xfer_core.py: xf-session-none, xf-rel-any, xf-traverse-skip (each fires on the workloads, but no answer or
   state moves). ad-lra-not-expr is void as in (i), caught by test_lra_slot.py.
4. **Handler multiset same as base** (39 rows in 2 tests: 34 + 4 `_consistent` AttributeError in
   test_ci_stream_reports_only_what_replays, and 1 `_build_context` "Already mutably borrowed" in test_protocol_on_fuzz).
   **ctx:caught 0 on all seven workloads.** TermFault in pytest.log 0; live and extra handler files 0 rows.
5. Known differences: none.

## Counters on the workloads (Rust run)
xf:record 0 and xf:session_view/xf:rel_view 0 on all seven (Python reads no view on any workload). xf:read_core: dev 4,315,
fuzz 58,027, zero 18,427, loop 1,437, scope 1,457, cert 615, budget 52. xf:engage_core equals rel:engage_transfer (dev 35, fuzz
911, zero 550, scope 11). Reached by: dev, fuzz, zero, scope (engagement) and all seven (reads).
**ad:cbm_noid 0 on all seven**; `integer_form` 0 outside kept paths (ad:lra_not_expr: scope 4, native).
dispatch.rs:242 / rows_tpl.rs:413 per template: **every count equals (i)'s table above** (dev 126/625, fuzz 38/378, zero
43/119, loop 31/161, cert 24/208, scope 26/0, budget 469/80; registry:kept dev 4). Rows: bar dir fb.txt and counts.txt.
Kept shares: out-of-scope dev 24/1,985 (1.21%), 0 elsewhere; refused 0; equal to base.
getattr guards in the adapter slots: 0 added. session_glue's xfer_sel reads now do one `core_of` per call (s.table + .core).

## State decisions
| container | decision | inventory row |
|---|---|---|
| Session.xfer | Rust-native in SessionCore; Python view | INVENTORY-state.md :302-311 (relations.py:1689 writer) |
| Relations.xfer / xfer_sel / _xadapter | Rust-native per-Relations record; Python views, counted record writes | :172-187 |
| Session.solver | core holds a copy; Python's attribute stays for its other readers (part 3) | :302-311 |
Snapshot digest at the switch: the live state comparison (end states, traced) MATCHes on all seven workloads. No separate
export digest was taken for these three handles; test_xfer_core.py pins the write sequence field by field.

## Group D
Sample counts, not timings (shared lease, pareto1; sa-port-146's method, tools/sum202.py). Relations path (a)+(b)+(c)+(d):
| tree | dev | fuzz | of which transfer sites (a'), dev / fuzz |
|---|---|---|---|
| BEFORE c3d0999 (sa-port-202) | 530/7,620 = 7.0% | 2,969/19,348 = 15.3% | 18 (0.2%) / 139 (0.7%) |
| AFTER 9e10f0d, landed (ii) (sa-port-207) | 578/8,542 = 6.8% | 3,323/21,859 = 15.2% | 18 (0.2%) / 161 (0.7%) |
Flat, as expected: (ii) moved three handles into the core, not a hot loop. The largest (b) callback on both is still term_live's
`_relation_atom` (dev 87, fuzz 548), then `_under_apps`, `_rel_m`. dev digest 31cd0945c07f02a6 on every AFTER row. Rows:
orion ~/sa-rust-ids-work/sa-port-207/gd/run-9e10f0d/SUMMARY-rel.md.

## Not run
seed1; and the "before any backend PR" list as in (i) (mutants 2, 5, 6, 7, 9 and mutlive's control, boundary
rescore and suite column, final drop score, suite split with Python's counter, order:_rows' evidence (not caught meanwhile),
the _forms guard test, history and seed reruns, forced moves, native path, timing). S's standing: S's gate is met except for
the 46 named stub failures, one cause. `_n_conflicts` view: test-plugin shim (64 tests). test_equality_sharing_is_needed_and_works
is still needs-internals, unedited. test_public_comparison_catches_a_planted_history_dependence is the known id()-reuse
failure (a28c548). Speed not measured.

# Sub-part (iii), first part: relations.py's per-query Python on converted queries (issue 323), LANDED cac82a9

Work by sa-port-205 (code, first bar) and sa-port-207 (fix, second bar, landing). Stacked on (ii).

## What moved
- relations_core.rs `glue_objects_plain` (relations.py:1994's glue_objects without its eq branch). budget.rs's cone kids call
  it for every relation atom except a two-sided eq, which keeps term_live's ids path. While relations run on Python
  (SLICE_REL=py: rel_install hasn't run), budget.rs keeps Python's glue_objects for every relation atom (`installed()`,
  relations_core.rs). Counter 344 gl:plain, plant 263 gl-plain-no-link.
- session_live's install rewraps a default engine built before the install (scope_wl builds one while its queries load)
  on Rust's `with_closed_units`; its undo puts Python's back.

## SHAs
First bar on 83affaa (pareto1 `~/sp19/sa-rust-ids-work/sa-port-205/bar-state-relations-iii1`): suite, live, plants and extra
clean, but **its tests phase failed 4** in test_relations_core.py. Three of them were "relations_core: rel_install hasn't run":
budget.rs called glue_objects_plain in SLICE_REL=py runs. The fourth was test_module_function_plant_is_seen[terms-of-no-order]:
the module-function comparison had lost its only ordered `_terms_of` caller, Python's glue_objects of an `lt`. Fixed in
ce1092c. budget.rs got the `installed()` check. terms-of-no-order is void on the glue sets, because order_sides adds terms
only for an `oo` summand, which is a side already. So it moved from that parametrize list to test_glue_plain.py, which
compares Python's `_terms_of` with relations_core's on `lt` atoms with an `oo` summand, and it is caught there.
**Tested ce1092c** (port/state-relations-iii, rebased on 9e10f0d). **Landed cac82a9** (14:45Z, week 89%). Incoming diff
9e10f0d..rust-slice at landing: none (rust-slice was 9e10f0d).

## The bar (pareto1 `~/sp19/sa-rust-ids-work/sa-port-207/bar-state-relations-iii1b`, 13:47Z-14:44Z, every phase exit 0, seed1 not run)
.so sha256 d5c84c1d…. Base rows: the (ii) bar's suite (= landed 9e10f0d's tested source).
1. **Suite by id:** 5,991 passed (5,990 with no firing, 1 with a firing: test_ci_stream_reports_only_what_replays, the named
   case), 127 failed, 23 skipped, 18 xfailed, 6,159 ids. **New 0, gone 0, changed 0.** Tests phase 696 passed, 4 skipped.
2. **dev and fuzz MATCH** (answers and state, traced and untraced, Python-Python control MATCH): dev 31cd0945c07f02a6, fuzz
   173502b6ef285ad6; loop, zero, cert, scope (12e06b0586faee40) and budget MATCH.
3. **Plants:** the table is identical to the 83affaa bar's (same fire counts and verdicts). Caught: xf-solver-fresh on all
   seven, xf-sel-none (dev, fuzz, zero), ad-lra-kind-key, ad-lra-pair-swap, xf-rel-view-none (suite, 2 tests).
   **Void on the workloads:** gl-plain-no-link (dev 31, fuzz 3,187, cert 72, scope 18, zero 2 fired; caught by
   test_glue_plain.py), terms-of-no-order (glue sets; caught by test_glue_plain.py), xf-session-none, xf-rel-any and
   xf-traverse-skip (caught by test_xfer_core.py), ad-lra-not-expr (caught by test_lra_slot.py).
4. **Handler multiset same as base**: 34 + 4 `_consistent` AttributeError in test_ci_stream_reports_only_what_replays, and 1
   `_build_context` "Already mutably borrowed" in test_protocol_on_fuzz (the named 46-stub cause). **ctx:caught 0 on all
   seven.** TermFault 0. Live and extra handler files have 0 rows outside plant runs.
5. Known differences: none.

## Counters, fallbacks, kept shares (Rust run, bar dir counts.txt and fb.txt)
| wl | ad:cbm_noid | integer_form outside kept (ad:lra_not_expr) | gl:plain | xf:record |
|---|---|---|---|---|
| dev | 0 | 0 | 27 | 0 |
| fuzz | 0 | 0 | 1,697 | 0 |
| zero | 0 | 0 | 2 | 0 |
| loop | 0 | 0 | 0 | 0 |
| cert | 0 | 0 | 72 | 0 |
| scope | 0 | 0 (4 on the native not-an-Expr path) | 13 | 0 |
| budget | 0 | 0 | 0 | 0 |
dispatch.rs:242 (registry:python) / rows_tpl.rs:413 (rows:python) per template: **every count equals (ii)'s** (dev 126/625,
fuzz 38/378, zero 43/119, loop 31/161, cert 24/208, scope 26/0, budget 469/80; registry:kept dev 4: add_rows_templates 2,
mul_rows_templates 2). Kept shares: out-of-scope dev 24/1,985 (1.21%), 0 elsewhere; refused 0; equal to base.
Reached: glue_objects_plain by dev, fuzz, zero, cert and scope; the rewrap by scope (the only workload that builds its
default engine before the install). getattr guards added in the adapter slots: 0.
Scope MATCH still rests on live.py's old install order (the default engine is built before backend.install()). sa-port-209's
harness fix changes that.

## Module-wide relations.py probe (pycalls.py, every function in the file, converted queries)
0 on dev, fuzz, zero, loop, cert and budget. On scope (with_closed_units 518 and glue_objects 13 are now 0), what is left,
by caller (cProfile):
- relation_atom 385 <- scope_wl.py:29's extension lambda. scope_wl imports `relation_atom` from relations at import time,
  before term_live's install patches the module attribute, so the user's fact builder calls Python's original directly;
- relation_atom 12, _is_number 392, _under_apps 11, _key 8, _structural_subterms 4 <- term_live's wrappers falling back,
  all for a plain Python `int` side (term:unknown:link:int 127, key:int 4, relation_atom:int 12; the extension's
  `relation_atom('lt', s, 1)`). Python's semantics for an int differ from Integer's (`_is_number(1)` is False, and
  `_under_apps` and `_structural_subterms` skip non-Basic sides), so it can't be given a number id.
**relations.py stays off the counted list.** These two are the rest of (iii)(a).

## Not run
seed1; the "before any backend PR" list as in (i). S's standing: S's gate is met except for the 46 named stub failures, one
cause. `_n_conflicts` view: test-plugin shim (64 tests). test_equality_sharing_is_needed_and_works is still needs-internals,
unedited. test_public_comparison_catches_a_planted_history_dependence is the known id()-reuse failure (a28c548). Speed not
measured. Group-D after (iii) part 1 not run.

# Sub-part (iii)(a) and (iii)(b) first move (issue 323), LANDED c822173 (tested 022630c, report 5a3c218)

Header corrected by sa-port-240: the text below was written before the bar. The bar ran on 022630c (pareto1
`~/sp19/sa-rust-ids-work/sa-port-217/bar-state-relations-iii-ab`, clean) and the step landed as c822173 at 06:09Z 10 Nov;
the five items are in report 5a3c218 (suite 5,990 passed: 5,989 with no firing and 1 with a firing; 128 failed; 0 new, 0
gone, 2 changed: test_module_state_inventory_is_classified, fixed in c822173 by classing `RELATION_ATOM_IMPL` as
configuration in harness/state.py, and the planted-history test, a28c548).

Work by sa-port-211 ((a)) and sa-port-213 (rebase, (b)'s first move). Branch port/state-relations-iii, head carries this
section; code at 6ed06b9, rebased on rust-slice 80665b5 (S2). Incoming diff cac82a9..80665b5: S2 (block.rs rule tables,
session.rs, test_rule_tables.py; 12 files, +773/-19), which the run executes, so the bar must be run on the rebased source.

## What moved
- (a) f7e5f24 -> a5f57ce: `relations.relation_atom` dispatches itself through `RELATION_ATOM_IMPL` at call time (planner Q1),
  test_term_ids.py::test_a_name_imported_before_install_dispatches. e025aa5 -> f593984: a plain Python int side is a foreign
  leaf in Rust's term table (`Kind::PyInt`), plant 265 int-as-number, counter 346 term:int:*.
- (b), first move, 7899a6a + 6ed06b9: Relations' seven scalar cursors (`_xtcur`, `_xhn`, `_xhseen`, `_xslot`, `_xterm`,
  `_xnsides`, `_xsides_n`) held in session.rs `SessionCore.relc` (`RelC`, `RC_NAMES`, `RC_INIT`). rel_init writes the core
  (a session with no core keeps Python's attributes); relations_core.rs `_transfer_terms`, `sync_transfer`, `_note_sides`
  read/write the core natively. Python reads through views (session_live `_rel_cview`); writes go to the record method
  `set_relc_field`; test-only export `relc_snapshot`. Counters 347 rc:core, 348 rc:view, 349 rc:record; plants 266
  rc-xterm-stale, 267 rc-hseen-stale, 268 rc-xslot-skip.

## State decision for each container moved
| container | inventory row (HANDOFF-sa-port-205 census) | decision |
|---|---|---|
| `_xtcur`, `_xhn`, `_xhseen`, `_xslot`, `_xterm`, `_xnsides`, `_xsides_n` | relations_core.rs 2-6 sites, relations.py only, no engine or wiring reader; tests: test_relations_core.py `_rel_state` (cursors), `rc` side writes `_xsides_n += 1` | Rust-native in the core; views for Python (relations.py under SLICE_REL=py, the tests) |
Snapshot digest at the switch (test_relc_core.py): Rust's `relc_snapshot` export = Python's own attributes,
995403f1a00b2735 on both, 469 queries (transfer:7:60, transfer2:3:40, fuzz[:200], scope), 445 rows with moved cursors.
The views read the same values; no cursor is left in `rel.__dict__` on Rust. test_relations_core.py passes unedited.
The 30 dict/set/list fields are not moved yet (see HANDOFF-sa-port-213.md).

## Checks run (orion, ~/sa-rust-ids-work/sa-port-213/pl1, not the bar)
- Unplanted Rust at 7899a6a: dev MATCH (31cd0945c07f02a6, 1,985 queries, end/stream/lra/stats 0), fuzz MATCH
  (173502b6ef285ad6, 3,000). Python solvers made on Rust 0.
- Plants: rc-xslot-skip caught on fuzz (end 88, stream 88, lra 8, answers same), void on dev. rc-xterm-stale and
  rc-hseen-stale void on dev and fuzz (they only drop idempotence guards: the repeated work changes nothing visible); caught
  by test_relc_core.py (each moves the digest). Transfer is reached on dev (35 engagements), fuzz (911), zero (550), scope (11)
  (iii1b bar counts).
- Tests (orion, after the rebase): test_term_ids, test_relations_core, test_glue_plain, test_scope_core, test_rule_tables
  285 passed; with (b): test_relations_core, test_xfer_core, test_glue_plain, test_scope_core, test_term_ids, test_query_core
  291 passed; test_relc_core.py 5 passed.

## Not run
The bar (config ready: pareto1 ~/sp19/sa-rust-ids-work/sa-port-213/run-bar-iii-ab.sh, bar.sh as bar-sa-port-213.sh); hence no
suite numbers, handler multiset, ctx:caught, fallback rows, kept shares or ad:cbm_noid/integer_form rows for this source.
Group-D before/after. The module-wide relations.py probe after (b) (sa-port-211's at e025aa5: 0 on six workloads, scope 385
all the dispatch frame, which the planner ruled public entry ~15:05 9 Nov, addenda/sa-port-relations-entry-ruling.txt).
seed1 and the "before any backend PR" list. Speed. Scope's MATCH still rests on live.py's old install order (sa-port-209's
harness fix is unlanded). getattr guards added in adapter slots: 0.

# Sub-part (iii)(b) rest and (iii)(c) (issue 323), LANDED 3203cb4 (tested ba1ca22)

Work by sa-port-221 (RelKeys, the nine sets), sa-port-222 and sa-port-225 (dicts, lists, first bar), sa-port-228 (first
finding, serial), sa-port-232 (second bar read, replays), sa-port-236 (cause, fix), sa-port-237 (third bar, landing) and
sa-port-240 (this section, group D, probe, ownership rows). No code after ba1ca22.

## SHAs
- **Tested ba1ca22. Landed 3203cb4** on rust-slice at 15:09:50Z 10 Nov (`PUSH=1 bash rust-spike/slice/p1/bar.sh land ba1ca22`),
  59e9d15..3203cb4. **Incoming diff** 59e9d15..origin/rust-slice at the landing: **empty**. The landing source differs from the
  tested one by HANDOFF-sa-port-236.md only (no guarded source), so no rerun was owed.
- Earlier tested SHAs, not landed: 1a6d38a (first bar, not clean), 0576370 (second bar, not clean).

## What moved
- `RelKeys` in SessionCore (relkeys.rs, session.rs :672), holding strong refs, per the RelKeys ruling: a key with a term id in
  the query's table takes that id; any other key is interned by hash and `==`, counted by origin (rk:intern:input,
  rk:intern:engine).
- Relations' **nine sets** (`RS_NAMES`: linked, _bounded, _user_eq, _xpairs, _aux_eq, _link_eq, _xpart, _xcounted, _xcand),
  **15 dicts** (`RD_NAMES`: adapters, status, _guards, _link_lt, top, link_sel, atom_sel, num_sel, _roles, _info, _link_of,
  _tv, _tsrc, _xside, _xheads; insertion-ordered `OrdMap`) and **four lists** (`RL_NAMES`: queue, _pending_links, _xextra,
  _xpend; `Vec` in `RelS.l`) are Rust-native in the core. Python reads through `RelSetView`, `RelDictView`, `RelListView`
  (session_live `_rel_sview`, `_rel_dview`, `_rel_lview`); writes go through the record methods (`set_rs_init`, `set_rd`,
  `set_rl`); test-only exports `rs_snapshot`, `rd_snapshot`, `rl_snapshot`.
- Counters 350-359 (rk:*, rs:core/view/record, rk:dict:hit, rk:twin), 520-525 (rd:*, rl:*). Plants 269-277 (rs-<set>-drop),
  390-404 (rd-<dict>-drop), 405-408 (rl-<list>-drop), 409 rk-class-split.
- **Shared-file changes, named:** satassume/relations.py :949-952 (`top, self.top = self.top, {}` became
  `top = list(self.top); self.top.clear()`: under the core `top` is a view, so the rebind emptied the held `top` too; the same
  for a plain dict); solver_rs/src/term/py.rs (`PyTermTable`'s process-wide serial, the first finding's fix);
  session_live.py (the views, and the plants' names in `_REL_STATE_PLANTS`, `rk-class-split` at :1001; sa-port-230 owns the
  file). None of the nine cbm_noid identity sites is touched; term_live.py:292 is unchanged.

## State decision for each container moved
| container | inventory row | decision |
|---|---|---|
| the nine sets (relations.py :805-869) | INVENTORY-state.md :172-187 (Relations' containers) | Rust-native in the core, keyed by RelKeys; `RelSetView` for Python |
| the 15 dicts (relations.py :802-866) | :172-187; `adapters` :184 | Rust-native, `OrdMap` in Python's dict order (a re-set keeps its place, a delete then set goes last); `RelDictView` (len, in, [], get, keys, values, items) for engine.py :1086-1129 and ref.py; default specs hold the Rust adapters, a user spec's Python adapter is the named user-spec exception (ad:cb_factory) |
| queue, _pending_links, _xextra, _xpend (:804, :812, :825, :868) | :172-187 | **Rust-native, `Vec` in `RelS.l`**; `RelListView`; engine.py :1177 and ref.py :416 test `rel.queue` for truth, ref.py :409 and engine.py :726 call `rel.enqueue` (Rust's rel_enqueue) |
| specs (:801) | :172-187 | **Python, configuration**: the default specs or a user's, never written after `__init__`, read only by iteration (relations_core.rs :1250/:1365/:1717) |
**Snapshot digest equal at the switch:** test_rs_core.py (the nine sets, `rs_snapshot` against Python's sets), test_rd_core.py
(the 15 dicts, 469 queries, items in insertion order, adapters compared by class name), test_rl_core.py (lists sampled at
every `_interpret`/`_link` call and at the end, with dicts and sets: 74b52f3903b5236b on both, 469 queries, each list seen
non-empty: queue 2,864, _pending_links 2,265, _xextra 369, _xpend 619). Tests that read internals (test_relations.py:209,
test_switched_glue.py:136-138, test_verify_integration.py:72) pass through the views unedited; none was added to
needs-internals. **The bar's own state comparison does not read these containers** (see condition (3) below).

## The three bars
### First bar, 1a6d38a: not clean (pareto1 ~/sp19/sa-rust-ids-work/sa-port-225/bar-iii-b)
Suite 5,989 passed / 129 failed; changed 3: test_history.py::test_module_state_inventory_is_classified failed -> passed
(c822173's fix), and **tests/test_scope.py::test_answers_agree_with_the_lazy_order and
::test_zero_twins_are_in_the_scope passed -> failed** (None where True is expected), in all five suite runs. All seven
workloads MATCHed; handler multiset same as base.
- **sa-port-228's reading:** RelKeys kept the query table's **address** to notice a session outliving its query; a dead
  table's address is reused by the next table, so old term ids would be read as the new table's.
- **Fix 0576370:** `PyTermTable` carries a process-wide serial (solver_rs/src/term/py.rs, shared file); RelKeys compares the
  serial (`RelKeys.table: Option<u64>`).
- **Control on the 1a6d38a build** (pareto1, scripts/rk_alias.py): a new table at the dead one's address, both symbols id 4,
  `b in rel._xcand` True and `a in rel._xcand` False; on the fixed build False, True, rk:outlive +1, rk:migrate +1.
- **Test:** test_rs_core.py::test_a_later_table_at_a_dead_tables_address_is_a_second_table (forces the reuse and asserts it
  was reached).
- **That reading was not the cause of the two failures** (below). The hazard is real as a built case, so the serial stays.

### Second bar, 0576370: not clean (pareto1 ~/sp19/sa-rust-ids-work/sa-port-228/bar-iii-b2)
Suite 5,983 passed (5,982 + 1 with a firing) / 135 failed; changed 9, all passed -> failed: **eight zero-twin answers**
(test_scope's two; test_ref.py::test_zero_under_an_application_is_an_equality[T1-transfer-congruent-application],
[T2-transfer-raise], [T4-transfer-two-zero-terms], [query-twin]; test_zero_glue.py::test_zero_in_the_set_is_an_equality[G5-default],
[G5-whole]) **plus the planted-history test**. The lost set differed per suite run. In the failing replays **rk:outlive 0 and
rk:migrate 0**: no session met a second table, so address reuse was not the cause. **All seven workloads MATCHed on both
bars while the suite lost answers:** no workload holds two equal classes.

### The real cause, and the fix ba1ca22
- **Cause: two equal `Function("f")` classes in one query.** Class A is made at import (knowledge/templates/_rows.py:166) and
  held by tests/test_ref.py's module constants. SymPy's lru cache later evicts `Function("f")`; the next `Function('f')` is a
  second class B, `==` to A and hashing alike (in the failing order made by harness/sympy_io.py:136 `from_srepr`). After a
  registry restore, process-wide memos keep B's objects, and a later query with A's objects meets both. The table gives a
  row only to its own class (term_live.py:292), so B's `f(0)` has no term id; RelKeys interned it by hash **beside** A's
  term-id key. **RelKeys split `_tv`'s keys** (`f(u)`, `f(0)` twice); the nine sets stayed equal to Python's. Python's dict
  held one member: Python True, Rust None.
- **Fix:** relkeys.rs `twin_row` (:98): when `term_of` has no id, the row of an `==` object of an equal, not identical, class
  in the query's own table; `rk_key` (:123) takes its id. Counter 359 **rk:twin**. Plant 409 **rk-class-split** (no
  equal-class row, RelKeys as on 0576370).
- **Control:** test_rs_core.py::test_two_equal_function_classes_key_as_one **fails on the 0576370 build** (old .so swapped
  in, orion ~/sa-rust-ids-work/sa-port-236/control-0576370.txt, at the answer assert).
- **Tests:** test_rs_core.py::test_two_equal_function_classes_key_as_one and ::test_class_split_plant_is_caught.
- **The first bar's two test_scope failures were this cause, not address reuse:** they failed again on 0576370 and pass on
  ba1ca22.
- `twin_row` adds 2 to 5 Python reads per key lookup of a Basic with no own-class row (`q.ids`, `.get`, on a hit
  `q.objects[i]`, `q.table`). These are not adapter slots.

### Third bar, ba1ca22: clean (pareto1 ~/sp19/sa-rust-ids-work/sa-port-236/bar-iii-b3, 12:11Z-15:04Z, every phase exit 0, seed1 not run)
.so sha256 fde4414dfab0…. Base rows: sa-port-219's stack bar suite (= rust-slice 59e9d15's tested source).
1. **Suite by id:** 5,992 passed (**5,991 with no firing, 1 with a firing**: test_ci_stream_reports_only_what_replays), 126
   failed, 23 skipped, 18 xfailed, 6,159 ids. **New 0, gone 0, changed 0.** All eight zero-twin ids pass. Tests phase 927
   passed, 4 skipped.
2. **dev and fuzz MATCH** (answers and end/stream/lra/stats 0, traced and untraced, Python-Python control MATCH): dev
   31cd0945c07f02a6 (1,985), fuzz 173502b6ef285ad6 (3,000); loop, zero, cert, scope (12e06b0586faee40), budget MATCH.
   Python solvers made on Rust: 0.
3. **Plants** (46 x 7 workloads; fired count, then D = DIFFER (caught), M = MATCH). The 17 older plants: caught
   ad-lra-kind-key, ad-lra-pair-swap, rc-xslot-skip (fuzz, zero), xf-sel-none, xf-solver-fresh (all seven), int-as-number
   (scope). The state plants:

| plant | dev | fuzz | zero | loop | cert | scope | budget |
|---|---|---|---|---|---|---|---|
| rd-adapters-drop | 3,162 D | 80,339 D | 14,049 D | 0 M | 809 D | 1,575 D | 0 M |
| rd-atom_sel-drop | 50 D | 1,831 D | 655 D | 0 M | 0 M | 22 D | 0 M |
| rd-guards-drop | 1,870 M | 45,802 M | 7,011 D | 0 M | 455 M | 875 M | 0 M |
| rd-info-drop | 1,501 D | 36,397 D | 6,278 D | 0 M | 374 M | 701 M | 0 M |
| rd-link_lt-drop | 750 D | 18,810 D | 3,466 D | 0 M | 162 D | 348 D | 0 M |
| rd-link_of-drop | 636 D | 9,765 D | 2,166 D | 0 M | 183 D | 387 D | 0 M |
| rd-link_sel-drop | 375 D | 9,421 D | 1,903 D | 0 M | 81 D | 174 D | 0 M |
| rd-num_sel-drop | 87 D | 322 D | 0 M | 0 M | 101 D | 0 M | 0 M |
| rd-roles-drop | 1,298 D | 31,657 D | 6,811 D | 0 M | 253 D | 539 D | 0 M |
| rd-status-drop | 1,501 D | 36,397 D | 6,278 D | 0 M | 374 M | 701 D | 0 M |
| rd-top-drop | 458 D | 5,463 D | 2,123 D | 0 M | 212 D | 156 D | 0 M |
| rd-tsrc-drop | 3,466 D | 103,171 D | 17,400 D | 0 M | 718 D | 1,545 D | 0 M |
| rd-tv-drop | 732 D | 17,688 D | 9,085 D | 0 M | 40 D | 54 D | 0 M |
| rd-xheads-drop | 15 M | 3,871 D | 1,512 D | 0 M | 0 M | 0 M | 0 M |
| rd-xside-drop | 872 D | 22,438 D | 5,224 D | 0 M | 162 M | 370 D | 0 M |
| rk-class-split | 0 M | 0 M | 0 M | 0 M | 0 M | 0 M | 0 M |
| rl-pending_links-drop | 375 D | 9,421 D | 1,903 D | 0 M | 81 D | 174 D | 0 M |
| rl-queue-drop | 1,187 D | 21,333 D | 5,287 D | 0 M | 364 D | 619 D | 0 M |
| rl-xextra-drop | 87 M | 322 M | 0 M | 0 M | 101 M | 0 M | 0 M |
| rl-xpend-drop | 128 D | 5,736 D | 2,423 D | 0 M | 0 M | 11 D | 0 M |
| rs-aux_eq-drop | 500 D | 11,848 D | 2,341 D | 0 M | 91 M | 191 D | 0 M |
| rs-bounded-drop | 0 M | 0 M | 0 M | 0 M | 0 M | 0 M | 0 M |
| rs-link_eq-drop | 372 D | 9,367 D | 1,328 D | 0 M | 81 M | 174 D | 0 M |
| rs-linked-drop | 715 D | 13,704 D | 2,648 D | 0 M | 243 D | 193 D | 0 M |
| rs-user_eq-drop | 38 D | 888 M | 822 M | 0 M | 0 M | 0 M | 0 M |
| rs-xcand-drop | 50 M | 1,918 D | 797 M | 0 M | 0 M | 11 M | 0 M |
| rs-xcounted-drop | 15 M | 3,876 M | 1,512 M | 0 M | 0 M | 0 M | 0 M |
| rs-xpairs-drop | 0 M | 4,923 D | 242 D | 0 M | 0 M | 0 M | 0 M |
| rs-xpart-drop | 81 D | 3,936 D | 1,907 D | 0 M | 0 M | 12 D | 0 M |
   - **Void, fired 0 on all seven:** rk-class-split (caught on the suite), rs-bounded-drop (0 in the suite too),
     xf-rel-view-none (caught on the suite: 2 tests, 461 firings), int-as-number by plant_fired (its counter is term:int:*).
   - **Void as a workload check, fired but MATCH everywhere (each caught by its unit test):** ad-lra-flag-key,
     ad-lra-not-expr (scope 4), ad-lra-patch-guard, ad-lra-slot-stale, gl-plain-no-link, rc-hseen-stale, rc-xterm-stale,
     rl-xextra-drop, rs-xcounted-drop, xf-rel-any, xf-session-none, xf-traverse-skip.
   - **Suite plants:** rk-class-split fired 692 and loses 10 ids (5,982 / 136): test_ref's four zero-under-an-application
     ids, test_relevance's test_common_value_does_not_connect and test_undefined_function_connects, test_scope's two,
     test_zero_glue's test_unrelated_relation_adds_nothing[G1-default] and [G1-whole]. xf-rel-view-none: 2 changed.
     ad-lra-not-expr, int-as-number, rs-bounded-drop fired 0 in the suite: void there too.
4. **Handler multiset same as base:** 39 rows in 2 tests (34 + 4 `_consistent` AttributeError in
   test_ci_stream_reports_only_what_replays; 1 `_build_context` "Already mutably borrowed" in test_protocol_on_fuzz, the
   named 46-stub cause). **engine.py:1906's catches: ctx:caught 0 on all seven workloads, 1 in the suite (= base).**
   TermFault 0.
5. Known differences in answers or read state: none.

**The six 6i workloads (core, f6, opaque, rootof, value, wiring) were not in this bar.** They were run **after the bar,
outside it, without plants**, on the tested tree and .so (pareto1 ~/sp19/sa-rust-ids-work/sa-port-237/extra6): all six
Python-Python MATCH and Python-Rust MATCH, handler rows 0. wiring ended 15:13Z, after the landing. Only `value` reaches
Relations (rel:init 198).

## Which moved items are reached, and by which workload
The plant table's fired column is the reach per container: every moved container except `_bounded` is reached by dev, fuzz
or zero; `_bounded` by none of the seven nor by the suite (its plant is void; test_rs_core.py covers it). loop and budget
reach no Relations (rel:init 0). Of the six 6i workloads only value does. Group counters, Rust run (bar, pareto1
sa-port-237/counts.txt; the same numbers on orion's build in the probe run below):
| wl | rk:term | rk:twin | rk:intern:input | rk:intern:engine | rk:outlive | rk:migrate | ad:cb_factory | ad:cbm_noid | integer_form outside kept (ad:lra_not_expr) | rs:core | rd:core | rl:core | rel:init |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | 8,971 | 0 | 511 | 4,067 | 0 | 0 | 0 | 0 | 0 | 4,358 | 36,057 | 5,481 | 198 |
| fuzz | 217,752 | 0 | 9,539 | 93,286 | 0 | 0 | 0 | 0 | 0 | 131,651 | 904,680 | 127,482 | 3,018 |
| zero | 57,170 | 0 | 1,027 | 18,338 | 0 | 0 | 0 | 0 | 0 | 30,932 | 179,145 | 26,152 | 556 |
| loop | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| cert | 2,699 | 0 | 192 | 902 | 0 | 0 | 0 | 0 | 0 | 1,082 | 8,657 | 1,356 | 61 |
| scope | 2,112 | 0 | 303 | 1,953 | 0 | 0 | 0 | 0 | 0 (4 on the native not-an-Expr path) | 1,503 | 14,161 | 2,509 | 135 |
| budget | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| value (outside the bar) | 2,956 | 0 | 394 | 1,183 | 0 | 0 | 0 | 0 | 0 | not read | not read | not read | 198 |
core, f6, opaque, rootof, wiring: every column 0. rs:view, rs:record, rd:view, rd:record, rl:view, rl:record: 0 on all seven
(no Python reader on the workloads).
- **rk:twin 0 on every workload; 118 in the plain suite** (0 under rk-class-split, with 692 plant firings).
- **Sessions that outlive their query: none.** rk:outlive 0 and rk:migrate 0 on every workload and in the suite.
- **rk:intern:engine** is scaffolding by the RelKeys ruling (formula step for atoms, term-id step for terms), target 0
  before any backend PR.
- **Per-call `getattr` guards in the adapter slots: this part adds 0** (adapters.rs and lra_adapter.py are not in
  59e9d15..ba1ca22's 17 files); none fixed.

## Fallbacks, kept shares
- **ad:cbm_noid: 0 on all seven workloads** (and on the six). **Per suite run:** plain 94; under ad-lra-not-expr 1,011,
  int-as-number 287, rs-bounded-drop 631, rk-class-split 980, xf-rel-view-none 790. Base 19; the 0576370 bar 386; earlier
  19/910/376/208. It varies between runs of one source.
- **Do two equal Function classes move ad:cbm_noid? Yes.** twin6 (the same query asked with class f, then with an equal
  second class g, fresh engines): ad:cbm_noid 0 -> 29 from the second class alone, link:none 0 -> 64, answer still True. On
  twin11: 25 with two classes in one query, 29 when the second class comes alone, 0 with one class. So it moves with class
  identity through SymPy's cache, not with `id()` or addresses in this code. One case, not the whole variance; for the
  planner's cause read.
- **dispatch.rs:242 (registry:python) / rows_tpl.rs:413 (rows:python) per template name**, identical to the base's on the
  seven (pareto1 sa-port-237/fb-cand.txt against fb-base.txt):

| wl | dispatch.rs:242 | rows_tpl.rs:413 |
|---|---|---|
| dev | 95: _load 68, constant_units 12, symbol_units 15 | 521: Add 6, Integer 256, Mul 3, const_value 256 |
| fuzz | 38: _load 30, constant_units 6, symbol_units 2 | 272: Integer 136, const_value 136 |
| zero | 38: _load 29, constant_units 3, symbol_units 6 | 72: Integer 36, const_value 36 |
| loop | 31: _load 20, constant_units 5, symbol_units 6 | 129: Add 6, Integer 60, Mul 3, const_value 60 |
| cert | 24: _load 20, constant_units 1, symbol_units 3 | 208: Integer 104, const_value 104 |
| scope | 33: _load 27, constant_units 2, symbol_units 4 | 64: Integer 32, const_value 32 |
| budget | 469: _load 19, symbol_units 450 | 80: Integer 40, const_value 40 |
  registry:kept dev 4 (add_rows_templates 2, mul_rows_templates 2), 0 elsewhere. The six 6i workloads were not tabulated on
  the candidate (fb-base.txt has the base's rows).
- **scaffold:core:kept_product:mismatch: 0 on all thirteen workloads** (the counter exists on the base; orion probe run on
  the landed build). core:kept_product itself: dev 33, loop 2, core 163 (`:none` 14), f6 82, wiring 10.
- **Kept shares, equal to base:** out-of-scope dev 24/1,985 (1.21%), 0 elsewhere; refused 0 everywhere.

## The planted-history test
tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence is **the known id()-reuse
failure (a28c548)**, not edited. Its failure matches a28c548's signature: the same assertion (`assert len(run_stream(ops))
== 2`, :204), shapes `[]` and `[(1, True, False)]`. It flips both ways on the tested build: passed in the plain suite and
two plant suites, failed in the three inert-plant suites. sa-port-185's sweep on the ba1ca22 build (orion
~/sa-rust-ids-work/sa-port-237/h185): Rust 0/50, Python 46/50, keep-alive 50/50 on both, predict.py 100/100. In the suite's
order with one build (pareto1 sa-port-237/id-rust-{1,2,3}): 1 failed with both address pairs shared, 2 passed with none
shared.

## The planner's (a) to (e)
- **(a)** Reproduction: orion ~/sa-rust-ids-work/sa-port-236/twin11.py (`py` True, True; `rust` on 0576370 True, None) and
  `python test_rs_core.py twin rust`; the split is `_tv`'s keys under the plant.
- **(b)** Eight of the nine ids are this cause (they pass on ba1ca22 in the failing workers' whole orders). The ninth is the
  planted-history test, whose signature matches a28c548.
- **(c)** Test and plant as above. The nine sets' digest alone does not see the plant; the dicts' keys do.
- **(d)** 228's control is a built case, independent of the suite, and still shows the serial is needed: **the serial
  stays.** No replay showed address reuse in the suite.
- **(e)** ad:cbm_noid reported per workload and per suite run above.

## Landing condition (3): the planner's case (b)
The bar's end digest does **not** read Relations' moved containers: live.py :462-477 is `state.with_euf(dump, theories)`
(state.py :182), the solver's dump, each EUF theory's fields and the LRA text. Plant 409 is caught by its direct test and on
the suite (10 ids), not by the workloads' digest. **STATUS footnote text** (for the architect; STATUS.md is not edited
here): "State MATCH on the bars from 5c9a onward has not covered Relations' moved containers: live.py's end digest is the
solver dump, the EUF theories' fields and the LRA text. The nine sets, 15 dicts, 4 lists and 7 cursors are compared with
Python only by test_rs_core.py, test_rd_core.py, test_rl_core.py and test_relc_core.py (digest equal at the switch). Plant
409 rk-class-split is caught by its unit test and on the suite (10 ids), not by the workloads' digest. The next bar (part
3's or the formula step's) carries the digest extension (c931c16) and must catch 409 there." Which containers each landed
step from 5c9a had in the digest is still owed with that extension; for (i), (ii), (iii) part 1, (iii)(a)+(b) first move and
this step: none of Relations'.

## Module-wide relations.py probe on the landed source ((iii)(c))
pycalls.py, every function in satassume/relations.py, orion ~/sa-rust-ids-work/sa-port-240/pyc/landed (clone at 3203cb4's
code, .so sha256 bfc06f0cd68a…, the loaded .so and tree recorded in source.txt and in each run's `so_sha`), 13 workloads:
**converted 0 on all thirteen** (dev, fuzz, zero, loop, cert, budget, scope, core, f6, opaque, rootof, value, wiring). The
only calls: noquery 4 on each (import time: `<module>`, `AdapterSpec`, `Uninterpreted`, `Relations` class bodies) and dev
kept:out-of-scope 110 (`_is_number` 63, `_termwise` 16, `_relation_atom_py` 14, `_key` 12, `_affine_strip` 2,
`_structural_subterms` 2, `glue_objects` 1: kept queries run on Python).
- **Scope's 385 relation_atom calls go to the installed wrapper** (term_live.py:991 rebinds `relations.relation_atom`;
  scope_wl imports after install since the harness fix db7130a), a dispatch frame and public entry by the planner's ruling;
  no relations.py frame runs for them. A name imported before install still dispatches:
  test_term_ids.py::test_a_name_imported_before_install_dispatches. `RELATION_ATOM_IMPL` is classed as configuration in
  harness/state.py `MODULE_CONFIG` (c822173).
- **The suite** (pytest plugin pycalls_suite.py, the same count per test id; pareto1
  ~/sp19/sa-rust-ids-work/sa-port-240/suite-probe, the bar's tested tree ba1ca22 and its .so fde4414dfab0…, Rust, 5,992
  passed / 126 failed as the bar; plugin kept on orion ~/sa-rust-ids-work/sa-port-240/p1): **converted 42, all in one test**,
  tests/test_transfer.py::test_inequalities_restate_an_equality: `_is_number` 18 and `_key` 12 (term_live's `is_number` and
  `key` wrappers falling back), `_relation_atom_py` 6 (term_live's `relation_atom` wrapper falling back) and `_affine_strip`
  6 under it. Why those six atoms fall back on a converted query was **not read** in this link. Other states in the suite:
  noquery 2,944,429 (no query on term_live's stack: tests and Python-side runs outside a Rust query; not split by caller
  here, the per-worker files hold the callers), kept:refused 66,512, kept:non-default-registry 12,888, kept:out-of-scope
  12,290, kept:args-eq-not-is 2,714, kept:sum-product-integral 1,152.
- **Count line: relations.py does not count yet.** The probe is 0 on all thirteen workloads but 42 in the suite, and those
  calls are a fallback inside ported code, not a named callback or conversion. Proposed owner: the formula step
  (sa-port-234), which owns the atoms and term_live's wrapper sites; the first thing to read is which side of that test's
  relations has no term id. The count stays 21.

## Group D (before c822173, after 1a6d38a)
**The after column is 1a6d38a, not the landed SHA**: it is this step before the two fixes (the serial changes one
comparison; `twin_row` adds reads only on a key with no own-class row) and without 6i(b)+(c), which the landed source also
carries. Sample counts, not timings (shared lease, pareto1; sa-port-146's method, tools/sum202.py; dev 10 runs, fuzz 3).
| tree | relations path (a)+(b)+(c)+(d), dev | fuzz | (a) D from relations_core + session_glue, dev / fuzz | D from relkeys, dev / fuzz | all D (C API from Rust), dev / fuzz |
|---|---|---|---|---|---|
| BEFORE c822173 | 1,552/21,138 = 7.3% | 7,844/50,375 = 15.6% | 954 (4.5%) / 4,266 (8.5%) | none (no relkeys.rs) | 5,442 (25.7%) / 18,038 (35.8%) |
| AFTER 1a6d38a | 1,307/19,811 = 6.6% | 5,761/43,273 = 13.3% | 725 (3.7%) / 2,893 (6.7%) | 133 (0.7%) / 719 (1.7%) | 5,075 (25.6%) / 15,309 (35.4%) |
- **sum202.py's (a) does not count relkeys.rs**, where the moved containers' key work now runs. With it, (a) after is
  858 (4.3%) dev / 3,612 (8.3%) fuzz, against 4.5% / 8.5% before: the step moved the containers but most of the C API time stays, because the keys
  and values are still Python objects (hash and `==` of atoms and terms, strong refs).
- relations_core alone: dev 707 (3.3%) -> 516 (2.6%), fuzz 3,823 (7.6%) -> 2,499 (5.8%). (b) callbacks: dev 478 (2.3%) ->
  496 (2.5%), fuzz 2,554 (5.1%) -> 2,126 (4.9%); largest still term_live's `_relation_atom` (dev 156 -> 140, fuzz 1,226 ->
  1,018) and `_under_apps`. (c) SymPy from relations_core: dev 120 -> 86, fuzz 1,024 -> 742. (d) 0.
- **Against sa-port-146's baseline (group D 0.158 s dev / 1.990 s fuzz): not derived.** These runs give shares of samples
  on a shared lease, not seconds; all D is 25.6% of dev's samples and 35.4% of fuzz's after. A seconds figure needs a
  quiet-lease pass with 146's method. Owed.
- **What is left on the relations path, by owner** (my reading of the after tree's sub rows): Session's own containers and
  handles (D from session 248 / 1,082, session_glue 209 / 394, query 145 / 234, context 175 / 214): state part 3,
  sa-port-230. Atoms and terms held as Python objects in RelKeys and relations_core (`term_of`'s attribute lookups, `two`'s
  tuple reads, rk:intern:engine) and the `_relation_atom` callback: the formula step, sa-port-234, for atoms; the term-id
  step for terms. `specs` stays Python (configuration).
Rows: orion ~/sa-rust-ids-work/sa-port-225/gd/run-{c822173,1a6d38a}/SUMMARY-rel.md.

## Not run
seed1; and the "before any backend PR" list as in port-5c10d.md (mutants 2, 5, 6, 7, 9 and mutlive's control, boundary
rescore and suite column, final drop score, suite split with Python's counter, order:_rows' evidence (not caught
meanwhile), the _forms guard test, history and seed reruns, forced moves, native path, timing). Plants on the six 6i
workloads. Group D on the landed source and in seconds. The Python-backend replays id-py-{1,2} were not read. Speed not
measured.
S's standing: S's gate is met except for the 46 named stub failures, one cause. `_n_conflicts` view: test-plugin shim (64
tests). test_equality_sharing_is_needed_and_works is still named needs-internals, unedited. test_term_live.py's 2
`_Mark.facts` failures stand as in the earlier reports (not rerun in this link).
