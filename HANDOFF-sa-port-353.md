# HANDOFF sa-port-353: items 3 and 4 DONE and pushed; items 5-7 NOT STARTED; nothing landed

Stopped between items at the context budget. Branch port/witness-native (pushed, head b7302f83 plus this handoff
commit), worktree ~/sa-rust-ids-work/sa-port-350/wt in clone ~/dev/sa-port-19, on rust-slice 6ee354f9. Nothing of
mine runs; no lease is held. Read results/witness-native.md (1)-(4) for what is measured; HANDOFF-sa-port-352.md and
HANDOFF-sa-port-351.md for the port's map.

## Done

- Item 3 (source b79f6657; results ecf05f62; .so orion e0365239348de148, pareto venv 37b7560e245df518, bench
  0b6f073f5c5a600b: the crate is unchanged since 6746bfe3 and the rebuild reproduced both hashes).
  (a) `witness.NATIVE` is in harness/state.py MODULE_CONFIG, with
  tests/test_history.py::test_the_witness_checks_native_hook_is_configuration.
  (b) The extra failed id of the native cell was
  tests/test_witness.py::test_a_set_the_engine_knows_inconsistent_tries_no_point (`assert 0 > 0`): a native-path
  failure (the test wraps `witness._holds`). Fixed: witness_live.py `_replaced` sends a query to witness.py
  (`wn:fallback:off`) when one of witness.py's 23 own functions or classes (`_OWN`) is not the imported object. Plant
  764 `wn-skip-own` and test_a_replaced_function_of_witness_py_is_called. On b79f6657, pareto0: the cells nat, wit,
  off and base 6ee354f9 fail the SAME 127 ids (planted-history fails in all four, :204, no flip, so a28c548's method
  was not run); 49 quiet catches in each; iv 0 of 64 run pairs differ. Per query (20 workloads, seeds 0/1/2/42) and
  R5 rerun on b79f6657: identical to 352's tables (0 mismatches in 23,156 calls; every rollback clean).
  (c) witness-native.md (2), (3): the ruled line on B's lookup; cls 71.4% is equal-but-distinct `Function('f')`
  classes, NOT int or bool, witness.py returns None on all 15, cls gets no gain; lra 30.0% is the second run of a
  query the slice refused (456 refusals, reasons listed), which has no table.
- Item 4 (b7302f83): the fired route for 762 and 764 is plant_count.py (`wnative`, suite rows) plus the session
  report's `witness_plant_fired` (session_live.py `_write_report`, a SHARED file, 3 lines; workload rows).
  tools353/job353bar.sh has the rows (witness:on, wnative:on, the five plants) and runs the kept tests under each
  plant after the bar (kept.txt); gobar353.sh launches it. Orion trial (rows353.sh, not the bar): wnative:on MATCH on
  dev and fuzz; 760 fired 403/343, DIFFER on both; 761 fired 0/0; 762 535/2697; 763 3032/19426; 764 776/2772; 761-764
  MATCH on both and are caught by their kept tests (witness-native.md (4) says why no workload reaches each).

## To do, in the ruling's order

5. S1, 12 rounds, quiet lease on pareto1, dev, fuzz, budget, wiring. Item 4 moved Python source, so first restage the
   head you will test: `S=sa-port-353 bash rust-spike/slice/results/tools352/stage352.sh SHA 6ee354f9` (orion, setsid;
   end marker ~/sa-rust-ids-work/sa-port-353/stage-SHA.txt; it builds the venv and the bench .so on pareto1 and stages
   pareto0; expect the same two hashes). Model: tools347/time347.sh, onlease347.sh, gos1347.sh, med347.py; S1's
   common/ is pareto1 ~/sa-rust-ids-work/sa-port-350/s1/common. Arms: Rust-on at 6ee354f9 against Rust-on with
   SLICE_WITNESS_RUST=1 at SHA (the landing rule: faster beyond the spread on wiring, no worse on any), the Python
   rows (must stay within the spread), and on against off with the native check for all four.
   TRAP: with the new rule, any tool that replaces a function of witness.py (prof350.py's timed wrappers, a `_Query`
   subclass) turns the native path OFF for every query. Time and count from outside (wall time, sys.setprofile or
   sys.monitoring), or re-read `witness_live._OWN` after installing, as tools352/diff352.py does. Check `wn:compile`
   is not 0 in every native arm before reading its numbers.
6. Count rule: witness.py's Python calls per query with the native check on (expected `independent`, `witnesses`,
   `_patched`, and `_users_knowledge` on a certified one; the guards stay Python by ruling), the lookups as boundary
   reads (`wn:lookup`: dev 3032, fuzz 19501, wiring 34626), `_replaced`'s 23 dictionary reads per call as reads, the
   probe count against 21/32.
