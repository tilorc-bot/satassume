# Formula's next step (B): batch bar on 506d7ac, landed (sa-port-291, issue 323)

Batch: the Hand at eng.ask 6a461f2, C2 d25b1a7, C7/(2) ea05bd5 (sa-port-289); refuse:object a9ff049 and the bar gaps
94a548e (sa-port-290). Tested source port/formula 506d7aca (= 94a548e's source plus HANDOFF-sa-port-290.md).

## Bar (pareto0, bar288.sh's config plus plants 622-624, the new p1/bar.sh; .so 9102fe85 built on pareto1)
End marker "END 0 2026-11-11T18:58:32Z 9102fe85 506d7aca". BASE = sa-port-288's suite (the landed rust-slice's bar).
- tests: 66 files, all exit 0, including test_hand_per_ask.py 2, test_noncomm_native.py 2, test_occ_object.py 2,
  test_cbm_noid.py 9 (on Rust), test_handler_count.py 2, test_catch_count.py 3, test_cf_diff.py MISMATCHES 0,
  test_term_live.py 20 passed 1 skipped. DIRECT relations_direct.py exit 0, direct.txt identical to 288's.
- suite: 126 failed / 5992 passed; against base new 0, gone 0, changed outcome 1: the planted-history test
  (test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence) failed -> passed, the known
  id()-reuse flake (a28c548) flipping as before. Handler rows 39 in 2 tests, multiset same as base; caught rows
  differing 0; TermFault 0.
- live (dev, fuzz) and extra (15 workloads): every Python-vs-Rust and traced/untraced comparison MATCH; answers_sha equal.
  live/summary.txt (apart from its date line), extra/summary.txt (the _SPLIT/_CACHE rows included), fmrows/check.txt
  ("fm rows: 20 workloads, 0 differ" against results/fm_rows.json) and both fmrows plant checks (exit 1) are identical to
  sa-port-288's bar on 42fd78e. Rust handler files on live and extra: 0 rows.
- Suite counters, against 288's suite: refuse:object 3789 -> **0**; ent:cb_noncomm (Python _noncommutative_atoms calls)
  300105 -> 9714, nc:memo_miss 5730, ctx:cb_helpers 4816 -> **0**; fm:again 0, fm:twice 0, fm:nosession 0, ad:cbm_noid 0;
  occ:two 935, occ:reach 22; ctx:caught 1 -> 1 (one test file in both, not new).

## Plants
| plant | workloads (fired) | caught by |
|---|---|---|
| 622 fm-hand-per-entry | fires on all 17 (dev 2040, fuzz 5919, wiring 11327), answers MATCH | test_hand_per_ask.py: fm:again within an ask > 0 under the plant (not the plant's counter); exact fm rows. Speed-shaped: answers can't change |
| 623 nc-memo-true-false | 0 on all 17 | suite (13 tests in test_noncommutative.py fail) and test_noncomm_native.py's answer check |
| 624 occ-walk-first | fuzz 61, transfer:7:60 56, transfer2:3:40 10; answers MATCH | test_occ_object.py::test_plant_624_is_caught_by_the_comparison (Rust's held object against Python's). The workloads' ==-equal objects answer the same, so no workload can tell |

Every earlier plant has the catch it had on 288's bar. In the suite plant runs, each plant's set of tests caught (beyond
the plain suite) is the same as or larger than on 288's, apart from the randomized test_verify_soundness fuzz cases
288 already listed (dispatch-keeps-memo's catch is its kept test test_cache_fix.py:172; fm-ite-swap is still caught by
test_sympy_api.py::test_xor_and_ite). fm-implies-swap is caught by 71 tests instead of 58: test_transfer_fuzz's 12 cases
plus the flake, as a second object now compiles in Rust instead of being refused.

## Per workload (20 workloads, on the tested source: sa-port-290's cnt-item1b, a9ff049 + 94a548e)
refuse:object 0 on all 20 (was dev 17, fuzz 30, zero 94, transfer:7:60 17, transfer2:3:40 2, cls 3, scope 1, ground 2,
port 6; total 172). _noncommutative_atoms: ent:cb_noncomm = nc:memo_miss on every workload (lra 1291, value 150, fuzz 97,
cert 30, ground 8, transfer2:3:40 8, cls 7, dev 6, port 5, transfer:7:60 4, scope 3, twin 1, zero 1, others 0; total
1611), ctx:cb_helpers 0. ctx:caught (engine.py:1906's catch, context.rs:279) 0 on all 20. fm:twice, fm:nosession 0.
fm:again (total, from the bar's fmrows): budget 385, cert 30, cls 2, core 824, dev 1104, f6 896, fuzz 1440, ground 5,
loop 339, lra 6, opaque 30, port 6, rootof 367, scope 283, transfer2:3:40 1, transfer:7:60 4, twin 0, value 634,
wiring 9930, zero 1288. Within an ask: see the post-landing probe below.

## Group D (pinned, not a blocker)
C2 before/after on pareto1 (sa-port-289's run, results/gd-c2-med-r1.md): fuzz Group D 2.178 -> 2.172 s; per-module shares
in HANDOFF-sa-port-290.md (relations_core 5.8% -> 5.4% of fuzz samples, others within 0.4 points).

## session.rs (planner's OK, conditions (a)-(d))
Changed ranges (172d690/053481b numbering): 122-123, 666-667, 1176-1215, 1369, 1406-1413, 1451, 1737, 1762, 2179-2188.
None of A's hunks; A's 172d690..3070c52 session.rs diff applied cleanly on top (git apply --check, sa-port-290).
