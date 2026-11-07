# Components D and 0: landing report (issue 323)

By sa-port-20, 7 Nov. `.so` sha 5e6231ab (crate 446d68d, unchanged since), x86-64 build 4bdc9b63 on pareto1. Output: `~/sa-rust-ids-work/sa-port-20/`, and `sa-port-18/` for the runs it names.

**Modules of the 32 running in the real engine because of this: 0.** D is offline and nothing of it is ported. Component 0 runs beside the real engine under a shadow that checks it and decides nothing, and nothing consumes conversion yet. So "wired into the real engine" holds only as observation. No answer comes from this code, and the shadow isn't installed by default, so pure Python's behaviour is unchanged.

## D: offline data

`tests_offline.py`: ALL PASS. Same bytes as the committed file under hash seeds 0, 1, 2, 3, 77, 4242; Rust reads it whole and refuses on any mismatch.

## 0: answers and state against Python, fresh engine per query

| Run | Answers, same as plain | Mismatches | Refusals | Kept on Python |
|---|---|---:|---|---|
| dev, seed 0 | a5349612416b55ef, yes | 0 | 0 | 50, out-of-scope |
| fuzz 424242, seeds 0, 1 (`.so` before the `oo` rule) | d4006a14c365ecdf, yes | 0 | 0 | 0 |
| corpus, seeds 0, 1, 2 | 544a8c885fcd4911, yes | 0 | 18, same table by reason at all three | 190, out-of-scope |

**Fuzz under the plain shadow wasn't rerun on this `.so`; its plain-shadow row is sa-port-14's.** It did run on this `.so` under `--synthetic` below, with the same answers and 0 mismatches.

Corpus's 18: derived key, power base not an input term 8; `__mul__` infinity or nan 4; Float in `__mul__`, `__sub__`, `__truediv__` 1 each; `__truediv__` denominator 1; `x**1.4` against `x`, both ways, 2.

**`--synthetic`, its first run:** algebra checked against SymPy-built results, wider than the engine reaches. Mismatches 0. These counts size the gap in shape coverage, not lost queries.

| | Ops | Refused | Largest reason | Python itself raised (skipped, not compared) |
|---|---:|---:|---|---:|
| dev | 102,930 | 6,666 | factors share a base, 6,187 | 12 |
| fuzz | 518,616 | 19,718 | factors share a base, 19,098 | 0 |
| corpus | 123,614 | 12,811 | factors share a base, 6,517 | 136 |

`-2` was added to the coefficients afterwards (planted bugs, below). **Only dev has rerun with it:** 0 mismatches, refused 6,676. Fuzz and corpus above are the earlier set.

## Pow refusal (planner's ruling, point 3)

Corpus, seeds 0, 1, 2: 9 such terms, 9 queries holding one, **0 refused at a used key, 9 finished without refusing,** the same at all three. Dev and fuzz hold none.

The 8 `derived key: power base not an input term` refusals don't count as refusals at key time. By reading: `check_derived` asks `table.sort_key` for every new derived row whether or not the query uses it, and a used key sets `pow_refused` separately (`term_shadow.py:663`). A real consumer asking for those keys would refuse. This benefit rests on one workload.

## The suite

**5,960 / 77 / 46 plus 1 other failure, against the base's 5,961 / 77 / 46.** sa-port-18's run, `.so` 5e6231ab, orion, `-n 3`, shuffled; not rerun, since neither the crate nor any source the suite reads has changed. By id, of 6,125 on both sides, none added or lost and one changed: `tests/test_wide_derived.py::test_wide_derived_or_against_or_is_fast[nor-nor]`, passed to failed, a wall-clock assert at 2.27s against 2.0s, load about 54. Alone at load 41, all 4 parameters passed in 6 of 6 runs. **Not run on the base tree at comparable load, so "load" is a likely reading, not a shown one.** The suite doesn't install the shadow and nothing consumes conversion, so it shows the rest of the crate still behaves. It is not evidence that component 0 is right.

## Planted bugs: 22 of 27 caught, 5 not

Dev, engine-reached ops: 19 caught. Corpus with `--synthetic` added `neg-keeps-sign` and `mul-unsorted`. Adding `-2` to the synthetic coefficients added `keep-coeff-minus-one`: by hand it builds `Mul(-1,x)` where SymPy has `-2*x`, a real wrong form that no workload's shape reached. All three base rows read 0.

**Not caught.** The reasons are from reading, and none of them was run:

