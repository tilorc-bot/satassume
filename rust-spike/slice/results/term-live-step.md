# term_live's per-query frames on Rust (issue 323; sa-port-313, -314, -315)

Tested source 5b1d96f (from rust-slice c229014). Times UTC, 17-18 Nov. Scratch: orion ~/sa-rust-ids-work/sa-port-313/,
-314/, -315/; bar rows pareto0 ~/sp19/sa-rust-ids-work/sa-port-314/bar/ (sum.txt).

## What moved

`solver_rs/src/term/live.rs` (`sa_solver.TermFrames`, `Guarded`, `RelationRun`): `current`, `term_id` (+ `_int_id`,
`same_class`), `_ids`, `_relation_atom`'s `run`, `_guarded`'s wrapper, `_Mark` init/`_note`/`add`. Rust reads and
writes Python's own maps under Python's keys.

- Python stays the default and the reference. The Rust frames are opt-in: `SLICE_TERM_FRAMES=rust` (default `py`),
  read in `term_live.from_env` and `fresh.py`; `term_live.use_rust(on)`.
- No new native table. The one store is plant 740's (`stale`), listed as `term.live.STALE` in `NATIVE_EXTRA` while the
  frames are on.
- Shared files touched: p1/bar.sh (`penv`), fresh.py (reads the switch), formula.rs (`class_is_on`), lib.rs,
  term/mod.rs.
