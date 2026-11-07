# Step 4 gate (issue 323)

**The gate as ruled is not met.** Number 3 is 46: under the ruling each of those is a gate failure, whatever its cause, and every one is the same stub re-entering the solver. Nothing else in the gate fails: every answer, state and harness compare matches Python with 0 differences, and every mutant is caught by some column.

It rests on:
- **Suite:** run 5, 5,960 / 77 / 46, below. Of the 5,960, only 2,822 made a Rust solver inside the test.
- **History:** 14 of 14 pairs, 0 differences.
- **Harness:** 78,000 queries, 0 mismatches, identical on both backends.
- **Mutants:** 35 of 35 caught, but 5, 6, 7 and 9 only by the API fuzzer with stub theories, and 10 of the 25 boundary mutants by no real-engine column.

Crate: `sa_solver.so` sha 44577e02, on all of these. No commit touches `solver_rs` since step 3's 1b84ef9.

## The planner's three numbers
Run 5: real crate, shuffled order, 3 workers, orion. An unshuffled run on the probe build gave the same counts.

| | tests |
|---|---:|
| 1. Ran on Rust and passed | 5,960 |
| 2. Kept on Python, needs internals (all pass on Python) | 77 |
| 3. Failed | 46, all with the borrow RuntimeError from a test stub |
| Skipped / xfailed, same on both | 23 / 18 |

Python on the same run: 6,083 passed, 0 failed. Python solvers made in the Rust run: 0.
- **Not "passes the full suite".** Number 2 and 3 are real. Of the 5,960, 2,822 made a Rust solver inside the test; 3,138 didn't, so they say little or nothing about Rust.
- Change from sa-rust-17 (5,949 / 77 / 57): the 11 failing on both now pass on both.
- By-name lists, the 46 included: `step4-lists.md`. Full report: `step4-suite-run5.md`.

**Smallest test for number 3:** `tests/test_euf.py::test_solver_reflexive_atom_is_valid`, 4 lines. On Rust: `RuntimeError: Already mutably borrowed` at `tests/theory_harness.py:242`, reached from `check_entails`. On Python it passes.

**Not fixed, and why.** The ruling says to fix this if an adapter can reach it; only the stub does (below). Line 242 is `s.nvars()` inside the audit's `assert`, and the same expression reads `s._val` next. So letting `nvars` run during a hook would only change the error to a missing attribute, which moves these tests to number 2 and shows nothing new about Rust. That's from reading the line, not from a run. It would also change the crate that all the results here rest on.

## The 11 failing on both: environment, fixed
The tests set `PYTHONPATH` to the repo root, or run `python -I`, so their subprocesses lost sympy, which was on `PYTHONPATH` only. Added `~/sa-rust-ids-work/venv/lib/python3.12/site-packages/sa_rust_sympy.pth`, outside the clone. Their 5 files: 137 of 137 pass on both backends. **These 11 count in number 1 but aren't evidence about Rust:** they made 0 Rust solvers, and their subprocesses don't get the patch.

## Re-entry: only a test stub
Every borrow RuntimeError found raises at `tests/theory_harness.py:242`, in `Recorder.check`, which audits the solver from inside a hook. This covers the 5 that showed only a Hypothesis frame: read from their sub-exceptions, and the text of all 5 in run 5 names line 242.
- **Adapters:** `LRATheory`, `EUFTheory` and `TransferTheory`, the objects that get hooks, hold no solver reference (rg for `self._solver` and the like hits only `lra_adapter.py` and `euf_adapter.py`, whose objects aren't attached as theories). Read, and consistent with the runs below; not a proof over every path.
- **Audit off (`SLICE_AUDIT_OFF=1`, 10 theory files, Rust):** 0 borrow errors in 928 tests.
- **Control:** the same patch on pure Python. Every Rust failure that isn't a missing attribute fails on Python with the same message (hiding the solver breaks the harness's level checks). No test passes on Rust and fails on Python; the only tests passing on Python and failing on Rust are missing-attribute failures.
- **`SLICE_AUDIT_OFF=2`** also drops `check_protocol`: of the 18 such tests, 17 pass on both backends, so their answer comparisons ran on Rust. The other, `test_protocol_on_fuzz`, needs the counts that patch removes, and fails the same on both.
- Of the 46, 44 pass on Rust with the audit off. The other 2: `test_protocol_on_fuzz`, and `test_real_theories_match_fresh_solvers[both]`, which then reads `_trail_lim`.
- **They stay failures in number 3.** Audit-off is reported apart and isn't part of the numbers. Hook-audit limit: an exception swallowed by `except` inside a hook wouldn't show here.

