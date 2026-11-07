# Component 4, slice A: conversion on the real engine path (issue 323)

**Tested source `3fab435`, on `rust-slice` 60493d6 (1b, on realroots), on pareto1 (x86-64). Landed as the commit that adds this report, whose only change from the tested source is this file.** Output: `/home/tilo/sa-rust-ids-work/sa-port-60/l1` on pareto1, read copies in `~/sa-rust-ids-work/sa-port-60/a` on orion. **Modules that now run whole because of this: 0 of 32**, as the planner expected. The keys consumer asks Rust and drops the value, so every answer still comes from Python's path.

**Incoming diff, 4b2f12b to 60493d6:** 41 files, +6,142 / -842. Realroots and 1b, including `knowledge_live.py`, `lib.rs`, `lra_backend.py`, `lra.rs`, `lra_py.rs`, `constfield.rs` and `lra_cert.rs`, and 0 lines in `satassume/` or `tests/`. It changes code the run executes, so everything below was rerun on the rebased source. The earlier run on `56bc4e1` (sa-port-55, on 4b2f12b) isn't quoted as evidence.

**Base for the suite: 1b's landing rows,** `pareto1:~/sp51/out/land/suite-rust`, as they changed from `port-census/pr328-check/suite-rust` by 1 test, named below.

## What it does

- A per-query table at `_ask` (`term_live.py`), with the Kept route: a kept query stays wholly on Python.
- A refusal reaches the top of the run. `TermRefuse` is a `BaseException` now, so none of the 7 `except Exception` handlers on the path can catch it: `engine.py:1906`, `sympy_api.py:1107`, `relations.py:1989`, `:2011`, `:2018`, `lra.py:461`, `lra_bounds.py:249`. Inventory line 373 said 2. **Since 1b, the sixth on Rust's solver is `lra.rs:935-936`,** because the core runs the certificate and `LRATheory._certify` is never called there. It's written to let a BaseException up, and `test_term_live.py` now plants there.
- A discarded run is rolled back (`_Mark`), then the query answers on Python.

## The bar

| # | Item | Result |
|---|---|---|
| 1 | Suite by id, Rust solver, EUF and LRA, `-n 8` | **5,960 / 77 / 46, plus 1 failure from 1b, below.** 124 failed, 23 skipped, 18 xfailed. 6,125 ids, none added or gone, **0 outcomes changed** against 1b's rows. Run twice on this source: 0 outcomes differ between the runs |
| 2 | Fresh dev 1,985 and fuzz 3,000: answers and state | **MATCH.** Python against Rust, and each against a keys run and a discard run: 0 answers, 0 digests, 0 session counts differ. Live: 8 of 8 MATCH, digests 31cd0945c07f02a6 and 173502b6ef285ad6 |
| 3 | Planted bugs through that comparison | **Caught, two ways, below** |
| 4 | Quiet firings on Rust, that suite run | **39 rows, 2 tests, both already named**, below. 0 findings. Same rows in the second run |
| 5 | Known differences | None in answers or read state on these comparisons. Limits below |

**The 1 failure:** `tests/test_lra_exhaustion.py::test_split_beyond_the_certificate_bound_counts_as_exhausted`, passed in `pr328-check/suite-rust`, failed in 1b's rows and here. `port-1b.md` gives its cause: it patches `LRATheory._certificate`, and the Rust core doesn't read that attribute. This slice didn't change it.

### Planted bugs

- **No rollback, `--no-rollback`, dev:** state left on 1,985 of 1,985, 45 kinds; 494 digests and 494 session counts differ; **0 answers differ.** So the state check catches this and answers alone wouldn't.
- **Solver mutant 0, live, dev:** DIFFERS: 47 ends, 49 streams, 19 LRA states, first q348. 0 answers differ. Answer digest unchanged. The unmutated column on the same source reads MATCH. Fuzz not run for this mutant.

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

**Passed, split per the planner's rule: 5,959 with no firing, 1 with a firing on Rust,** of 5,960. Python's counter wasn't run on this source, so "doesn't fire on Python" for that 1 comes from earlier reports.

