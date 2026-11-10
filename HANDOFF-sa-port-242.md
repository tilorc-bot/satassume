# HANDOFF sa-port-242: state part 3. Digest extension committed and pushed (e82147a); AFTER probe read; scope differs on this branch (not bisected); container tests, core_of, results, bar open

Branch port/state-part3, head = this file's commit, on e82147a, on 46b9f83 (rust-slice 0192b35 underneath). Pushed.
Read this file, then HANDOFF-sa-port-241.md (FILE:LINE MAP) only where a task needs it.

## Done (sa-port-242)

1. THE GATE: e82147a, one test-only commit: c931c16 + 0e41490 + 76d81e0 (digest-coverage.md), extended per the planner's
   (A)/(B) rulings. No engine or crate source changed. The architect (architect-64) and the formula session (now sa-port-244,
   ~/dev/sa-port-7; sa-port-234 no longer exists) have its SHA. What it holds is in
   rust-spike/slice/results/digest-coverage.md, last section ("The extension as taken"): read that, not the code.
   - (A) known differences inside livecmp.py's verdict, exact: known_moved.json, `[_SPLIT python, rust, _CACHE python, rust]`
     per workload and engine point; written by `python known_moved.py X/*.cmp` (it refuses a comparison with any other
     difference). twin [2,4,2,0] and transfer:7:60 [174,182,19,14], [277,289,23,16], [332,347,24,17] reproduce the planner's
     rows. Largest gaps: budget 30 rows on Python against 450 on Rust, value 5673/6443, wiring 1708/2250; distinct rows equal.
   - (B) added: the seven session containers (sc_snapshot) and six scalars (ses_snapshot) per session; the (ii) handles; the
     LRA slot per query (every Rust slot entry must be among Python's `_memoized` calls of that query); every engine a
     workload builds; 5c9a's native tables checked row by row in the process (no Python container to compare with: the
     reason for the report). No plant gives a native table a wrong row, so that check has no planted control.
   - Local result (orion, ~/sa-rust-ids-work/sa-port-242/dg2, one run each, PYTHONHASHSEED=0): Python against Rust MATCH on
     15 workloads (dev fuzz loop zero cert budget core f6 opaque rootof value wiring twin transfer:7:60 transfer2:3:40).
   - Plants caught by the verdict on twin: 409, 450, 451, 453, a known row off by one, and 442 sc-demand-drop
     (test_moved_digest.py; DIFFER only asserted for 442, not which row). 452 by the guard (test_split_order.py). 4 passed.
   - Not done in it: twin in WLS, rk-class-split in PLANTS, test_moved_digest.py and test_split_order.py in TESTS are bar
     arguments (bar.sh takes them from the environment), so they go on the bar's command line. No rows for a second hash
     seed or a shuffle (keys `dev@seed1`): the SEED1 phase would DIFFER on `moved_known_diff` until rows are generated.
   - The 16-workload run took an hour on orion (15:55Z to 16:56Z; fuzz is the long one). Run it on a pareto under a shared
     lease next time, or only the workloads whose rows change.
   - Shared-file changes to name in the report: memo_check.py `_canon` (a split with unset slots reads "<unset>": scope's
     Python run crashed there on an engine built inside a query), live.py (+3 lines for `moved_q`), livecmp.py.
   - Digest side effects on a Rust run: the handles are read through their views (three reads per `Relations`, one per
     session: `xf:*` view counters rise by that much), `memo:native_items` ticks at each engine point, and the LRA slot
     export stays on. Say so beside any counter table taken from a live.py run with the digest on (SLICE_MOVED=0 is off).

2. AFTER probe read (task 2). Summary written to ~/sa-rust-ids-work/sa-port-242/pyc/after-summary.txt (sum.py after; all
   seven exits 0; END 15:48:25Z). sum.py does find sb:*/sc:*; BEFORE's summary has no counts line.
   | workload | queries | _table_get before -> after | converted calls before -> after | sb:fwd_direct | sb:scalar_core | sc:core |
   |---|---|---|---|---|---|---|
   | fuzz | 3000 | 2,079,683 -> 2,268,435 | 3,009,742 -> 3,137,531 | 67,229 | 47,540 | 908,133 |
   | dev | 1985 | 120,618 -> 149,444 | 201,983 -> 228,016 | 4,634 | 11,628 | 66,462 |
   | zero | 854 | 418,024 -> 455,128 | 593,181 -> 618,776 | 12,843 | 10,487 | 145,552 |
   | loop | 420 | 24,873 -> 39,288 | 58,863 -> 71,762 | 2,284 | 3,511 | 36,879 |
   | scope | 169 | 43,720 -> 50,202 | 69,286 -> 74,649 | 1,376 | 2,503 | 22,028 |
   | budget | 28 | 6,245 -> 9,430 | 20,333 -> 21,591 | 1,961 | 200 | 53,922 |
   | cert | 61 | 24,016 -> 27,541 | 36,798 -> 39,799 | 698 | 1,042 | 12,904 |
   sb:attr, sb:fwd_named, sb:scalar_record, sb:scalar_view, sc:record and sc:view are 0 on all seven. The four wrappers
   (_rel_interpret, _rel_link, _rel_share_guard, _ses_visit) are 0 on converted on all seven. The module-wide count ROSE
   after the containers moved, on every workload.

