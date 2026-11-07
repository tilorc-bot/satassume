# Handoff, sa-port-61: `_rows_runtime.py` on Rust (issue 323)

Head: `port/rows-runtime` at 9e1612a, pushed, built from origin/rust-slice 60493d6. **Not landed; nothing on rust-slice.** rust-slice hadn't moved at 14:22 UTC, 7 Nov. Slice A (sa-port-60) may land first and changes `knowledge_live.py`, so expect a conflict around `install()`.

## Bar status: none of the five landing conditions is met yet

| Bar item | State |
|---|---|
| 1. Suite by id, three numbers | **Not run** |
| 2. Fresh dev and fuzz MATCH on the landing source | **Not run on the landing source.** Earlier runs below |
| 3. Planted bug caught | **Not run.** 9 plants written, harness never executed |
| 4. Quiet handler firings from the suite | **Not run** |
| 5. Explained cause for known differences | None known, but only short runs back that |

## What did run, orion (aarch64), short runs only

| Run | Source | Result |
|---|---|---|
| `knowledge_fresh` dev, plain vs atoms vs shadow | 8dec4f9 | byte-identical tsv, 0 mismatches, 0 faults |
| `knowledge_fresh` fuzz, same | 8dec4f9 | byte-identical tsv, 0 mismatches, 0 faults |
| `knowledge_fresh` rows (new workload), same | working tree, same Rust and `knowledge_live.py` as 9e1612a | byte-identical tsv, 2,872 queries, 2,879 shadow compares, 0 mismatches, 0 faults |
| `rows_cmp.py 3000 1 --plant-check` | 8dec4f9 | 0 differences: 95 functions, 475 attributes, 853 `gen` calls, 801 `constant_value`, 1,418 `from_text` |
| `test_knowledge_rows.py` | working tree | 42 passed |

Caveats:
- dev and fuzz predate the `rust_generator` rewrite (lazy read for families first used by a kept query), so they don't count for the head.
- `--plant-check` only tests `_same_objects` on hand values. It doesn't show `rows_cmp` catches a Rust bug. Only the plants can.
- `fault` and `shadow:mismatch` have not been shown firing under this port (FALSE ZEROS). Only `rows:constant_value:python` is shown firing (906).

## Reach: who calls this module

| Calls | dev | fuzz | rows |
|---|---|---|---|
| `RowsGen` built (of 95) | 27 | 3 | 95 |
| `gen(R, c)` | 283 | **0** | 1,562 |
| `constant_value` on Rust | 1,239 | 5,575 | 3,310 |
| of those, gone to Python | 0 | 0 | 906 |
| `rows:kept` | 12 | 0 | not read |

dev and fuzz counts are from 8dec4f9. **The fuzz MATCH says nothing about `gen(R, c)`, and neither dev nor fuzz reaches a Python fallback in `constant_value`.** Only the rows workload and `rows_cmp` reach those. Suite reach: unknown.

## Inventory claims checked

- "Parser over Rust numbers": true, `rows.rs:172`, `:214`.
- "`-1/E` needs the constant field": **`-1/E` isn't in the compiled rows now**, only in the docstring. What needs the field is `E` (Pow, 9 shape uses) and `exp(-1)` (LambertW, 2 term uses). `-1/E` still reads and is tested.
- "`generator` becomes the data reader": true for reading, but every value goes back out as a SymPy object, because `wiring.py` is still Python.
- Registry order: reading `E` or `pi` can't reorder `_CONSTANTS`, since both register at import (`constfield.py:1318`, `:1320`). `sqrt(2)` would register a radical, so Rust declines it and no row uses it.

## Whole or partial: my reading is PARTIAL, so 0 of the 32, not the expected 1. Yours to confirm

All 6 functions have a Rust counterpart, but by the brief's own test some values stay on Python:

