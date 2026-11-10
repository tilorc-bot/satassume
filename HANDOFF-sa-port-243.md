# HANDOFF sa-port-243: formula step (issue 323), third part

Branch `port/formula`, head = this commit, on rust-slice 0192b35. **Unbarred, unlanded.** Handed off at the context budget,
**in the middle of the `ad:cbm_noid` item** (gate item 2), not between items.

## Done
1. Gate item 1: after-probe and plants 601-606 on dev and zero read; port-formula.md has the after table (3985a76).
   Plants 604 and 605 are void on dev and zero (fired 0); 602 fires and is not caught on either.
2. Gate item 2, **work in progress** (this commit): `same_class` on the query's own class table at 11 sites, counters
   670/671, plants 660/661, test_cbm_noid.py. Two-order reproduction: `ad:cbm_noid` 0 and 0, refusals 0 and 0, same answers.
   dev and scope MATCH. Details: rust-spike/slice/results/cbm-noid-cause.md, last three sections.

## Not done in item 2 (in order)
1. Three slice tests of state part 2 (iii) fail because they hold the old rule: test_rs_core.py:271 and :285 (`rk:twin`
   now 0; relkeys.rs `twin_row` :97 and plant 409 are dead), test_relations_core.py:981 (the other class now has an id).
   Proposed change is in cbm-noid-cause.md; relations_core.rs:685 and session_live.py:1001 are in files state part 3
   edits, so tell the architect first.
2. Four more failing slice files not checked against the base build (test_term_live.py, test_handler_count.py,
   test_catch_count.py, test_cf_diff.py). Build origin/rust-slice in a worktree, or ask who owns them.
3. Q1 (which object a native result holds) is with the planner; no plant built for it. Don't decide it in the bar.
4. Read `~/sa-rust-ids-work/sa-port-243/c1/live/summary.txt` once `c1/end.txt` exists: zero, and plant 661 on dev
   (expected void: `cls:eq` is 0 on dev). **Don't rebuild the clone before `c1/end.txt` exists.**
5. A workload that reaches `cls:eq` with plant 661 caught, or a footnote. The suite totals 19/910/376/208 by test file
   come from the bar's rows.

## Then, unchanged from the brief's gate
3 `_common._CACHE` fix; 4 the entry converts once (`fm:nosession` to 0); 5 the term_live fallback cause; 6 D and E
(C waits on state part 3); plant 602's classification; workloads for plants 604/605; the bar after state part 3 lands.

## File:line map (at this head)
- formula.rs: counters :61 (630-644, 670-671), plants :97 (601-606, 660, 661), `class_is_planted` :137,
  `same_class` :147, `class_is_plant` :177; the rest as in HANDOFF-sa-port-234.md plus about 50 lines after :130.
- term_live.py: `_Query.classes` :74-92, `same_class` :275, sites :249, :314, :325, :381.
- Rust sites: adapters.rs:321-323; rows_tpl.rs:1375, :1399, :1534; outer_tpl.rs:242; fn_tpl.rs:201. Not edited:
  rows_tpl.rs:757 `same_value`. Python sites: knowledge_core_live.py:89, knowledge_live.py:272.
- convert.py: `_Walk.classes` :129, `klass` :218 (the per-query class table).
- relkeys.rs: `twin_row` :97, its call in `rk_key` :137; plant 409 :85. test_rs_core.py:271-295.
  test_relations_core.py `_join` :694, the assertion :986.
- test_cbm_noid.py: `_run(watch)`, `_held`, the four tests.
- Everything else as in HANDOFF-sa-port-234.md (session.rs, scope_core.rs, budget.rs, session_live.py lines).

## Watch
- Runs: `~/sa-rust-ids-work/sa-port-243/` (`check1.sh TAG` runs all 50 slice files, then dev/scope/zero on Rust against
  sa-port-234's Python runs; `probe/run.sh` is sa-port-235's reproduction pointed at this clone).
- Plants 607-629, 662-669 and counters 645-659, 672-679 are free.
