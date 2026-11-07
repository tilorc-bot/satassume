# Component 4, slice D: `lra_adapter.py` and `_from_sympy` through ids (issue 323)

**Tested source `1436a29`, on `rust-slice` ce19962, on pareto0 (x86-64, Python 3.12.14), `.so` sha256 starts a2395bc7301e, built on pareto1. It lands with this report and one harness line in `fresh.py` as the only changes from the tested source; `rust-slice` didn't move, so the incoming diff is empty.** Output: `/home/tilo/sa-rust-ids-work/sa-port-71/l1` on pareto0, read copy on orion, with `s1`, `s2` and `rb` beside it. Base rows: `pareto1:~/sa-rust-ids-work/sa-port-66/l2/suite`.

**Modules that now run whole because of this: 0 of 32.** Neither candidate is whole:

- **`lra_adapter.py`, partial.** `relation` stays conversion, as ruled. `LRAAdapter`, `terms`, `to_constraint` and `_memoized` still run on Python. A kept query, a refused run's second go and a direct `Engine` call run Python's `interpret`, `order_sides`, `integer_form` and `closed_sign`: on the suite, 9,882 `interpret` calls against 630,140 on Rust, and the rest under Reach below.
- **`constfield.py`, partial.** The registry, `Constant`, `Element` at the crossings, `_generic` and R9 `enclose` stay on Python.

## What moved

- `interpret`, `order_sides`, `integer_form`, `closed_sign` and `_from_sympy` answer from `term/lra_read.rs` on a query with a table. `num` is `sa_solver.cf_num` on every path.
- **`_INTERPRETED`:** a call with ids doesn't read it. Each table holds its own memo, which dies with the query. **Cost not measured**, since timing is on the backend list.
- **The closed product (`lra_adapter.py:213`):** this doesn't multiply field elements as section 3 asks. It goes through Rust's `mul`, then `from_sympy`, so no SymPy term is built unless `mul` refuses. When it refuses, Python builds the product, counted as `closed_mul_scaffold`.
- **The registry:** Rust reads `_CONSTANTS` live, the planner's accepted first version. No per-query registry was tried.
- **Sort sites:** Rust's key decides order here, and Python's key isn't computed outside check mode. So "match or refuse" holds through Rust's refusals plus check mode, not through a comparison on every run.

**Shared files touched:** `convert.py` (flag bits 16-18, `exp`), `term/table.rs`, `constfield.rs` (`py_err` pub, `cf_num`, `NUM_PY`), `term/algebra.rs` (`is_rational_kind` `pub(super)`), `lra_backend.py` (`num`), `live.py`, `rust_plugin.py`, `fresh.py`. 0 lines in `satassume/` or `tests/`. **`knowledge_live.py` is untouched, so the `rows_kept` guard ruling doesn't apply.**

## The bar

| # | What | Result |
|---|---|---|
| 1 | Suite by id, Rust, `-n 6` | **5,960 / 77 / 46, plus the 1 failure from 1b.** 124 failed, 23 skipped, 18 xfailed. 6,125 ids, none added or gone, **0 outcomes changed** against the base. Same again with `SLICE_LRA_CHECK=1`, `-n 8` |
| 2 | Fresh dev 1,985 and fuzz 3,000 | **MATCH.** 0 answers, 0 digests, 0 refused. Live: 8 of 8 MATCH |
| 3 | Planted bugs through that comparison | **Caught, 3 of 4 plants**, below. `eq` is caught by check mode only |
| 4 | Quiet firings on Rust, that suite run | **39 rows, 2 tests, both already named.** 0 findings |
| 5 | Known differences | **One, explained:** 16 session lists on the `lra` workload, below |
| Registry | Python with history against Rust | **MATCH, both orders**, below |

**S's standing:** S's gate is met except for the 46 named stub failures, one cause. They stay listed in number 3, and the crate is unchanged for them. The `_n_conflicts` view in `rust_plugin.py` isn't a port: it's a test-plugin shim, with the 64 tests it moved.

**Passed, split per the planner's rule: 5,959 with no firing, 1 with a firing on Rust,** of 5,960. Python's counter wasn't run on this source. `suite_report.py` compared against the older `pr328-check/suite-python` rows, so its "passing on Python 1" isn't from this run: that 1 is unchanged by id from the base. `test_performance_smoke_300_vars` passed here; it's the 1 failure in those Python rows, and I didn't chase it.