## `test_fuzz_entails_and_implied`: the 120 s TimeoutError
**Answer: the audit's re-entry failure plus load, not a hang. A real Rust slowdown isn't shown to be the cause.** Shown on reproductions; for the 3 original runs it's inferred from their stacks and outcomes, since they weren't instrumented. The test stays a failure in number 3 either way.

The guard is `_hang_guard`, an autouse fixture: 120 s around the **whole** `@given` test, shrinking included, not per example. With the audit on, Rust fails on the first example (about 0.1 s in) and Hypothesis then spends the rest of the time shrinking.

`guard_probe.py`, same Hypothesis seeds 0, 1, 2. Wall clock on a shared machine, so a diagnostic, not a timing result:

| Case | Outcome | Whole test (s) | Examples run | Longest example (s) | Guard fired |
|---|---|---|---|---|---|
| Rust, audit on | failed | 58, 68, 106 | 2,765, 2,926, 3,742 | 1.0, 1.1, 1.3 | no |
| Python, same failure injected | failed | 35, 23, 34 | 685, 593, 694 | 0.9, 0.7, 2.0 | no |
| Rust, audit-off-2 | passed | 14, 9, 23 | 152, 151, 150 | 0.8, 0.3, 1.7 | no |
| Python | passed | 15, 3, 14 | 152, 151, 150 | 0.8, 0.1, 1.7 | no |
| **One core, 3 at once:** Rust, audit on | failed | 120, 120, 200 | 1,738, 1,433, 1,628 when it fired | 3.3, 2.0, 2.3 | **yes, all 3, at 120.0 s** |
| One core: Python, injected | failed | 48, 53, 59 | 685, 593, 694 | 0.8, 2.1, 2.0 | no |
| One core: Rust, audit-off-2 | passed | 13, 11, 16 | 152, 151, 150 | 0.8, 0.4, 1.6 | no |

- **Audit re-entry:** it's what makes the test fail and shrink. With the audit off, Rust runs about 150 examples and passes.
- **Load:** the same runs stay under 120 s unpinned and pass it on a shared core. The old runs varied the same way: 3 of 5 fired.
- **Hang:** no. No example took over 3.3 s. In the pinned runs the guard fired in Hypothesis's `cache.py` once and in the test's own `fm_feasible` reference twice. The 3 original stacks are the same kind: Hypothesis `cache.py`, `brute_models`, Hypothesis `data.py`.
- **Same symptoms:** 2 of the 3 pinned runs end in `FlakyStrategyDefinition`, as sa-rust-17's first run did. The third ends with "4 distinct failures".
- **Why Rust runs more examples than the injected control:** Rust has two failure kinds (RuntimeError and an AttributeError from `check_protocol`), reported as 4 distinct failures, and the control has only the RuntimeError. So the control isn't an exact match. It shows Python shrinking its one failure well inside the guard, not the same work.

**Limits.** A Python signal handler only runs in Python code, so a stack can't show time spent in Rust; the longest-example column is the check on that. Rust with the audit off took 9 to 23 s where Python took 3 to 15 s on an unquiet machine. That doesn't explain the guard, and it isn't a speed result either way.

## "Needs internals": resolved test by test
All 77 raise in `tests/`, none in `satassume/` or `harness/`, and all pass on Python.

| Handoff mismatch | Finding | Verdict |
|---|---|---|
| `test_verify_integration.py:95` | Reads `solver._trail_lim`, then `_held`, `_backtrack`, on `sess.solver`. It gets the solver from the engine, so sa-rust-16's by-name search couldn't list it | In class: listed private attribute |
| `test_writeback_provenance.py:29` | `s.owner = "B"` raises the provenance NotImplementedError | In class: named by the ruling |
| `test_writeback_provenance.py:60` | `s.provenance(1, {})`, same | In class |
| `test_writeback_provenance.py:212` | `sv.owner is BOTTOM` passes, then `_cowner` raises | In class. **Lines 213 to 216 don't run on Rust** |
| `test_lra_integers` on the handoff, none kept | Its private reads are on the theory (`t._int_lits`, `t._lo`), not the solver; `Solver()` use is public. 808 pass on Rust with 1,481 solvers | The handoff's entry was wrong |

