# HANDOFF sa-port-290 (B, formula's next step, issue 323): items (0), (1), (3) done; the batch bar is NOT launched

Branch port/formula = origin/rust-slice 9595874 + 289's commits + a9ff049 (item 1) + 94a548e (item 3) + this file. Pushed,
not landed. Plants 622-624 and counters 720-722 are used; plants 625-629 + 669 and counters 723-739 are free.

| item | commit | state |
|---|---|---|
| Hand at eng.ask / C2 / C7=(2) | 6a461f2 / d25b1a7 / ea05bd5 | done by 289 |
| (0) read C2 Group D + C7 counts | - | done, below (no rerun needed) |
| (1) refuse:object | a9ff049 | done: 172 -> 0 on 20 workloads, answers_sha equal; plant 624; counters 721-722 |
| (3) bar gaps | 94a548e | done: cbm_noid on Rust in the bar; term plants' fired count |
| batch bar (Hand, C2, C7/(2), (1), (3)) | - | NOT LAUNCHED: next step |

## (0) Group D per-module shares, C2 (6a461f2 -> d25b1a7), from ~/sa-rust-ids-work/sa-port-289/gd/run-*/SUMMARY.md
fuzz, D C API from Rust 6588 (33.7%) -> 6600 (33.9%) samples: relations_core 5.8% -> 5.4%, compile_loop 3.5 -> 3.4,
lib.rs 3.2 -> 3.4, adapters 3.2 -> 3.3, session 2.6 -> 2.2, constfield 1.8 -> 1.9, relkeys 1.6 -> 1.7, solver 1.3 -> 1.4,
formula_py 1.1 -> 1.3, entry 1.1 -> 1.1, discovery 1.0 -> 1.0, session_glue 0.8 -> 0.8. dev: all within 0.2 points
(compile_loop 3.6 -> 3.8, relations_core 2.4 -> 2.4). Seconds as in results/gd-c2-med-r1.md (fuzz Group D 2.178 -> 2.172 s).
The pipeline gives per-module rows, the finest it has. C7/(2) counts: HANDOFF-sa-port-289.md "Counts per workload".

## (1) refuse:object, per workload (~/sa-rust-ids-work/sa-port-290/cnt-item1b/rows.txt; before = 289's cnt-c7)
refuse:object dev 17>0, fuzz 30>0, zero 94>0, transfer:7:60 17>0, transfer2:3:40 2>0, cls 3>0, scope 1>0, ground 2>0,
port 6>0, others 0>0 (total 172>0). The suite count is not measured (the bar's suite run will show it).
occ:two (722: formula with a second object, now compiled in Rust): fuzz 27, transfer:7:60 14, transfer2:3:40 2.
The rest of the old 172 were custom atoms over a node whose object isn't theirs (no slot on Python), no longer refused.
occ:reach (721) 0 on workloads, 83 on the kept test. ctx:caught 0 on all 20, and it IS engine.py:1906's catch
(context.rs:279; fires on plant 221 in test_context_core.py:191). fm:twice, fm:nosession, second:visit 0 on all.
_noncommutative_atoms: nc:memo_miss = ent:cb_noncomm unchanged by item (1) (total 1611); ctx:cb_helpers 0.
session.rs changed ranges (172d690/053481b numbering): 122-123, 666-667, 1176-1215, 1369, 1406-1413, 1451, 1737,
1762, 2179-2188. None of A's hunks; A's 172d690..3070c52 session.rs diff applies cleanly on top (git apply --check).
Also edited: compile.rs (Cx::reach), formula.rs (names, plant 624), test_session_limits.py:393 (refuse:object == 0).
Tests on orion: test_occ_object, test_session_limits, test_formula_nodes, test_hand_per_ask, test_noncomm_native: 263 passed.

## Batch bar: what to run (nothing launched)
- Build x86 .so on pareto1 as 288 did (~/sp19/sa-rust-ids-work/sa-port-288/build: bar.sh build phase, OUT dir, clone
  ~/sp19/dev/sa-port-288 there). No ~/sp19/dev/sa-port-7 exists on pareto0/pareto1: clone or reuse -288's checkout
  for port/formula 94a548e (or this file's commit).
- pareto0 config: copy ~/sp19/bar288.sh, set NAME/branch port/formula, and add to PLANTS: fm-hand-per-entry (622),
  nc-memo-true-false (623), occ-walk-first (624). TESTS=all TESTS_SPLIT=1 already runs test_hand_per_ask.py,
  test_noncomm_native.py, test_occ_object.py, and test_cbm_noid.py on Rust now. Note bar-288.sh is a copy of
  p1/bar.sh: use the new p1/bar.sh (94a548e) so the term-plant fired column and cbm_noid route are in.
- Run under `machine run pareto0 --shared --wait 4h`, detached, end marker written by the job.

## FILE:LINE MAP (rust-spike/slice/ on 94a548e)
- solver_rs/src/session.rs: nid_in_formula :1185, occ_note :1193, reach :1215, occ_done :1254, custom_in_formula :1270,
  convert's occ:two tick :1473, node_id's `passing` :1526, PyCx::reach :1817.
- solver_rs/src/compile.rs: Cx::reach :66, def_at :134, Part.at :327; reach calls in compile/compile_not/literal atom arms,
  def_of, and or_cnf's chosen parts (rg "cx.reach").
- solver_rs/src/formula.rs: OCC_REACH :94 (721), OCC_TWO :96 (722), planted_occ_walk_first :194 (624).
- test_occ_object.py (kept test + plant 624); test_session_limits.py test_counters_fired.
- p1/one_test.sh test_cbm_noid.py case; p1/bar.sh fired() and the plants/extra SLICE_TERM_COUNTS; p1/bar_sum.py plants
  fired column; term_live.py `_Plant` (after `PLANT = [None]`) and from_env.
- Tools: ~/sa-rust-ids-work/sa-port-290/tools/cnt.sh OUT SO (20 workloads, -P 3), cnt_rows.py; env.sh there.
