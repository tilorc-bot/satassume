# HANDOFF sa-port-106: 5c2's bar running, loop workload added; 5c3 first version on port/5c3 (issue 323)

Clone /home/tilo/dev/sa-port-7. port/5c at 326d9f8 (pushed) = 53adc14's 5c2 + 7adb61e handoff + loop workload and bar.sh `extra` phase.
port/5c3 at 3491f6b (pushed) = port/5c + 5c3's first version. rust-slice still d2d3234 at 23:13Z; sa-port-104 was running 6e's bar
(port/6e ac0f88d) on pareto1, so 6e may land first: then the rebase rule applies (6e touches knowledge_live.py, which the
default Rust path runs, so 5c2 reruns the full bar after rebasing).

## Jobs (both detached; read, don't wait in a shell)
- **5c2a rerun** (sa-port-103's, tested afcc6eb): pareto1 `~/sp19/sa-rust-ids-work/sa-port-103a/`. At 23:13Z build/tests/suite/live
  done, plants running; sum.txt and done.txt at the end. Launch log on orion `~/sa-rust-ids-work/sa-port-103/bar-a-launch.log`.
- **5c2 bar** (mine, tested 7adb61e = 53adc14's source + the handoff doc): pareto1 `~/sp19/sa-rust-ids-work/sa-port-106/`, launched
  23:06Z by orion `~/sa-rust-ids-work/sa-port-106/launch-5c2.sh` (machine run PID 542051 on orion; log `bar-5c2-launch.log`).
  BASE sa-port-99's suite rows, PLANTS the 11 `_LOOP_PLANTS`, SUITE_PLANTS=zero, TESTS as launch-a.sh, DIRECT relations_direct.py.
  So far: build ok; tests **438 passed**, direct exit 0; suite done 23:10Z; live, plants, suiteplants, sum to come.
- **Not yet run: the loop workload on pareto1.** After the 5c2 bar's done.txt exists (bar.sh checks out the tree, so not while
  it runs), run phases `extra sum` with WLS=loop, the 11 PLANTS, NAME sa-port-106 (same tree, .so already built), and
  OUT=/home/tilo/sp19/sa-rust-ids-work/sa-port-106-loop. Copy bar.sh from 326d9f8 first (`scp rust-spike/slice/p1/bar.sh
  pareto1:sp19/bar-sa-port-106.sh`). Tested source becomes 326d9f8, which adds only loop_wl.py, live.py's `loop` branch (not run by dev/fuzz) and bar.sh/bar_sum.py.

## drop-compile-demand (gaps ruling)
Fired 0 on dev and fuzz (sa-port-100's bar): they register no vocabulary function, so no non-pattern formula mentions another
node's atom. **loop_wl.py** (`live.py loop`, 420 queries, in the repo) registers four vocabulary functions on the default
registry (Add/even, Mul/positive, Pow/positive, sin/zero), true of SymPy's meaning, mentioning direct arguments and derived nodes.
On orion at 53adc14: Python twice MATCH; Python against Rust MATCH (answers 09238b2537e54383, 0 handler rows); the plant
**fires 3,286 times and DIFFERs** (99 end-state and 99 stream diffs, answers unchanged). Whether it fires in the suite: read
the 5c2a rerun's and the 5c2 bar's "plant fired in the suite" lines (bar_sum.py).

## 5c3 first version (port/5c3 3491f6b; not checked, not for landing as is)
`solver_rs/src/query.rs`: query_lit, prepare_query, emit, query_literal, _query_all, literal_of, _relations, _ensure_atoms,
_ensure_twins (engine.py:506-545, 852-935, 1155-1220), session and solver methods called by name. Counters ses:query_lit..
ses:ensure_twins (session.rs NAMES 78, SES_* 69-77). Plants 49-60 in relations_core.rs: drop-prep-twins, drop-prep-rel,
query-lit-tuple, drop-ql-mention, ql-skip-consistent, drop-qa-mention, drop-lo-memo, drop-lo-discover, drop-rel-process,
drop-ea-ensure, drop-twins-var, drop-emit (`_QUERY_PLANTS` in session_live.py; `_install_queries`, SLICE_QUERY=py keeps Python's).
On orion: loop and dev's first 400 MATCH, handler files 0 rows. **literal_of was reached 0 times** on both (it's only for
non-vocabulary propositions); `_relations` 36 on dev-400, 0 on loop. By rg no test patches a moved method.
Left: test_query_core.py (direct test, in test_compile_loop_core.py's form: `D._case`, Python vs Rust in separate processes;
`Session(Engine())` has relation specs; relation atoms are `eq` and `lt`, made with P's two-argument form, see
satassume/sat/formula.py:14; `prepare_query(P('zero', x+y))` returns an int and leaves relations None), then the 5c3 bar
with the 12 plants, a workload if literal_of stays at 0 on dev/fuzz, and results/port-5c3.md.

## Reports still owe (unchanged)
Quiet catches at engine.py:1906 (5c1, 5c2a first bar: 1 in the suite, 0 dev/fuzz); S's standing as ruled; the _n_conflicts
shim (64 tests); test_incremental_matches_fresh still owed (test-only step before 5c7); test_equality_sharing_is_needed_and_works
re-pointed at 5c4 via `skip-share` (5c2/5c3 don't touch `_share`). No module newly counts whole at 5c2 or 5c3.
