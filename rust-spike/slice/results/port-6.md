# Port component 6, atoms family: landing report (issue 323)

Tested source 4ff243e, on `rust-slice` 6827bf7, x86-64 on pareto1, hash seed 0. Commits after 4ff243e change only docs. Job output: `~/sa-rust-ids-work/sa-port-44/` (orion and pareto1).

**Modules: 0 of the 32 runtime modules run whole in the real engine because of this.** Partly ported: `templates/atoms.py` (`symbol_units`, `constant_units`; `value_units` stays Python for `functions.py` and `special.py`) and the parts of `_common.py` they need. These run from Rust only under `knowledge_live.install()`, so Python stays the default. If partial modules count, it is 1 of 32.

## The bar

| # | Item | Result |
|---|---|---|
| 1 | Suite by id against `port-census/pr328-check/suite-rust` | **5,961 / 77 / 46**, 23 skipped, 18 xfailed. Base 5,961 / 77 / 46. 6,125 ids, 0 added, 0 gone, **0 outcomes changed** |
| 2 | Fresh dev and fuzz, answers and session digests against plain | **MATCH** for atoms, shadow and discard: dev 1,986 lines, fuzz 3,001. Shadow mismatches 0 |
| 3 | Planted bugs, compared against plain, base row clean | `expand-pos-neg-swap` **caught**: 383 lines differ on dev, all 383 answers. Base row `no` in all three columns |
| 4 | Quiet firings on Rust, that suite run | 2 tests, below. No firing outside the named causes |
| 5 | Known differences | Two, below, each with its cause |

S's gate is met except for the 46 named stub failures, one cause. Passed splits as **5,960 with no firing and 1 with a firing on Rust**. This run has no Python handler rows (the base's Python directory has no handler files), so "not on Python" isn't tested here; the suite split with Python's counter is on the backend PR list. The `_n_conflicts` view in `rust_plugin.py` isn't a port: it stays a test-plugin shim, with the 64 tests it moved.

Other plants, all loaded from their own build:

| Plant | `off`, the real mode | Note |
|---|---|---|
| `conv-const-reversed` | caught: 359 lines, 357 answers | |
| `conv-no-symbol-rows` | caught: 9 lines, 0 answers | Moved state only |
| `atom-row-wrong-id` | crash only | Not a comparison catch |

## Firings

| Test | Outcome | Site, type, text | n | Status |
|---|---|---|---|---|
| `test_invariants::test_ci_stream_reports_only_what_replays` | passed | `_consistent`, AttributeError, no `_ok` | 34 | Named needs-internals case |
| same | passed | `_consistent`, AttributeError, no `_rb_clauses` | 4 | Same |
| `test_transfer::test_protocol_on_fuzz` | failed, one of the 46 | `Engine._build_context`, RuntimeError, "Already mutably borrowed" | 1 | Named cause, `tests/theory_harness.py:242` |

**The borrow firing is on the base too:** the test alone on a clean 6827bf7 gives the same row, and fails in 0.26 s. An earlier run of that check read 0 only because a plugin missing from that tree stopped pytest from starting; that zero was void and is not the result quoted here.

**Smallest case**, `~/sa-rust-ids-work/sa-port-44/borrow/min/test_min_reentry.py`: one variable, one attached theory whose `check` calls `s.nvars()`. Rust raises "Already mutably borrowed"; Python passes. This reproduces the raise at solver level. It does not go through `_build_context`; the test above is the smallest case I ran that fires that handler.

Counters are shown firing: 9 workers, each of the 4 planted raises seen 9 times.

## The earlier new failures

The pre-lazy partial run named 8 failures and one hang. All 9 tests pass here.

| Test | Cause | How that's known |
|---|---|---|
| `test_lra_constants` hang | Eager `complex(t)` in conversion | Conversion no longer calls it; the query takes 0.01 s |
| `test_add_rows::test_a_node_of_one_term_is_that_term`, `test_mul_rows::test_a_node_of_one_factor_is_that_factor` | Eager reads on a node with no `is_commutative` | Those reads are gone from conversion; both pass |
| `test_shared_facts::test_engine_does_not_write_sympy_assumptions` | Conversion's reads wrote `_assumptions` | Passes |
| `test_wide_derived`, 5 tests | **Load, not conversion** | Pre-lazy and new atoms alternated on orion at load about 4, three runs each: 72 of 72 pass on both, about 6 s and 5 s |

`test_performance_smoke_300_vars` passed on Rust and didn't move. It failed on the base's Python row, which this run didn't repeat.

## What changed

