# HANDOFF sa-port-180: step 5c9c (issue 323), the engine memos `_kids`, `_qcones`, `_glue_adapters`, `_xbasis`, `splits`

Branch port/5c9c from rust-slice 2553a68. sa-port-179's design (engmemo.rs) is now compiled, wired and tested. No bar yet.
HANDOFF-sa-port-179.md has the classification table and the design; read its "Classification" and "Open points" only.

## Done (sa-port-180)
- **Steps 1-8 of HANDOFF-sa-port-179.md "What's left" are done**:
  - Counters 250-259 (`em:py_kids`..`em:key_eq`, `bud:query_cone`); NAMES/COUNTS are 260. `BUD_CB_QUERY_CONE` (160) is retired
    (kept, `allow(dead_code)`), since `_query_cone` no longer calls back.
  - Plants 190-198 in relations_core.rs, `rel_plant` and `_MEMO_PLANTS`.
  - lib.rs registers engmemo. `__get__` takes no `signature` attribute (pyo3 refuses it on that magic method).
  - budget.rs: `_query_cone` ported (`query_cone(eng, f, link, budget)`, `bud_query_cone` with the `py_method` fallback),
    in Python's order: objs, link, sums, union, zero_args. `within_budget` calls it natively.
  - relations_core.rs `number_basis` and `guarded_adapters` go through `engmemo::get/set` (plants 193, 192); comment updated.
    `engmemo::first` was added for plant 193.
  - relevance.rs `part_consistent` and `relevant` go through `engmemo::get/put` (plant 198). The `rv:cb_memo` ticks are gone
    for `splits`. The header is updated.
  - session_live.py: `_install_engmemos` (under `SLICE_ENGMEMOS`, default rust) called from `_install_memos`;
    `'_query_cone'` is in `_BUDGET_METHODS`; comments updated.
  - memo_check.py: `ENGMEMOS`, `_canon`, `engmemo_rows`, `engmemo_view_ok`; result keys `em_sizes`, `em_content`
    (sorted), `em_order` (compared only under one PYTHONHASHSEED), `em_view_bad`; the five are checked empty after clear.
  - test_engmemo_core.py: **11 passed** (Python == Rust on every case, counters fire, **all 9 plants fire and are
    caught**, including **190 `em-qcones-clear-skip`**, which `settings:budget` catches).
- Build ok (orion). Tests on Rust: test_relevance_core, test_relations_core and test_procmemo_core give 129 passed when
  run plain. Under rust_plugin, tests/test_memos.py, test_p4_review.py, test_registry_versioning.py and
  test_writeback_provenance.py: all pass except 3 writeback_provenance ids that **fail identically on base**
  (`NotImplementedError: no provenance` x2, `_cowner`), per pareto1's ~/sp19/.../sa-port-177/bar-5c9b/suite rows. Running
  test_relevance_core.py under rust_plugin fails `test_installed`/`test_same_catches`: it's meant to run plain (check base
  if in doubt). Output is in ~/sa-rust-ids-work/sa-port-180/regtests1.
- memo_check on cert, 5c9c Rust: answers c8e58c56d2ac2beb and digest 124879cd9aca401c, **equal to 5c9b's**. em_view_bad is
  empty. Output: ~/sa-rust-ids-work/sa-port-180/mc/cert-rust.json.
- Base worktree for the switch digest: ~/sa-rust-ids-work/sa-port-180/base (2553a68, built: base-build.txt rc=0).

## What's left, in order
1. **Switch digest**: copy rust-spike/slice/memo_check.py into base/rust-spike/slice/ (untracked; it reads base's
   sa_solver). With PYTHONHASHSEED=0, run `memo_check.py WL rust OUT` for dev, fuzz, loop, zero, cert and scope in both
   trees (base needs PYTHONPATH=base:$W/sympy:$W/shim). Then `memo_check.py --cmp base.json 5c9c.json`. em_view_bad exists
   only on 5c9c. On base, `em_view_bad` is absent and the types are dicts. Expect MATCH on answers, digest, em_sizes,
   em_content and em_order.
2. Plants on the workloads, for the report's table (fired per workload, caught by): `SLICE_SESSION_PLANT=<p>` memo_check
   runs against the unplanted 5c9c run (port-5c9b.md's form; counts copy as sa-port-177's memo_check-counts.py).
3. Trace counts per workload for the five containers and `em:*` counters (the handoff-179 table still owes them), from the
   bar's counts.
4. The bar (port-5c9b.md "bar launch"; read the "90% about" line in ~/dev/architect/STATUS.md first; it said 14:13 on 9 Nov
   at 15:32, so the bar must end by about 13:13): `PUSH=1 sh rust-spike/slice/bar.sh land TESTED_SHA`. Base suite rows are
   pareto1 ~/sp19/sa-rust-ids-work/sa-port-177/bar-5c9b/suite (126 failed, 5992 passed). Check origin/rust-slice first:
   sa-port-175's 6g stack may have landed (rebase rule in the brief).
5. Report results/port-5c9c.md in port-5c9b.md's form, port-ownership.md and the .tsv (state rows for the five, and the
   `_query_cone` row moved to 5c9c), `agent report`, push.

## FILE:LINE MAP (on this commit)
- solver_rs/src/engmemo.rs: whole file is 5c9c's (SLOTS, EngineMemo, MemoSlot, get/set/put/first/len/clear, em_snapshot).
- solver_rs/src/session.rs: NAMES :17 (260), EM_* :307-321.
- solver_rs/src/relations_core.rs: plants :247-264, `rel_plant` :429-437, `number_basis` memo ~:2529-2537, `guarded_adapters`
  ~:2775-2786.
- solver_rs/src/budget.rs: `query_cone` :96, `bud_query_cone` :168.
- solver_rs/src/relevance.rs: `part_consistent` :653-657, `relevant` :665-669.
- session_live.py: `_BUDGET_METHODS` :732, `_MEMO_PLANTS` 5c9c rows :796, `ENGMEMO_SLOTS` :800, `_install_memos` :809,
  `_install_engmemos` :819.
- memo_check.py: ENGMEMOS :30, engmemo_rows :47, engmemo_view_ok :57, keys ~:140-147.
- test_engmemo_core.py: new.
- satassume/engine.py `_query_cone` :1726 (Python's, kept for PY_BUDGET and the py backend).

## Open points for the report (besides handoff-179's)
- `em-splits-no-bound` (194) and `em-slot-no-maxsize` (197) are reached only by test_engmemo_core (the harness form with
  AnswerMemo(4)). 193 and 195 need the test's own queries: say whether the workloads reach them, from step 2.
- `_qcones` is emptied at 50,000 (`em:full`); no workload is likely to reach it. The bound has no plant of its own.
