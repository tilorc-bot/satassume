# HANDOFF sa-port-281: formula step (issue 323), twentieth part: the bar read; unlanded

Branch `port/formula`, head = this commit, on rust-slice **9151316** (origin/rust-slice unmoved at 10:30Z); **tested
source 7b637e2** (.so fdcdeaab); later commits are results/handoff only. **Bar read: clean on every gate (1) item. Not
landed: gate item (2), the planted-history repeat run, not done (context).**

## Bar (pareto0 `~/sp19/sa-rust-ids-work/sa-port-280/bar`, END 0 10:09:59Z fdcdeaab 7b637e20; all phases exit 0)
Orion copies: `~/sa-rust-ids-work/sa-port-281/bar/` (sum.txt, fmrows.txt, wl/ = the Rust runs' session/knowledge/tot).
- tests: 62 files exit 0 (handler_count 2, catch_count 3, cf_diff MISMATCHES 0, discard_exempt 10, clear_sequence 5,
  two_order_twins 5, moved_digest 4, convert_once 17, cache_fix 7, cache_rollback 3, formula_nodes 15).
  **Bar gap:** the tests phase runs test_cbm_noid.py on the Python backend (3 passed, 6 skipped: R1 and the 660-663 kept
  tests). Rerun on Rust, pareto0, tree 7b637e2/.so fdcdeaab (`run_suite.sh ... rust test_cbm_noid.py`, PYTEST_N=""):
  **9 passed** (`pareto0:~/sp19/sa-rust-ids-work/sa-port-281/cbm`). bar.sh should run it under rust_plugin (owner: formula).
- suite: 127 failed / 5991 passed / 23 skipped / 18 xfailed; vs base 247/bar-part3: new 0, gone 0, changed 1 =
  tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence (passed -> failed).
  Passed split: 5990 no firing + 1 firing (test_invariants.py::test_ci_stream_reports_only_what_replays). Handler
  multiset = base (39 rows: 34 `_ok`, 4 `_rb_clauses`, 1 Already mutably borrowed). Caught rows differ 0. TermFault 0.
  The planted-history test flips back to passed under suite plants fm-ite-swap and term:mark-wrong-pattern (both ways).
- live dev/fuzz and the 15 extra workloads: **all MATCH** py vs rust (and py vs py control). Per workload: moved_diff 0,
  moved_known_diff 0, cache key/value diff 0 (points: twin 1, scope 7, loop 17, zero 35, cert 3, budget 2, core 66,
  f6 117, opaque 102, rootof 208, value 150, wiring 261, transfer7 3, transfer2 2, cls 3), native bad [] on both,
  known rows [] (known_moved.json empty). _SPLIT/_CACHE py == rust at every engine point, counts included.
  cls `moved_lra_python_only` 48 (lra 454 vs 406): same 48 on 276's plain Rust (p612e/cls-rs.cmp) and 280's prep
  (prep/wl/cls.cmp); outside the verdict; not new.
- Rows per workload (Rust, 7b637e2) = 280's prep rows on 212a7d6 exactly: discarded runs f6 13, opaque 7, value 15,
  wiring 1, others 0 (solvers 0, sessions 0); rk:intern engine/input dev 4067/511, fuzz 93286/9539, zero 18338/1027,
  scope 1953/303, cert 902/192, value 1183/394, transfer7 2476/209, transfer2 2080/221, cls 666/104, twin 56/2, rest 0;
  refuse:object dev 17, fuzz 30, zero 94, transfer7 17, transfer2 2, cls 3, scope 1; cls:eq cls 174, twin 21; same:eq 0;
  ad:cbm_noid 0 on all (cls 0; under 660 and 661: 264); kept_product mismatch 0 everywhere (checked: dev 33, core 163,
  f6 82, wiring 10, loop 2, transfer 2/2); sb:fwd_named 0 everywhere with digest on, sb:fwd_direct cls 453 / wiring
  48945 / f6 11575; kept test test_moved_digest.py:110 (on == off, fwd_named 0, direct > 0) passes.
- fm rows (fm_rows.py check, 20 workloads): **0 differ, exit 0**; fm:nosession 0, fm:twice 0, fm:twice:patched 0 on
  all 20; fm:convert/fm:again = fm_rows.json (table: orion `sa-port-281/bar/fmrows.txt`). Plants: 613
  fm-args-drop-last 5 differ exit 1; 612 fm-atoms-merge-pred 3 differ exit 1 (caught).
- Plant table vs results/port-formula.md (276's table + earlier): no plant newly uncaught.
  601/606/612/613 DIFFER (answers/rows) where they fire; 604 fm-implies-swap DIFFER budget/loop/scope/wiring + suite 58
  changed; 605 fm-ite-swap suite 2 changed (test_xor_and_ite, test_fuzz_symbols_may_be_nan); 607 fm-hand-no-give and
  608 fm-hand-kept MATCH (count plants; fm row + kept tests, as before); 660 ad-lra-class-is MATCH, ad:cbm_noid 0 -> 264;
  661 class-is DIFFER twin, suite 6 changed, ad:cbm_noid 264 on cls (cls livecmp MATCH: 276's "row on cls" was an fm row
  from 270's sweep, not run here); 662 kept-test (R1) catch, passes on Rust; 663 same-is suite fired 0, kept test passes
  on Rust; 664 atom-symbol-key-names now DIFFER on all 16 via the 4i `_CACHE` key row (was kept-test only); 665
  dispatch-keeps-memo suite 0 changed (kept test test_cache_fix.py passes); 666 term:mark-wrong-pattern DIFFER answers on
  f6 and wiring (wrong-value since 010f1d6; wiring first q4264 False vs True, as 278's orion read); 611/667 fire on f6
  234/13, opaque 126/7, value 270/15, wiring 18/1 (667 = discarded runs), kept tests in test_discard_exempt.py pass
  (incl. test_plant_611_on_a_dispatch_store_is_caught, the new DispatchStore path); 600 rows-product-verdict-flip
  kept_product row; P1 fm-hand-instrument-by-name / fm-hand-patched-direct: test_convert_once.py 17 passed.
  **Bar gap:** bar_sum's `fired` column reads only plant_fired/rel:plant_fired, so term plants show 0 there; the counts
  above are `plant:*` in the plant runs' jsonl.
- Kept shares (Rust): dev kept:out-of-scope 24/1985; cls kept:args-eq-not-is 6/72; refused f6 13, opaque 7, value 15,
  wiring 1 ("base not found" in bar_sum: no base kept rows in 247's dir).
- Group D: not measured (pareto1 held by hand-sim-bf); onlease280.sh end marker
  pareto1:`~/sa-rust-ids-work/sa-port-280/gd/timing/end.txt` not checked.

## Next (gate for sa-port-281)
1. Gate (2): a28c548's method (`agent journal -v | rg a28c548`, OWED [113](b)): ~20 runs each of the planted-history
   test on 7b637e2 in both cells, plain and with keep-alive, on Rust and Python. Qualifies only if plain fails some,
   keep-alive passes all, Python ~ base rate, same assertion (test_public_incremental.py:204, assert 0 == 2 / len 1 vs 2).
2. If it qualifies: `bash rust-spike/slice/p1/bar.sh land 7b637e2` here (read the incoming diff; PUSH=1 lands). Group D
   seconds + memo cost to OWED with the STATUS footnote naming hand-sim-bf.
3. After landing: module-wide probe on the landed SHA (previously 21/32; does _nt_mark's move change it), knowledge_live
   per workload (results/pc280-7b637e2.md has base -> 212a7d6 -> 7b637e2).

## File:line map (this head)
- As HANDOFF-sa-port-280.md: dispatch.rs `_nt_mark` :337, `_nt_rollback` :346, `_nt_rows` :368, DispatchStore ~:466-:500;
  knowledge_live.py install_dispatch :254-:256; term_live.py `_Seen` :110-:121, `_Mark` :188-:235, plants :235-:258.
- p1/bar.sh: penv :85, suite() :96, tests :108 (runs test files without rust_plugin: the cbm_noid gap), plants :132,
  fired() :101; p1/bar_sum.py plants :119-:141 (the fired column).
- test_cbm_noid.py: Rust-only tests :92-:290 (skip on Python); run by run_suite.sh WORK rust.
- results/port-formula.md: plant tables :618-:660.
No plant or counter taken.
