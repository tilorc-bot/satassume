# Handoff: sa-port-334 to the next session (issue 323, F_MAYBE_NAN removal)

Handed off at the architect's instruction (rule 11) with the 2x2 read and equal, and **the bar and the row-bytes check
still running, detached**. Nothing is landed. rust-slice is at ec34788.

## State

- Branch `port/maybe-nan-removal`. Tested SHA **f4ce4b2** (source), from rust-slice ec34788; one commit above it holds
  results/tools334 and this file (no source). Worktree: orion `~/sa-rust-ids-work/sa-port-332/wt` (clone ~/dev/sa-port-24).
- x86-64 .so of f4ce4b2: **c20c326f** (built on pareto1 by pc334.sh's head run, copied to pareto0). Orion .so 09e6fa11.
- f4ce4b2 is 332's 7dd452c plus the planner's ruling (2): plant 753 is now `dispatch-nan-arg-on`. At `opaque`'s call
  `may_be_nan` is taken as True for every argument; `fired` counts the `opaque` calls whose result that changes.
- `dispatch::may_be_nan`'s cases are unchanged from ec34788 (the plant parameter and its three branches are gone, which
  were off for the dispatch). `git diff ec34788 f4ce4b2 -- satassume` is empty, so `_applied_to_nan` is unchanged.

## Two jobs are running, both detached from this session

| job | host | end marker | written by |
|---|---|---|---|
| bar | pareto0 | `/home/tilo/sp19/sa-rust-ids-work/sa-port-334/bar-end.txt` | results/tools334/job334.sh:40 `echo "END $? ..." > $L/bar-end.txt`, then :43 `echo "WATCHER-END ..." >> $L/bar-end.txt` (wait for the second line) |
| row bytes, head half | pareto1 | `/home/tilo/sp19/sa-rust-ids-work/sa-port-334/rb-all-end.txt` | results/tools334/rbgo334.sh, last line `echo "ALLEND ..." > $P/rb-all-end.txt` (rb334.sh:8 `fin()` writes rb-head/end.txt before it) |

- Bar: shared lease 28cc384f, started 04:50Z 19 Nov. Phases so far (bar/phases.txt): tests 04:53:29Z, suite 04:55:19Z,
  live 05:09:43Z, plants 05:21:01Z, all exit 0. Left: extra (15 workloads), suiteplants (about 10 rows at 1 m 50 s),
  fmrows, sum. My estimate of the end is 06:30Z to 07:00Z; it is an estimate.
- Row bytes: shared lease be8dcf41, relaunched 05:30Z. The base half took 30 minutes (rb-base, ec34788, END done
  05:23:19Z, 40 of 40 rows run 0), so the head half should end near 06:00Z. My first launch of it ran under this
  session's shell; I stopped it at 18 of 40 rows and started the head half again from zero, detached.
- Orion side of each is `machine run` in its own session (setsid); logs ~/sa-rust-ids-work/sa-port-334/bar-launch.log
  and rb-launch2.log. No waiter shell of mine is left.

## Read so far

- **2x2 equal** (pareto1). Base ec34788 (.so 8cb9b507) and head f4ce4b2 (.so c20c326f): 20 of 20 references exit 0
  and 80 of 80 cells run 0 cmp 0 on each. Rows: pareto1 ~/sp19/sa-rust-ids-work/sa-port-334/pc-base, pc-head;
  comparison pccmp-head-base.txt there.
- **Probe**: `templates/__init__.py` goes from 2,187,213 calls to 20 (the imports) in the two convert-py cells and
  stays at 20 in the two convert-rust cells. The falls are `_may_be_nan` 1,072,885 and its generator expressions
  781,317 and 332,991. No other probed file moved, 0 per-function rises, knowledge_live equal per workload, queries
  equal (30,753). **The count stays 21 of 32**: STATUS.md:19 already counts `templates/__init__.py`, with the footnote
  "`_may_be_nan` called per query only by convert.py (input layer)". That footnote no longer applies; tell the architect.
