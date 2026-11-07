# Component 4, slice A: conversion on the real engine path (issue 323)

Run on `56bc4e1`, which is slice A on `rust-slice` 4b2f12b, on pareto1 (x86-64). Output: `/home/tilo/sa-rust-ids-work/sa-port-55/m1` on pareto1, suite rows copied to `~/sa-rust-ids-work/sa-port-55/a/m1/suite` on orion. **Modules that now run whole because of this: 0 of 32**, as the planner expected. The keys consumer asks Rust and drops the value, so every answer still comes from Python's path.

## What it does

- A per-query table at `_ask` (`term_live.py`), with the Kept route: a kept query stays wholly on Python.
- A refusal reaches the top of the run. `TermRefuse` is a `BaseException` now, so none of the 7 `except Exception` handlers on the path can catch it: `engine.py:1906`, `sympy_api.py:1107`, `relations.py:1989`, `:2011`, `:2018`, `lra.py:461`, `lra_bounds.py:249`. Inventory line 373 said 2.
- A discarded run is rolled back (`_Mark`), then the query answers on Python.

## The bar

| # | Item | Result |
|---|---|---|
| 1 | Suite by id, Rust solver, EUF and LRA, `-n 8` | **5,961 / 77 / 46**, 23 skipped, 18 xfailed. Base 5,961 / 77 / 46. 6,125 ids, none added or gone, **0 outcomes changed** against `port-census/pr328-check/suite-rust` |
| 2 | Fresh dev 1,985 and fuzz 3,000: answers and state | **MATCH.** Python against Rust, and each against a keys run and a discard run: 0 answers, 0 digests, 0 session counts differ. Live: 8 of 8 MATCH, digests 31cd0945c07f02a6 and 173502b6ef285ad6 |
| 3 | Planted bugs through that comparison | **Caught, two ways, below** |
| 4 | Quiet firings on Rust, that suite run | **39 rows, 2 tests, both already named**, below. 0 findings |
| 5 | Known differences | None in answers or read state on these comparisons. Limits below |

### Planted bugs

- **No rollback, `--no-rollback`, dev:** state left on 1,985 of 1,985, 45 kinds; 494 digests and 493 session counts differ; **0 answers differ.** So the state check catches this and answers alone wouldn't.
- **Solver mutant 0, live, dev:** DIFFERS: 47 ends, 49 streams, 19 LRA states, first q348. 0 answers differ. Its build was checked by `--so`. The unmutated column on the same source reads MATCH. Fuzz not run for this mutant.

### Discard: a refusal planted in every query

| Column | Checked | Clean | Left | `dummy-count-moved` | `rollback:cleared` | `rollback:restamped` |
|---|---:|---:|---:|---:|---:|---:|
| dev, Python solver | 1,985 | 1,985 | 0 | 0 | 0 | 5,091 |
| dev, Rust solver | 1,985 | 1,985 | 0 | 0 | 0 | 5,091 |
| fuzz, Python solver | 3,000 | 3,000 | 0 | 0 | 0 | 8,667 |
| fuzz, Rust solver | 3,000 | 3,000 | 0 | 0 | 0 | 8,667 |

This is the first consumer's item: a discarded run leaves nothing in Python that the state check reads. Its limits are in "Limits".

### Quiet firings (the recount at `engine.py:1906`)

| Rows | Test | Outcome | Site | Text |
|---:|---|---|---|---|
| 34 | `test_ci_stream_reports_only_what_replays` | passed | `_consistent` | `'Solver' object has no attribute '_ok'` |
| 4 | same | passed | `_consistent` | `'Solver' object has no attribute '_rb_clauses'` |
| 1 | `test_protocol_on_fuzz` | failed | `Engine._build_context` | `Already mutably borrowed` |

The first is the named needs-internals case and the last the named 46-stub cause (`tests/theory_harness.py:242`).

**Passed, split per the planner's rule: 5,960 with no firing, 1 with a firing on Rust.** Python's counter wasn't run on this source, so "doesn't fire on Python" for that 1 comes from earlier reports.

The counter fires first: `quiet_fire.py` on this source plants an `Exception` at `engine.py:1906` (`_complete_check`, `s.assumption_lits`) and `sympy_api.py:1107` (`_formula`, `eng.verdict`), and `handler_count` sees 1 at each. `lazy_fire.py` plants a `TermRefuse` at the same places: it comes through, and the counter stays 0. Fresh dev and fuzz: 0 rows.

