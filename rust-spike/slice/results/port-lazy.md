# Lazy reads: landing report (issue 323)

Rust asks Python for a closed value, or an input term's sort key, when a key needs it. The read is read-only on the original object and memoized in the per-query table, so it dies with the query. Conversion no longer computes these up front. There is one path, with no refusal rule, class list or time limit, and no heuristic added.

**This adds 0 of the 32 runtime modules, because nothing consumes conversion yet.** Python stays the default and the reference.

Landing source: `port/lazy` rebased on `rust-slice` 69639da, tree 1724b7e; only this report comes after it. Build on pareto1 (x86_64), sha256 starts 65b800776da3. Runs on pareto0 under `--shared`. Output: `~/sa-rust-ids-work/sa-port-39/land/t1/out/`.

## The bar

| # | Item | Result |
|---|---|---|
| 1 | Suite by id, Rust solver, EUF and LRA, `-n 8`, pareto0 | **5,961 / 77 / 46**, 23 skipped, 18 xfailed. Base 5,961 / 77 / 46. 6,125 ids, none added or gone, **0 outcomes changed** against `port-census/pr328-check/suite-rust` |
| 2 | Fresh engine, memos cleared, dev 1,985 and fuzz 3,000 | **MATCH** on all 8 comparisons. Digests 31cd0945c07f02a6 and 173502b6ef285ad6, the same as 1a's |
| 3 | Planted bug through that comparison, dev | **Solver mutant 0 DIFFERS:** 47 ends, 49 streams, 19 LRA states, first q348. Dev answers don't change. The same build unmutated reads MATCH. Fuzz columns not run |
| 4 | Quiet firings on Rust, that suite run | **39 rows, 2 tests**, below. No new firing |
| 5 | Known differences | None in answers or read state on this comparison. Limit below |

**Limit on item 2:** a plain run doesn't run conversion, so this MATCH says the tree's engine is unchanged by this work. It doesn't say reads are right. The evidence for reads is the shadow runs below.

**S's standing:** S's gate is met except for the 46 named stub failures, one cause.

**Passed split:** 5,960 with no firing, 1 with a firing. Python's counter wasn't compared (the bar moved that).
- `test_invariants.py::test_ci_stream_reports_only_what_replays`, `_consistent`, AttributeError `_ok` 34, `_rb_clauses` 4: the named needs-internals case.
- `test_transfer.py::test_protocol_on_fuzz`, `_build_context`, RuntimeError `Already mutably borrowed`, 1: the 46-stub cause, a failing test, among the 46 by id.

`_n_conflicts` in `rust_plugin.py` is a test-plugin shim, not a port; 64 tests moved with it.

## The 39 (suite ruling)

The census has no ids and its counts are floors with memos on, so its 39 can only be matched by shape.

| Outcome | Queries | Which |
|---|---:|---|
| **Matched** | 36 | 288 rows, 11 tests, below |
| **Refused** | 2 | `iuu30*exp(iuu31)` in `test_ci_stream_no_longer_finds_the_zero_i2_family`; `p*x*z*exp(q)` in `test_engine_agrees_with_reference[general-1]` |
| **Not compared in the suite; matched when built directly** | 1 | `y**2*f(r + y)` in `test_cache_audit_counts_what_it_could_not_check` |
| **Mismatched** | 0 | |

The 36 are:
- `test_engine.py::test_stream_under_one_set_answers_as_a_fresh_engine` 3
- `test_eq_links.py::test_glue_made_equality_gets_user_clauses_when_asked` 1
- `test_history.py::test_cache_audit_counts_what_it_could_not_check` 1
- `test_history.py::test_checker_catches_a_planted_history_dependence` 4
- `test_history.py::test_fixed_repro_stays_fixed[E1c-order-clauses-write-back-oo-sum-relation-in-set]` 1
- `test_history.py::test_fixed_repro_stays_fixed[S1-reused-session-eq-after-real]` 1
- `test_invariants.py::test_ci_stream_no_longer_finds_the_zero_i2_family` 2
- `test_ref_fuzz.py::test_engine_agrees_with_reference[general-0]` 9, `[general-1]` 8, `[inconsistent-0]` 4
- `test_unevaluated_products.py::test_kept_products_still_answer` 2

**The other 3 are an inference, not a by-id match.** Per term per query, these rows give 2 args 26, 3 args 9, 4 or more 5. The census has 28, 9, 6. These three terms close that gap exactly, in exactly 3 queries. Calls still differ: 288 + 18 = 306 against the census's 311, and I didn't explain the 5.

**How the 3 were compared.** In the suite the shadow scored them `unknown` (Rust has no id for the term) and `no-table` (the query is Kept, so it answers on Python). `read/three_keys.py` builds each in Rust from its factors. Both `exp` products refuse with `mul: class has its own as_base_exp`, so **the refused shape is a product with an `exp` factor**. A refusal is safe but isn't evidence the key is right. `y**2*f(r + y)` matches `default_sort_key`, and the control against a wrong term reads false.

**The rows do reach the shapes the ruling names:** 2 args with a Pow factor 62 rows, 3 args 39, 4 or more 35.

