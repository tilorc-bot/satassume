# HANDOFF sa-port-248: formula step (issue 323), sixth part

Branch `port/formula`, head = this commit, on rust-slice 0192b35. **Unbarred, unlanded.** Handed off at the context
budget, inside gate item 1: the detached job was read, was **not** as expected, and one more cause was found and fixed
(311fb80). Items 2 to 5 are not started (item 2 is scoped in HANDOFF-sa-port-246.md, "Item 2").

## Done (details: rust-spike/slice/results/port-formula.md, last section)
- The job `~/sa-rust-ids-work/sa-port-246/j1`, read: cache_det 0 mismatches on both backends (20 workloads and the
  suite); pycalls as expected (no per-query Python added); the suite's 127 Rust failures are the same ids as 244's; the
  digest gave 16 MATCH and **4 DIFFER (f6, wiring, lra, scope)**.
- f6, wiring, lra: Rust's `_CACHE` short of non-atom keys. Cause: a refused query's rollback cut `_CACHE` to the mark
  while Rust's memo of compiled nodes kept the nodes, so the Python rerun never rebuilt the patterns. Fix, 311fb80:
  the pattern cache is not rolled back (term_live.py:147-157). Plant 666 `mark-cuts-patterns`; test_cache_rollback.py
  (2 passed; with test_cache_fix.py 9 passed). After it: per-query `_CACHE` additions equal on f6, wiring, lra; digest f6
  MATCH, wiring MATCH.
- scope (`engine:splits`) and lra (stream 2, end 2, lra 2, stats 1427) differ **on base 0192b35 too**; reproductions in
  the results section.

## Running detached: read it first
`~/sa-rust-ids-work/sa-port-248/j2` (job2.sh, started 20:42Z 10 Nov, end marker **`j2/end.txt`**; lra alone takes over an
hour), in the scratch worktree `~/sa-rust-ids-work/sa-port-248/dg` (32eb7e1 + e82147a cherry-picked, not committed +
cache-values.diff + empty known_moved.json + the clone's .so + 311fb80's term_live.py), so the clone is free.
1. `j2/dg/verdicts.txt`: the digest on 20 workloads. Expected: 18 MATCH; scope DIFFER by `engine:splits` only and lra
   DIFFER by end/stream/lra/stats only, both as on base, with `_CACHE` equal at every engine point (no "known" row in
   any .cmp: `rg -c '"known"' j2/dg/*.cmp`).
2. `j2/p666/verdict.txt`: plant 666 on f6 against Python. Expected DIFFER (`_CACHE` rows). MATCH would make the plant
   caught only by the test.
If a third workload DIFFERs or a `_CACHE` count differs, item 1 is still not done.

## Open, for the planner (in my report)
1. **The choice in 311fb80**: leave `_CACHE` as the discarded run filled it, or roll Rust's node memo back with it. I took
   the first: the second would rebuild every pattern in the rerun and leave the discarded run's rows in the native
   `_SPLIT`, which no rollback touches. It rests on "the key determines the value" (cache_det).
2. **term_discard.py** (`fresh.py --discard`) compares Python's state after the rollback with its copy from the start. It
   will now count `_CACHE` as left. Not run. It needs an exemption for `_CACHE` or the other fix.
3. **lra on base**: a refused query's rerun does one session and one consistency check fewer than Python (query 73 alone,
   `--check plain`), and queries 204 and 585 differ in end, stream and lra digests (`--only 204,585,6 --check entry`),
   answers equal. On 0192b35. No owner. `lra` is in no bar's WLS.
4. scope's `engine:splits` on base: expected gone with state part 3's 4d14638; check after the rebase.

## Not done
- Gate items 2 to 5 and 4 (a)-(c); the additions (twin harness and two-order harness as kept tests; test_term_live's two
  stale tests; bar.sh's invocation of test_handler_count / test_catch_count / test_cf_diff; the clear() test with SymPy's
  cache cleared; the 42 fallbacks' containers under item 3; the 8 two-order runs on base and step; h2.py int:condio and
  int:engio with CLEAR=process).
- After state part 3 lands: the rebase, e82147a, cache-values.diff, known_moved.json, `_SPLIT` exact,
  test_split_order.py's counts, the (iii) edits, the bar.

## File:line map (at this head)
- term_live.py: `_Mark` :133 (`_CACHE` skipped :147-157, `_note` :162), `rollback` :182, `PLANT` :282 (666 read at :155),
  `_ask` wrapper about :960 (mark :965, rollback :995), `from_env` :1076. Everything after :50 moved down by 1, after
  :147 by 11.
- cache_rollback.py (the two queries, live.py's installs, one JSON line). test_cache_rollback.py: :29, :37 (plant 666).
- dispatch.rs: `memo` :52, `sync_epoch` :173, `clear_memos` :316, `clauses_for` :353 (memo hit :357, set :418).
  common.rs: `facts` :342 (`kept` :351, cache fill :424), `units` :432.
- knowledge_live.py `_WithRusts` :246. `_common.py`: `_CACHE` :320.
- Everything else: HANDOFF-sa-port-246.md's map (common.rs, knowledge_live.py, item 2's sites) and HANDOFF-sa-port-244.md's
  (formula.rs, rows_tpl.rs, adapters.rs, wiring.py, test_cbm_noid.py, relkeys.rs, session.rs) are unchanged.

## Watch
- Worktrees of this clone to remove when j2 has ended: `~/sa-rust-ids-work/sa-port-248/dg` and `basedg` (0192b35 +
  e82147a, base .so), and 246's `dg`, 244's `base` and `q1tree`.
- My helpers in `~/sa-rust-ids-work/sa-port-248/`: perq.py + run_perq.sh + cmp_perq.py (`_CACHE` keys added per query,
  both backends), run_dg.sh (digest on named workloads), run_stat.sh / statdiff.py (engine stats per query), run_ent.sh
  (`--only` with the entry digest), lraq.py (one workload query with stats and refusal counts). All take TREE.
- Never `pkill -f` a pattern that is in your own command line: it killed my shell once.
- Plants 600-606 and 660-666 are used; 667-669 and 607-629 are free. Counters: none taken; 673-679 and 645-659 free.
- test_cache_fix.py, test_cache_rollback.py and test_cbm_noid.py are not for `run_suite.sh ... -p cache_det`: under the
  two plugins together they fail or error (13 ids in j1). Run them plain or under the backend plugin alone.
