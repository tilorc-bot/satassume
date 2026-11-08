# HANDOFF sa-port-151: step 5c7, `_union` and `_within_budget` only; budget workload drafted but too slow under live.py (issue 323)

Branch port/5c7 in /home/tilo/dev/sa-port-7. The head is the commit carrying this file. It is **not rebased**: rust-slice moved to
4dd2ed9 (adapters B+C1), which collides with this branch's counter and plant numbers (below). I handed off at about 125k.

## Rulings since sa-port-148
- Planner's inventory ruling (8 Nov ~06:22, ~/dev/architect/briefs/addenda/sa-port-inventory-ruling.txt): 5c7 lands `_union` and
  `_within_budget` only. `_over_budget` and `_note_budget` go to 5c10d, their Rust code kept on port/5c7. The budget workload and
  its plant stay on 5c7's bar.
- Planner's follow-up (in sa-port-5c7-move-ruling.txt): `_struct` and `_drop_cones` go to 5c10.

## Done in this session (all on orion, build OK)
- session_live.py: `_BUDGET_METHODS` wires only `_union` and `_within_budget`. `_over_budget`/`_note_budget` (`bud_over_budget`,
  `bud_note_budget` in budget.rs) are unwired unless `SLICE_BUDGET_FLAGS=rust`, which isn't a landing configuration.
- budget.rs: 5 branch counters, `bud:union_cone_none`, `bud:union_over`, `bud:union_partial`, `bud:within_partial`,
  `bud:within_false` (session.rs indices 149-153; NAMES/COUNTS sized 154).
- budget_wl.py (new) and live.py `load()` "budget". It covers C-WIDEADD sums (401 and 420 terms), unions whose running weight passes 400,
  sums overlapping in one symbol, k overlapping sums `s, s + b_i` under a set (the catch for `union-skip-overlap`: the exact
  weight is about |s| + 2k, but counting whole cones gives about k(|s| + 2) > 400, so True/False becomes None), and
  `_within_budget`'s `wp + wa` test. Sums share `b0` with the rest of the query, because sympy_api's relevance split drops a disjoint
  set before the engine weighs it. My first draft did that: answers None with `last_budget_limited` False.
- TSV: `_struct` and `_drop_cones` are set to 5c10, and `_over_budget`/`_note_budget` to 5c10d (Python). port-ownership.md's engine.py
  5c7 line is split into four lines: landed 5c7 for `_union`/`_within_budget`, 5c9, 5c10 and 5c10d. **"landed 5c7" is written
  ahead of the landing: correct it if the bar fails.**

## The blocker: speed under live.py
`python budget_wl.py` (fresh engine per query, no tracing) answers all 30 queries in about 2 min. Over-budget queries take
0.0-0.2 s, (8,50) about 1 s, (5,80) about 2.3 s and (3,130) about 10 s. Under `live.py budget` (warm engine, `--check entry`),
queries 0-13 (over budget, no session) were quick, but **each overlap query took about 14 min**. After 56 min Python had 18 rows
and Rust 21, so I stopped both by PID. Those 18 shared rows MATCH: ~/sa-rust-ids-work/sa-port-151/cal1/partial-cmp.txt, answers in
budget-{py,rust}.jsonl. No counters or plants were read: the session reports are written at the end.
Next: find what costs this. Run one query with `live.py budget py OUT --only 14 --check plain`, then with `--check entry`,
to see whether it's the tracing or the warm engine. Then reshape the catch so every session is small. Options:
- more, shorter sums, e.g. k=16, |s|=25, plant weight about 432;
- a predicate whose session needs no LRA rows, e.g. integer or finite.

The bar needs the workload in single-digit minutes per mode. Keep at least one `union-skip-overlap` catch, plus `bud:union_over`,
`bud:union_partial`, `bud:union_cone_none`, `bud:within_partial` and `bud:within_false` each above 0 on Rust.
The planned `_sum_over` queries (proposition Q.positive(S(0,200)) under sets on the same 200 symbols) are quick only when the
set's extra objects are already in the proposition's cone. Two variants with new objects took 37 s fresh and were dropped.
`within-no-link` is likely void on live: `link` changed no weight in the cases I tried (no vocabulary functions registered).
Run it and `union-skip-overlap` on the suite too.

## Rebase onto origin/rust-slice 4dd2ed9 (adapters landed): renumber
- session.rs: adapters took counter indices 140-154 (NAMES sized 155). Move BUD_* from 140-153 to 155-168, size NAMES/COUNTS at
  169, and keep the NAMES order matching the indices.
- relations_core.rs: adapters took plants 104-110. Move UNION_SKIP_OVERLAP .. NOTE_BUDGET_KEEP_FLAG from 104-107 to 111-114.
- session_live.py: `_REL_PLANTS` gained the adapters' names. The budget plants are separate (`_BUDGET_PLANTS`), so keep both.
- bar.sh now has a push guard: the source must equal TESTED. So rebase first, run the bar on the rebased head, then
  `PUSH=1 sh rust-spike/slice/p1/bar.sh land THAT_SHA`.

## FILE:LINE MAP (this head, before the rebase)
- rust-spike/slice/solver_rs/src/budget.rs: `union` :48 (branch ticks inside), `within_budget` :~105, `bud_union`,
  `bud_within_budget` (ticks `bud:within_false`), `bud_over_budget`, `bud_note_budget` (unwired).
- rust-spike/slice/solver_rs/src/session.rs :192-207: BUD_* 140-153; NAMES :17 and COUNTS :~215 sized 154.
- rust-spike/slice/solver_rs/src/relations_core.rs :156-159 plants 104-107, names in the plant match :273-276.
- rust-spike/slice/session_live.py :715-728: `_BUDGET_METHODS`, `SLICE_BUDGET_FLAGS`; install hook :~870.
- rust-spike/slice/budget_wl.py: `_over`, `_overlap`, `_sum_over`; `python budget_wl.py` times each query fresh.
- rust-spike/slice/live.py `load()` "budget" branch.
- satassume/engine.py: `_union` :1759, `_within_budget` :1783; sympy_api.ask's relevance split decides what reaches them.
- ~/sa-rust-ids-work/sa-port-151/cal1/: run.sh (py, rust with SESSION_REPORT, then both plants, then livecmp), fresh.txt.
- Smoke counts (sa-port-148, ~/sa-rust-ids-work/sa-port-148/smoke1/*-rust.session.json): over_budget 0 on dev, fuzz and zero;
  union 615/8621/277; within_budget 840/3127/724.

## Still to do
1. Reshape and time the workload (above). Then run Python, Rust and the two plants on it, plus dev and fuzz.
2. Rebase and renumber, build, run a short check, push port/5c7.
3. The bar on pareto1: `PLANTS="union-skip-overlap within-no-link" WLS="zero budget" SUITE_PLANTS=zero`,
   base ~/sp19/sa-rust-ids-work/sa-port-141/bar-5c7t2/suite, launched as port-5c6.md describes.
4. results/port-5c7.md in port-5c6.md's form; `agent report`; land.
5. Ask the architect to confirm `_struct`/`_drop_cones` -> 5c10. The planner's follow-up already rules it, so this may be moot.