**The plant on that path** (`mul_key`, the 11 tests, `so.*.txt` checked against the shas):

| Build | sha starts | LRA derived rows | Result |
|---|---|---|---|
| Base | d8051340 | 281 | 281 matched, 0 mismatch |
| Count + 1 | 78b1b4a4 | 281 | **281 mismatch** |
| Unsorted | 02776552 | 281 | **158 mismatch**, 123 matched |

That run reaches 10 of the 11 tests and 281 of the 288 rows. I didn't chase why.

**Rows never compared, all sites, checks on:** no-table 849, outside-ask 722, unknown 14. At the LRA site as Mul: no-table 555, of which 540 are `test_ci_stream_reports_only_what_replays`; outside-ask 162; unknown 14.

**The slow worker:** `test_constants_evalf_cannot_bound_rigorously_are_not_read`. Under forced reads it hit `timeout 600` on pareto0 and ran over 90 minutes on orion, so it is **not comparable under checks**. I stopped the orion session (4132195). It passes plain and under DRIVE, and DRIVE's whole suite gives the same 288 rows, 36 queries, 11 tests, so it adds none of the 39. Checks-on coverage is 6,124 of 6,125.

## Shadow on against off

**Under DRIVE on the landing tree, 0 of 6,125 tests differ from off.** The numbers quoted stay off's.

With checks on (forced reads; `snap3` plus `rest` on `snap4`, compared to off), 3 differ:

| Test | With checks on | Reading |
|---|---|---|
| `test_mul_rows::test_a_node_of_one_factor_is_that_factor` | Failed on `snap3`, from the shadow's own `str()` raising | **Fixed; rerun on the landing tree under checks, 1 passed** |
| `test_shared_facts::test_engine_does_not_write_sympy_assumptions` | Forced reads write `_assumptions` | Passes under DRIVE, so it comes from forcing reads |
| `test_constfield::test_eliminations_finish_or_refuse_quickly[pi,E,sqrt2-8]` | Wall clock, 10.68 s against 10 | Load and forced reads; passes under DRIVE. Not timed further |

No `test_wide_derived.py` failure and no change in `test_performance_smoke_300_vars`: the suite moved no outcome against the base.

## read_term_missing and read_raised

| Workload | Mode | `read_term_missing` | `read_raised` |
|---|---|---:|---:|
| Dev, fuzz, corpus | Checks on | 0 | 0 |
| **Whole suite, landing tree** | **DRIVE** | **0** | **0** |
| Whole suite, `snap4` | DRIVE | 0 | 0 |
| Suite, 6,124 of 6,125 | Checks on | 0 | 11 in 5 tests |

**The counter fires:** `test_a_raising_read_refuses_and_counts` passes, and `lazy_fire.py` shows the handlers seeing a raise from the lazy path (TermRefuse at `_consistent`, through `sympy_api.py:1107`).

**What the zero covers:** reads the real run asks for, with the shadow's DRIVE on. Nothing consumes the result yet, so DRIVE reads what Python's ask would have Rust read, and answers still come from Python.

**The 11 under checks** are all from the shadow's forced reads, on queries where DRIVE raises 0:
- `test_add_rows::test_a_node_of_one_term_is_that_term` 3 and `test_mul_rows::test_a_node_of_one_factor_is_that_factor` 1: `Basic.__new__` nodes with no `is_commutative`. My rerun of that one test on the landing tree reads 2, not 1; I didn't chase the difference, so 11 is a floor.
- `test_nan_arguments::test_rereview_r1_reproducers` 4, `test_noncommutative::test_scalar_with_a_matrix_in_a_container_stays_in_scope` 2, `test_invariants::test_ci_stream_no_longer_finds_the_zero_i2_family` 1: `complex()` TypeError on UnevaluatedExpr(nan), Abs, sign of it, VectorZero, Mod(I, n).

The 7 in the checks-on `shadow.*.json` files come from 3 workers. The 11 by test come from `raised.py`, because the fourth worker's file was never written.

**"Harmless to landing" is a reading, not a result.** Its limit is that nothing consumes conversion. DRIVE's whole-suite count now exists and supports it for reads on this suite, nothing more.

**Reads under DRIVE, whole suite:** key 88,342, commutative 78,091, power 3, complex 0, finite 0. 34,718 queries converted. Kept: out-of-scope 2,468, non-default-registry 184, sum-product-integral 42, args-eq-not-is 2. `snap4` has power 0 and args-eq-not-is 0 on the same suite; those small differences between trees weren't chased.

## The ruling's three items