## Reach: how often each workload calls this slice

Calls answered by Rust. A MATCH says nothing where the count is 0, and **fuzz reaches none of the closed-term paths.**

| | dev | fuzz | `lra` (new) | suite |
|---|---:|---:|---:|---:|
| `interpret` | 5,848 | 124,642 | 35,342 | 630,140 |
| `order_sides` | 2,901 | 58,982 | 15,709 | 241,411 |
| `integer_form` | 1,194 | 24,134 | 6,972 | 106,986 |
| `closed_sign` | 264 | 597 | 6,944 | 503 |
| keys | 4,055 | 117,684 | 39,215 | 635,992 |
| product terms | 6 | 0 | 8,726 | 1,283 |
| closed product, one factor | 306 | 0 | 7,822 | 3,904 |
| closed product, Rust's `mul` | 0 | 0 | 10,879 | 182 |

Dev and fuzz counts for the first four come from the check column, where they equal the calls because neither refuses. `lra` is `lra_wl.py`, 1,500 queries aimed at the sites dev and fuzz miss. **Its 298 refused queries test the refusal path, not Rust's reading, so subtract them when quoting reach.**

**Calls left on Python, suite:** `interpret` kept 5,794, no-id 86, no-query 4,002. `order_sides` kept 792, no-id 48, no-query 1,520. `integer_form` kept 330, no-query 583. `closed_sign` kept 42, no-query 1,179. `closed_sign` is the one where Python's share is large: 503 on Rust against 1,221 on Python.

## Check mode

Python's function run beside Rust's and compared, **0 differences on all of it:** suite 983,669 comparisons, dev 10,207, fuzz 208,355, `lra` 64,764. The counter fires: `plant-eq` and `plant-sort` each hit the 50 cap on `lra`. On `lra` it compared `closed_sign` 6,942 of 6,944 and `integer_form` 6,771 of 6,972; my reading, not counted, is that the rest refused inside Rust, which never reaches the comparison.

## Planted bugs

Answers and digests that differ from Python, on the tested source.

| Plant | Dev | Fuzz | `lra` |
|---|---|---|---|
| `coeff`: `_lin`'s coefficient loses its sign | **Caught:** 17, 59 | **Caught:** 790, 2,520 | **Caught:** 32, 791 |
| `sort`: sort sites backwards | **Caught:** 0, 45 | **Caught:** 0, 1,090 | **Caught:** 0, 644 |
| `pi`: `_from_sympy` reads pi as E | **Caught:** 3, 41 | **Caught:** 6, 210 | **Caught:** 0, 355 |
| `eq`: an eq's sign normalisation doesn't run | **Not caught** | **Not caught** | **Not caught**, caught by check mode |

**`eq` is a real limit.** A wrong sign at that normalisation moves no answer or digest on any workload, so the evidence for that line is check mode alone. My reading, not tested: negating both sides is the same constraint, and the digest doesn't hold the form.

## The 16 session lists (bar item 5)

Before the fix, `lra` showed 16 queries whose digest lists differed, with 0 answers differing. **Cause: a refused run's discarded sessions were still in `fresh.py`'s list.** `rb` logged every rollback uncapped: 298 refused queries, 282 with no session alive at the rollback and 16 with some (8 with 1, 7 with 2, 1 with 3). Those 16 are exactly the differing queries. On all 298, the final list equals the discarded sessions followed by Python's. `fresh.py` now drops them at the rollback and reports `discarded_sessions` (25, which matches), and `lra` then shows 0 digests differing.

**A discarded run leaves nothing:** planted refusal in every run, `--lra --discard`. Dev: 1,985 refused, 0 answers, 0 digests, 0 left. `lra`: 1,500 armed, 1,259 raised, 1,798 rollbacks checked and clean, 0 answers, 0 digests. "Nothing" means what `term_discard.py`'s state reads, which leaves out SymPy's caches. **The `lra` column ran on orion:** on pareto0 it stopped at query 6 with a `TermFault`, because a run's own refusal left the plant armed for the second run. That was the harness, not the slice. The one-line fix is the `fresh.py` change that lands here, and dev's column predates it.

## The registry

`lra_registry.py`, one process with no reset between queries, one engine and then a new engine per query, 435 lines per run: **Python against Rust is byte-identical in each order.** Control: the two orders differ from each other. It carries no refusal, so `lra` and its column above are the evidence for refusal with registry history, where rollback truncates `_CONSTANTS`. `fresh.py` shares that history across queries because `reset_module_state` doesn't clear `_CONSTANTS`.

