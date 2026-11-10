# HANDOFF sa-port-232 (state step part 2, (iii)(b) rest, land-only link): NOT LANDED. The bar on 0576370 is not clean; sa-port-228's fix did not fix the suite's lost answers. Issue 323

Nothing landed, no code changed, marker `~/dev/architect/markers/state-relations-iii-landed` NOT touched. rust-slice is still
59e9d15. Read HANDOFF-sa-port-228.md for the step's map; this file only adds what the new bar and the replays showed.

## The bar on tested 0576370 (pareto1 ~/sp19/sa-rust-ids-work/sa-port-228/bar-iii-b2/sum.txt, END exit 0 11:39Z)
- **Suite: 5,983 passed / 135 failed** (base, sa-port-219's stack bar: 5,992 / 126). Against base: new 0, gone 0,
  **changed 9**, all passed -> failed:
  - tests/test_scope.py::test_answers_agree_with_the_lazy_order
  - tests/test_scope.py::test_zero_twins_are_in_the_scope
  - tests/test_ref.py::test_zero_under_an_application_is_an_equality[T1-transfer-congruent-application], [T2-transfer-raise],
    [T4-transfer-two-zero-terms], [query-twin]
  - tests/test_zero_glue.py::test_zero_in_the_set_is_an_equality[G5-default], [G5-whole]
  - tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence (the known id()-reuse
    failure, a28c548; passed in the base run, failed in all five suite runs of this bar)
  Eight of the nine are an engine answer of None where True, False or ValueError is expected, all on zero-twin queries
  (`Q.eq(x, 0) & Q.positive(f(0))` asked about `f(x)`).
- Passed 5,983: 5,982 with no handler firing, 1 with a firing (test_ci_stream_reports_only_what_replays). Handler rows 39
  in 2 tests, multiset same as base. TermFault 0.
- **The lost set differs per run.** The four planted suite runs (suite-ad-lra-not-expr, suite-int-as-number,
  suite-rs-bounded-drop, suite-xf-rel-view-none) lost 5, 3, 2 and 2 of the eight, different ones each. So it depends on
  what each xdist worker ran before.
- tests phase 925 passed, 4 skipped. Dev and fuzz MATCH (py/py, py/rust, traced/untraced); loop, zero, cert, scope, budget
  MATCH. Plants and the rest of sum.txt: not read (sections from :135).
- So the architect's note item (1), "test_scope's two answers MATCH in suite order on the new bar", is **not met**.

## What the replays show (pareto1 ~/sp19/sa-rust-ids-work/sa-port-232/, tree ~/sp19/dev/sa-port-228-iii = the tested build)
- `replay.sh OUT IDFILE` (228's, pointed at sa-port-228-iii and this directory; `BACKEND=python` for Python).
  - r-scope (pre-scope.txt, worker 3894914's 749 ids up to the target): 1 failed (test_answers_agree_with_the_lazy_order).
  - r-ref (pre-ref.txt, worker 3894911's 566 ids): the 4 test_ref ids failed. The planted-history test passed in this replay.
  - r-scope-py: 733 passed, 0 failed. So it is Rust-only and replays serially.
- **sa-port-228's cause is not this failure's cause.** In both failing replays `rk:outlive` is 0 and `rk:migrate` is 0: no
  session met a second table. The table serial of 0576370 closes a real hazard (228's control stands), but the suite's lost
  answers have another cause. 228 did not replay the suite order on the fixed build.
- Halving (halve.py, halve-ref.log): the first 280 ids plus the T1 target still fail (h1.txt, 281 ids, 44 s); neither
  140-id half alone fails (h3, h4). 228's halving also needed both halves. Both failing workers started with
  tests/test_extended_order.py.
- Counters of the T1 test, alone (one-T1, passed) against the failing order (r-ref):
  link:second 0 -> 25, link:none 0 -> 17, join 0 -> 4, ad:cbm_noid 0 -> 25, link:hit 109 -> 86, rk:term 86 -> 75,
  rk:intern:input 1 -> 3, ses:query_all 1 -> 2.
- Join log (replay-j.sh adds `-p join_log`; j1/joins.*.jsonl): the 4 joins are `f(u)` and `f(0)`, each present as two
  objects of **two different classes named `f`** (type ids 766143280 and 762477680, same text, kwargs {}). So one process
  holds two equal `Function("f")` classes, and one query's session sees a term under both.

## Reading so far (a hypothesis, not shown)
relkeys.rs `rk_key` (~:83-135) keys the first object by its term id (`by_term`). An equal object of the other class has no
row for its class (`term_id` returns None: link:none), so it falls to the dict path and is interned by hash as a **second
key**. The dict path never looks in `by_term`, and the `by_term` branch looks in the dict only on a miss with
`basic_dict > 0`. Python's sets and dicts joined the two objects by `==`; the moved containers would hold them apart. That
fits "None for True" on a twin that the set no longer finds. Not checked: test_rs_core.py has a "class join" test from
sa-port-221; read what it covers before trusting this.

## Standalone attempts (orion ~/sa-rust-ids-work/sa-port-232/twin*.py; run in rust-spike/slice with the clone's PYTHONPATH)
None reproduces the lost answer yet. twin3 to twin6 build a second equal class with `clear_cache()` then `Function("f")`:
- `f is not g`, `f == g`, and `f(0)` then returns the cached object of class g. Answers stay True on both backends, join 0.
- twin6 (same query asked first with class f, then with class g, fresh engines): link:none 0 -> 64 and
  **ad:cbm_noid 0 -> 29**, answer still True. So a second equal class alone moves `ad:cbm_noid`. That is history
  dependence through SymPy's cache and class identity, not through `id()` or an address in this code. Worth telling the
  planner for ruling (c); it is one case, not the whole 19-to-910 variance.
The suite case has join 4 and link:second 25, which no twin script reaches: the session's node table must meet both classes.

## Next steps
1. Find which class is test_ref's `_f` and which earlier test made the other: add `id(type)` of `tests.test_ref._f` to the
   join rows, or print `Function("f")`'s id per test over h1.txt. Reduce h1.txt by removing chunks (keep a removal while it
   still fails) instead of halving, since it needs ids from both halves.
2. Turn that into a standalone script that loses the answer, then into a test in test_rs_core.py that fails on 0576370.
3. Fix in relkeys.rs (this step's file), rebuild, replay r-ref and r-scope orders clean, then a full bar
   (run-bar-iii-b2.sh as a template; BASE stays sa-port-219's stack bar suite). A new tested SHA needs the whole bar.
4. Then the brief's tasks 2 to 5, all still open: land, marker, group-D post-processing, the (iii)(c) probe
   (all2 has its done file, unread), TSV/ownership/results, report.

## Doc nit, not done
session.rs RelKeys doc comment still says "`table` is the address of the one query table" (sa-port-233's audit, 83cbcb9).
It can go into the next code commit, since a new bar is owed anyway.
