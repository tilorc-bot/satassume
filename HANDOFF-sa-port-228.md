# HANDOFF sa-port-228 (state step part 2, rest of (iii)(b) and (iii)(c)): NOT LANDED. Bar on 1a6d38a not clean (a real bug, fixed); new bar running on 0576370. Issue 323

## What happened
- **The bar on 1a6d38a is NOT clean** (pareto1 ~/sp19/sa-rust-ids-work/sa-port-225/bar-iii-b/sum.txt; copy on orion
  ~/sa-rust-ids-work/sa-port-228/bar/sum.txt). Suite 5,989 passed / 129 failed, against base new 0, gone 0, **changed 3**:
  - tests/test_history.py::test_module_state_inventory_is_classified failed -> passed (c822173's fix, expected);
  - **tests/test_scope.py::test_answers_agree_with_the_lazy_order passed -> failed**;
  - **tests/test_scope.py::test_zero_twins_are_in_the_scope passed -> failed**.
  Both answer None where True is expected (`ask(Q.positive(f(x)), Q.eq(x, 0) & Q.positive(f(0)))`), in all five suite runs of
  that bar. Dev, fuzz and the five extra workloads all MATCH; handler multiset same as base (39 rows). So this is a lost
  answer the workloads don't see.
- **Cause (found, with a control):** RelKeys kept the query table's **address** (`l.table.as_ptr() as usize`, relkeys.rs) to
  notice a session outliving its query. A dead table's address is reused by the next table, so the session read its old term
  ids as the new table's: a wrong member of the moved sets and dicts. The tests pass alone and paired with any one file; they
  fail only in the suite's order (replayed serially on pareto1: ~/sp19/sa-rust-ids-work/sa-port-228/replay2, 1 failed).
  Control on the tested 1a6d38a build (pareto1, scripts/rk_alias.py): new table at the dead one's address, both symbols id 4,
  `b in rel._xcand` True and `a in rel._xcand` False. On the fixed build: False, True, rk:outlive +1, rk:migrate +1.
- **Fix, 0576370** (on port/state-relations-iii, rebased on rust-slice 59e9d15, pushed):
  - solver_rs/src/term/py.rs (**shared file, name it**): `PyTermTable` has a 4th field, a process-wide serial
    (`TABLE_SERIAL`, `serial()`); set in `new` (~:296).
  - solver_rs/src/relkeys.rs ~:99: `let t = l.table.try_borrow()?.serial();` session.rs ~:671: `RelKeys.table: Option<u64>`.
  - test_rs_core.py::test_a_later_table_at_a_dead_tables_address_is_a_second_table (the child's `alias` section): forces
    the address reuse and asserts it was reached (`same_address`), so the test can't pass vacuously.
  - orion check (~/sa-rust-ids-work/sa-port-228/t-rs): test_rs_core, test_rd_core, test_rl_core, test_relations_core,
    test_relc_core, test_term_ids: 301 passed. tests/test_scope.py alone: 12 passed on both backends.
  - Other address-keyed memos I read and left alone, because each holds a strong ref beside the key (landed code, not this
    step's): relations_core.rs:2673 `SPEC_ROWS`, adapters.rs:139 the lra slot memo, procmemo.rs:203/:232 `_SPLIT`.
- **Rebase:** rust-slice moved c822173 -> 59e9d15 at 08:52Z (sa-port-224, the 6i(b)+6i(c) stack). The incoming diff changes
  executed source (term/dispatch.rs, fn_tpl.rs, rows_tpl.rs, tcore.rs, tf6.rs, common.rs, wiring.py, knowledge_live.py,
  knowledge_common_live.py, offline_data.json), so a full bar was owed anyway. Rebase had no conflicts. Branch commits on
  59e9d15: 181c161, ad5745f, e1432ec, 6ec957e (was 1a6d38a), 4bf3d9c (handoff 225), 0576370 (fix), then this handoff.

## Running (detached; read the end markers)
- **Bar on tested 0576370:** pareto1 `~/sp19/sa-rust-ids-work/sa-port-228/bar-iii-b2/end.txt` (sum.txt). Started 09:07Z,
  about 2 h (the last one took 2 h 05). Config `~/sp19/sa-rust-ids-work/sa-port-228/run-bar-iii-b2.sh`: same 45 plants,
  WLS loop zero cert scope budget, SUITE_PLANTS zero; **BASE = sa-port-219's stack bar suite**
  (~/sp19/sa-rust-ids-work/sa-port-219/bar-6ic-stack/suite, tested 6f9c44a = 59e9d15's source: 5,992 passed / 126 failed);
  TESTS = 219's list plus test_rs_core, test_rd_core, test_rl_core. Tree ~/sp19/dev/sa-port-228-iii. Launcher on orion: pid
  in ~/sa-rust-ids-work/sa-port-228/bar-launch.pid, log bar-launch.log. build phase ended 09:07:50Z exit 0.
  **First thing to read:** suite's "against base" line. Expected: new 0, gone 0, changed 0 (the two test_scope ids pass).
- **(iii)(c) probe on 0576370** (the landing source if the bar is clean): orion ~/sa-rust-ids-work/sa-port-228/pyc/all2
  (done-*.txt when finished; `python3 pyc/summ.py` as in sa-port-225's pyc, check its arguments by head). It reads the
  clone's build, so **don't rebuild the clone before all2 has its done file**. The 1a6d38a table (all1, sa-port-225) was
  converted 0 on all seven.
- **Group-D:** both runs ended "END exit 0" (orion ~/sa-rust-ids-work/sa-port-225/gd/run-{c822173,1a6d38a}.log).
  Post-processing NOT run. They compare c822173 with 1a6d38a, which is this step alone (the fix changes one comparison);
  the landing SHA also carries 6i(b)+(c), so say in the report that the after column is 1a6d38a, not the landed SHA.

## Not done
1. Read the new bar (sum.txt by section: suite :15, live :33, extra :88, plants :135, suite plants ~:453, kept ~:534 in
   the old one). State the five items. **If the two test_scope ids still fail, do not land**: replay with
   pareto1 ~/sp19/sa-rust-ids-work/sa-port-228/replay.sh OUT IDFILE (tree name inside it is sa-port-225-iii; change it to
   sa-port-228-iii) on pre.txt (the failing worker's 822 ids in order).
2. Land: in the clone, `bash rust-spike/slice/p1/bar.sh land 0576370` (no PUSH first; read the diff), then `PUSH=1`. Rule
   [91]: check `agent ls` and `machine ls` for another session's full bar first. If rust-slice moved again, the rebase rule.
   Right after the push: `touch ~/dev/architect/markers/state-relations-iii-landed` (sa-port-230 is queued on it) and tell
   the architect the landed SHA. **I did not touch the marker.**
3. Group-D post-processing: for each SHA `bash ~/sa-rust-ids-work/sa-port-225/gd/tools/post195.sh SHA`, then
   `python3 tools/sum202.py gd/run-SHA > gd/run-SHA/SUMMARY-rel.md`; table format at results/port-state-relations.md :237.
4. TSV and port-ownership.md (results/port-ownership.tsv glue_objects row, was :372 before the rebase, find it by rg; state
   rows for the 9 sets, 15 dicts, 4 lists, plus specs as configuration; the relations.py count line from the probe on the
   landed SHA). results/port-state-relations.md: fix the stale UNBARRED/UNLANDED header of the (iii)(a)+(b) section (was
   :329; LANDED c822173, report 5a3c218), append this step's section with every MUST-STAY item, **including the finding
   above** (first bar not clean, cause, fix, control, the new test by id).
5. agent report, push.

## For the report
- The old bar's zeros on 1a6d38a don't cover this bug: answers MATCH on all seven workloads while the suite lost two.
  Worth saying that no workload reaches "a session outliving its query whose next table reuses the address with a
  different term at the same id"; rk:outlive per workload shows which sessions outlive their query at all.
- Shared files changed by this step: satassume/relations.py :949-952 (sa-port-225), solver_rs/src/term/py.rs (the serial).
- Scope MATCH rests on the harness fix db7130a's order (scope_wl imports after install).
