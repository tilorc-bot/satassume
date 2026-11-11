# HANDOFF sa-port-293 (A, part 3 follow-up; issue 323)

Branch port/part3-followup, rebased onto rust-slice 15c62a7 (clean, no session.rs conflicts with B's ranges). Code head
e41642f. Nothing landed; no bar run. I followed the gate (~19:25Z 11 Nov) for the order: (2) conditions, C7 entry frame,
(4). The brief's TASK line (item 3, one Hand per ask) is B's and landed in 2439bac.

## Done (each its own commit)
- 9255774 (2) conditions (a)-(e), checked. Plants 616 sc-key-id-weak (no strong ref) and 617 sc-key-id-shared (process-wide)
  are each caught by test_ses_keys.py against plain dicts. (d): the memo lives in SesDict (clear/replace take it;
  sessions are per query), and moved_digest.py names it as derived. Also fixed test_rs_core.py's join-key control
  after the rebase: something made once on the first join path takes the first freed slot. Now a warm-up session runs
  first, and 614 is caught again.
- f4afbab C7 entry frame: session_glue.rs EntMethod (PyMethod_New binding) replaces `_ent`'s def; plant 618
  ent-method-first-self; test_entry_frame.py. Unpinned on orion: 260 -> 130 ns/entry call.
- e41642f (4) first half: GuardMethod replaces 58 guarded wrappers (33 Relations, 25 Session); session.rs `named`
  accepts GuardMethod.origin; discovery.rs ses_ensure param renamed `node`; plant 619 gm-guard-skip;
  test_guard_method.py (ask_ref exercises the no-core fallback). Ten asks: wrapper frames 1,194 -> 112.

## (4) left (mid-item: the context budget ran out)
1. Per-function owner table for session_live converted calls still running. Baseline 2439bac (pareto0
   ~/sp19/sa-rust-ids-work/sa-port-291/pc/*.json, by_name_state "session_live.py:<fn> converted"): TableView 667,978,
   _BaseOf 241,845, _ses_query_literal 55,202, _table_get 50,059, _ses_incomplete 39,032, _Custom 35,966, _ses_init/
   _ses_solver_set/_table_set/_core_rules/_ses_solver_get/_Slots/_Base/_base_set 27,882 each, _node 25,966,
   _ses_assumption_lits 23,259, _rust_call 20,775, _compile_formula 17,457. Owner A for all (session_live is A's).
   The candidates are TableView and _BaseOf as Rust classes, plus query_literal's defaults in query.rs (A's), so that
   `_frameless` takes it.
2. Re-probe on the head: pc291.sh's recipe on pareto0 (pycalls.py --check plain, 20 workloads, PCF list). Build the
   x86-64 .so on pareto1. That gives the per-function table after the change, and the module-wide probe count
   against 21/32.
3. Then the bar (p1/bar.sh, PLANTS including sb-join-address, sc-key-id-stale, sc-key-id-weak, sc-key-id-shared,
   ent-method-first-self, gm-guard-skip; SLICE_SESSION_PLANT routing handles all six via _SB_PLANTS), rebase, land.
   Speed is judged by pinned wall time plus per-function inclusive time (RULINGS 16), before (15c62a7) and after.

## FILE:LINE MAP (on e41642f, rust-spike/slice/)
- solver_rs/src/ses_cont.rs:64/66 plants 616/617, :127 sd_find, :170 seen_row, :179 seen_put (both plants switch here).
- solver_rs/src/session_glue.rs:483 plant 618, :493 EntMethod, :553 plant 619, :556 GuardMethod, :632 has_core.
- solver_rs/src/session.rs:740 A_PLANTS (614-619), :872 `named` accepts GuardMethod.origin.
- solver_rs/src/discovery.rs:61 ses_ensure signature (node).
- session_live.py:1099 _SB_PLANTS, :1111 _ent, :1124 ENTRY_FRAME (SLICE_ENTRY_FRAME=py puts every def back), :1127
  _guard_shapes, :1165 _frameless; the install loops call _frameless (_DISC/_LOOP/_QUERY/_GLUE/_REL_METHODS).
- Tests: test_ses_keys.py, test_rs_core.py (joinkey warm-up), test_entry_frame.py, test_guard_method.py.
- Ranges: plants 614-619 used (620, 621, 668 free); counters 700 used (701-719 free).
- Logs: orion ~/sa-rust-ids-work/sa-port-293/ (build*.log, c7-tests.log, gm-tests*.log).