| Plant | Why, by reading | Standing |
|---|---|---|
| `float-not-inherited` | `operand` refuses a Float at `algebra.rs:64`, so the bit is never set on an operand | Unreachable while that refusal stands |
| `tuple-length-flipped` | Key tuples lead with their length, so one is never a prefix of another; a custom `class_key` might differ | Not reached; no direct test |
| `custom-content-flipped` | `Class.custom_content` has no reader in Rust, and `class_row` doesn't expose it | **Crossing unchecked** |
| `class-flag-bit` | Bit 0, `is_Add`, has no reader in Rust. `class_row` exposes flags and `term_shadow.py:90` reads them, yet this survived; not traced | **Crossing unchecked** |
| `conv-free-unordered` | Rust re-sorts at `algebra.rs:92`, and the shadow compares sorted, so the row's "ordered by id" isn't checked | Harmless today; the claim is unchecked |

**Boundary re-score, 12 plants:** 9 caught. Rust's reads 5 of 7, conversion 4 of 5. `term-id-off-by-one` is caught by SIGSEGV (exit -11), so a malformed table kills the process and raises nothing. Probably a stack overflow from a cycle; not traced.

## History independence

**Conversion and Rust's reads of the table: 0 differ.** `term_history.py`, dev 1,985, corpus 2,863, fuzz 3,000: seeds 0, 1, 2 fresh, reverse dirty at seed 0, shuffle dirty at seeds 0 and 1, each against seed 0. Limits: the digest covers the tables, rows and `compare` over the first 20 terms of each query. It doesn't cover derived terms.

**No cross-query state in the term code:** ids are per table, per query.

### Hash order on Python's side: wider than known, and it's read

`Engine._union` iterates a set and can return early, so an over-budget result's `(weight, rel)` depends on the hash seed. Seeds 0, 1, 2:

| Workload, budget | Answers, `_within_budget`, limited | Over-budget `(weight, rel)` differs | Fitting cone records differ |
|---|---|---:|---:|
| dev, 5 | 0 differ | 8: 519-526 | 0 |
| corpus, 5 | 0 differ | 1: 2854 | 0 |
| corpus, 2 | 0 differ | 3: 2853, 2854, 2855 | 0 |
| fuzz, 5 | 0 differ | 389 | **16** |
| fuzz, 2 | 0 differ | 1,019 | **11** |
| dev 25 and 400; fuzz and corpus 25 and 400 | 0 differ | 0 | 0 |

Fuzz's ids: `union/fuzz-b{5,2}-none-ids.txt`. Fitting records, budget 5: 38, 90, 94, 246, 441, 745, 876, 953, 1018, 1055, 1254, 1902, 2425, 2443, 2490, 2566.

**This corrects "nothing reads those values".** `_within_budget:1795-1810` reads `rel` from that early return and uses it to choose `link`, so the seed reaches control flow. On all 16, `_within_budget` is False at every seed; budget 2's 11 weren't traced. Smallest, fuzz 2425, `ask(Q.real(1 - 2*x), Q.ge(x, pi/2) & Q.le(x - y - 1, 1 - y))`: the assumptions' over-budget `rel` is False at seed 0 and True at 1 and 2, and those seeds also compute the `link=True` cones. So which entries `_qcones` holds, and which `link_objects` work is done, depends on the seed.

**Argued harmless, not proven, and it is not history independence.** The argument: `link` only adds objects, so an over-budget cone stays over budget and `_within_budget` returns False either way. That covers the verdict only. `link_objects` also reaches `_glue_adapters`, SymPy construction and an `except Exception: pass` (`relations.py:1989`), and no run compares those per-engine memos across seeds. Whether they can change a later query on the same engine is untested, since these runs use a fresh engine per query. **Rust's `_union` and `_within_budget` must not copy this if anything ever reads those values.**

`struct:calls` and `alg:same-as-known` also move with the seed, ops and answers don't. Fuzz by caller: `:1777` 19,008 / 16,664, `_cone_info`'s walk 49,160 at both, 1,795 of 3,000 queries differ. Corpus settle, seeds 0, 1, 2: `alg:derived-terms` is 5,939 at all three, but its split moves, new at an op 3,681 / 3,714 / 3,647 and new at a number read 2,258 / 2,225 / 2,292. So which site first registers a rational depends on the seed. That `_union` causes this is an inference from the same traversal, not a direct check. It means the shadow's derived-id numbering follows Python's traversal; it says nothing about Rust's own order, which doesn't exist yet.

**Also open:** pure Python's construction count isn't reproducible between identical runs at one hash seed (`_assumptions_shuffle`, noise about 10 in 8,000; see `HANDOFF-sa-port-18.md`). Same site as issue 329 and PR 330, so don't read it as affecting counts only.

## Counts and speed

**Callbacks: 0,** since nothing consumes conversion. **Derived terms rebuilt in SymPy: 0.** Input-layer construction, a separate count outside the "must reach zero" rule, is sa-port-18's table on pareto1, quiet lease, 3 rounds:

