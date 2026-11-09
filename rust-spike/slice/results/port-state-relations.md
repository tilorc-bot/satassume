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