So the list is right and the handoff's was incomplete: no real failure was hiding in those 5. **Limit:** a kept test stops at its first private read, so anything after it isn't run on Rust. That includes `test_incremental_matches_fresh` and its family in `test_solver_incremental`, the suite's own differential tests of incremental against fresh. 20 of the 22 kept for a read inside the harness pass with the audit off.
**For the planner:** `_n_conflicts` is a read-only view of public `stats()` in `rust_plugin.py`, which moved 64 tests to Rust. I read it as not a port; it's their ruling.

## Mutants: pass rule as written holds
**Not caught by any column: none.** No mutant is argued equivalent. All 25 boundary mutants (10 to 34) and the 10 solver mutants (0 to 9) are caught. Base rows all read "no". No live cell is a hang.

What the catches rest on:
- **No real-engine column catches 10 of the 25:** 11, 26, 33, 34 (API only); 27, 29, 31 (nested only); 17, 18, 32 (API and nested).
- **The solver mutants 2, 5, 6, 7, 9** are caught by the API fuzzer alone. 5 needs hand-written `fixed 5`, and 7 a hand-set `_cla_inc`.
- **The suite column wasn't run:** `mutate_boundary.py --suite` was optional, so whether the suite itself catches callback bugs isn't known.

Full cells: `step4-mutants-api.md`, `step4-mutants-nested.md`, `step4-mutants-live.md`. Solver mutants' scores are step 3's sweep, carried because the crate is unchanged.

### Boundary mutants, step 4

c: caught. API columns are the fuzzer: digest and state on step 1's corpus, then answers and state on fuzz sessions. Live columns are the real engine.

| # | mutant | API digest | API state | API fuzz answers | API fuzz state | nested | live dev answers | live fuzz answers | live dev state | live fuzz state | columns catching |
|---|---|---|---|---|---|---|---|---|---|---|---:|
| 10 | batch flush: pending trail reaches theories newest first | no | no | c | c | c | no | no | c | c | 5 |
| 11 | batch: add_clauses in reverse | c | c | c | c | no | no | no | no | no | 4 |
| 12 | batch: add_internal clauses in reverse | no | c | c | c | no | no | no | c | c | 5 |
| 13 | callback order: check, last theory first | no | no | c | c | c | no | no | c | c | 5 |
| 14 | callback order: push_level, last theory first | no | no | c | c | c | no | no | c | c | 5 |
| 15 | callback order: pop_level, last theory first | no | no | no | c | c | no | no | c | c | 4 |
| 16 | callback order: propagate, last theory first | no | no | c | c | c | no | no | c | c | 5 |
| 17 | callback order: decide, last theory first | no | no | no | c | c | no | no | no | no | 2 |
| 18 | callback order: a shared variable's theories, last first | no | no | c | c | c | no | no | no | no | 3 |
| 19 | dropped: assert_lit's conflict | no | no | c | c | c | c | c | c | c | 7 |
| 20 | dropped: check's conflict | no | no | c | c | c | no | c | c | c | 6 |
| 21 | dropped: check's model | no | no | c | c | c | no | no | c | c | 5 |
| 22 | dropped: propagate's first pair | no | no | c | c | c | no | no | c | c | 5 |
| 23 | dropped: decide's answer | no | no | c | c | no | no | no | c | c | 4 |
| 24 | dropped: register_atom never reaches the theory | no | no | c | c | c | c | c | c | c | 7 |
| 25 | dropped: pop_level never reaches the theory | no | no | c | c | c | c | c | c | c | 7 |
| 26 | dropped: assert_lit's exception | no | no | c | c | no | no | no | no | no | 2 |
| 27 | conflict_of: any falsy first item, not `is False` | no | no | no | no | c | no | no | no | no | 1 |
| 28 | hook_lits: a theory's clause reversed | no | no | c | c | c | no | no | c | c | 5 |
| 29 | stale handle: check goes to the process's latest theory at that place | no | no | no | no | c | no | no | no | no | 1 |
| 30 | stale handle: a variable keeps the process's first payload | no | no | no | no | c | c | c | c | c | 5 |
| 31 | lifetime: __traverse__ misses the theory, so a cycle never frees | no | no | no | no | c | no | no | no | no | 1 |
| 32 | theory_models: reversed | no | no | c | c | c | no | no | no | no | 3 |
| 33 | run: a solver fault raises ValueError, not RuntimeError | no | no | c | c | no | no | no | no | no | 2 |
| 34 | model: an unassigned variable reads False | no | no | c | c | no | no | no | no | no | 2 |

