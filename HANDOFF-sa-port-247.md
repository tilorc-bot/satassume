# HANDOFF sa-port-247: state part 3. Gate items (ii) and (iii) done; the landing bar (iv) is RUNNING on f252daf; NOT LANDED

Branch port/state-part3, pushed, on origin/rust-slice 0192b35 (unchanged when checked 17:46Z 10 Nov). Handed off between
items: the bar needs about three hours and nothing else is left before it is read. Read this, then HANDOFF-sa-port-245.md
(scope fix), HANDOFF-sa-port-242.md (digest, probe) and results/port-state-part3.md's sub-part 5 section (written here).

## Done (sa-port-247)
0. Gate (i), the detached slice run on 4d14638 (orion:~/sa-rust-ids-work/sa-port-245/slice-i/summary.txt, 53 files, END
   17:22:55Z): three files not exit 0, all known base failures: test_cf_diff.py (collection error), test_catch_count.py
   (3 failed), test_handler_count.py (2 failed). test_term_live.py passes on this branch (20 passed, 1 skipped; 02354d4
   fixed its two stale tests). Nothing new belongs to 4d14638.
1. Gate (ii), fd0fabb: `core_of` off the `Session.table` property.
   - session_live `_table_set` stores `_core` beside `_table_view`; session.rs `core_of` reads `_core`, `table_of` reads
     `_table_view` (11 sites: compile_loop.rs 5, session_glue.rs 4, query.rs 2); compile_loop.rs and discovery.rs use
     session.rs's `core_of`; session_live's 44 `isinstance(s.table, TableView)` dispatch tests read `__dict__`.
   - Counter 570 `sb:core_prop` (a read that still goes through the property). NAMES and COUNTS are 571 long.
   - Plants 447 `sb-core-unset` (equal answers by construction; caught by `sb:core_prop` > 0 and `_table_get` rising, in
     test_core_read_without_the_property) and 448 `sb-core-stale` (first core seen for every session; rows differ).
     SB_PLANTS has 18 names (431 + index).
   - Not touched (condition 2), still reading the property from Rust: relations_core.rs :786 (`s.table.core`), :2270,
     :2332, :2468. (:742, :2577 read a query's table.) Nothing stopped on; no question sent. A one-line change at :786
     (call `session::core_of`) would remove most of what is left; it is the file owner's (formula, after rebasing) or the
     planner's to rule. NAME IT IN THE REPORT.
   - Probe (pycalls.py, session_live.py, seven workloads, Rust, --check plain, all exit 0;
     orion:~/sa-rust-ids-work/sa-port-247/pyc/core, probe.sh and sum.py beside it). `_table_get` on converted queries,
     d8f9146 -> 7a18df2 -> fd0fabb: fuzz 2,079,683 -> 2,268,435 -> 218,742; dev 120,618 -> 149,444 -> 10,775; zero
     418,024 -> 455,128 -> 46,702; loop 24,873 -> 39,288 -> 2,483; scope 43,720 -> 50,202 -> 4,472; budget 6,245 -> 9,430
     -> 533; cert 24,016 -> 27,541 -> 2,411. All converted calls at fd0fabb: fuzz 1,087,838, dev 89,347, zero 210,350, loop
     34,957, scope 29,003, budget 12,694, cert 14,669 (27 to 40 nonzero names: the module does not count yet).
     sb:core_prop, sb:attr, sb:fwd_named, sc:view, sc:record: 0 on all seven. sc:key_hash / sc:key_eq: fuzz 478,541 /
     1,193; dev 28,951 / 0; zero 73,045 / 0; loop 14,880 / 16; scope 10,220 / 0; budget 46,412 / 0; cert 6,513 / 0.
     The full table is in results/port-state-part3.md.
   - Every slice test file, one process per file, on fd0fabb's tree (orion:~/sa-rust-ids-work/sa-port-247/slice-ii): the
     same three known base failures, nothing else.
2. Gate (iii), 4ce60ab (test-only): container tests and plants 439-445 in test_session_boundary.py (27 passed).
   Content rows `cont:*` Python against Rust; `cview` (sc_snapshot equals the views; view writes and assignments read
   back); sc:core, sc:view, sc:record fire; one run with SLICE_DISC=py SLICE_LOOP=py SLICE_GLUE=py. Each plant fires and
   its content row differs. Rows that differ besides content: frontier, pending_c, _groups: answers; deferred: the cut
   session's row; demand: solver dump and the keys case's counts; literals and pending: content only (literals is a memo;
   pending's native write is reached only with a registered vocabulary function under a demand, so expect
   `sc-pending-drop` to fire 0 on the workloads: void there, footnote or a workload under the gaps ruling).
3. bar.sh, f252daf: `TESTS_SPLIT=1` runs each test file in its own pytest process; `TESTS=all` is every test_*.py.
4. results/port-state-part3.md: sub-part 5 section and a new "Not run" (docs; committed after the tested SHA, which
   `bar.sh land` allows for results/).

## Running (detached; read the end marker)
The landing bar on tested f252daf: pareto1 `~/sp19/sa-rust-ids-work/sa-port-247/bar-part3/` (end.txt, sum.txt, phases.txt,
tests.txt + tests/, suite, live, extra/summary.txt, suite-<plant>). Started 17:46:58Z 10 Nov; (iii)'s took 2 h 52 with 46
plants and 5 workloads, this one has 22 plants and 14 workloads. Config: `run-bar-part3.sh` in that directory's parent
(BASE = (iii)'s bar suite rows, sa-port-236/bar-iii-b3/suite; SUITE_PLANTS zero; N=6; DIRECT relations_direct.py 300 0).
Launcher on orion: pid in ~/sa-rust-ids-work/sa-port-247/bar-launch.pid, log bar-launch.log (machine run, shared lease).
Read at 17:48Z: build exit 0 (.so sha256 e9aaf5052540); tests: 36 of 53 files in, not exit 0 only test_cf_diff.py,
test_catch_count.py, test_handler_count.py.

## Not done: gate (iv)
1. Read the bar: sum.txt (three suite numbers, passed split by firing, handler multiset against the base), tests.txt's
   last line, live and extra summaries (16 workloads Python against Rust; twin and scope are in WLS), the plant table for
   all 22 PLANTS on dev, fuzz and the 14 WLS, with the void ones named and classified, and the suite runs under the plants
   that fired 0 on dev and fuzz. Plant 420 is test_install_order.py::test_engine_first_refused (in tests).
2. The gate's additions: sc:key_hash and sc:key_eq per workload and in the suite (session reports in live/ and extra/);
   the relevance.rs AttributeError change: handler multiset against the base on every workload and the suite, any new
   firing is a DIFFER.
3. Memo-cost timing on a quiet pareto1 lease; Group D in seconds, pinned on pareto1 via bench-container, against
   sa-port-146's 0.158 s dev / 1.990 s fuzz (RULINGS.md line 12; results/port-state-relations.md :237 and :638 show what
   (iii) reported and why shares alone don't count).
4. Land: `sh rust-spike/slice/p1/bar.sh land f252daf` in this clone (no PUSH; read the incoming diff), then PUSH=1; no
   landing while another session's full bar runs ([91]); tell the architect the SHA. Then the report with every MUST STAY
   item.
Not in this link's gate and not done: "relations' reference held by the core" (the brief's old TASK item 3).

## FILE:LINE MAP (at this head; the rest is HANDOFF-sa-port-245.md's, -242's and -241's)
- rust-spike/slice/solver_rs/src/session.rs: :17 NAMES[571]; SB_CORE_PROP = 570 below SC_KEY_EQ; SB_PLANTS (18 names),
  SB_CORE_UNSET 447, SB_CORE_STALE 448; `table_of`, STALE_CORE and `core_of` together (rg 'fn core_of'); sc_snapshot
  (rg 'fn sc_snapshot')
- rust-spike/slice/session_live.py: `_table_get` :179, `_table_set` below it (stores `_core`); `_SB_PLANTS` (rg)
- rust-spike/slice/test_session_boundary.py: CONT_PLANTS, CORE_PLANTS near :40; CHILD's rnd/cont/csnap, CASES, trunc
  (cview-write), keys, core, mid; tests test_core_read_without_the_property, test_containers_mean_something,
  test_python_methods_on_the_views, test_container_plants (prints a PLANT line per plant: pytest -rA)
- rust-spike/slice/p1/bar.sh: tests phase (TESTS_SPLIT), land at the top; bar_sum.py
- relations_core.rs (not touched): :786, :2270, :2332, :2468
- results/port-state-part3.md: "Sub-part 5" and "Not run"
- Outputs: orion:~/sa-rust-ids-work/sa-port-247/{pyc/core,slice-ii,tsb4.log,bar-launch.log};
  pareto1:~/sp19/sa-rust-ids-work/sa-port-247/{bar-part3,run-bar-part3.sh}; tree pareto1:~/sp19/dev/sa-port-247-part3
- Ranges left: plant 449 and 460-469; counters 571-579 and 690-699
