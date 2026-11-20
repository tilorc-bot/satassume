# HANDOFF sa-port-352: item 3 PARTLY done (stopped at the context budget, mid-item); items 4-7 NOT STARTED; nothing landed

Branch port/witness-native (pushed), worktree ~/sa-rust-ids-work/sa-port-350/wt in clone ~/dev/sa-port-19, on rust-slice
6ee354f9. Source commit 6746bfe3 (witness.rs trimmed); f56f65d4 adds fresh.py's switch and tools352. No lease is held
by a shell of mine. ONE detached job may still run: go352b.sh on pareto0 (shared lease d7d0b3df, iv's 128 runs);
its end marker is orion ~/sa-rust-ids-work/sa-port-352/go-end.txt, and its suite rows are VOID for landing (see 1 below).
Read HANDOFF-sa-port-351.md for the port's map, HANDOFF-sa-port-350.md for the profile.

## Done in item 3 (all on 6746bfe3; orion .so e0365239348de148, pareto venv .so 37b7560e245df518, bench .so 0b6f073f5c5a600b)

- The ruling's pass over witness.rs: 1063 to 1036 lines, no restructuring (the commit message lists what went and
  what stayed and why). test_witness_native.py 9 passed under both walkers; plants 760-763 each fail it (760 fails two
  tests); tests/test_witness.py 157 passed.
- Per query, the 20 workloads and fuzz seeds 0/1/2/42 (tools352/job352a.sh; output ~/sa-rust-ids-work/sa-port-352/a,
  table a/tab.txt by tab352.py): arm diff (every call natively, then by witness.py) 0 mismatches in 23,156 calls;
  arms native against python (cmp352.py): answer, Engine.stats, last_budget_limited and every `witnesses` result
  (the certified set with its points) equal on all 24, 0 queries differ; the three arms' answer digests equal.
- Fallbacks to Python per workload: fuzz 75/2772 (2.7%, miss), seeds 2.0-2.3% (miss); lra 334/1115 (30.0%), all
  `wn:fallback:off` and all `_Refused` (the second run of a discarded query: R5's case, checked with
  ~/sa-rust-ids-work/sa-port-352/why_off.py); cls 15/21 (71.4%), all `wn:fallback:type` (cls_wl's equal-but-distinct
  class objects: the found row's object has another type; NOT yet looked at beyond the counter: say why in the
  report); every other workload 0, dev and wiring among them.
- R5 with term_discard.py (tools352/disc352.sh, disctab352.py; output sa-port-352/disc/tab.txt): fresh.py --term terms
  --lra --full --discard with the native check on. dev 1985 rollbacks checked, 1985 clean; lra 1957/1957; fuzz
  3000/3000; left only the exempt _CACHE; answers and session digests equal a plain run's on all three. Discarded
  runs held native work: dev 727 compiles and 521 searches (discard minus plain counters), fuzz 1209 and 1175, lra 622
  and 11. The plant --no-rollback: 300 checked, 0 clean. Found on the way: term_discard wraps Engine.verdict, which
  witness.py's P1 guard takes for a user's method, so the check (native or Python) stood down after its compile in
  every run (first pass, sa-port-352/disc0: 409 digests differ from plain on dev). fresh.py now accepts that wrapper
  as an instrument (witness.accept) ONLY when SLICE_WITNESS_RUST=1; fresh.py is otherwise untouched. Name it (a shared
  harness file).

## Item 3, still to do

1. NEW FAILURE, item 2's, by id: tests/test_history.py::test_module_state_inventory_is_classified, "unclassified
   module-level state: [('satassume.witness', 'NATIVE', 'list')]" in every cell on 6746bfe3 (nat, wit, off). Fix:
   classify the hook in harness/state.py next to the witness switch's row (:288; the tables are at :260-265). That
   changes the tested SHA: rebuild nothing (the crate is unchanged), but restage (stage352.sh NEW 6ee354f9; it rebuilds
   on pareto1 anyway) and rerun go352b.sh NEW 6ee354f9.