- **Row values, 2 of 122 uses:** `I` and `-I`, both in Pow's shapes. The constant field is real.
- **`constant_value` calls by `c`:** `Float`, `oo`, `-oo`, `nan`, on all 7 texts, plus `1/number` at 0, whose value is `zoo`. 906 of 3,310 on the rows workload, 0 on dev and fuzz.
- **Not reached by any row, also Python's:** `sqrt` of a non-square, and any value that isn't a rational times one power of `E` or `pi`.
- **Callers needing SymPy objects, all in `wiring.py`:** `matches` :207, `_allowed` :449, `shifted` :147-148, the shifts and times at :255-264 and :306, `constant_value` :320 and :604. Rust supplies every one except `I`/`-I`, by conversion at the boundary (`to_sympy`, `rows.rs:275`), so none of these has a Rust consumer until `wiring.py` is ported.

Also on Python: `gen.__module__`, `__name__`, `__qualname__`, `arity` and the kept path live in the install shim, `knowledge_live.py:366`.

## Kept queries

`gen(R, c)` and `constant_value` go to Python in a kept query. A family first used by a kept query keeps Python-built attributes for the process, with the same values, counted as `rows:generator:kept`. Its later rules are still Rust's.

## Next steps, in order

1. Rebase on origin/rust-slice, build, and `git log` the incoming diff.
2. Regenerate plain tsvs on the landing source, including `value-plain.tsv`, which `first/` lacks: dev, fuzz, value, rootof, rows.
3. Run fresh dev and fuzz, plain vs atoms vs shadow, with `rows:*` counts read per text.
4. Run the 9 rows plants plus control `common-contrapositive-sign`: `mutate_knowledge.py WORK PLAIN_DIR --only ...`. The harness additions are unrun, so check the base row reads `no` first. On pareto1 per the MACHINES line.
5. Run the suite with `SLICE_KNOWLEDGE=atoms`, handler_count on, x86-64 .so. See `knowledge_suite.py:3`, `run_suite.sh` header, `~/sp19/p1_job.sh`. I did not find the exact landing command in `port-realroots.md`, so check `rust_plugin.py` and the sa-port-48 job dirs. Base rows: `~/sa-rust-ids-work/port-census/pr328-check/suite-rust`.
6. Write `results/port-rows-runtime.md`, land without force, report.

Fix the docstring in `knowledge_rows_wl.py` if a run changes its claims about fuzz.

## File map

| What | Where |
|---|---|
| Python module | `satassume/knowledge/templates/_rows_runtime.py` (from_text :32, constant_value :47, _read :60, _shape_object :74, _term_object :80, generator :91) |
| Rust parser and eval | `rust-spike/slice/solver_rs/src/rows.rs` :172, :214; limits :20-23 |
| SymPy boundary | `rows.rs:247` monomial, `:275` to_sympy |
| Python-facing | `rows.rs:315` rows_from_text, `:328` rows_constant_value, `:388` RowsGen, `:475` new, `:583` __call__ |
| Registration | `solver_rs/src/lib.rs` (`mod rows`, `rows::register`) |
| Install | `rust-spike/slice/knowledge_live.py` `_same_objects` :143, `_rows_compare` :154, block from :335, `rust_constant_value` :347, `rust_generator` :366, swap :412, undo :459 |
| Direct comparison | `rust-spike/slice/rows_cmp.py` |
| Workload | `rust-spike/slice/knowledge_rows_wl.py`, hooked in `knowledge_fresh.py` as `rows` |
| Unit tests | `rust-spike/slice/test_knowledge_rows.py` (not in `tests/`, so no new suite ids) |
| Plants | `rust-spike/slice/mutate_knowledge.py` from :75, `RW` :28, rows column :187 |
| Output so far | `~/sa-rust-ids-work/sa-port-61/first/`, `cmp0.txt` |
| Inventory | `rust-spike/PORT-INVENTORY.md` :49, :74, :465, :626-627 |

## History note

8e04661 on this branch has a syntax error in `mutate_knowledge.py`, from a bad `sed` of mine. 9e1612a fixes it. Squash or keep as you like; neither is on rust-slice.
