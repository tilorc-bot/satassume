# Element._new step: interpret's memo and results off Python (issue 323)

By sa-port-159 (part 1, a360067 after rebase; was dbcda83) and sa-port-160 (parts 2 and 2b), 8 Nov; plant 123 by sa-port-162; landed by sa-port-169 as one stack with 6g(c2) (tested f1e4a74, bar S1). Planner's C2 ruling
(b): port `Element._new` by taking interpret's memo and results off Python, in its own step after C2. It follows the
state ruling: Rust numbers in payloads, and a Rust `Element` pyclass only where Python reads.

## What moved
- **Part 1 (sa-port-159):** `Num::to_py` (constfield.rs) returns the Rust `Element` pyclass (`PyElem`, end of
  constfield.rs) where it called `Element._new`. `==`, `!=`, `bool`, `hash` and `repr` run on Rust (counters 172-174);
  any other read is the named callback `cf:elem_py_read` (171), which builds the Python Element once per value. The term
  table's `lra_*` memo holds Rust values (`LraMemo`, term/py.rs) and builds the Python result per call (175/176 hit/miss).
- **Part 2 (e2dcace):** the pyclass has `sign()` (`Elem::sign`, counted 177 `cf:elem_sign`), and `constfield.sign` calls
  it for a value that isn't an Element, Fraction or int. The pure-Python default's path is unchanged.
- **Part 2b (5b705df):** the last 100 `Element._new` on dev came from Rust itself: relations_core.rs's port of
  `_order_infinite` called Python's `relations.sign` on an `order_sides` memo coefficient (found by a profile hook:
  `session_live.py:292 _rel_interpret` -> `sa_solver.rel_interpret` -> `constfield.sign`, 100 on dev). A pyclass
  coefficient's sign is now read on Rust (`Elem::sign`), counted 178 `rel:elem_sign`. Undecided returns early, as before.
  So `cf:elem_sign` is 0 on every workload: part 2's Python route is kept only as a guard for other Python readers.
- **Part 2b plant (62a6723, sa-port-162):** plant **123 `rel-elem-sign-flip`** reads a pyclass coefficient's sign negated
  in that branch (a wrong value). Planner's ruling (8 Nov ~09:40): dev reaches the branch 100 times, so the plant must
  be caught on dev. It is (Plants).
- **Shared-file changes:** session_live.py (plant names 118-123), session.rs (counters 170-178), relations_core.rs
  (plants 118-123, the 2b branch), term/py.rs (`LraMemo`), constfield.py `sign` (a `sign()` method of a value that isn't
  an Element, Fraction or int; the pure-Python default never takes it). New step test: test_elem_pyclass.py (27 tests).
- **Numbers this step holds:** counters 170-178, plants 118-123. 5c7 holds 114-117 and counters 156-169.