Not caught by any column: none. Not caught by a live column: 11, 17, 18, 26, 27, 29, 31, 32, 33, 34 (10 of 25).

### The 10 solver mutants, step 3's sweep on the same crate

| # | mutant | dev digest | fuzz digest | dev state | fuzz state | API answers | API state |
|---|---|---|---|---|---|---|---|
| 0 | level sort: ties flip | no | no | 49 streams, first q348 | 1,603 streams, first q0 | caught | caught |
| 1 | explain: last best wins | no | no | 6 streams, first q364 | 300 streams, first q9 | caught | caught |
| 2 | `_mention` order | no | no | no | no | no | caught |
| 3 | no var_inc decay | no | no | 133 streams, first q278 | 2,573 streams, first q0 | caught | caught |
| 4 | watch: blocker-style keep | no | no | 321 streams, first q0 | 2,739 streams, first q0 | caught | caught |
| 5 | ring: None as false | no | no | no | no | caught, `fixed 5` only | caught, `fixed 5` only |
| 6 | `_fill` growth | no | no | no | no | caught | caught |
| 7 | `_learn` bump order | no | no | no | no | no | caught, hand-set `_cla_inc` |
| 8 | decisions not counted on -1 | no | no | 876 streams, first q0 | 2,913 streams, first q0 | caught | caught |
| 9 | theory unit reason as learnt | no | no | no | no | no | caught |

### Mutants 27, 29, 30, 31: read for their reason, nested column
Live columns: 27, 29, 31 are "no" in all four; 30 is caught in all four (193 dev and 2,588 fuzz answers).

`step4-mutants-nested.md`, 500 seeds, base row "no" (278 nested-in-hook sessions). Each was read for its reason:

| # | Caught by | First difference |
|---|---|---|
| 27 | `odd`, seed 5 | Python goes on to `prop`; the mutant raises RuntimeError from `solve`. **Only on the constructed `(0, model)` input**; `odd` was written to reach it |
| 29 | `in-check`, seed 1 | `outer.a check` goes to `inner.a` |
| 30 | `in-check`, seed 1 | payload `outer.b.5` arrives as `outer.a.5` |
| 31 | `in-check`, seed 1 | 0 alive after drop on Python, 6 on the mutant |

With the API columns, all 25 boundary mutants (10 to 34) are now caught by at least one column. Not caught by nested, all caught by API: 11, 12, 23, 26, 33, 34. Batch flush order: the crate has no batching layer, so 10 to 12 mutate the batches it has.

## Reach, suite on the probe build
| Path | Suite hits | With theories | Tests |
|---|---:|---:|---:|
| restart | 22 | 9 | 8 |
| `reduce_db` | 11 | 4 | 3 |
| mutant 2, 2+ pending blocks | 1,571 | 80 | 94 |
| mutants 5, 6, 7, 9 | **0** | 0 | 0 |

The audit-off-2 run on the theory files added nothing for 5, 6, 7, 9. **Those 4 paths rest on the API fuzzer alone**, with stub theories. Kept tests stop early on Rust, so they may reach these paths on Python only.

## B to E
None occurred: no panic in the run 5 or probe logs, and none in any failure's text. Unfixed.

## History: all rows match
**14 of 14 pairs finished with 0 differing.** Full output, with the runs 1 to 4 tables: `step4-history.md`.

