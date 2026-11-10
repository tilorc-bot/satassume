# HANDOFF sa-port-236 (state step part 2, (iii)(b) rest): cause found and fixed in ba1ca22; bar on ba1ca22 RUNNING; NOT LANDED. Issue 323

Nothing landed. rust-slice is still 59e9d15. Marker `~/dev/architect/markers/state-relations-iii-landed` NOT touched.
Branch port/state-relations-iii is pushed with ba1ca22 (code) and this handoff. Read HANDOFF-sa-port-228.md for the
step's map; this file adds the cause, the fix and what is running.

## The cause (shown, with a control)
The eight lost zero-twin answers on the bar of 0576370 come from **two equal `Function("f")` classes in one query**:
- Class A is made at import (satassume/knowledge/templates/_rows.py:166). tests/test_ref.py's module constants (`_f`,
  ZERO_GLUE's propositions and sets) are A's objects, held from collection on.
- SymPy's lru cache later evicts `Function("f")`. The next `Function('f')` is a second class B, `==` to A and hashing
  alike. In the failing order harness/sympy_io.py:136 `from_srepr` makes it, in
  tests/test_history.py::test_fixed_repro_stays_fixed[Gp1-links-accumulate-per-term] (orion o2/made.json).
- tests/test_history.py::test_fixed_repro_stays_fixed[T1-transfer-congruent-application] asks T1 with B's objects.
  harness/checker.py `execute` ends with a registry restore (a new registry version); process-wide memos keep B's objects.
- test_ref's T1 then asks with A's held objects on a fresh engine. Its session meets A's `f(u)`, `f(0)` from the query
  and B's from the memos (join 4, link:second 17).
- The table gives a row only to its own class (term_live.py:292), so B's `f(0)` has no term id. RelKeys (0576370)
  interned it by hash **beside** A's term-id key. The split shows in the moved dict `_tv` (keys `f(u)`, `f(0)` twice);
  the nine sets stay equal to Python's. Python's dict held one member, so Python answers True and Rust None.
