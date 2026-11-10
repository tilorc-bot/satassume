# HANDOFF sa-port-237 (state step part 2, (iii)(b) rest): bar on ba1ca22 read, clean; LANDED 3203cb4 on rust-slice; marker touched; reporting work NOT done. Issue 323

Read HANDOFF-sa-port-236.md (cause, fix) and HANDOFF-sa-port-228.md (the step's map) with this file.
What is left is the reporting work only (the brief's tasks 4 to 7). No code is owed.

## The bar on tested ba1ca22 (pareto1 ~/sp19/sa-rust-ids-work/sa-port-236/bar-iii-b3, 12:11Z-15:04Z, every phase exit 0, seed1 not run)
.so sha256 fde4414dfab0…, tree ~/sp19/dev/sa-port-236-iii. Base rows: sa-port-219's stack bar suite (= rust-slice 59e9d15's
tested source). Copy of sum.txt: orion ~/sa-rust-ids-work/sa-port-237/bar/sum.txt.
1. **Suite by id:** 5,992 passed (5,991 with no firing, 1 with a firing: test_ci_stream_reports_only_what_replays), 126
   failed, 23 skipped, 18 xfailed, 6,159 ids. **New 0, gone 0, changed 0.** All eight zero-twin ids pass, test_scope's two
   among them. Tests phase 927 passed, 4 skipped (test_rs_core, test_rd_core, test_rl_core included). direct.txt exit 0.
2. **dev and fuzz MATCH** (answers and end/stream/lra/stats 0, traced and untraced, Python-Python control MATCH): dev
   31cd0945c07f02a6 (1,985), fuzz 173502b6ef285ad6 (3,000). loop 09238b2537e54383, zero d9ed3534a2093027, cert
   6a09c059eb266747, scope 12e06b0586faee40, budget 35bc2c4a937bebc0 MATCH. Python solvers made on Rust: 0.
3. **Plants** (46 x 7 workloads, table by `python3` over sum.txt's `| plant | wl | fired | verdict |` rows):
   - Caught on a workload (DIFFER): ad-lra-kind-key, ad-lra-pair-swap, rc-xslot-skip (fuzz, zero), xf-sel-none, xf-solver-fresh
     (all seven), int-as-number (scope; fired reads 0 there because its counter is term:int:*, as on c822173's bar), all
     15 rd-*-drop (rd-xheads-drop on fuzz and zero only, rd-guards-drop on zero only), rl-queue-drop, rl-pending_links-drop, rl-xpend-drop, and rs-aux_eq, rs-link_eq, rs-linked, rs-user_eq (dev only),
     rs-xcand (fuzz only), rs-xpairs (fuzz, zero), rs-xpart.
   - **Fired 0 on all seven (void on the workloads):** rk-class-split (caught on the suite, below), rs-bounded-drop,
     xf-rel-view-none (caught on the suite: 2 tests, 461 firings), int-as-number by plant_fired (see above).
   - **Fired but MATCH on every workload (void as a workload check; each caught by its unit test):** ad-lra-flag-key,
     ad-lra-not-expr (scope 4), ad-lra-patch-guard, ad-lra-slot-stale, gl-plain-no-link, rc-hseen-stale, rc-xterm-stale,
     rl-xextra-drop, rs-xcounted-drop, xf-rel-any, xf-session-none, xf-traverse-skip.
   - **Suite plants** (the zero ones): rk-class-split fired 692 in the suite and loses 10 ids (5,982 passed / 136 failed):
     test_ref's four zero-under-an-application ids (T1, T2, T4, query-twin), test_relevance's
     test_common_value_does_not_connect and test_undefined_function_connects, test_scope's
     test_answers_agree_with_the_lazy_order and test_zero_twins_are_in_the_scope, test_zero_glue's
     test_unrelated_relation_adds_nothing[G1-default] and [G1-whole]. That is the plant's control on the suite (the set
     differs from the 0576370 bar's eight: G1 not G5 ids, plus test_relevance's two; xdist's worker orders differ per run).
     xf-rel-view-none: 2 changed (test_scope.py::test_glue_and_transfer_exist_from_construction,
     test_switched_glue.py::test_set_glue_at_the_root). ad-lra-not-expr, int-as-number, rs-bounded-drop fired 0 in the
     suite too: **void there as well**; their only change is the planted-history test (below).
4. **Handler multiset same as base:** 39 rows in 2 tests (34 + 4 `_consistent` AttributeError in
   test_ci_stream_reports_only_what_replays; 1 `_build_context` "Already mutably borrowed" in test_protocol_on_fuzz, the
   named cause). engine.py:1906's catches: ctx:caught 0 on all seven workloads, 1 in the suite (= base, the row above).
   TermFault 0. Live and extra handler files 0 rows outside plant runs.
5. Known differences in answers or read state: none.

Kept shares equal to base: out-of-scope dev 24/1,985 (1.21%), 0 elsewhere; refused 0 everywhere.

### Counters per workload, Rust run (pareto1 ~/sp19/sa-rust-ids-work/sa-port-237/counts.txt; base = 219's bar beside it)
| wl | ad:cbm_noid | ad:lra_not_expr | ad:cb_factory | rk:term | rk:twin | rk:intern:input | rk:intern:engine | rk:outlive | rk:migrate | rs:core | rd:core | rl:core | rc:core | rel:init / ses:init |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | 0 | 0 | 0 | 8,971 | 0 | 511 | 4,067 | 0 | 0 | 4,358 | 36,057 | 5,481 | 2,676 | 198 / 918 |
| fuzz | 0 | 0 | 0 | 217,752 | 0 | 9,539 | 93,286 | 0 | 0 | 131,651 | 904,680 | 127,482 | 69,245 | 3,018 / 3,133 |
| zero | 0 | 0 | 0 | 57,170 | 0 | 1,027 | 18,338 | 0 | 0 | 30,932 | 179,145 | 26,152 | 28,244 | 556 / 667 |
| loop | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 384 |
| cert | 0 | 0 | 0 | 2,699 | 0 | 192 | 902 | 0 | 0 | 1,082 | 8,657 | 1,356 | 345 | 61 / 87 |
| scope | 0 | 4 | 0 | 2,112 | 0 | 303 | 1,953 | 0 | 0 | 1,503 | 14,161 | 2,509 | 1,157 | 135 / 171 |
| budget | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 17 |
- rs:view, rs:record, rd:view, rd:record, rl:view, rl:record, rc:view, rc:record, xf:record: 0 on all seven (no Python
  reader on the workloads). rk:dict:hit: dev 22,160, fuzz 584,041, zero 114,108, cert 4,792, scope 9,050.
- **rk:twin 0 on all seven** (no workload has two equal classes); **118 on the plain suite** (0 under rk-class-split, with
  692 plant firings there). rk:outlive 0 and rk:migrate 0 on all seven and in the suite: no session outlives its query.
- `integer_form`: ad:lra_not_expr scope 4 (the native not-an-Expr path), 0 elsewhere, = base. gl:plain dev 27, fuzz 1,697,
  cert 72, scope 13, zero 2 (= base). rel:cb_relation_atom (= base): dev 549, fuzz 27,426, zero 828, cert 507, scope 180,
  budget 36. rel:py_is_number scope 261, dev 8 (= base). link:second fuzz 19 (base 11), scope link:none 127 (= base).
- **ad:cbm_noid per suite run** (pareto1 sa-port-224/suitecnt.py): plain suite 94; under the inert plants ad-lra-not-expr
  1,011, int-as-number 287, rs-bounded-drop 631; rk-class-split 980; xf-rel-view-none 790. Base (219's stack bar) 19; the
  0576370 bar 386. It goes beside the earlier 19/910/376/208: it varies between runs of one source.
- **Fallbacks per template** (224's fbcounts.py; fb-cand.txt and fb-base.txt in the same directory): for the seven
  workloads this bar ran, every row (registry:python = dispatch.rs:242, rows:python = rows_tpl.rs:413, registry:kept,
  rows:kept, ad:cbm_noid, scaffold, rows:ids, outer, value, realroots, ctx:caught) is **identical to the base's**; `diff`
  shows only the six workloads this bar did not run. Per-template names: read fb-cand.txt (91 lines) by workload.
  scaffold:core:kept_product:mismatch: the counter exists on the base (`scaffold ... mismatch`); read it per workload from
  fb-cand.txt (rg "scaffold").
- **Not run on this bar:** the six 6i workloads core, f6, opaque, rootof, value, wiring (228's WLS predates the rebase onto
  59e9d15). On the base only `value` reaches Relations (rel:init 198, rc:core 5,720). **Run after the bar by this session** on the
  tested tree (ba1ca22, same .so fde4414dfab0…; pareto1 ~/sp19/sa-rust-ids-work/sa-port-237/extra6, script extra6.sh, no
  plants): core f9f2a582ea6ac149, f6 fc0c2f738a1f6dbf, opaque c7e1a7ca3a110ebb, rootof b4cc56a71a21baeb, value
  3ce3797a267d71a6: Python-Python control MATCH and Python-Rust MATCH, handler rows 0. `value` on Rust: rel:init 198,
  rk:term 2,956, rk:twin 0, rk:intern:input 394, rk:intern:engine 1,183, rk:outlive 0, ad:cbm_noid 0, ad:cb_factory 0,
  ctx:caught 0; the other four reach no Relations (all 0). **wiring was still running at the landing** (it reaches no
  Relations on the base: rel:init 0): read extra6/wiring.cmp and extra6/end.txt, and say which in the report.

### Condition (3) of the landing conditions: which case
The bar's state comparison does **not** read the moved containers. live.py's `end` digest (:462-477) is
`state.with_euf(dump, theories)`: the SAT solver's dump plus each EUF theory's fields, with the LRA text beside it; nothing
in live.py, livecmp.py, state.py or bar.sh calls rs_snapshot, rd_snapshot or rl_snapshot. So it is the planner's case (b):
plant 409 is caught by 236's direct test (test_rs_core.py::test_class_split_plant_is_caught, in the bar's tests phase) and
on the suite (10 ids), not by the workloads' digest. The rd-/rs-/rl- drop plants that DIFFER on the workloads are seen
through their effects (end, stream, lra, answers), not through the containers' keys.
**STATUS footnote text for the architect:** "State MATCH on the bars from 5c9a onward has not covered Relations' moved
containers: live.py's end digest is the solver dump, the EUF theories' fields and the LRA text. The nine sets, 15 dicts, 4
lists and 7 cursors are compared with Python only by test_rs_core.py, test_rd_core.py, test_rl_core.py and
test_relc_core.py (digest equal at the switch). Plant 409 rk-class-split is caught by its unit test and on the suite (10
ids), not by the workloads' digest. The next bar (part 3's or the formula step's) carries the digest extension (c931c16)
and must catch 409 there." Which containers each landed step from 5c9a had in the digest is not listed yet (owed with that
extension; for (i), (ii), (iii) part 1, (iii)(a)+(b) first move and this step the answer is: none of Relations').

### The planted-history test (planner's (b) and landing condition (2)): it matches a28c548's signature
tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence, same assertion as a28c548
(`assert len(run_stream(ops)) == 2`, test_public_incremental.py:204), same shapes: `[]` (0 == 2) or
`[(1, ('ask', positive(a), Not(positive(a))), True, False)]` alone (1 == 2).
- It **flips both ways between runs of the tested build**: passed in the bar's plain suite, in the rk-class-split suite and
  in the xf-rel-view-none suite; failed in the three suite runs whose plant fired 0 (ad-lra-not-expr `0 == 2`,
  int-as-number `1 == 2`, rs-bounded-drop `0 == 2`), in r-ref (`0 == 2`) and rw-ref (`1 == 2`). On the 0576370 bar: `1 == 2`.
- sa-port-185's own sweep rerun on the ba1ca22 build (orion ~/sa-rust-ids-work/sa-port-237/h185/, runs/ba1ca22, clone at
  3203cb4 clean, 300 runs all importing the clone's tree and .so), passes out of 50:
  | cell | original | original + id log | keep-alive variant |
  |---|---|---|---|
  | Python | 46/50 | 47/50 | 50/50 |
  | Rust | 0/50 | 0/50 | 50/50 |
  predict.py (difference count from the engines' ids alone): 100 of 100 logged runs match (Rust 35 x 0 and 15 x 1; Python
  47 x 2 and 3 x 1; reported shapes `[]` 35, `[(1, True, False)]` 13, `[(3, None, True)]` 2). With every engine kept
  alive both backends report exactly 2 on every run. Python fails too (4/50). This is 67d108d's row of a28c548's table.
- **In the suite's order too** (pareto1 ~/sp19/sa-rust-ids-work/sa-port-237/id-rust-{1,2,3}: worker 3894911's 972 ids, serial,
  Rust, the tested tree, with the engine-id logger idlog185f; replay-id.sh): three runs of one order on one build. id-rust-1
  FAILED (`[]`: op 1's engine at op 0's address and op 3's at op 2's); id-rust-2 and id-rust-3 passed (2 differences, no
  address shared). Predicted from the ids 3 of 3. So it flips both ways with the order held fixed.
- The fix variant (plugfix/test_fix185.py) was not rerun. id-py-{1,2} (the same order on the Python backend) were still
  running at the handoff; optional.

## Landing
- **Landed 3203cb4 on rust-slice at 15:09:50Z** (`PUSH=1 bash rust-spike/slice/p1/bar.sh land ba1ca22`), 59e9d15..3203cb4.
  Tested ba1ca22. **Incoming diff** (59e9d15..origin/rust-slice at the landing): **empty**, no rebase needed. Landing source
  differs from tested by HANDOFF-sa-port-236.md only (no guarded source), so no rerun was owed.
- Rule [91]: `agent ls` and `machine ls` showed no other session's full bar (sa-port-230 and sa-port-234 queued on the marker).
- Landing conditions: (1) the eight ids pass on the bar, changed 0; (2) signature matches, flips both ways (above); (3)
  case (b), footnote above; (4) ad:cbm_noid per workload and per suite run above; (5) the five items above.
- Marker `~/dev/architect/markers/state-relations-iii-landed` touched 15:10Z. architect-64 told the SHA by SendMessage.
- Branch port/state-relations-iii = 3203cb4 plus this handoff commit.

## Not done (the brief's tasks 4 to 7, in order)
1. Group-D post-processing, both SHAs: `bash ~/sa-rust-ids-work/sa-port-225/gd/tools/post195.sh SHA`, then
   `python3 tools/sum202.py gd/run-SHA > gd/run-SHA/SUMMARY-rel.md` (HANDOFF-sa-port-228.md "Not done" 3); table format at
   results/port-state-relations.md :237. The after column is 1a6d38a, not the landed SHA: say so.
2. (iii)(c) probe on the landed source: orion ~/sa-rust-ids-work/sa-port-228/pyc/run.sh NAME dev fuzz zero loop cert budget
   scope, own output directory under ~/sa-rust-ids-work/sa-port-237/; summ.py. The clone's build is ba1ca22's source
   (.so sha256 bfc06f0cd68a…, orion aarch64); it was not rebuilt by this session.
3. results/port-ownership.tsv and port-ownership.md (glue_objects row cites cac82a9; state rows for the 28 moved
   containers: 9 sets, 15 dicts, 4 lists, plus specs as Python configuration; the relations.py count line from the probe).
4. results/port-state-relations.md: fix the stale header at :329 (LANDED c822173, tested 022630c, report 5a3c218); new
   section for this step from this file, HANDOFF-sa-port-236.md and HANDOFF-sa-port-228.md, with every MUST-STAY item and
   the planner's (a) to (e). Items this file does not hold and the section needs: the per-template fallback names
   (fb-cand.txt), the group-D table, the probe table, the getattr-guard count (236: `twin_row` adds 2 to 5 Python reads
   per key lookup of a Basic with no own-class row, not adapter slots; adapter-slot guards added by this part: 0 per
   225/228's handoffs, check), which moved items are reached by which workload (the table above: all 28 containers'
   counters are nonzero on dev, fuzz, zero, cert, scope and 0 on loop and budget; per-container reach is the plant table's
   fired column, e.g. rd-num_sel only dev, fuzz, cert; rs-xpairs only fuzz, zero; rs-bounded nowhere).
5. `agent report` (Status: done) with the tested and landed SHAs and the incoming diff, then push.

## FILE:LINE additions
- orion ~/sa-rust-ids-work/sa-port-237/: bar/sum.txt (copy), h185/ (sweep, tally, predict, runs/ba1ca22), p1/ (the scripts
  sent to pareto1: replay-id.sh, run-id.sh, extra6.sh, idlog185f.py).
- pareto1 ~/sp19/sa-rust-ids-work/sa-port-237/: counts.py, counts.txt, fb-cand.txt, fb-base.txt, id-*/, extra6/.
- live.py :462-477 (the end digest), state.py :182 (with_euf). bar.sh land: p1/bar.sh :35-63.
