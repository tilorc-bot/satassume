# Part 3 follow-up (A): batch bar, probe, planted-history, S1 speed, on 1d22f9a (issue 323, sa-port-295)

Tested source 1d22f9a (Rust source as at 5bf9c47), base rust-slice 15c62a7. Bar: pareto0 ~/sp19/bar294.sh, out
~/sp19/sa-rust-ids-work/sa-port-294/bar (END 0, 23:43:54Z 11 Nov), .so 2cc2e09f built on pareto1. Probe: pc294.sh, out
sa-port-294/pc (all 40 jobs exit 0). Base rows: sa-port-291/bar/suite and sa-port-291/pc (2439bac = 15c62a7's source).

## Bar (five items)
1. Tests: 69 files, all exit 0; relations_direct.py exit 0.
2. Suite: 127 failed / 5991 passed (ids 6159); against base new 0, gone 0, changed outcome 1: the planted-history test
   (test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence) passed -> failed, the known
   id()-reuse failure (a28c548; repeat run below). TermFault 0.
3. Live: dev and fuzz, Python vs Python, Python vs Rust, traced vs untraced: all MATCH (dev answers_sha 31cd0945c07f02a6,
   fuzz 173502b6ef285ad6; Rust makes 0 Python solvers). Extra workloads (15): 31 of 31 comparisons MATCH.
4. Quiet failures (engine.py `except Exception` catches): suite 39 rows in 2 tests, multiset equal to base (34 + 4
   `_consistent` AttributeError in test_ci_stream_reports_only_what_replays, 1 `Already mutably borrowed` in
   test_protocol_on_fuzz; ids whose rows differ from base 0); live and extra handler files 0 rows each; probe 0 rows.
   The counter fires (those 39 suite rows).
5. Kept reasons: every live/extra share equal to base (dev kept:out-of-scope 24/1985; cls kept:args-eq-not-is 6/72;
   refused f6 13, opaque 7, value 15, wiring 1, as base).
- fm rows: 20 workloads, 0 differ (fm:nosession 0, fm:twice 0, fm:twice:patched 0 on all 20); fm-args-drop-last caught
  (4 differ), fm-atoms-merge-pred caught (3 differ).
- Suite plants: same pattern as 291's bar (each caught plant changes outcomes; the plain-run differences of +-1 are the
  planted-history test flipping both ways). suite-sb-join-address (new): 65 fired, changed outcome 0.

## Plants 614-620 (A's), 17 workloads each, against this run's Python
| plant | name | fired on | workload DIFFER | catch |
|---|---|---|---|---|
| 614 | sb-join-address | 2 (cls 367, twin 2) | 0 | kept test only (test_rs_core.py). No workload sets the join hook; only join_log.py does. |
| 615 | sc-key-id-stale | 6 | 6 (dev fuzz cert scope transfer:7:60 zero) | workloads + kept test (test_ses_keys.py) |
| 616 | sc-key-id-weak | 17 | 0 | kept test only (test_ses_keys.py against plain dicts). Without the strong ref, a stale row needs its key object freed and its address reused while the memo lives. In the workloads, the keys are held elsewhere for the whole session (the dict's own entry, the session's tables), so no address is reused (fired 17, DIFFER 0). |
| 617 | sc-key-id-shared | 17 | 16 | workloads + kept test |
| 618 | ent-method-first-self | 17 | 1 (twin) | twin + kept test (test_entry_frame.py) |
| 619 | gm-guard-skip | 17 | 0 | kept test only (test_guard_method.py, via `ask_ref`). The guard sends a session with no core (ref.py's, or one built while `engine.VarTable` isn't TableView) to the Python method. Every workload session has a core, so skipping the guard changes nothing there. |
| 620 | cl-view-nodes-drop | 17 | 1 (loop) | loop + kept tests (test_compile_loop_core.py, test_discovery_core.py) |
Other plants: same verdicts as 291's bar (class-is twin, term:mark-wrong-pattern f6/wiring DIFFER on both).

## Item 2 (SesDict) as it lands
- sc:key_hash per query on fuzz: before 159.5 (478,541 / 3000), after 16.3 (48,913 / 3000; probe on 1d22f9a, unchanged).
- Term-id deviation (accepted earlier): the memo is keyed by identity on the object the row holds, not by the query's term
  id. A term id goes through `term_of` -> `node_quiet`, a Python dict lookup counted `link:cross_hash`, so a term-id key
  would only move each hash() from one counter to another.
- Conditions (a)-(e), all hold (9255774, c4701f4): (a) each row holds its key object strongly (plant 616 drops it);
  (b) a miss falls through to hash + == and stores the first key object; (c) per dict, never process-wide (plant 617
  shares it); (d) the memo lives in SesDict and goes with clear/replace and with the session; moved_digest.py names it as
  derived from the dict; (e) 616 and 617 are each caught by test_ses_keys.py against plain dicts (617 also by 16 workloads).

