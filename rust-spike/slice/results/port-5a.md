# Component 5, step 5a: landing report (issue 323)

Tested source 55cb00d, on `rust-slice` d29e94b, x86-64, pareto0, .so db2e4182250f. `rust-slice` isn't reachable by any user and Python stays the default.

5a ports `compile.py`'s `VarTable` and `compile_formula`, and `Session`'s variable and clause surface, to `solver_rs/src/compile.rs` and `session.rs`, keyed on session-local ids. Python's `Session` shell, `Relations` and templates call it through a pyclass. 5b and 5c aren't started.

## A1 and A2, the evaluator's holds
- **A1:** after `table.node_base(slot)`, `s.var(pred, passed)` visited `slot` on Rust and `passed` on Python. Fixed: `var`, `dvar` and `_dvar` pass the caller's object down to the visit. This departs from sa-port-82's design, a visit before the call, because `_dvar` reads its memo first and a visit ahead of that read would change numbering. A formula's second object now refuses whenever the node has no visit.
- **A2:** a custom atom's expr came from the node's object, so an `Args` could read as a `Tuple` and miss a 2-argument handler. Fixed: each custom atom keeps its own expr. This ends the `mine(1.0)` / `mine(True)` named difference.
- **Object rule (`results/port-1a.md`):** the slot keeps the first object, the visit takes the one passed, and a custom atom keeps the first to reach `table.var`. `test_session_limits.py` pins each in both orders.
- **Through `ask`:** 28 A1 and 10 A2 queries, each on a fresh engine, gave the same answers and the same visits as Python. **Neither reached the changed path:** `second:visit` 0 and `join` 0, so the probe shows no answer moving but not that one can't. By the ruling, the direct tests stay and it lands.
- **Residual, read and not driven:** a template passing a second object in the middle of a compile with `dv`. My direct probe made no visits, so it says nothing. By reading, `engine.py:944` and `:1159` visit the atoms first, and `:684` and `:732` pass no `dv`. The `a1:reenter` cases take the `_ensure_atoms` path, so they don't exercise this.

## The bar
1. **Suite, `-n 8`:** 5,960 passed, 124 failed, 23 skipped, 18 xfailed; 6,125 ids. Against `suite-cea574c`: 0 new, 0 gone, 0 changed. Against `pr328-check/suite-rust`: 0 new, 0 gone, 1 changed, the known `test_split_beyond_the_certificate_bound_counts_as_exhausted`. `test_performance_smoke_300_vars` passed.
   Against `pr328-check/suite-python`, by `suite_report.py`: 5,960 ran on Rust and passed, 77 kept on Python as needs internals, 46 failed on Rust from re-entry, plus 1 other that passes on Python, the test named above. 0 Python solvers in the Rust run.
2. **Dev and fuzz:** all 8 comparisons MATCH. Dev digest 31cd0945c07f02a6, 1,985 queries, 918 Python sessions and 0 Python solvers on Rust. Fuzz 3,000 queries. Handlers empty on both.
3. **Plants** (`--so`; `limits` is `test_session_limits.py`, 242 tests, 242 passed unplanted):

| plant | dev | fuzz | limits |
|---|---|---|---|
| `c198-and`, compile.rs | 1,269 logged, DIFFER, end 708, stream 713, answers 0 | 4,430, DIFFER, end 2,395, stream 2,398, answers 0 | 55 fail |
| `s425-have`, session.rs | 1,694, DIFFER, end 172, stream 173, answers 0 | 65,376, DIFFER, end 2,945, stream 2,945, answers 0 | 13 fail |
| `a1-slot`, undoes A1 | 0, MATCH | 0, MATCH | 15 fail |
| `a2-objs`, undoes A2 | 3,258 logged, MATCH | 85,348 logged, MATCH | 11 fail |

   **Only the limits file catches A1 and A2**; dev, fuzz and the `ask` probe don't. `a2-objs` logs every read, changed or not, so its count isn't a count of moved objects.
4. **Handlers, suite:** 39 rows in 2 tests. `test_ci_stream_reports_only_what_replays` passed: `_consistent` AttributeError, `_ok` 34, `_rb_clauses` 4. `test_protocol_on_fuzz` failed: `_build_context` "Already mutably borrowed" 1, the 46-stub cause. So 5,959 passed with no firing, 1 with. Control on this source: 4 passed, 6 rows; live dev `--limit 60`: formula 1, complete_check 13, assumption_lits 46, verdict 1.
5. **Known differences:** see below. No answer or read-state difference on these workloads.

## Crossings

| | dev | fuzz | suite |
|---|--:|--:|--:|
| `refuse:object` | 17 | 30 | 3,676 in 188 tests |
| `join` | 0 | 0 | 769 in 18 tests |
| `refuse:depth`, `refuse:convert` | 0 | 0 | 0 |
| `second:visit` | 0 | 0 | 0 |
| `custom:own` | 826 | 22,139 | 221,159 in 860 tests |
| `py:compile` | 833 | 2,952 | 38,655 |
| `py:dvar` | 21 | 120 | 585,852 |
| `py:literal` | 44 | 1,957 | 24,724 |
| `py:var` | 4,032 | 134,774 | 910,320 |
| `py:node` | 14,769 | 177,962 | 5,276,751 |
| `py:table` | 32,783 | 574,631 | 10,207,036 |
| `rs:visit` | 2,482 | 16,537 | 1,001,212 |
| `rs:add_clause` | 2,696 | 60,597 | 2,813,217 |
| `rs:emit_callback` | 2,568 | 8,703 | 265,401 |
| `rs:ensure_vars` | 886 | 19,336 | 542,537 |
| `rs:def_implications` | 0 | 0 | 825 in 49 tests |
| `rs:neg_shared` | 0 | 0 | 38,665 in 96 tests |

