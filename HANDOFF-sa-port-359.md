# HANDOFF sa-port-359 (20 Nov, ~10:40Z): item 4 (the gate) started, jobs running detached; items 5 and 6 open

Handed off at the context budget, in the middle of item 4, with nothing lost: every job is detached and writes its own
end marker. Branch port/measured-next, pushed to the clone's origin. Worktree ~/sa-rust-ids-work/sa-port-356/wt in
clone ~/dev/sa-port-5. Nothing is landed. Output: ~/sa-rust-ids-work/sa-port-359.

TESTED SHA 00535462 (source b580119 plus the ruled skipif in test_convert_walk.py; the crate is b580119's). The commit
after it adds only results/tools359 and this file. .so of 00535462: aarch64 (orion, worktree, untracked)
4d8921d9c510e99f; x86-64 venv build 0f78ac2962f34b3a (suite, gate, bar: orion sa-port-359/so/sa_solver-00535462.so);
x86-64 bench build 8b8041d3fe6223c2 (S1). Base de88d9b9 (crate equal to b7302f83's): venv 37b7560e245df518, bench
0b6f073f5c5a600b.

## Done by 359
1. The ruled skipif (00535462): `[700-too-deep]` skips only when `exception_handled_tool()` is true (some sys.monitoring
   tool id has EXCEPTION_HANDLED in get_events, or in the local events of Python's `formula` code); the reason names
   OWED [157] and tools358/repro.py; read at the test's setup. Plain pytest: 5 passed; under run_suite.sh: SKIPPED.
   passes.sh lost its deselect and timeout. measured-next.md: the hang is not specific to 3.12.14.
   The row the ruling asks for: pareto0 job-00535462/gate/kept.log, plain pytest on the x86-64 build, 34 passed,
   `test_a_deep_formula_is_pythons[700-too-deep] PASSED`. The bar's tests phase must show it again (item 6).
2. The x86-64 builds and the staging (tools359/stage359.sh; pareto1 and pareto0 trees are git archives of the SHAs).
3. The per-query gate, READ (tools359/gate-perquery.txt, from gate359.sh step 2 on pareto0, x86-64 0f78ac2962f34b3a):
   the 20 workloads and fuzz seeds 0/1/2/42, SLICE_TERM_FRAMES=rust SLICE_WITNESS=1, Python's walker (SLICE_CONVERT=py)
   against SLICE_CONVERT=rust: 24 of 24 EQUAL; 42,753 queries, 41,354 conversions (30 kept), 78,743 reads, 0 raised;
   0 rows differ in answer, Engine.stats, last_budget_limited, kept/converted, counts (keys, order, numbers), raised,
   number of terms. The nat arm (plus SLICE_WITNESS_RUST=1) has rust's answers digest on all 24.
   Counters over the rust pass: 740 cv:entry 41,354 (= conversions), 741 cv:formula 67,269, 742 cv:read 78,743,
   743 depth 0, 744 name 0, 746 patched 0 on every workload; 745 own_base 12, all on lra. Each fires in a kept test on
   this build (kept.log, 34 passed). The Python walker's pass shows every counter 0.
   Moved ids per query are NOT read yet: they are livecmp's rows (step 3 of gate359.sh, running).
4. Ruling (1), Walk's weak references: 0 weak references found on any walker at any query's end, all 72 passes
   (`wr0`). Outside tests and instruments no source takes a weakref to a Walk (rg weakref: backend.py:80, boundary.py:95,
   rust_plugin.py:63, live.py:119, moved_digest.py:180, session_live.py:129 are on solvers, sessions, engines).
   A BASE ROW to report, not this step's: the last query's `_Query`, TermTable and walker stay referenced after the
   query until the next conversion (alive after the pass and gc.collect(): 1, never more), under Python's walker and on
   de88d9b9 alike (tools359/holder359.py on both trees; gc shows no referrer, so the holder is not a Python container).
   Earlier walkers die with their query. Not diagnosed further; say so.
5. lazy_reads.py under plant 773, checked (output sa-port-359/lazy, tools359/lazyrun359.py, dev first 150):
   as a script lazy_reads.py NEVER turns Rust's walker on (it does not call convert.from_env()): with SLICE_CONVERT=py,
   =rust and =rust plus the plant its rows are byte-equal, convert.WALK[0] is None, every counter 0. So the brief's
   "under lazy_reads.py the read item is off for every query (746)" holds only when something turns the walker on.
   With convert.from_env() called first (FROM_ENV=1): rows byte-equal to Python's, cv:patched 150 of 150, cv:read 0;
   under plant 773: cv:patched 0, cv:read 28, and 14 of 150 rows differ (the instrument's 28 lazy reads vanish).
   So 773 is caught by the instrument's rows only with the walker forced on; its bar catch stays the kept test.

## Running, detached (read the end markers; nothing needs this session)
- pareto0, shared lease, `tools359/go359.sh 00535462 de88d9b9` (orion setsid; job359.sh there): gate359.sh step 3
  (p1/convert_diff.sh into job-00535462/convdiff, then livecmp per workload into gate/livecmp-WL.txt and gate/end.txt),
  suite359.sh (cells rust, py, nat, off, base), iv359.sh (128 runs). About 90 minutes from 10:34Z.
  End marker: ~/sa-rust-ids-work/sa-port-359/go-end.txt; then job-00535462/byid.txt (byid359.py) is the summary.
- pareto1, quiet lease, `tools359/gos1359.sh 00535462 de88d9b9`: S1, 10 arms (base and head: py-off, py-on32,
  rust-off, rust-on32, rust-nat), 12 rounds, dev fuzz then budget wiring. End marker: sa-port-359/gos1-end.txt; then
  s1/med.txt (med359.py): section A is the landing rule (head rust against base rust, nat first), P the Python rows.
- orion: sa-port-359/orion359.sh: passes.sh (done: k-py 10 failed 5 errors 7 skipped, k-rust the same, k-base 18
  failed 5 errors; compare by id with tools358/readrows.sh's method, O=sa-port-359) and then R5,
  tools352/disc352.sh into sa-port-359/disc (read with tools352/disctab352.py). End marker: sa-port-359/orion-end.txt.

## Not done
- Item 4, to read: gate/end.txt (differential total, livecmp MATCH per workload: the moved ids), byid.txt (suite by id
  rust against py: 0 expected; nat against rust; rust against base; off against base; cv counters per cell; iv MOVED
  lines), the 15 known plugin-mode ids by id and the 8 test_lazy_reads ids base's Rust walker fails (named in
  measured-next.md (3)'s table; the cause still has to be written from sa-port-358/k-base/pytest.log, not guessed),
  R5 (disc), the quiet-handler counter shown to fire (live.py SLICE_PLANT_HANDLER, live.py:434-447) before any zero.
  Quiet catches (engine.py's `except Exception`): count them from the livecmp rows (`caught`) and the suite rows.
- Item 5: read s1/med.txt against the rule (faster beyond the spread on at least two of four, no worse on any, Python
  rows within the spread). If the rule is not met: Status: question.
- Item 6: the bar (copy results/tools354/job354bar.sh and gobar354.sh; rows from tools358/rows358.sh; the bar tests
  origin/bar/NAME-SHA's head, so push that branch at the tested SHA; the staged venv .so is sa-port-359/so), bar.sh
  land, guard, PUSH=1, rule [91]; the probe count against 21 of 32.
- measured-next.md (4), (5), (6); then the NEXT brief again.
- `git worktree remove` ~/sa-rust-ids-work/sa-port-357/base when no step needs it (holder359.py used it).

## File:line map
- rust-spike/slice/test_convert_walk.py: exception_handled_tool :263, TOO_DEEP :283, test_a_deep_formula_is_pythons :290.
- rust-spike/slice/results/tools359: stage359.sh, go359.sh -> job359.sh -> gate359.sh, suite359.sh, iv359.sh;
  diff359.py (per query rows; `life`), cmp359.py, tab359.py, gate-perquery.txt; byid359.py; cv_seen.py (plugin);
  gos1359.sh -> onlease359.sh -> time359.sh, wn359.py; med359.py; lazyrun359.py; holder359.py.
- The bar: p1/bar.sh penv :102, tests phase :168-:178, convdiff :228-:236; p1/convert_diff.sh; live.py's handler
  plant :434-447, its per-query record :504-:518; livecmp.py's moved rows :56-:95.
- term_live.py: _note_query :298, _convert :306, the ask wrapper :1088-:1112. convert.py: from_env :470, formula :523,
  _ORIGINAL :606. walk.rs: counters :48-:85, Walk :314.
- Everything else: HANDOFF-sa-port-358.md "File:line map", then 357's and 356's. Plants from 774, counters from 747.