## Rulings (1)-(3) on 293's deviations
- (1) The cached hash is keyed by identity on an object the row holds (ses_cont.rs `Seen`).
- (2) No session crosses queries. Gauges 701 sc:ses_live / 702 sc:memo_peak, probe on 1d22f9a, per workload: sessions
  alive at an ask's end 0 on all 20 (asks_ending_with_live_session 0, max 0; sc:ses_live 0 at the end). Peak memo size
  (largest one-dict memo): lra 102, f6 8, wiring 38, scope 7, dev 11, fuzz 14, ground 7, port 6, loop 14, zero 11, cert 5,
  budget 302, core 8, opaque 4, rootof 3, value 3, twin 3, transfer760 19, transfer2340 35, cls 13.
- (3) Bound EntMethods and all 58 GuardMethods carry the Python method's `__name__`, `__qualname__` and `__doc__` (kept
  tests test_entry_frame.py, test_guard_method.py). Explained row, not a blocker (planner ~20:35Z): GuardMethod
  `__module__` stays `sa_solver`. Python's module is OWED, as the rk_key step's first item, with a kept test.

## fm:again per workload
Within an ask (fm_again_split.py mode=ask): 0 on all 20 (asks_with_again 0). Across queries (the bar's fm rows):
budget 385, cert 30, cls 2, core 824, dev 1104, f6 896, fuzz 1440, ground 5, loop 339, lra 6, opaque 30, port 6,
rootof 367, scope 283, transfer2:3:40 1, transfer:7:60 4, twin 0, value 634, wiring 9930, zero 1288.

## Planted-history repeat run (a28c548's method; 20 fresh pytest processes per cell, pareto0)
Trees: 15c62a7 = sp19/dev/sa-port-291 (2439bac source, .so 9102fe85), head = sp19/dev/sa-port-294 (1d22f9a, .so 2cc2e09f);
each run's import checked (80 + 80). Keep-alive = sa-port-185's test_keepalive185.py.
| cell | 15c62a7 plain | 15c62a7 keep-alive | 1d22f9a plain | 1d22f9a keep-alive |
|---|---|---|---|---|
| Rust | 0/20 | 20/20 | 0/20 | 20/20 |
| Python | 17/20 | 20/20 | 17/20 | 20/20 |
Every failure is test_public_incremental.py:204, `assert len(...) == 2`, got 0 or 1 (15c62a7 15 + 8, head 16 + 7).
The pass rate did not move with the session-lived memo. Rust plain 0/20 matches 282's 7b637e2 run and a28c548's 0/50;
Python's 3/20 is near its base rate (a28c548 2/50 and 6/50, 282 1/20). Matches a28c548's signature: the known id()-reuse
failure. Test not edited. Script ~/sa-rust-ids-work/sa-port-295/scripts/ph295.sh; runs pareto0 sa-port-295/ph.

## session_live converted calls per function (20 workloads; slfn294.py sa-port-291/pc sa-port-294/pc)
Total 2,445,317 -> 623,262 (functions with calls 37 -> 19). Gone: _rel_m 317,337, _q 210,338, _ses_ensure 187,617,
_ses_discover 99,320, _ent 77,795, _ses_custom 56,682, _ses_query_literal 55,202, _g 23,315, _ses_assumption_lits 23,259,
_ses_escalate 16,195, _rel_sync_transfer 11,277, _rel_selectors_of 9,727, _rel_add_role 7,852, _rel_transfer_terms 4,091,
_rel_fresh 2,427, _rel_engage_transfer 2,107, _rel_mention_number 714, _ses_flush 142. Reduced: TableView 667,978 ->
165,283, _BaseOf 241,845 -> 27,882. Unchanged: _table_get 50,059, _ses_incomplete 39,032, _Custom 35,966, the eight
per-session ones 27,882 each, _node 25,966, _rust_call 20,775, _compile_formula 17,457, _rel_process 9,218, _rel_init
5,250, _formula_literal 3,318. Next cheap one: `_node` as a Rust entry (also removes its `_table_get`).

## Module-wide probe (pcsum.py sa-port-294/pc sa-port-291/pc)
- session_live.py all (converted) drops on all 20 (dev 83,101 (76,153) -> 24,545 (20,561); fuzz 866,097 (853,958) ->
  115,383 (106,180); wiring 473,968 (447,738) -> 141,009 (121,243)). formula.py drops slightly on 13 (fuzz 62,568 ->
  60,946 converted). knowledge_live.py, term_live.py, engine.py, compile.py, wiring.py, knowledge_common/core_live.py
  unchanged on all 20.
- knowledge_live.py per workload, all (converted), unchanged: lra 4326 (34), f6 328 (22), wiring 125 (80), scope 42 (12),
  dev 160 (50), fuzz 46 (16), ground 40 (10), port 48 (18), loop 70 (22), zero 63 (18), cert 38 (8), budget 930 (900),
  core 88 (16), opaque 140 (6), rootof 32 (2), value 952 (794), twin 38 (8), transfer760 65 (20), transfer2340 73 (28),
  cls 42 (12).
- Count: **21 of 32, unchanged.** session_live.py still runs Python per converted query (623,262 calls on the 20), so it
  and ses_cont (whose session setup and `_ses_incomplete` still go through session_live) don't count. relations.py isn't
  counted (STATUS: 42 per-query fallbacks in test_transfer.py::test_inequalities_restate_an_equality); this step didn't
  touch it, and the probe's file list has no relations.py rows.

## Speed (S1): pinned wall time plus per-function inclusive time
**Deviation, host:** pareto0, not pareto1. pareto1 went under train-test-1's shared lease (~21 h of CPU training) before my
quiet request, so the request was withdrawn. pareto0 has the same CPU model (i5-13600T) and the same sa-eval-bench:1 image
id (95132be5). The three trees alternate inside one bench-container invocation (BENCH_CPU=2, quiet pareto0 lease c2a95fc6,
23:54:58-23:57:47Z, load 0.19 before), 7 rounds, rotating order. That's 42 rows, **0 answer-digest mismatches**. The
harness is sa-port-292's go292.sh (time285.sh, med285.py, prof292.py, cmp292.py). Trees were staged by `git archive` and
built in sa-cy-build:1: 1401d1f (146's tree, .so 9ac1e109), 15c62a7 (b5a4ac62), 1d22f9a (ff007ad6).
| workload | 146 tree 1401d1f | rust-slice 15c62a7 | head 1d22f9a | head vs 15c62a7 | head vs 146 tree |
|---|---|---|---|---|---|
| dev, Rust median s (min-max) | 0.750 (0.745-0.759) | 0.761 (0.758-0.763) | 0.760 (0.752-0.774) | -0.1% | +1.3% |
| fuzz, Rust median s (min-max) | 6.689 (6.661-6.698) | 6.440 (6.405-6.464) | 6.420 (6.367-6.464) | -0.3% | -4.0% |
There's no wall-time regression against 15c62a7. Against 146 in wall time: dev +0.010 s (+1.3%), fuzz -0.269 s (-4.0%). 146's
own medians were 0.767 / 6.802 on pareto1. Group D, a reported row: dev 0.186 -> 0.187 s, fuzz 2.210 -> 2.221 s (146 baseline
0.158 / 1.990).
Per function, inclusive (pysampler, prof292.py; seconds = share x the tree's pinned median). Samples: 1d22f9a has fresh
samples (dev 3, fuzz 6 runs, shared pareto1 lease, before train-test-1's). 15c62a7 reuses sa-port-292's samples, which
came from the same harness and the same .so b5a4ac62.
- session_live.py frames, inclusive: dev 0.342 -> 0.145 s, fuzz 4.860 -> 2.813 s. Gone on fuzz: `_ent` wrapper 4.736 s,
  `_q` 2.979 s, `_g` 1.553 s (inclusive, so they overlap). In their place, GuardMethod.__call__ is 0.232 s inclusive on
  dev and 3.607 s on fuzz, with self time 0.002 s dev and 0.019 s fuzz.
- formula_ask, the whole ask: dev 0.752 -> 0.749 s, fuzz 6.404 -> 6.377 s. Category totals on fuzz: callback -0.088 s,
  glue +0.037 s, rust +0.036 s, capi<-rust +0.011 s. No single function's self time moved by more than 0.02 s, and none's
  self+C by more than 0.054 s (relations_core::ensure +0.054 s and rel_process +0.049 s; the sampling SE is about 0.02 s
  per tree, so these are reported rows, not findings).
- Removing about 1.8M Python wrapper calls gave about 0.02 s of fuzz wall time. The wrappers' cost was mostly the call
  protocol, and GuardMethod's call still pays it (_PyObject_MakeTpCall inclusive +3.48 s on fuzz, moved, not removed).
Files: orion ~/sa-rust-ids-work/sa-port-295/gd (go295.sh, go295b.sh, med-r1.md, cmp-dev.txt, cmp-fuzz.txt, timing-r1/).

## Files touched outside A's four (session_live.py, session.rs, query.rs, session_glue.rs)
ses_cont.rs, compile_loop.rs, discovery.rs (ses_ensure parameter name), moved_digest.py (doc), fm_again_split.py,
test_rs_core.py, test_ses_keys.py, test_entry_frame.py, test_guard_method.py, test_query_core.py,
test_compile_loop_core.py.
