# Handoff: component 4, slice C, items 1-5 written (sa-port-72, issue 323)

Branch `port/4c`, rebased on `rust-slice` ce19962 (the old head 5160daf is replaced). **Nothing is on `rust-slice`. Modules running whole because of this: 0 of 32 so far.** Stopped at the 141k context note. `knowledge_live.py` isn't touched, so the rows-kept guard ruling doesn't apply: say so in the report. The planner has accepted `own_base` on the input layer's count (architect, 7 Nov).

## Running when I stopped: read it first

`~/sa-rust-ids-work/sa-port-72/c3/run1/` on orion, detached, ends with `DONE`. **Don't rebuild or edit `term_live.py`, `convert.py` or `fresh.py` until `DONE` exists:** later jobs import the current tree. Read with `python3 ~/sa-rust-ids-work/sa-port-72/cmp3.py DIR`, and check `rc.txt` for anything not 0 (124 is a timeout). Its source is the commit that adds this file.

## Written, and what ran on it

Item numbers are sa-port-70's in `HANDOFF-sa-port-70.md`.

| Item | What | Status |
|---|---|---|
| 1 | `relation_atom` lt, gt, le, ge: `order_relation`, positions only | Written, compared |
| 2 | `_ext_atoms`: `needs_ext` | Written, compared |
| 3 | `_eq_links` and `_eq_infinity` as plans; `_run_plan` runs them left to right | Written, compared |
| 4 | `scope`: `affine_pair`, plus `_is_number`, which is the term work of `linked_terms` and `zero_args`; `_under_apps` and `zero_twin` under a per-query memo (`_Query.memo`) | Written, compared |
| 5 | `euf_adapter`: `structural`, `interned`; `relations._structural_subterms` | Written, compared. `_intern` stays Python's: partial, name it |
| 6 | The rest of `Relations`, `relations.py:777-1921` | **Not started. Slice again here unless it fits, and say so in the report** |

| Run on this tree (orion) | Result |
|---|---|
| Dev, default budget | Rust against Python byte-identical, 0 refusals, 0 faults |
| Dev, check mode (`fresh.py --term-check`) | 0 differ. `relation_atom` 4,068, `_is_number` 14,259, `_under_apps` 6,840, `structural` 4,012, `affine_pair` 3,132, `_structural_subterms` 802, `interned` 552, `_ext_atoms` 176, `_eq_links` 40, `glue_objects` 30 |
| Fuzz, default budget | 3,000 rows: 0 answers, 0 digests, 0 refused, 0 faults; check mode the same, 0 bad. **Per-site check counts not read** |
| `relations_direct.py 300 1` (new) | 295 cases, 0 `differs:*`; `plan:_eq_links` 156, `plan:_eq_infinity` 38, `is_:_eq_infinity` 1. Thin on `is_`. Output `c3/rd.txt` |
| Same, `--plant plan-drop` at 100 | Caught: 52 `_eq_links`, 14 `_eq_infinity`, exit 1 |
| `test_term_ids`, `test_term_live`, `test_lazy_reads`, Python's solver | 148 passed, 6 skipped |
| Same, `SLICE_TERM_TEST_RUST=1`, `-n 2` | **3 runs 149 passed, 5 skipped; 1 run failed `test_lazy_reads.py::test_stock_term_plant_is_caught[finite-stock_finite]`.** Alone: 74 passed twice. Cause unknown. My guess, untested, is test order and SymPy's assumption cache. Check whether the base does it too, and report it either way |

**Answer to the first step's question:** `test_term_ids.py` did not rely on the old plant site.

### Plants on dev (fuzz was partly done, read `run1`)

| Plant | Answers | Digests |
|---|---|---|
| `le-swap` | 82 | 93 |
| `no-ext` | 27 | 93 |
| `is-number-false` | 0 | 169 |
| `plan-drop` | 0 | 15 |
| `plan-pred` | 0 | 15 |
| `interned-reversed` | 0 | 5 |
| `affine-false`, `linked-drop`, `under-empty` | **0** | **0: not caught on dev** |

Fuzz so far: `no-ext` 123 answers and 2,055 digests, `plan-pred` 2 answers and 754 digests. For a plant fuzz doesn't catch either, say why with its reach count. No plant is void until its count says so. `zero_twin` has no plant, and `_eq_infinity` has 0 plans on dev, so its evidence is `relations_direct.py` unless fuzz's count says otherwise.

### The `termwise-true` line (landing bar)

Run on the tree before items 1-5, rebased on ce19962: `c2/plantb/`. **Rerun it on the landing source:** `bash ~/sa-rust-ids-work/sa-port-72/plantb.sh OUT`, then `python3 ~/sa-rust-ids-work/sa-port-72/cmpb.py OUT rust true`.

| | Real True / False at the glue | Rust vs Python | `termwise-true` |
|---|---|---|---|
| Dev, budget 5 | 30 / **0** | 0, 0 | 0 answers, 0 digests |
| Dev, budget 2 | 30 / **0** | 0, 0 | 0 answers, 0 digests |
| Fuzz, budget 5 | 100 / 1,476 | 0, 0 | **7 answers, 74 digests** (q352, q632, q912, q2211, q2648 first) |
| Fuzz, budget 2 | 92 / 1,424 | 0, 0 | 0 answers, **3 digests** |

