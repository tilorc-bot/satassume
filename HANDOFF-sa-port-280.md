# HANDOFF sa-port-280: formula step (issue 323), nineteenth part

Branch `port/formula`, head = this commit, on rust-slice **9151316**; **tested source 7b637e2** (later commits are
results/handoff only). **Full bar RUNNING on pareto0; unlanded.** Handed off ~08:40Z on the architect's word (context;
the bar runs past 09:20Z: extra, suiteplants and fmrows remain, fmrows runs lra three times).

## Done
- **Prep read (212a7d6, .so 802adb75): clean.** Suite 126 failed / 5992 passed / 23 skipped, same failing ids as
  sa-port-247 bar-part3 (new 0, gone 0, changed 0); passed 5991 no firing + 1 firing (test_invariants.py::
  test_ci_stream_reports_only_what_replays); handler multiset same (39 rows). 20/20 MATCH; cls and zero twice MATCH both
  backends. Rows: orion `~/sa-rust-ids-work/sa-port-280/prep/rows.md` (rows278.py).
- **7b637e2, `_nt_mark` in Rust (gate for 280, R3).** dispatch.rs `DispatchStore` (`Dispatch.store(part, name)`:
  native, name, items, `_nt_mark`, `_nt_rollback`) replaces knowledge_live.py's Python `_Store`; term_live.py
  `_Seen._nt_mark = sa_solver.formula_seen_rows` (a builtin isn't bound). +18 net lines. Orion tests pass (discard_exempt
  10, term_live 20, cache_rollback 3, cache_fix 7, knowledge_wire 6, install_order 198, session_boundary 27).
  pareto1 build .so **fdcdeaab** (bar.sh build, OUT sa-port-280/build). Spot-check on pareto0: f6 opaque value wiring MATCH.
- **cache_det on 7b637e2: 0 mismatches both backends, 20/20** (hits py 14,969, rust 7,003; answers py == rust plain).
  **knowledge_live.py base -> head -> after**: _nt_mark 0 everywhere after; module at or below base on every workload
  (f6 338->6161->328, wiring 164->13154->125, lra 4434->8227->4326). Table: results/pc280-7b637e2.md. term_live _Seen
  after = discards (lra 457 vs 456 discarded runs), not per query.
- **Group D shares (sampler, shared, pareto1, 7b637e2)**: all D dev 25.1% -> 25.8%, fuzz 34.5% -> 34.1% (f252daf -> 7b637e2;
  orion `~/sa-rust-ids-work/sa-port-280/gd/dmods.json`, run-7b637e2/SUMMARY.md). **Seconds NOT measured**: pareto1 held by
  hand-sim-bf's shared lease (renewed 5h+). A quiet-lease job is queued (`machine run pareto1 --quiet --wait 4h`, from
  08:12Z; onlease280.sh -> pareto1 `~/sa-rust-ids-work/sa-port-280/gd/timing/end.txt`; log orion gd/timing-lease.log). If it
  ran: `python3 gd/med280.py timing/time.jsonl gd/dmods.json`. Per the architect: land without it; Group D seconds +
  memo cost go on OWED with a STATUS footnote naming hand-sim-bf.

## Bar (pareto0, lease fd007d5a, `~/sp19/bar280.sh`, copy orion `~/sa-rust-ids-work/sa-port-280/bar280.sh`)
Out `pareto0:~/sp19/sa-rust-ids-work/sa-port-280/bar`, **end marker `bar-end.txt`** ("END rc time so-sha8 sha").
Config = 278's planned config (PLANTS 15 incl. term:mark-*; SUITE_PLANTS "zero fm-ite-swap same-is dispatch-keeps-memo
fm-hand-instrument-by-name fm-hand-patched-direct"; WLS = 247's 14 + cls; FM_WLS the 20; FM_PLANTS fm-atoms-merge-pred
fm-args-drop-last; TESTS=all split; DIRECT relations_direct.py 300 0; N=6). No build phase (pareto0 has no cargo; .so
fdcdeaab copied in). BASE = sa-port-247/bar-part3/suite (copied to pareto0).
Read at handoff (`bar/sum-partial.txt`; rerun bar_sum with `export HOME=/home/tilo/sp19` before sourcing env.sh):
- tests: 62 files, all exit 0.
- suite: **127 failed** / 5991 passed: changed outcome 1 = tests/test_public_incremental.py::
  test_public_comparison_catches_a_planted_history_dependence (passed -> failed; `assert len(run_stream(ops)) == 2`, got 1).
  This is the known planted-history id()-reuse failure under Rust (sa-port-185, a28c548; SIBLINGS block: report by id,
  don't edit); it passed in the prep suite on 212a7d6. Handler multiset same as base; caught rows differ 0; TermFault 0.
- live (dev, fuzz) and plants done; plant rows on dev/fuzz in sum-partial.txt. "plant handler files with 0 rows: 30" is
  new in the summary (prep had no plant phase): read what bar_sum counts there before calling it.
- To do when bar-end.txt exists: `bar_sum.py` -> sum.txt; extra/summary.txt (py vs py control, py vs rust per WL);
  fmrows/check.txt (exit 0) and fmrows-PLANT/check.txt (exit 1 = caught); suite-plants. Then the verdict list (gate item 5)
  and `bash rust-spike/slice/p1/bar.sh land 7b637e2` in this clone (PUSH=1 to land).

## File:line map (this head)
- solver_rs/src/term/dispatch.rs: `_nt_mark` :337, `_nt_rollback` :346, `_nt_rows` :368, `store` + `DispatchStore` after
  `clauses_for` (~:466-:500). knowledge_live.py `install_dispatch` stores :254-:256. term_live.py `_Seen` :110-:121,
  `_Mark` :188-:235.
- p1/bar.sh as in HANDOFF-sa-port-278.md (penv :85, suite() :96, tests :108, plants :132, extra :148, fmrows :164).
- Job scripts (orion `~/sa-rust-ids-work/sa-port-280/`): aux280.sh (pareto0 aux, done), bar280.sh, pc280.py, gd/tools
  (go195/job195/post195, paths to sa-port-280), gd/tools280 (time280.sh, onlease280.sh), gd/med280.py, gd/dmods280.py.
No plant or counter taken.