**Correction:** commit a595e94's message (1859d3c before the rebase) says "both orders: 545 lines identical". That run was void for order, because its reversed scenario kept `log(2)` first. Quote this run.

**Python reads during search:**

| | dev | fuzz | `lra` | suite |
|---|---:|---:|---:|---:|
| registry | 886 | 1,836 | 31,231 | 28,998 |
| `_generic` | 1 | 0 | 15,427 | 136,122 |
| `enclose`, through `bounds` | 1 | 0 | 440 | 134,419 |
| `num` on Python | 0 | 0 | 0 | 1 |

## Scaffolding, which must reach 0 before any backend PR

| | dev | fuzz | `lra` | suite |
|---|---:|---:|---:|---:|
| `closed_mul_scaffold` | 0 | 0 | 5,946 | **0** |
| `scaffold:rebuilt` | 1 | 100 | 968 | 19,072 |

- **`closed_mul_scaffold` on `lra`, by Rust's refusal:** own `as_base_exp` 2,854, a numeric-base power 1,103, factors share a base 1,005, a coefficient beside a numeric-base power 544, Float 433, more than one I 7. **The fix is in `algebra.rs`, which is B's.** I didn't message B's session, because nothing here blocks landing and the suite and dev and fuzz never reach it.
- **`scaffold:rebuilt` on the suite:** `_eq_links` 18,951 (B's), `integer_form` 112, `relation_atom` 8, `order_sides` 1. Fuzz's 100 are `relation_atom`. `lra`: `integer_form` 967, `order_sides` 1.
- Each rebuilt term is checked against Rust's form: `scaffold_bad` 0 on every column. A `closed_mul_scaffold` product has no Rust form to check against, since Rust refused it.

## Refusals

- **`lra`, 298:** factors share a base 200, Float or infinity 42, coefficient beside a numeric-base power 37, own `as_base_exp` 13, a callback on a derived term 3, B's termwise 3. The workload aims at these, so this is no rate for real use.
- **Suite, 363:** factors share a base 308, own `as_base_exp` 22, Float or infinity 9, a class with its own coefficient split 10, `compare` 8, a callback on a derived term 4, coefficient beside a numeric-base power 2.
- `fault` 0 everywhere. `read_raised` and `read_term_missing` 0 on the suite and fresh columns, on the reads the runs asked for.

## Quiet firings

| Handler | Test | Type | Rows | Status |
|---|---|---|---:|---|
| `_consistent` | `test_invariants.py::test_ci_stream_reports_only_what_replays` | AttributeError, `_ok` 34 and `_rb_clauses` 4 | 38 | Named needs-internals case, passed |
| `Engine._build_context` | `test_transfer.py::test_protocol_on_fuzz` | RuntimeError, "Already mutably borrowed" | 1 | Named 46-stub cause, `tests/theory_harness.py:242`, failed |

- **`engine.py:1906`: 0 catches** on the suite, and every fresh column has an empty handler file. `quiet_fire.py` and `lazy_fire.py` exit 0 on this source, so the counter fires. `handler_count` covers 2 of the 7 handlers.

## Open, and what didn't run

- **Not explained:** `kept:args-eq-not-is` is 3 on the suite and 11 on the check suite, which also used more workers. Those queries answer on Python and no outcome changed. I didn't look into it.
- **`num_python`** is reached 1 time on the suite. `test_lra_live.py` is the other evidence: 27 pass on 25 values.
- **`transfer_fuzz` (with the landing job, not a condition):** seeds 2, 3, 5, 7, 11, 13 all exit 0, each with its named differences.
- **Units:** 175 passed, 6 skipped; with `SLICE_TERM_TEST_RUST=1`, 75 passed.
- **One hash seed**, from `env.sh`.

**Not run, moved to before any backend PR:** the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the boundary rescore and suite column (10 of the 25 boundary mutants have no real-engine catch); the final drop score and its lost rows; the suite split with Python's counter; `order:_rows`' evidence (not caught meanwhile); the `_forms` guard test; history and seed reruns; forced moves; the native path; timing, including `_INTERPRETED`'s cost. **Also not run:** `term_ids_direct.py` (B's), the component 0 shadow on the suite, a public-API version of `test_incremental_matches_fresh`.