7. Bar: push the tested SHA as origin/bar/witness-native-SHA, then `gobar353.sh SHA 37b7560e245df518` (orion,
   setsid; end marker ~/sa-rust-ids-work/sa-port-353/gobar-end.txt; BASE is sa-port-348's bar on 82d4ddf3). Read
   sum.txt, kept.txt, the plant table with wall times, the quiet catches, the suite rows of 762, 763 and 764 (764's
   is expected to fail tests/test_witness.py::test_a_set_the_engine_knows_inconsistent_tries_no_point). The
   planted-history test: if a row flips, run a28c548's method. Then bar.sh land, the guard, PUSH=1; rule [91].

## Report open points (still owed)

- The switch tie to SLICE_CONVERT=rust is not needed by the code. fresh.py (shared harness file) accepts
  term_discard's wrapper when SLICE_WITNESS_RUST=1. session_live.py (shared) adds witness_live.FIRED to the report.
- The new fallback rule is a behaviour the planner has not ruled on: name it in the report (it is P1's rule applied
  to witness.py's own functions; no workload uses it; cost 23 dictionary reads per call of the check).
- `symbol_facts` read counts, `_roots` order, the enclosure's OnceLock, `_CLASSES` and `_OWN` as constants.
- Quiet catches (engine.py:1906): 49 in every suite cell, base among them; not counted on the workloads (the bar's
  handler rows do it).

## FILE:LINE MAP (b7302f83)

- rust-spike/slice/witness_live.py: `_BY_NAME` :40, `_OWN` :42, `_replaced` :54, `native` :66, `counts` :93,
  `install` :100, `plant` :104, `from_env` :110.
- solver_rs/src/witness.rs (1036 lines, unchanged): PLANTS :63, `planted` :82, `pred` :288, `side` :574 (type check
  :581), `formula` :591, `spend` :694 (plant 761 :697), `roots` :703, `pools` :741, `run` :807.
- harness/state.py :296-299 (NATIVE); tests/test_history.py :124; satassume/witness.py NATIVE :128, the call :836.
- test_witness_native.py: the work-bound test :122, test_a_replaced_function_of_witness_py_is_called :221.
- plant_count.py :49-51 (`wnative`); session_live.py `_write_report` :1567-1576; p1/bar.sh penv :102, pref :105,
  woff :107, pywit :111, fired :133, the plants command :189, land :50.
- results/tools353: job353bar.sh, gobar353.sh, rows353.sh. tools352 take S=SESSION (stage352.sh, build352.sh's
  second argument, go352b.sh); byid352.py reads a cell without counters.
- Output: ~/sa-rust-ids-work/sa-port-353 (a/tab.txt, disc/tab.txt, job-b79f6657/byid.txt, rows/rows.txt, why_type.py,
  why_refused.py, why-cls.err, why-lra.err); pareto1 ~/sa-rust-ids-work/sa-port-353/s1/bench-b79f6657/tree has the
  bench .so; pareto0 ~/sp19/sa-rust-ids-work/sa-port-353.

## Must stay in every report

Tested SHA b79f6657 for items 1-3 (b7302f83 adds item 4's Python-side route; the bar's SHA is to come) on rust-slice
6ee354f9; .so orion e0365239348de148, pareto venv 37b7560e245df518, bench 0b6f073f5c5a600b. SLICE_WITNESS off by
default, Python witness.py the default and the reference, the unchanged path the default. No SymPy construction or
evaluation at query time; no floats in any decision; "exact" rests on 325's 14-predicate table plus 2030cdc6's Q[pi]
arguments (issue 247). Measured: per query on dev, fuzz 424242, the 20 workloads and seeds 0/1/2/42, certified set,
witness_certified and Engine.stats equal Python's; suite by id (the same 127 base ids in every cell, planted-history
among them by id, [137e], id()-reuse) and iv. Fallbacks: dev, wiring, budget 0; fuzz 2.7% (miss); lra 30.0% (second
run of a refused query); cls 71.4% (equal but distinct Function classes; no gain on cls). Owed: bar row wall times, S1
from quiet-lease runs only, on against off with the native check, witness.py's per-query Python calls and the lookups
as boundary reads, the probe count against 21/32, that the switch tie is not needed by the code; the profile's numbers
(10.1% of Rust dev, 9.4% of Rust wiring, 17.8% of Rust fuzz) are the "before"; fresh.py's change named.