2. The suite by id (suite352.sh: cells nat, wit, off on NEW, base on 6ee354f9; byid352.py reads them). This run's
   rows: nat 129 failed, wit 128, off 128 (347's on-suite at this invocation: 126 failed, so about 126 are this
   invocation's base rows, `'Solver' object has no attribute '_val'` and the like). Not read by id yet: nat has ONE
   more failed id than wit; find it (byid.txt after go-end.txt, or grep FAILED in job-6746bfe3/suite-*/pytest.log on
   pareto0 ~/sp19/sa-rust-ids-work/sa-port-352) and run a28c548's method if it is the planted-history test. The
   base cell crashed in wn_seen.py at session end (no NATIVE on 6ee354f9; fixed in f56f65d4), so base's exit line
   is void; its rows.*.jsonl are there.
3. iv (iv352.sh: 64 runs wit, 64 nat): running or done on pareto0; byid352.py prints "MOVED" per run whose failing
   ids differ and the native counters summed per switch (nat must show compiles, wit none). Rerun with the fix of 1.
4. One line in results/witness-native.md, ruled: B's lookup is `==` plus an exact type check, and why. The file
   still has only section (1): add (2) the port (HANDOFF-sa-port-351.md) and (3) this item's tables (a/tab.txt,
   disc/tab.txt, byid.txt).
5. Commit item 3's results, then items 4-7 as ruled.

## For items 4-7

- pareto1 ~/sa-rust-ids-work/sa-port-352/s1/bench-6746bfe3/tree has the bench .so (S1's build, sa-cy-build:1);
  S1's common/ is sa-port-350/s1/common. build352.sh builds both .so from a staged archive.
- Report open points (from 351, still owed): the switch tie is not needed by the code; `symbol_facts` read counts;
  `_roots` order argument; the enclosure's OnceLock and witness_live._CLASSES (the nine classes, a module constant,
  not query state); plant 762 sits in witness_live.py because the P1 guards stay Python by ruling.
- Quiet catches (engine.py:1906) were NOT counted in my runs; the bar's handler rows do it.

## FILE:LINE MAP (f56f65d4)

- solver_rs/src/witness.rs (1036 lines): NAMES :45, PLANTS :63, `power` :163, `pi_sign` :211, DEFS :260, `pred` :288,
  `basis_q` :328, `eval` :387, `holds_f` :432, `Cx::term` :513, `side` :574, `formula` :591, `WitnessQuery` :670,
  `spend` :694, `roots` :703, `pools` :741, `run` :807, `witness_compile` :947 (lines after :348 are 351's minus 14,
  after :600 minus 17: check with rg).
- witness_live.py `native` :44, `from_env` :88; term_live.py :1276; satassume/witness.py NATIVE :128, the call :836,
  GUARDED :152, `accept` :158, `_patched` :168. harness/state.py witness rows :260-265, :288.
- fresh.py: the two SLICE_WITNESS_RUST blocks (after PLANT_NO_ROLLBACK and after TD.install()), the .wn.json write.
- p1/bar.sh penv :102, pref :105, woff :107, pywit :111; plant_count.py :44 (witness.FIRED; 762's is witness_live.FIRED).
- results/tools352: diff352.py, cmp352.py, run352.sh, job352a.sh, tab352.py (per query); stage352.sh, build352.sh
  (staging, both paretos); suite352.sh, iv352.sh, job352b.sh, go352b.sh, byid352.py, wn_seen.py (suite, iv);
  disc352.sh, disctab352.py (R5).

## Must stay in every report

Tested SHA 6746bfe3 on rust-slice 6ee354f9; orion .so e0365239348de148, pareto venv .so 37b7560e245df518, bench .so
0b6f073f5c5a600b. SLICE_WITNESS off by default, Python witness.py the default and the reference, the unchanged path
the default. No SymPy construction or evaluation at query time; no floats in any decision; "exact" rests on 325's
14-predicate table plus 2030cdc6's Q[pi] arguments (issue 247). Measured: per query on dev, fuzz 424242, the 20
workloads and seeds 0/1/2/42, certified set, witness_certified and Engine.stats equal Python's. Owed: suite by id and
iv on the fixed SHA, bar row wall times, known base rows by id with the planted-history test footnoted ([137e],
id()-reuse), S1 from quiet-lease runs only, on against off with the native check, witness.py's per-query Python calls
(the guards stay Python) and the lookups as boundary reads, the fallback rate per workload and why, the probe count
against 21/32, that the switch tie is not needed by the code; the profile's numbers are the "before".
