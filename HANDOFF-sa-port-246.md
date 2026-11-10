# HANDOFF sa-port-246: formula step (issue 323), fifth part

Branch `port/formula`, head = this commit, on rust-slice 0192b35. **Unbarred, unlanded.** Handed off at the context
budget, **between gate items**: item 1 of the gate (the `_CACHE` fix) is committed (c170496) and its long checks are
running detached; items 2 to 5 are not started (item 2 is scoped below).

## Done (details: rust-spike/slice/results/port-formula.md, last section)
- Gate item 1, c170496: Rust's atom templates read and fill `_common._CACHE` under Python's keys (common.rs
  `atom_pattern`); twin and transfer:7:60 MATCH with `_SPLIT` and `_CACHE` counts equal and no known rows (scratch tree
  with e82147a); dev and cls too.
- A second cause found and fixed in the same commit: `memos.PROCESS.clear()` left Rust's memo of compiled nodes
  (`Dispatch.memo`), so after a clear `_CACHE` stayed short of Python's keys (dispatch.rs `clear_memos`).
- The key determines the value: cache_det.py (every hit rebuilt and compared), plants 664 and 665 caught by
  test_cache_fix.py (7 passed).

## Running detached: read it first
`~/sa-rust-ids-work/sa-port-246/j1`, started ~17:25Z by `job1.sh`, end marker **`j1/end.txt`**. It runs in the scratch
worktree `~/sa-rust-ids-work/sa-port-246/dg` (c170496 + e82147a cherry-picked, not committed + cache-values.diff + empty
known_moved.json + the clone's .so, sha256 1eef4018df4c), so the clone is free.
1. `j1/dg/verdicts.txt`: digest Python against Rust on 20 workloads, `--check entry`. Expected MATCH on all with no known
   rows. **scope DIFFERs on state part 3's branch from their own commits; here it should MATCH.**
2. `j1/det/NAME-py.json`, `NAME-rust.json`: cache_det totals (`hits`, `mismatch` by key family). Expected: no mismatch.
   A hit count of 0 for a family proves nothing for it. `j1/det/verdicts.txt`: answers Python against Rust.
3. `j1/pc/NAME-before.json` (q1tree, 17241af) and `-after.json`: pycalls for knowledge_live.py on dev, fuzz,
   transfer:7:60, value, wiring, core, Rust. The ruling: the fix must not add per-query Python. Expected: `rust_compiled`
   equal, `_wrap` and `_derived_facts` 0 after (they are called only by the probe and the shadow now).
4. `j1/suite-python`, `j1/suite-rust` (`exit.txt`, `rows.*.jsonl`, `cache_det.PID.json` per worker): the suite plus
   test_cache_fix.py and test_cbm_noid.py with `-p cache_det`. Compare failed ids with
   `~/sa-rust-ids-work/sa-port-244/q1/suite-rust` (127 failed there, the base bar's count). The probe rebuilds on every
   hit, so these two runs are not the bar's suite numbers.
If any of these is not as expected, item 1 is not done: fix it before item 2.

## Not done
- Item 1's digest part: after the rebase onto state part 3 (e82147a), apply `~/sa-rust-ids-work/sa-port-246/cache-values.diff`,
  regenerate known_moved.json (known_moved.py, clean runs), switch `_SPLIT` to exact, update test_split_order.py's
  expected Rust counts (plant 451).
- Gate items 2 to 5, and 4 (a)-(c) (the `ad:cbm_noid == 0` on cls bar line; relations.py:1116; plant 663's class).
- Gate 1 (a) of the earlier gate (`twin_row` / plant 409 / `rk:twin`, three known-failing tests) after state part 3.
- The bar.

## Item 2 (the entry converts once), as far as it was read: nothing edited
- The converters to remove: `formula::atoms_nosession` (formula.rs:503) at scope_core.rs:259 (the formulas
  `extensions.facts_for(a)` returns, new objects per call), :291 (`scope_theory_scope`'s two formulas), budget.rs:61
  (`add_kids_of`), :373 (`query_cone`), :465-466 (`within_budget`).
- `theory_scope` is reached by its Python name with Formula objects from entry.rs:703 (:727, :792), context.rs:175,
  session_glue.rs:124 and relevance.rs:741, and `query_cone` from budget.rs:438, :451, :458, :490, :497. So nodes as
  arguments means those callers hold nodes: `FNode` is a pyclass (`FormulaNode`, formula.rs:331), so one can pass through
  a call made by name.
- The session's cache is `SessionCore::fnode` (session.rs:1045), by object identity; context.rs:175 runs before the
  session exists. The entry would convert (formula.rs `convert_or` :451) and hand the node to both.
- `_qcones` is keyed `(f, link)` on the Formula object (budget.rs:367), an engine memo across queries: a hit needs no
  atoms, a miss needs the node.
- The extensions' facts (scope_core.rs:259) have no node anywhere: whether the session later converts the same objects
  was not read. If it does not hold them, that is "an entry point with no formula in hand": a question for the architect.

## File:line map (at this head)
- common.rs: `PLANTS` :23 (664 at :38), `unit_pattern` :158, `const_key_raw` :174, `units` about :430, `const_key` about
  :620, `atom_pattern` :636. py.rs: `PyTermTable::table` :108. dispatch.rs: `sync_epoch` :173, `clear_memos` :316.
- knowledge_live.py: `PLANTS` :68, `_wrap` :79, `_copy` :114, `RECHECK` :124, `_fresh` :127, `_derived_facts` about :135,
  `install_dispatch` about :236 (`_WithRusts` :246), `rust_compiled` :288 (`atom_pattern` call :310).
  knowledge_common_live.py: plant 664 :55. live.py: `CACHE_DET` :389.
- cache_det.py (probe; `install()` after the backend). test_cache_fix.py: tests :80, :88, :109, :126, :139 (plant 664),
  :163, :171 (plant 665).
- Everything else: HANDOFF-sa-port-244.md's map is unchanged (formula.rs, rows_tpl.rs, adapters.rs, wiring.py,
  test_cbm_noid.py, relkeys.rs, session.rs); knowledge_live.py lines after :114 moved down by about 30.

## Watch
- Worktrees of this clone: `~/sa-rust-ids-work/sa-port-246/dg` (in use by the job), and sa-port-244's `base` and
  `q1tree` (`q1tree` is the job's "before" tree). `git worktree remove` them when the job has ended.
- cache_det runs are not for a digest or for timing (each hit builds twice, and the put-back moves the key to the end).
- Plants 664, 665 are used; 666-669 and 607-629 are free. No numbered counter was taken (`common:atom:hit`,
  `common:atom:miss`, `registry:memos-clear` are string keys in `Common`'s and `Dispatch`'s counts); 673-679 and 645-659
  are free.
- A wiring.py edit needs `gen_offline_data.py` rerun. test_formula_nodes.py runs plain, not under run_suite.sh's plugin.
