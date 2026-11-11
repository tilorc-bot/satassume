# HANDOFF sa-port-260: formula step (issue 323), seventh part

Branch `port/formula`, head = this commit, on rust-slice **9151316** (state part 3). **Unbarred, unlanded.** Handed off at the
context budget, between gate steps: gate step 1's read and rebase and gate step 2's edits are committed; steps 3 to 5 are
not started. Details and tables: rust-spike/slice/results/port-formula.md, last section.

## Done
- j2 read: 18 MATCH, scope and lra DIFFER as on base, no known row anywhere, plant 666 DIFFER. As expected.
- Rebased onto 9151316 (78962f7): no conflict, one build fix (session.rs `PyBool`), cache-values.diff applied,
  known_moved.json empty (exact `_SPLIT` and `_CACHE`).
- (iii) edits (132fa61): `twin_row`, plant 409, `rk:twin` removed; three tests on the class-table rule, each caught by plant
  661; split_order.compare exact; test_term_live's stale tests were already fixed by part 3.
- relations_core.rs's four `.table` reads off the property (b0106f7), `_table_get` before/after on 6 workloads.
- Rulings 1-2 (afca220): term_discard.py exempts `_CACHE` only; plant 667 `mark-leaves-entry` caught on dev.

## Running detached: read it first
`~/sa-rust-ids-work/sa-port-260/j1` (job1.sh, started 23:46Z 10 Nov, end marker **`j1/end.txt`**; lra takes over an hour),
in the scratch worktree `~/sa-rust-ids-work/sa-port-260/dg` at **78962f7 with that commit's .so**: it does not hold 132fa61,
b0106f7 or afca220, so it is the rebase's check, not the head's.
- `j1/dg/verdicts.txt`: expected 19 MATCH and lra DIFFER by end/stream/lra/stats only (ruling 3's known row), no `"known"`
  row in any .cmp. At 00:35Z: scope, dev, f6, wiring, port, ground, loop MATCH; the rest not written.
- `j1/p666/verdict.txt`: expected DIFFER.
- Then `python known_moved.py j1/dg/*.cmp` in the clone should leave known_moved.json empty (lra is refused: it has other
  differences).
The head's own digest is owed to the bar (the three later commits change relkeys.rs, relations_core.rs, term_live.py).

## Open, for the planner (in my report)
1. Ruling 1's condition was met on sa-port-246's cache_det run (pre-rebase tree). I did not rerun cache_det after the
   rebase; the bar should.
2. Plant 667 and the `_CACHE` exemption have no kept test (three dev runs of 100 s each are the evidence).
3. `link:second` 3 in the join test: two equal-class objects alternating on one node ask `term_id` in Python each time.
   Not changed; say if it should be.

## Not done
Gate steps 3, 4, 5 and every bar addition: see "Not run" in the results section. Ruling 3 (lra's cause, after the rebase,
no fix without the planner) and ruling 4's lra half.

## File:line map (at this head)
- relkeys.rs: `rk_key` :83 (`term_of` call :99); `twin_row` and plant 409 are gone. relations_core.rs: `term_of` :725,
  `session_of` :778 (`core_of`), `table_of` at :2269, :2331, :2467; lines after :684 moved up by 2 against part 3's map,
  after :784 by 1. session.rs: `table_of` :930, `core_of` :949 (their lines moved up by 2), `session_counts` :547, `fnode`
  :1312, `atoms_of` :1329, `to_f` :1342, `convert` :1381; counter slot 359 is `reserved:359`.
- term_live.py: `_Mark` :134 (`_CACHE` skipped :148-158), `rollback` :183 (plant 667 :189-196), plant note :290, `PLANT`
  :292, `from_env` :1088. term_discard.py: `EXEMPT` :48, the exemption :139-142.
- split_order.py `compare` :24. test_split_order.py :24. test_moved_digest.py :33, :44. test_rs_core.py :271, :286.
  test_relations_core.py `_join` :694, the test :981.
- session_live.py (after part 3): `PY_COMPILE` :25, `_core_rules` :34, `_rust_call` :1319, `_compile_formula` :1331
  (fallback :1338), `_formula_literal` :1341; the plant tuple that held 409 ends at about :1071.
- Step 3 (convert once), unchanged by this session: formula.rs `FNode` :331, `convert` :446, `convert_or` :451,
  `atoms_nosession` :503; scope_core.rs `extension_atoms` :240 (:259), `scope_theory_scope` :278 (:291); budget.rs
  `add_kids_of` :60, `query_cone` :364 (:373), `within_budget` :449 (:465-466); `theory_scope` by name at entry.rs:706,
  context.rs:171, session_glue.rs:120. HANDOFF-sa-port-246.md "Item 2" has the reasoning.
- Everything else: the brief's map at 08a2004 holds for files part 3 did not touch (formula.rs, rows_tpl.rs, adapters.rs,
  common.rs, dispatch.rs, knowledge_live.py, wiring.py, convert.py, test_cbm_noid.py, test_cache_fix.py); for session.rs,
  session_live.py, compile_loop.rs, query.rs, session_glue.rs, entry.rs, context.rs, relevance.rs find by name.

## Watch
- Helpers in `~/sa-rust-ids-work/sa-port-260/`: job1.sh (digest, 20 workloads), tg.sh TREE OUT WL... (pycalls.py on
  session_live.py), `disc/` (the three discard runs), `t1`-`t3` (test logs), build1-5.log.
- Worktrees of this clone to remove once their jobs have ended: `sa-port-260/dg` (after j1/end.txt), `sa-port-248/dg` and
  `basedg` (j2 has ended), 246's `dg`, 244's `base` and `q1tree`.
- A backup of the pre-rebase head is the local branch `port/formula-pre-rebase-08a2004` (origin had 08a2004 until this push).
- Plants 600-606 and 660-667 are used (409 retired); 607-629 and 668-669 are free. Counters: none taken; 645-659 and
  673-679 free.
- In a batch runner, `wait` with no pids also waits for a long job started beside the batch; job1.sh waits on the batch's
  own pids.
- `fresh.py WL rust OUT --term terms --lra --discard --term-out J` is the discard check; `--term-plant NAME` sets a
  term_live plant.
