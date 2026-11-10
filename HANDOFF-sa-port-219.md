# HANDOFF sa-port-219 → land-only successor (6i(b) + 6i(c) stack, issue 323), 10 Nov ~06:50 UTC

Branch **port/6i-c-stack** in ~/dev/sa-port-7 = 6i(b)'s tested c59bb1a (port/6i-b, on rust-slice c822173) + 6i(c)'s 4
commits cherry-picked (c81a3d8, 8228a8e code = 377e188, 1d452e0; edffe11 handoff-215; 6f9c44a test) + docs b95f03b + this
handoff 05f2d8a (results/ and HANDOFF only after 6f9c44a).
Tested source of the stack bar: **6f9c44a**. port/6i-c (59ebd3c) is 6i(c) alone on c822173, kept for a fallback.
Architect (07:00): the stack lands 6i(b) + 6i(c) in one push; the separate 6i(b) land-only launch was cancelled.

## Running (read these)
- STACK BAR on 6f9c44a: pareto1 `~/sp19/sa-rust-ids-work/sa-port-219/bar-6ic-stack/end.txt` (sum.txt, bar.out); lease
  f30bc65d; launcher `~/sa-rust-ids-work/sa-port-219/launch-bar.sh` (orion pid in machine-run.pid). Config: BASE =
  sa-port-217/bar-state-relations-iii-ab/suite (c822173's landing bar, as 220's bar 3); PLANTS = rows-number-id-shift
  rows-product-first rows-pow-bound-args-swap rows-mul-ct-drop ctx-check-raise; SUITE_PLANTS=zero; WLS = the 11; TESTS =
  215's list + test_relc_core.py + test_knowledge_fn_direct.py; DIRECT = relations_direct.py 300 0; dispatch_direct.py.
- 6i(b)'s own evidence: sa-port-220's bar 3 on c59bb1a, pareto1 `~/sp19/sa-rust-ids-work/sa-port-220/bar-6ib3/end.txt`
  (6i(b)'s fn plants are there, not in the stack bar; keep the per-step plant tables separate).

## 6i(c) findings (bar 1 = sa-port-215's on 1d452e0/db7130a, pareto1 sa-port-215/bar-6ic): CLEAN
- Suite 5,991 passed / 127 failed / 23 skipped (+18 xfailed), 6,159 ids; vs 209's base new 0, gone 0, changed 1 (planted-
  history test passed→failed, the known id()-reuse failure a28c548). Passed: 5,990 no firing + 1 named
  (test_ci_stream_reports_only_what_replays). Handler multiset = base (34+4 `_consistent`, 1 `_build_context` RuntimeError
  "Already mutably borrowed" in test_protocol_on_fuzz). ctx:caught: 0 on all 13 workloads, 1 in the suite (that test).
- dev, fuzz, 11 WLS MATCH. Kept shares = base. ad:cbm_noid 0 everywhere. rows:kept 0 everywhere.
- Plants: 370 rows-number-id-shift caught core (fired 159; also fired dev 4, loop 11, wiring 7 without a change);
  371 rows-product-first caught dev, core, f6, loop, wiring; 373 rows-mul-ct-drop caught dev, core, f6, loop, wiring;
  **372 rows-pow-bound-args-swap void** on workloads (loop fired 3, MATCH) and suite (fired 0, changed 0). Reason: loop's
  derived Pows are `b**2` (loop_wl.py's extension `_pow`), no split either way. test_core_derived_args.py's first test
  did NOT catch it (checked in-process: fired 3, shadow:mismatch 0; SLICE_SESSION_PLANT isn't read under pytest, set
  K.PLANT). sa-port-219 added `test_pow_bound_args_swap_plant_is_caught` (extension-derived `1/(3*x + 2)`: fired 1,
  shadow catches) + `test_extension_derived_pow_bound_by_args` (59ebd3c). 54 passed with test_knowledge_rows.py.
- Probe (15 runs, `~/sa-rust-ids-work/sa-port-219/summ-cand.txt` vs sa-port-215/probe/summ-base.txt): core.py [query] 0
  on every workload except `_unit_power_units` core 15; `_imag_templates` 0. Table in results/port-6i-c.md.
- fbcounts: `~/sa-rust-ids-work/sa-port-219/fbcounts.py` (adds rows:kept, ad:cbm_noid, rows:ids, rows:pow_bound,
  ctx:caught); fb-base.txt (209's bar) and fb-cand.txt (215's bar). Kcl shells gone from rows:python everywhere.
- Count: core.py counts → 20 of 32 (STATUS 19 + core.py), plus whatever 6i(b) brings (functions.py, 220's claim).
  Question for the planner in port-6i-c.md: kept_product scaffold's mismatch gives no split (Python's answer), not refusal.

## Left
1. Read bar-6ic-stack (five items; 6i(c) plants + ctx-check-raise) and bar-6ib3; fbcounts on the stack bar.
2. Fill results/port-6i-c.md's BAR_HERE / PLANTS_HERE / KEPT_HERE / NOTRUN_HERE (form: port-6i-a.md); finish
   port-6i-b.md from bar-6ib3 (220's draft at results/port-6i-b.md:107-183).
3. Land: `bar.sh land 6f9c44a` without PUSH, read the incoming diff (rust-slice was c822173); clean → PUSH=1; else per NEXT.