The counter fires first: `quiet_fire.py` on this source plants an `Exception` at `engine.py:1906` (`_complete_check`, `s.assumption_lits`) and `sympy_api.py:1107` (`_formula`, `eng.verdict`), and `handler_count` sees 1 at each. `lazy_fire.py` plants a `TermRefuse` at the same places: it comes through, and the counter stays 0. Fresh dev and fuzz: 0 rows.

**`handler_count` covers 2 of the 7 handlers.** `TermRefuse` can't be caught at the other 5 (`test_term_live.py`'s `HANDLERS` reaches each with a plant), but an ordinary Rust `Exception` there would be quiet and isn't counted. That includes `lra.rs:936`: `test_the_core_certificate_handler_is_quiet_on_an_exception` shows an `Exception` from `pi_laurent` doesn't come out, so a Rust bug in the certificate would read as "not certified". **So 0 firings can't be claimed for those 5.**

## Real refusals and reads

| Workload | `converted` | Kept | Refused | `read_raised` | `read_term_missing` | `key:asked` | `key:not-input` | `read:key` |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| dev | 1,935 | out-of-scope 50 | 0 | 0 | 0 | 5,967 | 850 | 499 |
| fuzz | 3,000 | 0 | 0 | 0 | 0 | 154,309 | 18,627 | 12,158 |
| suite | 34,727 | out-of-scope 2,468, non-default registry 184, Sum/Product/Integral 42 | 0 | 0 | 0 | 377,269 | 67,588 | 88,198 |
| suite, second run | 34,723 | the same, plus args-eq-not-is 5 | 0 | 0 | 0 | 379,437 | 66,849 | 88,103 |

**The suite's counts move between runs of one source,** with the same 6,125 outcomes: `args-eq-not-is` is 0 and 5 here, and was 4 on `56bc4e1`. It's the Kept route at `convert.py:208`, which tests whether equal args are the same object, so I read that as depending on what SymPy's cache holds in each worker, and on how tests fall to workers. That's a reading, not a test of the cause. So the Kept route isn't stable per query across a suite run. A kept query answers on Python, so this can't move an answer today. Whichever slice first consumes the table should know its Rust coverage has this noise.

**The 0 refusals are weak evidence, and the refusal path has run on plants only.** The consumer asks Rust's key only for input terms: `key:not-input` returns without asking. So derived terms, including `Mul(*factors)` products at the LRA sort sites, don't reach Rust's key on this path; only the shadow compares those (`bad` empty on dev and fuzz: 183,980 and 757,774 compares, 4,919 and 27,647 derived keys). The shadow wasn't run on the suite on this source.

