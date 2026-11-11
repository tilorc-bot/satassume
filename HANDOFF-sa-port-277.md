# HANDOFF sa-port-277: formula step (issue 323), seventeenth part

Branch `port/formula`, head = this commit, on rust-slice **9151316**. **Unbarred, unlanded.** Handed off at the context
note, between items (after 4e). Before this: HANDOFF-sa-port-276.md. No numbers section in results/port-formula.md yet:
the numbers are in the commit messages below (copy them into a "sa-port-277" section at the bar).

## Done this session (one commit per item)
- **010f1d6, gate 1, plant 666**: `mark-wrong-pattern` replaces the speed-only `mark-cuts-patterns` at the same site
  (term_live.py `_Mark.rollback`): the first `_CACHE` entry of the discarded run takes another key's pattern (same node
  slot/object count first, so `_common.facts`' shape check doesn't raise). R3 stays. Caught by cache_det (plant: mismatch
  mul 2; plain Rust 0, hits cosh 1 add 1 mul 3) and by the digest's `_CACHE` value row (plain Rust == Python; plant
  differs); answers equal under it. test_cache_rollback.py 3 pass; test_cache_fix.py + test_discard_exempt.py 17 pass
  twice under -n 4. **Not yet run on workloads** (needs SLICE_TERM_PLANT=mark-wrong-pattern in the bar's plant table on
  f6/opaque/value/wiring/lra, the workloads with discarded runs).
- **378973b, the seed item**: explained. The "value hash" 274 saw is the digest's *order* hash; content hashes are
  sorted reprs and equal across seeds 1/2 on cls and zero, py and rust. Cause: procmemo.rs `PyKeyMap.items()` and
  `split_items()` walked a std HashMap (per-process RandomState). Fixed: `AddLog::in_order` (memos.rs) replays the add log;
  now every process-memo row of two Rust processes equals Python's byte for byte at seed 0 (cls). livecmp's verdict never
  read the order hash (it goes to `moved_order_differs`). Kept test in test_procmemo_core.py (fails on old .so).
  Seen, not acted on: across *different* seeds `moved_q eng0:_kids` differs on zero, py vs py too (engine state follows
  set order; bar runs at PYTHONHASHSEED=0 from env.sh; py vs rust at seed 1 MATCH).
- **cb118e0, 4c**: no workload reaches relations.py:1116 (py probe: 0 number terms in 76,394 `_guard` calls on the 20
  workloads; probe fires). Test case `guard-equal-distinct` in test_relations_core.py (88 pass): one store key, the first
  object, `{'real': True}`, no guard literal, py == rust.
- **3d2fe5d, 4h**: test_clear_sequence.py: 1/One sequence (cond, eng; orders 12, 21) with PROCESS.clear() + clear_cache():
  Rust's answers and state equal Python's (5 pass). Answers: [None, True] / [True, None] (int 1 None is #96, held fix).
- **d6b5701, 4e**: two_order.py + test_two_order_twins.py (160 queries, py and rust): head 5 pass; base Python fails
  (twin 30/160, two-order 60/320 differ); **base Rust fails the same: 30/160, 60/320** (base worktree at 9151316, own
  .so; worktree removed).

## Not done (gate order)
1. (4e done.)
2. 4j: `link:second 3` in the join test (test_relations_core.py:744 computes `second`; HANDOFF-sa-port-260.md:31: two
   equal-class objects alternating on one node ask `term_id` in Python each time). One line or an exact row.
3. 4f: bar.sh invocation of test_handler_count.py and test_catch_count.py with `-p rust_plugin -p handler_count`, and
   test_cf_diff.py as a script (MISMATCHES 0). 4i: the bar's line for the digest's `_CACHE` row (keys and values: the
   row already hashes values, moved_digest.py:419; livecmp.py:103 skips it only when the counts differ from the known row).
4. The bar: PLANTS incl. 666 `mark-wrong-pattern` via SLICE_TERM_PLANT (bar.sh plant phases set SLICE_SESSION_PLANT only:
   add a term-plant route), WLS incl. cls, FM_PLANTS 612/613; every standing row. Rebuild the x86-64 .so on pareto1 (the
   Rust source changed: memos.rs, procmemo.rs).
- Not run on this head: the suite, the 20 workloads under --check entry, slice files other than test_cache_rollback,
  test_cache_fix, test_discard_exempt, test_procmemo_core, test_moved_digest, test_split_order, test_relations_core,
  test_clear_sequence, test_two_order_twins.

## File:line map (this head)
- term_live.py: `_Mark.__init__` cache_n :188, `_CACHE` skip :198, rollback plant call :235, `_wrong_pattern` :360.
- memos.rs: `AddLog::keys` :53, `in_order` :63. procmemo.rs: `PyKeyMap::items` :141, `split_items` :239.
- cache_rollback.py (CACHE_DET, vals, fired); test_cache_rollback.py :31, :40, :48 (666).
- test_procmemo_core.py :67/:73 (order cases), :100. test_relations_core.py :272 (4c case), :838.
- two_order.py (`install` used by test_clear_sequence.py); test_two_order_twins.py :28, :37, :46; test_clear_sequence.py :75, :82.
- Earlier map (276): formula.rs PLANTS :103, 612 :291; knowledge_live.py undo :285; fm_rows.py run :29; p1/bar.sh
  plants :121, extra :137, fmrows :150; livecmp.py moved_eng :86-:113; moved_digest.py `_CACHE` row :417-:420.

## Helpers and output (orion `~/sa-rust-ids-work/sa-port-277/`)
seed/ (wrap.py, run.sh, run0.sh: seed comparisons), p1116/ (probe.py, run.sh, 20 workload jsons), base/ (worktree).
No plant or counter number taken (666 reused at its site). Free: plants 614-629, 668-669; counters 649-659, 673-679.
