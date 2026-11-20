# HANDOFF sa-port-351: item 2 (the port) done and pushed; items 3-7 NOT STARTED; nothing landed

Stopped between items at the context budget. Branch port/witness-native (pushed), worktree
~/sa-rust-ids-work/sa-port-350/wt in clone ~/dev/sa-port-19, on rust-slice 6ee354f9. Source commit 338e6a30. Nothing
of mine runs; no lease is held. Read HANDOFF-sa-port-350.md for the profile and the earlier map.

## Done (item 2, commit 338e6a30; orion .so 14344b953afd8a33, not a bench build)

- solver_rs/src/witness.rs: compile, pools, search and exact evaluation on the query's term ids. term/rat.rs: sub, div,
  pow, bits, sign. No new crate. satassume/witness.py: only the hook `NATIVE` (None by default). witness_live.py: the
  hook, with the three guards in Python at witness.py's places. term_live.from_env reads SLICE_WITNESS_RUST.
- Choice B as ruled: the P formula is read once, one `ids` lookup per atom side. Found on the way: a Python `int` or
  `bool` side is `==` to an Integer's key (`{Integer(3): 1}.get(3)` is 1), and witness.py leaves such a side
  undecided, so the found row's object is compared by type (`q.objects[id]`), else the query goes to Python
  (`wn:fallback:type`; plant 763 removes the comparison).
- tools351/diff351.py arm `diff` (every call twice: native, then the reference): 0 differences in result, the two
  points, points tried, size, pi and work charged, on dev 776 calls / 173 certified, fuzz 424242 2772 / 1284, wiring
  4814 / 215, budget 19 / 0. Arms `native` against `python` (cmp351.py): per query the answer, Engine.stats and
  last_budget_limited are equal on the same four. Output: ~/sa-rust-ids-work/sa-port-351/ (diff-*.json, q-*.jsonl).
- Fallbacks to Python: fuzz 75 of 2772 calls (2.7%), all `wn:fallback:miss` (a side not in ids); dev, wiring and
  budget 0. Each fallback counter is shown to fire by test_what_is_not_mirrored_goes_to_python_and_is_counted.
- Plants 760 wn-integer-half, 761 wn-work-one, 762 wn-skip-patched (in witness_live.py), 763 wn-int-side: each fails
  exactly its test in test_witness_native.py (9 tests, pass under both walkers), which reads no plant flag. 764-767
  unused. Counters 706-712 in witness.rs, 713 `wn:fallback:off` in witness_live.py.
- tests/test_witness.py: 157 passed with the hook in place (the Python path is unchanged).

## Not done, in the ruling's order

3. Same behaviour on the rest: the 20 workloads (diff351.py takes an evalbench workload name), fuzz seeds 0/1/2/42
   (`fuzz0` etc.), iv, the suite by id with the switch on, R5 (a discarded run: the second run is `_Refused`, so
   table None and `wn:fallback:off`; no native store exists to reset, but show it with term_discard.py).
4. Plant rows in the bar: bar.sh has the row names (`wnative:on`, `wnative:NAME`) in penv/pref/woff/pywit, but no
   row is in PLANTS and none was run. 762's fired count is witness_live.FIRED, not on `rel:plant_fired`: route it
   (plant_count.py :44 is the place for witness.FIRED). The three in witness.rs tick `rel:plant_fired`.
5. S1, 12 rounds, quiet lease on pareto1 (tools347/time347.sh and onlease347.sh as the model; add an arm with
   SLICE_WITNESS_RUST=1; build the x86-64 .so in the bench image). Orion, loaded, one pass, NOT S1: native against
   the Python check 1.23 s / 1.33 s dev, 8.54 / 9.34 fuzz, 6.00 / 6.26 wiring.
6. Count rule: witness.py calls per query with the native check on (expected: independent, witnesses, _patched, and
   _users_knowledge on a certified one), the lookups as boundary reads (`wn:lookup`: dev 3032, fuzz 19501, wiring
   34626), the probe count against 21/32.
7. Bar, bar.sh land, guard, PUSH=1; rule [91].

## Open points for the report

- The switch tie to SLICE_CONVERT=rust is not needed by the code (test_witness_native.py passes under the Python
  walker); from_env enforces it as ruled.
- A certified query now makes one table read per symbol (`symbol_facts`, memoized, shared with the engine's symbol
  template in a fall-through query) where witness.py read `assumptions0` itself: SLICE_TERM_COUNTS read counts can
  differ from the Python-check run. Engine.stats does not.
- `witnesses` gives the table's symbol objects (`q.objects[id]`), `==` to the formula's; diff351 checks `==` and type.
- `_roots` visits a probe's symbols in index order, Python in its set's order: argued equal in witness.rs `roots`
  (per-symbol lists, equal charges within a probe) and confirmed by the work comparison; say it in the report.
- The enclosure's powers are a `OnceLock` static in witness.rs: constants, not query state.

## FILE:LINE MAP (338e6a30)

- solver_rs/src/witness.rs: NAMES :45, PLANTS :63, `power` :167, `pi_sign` :215, DEFS :264, `pred` :292, `basis_q`
  :332, `eval` :401, `holds_f` :446, `Cx::term` :527, `side` :588, `formula` :608, `WitnessQuery` :687, `spend` :711,
  `roots` :720, `pools` :758, `holds` :809, `run` :824, `compositions` :870, `search` :923, `compile_once` :935,
  `witness_compile` :964.
- witness_live.py: `native` :44, `counts` :71, `install` :78, `plant` :82, `from_env` :88. term_live.py :1276.
- satassume/witness.py: NATIVE :128, the hook's call :836. p1/bar.sh: penv :102, pref :105, woff :107, pywit :111.
- test_witness_native.py: `both` :37, tests :75-:218. results/tools351: diff351.py, cmp351.py, run351.sh (orion).
- Earlier map (witness.py, sympy_api.py, term table): HANDOFF-sa-port-350.md; witness.py lines after :124 moved by +12.

## Must stay in every report

Tested SHA 338e6a30 on rust-slice 6ee354f9, orion .so 14344b953afd8a33 (no bench build yet; the profile's bench .so
was 0982a28074215658). SLICE_WITNESS off by default, Python witness.py the default and the reference, the unchanged
path the default. No SymPy construction or evaluation at query time; no floats in any decision; "exact" rests on
325's 14-predicate table plus 2030cdc6's Q[pi] arguments (issue 247). Measured so far: per query on dev, fuzz 424242,
wiring and budget, certified set, witness_certified and Engine.stats equal Python's. Owed: the 20 workloads, bar row
wall times, known base rows by id with the planted-history test footnoted ([137e], id()-reuse), S1 from quiet-lease
runs only, on against off with the native check, witness.py's per-query Python calls, the probe count against 21/32;
the profile's numbers (results/witness-native.md (1)) are the "before".