**So dev's miss is explained: the plant only changes a False, and dev has none, so it is void there.** Fuzz catches it: at budget 5 through answers, at budget 2 through digests only. This supports the planner's reading on fuzz. It doesn't show why budget 2 moves fewer answers, and I didn't look.

`termwise-false` also strips differences in `_eq_links`, so its dev catch in sa-port-70's table isn't evidence about the glue alone. I dropped it from the rerun.

## Left, in order

1. Read `run1`, including per-site counts.
2. **Add slice C's tests to `test_term_ids.py`:** none exist yet. At least each plant's catch, nan under le and ge, and `_eq_infinity`'s three paths.
3. Run `relations_direct.py` larger (a few thousand, 2 seeds) on a machine, with each plant it can reach, and raise `is_` coverage.
4. Item 6, or slice again and say so. **Landing items 1-5 as C1 is the likely call.**
5. The bar on the landing source: suite by id with the three numbers and handler firings (`run_suite.sh`, on pareto0 or pareto1), fresh dev and fuzz, a plant caught, explained differences.
6. **Report owed from the brief:**
   - `mul` refusals before and after on the suite and fuzz. Base: slice B's 19 on 6 distinct queries. `term_ids_direct.py`'s old reason count was never read.
   - The discard state check on some of the suite's real refusals (slice B ran only planted ones; `_Query.memo` is new state, but dies with the query).
   - `handler_count` covers 2 of the 7 handlers. New handler sites: none added so far; state it.
   - Rebuilt terms per step. So far `scaffold:rebuilt` 69, all `glue_objects`, on dev. Plans can rebuild under `_eq_links`.
   - `engine.py:1906` catches, shown firing on a plant first.
   - Which of the 32 modules run whole. Expect `relations.py`, `euf_adapter.py` and `scope.py` all partial.

## Limits to keep in the report

- **Atoms and formulas stay Python's:** `P`, `And`, `Not`, `Args`, the session and every `s.var` key hold SymPy objects until component 5. "Clauses over ids" here means a plan Python runs.
- **`_is_number` is a wide new wrapper.** It reaches `scope` and `engine`, but `ref.py` keeps its own binding and stays Python's. Its cost per call wasn't measured, and timing isn't on this bar.
- `is_Rational` here is the class flag, where Python's `_structural_subterms` and `interned` test `isinstance(e, Rational)`. They'd differ only on a class that sets the flag without subclassing. Not tested.
- **`_under_apps` returns a set in a different insertion order.** I checked by `rg` that consumers test membership (`engine.py:1195`, `:1805`, `relations.py:612`, `:652`). I didn't read every path past `glue_atoms`' `cinfo`. Digests match on dev and fuzz.
- `_under_apps` falls back to Python for a side whose class has its own `atoms` (`PLAIN_ATOMS`), counted as `term:py:_under_apps:own-atoms`. Never seen firing, so that path is untested.
- **`term_ids_direct_terms.py` is a copy of `term_ids_direct.py`'s generator,** because that script runs `main()` on import. Remove the duplicate.
- `_plant_plan`'s `zero_only` argument is unused. Remove it.

## File map

| What | Where |
|---|---|
| Wrappers, in `rust-spike/slice/term_live.py` | `_relation_atom:366`, `_obj:435`, `_ext_atoms:439`, `_is_number:459`, `_affine_pair:484`, `_linked_terms:511` (count and plant only), `_under_apps:525`, `_zero_twin:560`, `_structural:574`, `_interned:595`, `_structural_subterms:620`, `_glue_objects:668`, `_plant_plan:725`, `_run_plan:737`, `_eq_links:754`, `_eq_infinity:791`, `install:893`, its bindings from `:965` |
| Rust, in `solver_rs/src/term/relations.rs` | `PlanOp:137`, `OrderAtom:146`, `needs_ext:155`, `order_relation:161`, `eq_links_plan:179`, `eq_infinity_plan:200`, `affine_pair:220`, `under_apps:240`, `structural:272`, `interned:277`, `structural_subterms:294` |
| Binding | `solver_rs/src/term/py.rs`: `PlanRow:84`, pymethods from `order_relation:248`. `table.rs:73` `PLAIN_ATOMS`, `convert.py:69`, `:236` |
| The `mul` line | sa-port-70's map: `algebra.rs` `mul`, `table.rs` `Read`, `convert.py` `own_base` |
| Python's own | `satassume/relations.py`: `relation_atom:511`, `_under_apps:571`, `zero_twin:618`, `Relations:777`, `_eq_infinity:1127`, `_eq_links:1325`, `_structural_subterms:1948`, `glue_objects:1994`; `satassume/scope.py:133`, `:150`; `satassume/theories/euf/euf_adapter.py:73`, `:191`, `:216` |
| Comparison | `fresh.py` (`--budget`, `--term-check`, `--term-plant`, `--term-out`), `relations_direct.py`, `term_ids_direct.py`, `~/sa-rust-ids-work/sa-port-72/cmp3.py`, `cmpb.py`, `c3.sh`, `plantb.sh` |
| Environment | `. ~/sa-rust-ids-work/sa-port-72/env72.sh` on orion. A new session should copy it and write under its own output directory |