**`handler_count` covers 2 of the 7 handlers.** `TermRefuse` can't be caught at the other 5 (`test_term_live.py`'s `HANDLERS` reaches each with a plant), but an ordinary Rust `Exception` there would be quiet and isn't counted.

## Real refusals and reads

| Workload | `converted` | Kept | Refused | `read_raised` | `read_term_missing` | `key:asked` | `key:not-input` | `read:key` |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| dev | 1,935 | out-of-scope 50 | 0 | 0 | 0 | 5,967 | 850 | 499 |
| fuzz | 3,000 | 0 | 0 | 0 | 0 | 154,309 | 18,627 | 12,158 |
| suite | 34,715 | out-of-scope 2,468, non-default registry 184, Sum/Product/Integral 42, args-eq-not-is 4 | 0 | 0 | 0 | 377,974 | 67,842 | 88,167 |

**The 0 refusals are weak evidence, and the refusal path has run on plants only.** The consumer asks Rust's key only for input terms: `key:not-input` returns without asking. So derived terms, including `Mul(*factors)` products at the LRA sort sites, don't reach Rust's key on this path; only the shadow compares those (`bad` empty on dev and fuzz: 183,980 and 757,774 compares, 4,919 and 27,647 derived keys). The shadow wasn't run on the suite on this source.

**Exp-factor product refusals (planner's follow-up): 0 on all three, and that doesn't answer the question.** Hand-built `x*exp(y)` queries, as input terms and in assumptions, didn't refuse either. Slice B is where this count starts to mean something.

`read_raised` and `read_term_missing` read 0 here, and each is shown firing by a plant in `test_term_live.py`. Those counts for the suite are new: `rust_plugin.py` writes `term.PID.json` per worker.

## Tests

- Slice tests that touch this: 124 passed, 5 skipped. `test_term_live.py`: 17 passed on Python's solver and 17 on Rust's. `test_handler_count.py` with its plugin: 2 passed.
- `test_term_live.py`: the 7 handlers, each with a plant shown reached; nested; second run; a Python theory's hook on the Rust solver; `read_raised` and `read_term_missing` to the top; 3 on rollback.

## A merge finding

Rebasing on `_common` broke `test_a_read_that_is_not_a_bool_is_a_fault_not_a_quiet_exception`, which is sa-port-48's. With `TermRefuse` a `BaseException`, `py.rs`'s non-bool `const_value` would have gone past `_common`'s `KnowledgeFault` and been answered on Python. It's a `TypeError` now, so it stays a fault, and that test passes unedited. `knowledge_live.py`'s `kept()` now reads `term_live.current()`.

## Limits

- **Rollback:** overwrites of an existing memo key and in-place changes to non-container values aren't rolled back; the state check sees the first and copies one level for the second. A run that re-adds the same key object at the same position isn't detected by `_Mark`. SymPy's caches, `_assumptions` and `Dummy._count` are also outside it.
- **`_CONSTANTS` and `_BY_KEY`** are truncated from outside, and `harness/state.py:262` says live objects refer to entries by index. Nothing here checked what survives a discard holding one. The Rust discard column shows no difference, which is evidence and not that check.
- **Nesting:** a nested `_ask` converts its own table, though section 5 says the table belongs to the top-level query. `Engine.is_` and `Engine.ask` called directly have no table, so they can't refuse.

## Standing, as the planner ruled

- **S's gate is met except for the 46 named stub failures, one cause.** They stay in number 3, and the crate is unchanged for them.
- The `_n_conflicts` view in `rust_plugin.py` isn't a port. It's a test-plugin shim, with the 64 tests it moved.
- Mutants 2, 5, 6, 7, 9 rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- `test_performance_smoke_300_vars` passed here and in the base.

## Not run

Moved to "before any backend PR" by the landing bar: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the boundary rescore and suite column; the final drop score and its lost rows; the suite split with Python's counter; `order:_rows`' evidence (not caught meanwhile); the `_forms` guard test; history and seed reruns; forced moves; the native path; timing.

Also not run: a Python-side suite on this source, mutant 0 on fuzz, the shadow on the suite.

## Reference

- Slice B is next, by the planner's order. `term_live.py`'s `_key_consumer` is where its first consumer goes.
- Evaluator: not asked for.