- **Plant 753 on orion** (.so 09e6fa11, `opaque` workload, --check entry): fired 61, DIFFER (answers_sha c3a4f036
  against c7e1a7ca; True 179 -> 18, False 169 -> 23). `dispatch-opaque-off`: fired 274, DIFFER, as port-6g.md:47
  ("`dispatch-opaque-off` fires 274 on the opaque workload, caught (DIFFER; 0 elsewhere)").
- **Bar rows seen before the handoff, not yet read properly**:
  - tests: 72 files, none not exit 0. direct exit 0.
  - suite, plain: **127 failed / 5991 passed, against base 126 / 5992**. The id is not read. 326's `walk:rust` row had
    the same shape from the planted-history test; that is a guess until the id is read (step 2 below).
  - dev and fuzz plant rows (last line of each .cmp): dev 753 DIFFER; dev `dispatch-opaque-off`, `walk:rust`,
    `both:rust` MATCH; fuzz all four MATCH. Fired counts not read.

## Open, in order

1. Wait for both markers. Read the row bytes: pareto1 ~/sp19/sa-rust-ids-work/sa-port-334/rbcmp.txt. The one line
   wants: masked digest equal between the trees on all 20 workloads in both walker cells, bit-32 rows N on base (327
   counted 5,838 True calls on `opaque`, 0 elsewhere) and 0 on head, head raw == head masked, `shape_bad` 0, and
   `rows:_RustWalk` non-zero in the crust cell (which walker ran).
2. Read the bar on pareto0 (`B=~/sp19/sa-rust-ids-work/sa-port-334/bar`): sum.txt; then tools318/barcmp318.py NEW OLD
   against 326's bar (~/sp19/sa-rust-ids-work/sa-port-326/bar) for suite rows by id, and tools318/wall318.py for the
   row wall times. Name the plain suite's differing id. If it is the planted-history test
   (tests/test_public_incremental.py:204), run a28c548's repeat check (results/tools327/run1.sh, sweep.sh) before
   calling it the id()-reuse flake; without that it is a DIFFER (planner [137e]).
3. For 753 and `dispatch-opaque-off`: fired count and verdict per workload (17), and their suite rows against this
   bar's plain row. Report whether a workload answer or a suite id catches 753.
4. Check env-summary.txt (which SLICE_ variables each suite row had), the `so_sha` the runs loaded (c20c326f), and
   the count of quiet catches (engine.py:1906) as earlier bars report it.
5. Land per the brief if all holds: `machine ls`, rule [91], `bar.sh land f4ce4b2` without PUSH, read the diff, then
   PUSH=1. Then results/maybe-nan-removal.md and the report. The probe "after" was taken on f4ce4b2, the tested SHA.

## Bar config (results/tools334/job334.sh)

TESTS=all, suite, live, plants, extra (15 workloads), suiteplants, fmrows, sum; N=6; BASE 326's suite rows.
PLANTS = `dispatch-nan-arg-on dispatch-opaque-off walk:rust both:rust`. SUITE_PLANTS = `zero`, those four, and the
five `convert:*`. Left out: the three `convert:nan-*` rows (retired) and the fm-*, term:* and frames:rust plants of
steps this one does not touch.

## File:line map (f4ce4b2)

- solver_rs/src/term/dispatch.rs: `opaque` :102, plant 753 :112, `may_be_nan` :126, fired count :436-440,
  `dispatch-opaque-off` :441.
- solver_rs/src/term/walk.rs: reserved comment :51, `term_row_native` :634. table.rs: reserved comment :57. py.rs:343.
- convert.py: flags :72, `term_row` :269, `rust_walk` :397, WALK_PLANTS :446. term_shadow.py:160. term_history.py:78-83.
- test_convert_walk.py: ALL_PLANTS :37, `test_reserved_bit_is_zero` :145, `test_plant_is_caught` :222.
- knowledge_live.py: PLANTS :68-70 (753's name at :67 and :70). p1/bar.sh: `penv` :91, `fired()` :112.
- results/tools334/: pc334.sh, pcby334.py, pccmp334.py (2x2 and probe); job334.sh (bar launcher); rowbit334.py,
  rb334.sh, rbgo334.sh, rbcmp334.py (row bytes). results/tools318/: barcmp318.py, wall318.py. results/tools327/:
  run1.sh, sweep.sh.
- results/may-be-nan-step.md:153 is the shape of the last bar's write-up.
