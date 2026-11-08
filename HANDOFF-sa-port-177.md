# HANDOFF sa-port-177: step 5c9b, switch digest equal, plants caught, bar RUNNING on 73c10d3 (issue 323)

Branch port/5c9b on origin/rust-slice e0ec542. **Tested source: 73c10d3** (5397118 + test_procmemo_core.py). Later commits
on the branch touch only results/ and this file (outside the landing guard).

## Done (rows under ~/sa-rust-ids-work/sa-port-177/)
1. **Switch digest** (`mc/`, run.sh): memo_check base Rust (worktree `base-tree` at e0ec542, own build) vs 5c9b Rust on
   dev, fuzz, loop, zero, cert, scope: answers and digest equal on all six, `--cmp` MATCH, equal to 5c9a's digests; the five
   tables' rows equal; view_ok, cleared [], rerun_same on all. Filled in results/port-5c9b.md.
2. **`_SPLIT` len cause found** (`split/`, who.py on cert): knowledge_live `rust_compiled` wraps a fresh Pattern per call
   (`_wrap`), outside `_common._CACHE`; `_SPLIT` keys by id(clauses), so the same symbol pattern adds entries. In the report.
3. **Plants via memo_check** (`pl/`, counts copy `memo_check-counts.py`): 181 C everywhere; 182 S everywhere; 185 S on dev,
   fuzz, cert (not loop, zero, scope); 186 S+A on all but loop (0 fired on loop); 187 V C S everywhere; 180, 183, 184 fire 0
   on every workload. Fired counts in each `pl/WL-PLANT.json` "counts".
4. **test_procmemo_core.py** (committed 73c10d3): 6 passed; catches 180 (`split:lens`), 181 (`split:after_clear`), 183 and 184
   (`neigh:*`); counters pm:full 1, pm:neigh 142, pm:cb_rules 47. tests/test_engine.py:195 runs Rust's neighbourhood under
   rust_plugin but passes under 183/184 (checked).
5. **Registry tests** (`regtests/`): test_memos.py + test_p4_review.py under rust_plugin+handler_count: 10 passed, caught empty.
6. results/port-ownership.md (neighbourhood row split from `_query_cone`) and .tsv (neighbourhood, state: _NEIGH, 4 new state
   rows) done. **results/port-5c9b.md drafted**: placeholders BAR_SHAS, BAR_ITEMS, PLANT_TABLE, KEPT_TABLE, NOT_RUN to fill.

## Running
**The bar**, launched 15:07 UTC from orion: `bar-launch.sh` (machine run pareto1 --shared, lease 6a0af971), output
pareto1 `~/sp19/sa-rust-ids-work/sa-port-177/bar-5c9b/` (end.txt written on finish; phases.txt; sum via bar_sum.py).
PLANTS = 180-187 names, WLS = loop zero cert scope, TESTS = 5c9a's 14 + test_procmemo_core.py, base suite rows
sa-port-174/bar-5c9a/suite. ~35-40 min expected.

## Next
1. When end.txt exists: read the bar's summary (`sum` phase output in bar.out / bar_sum), fill the placeholders in
   results/port-5c9b.md in port-5c9a.md's form: suite three numbers, passed split by firing, handler multiset vs 5c9a's
   (39 rows: `_consistent` AttributeError 34 `_ok` + 4 `_rb_clauses`; `_build_context` "Already mutably borrowed" 1),
   live MATCH, plant table (merge memo_check letters above with the bar's D column and T), kept shares per reason vs 5c9a's
   (dev 24 out-of-scope 1.21%, rest 0), not-run list as 5c9a's (+ seed1, + full suite under any plant; the void plants: none
   void if T counts, else 180/183/184 void on workloads).
2. Landing order: whichever of 5c9b and sa-port-175's 6g c3-c5 stack has the first clean bar lands first. If rust-slice
   moved, rebase, `bar.sh land 73c10d3` without PUSH, rerun if the guard sees incoming source diff.
3. Land: commit report, then in the clone `PUSH=1 bash rust-spike/slice/p1/bar.sh land 73c10d3`; report tested/landed SHA and
   incoming diff; `agent report`.

## FILE:LINE MAP (73c10d3)
- rust-spike/slice/test_procmemo_core.py (new): `_main` :27, tests :75-100
- rust-spike/slice/solver_rs/src/procmemo.rs: split_put :229 (bound, plant 180), pm_neighbourhood :327
- rust-spike/slice/solver_rs/src/relations_core.rs: plants 180-187 :227-243
- rust-spike/slice/session_live.py: _MEMO_PLANTS :789-794; _install_procmemos :809
- rust-spike/slice/knowledge_live.py: `_wrap` :80, `rust_compiled` :258 (the `_SPLIT` len cause)
- rust-spike/slice/p1/bar.sh (land :34-62)
- rust-spike/slice/results/port-5c9b.md (draft), port-5c9a.md (form)