1. **Other eager reads:** `is_finite`, `decompose_power`, `complex()` and the keys now read lazily. **`_may_be_nan` stays eager in conversion (`convert.py:287`),** with the other structural reads: 0 `complex()` and 0 `evalf` on sa-port-29's hand-built terms, and again on `read/nan_probe.py`'s `CRootOf` forms (`r`, `y + r`, `y*r`, `r**2`, `Abs(r)`, `sign(r)`, `y/r`). That is measured on those terms, not proved for all terms. `test_lazy_reads.py` on this tree: 74 passed, 5 skipped (2 don't build, 3 are Kept out-of-scope).
2. **The count test:** `Q.positive(y + r)` makes 0 `complex()` calls, by count, for convert, `TermTable` and the whole ask under DRIVE. The plant restoring the eager read fails it.
3. **Reads Python's run didn't make:** `with_extra` 0 on dev, corpus and fuzz (3,000 queries). This was measured before the rebase, on the same conversion source. Fuzz: lazy key 12,274, commutative 9,340, against Python key 211,535, complex 12,492, power 8,568.

## Decisions to name

- **nan's key:** accepted, `term_row` adds `-oo`'s row when it reaches `nan`. The plant deleting that line gives exactly 27 corpus queries missing, answers equal. Three caveats:
  - A shadow run takes answers from Python, so "answers equal" is weak here.
  - The shadow scores them as 27 `mismatch:key`, all `key nan None`.
  - A plain run shows nothing more, because a plain run doesn't run conversion.
- **`is_finite` and `decompose_power`** now catch Exception. A raise reads as unknown or refuses, counted.
- **`Kept('too-deep')`:** 0 on the lazy tree and on the eager tree. Kept and refusals on dev, fuzz and corpus equal `results/port-D0.md`.
- **Ruling 3, Pow:** dev holds 0. Corpus holds 9, and those 9 finished with no refusal under checks. The 8 `derived key: power base` refusals are on derived terms.
- **History, dev only, pre-rebase:** s0 against s1, s2, rev, shuf, dirty, 1,985 queries, differ 0.
- **Per-query memo:** the read memo lives in the table and dies with the query. `read-memo-off` isn't visible to the shadow, because values don't change. Whether the count test catches it wasn't run.
- **`mutate_term.py`, dev, pre-rebase:** 31 mutants, 22 caught, base no. Not caught: neg-keeps-sign, float-not-inherited, mul-unsorted, keep-coeff-minus-one, tuple-length-flipped, custom-content-flipped, class-flag-bit, conv-free-unordered, read-memo-off. `mul-unsorted` here is a different plant from the `mul_key` unsorted above.

## Suite-only shapes

The shape is one level of class and arg classes, `I:` input and `D:` derived, so it is coarse. Under DRIVE: 2,427 suite shapes, 1,011 on the five workloads, 1,740 suite-only.

**`D:` shapes:** 121 on the suite, 47 on the workloads, **92 suite-only, 15,042 calls.** The largest:

| Shape | Calls |
|---|---:|
| `Mul(AppliedUndef,Integer)` | 7,167 |
| `Add(Mul,Mul,Symbol)` | 4,656 |
| `Add(AppliedUndef,Mul,Symbol)` | 961 |
| `Add(AppliedUndef,Mul)` | 920 |
| `Add(AppliedUndef,Symbol)` | 486 |
| `Mul(Dummy,Integer)` | 143 |
| `Add(Dummy,Integer,Mul)` | 128 |
| `Mul(Rational,Symbol)` | 107 |

## Tool gaps from 1a's landing

Neither is fixed here; both affect anyone scoring mutants on this source.

- **`mutate_slice`'s copied crate no longer compiles.** `lib.rs` includes `lra.rs` by a relative `#[path]`. My job linked `$B/lra` to `rust-spike/lra`.
- **`mutate_live.py --handlers` raises** `tool 4 is already in use`, because `catch_count` holds that monitoring tool. Item 3 therefore ran `live.py` and `livecmp.py` directly, the same comparison with no handler count on the mutant runs.

## Not run

**Moved to before any backend PR by the bar:**
- Timing and ruling 6's rerun, including `klass`'s share. No timing was taken. Counts exist from before the rebase: dev constructions py 7,708, conv 104, table 0, rest 7,710; `conv_complex` 0; `rest_complex` 207 = `py_complex`. `counts_summary.py` crashes at its last lines on the gone `keys` field.
- The mutant 2, 5, 6, 7, 9 rerun and mutlive's control. Those five rest on the API fuzzer alone.
- The boundary rescore and suite column. 10 of the 25 boundary mutants have no real-engine catch.
- The final drop score and its lost rows, the suite split with Python's counter, `order:_rows` evidence (not caught meanwhile), the `_forms` guard test, history and seed reruns on the landing source, forced moves on the landing source, and the native path.

**Also not run:** item 3's fuzz columns, and `mutate_term.py` on the landing tree.

**Not read:** `term_history.py` fuzz and corpus, which finished before the rebase.

## Interface

`TERMS-INTERFACE.md` is current. For sa-port-31: `tables['reads']`, values are gone from rows, new methods, a lazy key can't add a term, `-oo`, `read_raised`. Section 9 is updated: `enclose` is no longer "the one permanent callback"; reads are read-only callbacks on input terms.

## Standing notes

- The fresh dev and fuzz comparisons and the suite ran beside each other on a shared machine, so wall times here aren't timing.
- I stopped sa-port-35's three queued pareto1 jobs and reran them on pareto0, because pareto1's queue sat behind a quiet lease.
- Evaluator: not asked for.
