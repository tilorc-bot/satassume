# HANDOFF sa-port-148: step 5c7, part 1 (four stateless budget rows) coded, not yet barred (issue 323)

Branch port/5c7 in /home/tilo/dev/sa-port-7, from origin/rust-slice 44f4762. The head is the commit carrying this file.
I handed off at about 141k context.

## Scope after the move ruling (planner, 8 Nov ~06:15; ~/dev/architect/briefs/addenda/sa-port-5c7-move-ruling.txt)
- 5c7 lands four stateless rows: `Engine._union`, `_within_budget`, `_over_budget`, `_note_budget`.
- `_struct`, `_query_cone`, `_drop_cones` and `neighbourhood` go to 5c9, and `_cone_info` goes to 5c10. Each is ported together
  with its container. This is recorded in port-ownership.tsv; port-ownership.md still needs the matching line.
  - `_struct` and `_drop_cones` go to 5c9 because 5c9 moves `_kids`, `_qcones` and `_glue_adapters`, and a Python
    `_struct` can't keep writing `_kids` after that. They touch `_constructing` (5c10) and `_cones` (5c10) through Python until
    then, as compile_loop.rs already does with `_constructing`. **This placement is my reading: flag it to the architect.**
  - `neighbourhood`: it reads and fills `_NEIGH`, which is adopted into the memo registry (state.memos PROCESS, 5c9) and read
    by term_live's `_Mark`. By the ruling's condition that sends it to 5c9. It also has no engine-path caller, only a test
    (sa-port-147 INVENTORY-state.md part 1a).
- Container decisions: sa-port-147's ~/sa-rust-ids-work/sa-port-147/INVENTORY-state.md part 1a. 5c7 removes no container's
  last non-test reader. `_kids`, `_qcones` and `_glue_adapters` go at 5c9; `_cones` and `_constructing` at 5c10; `_NEIGH` at
  5c9 (registry). `last_budget_limited` gets a read-only view when it moves (not 5c7), and `stats` stays Python's.
  These are the TSV's new `state:` rows.

## FILE:LINE MAP
- rust-spike/slice/solver_rs/src/budget.rs: `union` :48, `within_budget` :102, pyfunctions `bud_union` :185,
  `bud_within_budget` :195, `bud_over_budget` :206, `bud_note_budget` :226. Callbacks by name: `_query_cone`, `_cone_info`,
  `_struct`, plus the engine globals `atoms_of`, `under_of`, `zero_twin` and `_kid`. A budget that isn't an exact int falls
  back to Python's saved method (`bud:py_fallback`).
- Counters: session.rs :192-200 (`bud:union` .. `bud:py_fallback`, indices 140-148; NAMES and COUNTS are now 149).
- Plants: relations_core.rs :156-159, names in the plant match after `glue-of-plain`: `union-skip-overlap` (counts the
  whole weight of an overlapping cone), `within-no-link` (link False), `over-budget-no-flag`, `note-budget-keep-flag`.
- Wiring: session_live.py `PY_BUDGET` :721, `_bud` :728 (a pyfunction doesn't bind as a method, so it's wrapped), and
  `_install_budget` :736. install() :863. `SLICE_BUDGET=py` puts Python's methods back.
- engine.py on 44f4762: `_union` :1759, `_within_budget` :1783, `_over_budget` :1829, `_note_budget` :2246. Python callers:
  `ask` :2194/:2201 and `_is_custom`/`is_`/`is_many`/`verdict` (:1944, :2005, :2054, :2157, :2204) for within/over, and
  `_query_cone` :1752 for `_union`.

## Checked so far (orion)
- Build OK. The 7 budget-related test files under `-p rust_plugin`: 226 passed, 3 failed, the same 3 as with SLICE_BUDGET=py
  (the provenance/`_cowner` base failures).
- Dev on Rust (~/sa-rust-ids-work/sa-port-148/smoke1/): answers_sha 31cd0945c07f02a6, the same as base. Counts per dev pass:
  within_budget 840, note_budget 776, union 615 (all from Python `_query_cone`), over_budget 0, py_fallback 0,
  cb_query_cone 3232, cb_cone_info 881, cb_struct 153, cb_global 836.
- The fuzz and zero smoke runs (same directory; done.txt marks the end) hadn't finished when I handed off. Read them first.

## Still to do
1. Read the smoke1 fuzz and zero counts. `over_budget` is `~u` (0 on dev), and so is probably `_union`'s overflow branch. A
   budget workload is owed (REACHED-CODE ruling). I tried queries with 100-220 positive symbols under the default budget 400
   (calib.py in my scratchpad), but the first query hadn't answered after 2 minutes. Build it with fewer, cheaper objects,
   for example a wide sum of more than 400 terms with no assumptions (C-WIDEADD, `_struct` returns budget+1), and two
   overlapping sums inside one proposition with no per-symbol facts. Add it to live.py's `load()` the way `zero` was added.
2. Plants: dev, fuzz and the new workload. `over-budget-no-flag` and `note-budget-keep-flag` change only
   `last_budget_limited` and `stats`, which live.py doesn't record, so they will likely be void on live workloads. Run them on
   the suite (test_budget_cone.py reads both) and name them void, as 5c6 did for glue-of-plain.
3. The bar: `PUSH=1 sh rust-spike/slice/p1/bar.sh land TESTED_SHA`, base ~/sp19/sa-rust-ids-work/sa-port-141/bar-5c7t2/suite on
   pareto1, PLANTS="union-skip-overlap within-no-link over-budget-no-flag note-budget-keep-flag", WLS="zero <budget wl>",
   SUITE_PLANTS=zero. Launch as port-5c6.md describes.
4. results/port-5c7.md in port-5c6.md's form; the port-ownership.md line; `agent report`. Mind the landing order: sa-port-140,
   then sa-port-145.