- Smallest suite order (orion ~/sa-rust-ids-work/sa-port-236/m-min.txt, 3 ids, fails on 0576370 in 0.6 s):
  tests/test_history.py::test_module_state_inventory_is_classified (its `reset_module_state` empties SymPy's cache),
  the history T1 id, then the test_ref T1 id.
- Standalone: orion ~/sa-rust-ids-work/sa-port-236/twin11.py (`py`: True then True; `rust` on 0576370: True then None;
  `rust norestore`: True). In the repo: `python test_rs_core.py twin rust` (add SLICE_SESSION_PLANT=rk-class-split to
  see the split on the fixed build). twin7 to twin10 are the attempts that did not lose it; the registry restore
  between the two asks was the missing ingredient.

## The fix, ba1ca22 (pushed; orion: 303 passed on test_rs_core, test_rd_core, test_rl_core, test_relations_core, test_relc_core, test_term_ids)
- solver_rs/src/relkeys.rs: `twin_row` (:98): when `term_of` has no id for `x`, the row of an `==` object of an equal,
  not identical, class in the query's own table (`q.ids`/`q.objects`, then `q.derived`/`q.rev`); `rk_key` (:140) takes
  its id. Counter 359 `rk:twin` (a reserved slot of the rk group, no array growth). Plant 409 `rk-class-split`
  (:85): no equal-class row, RelKeys as on 0576370.
- session.rs: RK_TWIN :495; RelKeys doc comment now says serial (the doc nit). relations_core.rs :685 the plant's name.
- **Shared file:** session_live.py :1001, `rk-class-split` added to `_REL_STATE_PLANTS` (sa-port-230 owns the file).
- None of the nine cbm_noid identity sites is touched; term_live.py:292 is unchanged (sa-port-234's).
- Per key lookup of a Basic with no own-class row, `twin_row` adds 2 to 5 Python reads (`q.ids`, `.get`, and on a
  hit `q.objects[i]`, `q.table`). Not adapter slots; name it next to the getattr guards.
- Tests: test_rs_core.py::test_two_equal_function_classes_key_as_one (answer, and the sets' and dicts' keys, equal to
  Python's; control `join > 0`) and ::test_class_split_plant_is_caught (answer None, rows differ, `_tv` has a key twice).
- **Control on 0576370** (old .so swapped in, orion control-0576370.txt): test_two_equal_function_classes_key_as_one
  fails at the answer assert (:280). Old build kept: orion ~/sa-rust-ids-work/sa-port-236/sa_solver-0576370.so.
- On the fix twin11 gives True, rk:twin 12; under the plant None, rk:twin 0, rel:plant_fired 13.

## Replays on ba1ca22 (pareto1 ~/sp19/sa-rust-ids-work/sa-port-236/, tree ~/sp19/dev/sa-port-236-iii, .so sha256 fde4414dfab0)
- r-scope (pre-scope.txt): 733 passed, 0 failed. r-ref (pre-ref.txt): 553 passed, 1 failed.
- rw-ref and rw-scope: the two failing workers' **whole** orders from the 0576370 bar (worker-3894911.txt 972 ids,
  worker-3894914.txt 1,110 ids). 44 and 15 failed; every one is a base failure except the one below.
- So all eight zero-twin ids pass in the suite's order: test_ref's four and test_zero_glue's two G5 ids are in
  worker 3894911, test_scope's two in 3894914.
- **Still failing: tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence**
  (`assert len(run_stream(ops)) == 2`, `0 == 2`, test_public_incremental.py:204). NOT yet compared with a28c548's
  signature. The planner's (b) accepts it as the known id()-reuse failure only if it matches.

## Running (detached; read the end marker)
- **Bar on tested ba1ca22:** pareto1 `~/sp19/sa-rust-ids-work/sa-port-236/bar-iii-b3/end.txt` (sum.txt). Started
  12:11Z; about 2 h 20. Config run-bar-iii-b3.sh in that directory's parent: 228's config plus plant `rk-class-split`
  (46 plants), BASE = sa-port-219's stack bar suite, SUITE_PLANTS zero. `rk-class-split` should fire 0 on dev and fuzz
  (void there, name it), so the suite runs under it too: expect zero-twin ids lost in that suite run, which is the
  plant's control on the suite. Launcher on orion: pid in ~/sa-rust-ids-work/sa-port-236/bar-launch.pid.
- The clone's build is ba1ca22 (orion). The (iii)(c) probe all2 (0576370) is read: converted 0 on all seven
  (`python3 ~/sa-rust-ids-work/sa-port-228/pyc/summ.py ~/sa-rust-ids-work/sa-port-228/pyc/all2`).

## Not done (the brief's tasks 3 to 7)
1. Read the bar: suite's "against base" line first. Expected changed 1 (the planted-history test) or 0. State the
   five items. Read rk:twin per workload (expected 0 on all seven: no workload has two equal classes).
2. Planted-history test: compare its failure with a28c548's signature (`agent journal`, report a28c548).
3. Land (`bar.sh land ba1ca22`, no PUSH, read the diff, PUSH=1; rule [91]), marker, tell the architect the SHA.
4. Group-D post-processing, both SHAs (HANDOFF-sa-port-228.md "Not done" 3). The after column is 1a6d38a.
5. Rerun the (iii)(c) probe on the landed source (pyc/run.sh NAME dev fuzz zero loop cert budget scope).
6. TSV, port-ownership.md, results/port-state-relations.md, agent report, push (HANDOFF-sa-port-228.md "Not done" 4).

## For the report: the planner's (a) to (e)
- (a) twin11.py and `test_rs_core.py twin`; the split is `_tv`'s keys under the plant.
- (b) Eight ids by this cause (replays above). The ninth is the planted-history test: signature check owed.
- (c) Test and plant as above. The nine sets' digest alone does not see the plant; the dicts' keys do.
- (d) 228's control is a built case, independent of the suite: on 1a6d38a a new table at the dead one's address gives
  `b in rel._xcand` True and `a` False; test_a_later_table_at_a_dead_tables_address_is_a_second_table still passes with
  the serial. Keep the serial. But the first bar's two test_scope failures were this cause, not address reuse: they
  failed again on 0576370 and pass on ba1ca22. No replay showed address reuse in the suite (rk:outlive 0).
- (e) ad:cbm_noid per workload from the bar. On twin11 it is 25 with two classes in one query, 29 when the second class
  comes alone, 0 with one class: it moves with class identity through SymPy's cache, not with id() or addresses.
- All seven workloads MATCHed on both earlier bars while the suite lost answers: no workload holds two equal classes.

## FILE:LINE additions (ba1ca22; rust-spike/slice/)
- solver_rs/src/relkeys.rs: RK_PLANT_SPLIT :85, twin_row :98, rk_key :123 (the match on term_of :138-141).
- solver_rs/src/session.rs: RK_TWIN :495, RelKeys :672. relations_core.rs: rel_plant's arm :685.
- session_live.py: _REL_STATE_PLANTS :984-1001. test_rs_core.py: _twin :163, _run :223, the two tests :271, :285.
- orion ~/sa-rust-ids-work/sa-port-236/: twin7.py to twin11.py, plug/cls_log.py (who makes each class, stack at each
  join), replay-orion.sh, reduce-orion.py, m-min.txt, o2/ (made.json, cls.jsonl), control-0576370.txt, t-rs.log.
- pareto1 ~/sp19/sa-rust-ids-work/sa-port-236/: replay.sh, worker-*.txt, r-ref, r-scope, rw-ref, rw-scope,
  run-bar-iii-b3.sh, bar-iii-b3/. The build-only output went to ~/sa-rust-ids-work/sa-port-236/pre-build (outside sp19).
