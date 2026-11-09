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