- `symbol_units` and `constant_units` read `assumptions0` and `const_value` on the lazy path, when the template visits the term. `Read` gains `Symbol` and `Constant`; `AtomRow`, `read_atoms` and the eager walk are gone.
- `complex-unbounded` is gone. It existed only on this branch.
- `Converted` gains `raised`, a small change to a shared file. `mutate_knowledge.py` links `lra` beside its scratch crates. `knowledge_quiet.py` and the plants follow the new names.
- `test_knowledge_lazy.py`, 7 passed: no atom read in conversion, one read per table, no `complex()` call on a root, a raising read is loud, a `BaseException` comes through as itself. The plant in that file calls the reads by hand to show the count moves; it doesn't restore an eager read in conversion.

## Known differences

1. **A read that raises is loud on Rust.** Python's template would raise an ordinary `Exception`, which a quiet handler can catch. Rust's path raises `KnowledgeFault`, which isn't an `Exception`. That can't hide a wrong answer, but it isn't parity. It never happened on a real read here (next section).
2. **Rust can read a constant where Python wouldn't.** Python's `value_units` calls `const_value` only on a miss in its cross-query unit cache. Rust reads once per table. That can write SymPy's caches on a term Python's run left alone. This comes from reading the code and **isn't measured**: fresh runs clear memos per query, so they can't show it, and session digests don't cover SymPy's caches. `test_engine_does_not_write_sympy_assumptions` passes. History runs would be the place to measure it.

## Owed as first consumer

- **`read_raised` on real reads: 0** on dev, fuzz and the suite. The counter fires on a planted raise in `test_knowledge_lazy.py`. Reads: dev 2,569 symbol and 454 constant; fuzz 5,671 and 3,499; suite 2,504 and 194. Corpus was not run in atoms mode.
- **A discarded run leaves nothing in Python: shown for conversion only.** Discard against plain matches on dev and fuzz, and that compare fires on both plants (`noncomm`, `facts`). Scope: discard mode throws conversion's result away and runs no Rust template. Atoms has no mid-run discard: a failure there is a loud fault, so section 9's path isn't exercised by this component.
- **Recount at `engine.py:1906`: not reached by a real query on dev or fuzz**, for templates, `units` or conversion, so no real catch there can be claimed either way. At `sympy_api.py:1107`, a planted raise on the first reaching query escaped as `KnowledgeFault` with the counter at 0 (template: dev query 5, fuzz query 7; `units`: fuzz query 111). `units` on dev and conversion on either workload didn't reach that site. Forced nests at both sites escaped, counter 0. Unplanted handler rows in the scans: 0. Each counter saw 1 on its planted raise in `quiet_fire`.
- **"mul: class has its own as_base_exp", for the follow-up list: 0 queries** on dev (1,985), fuzz (3,000) and corpus (2,863), under the shadow's DRIVE. That report does record refusals (corpus has 8, all other algebra reasons), but this particular reason isn't shown firing, so treat it as a floor. The suite, battery and stream weren't counted. Atoms itself asks for no key, so this component can't produce that refusal.

## Reach is thin

Suite: 34,736 queries converted, but only 2,504 symbol and 194 constant reads. Derived atoms still read their facts in Python (`constant:derived`: suite 8, dev 27, fuzz 652), and Rust computes the units. Templates outside a query or on a kept query run on Python: `py:no-query` plus `py:kept` is suite 1,268, dev 38, fuzz 2. So a MATCH here says more about dev and fuzz than about the suite.

## A test that's flaky on the base

`test_lazy_reads.py::test_stock_term_plant_is_caught[finite-stock_finite]` fails now and then under `-n 3`: 2 of 9 runs here, 1 of 8 on clean 6827bf7, and it passes alone on both. It's lazy's test, the cause isn't investigated, and I left it unchanged.

## Not run

**Moved to before any backend PR by the bar:** the mutant 2, 5, 6, 7, 9 rerun and mutlive's control (those five rest on the API fuzzer alone); the boundary rescore and suite column (10 of the 25 boundary mutants have no real-engine catch); the final drop score and its lost rows; the suite split with Python's counter; `order:_rows` evidence (not caught meanwhile); the `_forms` guard test; history and seed reruns; forced moves; the native path; timing, including ruling 6's rerun.

**Also not run on this source:**
- Corpus fresh, corpus leak, and shuffled suite order.
- The other planted bugs. Only 4 of the 36 and the base were scored. The earlier 10 that nothing caught weren't rerun or analysed, and pre-lazy plant, leak and history results shouldn't be quoted for this source.
- Queries where the lazy path reads a term Python's run didn't, which is difference 2.
- A public-API `test_incremental_matches_fresh`: due during the engine port, not added.

The `mutate_slice` copied-crate failure and `mutate_live.py --handlers` raising are unchanged; only `mutate_knowledge.py` was fixed.