- **Counters fire:** `second:visit` 36 and `custom:own` 67 on the limits file, so their zeros and counts aren't false.
- **`custom:own`** counts reads of a custom atom whose kept expr isn't the node's object. What those objects are wasn't traced. In the `ask` probe it fired 32 times with `join` 0, so there they aren't objects of different classes.
- **`join`** went from 53 in 12 tests on 77d04e3 to 769 in 18. Sa-port-81 found it depends on order, `f(x)` with `f(x)` over different `Function('f')` classes, with earlier runs of 76 and 1,025. `test_relevance.py` and `test_transfer_fuzz.py` do use `Function`. **This run didn't log the joins**, and `test_p7_review_fixed_invariant_repros_replay.py`'s 28 aren't shown to be that shape.
- **`refuse:object`'s cost, speed and not answers:** 3,676 of 38,655 compile calls. Dev and fuzz are unchanged by the wider rule; the suite moved in 10 tests, both ways, mostly fuzz tests, which I haven't separated from run-to-run variation. `rs:emit_callback` is 265,401 against 3,133,410 at cea574c. `py:dvar` being new on dev and fuzz probably comes from the same refusals, not traced.

## From the earlier steps
- **`_link`:** "no comparison reaches it" holds for dev and fuzz only; the limits file catches `s466-impl` (sa-port-82: 34 fail). **Same shape, new gap:** neither dev nor fuzz reaches `compile`'s `Or` arm, which `Implies` also uses. The limits file and the suite do (`c204-or` on 77d04e3: 20 and 229 fail). Neither plant was rerun here.
- **PR 334's tie:** 0 fires on dev, fuzz and suite on cea574c, so the tie was never reached. `compile.py` takes `(abs(l), l)`, as `compile.rs` does.
- **`var-off`, still unexplained:** all 9 predicates `_var` sees fired and DIFFER on both workloads. A predicate outside them, such as `positive`, would fire 0 and MATCH: a candidate, not shown, since the original was never committed.
- **`compile.py` can't count whole:** `ref.py` imports it, `engine.py:2211` calls `basis_formula`, `session_live` passes `_Lit`, and every `refuse:*` runs Python's compiler by design. `ref.py` follows the inventory, not on the query path.

## Changed outside the component
- `rust_plugin.py`, 5 lines against d29e94b: 3 for session crossings per suite row, 2 to install the session.
- `satassume/knowledge/compile.py`, 1 line: PR 334's key.
- `run_live.sh`, 1 line: the rust column reports session reach and handlers.

## Named differences, as A2 leaves them
1. Ended: `mine(1.0)` against `mine(True)`.
2. Non-string predicates `==` across classes, on different nodes: `1(c)` against `True(c)`, shown form only.
3. Within a few frames of Python's recursion limit the two differ, by ruling not reproduced. `test_threshold_is_near_pythons` asserts within 5 frames and more than 3*64.
4. Not tested: a caller already within about 3*64 frames of the limit with a formula at or under depth 64. Backend PR list.

## Backend PR list
B1 to B10 in `~/sa-rust-ids-work/sa-port-83/verdict.txt`, including B3: `table.slots` past the end panics on Rust where Python raises `IndexError` (`sync_transfer` stays in range). Also the re-entry contract: re-entering the solver from a hook is allowed on Python and raises on Rust, and through `_build_context` it becomes a quiet unknown.

## Standing statements
- S's gate is met except for the 46 named stub failures, one cause.
- The `_n_conflicts` view in `rust_plugin.py` isn't a port. It's a test-plugin shim, with the 64 tests it moved.
- A public-API `test_incremental_matches_fresh` family is due by the engine port, at the latest.

## Not run
History and seed reruns, forced moves, the native path, mutants 2, 5, 6, 7, 9 and mutlive's control, the boundary rescore and suite column, the final drop score, the suite split with Python's counter, `order:_rows`' evidence (not caught meanwhile), the `_forms` guard test. `var-off`, `c204-or` and `s466-impl` weren't rerun on this source. No second evaluator ran on the A1 and A2 fixes.

## Sizing
5b about 4 to 6 sessions, 5c about 4 to 6: sa-port-75's estimate, from source lengths only, nothing tried.

## Speed
**Not measured.** The quiet lease on pareto1 wasn't granted after the 10-minute queue on 7 Nov, 18:50 UTC, blocked by another session's shared lease, `synth-speed-2`, which held about 3 hours more unless released. No number from another machine or an unpinned run stands in for it. To run it from orion: `machine run pareto1 --quiet -r WHY -- bash ~/sp19/job84.sh ~/sp19/timing.sh`, dev and fuzz, Python and Rust alternating, 3 rounds; output in `~/sp19/sa-rust-ids-work/sa-port-84/timing/times.txt`. No target.
