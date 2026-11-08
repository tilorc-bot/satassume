# HANDOFF sa-port-154: step 5c7 rebased on b838d3f, budget workload fixed, bar running on 1649e9b (issue 323)

Branch port/5c7 in /home/tilo/dev/sa-port-7. **Tested source 1649e9b** (port/5c7 on origin/rust-slice b838d3f, 6g(b)). The head
adds only this file. Handed off at about 142k.

## Done
1. **Why the overlap queries were slow:** live.py's `--check entry` digests the whole solver state after every outermost solver
   call. q14 (k=8, |s|=50, Q.positive) made 15,022 entries in one session: fresh engine 0.9 s, `--check plain` 1.6 s, `raw` 2.2 s,
   `end` 5.0 s, `entry` more than 5 min (stopped; sa-port-151 saw about 14 min). The warm engine isn't the cause.
   Rows: ~/sa-rust-ids-work/sa-port-154/t1, t2.
2. **Workload reshaped** (budget_wl.py): overlap sums on integer/real/finite (no LRA rows), k=16 |s|=25 and k=12 |s|=33;
   `_sum_over` on Q.integer with 0, about 100 and 200 set objects outside the proposition's cone (the last is None,
   budget-limited). 28 queries, about 12 min per mode under `entry`, about 0.1 s each fresh.
   cal2 (~/sa-rust-ids-work/sa-port-154/cal2, on the pre-6g rebase, same 5c7 code): Rust **MATCH** (28 q, sessions 17, end/stream 0
   diffs, answers_sha 35bc2c4a937bebc0); `union-skip-overlap` **DIFFER** (7 answers, first q14 True->None); `within-no-link`
   **MATCH (void)**, though its counters move (bud:union 38->31, union_over 6->3). bud:* on Rust: union 38, within_budget 37,
   union_cone_none 6, union_over 6, union_partial 69, within_partial 6, within_false 16; over_budget/note_budget 0 (unwired).
3. **Bug fixed:** `session_live.from_env` never passed `_BUDGET_PLANTS` to `sa_solver.rel_plant`, so both budget plants were
   void on every run before 1649e9b (sa-port-151's plant runs included). session_live.py :908.
4. **Rebased** on b838d3f (6g(b)), renumbered: BUD_* 156-169, NAMES/COUNTS 170, slot 155 = "rsv:155" held for adapters C2's
   `cf:pi_laurent` (C2 not landed when I rebased); plants 114-117 (C2 has 111-113). 6g(b)'s plants are name-based
   (rows_tpl.rs PLANTS), no collision. Only conflict: live.py's workload line (kept both). Short check on orion: build OK,
   test_session_limits.py 242 passed, budget `--check plain` Rust MATCH, union-skip-overlap DIFFER (~/sa-rust-ids-work/sa-port-154/chk).
   Pushed port/5c7 (force-with-lease over 38b0511, own branch).

## Running: the bar on pareto1
Launcher ~/sa-rust-ids-work/sa-port-154/bar/launch.sh (log launch.log, exit.txt when the machine run ends). Rows on pareto1 at
`~/sp19/sa-rust-ids-work/sa-port-154/bar-5c7/` (`sum.txt`, `commands.txt`, `done.txt`). Config: PLANTS="union-skip-overlap
within-no-link" WLS="zero budget" SUITE_PLANTS=zero, BASE sa-port-141/bar-5c7t2/suite, TESTS = 5c7t2's 11 files, DIRECT
"relations_direct.py 300 0", N=8. Started 08:06 UTC. To stop it: the machine run's PID from `ps` on orion matching launch.sh (mine
only), never by SHA pattern.

## Next
1. Read sum.txt when done.txt exists. If `within-no-link` fires on dev/fuzz but isn't caught, it isn't in `zero`: run the
   suite under it separately (as port-5c6.md did for glue-of-plain: phases build suite suiteplants sum, SUITE_PLANTS=within-no-link).
   Expect it void (no relation specs change the verdict; see the planner's _union argument).
2. LANDING ORDER: C2 (sa-port-153, bar on 3a34da4) and 6g(c1) (sa-port-155, bar on 4c3356d) were on pareto1 when mine started.
   If either lands first: rebase, `sh rust-spike/slice/p1/bar.sh land 1649e9b` without PUSH, read the incoming diff. C2's diff
   touches session.rs (replace "rsv:155" with its `cf:pi_laurent`) and source the guard covers, so the full bar reruns on the
   new head. Then `PUSH=1 sh rust-spike/slice/p1/bar.sh land NEW_TESTED`.
3. results/port-5c7.md in port-5c6.md's form, `agent report`, push.
4. The clone's sa_solver.so is the old 38b0511 build: rebuild before local runs. The rebased build is in the worktree
   ~/sa-rust-ids-work/sa-port-154/wt (branch port/5c7-rebase = 1649e9b); `git worktree remove` it when done.

## FILE:LINE MAP (1649e9b)
- rust-spike/slice/solver_rs/src/budget.rs: `union` :48 (plant at the `planted(UNION_SKIP_OVERLAP)` test), `within_budget` :~105
  (`planted(WITHIN_NO_LINK)` in `link`).
- rust-spike/slice/solver_rs/src/session.rs: NAMES :17 (170, "rsv:155" :44), BUD_* :213-230, COUNTS :238.
- rust-spike/slice/solver_rs/src/relations_core.rs: plants 114-117 after PAY_EQ_FLIP; names in the plant match.
- rust-spike/slice/session_live.py: `_BUDGET_METHODS`/`_BUDGET_PLANTS` :~720-729, from_env arming :~905-909.
- rust-spike/slice/budget_wl.py: `_over` (q0-13), `_overlap` (q14-23), `_sum_over` (q24-27).
- rust-spike/slice/results/port-ownership.tsv :79-101 (new owners already written; "landed 5c7" ahead of the landing).