**Exp-factor product refusals (planner's follow-up): 0 on all three, and that doesn't answer the question.** Hand-built `x*exp(y)` queries, as input terms and in assumptions, didn't refuse either. Slice B is where this count starts to mean something.

`read_raised` and `read_term_missing` read 0 here, and each is shown firing by a plant in `test_term_live.py`. Those counts for the suite are new: `rust_plugin.py` writes `term.PID.json` per worker.

## Tests

- Slice tests that touch this: 138 passed, 6 skipped (`test_term_live.py`, `test_lazy_reads.py`, `test_knowledge_lazy.py`, `test_knowledge_common.py`, `test_knowledge_realroots.py`). `test_term_live.py` on Rust's solver: 19 passed; on Python's: 18 passed, 1 skipped (the core's handler). `test_handler_count.py` with its plugin: 2 passed. `lazy_fire.py` and `quiet_fire.py`: rc=0.
- `test_term_live.py`: the 7 handlers, each with a plant shown reached; nested; second run; a Python theory's hook on the Rust solver; `read_raised` and `read_term_missing` to the top; 3 on rollback; a constant index a rollback frees.

## Merge findings

- **On 1b and realroots, a real one:** realroots' wrapper in `knowledge_live.py` called `_stack()`, which this branch moved to `term_live`. The text merge was clean there. I found this reading the merge and fixed it before running anything, so I didn't see it raise. By reading, it's a `NameError` on the first realroots call under `install()`, outside the wrapper's `try`, so a handler on the path could have made it a quiet "unknown". It reads `term_live.current()` now. `test_knowledge_realroots.py`, which is realroots' test, needed 2 lines changed for the move, and its `test_a_kept_query_stays_on_python` now covers that branch. That file wasn't in the job's list; it is now. **Neither `knowledge_live` nor realroots is installed in the suite or the fresh columns, so those runs say nothing about this; only the unit tests do.**
- **On 1b, a stale test row:** the `lra.py:461` row failed on Rust, never reached. See "What it does".
- **On `_common`, from sa-port-55:** with `TermRefuse` a `BaseException`, `py.rs`'s non-bool `const_value` would have gone past `_common`'s `KnowledgeFault` and been answered on Python. It's a `TypeError` now, so it stays a fault, and sa-port-48's test passes unedited.

## What a discard does to a constant

The open point from before 1b. A rollback truncates `_CONSTANTS`, so the next registration reuses the index, and `constfield.rs`'s `ENCLOSURES` is keyed by that index. Rust reads the constant live and checks the stored tuple is the object in that constant's `_cache`, so the old constant's enclosure isn't used. `test_a_constant_index_a_discard_frees_can_go_to_another` runs this on both solvers: `log(37)`, rollback, then `log(5)/2` at the same index.

**The test is shown to catch it:** with `ENCLOSURES`' identity check removed, it fails with `False is None`. My first version passed under that plant, because its stale value didn't move the answer, so I changed the constant.

## Limits

- **Rollback:** overwrites of an existing memo key and in-place changes to non-container values aren't rolled back; the state check sees the first and copies one level for the second. A run that re-adds the same key object at the same position isn't detected by `_Mark`. SymPy's caches, `_assumptions` and `Dummy._count` are also outside it.
- **`_CONSTANTS` and `_BY_KEY`** are truncated from outside, and `harness/state.py:262` says live objects refer to entries by index. The section above checks `ENCLOSURES` and one reuse. It doesn't walk for anything else holding a freed index, such as a memo entry overwritten during the run (see Rollback). In the discard columns the second run re-registers the same constants, so a freed index is rarely reused by a different one there; their clean result says little about this.
- **Nesting:** a nested `_ask` converts its own table, though section 5 says the table belongs to the top-level query. `Engine.is_` and `Engine.ask` called directly have no table, so they can't refuse.

## Standing, as the planner ruled

- **S's gate is met except for the 46 named stub failures, one cause.** They stay in number 3, and the crate is unchanged for them.
- The `_n_conflicts` view in `rust_plugin.py` isn't a port. It's a test-plugin shim, with the 64 tests it moved.
- Mutants 2, 5, 6, 7, 9 rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- `test_performance_smoke_300_vars` passed here, in both runs.
- **Files outside the slice:** `knowledge_live.py`, `knowledge_quiet.py`, `lazy_fire.py`, `live.py`, `rust_plugin.py`, `term_shadow.py`, `fresh.py`, `test_knowledge_lazy.py`, `test_knowledge_realroots.py`, `solver_rs/src/term/py.rs`, and the inventory. No heuristic added or changed. `lra_backend.py` and `constfield` are unchanged, and 0 lines in `satassume/` or `tests/`.

## Not run

Moved to "before any backend PR" by the landing bar: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the boundary rescore and suite column; the final drop score and its lost rows; the suite split with Python's counter; `order:_rows`' evidence (not caught meanwhile); the `_forms` guard test; history and seed reruns; forced moves; the native path; timing.

Also not run: a Python-side suite on this source, mutant 0 on fuzz, the shadow on the suite, and a counter on `lra.rs:936`.

## Reference

- Slice B is next, by the planner's order, and D's condition is met now that 1b is on. `term_live.py`'s `_key_consumer` is where its first consumer goes. No next brief is written, as this is a done report and not a handoff.
- Evaluator: not asked for.
