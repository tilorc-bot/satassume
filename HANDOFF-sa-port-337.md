# HANDOFF sa-port-337: witness check, land-only step stopped with Status: question; NOTHING IS LANDED

Branch port/witness-check, worktree ~/sa-rust-ids-work/sa-port-328/wt (clone ~/dev/sa-port-19), on rust-slice 32ba9a3.
Tested SHA 786410d (also origin `bar/witness-check-786410d`, kept), venv .so cad764d46471b1c6, bench .so
0982a28074215658. No source or test was changed by this step; its commit holds results and this file only.

## Read and decided

- (2b) dev and fuzz digests equal on and off, python and rust (31cd0945c07f02a6, 173502b6ef285ad6; certified 159
  and 1060); test_witness.py alone 102 passed in all four cells; iv 128 runs, 0 runs differ off against on. Suite by
  id: off against base 0 ids differ on both backends; **on against off 7 ids differ, all in tests/test_witness.py**.
  Cause: test order, not the switch (results/witness-check.md section 8). That is a moved id, so Status: question.
- (3) S1 on 786410d met: fuzz -28.2% py, -19.2% rust; dev -2.7% py, +1.1% rust with overlapping ranges.
  `_users_knowledge` 6.2 us py / 8.1 us rust a certified call on dev, 5.2 / 5.6 on fuzz; no memo needed.
- (4) NOT given. sa-port-336's bar is void (no .so in the bar's clone; every Rust row empty; `END 0` regardless).
  Relaunched detached at 09:42Z 19 Nov: gobar337.sh 786410d cad764d46471b1c6, pareto0 shared lease 34a14557, about
  2 h. END marker: orion ~/sa-rust-ids-work/sa-port-337/gobar-end.txt (`END rc <pareto0's bar-end line> | time`).
  Checked after launch: build.txt has the clone's .so at cad764d4, direct.txt exit 0, the suite writes rows.
- results/witness-check.md: header and sections 1, 2, 4, 5, 7 (one paragraph), 8, 10, 11 are on 786410d. Sections 6
  and 9 and section 7's table are from the earlier SHAs.

## Not done, in order

1. The planner's ruling on the 7 ids. If it is a fix: in tests/test_witness.py only, restore the default registry
   before the first assertion of the seven (map below). Then refreeze, restage, and rerun the suite by id, the
   digests, iv and a full bar on the new SHA. Whether a tests-only change needs S1 again is the planner's call.
2. Read the rerun bar (~/sa-rust-ids-work/sa-port-337/bar/bar/sum.txt): witness:on rows MATCH against pywit and
   answer_diff 0 against off on all 17 workloads; 749 and 750 caught by answers; 751, 752, 754 by kept tests in their
   suite rows; quiet handler rows; wall time per row (`python3 ~/sa-rust-ids-work/sa-port-337/tools/wall336.py
   ~/sa-rust-ids-work/sa-port-337/bar/bar`). First check direct.txt ends `exit 0` and "suite: no rows" is absent.
   Its suite rows (6 workers) can show the 7 ids by distribution: check which worker ran the two leaking tests.
3. Land only on a ruling: `bash rust-spike/slice/p1/bar.sh land SHA`, then PUSH=1; delete the origin bar branch after.
4. OWED to name: Engine.stats' 13th key on the default path; ent_record_certified has no tick; bar.sh's witness rows
   have no plant-fired counter ([147]). New, for the bar tooling: no phase of bar.sh fails when sa_solver does not
   import (a void bar exits 0).

## FILE:LINE MAP (786410d)

- tests/test_witness.py: `on` fixture :25; test_registered_knowledge_falls_through :276 (first assertion :280);
  `users_knowledge` fixture :294 (restores `registry._by_class`, `_lazy`, the two caches, then `bump()`, after the
  test only); the five-case test :310 (first assertion :317); test_on_skips_the_session_and_counts_the_query :396.
- The two leaking tests (older, on main and rust-slice): tests/test_templates.py:656 (registers at :672),
  tests/test_p4_review.py:26 and :33.
- satassume/witness.py: `_TEMPLATES`/`_THEORIES` :130-131, `_users_knowledge` :134-163, `witnesses` :508, the two
  guards at its end :553-556.
- rust-spike/slice/results/tools337/: job337bar.sh (checkout before the copy :19, the hash guard :21), gobar337.sh,
  wprobe337.py (a pytest plugin that says after each test why the check would fall through; WPROBE_OUT=file).
- The rest: HANDOFF-sa-port-336.md's map (bar.sh, bar_sum.py, tools336) and HANDOFF-sa-port-333.md's (function source).
- witness-check.md: section 2 :50, section 4 :260, section 5 :292, section 7 :398, section 8 :424, section 10 :516.
