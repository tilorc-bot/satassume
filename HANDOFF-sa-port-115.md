# HANDOFF sa-port-115: 5c4 tested source b8dda68, bar running on pareto1; re-pointing done; plants classified (issue 323)

Clone /home/tilo/dev/sa-port-7, branch port/5c4 (pushed). Tested source **b8dda68** (on rust-slice d14628d; rust-slice was still d14628d at 00:47Z).

## Running
The bar on pareto1, started 00:43Z: `machine run pareto1 --shared` (orion PID 604263, `~/sa-rust-ids-work/sa-port-115/bar-5c4.machine.pid`,
launcher log `~/sa-rust-ids-work/sa-port-115/bar-5c4.launch.log`). **Wait for `pareto1:~/sp19/sa-rust-ids-work/sa-port-115/bar-5c4/done.txt`**
(about 20 min; build and tests phases exited 0 by 00:45Z). Config (its `config.txt`): BASE = sa-port-109/bar-5c3/suite, PLANTS = the 7 bar plants
(drop-init-engage drop-enqueue drop-note-top drop-proc-eq-links drop-link-later wants-never drop-share), WLS=loop, SUITE_PLANTS=zero,
TESTS = 5c3's ten files, DIRECT = `relations_direct.py 300 0`. Then read `sum.txt` (bar_sum.py) and state the five items.

## Done
- 5509fba read against relations.py:777-979, 1516-1598: no difference found (attribute order, `_share`'s lazy map, short-circuits,
  `scope_misses`, the `Uninterpreted` text, patches honoured by calling methods by name).
- Re-pointing (b8dda68): test_relations_core.py `_sharing` mode, `test_sharing_is_needed_and_works` (dummy specs on True / off None via
  `skip-share` on Rust and the suite test's patches on Python; real specs `_trichotomy` off True, both off None; same on Python, Rust,
  SLICE_REL=py) and `test_sharing_case_fails_without_sharing` (sharing removed from the start: Python `_share` patch, Rust new test-only
  plant `drop-share-tri` = drop-share + trichotomy off, since one plant is on at a time; `tri_off` answers None on both).
  A 3-cycle `x<=y<=z<=x` doesn't work as a no-plant case: None everywhere with the stand-in (probes/probe.py).
- Named status: suite_report.py `PATCHED` classes test_equality_sharing_is_needed_and_works as needs-internals (a patch on a private method
  Rust's calls go past, the same kind as SUBCLASS's override), with the pointer. suite_split_named.py's NAMED is for passed-with-firing, not
  this; rust_plugin.py has no list. Python test unedited. To show it, run `suite_report.py <bar suite> <python suite rows>`
  (Python rows: pareto1 `~/sa-rust-ids-work/port-census/pr328-check/suite-python` per the standing block; check the path).
- The 7 bar plants added to `test_dropped_clause_is_seen`: each fires and moves a `run` case (fired 23/164/33/25/81/60/117).
  orion: test_relations_core.py + test_query_core.py 82 passed.

## Plant classification (by reading plus Python probes; for the report)
- **drop-prep-twins: unreached in a way that matters.** It fires on the guard (734/693/244), but the twin-allocating branch is never entered on
  dev/fuzz/loop: drop-twins-var, inside that loop, fired 0 on all three. Workload owed: a query whose glue has a zero twin (zero(n), n under
  an AppliedUndef). test_query_core.py catches it on forged state.
- **drop-twins-var: redundant, first reading.** Python probe (probes/twins.py, 6 queries with zero twins): with `var(atom)` skipped, answers are the
  same, and at `Relations.process` the twin is already allocated in all but one call: eq(t, 0) is also t's link atom (`_link`). The direct test
  catches it on state (test_query_core.py `ensure_twins:*`, `test_each_plant_fires_and_is_seen`), not on an answer. Removal candidate on
  Python, to check with a Python suite run (the one unallocated call is order-dependent).
- **drop-lo-memo: speed-only** by reading: `formula_literal` re-derives the same literal through `table.var`/`dvar`, so no state moves
  (fired 44/1,957, no change). Replacement wrong-value plant (another key's entry) owed; not written.
- **drop-lo-discover: redundant on dev.** probes/lodisc.py: 44 of 44 skips are followed in the same `literal_of` by `Relations.process`, whose
  loop starts with `discover()` (29 had work pending). Fuzz probe was running on orion, output
  `/tmp/claude-1000/-home-tilo-dev-satassume/56723487-a9d8-4141-9c07-43889348a869/scratchpad/lod-fuzz.err` (last line LODISC);
  if gone, rerun: `$PY probes/lodisc.py fuzz py OUT --check entry` from rust-spike/slice. With relations None the discover is needed (unreached).

## Next
1. Read the bar; state the five items; method reach from `rel:*` counters (dev/fuzz/loop/suite). Count engine.py:1906 catches.
2. results/port-5c4.md in port-5c3.md's form, with the MUST-STAY items; commit; `PUSH=1 sh rust-spike/slice/p1/bar.sh land b8dda68`
   (rebase rule: if rust-slice moved, full rerun only if the incoming diff changes executed code). `agent report`.
relations.py doesn't count whole after 5c4 (5c5 owns its module functions; Session 5c6, engine.py 5c10). Owed list additions: real-EUF case
for tests/test_relations.py (held Python PR candidate); drop-twins-var and drop-lo-discover as Python removal candidates; drop-lo-memo's
wrong-value plant; drop-prep-twins' workload.