| run | wl | queries Py/Rust | answers differ | msgs differ | sessions | end state differ | stream differ | session count differ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| recorded | dev | 1985/1985 | 0 | 0 | 918 | 0 | 0 | 0 |
| recorded | fuzz | 3000/3000 | 0 | 0 | 3133 | 0 | 0 | 0 |
| shuffle1 | dev | 1985/1985 | 0 | 0 | 912 | 0 | 0 | 0 |
| shuffle1 | fuzz | 3000/3000 | 0 | 0 | 3142 | 0 | 0 | 0 |
| shuffle2 | dev | 1985/1985 | 0 | 0 | 914 | 0 | 0 | 0 |
| shuffle2 | fuzz | 3000/3000 | 0 | 0 | 3141 | 0 | 0 | 0 |
| fork | dev | 1985/1985 | 0 | 0 | 3332 | 0 | 0 | 0 |
| fork | fuzz | 3000/3000 | 0 | 0 | 4943 | 0 | 0 | 0 |
| twice | dev | 3970/3970 | 0 | 0 | 918 | 0 | 0 | 0 |
| twice | fuzz | 6000/6000 | 0 | 0 | 3133 | 0 | 0 | 0 |
| seed1 | dev | 1985/1985 | 0 | 0 | 918 | 0 | 0 | 0 |
| seed1 | fuzz | 3000/3000 | 0 | 0 | 3133 | 0 | 0 | 0 |
| seed2 | dev | 1985/1985 | 0 | 0 | 918 | 0 | 0 | 0 |
| seed2 | fuzz | 3000/3000 | 0 | 0 | 3133 | 0 | 0 | 0 |

**Against itself (what history moves).** In all 10 rows against recorded order, answers moved 0 on both backends, and state moved by the same count on both:

| run | wl | state moved, each backend |
|---|---|---:|
| shuffle1 | dev | 335 |
| shuffle1 | fuzz | 86 |
| shuffle2 | dev | 358 |
| shuffle2 | fuzz | 91 |
| fork | dev | 1549 |
| fork | fuzz | 2981 |
| seed1 | dev | 27 |
| seed1 | fuzz | 131 |
| seed2 | dev | 19 |
| seed2 | fuzz | 225 |

- **Query 873:** its state moves with order on both backends (both shuffles), as the plan requires.
- **Run 3, the same query twice:** the repeat's answer differs 0 times on both backends, of 1,985 dev and 3,000 fuzz queries.
- **Answer digests:** dev `31cd0945c07f02a6` and fuzz `173502b6ef285ad6` in all 12 runs of each.
- **`test_history.py`, shuffled:** 135 passed, 15 skipped, 1 xfailed on both; 4,253 Rust solvers.
- **Re-entry and entry raises in the Rust runs:** 0. Python solvers made: 0.

## Harness presets, run 5: identical
`harness_rust.py fuzz --seeds 0-3 --config all`, both backends with engine and reference patched: 13 configs by 4 seeds, 1,500 queries each, 78,000 in all.

| | Rust | Python |
|---|---:|---:|
| Mismatches | 0 | 0 |
| Mismatch groups | 0 | 0 |
| Reference instability | 0 | 0 |
| Solvers made, own backend | 165,352 | 165,352 |
| Solvers made, other backend | 0 | 0 |
| Exit code | 0 | 0 |

Comparing all 52 result rows field by field, the only field that differs is `seconds`, so outcomes, pairs and kinds are equal. Rust's solvers gone: 165,352 of 165,352. `--confirm` and `hashseed` weren't used, since their subprocesses don't get the patch.

## Run 6: measured
**Dropped against created, Rust, `--check raw`: 918 of 918 on dev, 3,133 of 3,133 on fuzz** (`run6_counts.sh`, so sha 44577e02, digests as above). This is the same figure step 3 had.
- **What the count is:** `backend.py` counts a `weakref.finalize` on the Python object, so it shows Python released the solver, and not directly that the Rust side was freed. `boundary.py` separately finds 0 solvers or theories alive after drop on the unmutated build.
- **Not this count:** `traced_dropped` reads 0 in the same totals because raw mode's counter has no finalizer, and `historycmp.py`'s `0/0` column isn't a count because those counters run only under `--check raw`.
- **Grep:** no `static` or `thread_local` in the crate. The 3 `'static` are lifetimes: `solver.rs:2318` (`dump`'s names), `lib.rs:24` (`py()`), `lib.rs:89` (`PyProps`).
