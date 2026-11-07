# Handoff: sa-port-35 to the next session (issue 323), lazy reads

Clone `~/dev/sa-port-5`, branch `port/lazy`, head 12563e2. Output `~/sa-rust-ids-work/sa-port-35/` (`$O`); sa-port-33's jobs are `~/sa-rust-ids-work/sa-port-33/` (`$O33`). Nothing is on `rust-slice`, whose head was ceb6ceb at 11:07 UTC with docs-only changes over this branch's base; refetch, since 2 and 1a may land first. Modules of the 32: 0 added. Read the landing bar first: `~/dev/architect/briefs/addenda/sa-port-landing-bar-ruling.txt`. It moves timing and ruling 6's rerun to "before a backend PR": list them as not run.

## Jobs running, detached (11:53 UTC). Don't wait on a file a stopped run can't write.

| Job | Where | End marker | Read with |
|---|---|---|---|
| **Whole suite, shadow DRIVE**, `-n 6`, pareto1, tree `snap4` (12563e2's source) | `$O/drive/out/` (rsynced at the end; live at pareto1 `~/sp35/out/drive`) | `$O/drive/done.txt` ALL | `read_shadow.py`; `shadow.*.json` counts `convert:read_term_missing`, `convert:read_raised`; `so.*.txt` |
| **The 109 tests the orion shadow hasn't reached**, shadow checks on, pareto1, then the slow test alone under `timeout 600` | `$O/rest/rest`, `$O/rest/rest-slow`; `slow.txt` in `rest` | `$O/rest/done.txt` ALL | `read_shadow.py` |
| **`mul_key` plants on the 11 product-key tests**: base, arg, unsorted, pareto1 | `$O/plant-run/plant-{base,arg,unsorted}`; `ids.txt` | `$O/plant-run/done.txt` ALL | `read_shadow.py`; check `so.*.txt` against the shas below |
| Orion shadow suite, `snap3`, one worker left (pid 4132336, session 4132195) on `test_constants_evalf_cannot_bound_rigorously_are_not_read` since 11:23 | `$O33/suite/shadow` | `exit.txt` | see step 1 |
| Orion Python column of the off suite | `$O33/suite/python` | `$O33/suite/done.txt` ALL | no Python rerun is needed to land; use it for the passed split if it ends |
| `term_history.py` fuzz, corpus | `$O33/hist` | `done.txt` | moved to the backend PR list unless the rebase brings engine changes; dev is clean, below |

Plant shas (pareto1): arg 78b1b4a4, unsorted 02776552, base d8051340. Scripts: `$O/p1/`, tree at pareto1 `~/sp35` (env `~/sp35/env.sh`, venv and SymPy read from `~/sp19`).

## Done, with numbers

- **Bar 1, suite by id (shadow off, `$O33/suite/rust`, `snap2`):** 5,961 / 77 / 46, 23 skipped, 18 xfailed. Against `port-census/pr328-check/suite-rust`: 0 new ids, 0 gone, 0 changed outcomes. No `test_wide_derived.py` failures; `test_performance_smoke_300_vars` passed.
- **Bar 4, handlers, off suite:** 39 firings in 2 tests. Passed split: **5,960 with no firing, 1 with**: `test_ci_stream_reports_only_what_replays`, `_consistent`, AttributeError `_ok` 34, `_rb_clauses` 4 (the named case). One more on a failing test: `tests/test_transfer.py::test_protocol_on_fuzz`, `Engine._build_context`, RuntimeError `Already mutably borrowed`, among the 46 by id and failing on the base too. Python's counter isn't compared (moved by the bar).
- **Bar 2, fresh dev and fuzz (pareto1, `$O/live/out/summary.txt`, tree 6fce2db's source, .so d8051340):** MATCH on all 8 comparisons: py/py control, py/rust, traced/untraced, py traced/rust untraced, each on dev and fuzz. **Limit: in a plain run conversion doesn't run, so this says the tree's engine is unchanged, not that reads are right.**
- **Bar 3, plants:** solver mutant 0 (level sort) on that comparison: dev state caught, 49 streams, first q348, 47 end states; dev answers no; base row no (`$O/live/mutlive-out/table.md`; fuzz columns not run). `mutate_term.py` on dev (`$O/mut/work/results.jsonl`): 31 mutants, 22 caught, 9 no, base no. The 9: neg-keeps-sign, float-not-inherited, mul-unsorted, keep-coeff-minus-one, tuple-length-flipped, custom-content-flipped, class-flag-bit, conv-free-unordered, read-memo-off. dev only, no `--synthetic`. `mul-key-arg-count` caught (derived-key 100, key-used 7), `mul-key-unsorted` caught (derived-key 38, key-used 7). `read-memo-off` isn't visible to the shadow, since values don't change; whether the count test catches it wasn't run.
- **Whole ask under DRIVE:** `Q.positive(y + r)` 0 `complex()`, all reads 0, 1 query converted, 0 bad; the plant fails it. `test_lazy_reads.py` 74 passed, 5 skipped.
- **`lazy_reads.py`:** `with_extra` 0 on dev, corpus, fuzz (3,000 queries, same 3,000). Fuzz: lazy key 12,274, commutative 9,340; Python key 211,535, complex 12,492, power 8,568. Dev and corpus in HANDOFF-sa-port-33.md. Rust read complex, finite, power 0 times in DRIVE on dev and corpus (check fuzz: its summary lists none).
- **Kept and refusals equal the eager tree (`results/port-D0.md`):** dev 50 out-of-scope, 0 refused; fuzz 0, 0; corpus 190 out-of-scope, 18 refused, same reasons. No `too-deep`.
- **History, dev:** s0 against s1, s2, rev, shuf, dirty: 1,985 queries, differ 0.
- **Counts, not timing (`$O/counts/`, orion, snap 6fce2db):** dev constructions py 7,708, conv 104, table 0, rest 7,710; `conv_complex` 0, reads 0, `rest_complex` 207 = `py_complex`. Answers differ 0. Fuzz and corpus files are there; `counts_summary.py` crashes at its last lines on the gone `keys` field. Klass's share and times not run: moved by the bar, as is pareto1's quiet lease, which I stopped trying for.
- **Shadow checks, suite, 6,015 of 6,125 so far:** key rows 94,778: matched 93,209, no-table 849, outside-ask 706, unknown 14, refused 0, mismatch 0. By site `relations._key` 81,340, `lra_adapter` 13,438. **LRA derived Mul: 288 rows, 36 queries, 11 tests, all matched, 0 refused.** Pow-holding: 2 args 62, 3 args 39, 4+ 35, so the rows do reach 2, 3, 4+. Census: 39 queries, 311 calls. `read_term_missing` 0 on 3 workers and in every shadow row. Kept out-of-scope 2,462, non-default-registry 184, sum-product-integral 40, args-eq-not-is 4. Refused are in `shadow.*.json`; 4,233 on one worker, mostly algebra shapes: read them.
- **read_raised (sent to the architect; goes to the planner):** 11 in 5 tests, all from the shadow's forced reads: `test_add_rows::test_a_node_of_one_term_is_that_term` 3, `test_mul_rows::test_a_node_of_one_factor_is_that_factor` 1 (`Basic.__new__` nodes have no `is_commutative`); `test_nan_arguments::test_rereview_r1_reproducers` 4, `test_noncommutative::test_scalar_with_a_matrix_in_a_container_stays_in_scope` 2, `test_invariants::test_ci_stream_no_longer_finds_the_zero_i2_family` 1 (`complex()` TypeError on UnevaluatedExpr(nan), Abs, sign of it, VectorZero, Mod(I, n)). Under DRIVE, on these 5 tests' queries, 0. Script `$O/test/raised.py`, plugin `$O/test/raised_plugin.py`. Check the 11: the `test_mul_rows` 1 is from the fixed tree's rerun.
- **Shadow on against off, so far, 3 differ:** `test_mul_rows::test_a_node_of_one_factor_is_that_factor` (shadow's own str() raising; **fixed in 12563e2, passes under the shadow, only that test rerun**), `test_shared_facts::test_engine_does_not_write_sympy_assumptions` (forced reads write `_assumptions`; expected of checks on, not explained further, compare under DRIVE), `test_constfield::test_eliminations_finish_or_refuse_quickly[pi,E,sqrt2-8]` (wall clock, 10.68 s < 10). Add any from `rest` and DRIVE.
- **Docs:** section 9, `convert.py` header, `TERMS-INTERFACE.md` are done and committed. sa-port-31 needs: `tables['reads']`, values gone from rows, new methods, a lazy key can't add a term, `-oo`, `read_raised`.
- **Suite-only shapes (3 workers):** 2,338 suite shapes, 1,011 on the five workloads, 1,662 suite-only, 50,589 calls. Top ones are input skeletons (`AppliedPredicate(NonIntegerPredicate,Symbol)` 18,430, `Not(And)`, `AppliedUndef(...)`). **`D:` shapes not filtered yet: that's what the ruling asks.** `$O/onoff.py` prints this; shape is one level of class and arg classes.

## What's left, in order

1. **The 39 (architect's item 1).** Merge `$O33/suite/shadow` with `$O/rest/rest` and `rest-slow`; `$O/read_shadow.py DIR` per directory. Report all 39 by id as matched, refused, mismatched; name the other 3 and whether they're in the 110 or the slow test, or say they don't appear (the census is a floor, memos on, and it has no ids). **A mismatch comes to the architect first.** The slow test: forced reads under checks, 30+ min on orion, passes plain. If `slow.txt` shows the timeout, name it as not comparable under checks; then stop the orion worker (`ps -eo pid,sid,cmd | awk '$2==4132195'`, kill by session, naming it in the report), or let it end if nearly done. Its shadow.json won't be written if killed: counts come from `shadow-rows` and `shadow-keys`.
2. **The plant:** `$O/plant-run`: under arg and unsorted, the 11 tests' rows must turn to mismatch, with `so.*.txt` showing the plant loaded. Base must have none.
3. **DRIVE suite:** `read_term_missing` and `read_raised` per the nan ruling items 2, 3; passed and failed by id against off, naming each difference. Say the counter fires (`lazy_fire.py`, `test_a_raising_read_refuses_and_counts`). Any raise under DRIVE where Python doesn't raise goes to the architect with its smallest case.
4. **Suite-only `D:` shapes**, step 3 of HANDOFF-sa-port-33 with all workers.
5. **`results/port-lazy.md`**, then rebase on `origin/rust-slice`. If the rebase brings others' source: rerun suite, live and the plant on the paretos (bar: on the landing source). Push with no force. **Tell the architect the SHA first,** then report.

## The report owes

HANDOFF-sa-port-33.md's "The report owes" list, plus: passed split above; the bar's moved list as not run; the architect's three items; the nan plant's three caveats; "harmless to landing" is my reading, not a result. Its limit: nothing consumes conversion, and DRIVE's whole-suite count didn't exist when I wrote it.

## Traps

- `waitfor.sh` exits 0 at its limit too: read its output or the marker, not the exit.
- `snap` lacks the `bad()` fix. `snap4` has it. Pareto1's `~/sp35/dev` tree is `snap`'s source; `~/sp35/drive` is `snap4`'s.
- Architect, 7 Nov: new suites, mutants and history on pareto0 or pareto1 under `--shared --wait 4h`, not orion. Pareto0's `~/sp19` has no cargo: copy the `.so`. Progress goes to the journal.
- `term_shadow.bad` and friends use `_text` now: use it for any new printing of a term.

## Map (use rg)

| Topic | Where |
|---|---|
| Shadow's text, DRIVE switch | `term_shadow.py` `_text`; `term_shadow_suite.py` `pytest_configure` |
| Readers | `$O/read_shadow.py`, `$O/onoff.py` |
| Loaded build | `so_check.py` |
| Mutants | `mutate_term.py` `M` |
| Reads | `convert.py` `_Walk.read`; `table.rs:337` |