- Code redundant on the Rust path (Python's `current`/`term_id`/`_ids`/`_guarded`/`run`/`_Mark.__init__`/`_note`/`add`)
  stays as the reference. Owner: the step that makes the switch the default (Tilo's decision).

## Answers and Python calls (313, pareto1, tree 7a13f7b; 5b1d96f differs only in plant 740's branch)

2x2 of the frames switch against SLICE_CONVERT on the 20 workloads (30,753 queries): 80 of 80 cells MATCH Python.

| Python calls, 20 workloads | frames off | frames on |
|---|---|---|
| term_live.py | 8,497,075 | 1,258,512 (-85.2%), the same under both walkers |
| the other 12 probe files | | identical in all four cells |
| rises per function and workload | | 0 |
| knowledge_live per workload | | unchanged |

Moved functions go to 0: `current` 1,831,941, `_Mark._note` 1,214,148, `term_id` 686,469, `g` 424,891, `_ids` 397,106,
`run` 115,387. `stack` 1,890,663 -> 58,722; `same_class` 683,867 -> 7,029.

## The bar (pareto0, 5b1d96f, .so c1ede79e): END 0 at 04:36:30Z 18 Nov

Config: 302's full bar with 310's launcher (no SLICE_ variable from the launcher, N=6), plus the six `term:tl-*` plants
and `frames:rust` as workload columns and suite rows. Base: 310's suite rows on c229014 (127 failed, 5991 passed).

| check | result |
|---|---|
| tests (72 files, one process each) | all exit 0; test_term_frames.py 18 passed |
| suite, plain | 127 failed / 5991 passed, 6159 ids; against base new 0, gone 0, changed 0 |
| live dev, fuzz | 8 of 8 MATCH (answers_sha 31cd0945c07f02a6, 173502b6ef285ad6) |
| 15 extra workloads | 30 of 30 MATCH |
| `frames:rust`, 17 workloads | 17 of 17 MATCH |
| `frames:rust`, suite | 127 failed / 5991 passed; against base new 0, gone 0, changed 0 |
| fm rows | plain: 20 workloads, 0 differ; the two fm plants exit 1 |
| TermFault in any suite log | 0 |

`frames:rust` is the expected "no difference" row, not a plant missed. A workload row carries no record of which
frames ran. The switch reaches those rows by the same `penv` line as the `term:tl-*` rows, whose plants act only in
the Rust frames and fired there. S1's rows record `TermFrames` for each frames arm.

Environment (env-summary.txt, the watcher on every suite row's processes): `SLICE_TERM_FRAMES=rust` in
suite-frames:rust and the six suite-term:tl-* rows, in no other row; `SLICE_CONVERT=rust` in the five convert:* rows
only.

The 25 older workload plant columns: verdict and fired count equal 302's bar in all 425 rows.

Older suite plant rows against 310's rows by id: enc-int-no-sign 0 ids differ, term-row-no-number 0;
klass-no-is-expr, walk-args-unreversed and fm-ite-swap differ in one id, the planted-history test. enc-true-as-false:
585 failed, 458 changed, 101 ids differ from 310's row. That row did not reproduce by id for 310 either (130 ids
between its run and 309's); still caught.

The planted-history test (tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence,
the known id()-reuse row): failed in the plain suite and in frames:rust, as on base. Passed in 5 of the 25 suite rows
(klass-no-is-expr, fm-ite-swap, same-is, term:mark-leaves-entry, term:mark-skips-native), failed in 20. a28c548's
repeat check was not rerun, since the plain and frames:rust rows equal the base.

class-is: suite row 137 failed, 10 changed (informational); twin workload DIFFER, fired 100; the kept tests pass.

### Plants 740-745 (they act only in the Rust frames)

| plant | workloads DIFFER of 17 (dev fired / fuzz fired) | suite ids changed | caught beyond test_term_frames.py by |
|---|---|---|---|
| 740 tl-term-stale | 9 (1,727 / 94,495) | 112 | workload answers (dev, fuzz, budget, cls, scope, transfer, transfer2, value, zero); suite |
| 741 tl-ids-reversed | 11 (2,861 / 66,867) | 15 | workload rows (dev, fuzz, budget, cert, cls, scope, transfer, transfer2, twin, value, zero); suite |
| 742 tl-current-outer | 0 (0 / 0) | 0 | kept test only |
| 743 tl-run-flip | 9 (762 / 41,503) | 234 | workload answers (dev, fuzz, cert, cls, scope, transfer, transfer2, twin, zero); suite |
| 744 tl-guard-quiet | 0 (0 / 0) | 0 | kept test only |
| 745 tl-mark-skip | 0 (22,776 / 50,966) | 0 | the discard check: 40 names left in 1985 of 1985 (313, dev); kept test |

- 742, why no workload reaches it: it fires only when one query runs inside another (a per-thread stack of two). No
  workload does that (`reentry 0 0` on every row) and it fired 0 in all 17; the kept test builds the nesting.
- 744, why no workload reaches it: it fires only when an ordinary exception crosses a guarded site. None does in any
  workload or suite row (TermFault 0, handler files 0 rows); the kept test raises one.
- 745 is the discard plant. It fires in every workload and changes no answer; the restore it skips is checked by
  term_discard (fresh.py --discard), not by the bar's rows.
- 740 is not caught by the discard run (exit 0, output equal to the unplanted run).
- bar_sum prints "plant fired in the suite: 0" for all six suite rows: the frames' fires go to COUNTS, which that
  counter does not read. 740, 741 and 743 show they act in the suite by their changed ids.

### Exceptions caught at engine.py:1906

- Workload rows: 0. All 616 handler files in live/ and extra/ have 0 rows, the 17 frames:rust files and the 102
  term:tl-* files included.
- Suite, plain and frames:rust: 39 rows in 2 tests, the base's multiset (34 + 4 + 1); ids whose caught rows differ
  from base: 0.
- Suite term:tl-* rows: the same 39, except tl-run-flip 42 (5 ids differ from base).
- test_handler_count.py and test_catch_count.py pass in the tests phase, which is what shows the counter fires.

### Wall time of this bar (planner addition 7)

4 h 22 m 47 s (00:13:43Z to 04:36:30Z). 302's bar over the same phases: 3 h 48 m 01 s.

| phase | 302 (30 plant columns, 17 suite rows) | this bar (32 plant columns, 24 suite rows) |
|---|---|---|
| tests | 2 m 15 s | 2 m 21 s |
| suite | 1 m 48 s | 1 m 50 s |
| live | 14 m 14 s | 14 m 30 s |
| plants (dev, fuzz) | 53 m 06 s | 62 m 46 s |
| extra (15 workloads) | 122 m 58 s | 133 m 46 s |
| suiteplants | 32 m 47 s | 46 m 34 s |
| fmrows | 53 s | 57 s |

- Suite rows are 1 m 42 s to 2 m 10 s each; fm-ite-swap 4 m 39 s. The seven new rows (frames:rust and six term:tl-*)
  took 13 m 08 s, the five convert:* rows 9 m 08 s: 22 m 16 s for the twelve.
- The workload columns are the cost. Plants and extra are 196 m 32 s for 32 columns, about 6 m a column, so the seven
  new columns are about 43 m by share. Three workloads make 108 m of extra's 134 m: budget 43 m 37 s, rootof 33 m 01 s,
  wiring 31 m 16 s.
- The twelve rows cost about 65 m of the 4 h 23 m. The bar was already 3 h 48 m before them.

## Other checks

- History check (314, planner addition 5): 312's iv.sh with a frames column, 64 runs on orion, one process each: 0 ids
  move in any group against 312's c229014 rows. The 16 Rust-backend frames=rust runs had TermFrames installed.
- Discard check with the frames on (dev, 5b1d96f's build): output byte-equal to 313's; 1985 armed, checked, clean.
- The 10 slice-test ids that fail when the 10 slice files share one pytest process (6 in test_term_ids.py, 4 in
  test_term_live.py) fail the same on a c229014 tree and with the switch off and on. Their messages point to harness
  install/patch state between tests, not satassume answer state: KeyError 'term:rust:_eq_links', "refused:key: differs
  from Python's" and 'refused:scaffold: rebuilt form differs from Rust'; `GuardMethod` lacking `__wrapped__`; an
  identity assert on `relation_atom`; three "the query never reached it" (`assert 0 > 0`); one empty memo; one plant
  that did not move its answer. Classified from the messages and from each file passing alone in the bar's tests
  phase; the pairs of tests were not bisected.

## S1 (pareto1 quiet lease, pinned to CPU 2, 7 interleaved rounds; reported, not a gate)

Median wall seconds (min-max). Each row's `term_frames` field: `TermFrames` in both frames arms, `py` in the others,
`no-switch` on c229014; every digest equals Python's.

| arm | dev | fuzz |
|---|---|---|
| c229014 | 0.757 (0.754-0.772) | 6.388 (6.365-6.438) |
| 5b1d96f, frames off | 0.759 (0.750-0.790) | 6.394 (6.289-6.459) |
| 5b1d96f, frames on | 0.780 (0.772-0.794) | 6.407 (6.362-6.438) |
| 5b1d96f, Rust walker, frames off | 0.647 (0.645-0.677) | 5.916 (5.878-5.947) |
| 5b1d96f, Rust walker, frames on | 0.667 (0.664-0.682) | 5.912 (5.880-5.974) |

- Default path, c229014 -> 5b1d96f: dev +0.24% paired median (-1.63 to +4.71), fuzz +0.02% (-1.47 to +0.72): inside
  the spread.
- Frames off -> on, dev: +2.74% paired median (-1.88 to +5.72), slower in 6 of 7 rounds; under the Rust walker +3.06%
  (-0.91 to +4.76), 6 of 7. The min-max ranges overlap. The sampled runs agree: 0.772-0.792 s off, 0.798-0.810 s on
  (10 runs each).
- Frames off -> on, fuzz: +0.21% (-0.62 to +1.62) and, under the Rust walker, -0.07% (-0.74 to +0.46): inside the
  spread.
- So no wall gain, and dev is about 3% slower with the frames on.

term_live.py self samples (pysampler, N = samples inside the query loop):

| | frames off (5b1d96f) | frames on |
|---|---|---|
| dev | 207 of 7,777 (2.66%) | 79 of 7,977 (0.99%) |
| fuzz | 1,401 of 39,172 (3.58%) | 424 of 39,199 (1.08%) |

c229014: dev 207 of 7,759 (2.67%), fuzz 1,282 of 39,086 (3.28%). The samples move from the Python callback category
to C API calls made from Rust: dev callback 4,157 -> 3,747 and capi<-rust 1,934 -> 2,469; fuzz 13,589 -> 11,311 and
13,552 -> 15,253. The frames work over Python's own dicts, so each lookup is still a C API call.

## For the backend PR list

`Table::row` (solver_rs/src/term/table.rs:504) indexes unchecked and panics on a term id past the table
(PanicException through `formula_ask`). Reached only under the old, unbounded plant 740; no unplanted run reached it.
Not a landing condition.