3. Task 3, classified: core_of -> `_table_get` is PART 3's (session_live / SessionCore), so it goes into sub-part 5.
   `core_of` (session.rs:919) does `s.getattr("table")`, which runs session_live.py:179 `_table_get`, a Python function
   that only returns `self.__dict__['_table_view']`, then `.core`. Nothing is converted and no formula is involved: it is
   Rust reaching a session's own core through a Python property. `Ses::of` (ses_cont.rs:179) calls core_of at every
   container site, which is the rise above. NOT FIXED. Proposed: `_table_set` (session_live.py:183) also stores
   `self.__dict__['_core'] = view.core`, and core_of reads `_core` (a plain instance attribute, no Python frame), falling
   back to `table.core`. Then rerun the probe: the rest of `_table_get` is the other `getattr("table")` sites in Rust
   (relations_core.rs 6, compile_loop.rs 6, session_glue.rs 5, query.rs 2, six files with 1), which are not core_of.
   relations_core.rs is off limits under condition 2, so its six stay and are named.

## NEW, blocks the bar: workload scope is a DIFFER on this branch
`live.py scope`, Python against Rust, on the working tree at e82147a: answers equal (answer_diff 0), but stats_diff 164,
session_count_diff 1, end_diff 1, stream_diff 1; first at query 5: Python 3 sessions, Rust 2; engine stats after it
queries 34 against 20, searches 21 against 7, sessions 8 against 7. Totals: Python 171 sessions, Rust 170. The same
with SLICE_MOVED=0 (~/sa-rust-ids-work/sa-port-242/dg3/scope0-{py,rust}.jsonl), so it is not the digest. On (iii)'s bar
scope was a MATCH with 171 sessions (~/sa-rust-ids-work/sa-port-237/bar/sum.txt), so the cause is one of this branch's
unbarred commits: 0414c4f (scalars, solver_of, direct calls), 02354d4 (Session.solver setter) or 7a18df2 (containers).
NOT bisected. Cheapest: `git worktree add` at 02354d4 and at 0414c4f's parent, build each (build_solver.sh, own target
dir), run `live.py scope py` and `rust` with SLICE_MOVED=0 and livecmp. scope registers custom predicates
(scope_wl.py); query 5's lost session suggests a discovery/escalate path (demand, pending, deferred) or a scalar
(truncated, verdict) read differently. The other 15 workloads show no state difference, so this path is reached only
on scope. scope has no row in known_moved.json; generate it after the fix.

## Not done (the brief's remaining tasks, in order)
1. Bisect and fix scope (above). Then scope's known row.
2. core_of off the table property (above), in sub-part 5; rerun the probe (pycalls.py; 241's handoff has the command).
3. Container tests in test_session_boundary.py (its layout: CHILD script run per mode in a subprocess, CASES, rows dict,
   fixtures py/rs at :156-163, test_plant_caught :206 parametrised over PLANTS :24): each container's content, keys and
   values in order, Python against Rust; sc_snapshot equals the views; plants 439-445 fired and caught, each reported
   caught or void with its classification; sc:* fire; one run with SLICE_DISC=py SLICE_LOOP=py SLICE_GLUE=py. Plant 420
   (test_engine_first_refused) is reported the same way.
4. relations' reference held by the core.
5. results/port-state-part3.md sub-part 5 section (first part, the _neg_shared correction, OWED [100]'s two truncated
   sites closed by 0414c4f, the solver view, the containers, the probe table above, core_of).
6. Full bar on the merged tree (slice TESTS one process per file; WLS with twin; PLANTS with rk-class-split and
   sc-*-drop; TESTS with test_moved_digest.py and test_split_order.py), memo cost on a quiet pareto1 lease, Group D in
   seconds if this lands before formula, land. Plants 446-449 and counters 568-579 remain.

## FILE:LINE MAP (additions at this head; the rest is HANDOFF-sa-port-241.md's)
- rust-spike/slice/moved_digest.py: SQ/SD/SS/CACHE names near :58; `typed`; class Moved: `_more` (Session/Engine hooks,
  LRA export), `_lra_rows`, `_engine`, `query_rows`, `_native`, `session_rows` (`@xfer`), `engine_rows` (_SPLIT by content,
  SPLIT_PLANT 450/453, `engine#<n>:`)
- rust-spike/slice/livecmp.py: known rows :27-37 (key `<wl>[@seed<N>][@shuffle<N>]`), `moved_q` compare, known check in
  the `moved_eng` block, native and missing-point checks before `bad =`
- rust-spike/slice/known_moved.py, known_moved.json; live.py rg -n "moved_q"; memo_check.py:50 `_canon`
- rust-spike/slice/test_moved_digest.py (two tests), test_split_order.py
- session.rs:919 core_of; session_live.py:179 _table_get, :183 _table_set; ses_cont.rs:179 Ses::of
- Outputs: orion:~/sa-rust-ids-work/sa-port-242/{dg1,dg2,dg3,pyc/after-summary.txt}; dg2/run.sh is the 16-workload script