| | Pure Python constructs | Conversion | Keys computed / in queries using none |
|---|---:|---:|---|
| dev | 7,706 | 4,089 (0.53x) | 6,532 / 5,328 |
| fuzz | 93,006 | 25,053 (0.27x) | 28,864 / 338 |
| corpus | 6,070 | 9,811 (1.62x) | 6,849 / 6,587 |

`complex(t)`, with its own counter, is 2,553 / 12,429 / 6,341 of those.

**Item 1, key order only: confirmed by an uncut rg of the whole crate.** `Closed.complex` is read only by the key (`algebra.rs:642-645`) and the read-only `py.rs:99` view, and `Closed.is_finite` only by that view. So a floating value never decides a fact (issue 247).

**Item 3, conversion's self time by site.** pareto1, quiet lease, `BENCH_CPU=2`, 2 rounds within 2%, seed 0, instrumented (`conv_sites.py`), so shares rather than times. Percent of conversion; `table` is timed apart from it.

| Site | dev | fuzz | corpus |
|---|---:|---:|---:|
| `klass` | **56.3** | **35.7** | **54.7** |
| `default_sort_key` | 5.2 | 13.1 | 5.6 |
| key encoding | 5.8 | 8.9 | 4.8 |
| `complex(t)` | 5.8 | 8.6 | 11.0 |
| `has` (nan, bad, Float) and `atoms` | 6.6 | 11.1 | 5.2 |
| `table` | 3.9 | 3.5 | 3.3 |
| Conversion's total, s | 1.19 | 3.27 | 1.56 |

**`klass` is the largest site everywhere,** and it's a class-level read repeated per query. Nothing was optimized.

**Item 2, worst case of `complex(t)`.** Largest single call against pure Python's whole query:

| | Largest | Term, query | Pure Python, same query |
|---|---:|---|---:|
| dev | 0.21 ms | `I`, 1031 | 0.3 ms |
| fuzz | 0.05 ms | `pi/2`, 0 | 12.5 ms |
| corpus | 1.79 ms | `TribonacciConstant`, 586 | 0.2 ms |

Hand-built terms, `Q.positive`, 120 s limit:

| Term | Pure Python | `complex(t)` |
|---|---:|---:|
| **`CRootOf(x**50 - x + 1, 3)`** | **3.6 ms** | **over 120 s, stopped; conversion too** |
| `stieltjes(30)` | 0.5 ms | 37.7 ms |
| `besselk(100, pi)` | 0.5 ms | 8.8 ms |

`Q.integer` gives the same `CRootOf` result. **Limits:** 30 of the 32 terms ran. `E**(pi*sqrt(163))` failed because my script's `E` was the engine module, which also put that module in `Piecewise`'s row, and `meijerg` didn't construct. `hyper`, both `Limit`s and `Derivative` aren't `is_number`, so `closed` doesn't reach them.

**Question for the planner, raised with this report: `convert.py:291` has no bound on `complex(t)`,** so one such term stalls a query pure Python answers in milliseconds. No lazy path added. It can't happen by default today, since nothing consumes conversion. It would once something does.

**Item 4, arithmetic, not a measurement and not a gate** (sa-port-18's and the planner's figures, not rechecked). If conversion stays as it is, against pure Python: everything after conversion free, 2.2x dev, 6.7x fuzz, 2.0x corpus by total, about 1.1x on the median dev and corpus query; an assumed 10x on the rest, 1.8x / 4.0x / 1.7x. Conversion has no consumers yet, so these should move.

## `engine.py:1906`

0 fires: dev 2,631, fuzz 3,126, corpus 1,843 complete checks, plain and under the shadow, seed 0 only (sa-port-18). **It doesn't cover Rust conversion raising there, since nothing consumes conversion yet. Whichever session wires it in must recount.**

## Standing lines

- **S's gate** is met except for the 46 named stub failures, one cause. They stay listed in number 3.
- **The `_n_conflicts` view in `rust_plugin.py` isn't a port.** It's a test-plugin shim, with the 64 tests it moved.
- **Mutants 2, 5, 6, 7, 9** rest on the API fuzzer alone: rerun those paths once real theories run on Rust. **10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.**
- **Kept on Python with reason:** `Sum`, `Product`, `Integral`; queries under a non-default registry; R9 `enclose`, a permanent callback.
- **A public-API version of `test_incremental_matches_fresh`** is still owed by step 5.
- **Heuristics:** none added or changed. **Pure Python stays the default.**

## Not run

- `test_wide_derived_or_against_or_is_fast` on the base tree at comparable load.
- Fuzz under the plain shadow on this `.so`, and at seed 2.
- Synthetic at seeds other than 0, and on fuzz and corpus with `-2`.
- Survivors on fuzz. PR 330's pin.
- Timing at any seed but 0.
- A compare of per-engine memos across seeds, and any over-budget path with a shared engine.
