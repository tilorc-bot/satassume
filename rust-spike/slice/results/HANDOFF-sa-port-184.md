# Handoff sa-port-184 (step 5c10b, issue 323), head see `git log -1 port/5c10b`

DONE (on port/5c10b, from rust-slice 67d108d; no bar run yet, nothing landed):
- context.rs: `_context_session`, `_build_context_memoized`, `_build_context`, `verdict`, `_complete_check` in Rust, step for step
  as engine.py:1835-1983. engine.py:1906's handler is in `build_context` (context.rs:169-218): counted `ctx:caught`, row to
  handler_count under site `Engine._build_context`. Calls among the five are direct unless patched (`patched`, :43; counted
  `ctx:cb_patched`), so catch_count/mock patches of `_complete_check` etc. still run.
- Containers Rust-native: `_failed`, `_verdict`, `_context_sessions` are engmemo slots 5-7 (engmemo.rs:39, plants in `clear` :207);
  views as 5c9c's (EngineMemo; `native`, `moved`). Python's `_drop_set_memos` clears them through the view (em:py_*; 5c10d).
- Counters 271-287 (session.rs:350-372, NAMES 288). Plants 211-222 (relations_core.rs:288-310; `_CTX_PLANTS` in session_live).
  211 ctx-verdict-clear-skip IS the inventory's planted bug (`_verdict` kept across a settings change).
- session_live.py: `CTX_SLOTS`/`context_native()` (:806-815, SLICE_CONTEXT=py control), `_install_context` (:824), installed at :1071.
- handler_count.py:44-49 uses `session_live.PY_CONTEXT["_build_context"]`'s code when context.rs's is installed.
- memo_check.py:32-34: CTXMEMOS join ENGMEMOS (content, order, em_snapshot view check).
- test_context_core.py: 12 passed, 3 skipped (void here: 214 no-bound needs 20,000 sets; 216 no-fallback and 217 no-link didn't
  move any case tried: the bar's workloads/suite decide, else name void). ctx:caught 0 unplanted, >0 on plant 221 (FALSE ZEROS).
- Targeted suite files (13 test files + test_handler_count + test_catch_count) on orion: 5 failed, same 5 as SLICE_CONTEXT=py:
  test_theory_levels_match_the_solver_after_ask, test_equality_sharing_is_needed_and_works, test_protocol_on_fuzz,
  test_models_respect_transfer, test_split_beyond_the_certificate_bound_counts_as_exhausted (all on base's 127 failed list: check).
- test_engmemo_core + test_factcache_core: 24 passed.

NOT DONE:
1. Session.solver / Session.xfer handles and Session.truncated are still Python attributes on the shell (session_glue.rs:37,68,69
   set them; discovery.rs:220 sets truncated; budget.rs:315 reads it; query.rs:109-117, compile_loop.rs:98,385 read solver/xfer).
   Option: fields on SessionCore (session.rs:471) with a data descriptor on Session for the three names, Rust readers reaching
   the core directly. Or ask the architect to rule they stay to the state step (Session containers + session_live go together
   per the inventory's closing note, INVENTORY-state.md ~:296). The second is my recommendation: every other Session container is
   still Python and Session is still a Python shell.
2. Plant runs on the bar workloads; whether 216/217 are caught anywhere; 212/213/215/218-222 caught on the test, check workloads.
3. Ownership rows: port-ownership.md and .tsv (5c10b rows + state rows `_failed`, `_verdict`, `_context_sessions`, Session.*).
4. The bar (`PUSH=1 sh rust-spike/slice/p1/bar.sh land SHA`, BASE ~/sp19/sa-rust-ids-work/sa-port-182/bar-5c10a/suite on pareto1),
   check bar.sh's plant lists include `_CTX_PLANTS` and its slice test list includes test_context_core.py. Respect the 90% cutoff.
5. Report results/port-5c10b.md in port-5c10a.md's form; `test_public_comparison_catches_a_planted_history_dependence` is the
   known id()-reuse failure (sa-port-185, report a28c548: 50 of 50 fail under Rust at 67d108d; architect: report by id, don't edit).