## `_memoized`: its own named step
Decided with the planner (8 Nov ~09:40): lra_live `_memoized` becomes its own named step inside the state step(s), first
when they're split, with the atom's term ids and the query table on the Rust adapter. After this step no Element crosses
on it. What's left is Rust adapter -> Python `_memoized` -> lra_live `memoized` -> `interpret`/`relation(atom)`/`_ids`
(term_live's Python id lookup of a SymPy atom) -> Rust table -> `_pairs`/`_objs` -> back. Moving it needs term_live and
session_live per-query state on Rust, which the state ruling gives to the state step(s). Counts below are unchanged.

**State-rule search (memo tuple identity):** rg over satassume/, tests/ and rust-spike/slice/ found no reader of a memo
result's identity other than `is True/False/None` (singletons; tests/test_lra_adapter.py:213, test_lra_constants.py). So
returning a freshly built tuple per call, in place of Python's stored one, changes nothing Python can read.

## SHAs and incoming diff
Landed **as one stack with 6g(c2)** (planner's stack ruling, 8 Nov ~11:10: one candidate, one full bar, plant tables and
step evidence kept per step). Tested **f1e4a74** on branch port/stack-c2-elemnew = Element._new 9139a9b + d0965f3
(handoff, docs) on rust-slice **17442af** (5c7's landing), with 6g(c2) 14b76fd cherry-picked on top (clean). Landed on
rust-slice by `PUSH=1 bar.sh land f1e4a74` as the commit carrying this report (sa-port-169); **incoming diff at landing:
none** (rust-slice was still 17442af, the tested base). tested..landed adds HANDOFF-sa-port-167.md and results/ only,
outside the push guard.

Earlier incoming diffs, which is why this step has had three full bars: E2 (5b705df on 9c8d981) was clean; then
**30f3309** (6g(c1)'s landing: rows_tpl.rs and 6 other guarded files over 9c8d981) and **17442af** (5c7) each brought guarded source, so the step was
rebased and rebarred: **F1** (62a6723 on 30f3309) was **stopped by sa-port-162 after plants and seed1 when 5c7 landed**
(superseded by a newer base; not a landing bar); **F2** (9139a9b solo on 17442af, pareto1
`~/sp19/sa-rust-ids-work/sa-port-162/bar-F2/`) ran to `sum` at 12:41Z as the bisect fallback, not needed. The landing
bar is the stack bar **S1** on f1e4a74: pareto1 `~/sp19/sa-rust-ids-work/sa-port-167/bar-S1/` (`sum.txt`, `config.txt`,
`commands.txt`; end markers `done.txt` and `end.txt` written on pareto1 by the job, `exit 0 13:49:41Z`), shared lease,
.so sha256 43dea1a1…. Config: union of both steps': BASE 5c7's suite rows (`sa-port-158/bar-5c7b/suite`, 6,159 ids);
PLANTS 44 (this step's 13 + 6g(c2)'s 31); WLS `f6 value rootof core opaque scope loop zero wiring cert budget`; SEED1=1;
SUITE_PLANTS explicit, 7 (`elem-eq-flip union-skip-overlap within-no-link` for this step and 5c7, 6g's four
`dispatch-ignores-epoch dispatch-redefines-off dispatch-user-off knowledge-no-query-drop`); TESTS 20 files; DIRECT 16.

## The bar (S1, stack on f1e4a74)
S1 equals base on every item, so no bisect was run.
1. **Suite by id against 5c7's rows:** 5,992 passed, 126 failed, 23 skipped, 18 xfailed, 6,159 ids. New 0, gone 0,
   changed outcome 0. Passed: **5,991 with no firing, 1 with a firing** (`test_ci_stream_reports_only_what_replays`).
   S's standing: S's gate is met except for the 46 named stub failures, one cause. Step tests 655 passed (20 files).
2. **dev (1,985) and fuzz (3,000):** answers and end state MATCH py vs rust, traced vs untraced, each with a Python
   control (dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6; 0 Python solvers on the Rust side); seed1 dev and fuzz MATCH.
   The 11 workloads MATCH with controls (cert 6a09c059eb266747; core 1,636; budget 28).
3. **Plants:** per-step tables below (this step's here; 6g(c2)'s in results/port-6g.md, "Step 6g(c2)").
4. **Quiet handlers (suite):** 39 rows in 2 tests, **multiset same as base**: 34 `_ok` and 4 `_rb_clauses`
   AttributeError in `_consistent` (`test_ci_stream_reports_only_what_replays`), 1 "Already mutably borrowed" at
   `Engine._build_context` (`test_protocol_on_fuzz`, the 46-stub cause). 0 handler rows on dev, fuzz, seed1 and the 11
   workloads; plant runs have rows only under ad-kind-swap (dev 2, fuzz 315) and rows-block-key-n (dev 1, fuzz 16). The
   engine's `except Exception` at the complete check: TermFault 0.
5. **Known differences:** none in answers, read state or suite outcomes.
DIRECT: relations_direct, dispatch_direct and plain common_direct exit 0; each common_direct plant exits 1 (DIFFERENCES
1-10), as on F2 and 6g(c1)'s bar.

## Plants, this step (S1; fired, D = DIFFER against this run's Python)
| plant | caught (DIFFER) on, fired | fired, MATCH | 0 on |
|---|---|---|---|
| elem-memo-plus1 (memo, wrong value) | dev 2,461, fuzz 93,210, cert 1,532, scope 1,039, zero 5,612 | value 203 | the other 6 |
| **123 rel-elem-sign-flip** (2b branch) | **dev 100: end/stream only, answers equal** (caught by state) | | every other workload |
| elem-from-neg | dev 71, fuzz 617, cert 121 | | the other 10 |
| elem-repr-bracket | dev 2,870, fuzz 37,501, cert 533 | | the other 10 |
| elem-eq-flip | **void on all 13 workloads; caught by the suite** (`test_lra_constant_coefficients.py::test_pivots_with_constants_leave_a_consistent_tableau` passed -> failed, fired 1) | | all 13 |
| **elem-hash-skew** | | **dev 179: fired and silent** (a hash one off never changes a result; named) | the other 12 |
| controls: cf-laurent-rational (C2) | cert 119 | dev 121, fuzz 200 | others |
| pay-int-offset (C1) | dev 556, fuzz 18,488, cert 250, scope 230, zero 1,316 | budget 12, value 319 | others |
| ad-kind-swap (B) | dev 254, fuzz 4,191, cert 62, scope 147, value 396, zero 1,439 | budget 1 | others |
| theory-no-assume (scope) | dev 1,087, fuzz 5,918, cert 122, scope 299, zero 1,263 | budget 16, core 309, f6 10, loop 244, opaque 32, rootof 369, value 322, wiring 5,016 | |
| al-drop-delta (5c6) | dev 197, fuzz 2,631, cert 61, scope 36, value 197, zero 542 | | others |
| union-skip-overlap (5c7) | budget 65; suite: 2 changed (`test_set_verdict.py` x2) | dev 88, fuzz 7,236, cert 108, scope 43, zero 77 | |
| within-no-link (5c7) | suite: fired 31,129, 0 changed (as on 5c7's bar) | dev 197, fuzz 3,108, budget 7, cert 61, scope 133, value 318, zero 608 | |

The memo plant is caught as a wrong value (answers DIFFER, first dev query 275: `null` -> `false`), not as a dropped
entry, as ruling (b) asks. Plant 123: the planner's ruling (8 Nov ~09:40) asked for it on the 2b branch, caught on dev
before landing; it was (sa-port-162's orion run `p123/`, 50 queries end/stream DIFFER, answers_sha equal) and again here.

## Reached (moved item, Rust run, S1 session.json)
- `cf:elem_new` (a Rust `Element` pyclass made where Python reads): dev 1,380, fuzz 2,506, cert 446; 0 elsewhere.
- `cf:elem_repr` dev 2,870, fuzz 37,501, cert 533; `cf:elem_hash` dev 179; `cf:elem_eq` 0 on every workload (the
  suite reaches it: elem-eq-flip's catch); `cf:elem_py_read` (the named callback) **0 everywhere**.
- lra_* memo on Rust values: `lra:memo_hit`/`lra:memo_miss` dev 2,642/2,833, fuzz 94,596/70,358, cert 1,532/738, scope
  1,039/1,429, value 203/2,423, zero 7,209/11,462, budget 0/72.
- 2b: `rel:elem_sign` dev 100 (0 elsewhere); `cf:elem_sign` 0 everywhere (part 2's Python route is a guard only).
Reached by dev, fuzz and cert (all of the above), plus scope, value, zero and budget for the memo. Caught on dev, fuzz,
cert, scope and zero (table).

## Crossings before and after
- **`Element._new` from Rust** (cf_trace, sa-port-160/162 orion runs q3-q5 and `t4/`): dev **703 -> 0**, fuzz
  **1,552 -> 0**, cert **163 -> 0**. Python's own `constant`/`radical` callbacks and from_sympy still build Python
  Elements (f6 30, core 24, wiring 3, opaque 2, unchanged).
- **lra_live `_memoized`** (`ad:cb_memoized`): dev **5,508 -> 5,508**, fuzz **164,954 -> 164,954**, cert **2,270 ->
  2,270** (5c7's bar rows vs S1), also scope 2,472, value 2,626, zero 18,671, budget 72. Unchanged by design: it's its
  own named step inside the state step(s) (above). No Element crosses on it now.
- **enclose:** `Constant.enclose` dev **100 -> 0** (cf_trace): the 100 were Python `relations.sign` calls from
  relations_core.rs's `_order_infinite`, which part 2b moved onto `Elem::sign`. Other enclose calls unchanged. The bar
  itself has no enclose counter, so this rests on the orion traces.

## Module count
**13 of 32, unchanged**, checked against the "Counted modules" list in ~/dev/architect/STATUS.md (lines 11-17): solver,
euf, lra, transfer, lra_cert; realroots.py, templates/atoms.py (footnote: neither dev nor fuzz reaches realroots or
atoms' value_units; the suite reaches realroots); registry.py, templates/__init__.py; scope.py; table.py, _common.py
(footnotes: kept paths only; const_value callback); relations.py. constfield.py isn't whole (`constant`, `radical`,
`_generic`, `Constant.__init__`, the gcd trio, `_short`, `enclose` still run per query); lra_adapter.py isn't
(`_memoized`, `constant_bounds`). 6g(c2) leaves core.py per query (port-6g.md).

## Kept reasons (Rust run, share of queries, against base)
All equal to base: out-of-scope dev 24/1,985 (1.21%), fuzz 0/3,000, 0 on every extra workload; refused f6 13/2,902
(Float 10, lra callback on a derived term 1, scaffold mismatch 2), opaque 7/2,546 (infinity/nan/Float 2, infinity or
nan 5), value 15/3,742 (Float), wiring 1/6,512 (lra), 0 on cert, core, loop, rootof, scope, zero; budget 0/28 and 0/28
(base: 5c7's report, no bar row). No rise.

## Not run
Moved to "before any backend PR", and none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the
boundary rescore and suite column; the final drop score and its lost rows; the suite split with Python's counter;
`order:_rows`' evidence (not caught meanwhile); the `_forms` guard test; history reruns (seed1 was run); forced moves;
the native path; timing. **Speed not measured.**

Other notes:
- 6g(c2)'s solo bar (sa-port-161) and F2 weren't used: S1 matched base, so no bisect. sa-port-161's `done.txt` was **not
  written by hand**: its job wrote it on pareto1 (`Sun Nov 8 11:11:09 AM UTC 2026`, the same second as its `sum` phase)
  after its launcher's ssh dropped at ~10:38; F2's job wrote its own at 12:41Z. The completeness check the stack ruling
  asks before a hand-written marker therefore wasn't needed; S1's own completeness was checked: suite rows for all 6,159
  ids, 13 workload comparisons with controls plus seed1, 44 x 13 = 572 plant rows, handler rows for the suite, live,
  extra and plant runs.
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone; 10 of the 25 boundary mutants have no real-engine catch, and
  the boundary suite column wasn't run. The `_n_conflicts` view in rust_plugin.py is a test-plugin shim (64 tests).
- Ownership: port-ownership.md :107 and the TSV's `Element._new` row name the stack, tested f1e4a74.
