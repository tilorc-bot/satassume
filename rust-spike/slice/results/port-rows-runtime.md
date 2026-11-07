# Component 6: `knowledge/templates/_rows_runtime.py` on Rust (issue 323)

**Tested source `4095716`, on `rust-slice` b45b72f (slice B), on pareto1 (x86-64), hash seed from `env.sh`, `.so` sha256 starts 2511b9d0f95d.** It lands on 089c70d, whose only change from b45b72f is `results/port-4b.md`, with corrections to this report. Output: `/home/tilo/sa-rust-ids-work/sa-port-63/land4` on pareto1, read copies without the tsvs and plant builds in `~/sa-rust-ids-work/sa-port-63/land4` on orion.

**Module: PARTIAL. 0 of the 32 runtime modules newly run whole because of this, not the expected 1.** I confirm sa-port-61's reading rather than overrule it. All 6 functions have a Rust counterpart, but by the brief's own test some values stay on Python:

- **Row values, 2 of 122:** `I` and `-I`, both in Pow's shapes, because the constant field is real. `rows_cmp.py`: `values:read` 120, `values:python` 2.
- **`constant_value` by the class of `c`:** `Float`, `oo`, `-oo`, `nan` on all 7 texts, and `1/number` at 0, whose value is `zoo`. Python answers by text and class of `c`.
- **Not reached by any row, also Python's:** `sqrt` of a non-square, and any value that isn't a rational times one power of `E` or `pi`.
- **Attributes and the kept path:** `gen.__module__`, `__name__`, `__qualname__`, `arity` and the kept route live in the install shim, `knowledge_live.py`.

**Every value reaches `wiring.py` as SymPy, by conversion at the boundary (`rows.rs` `to_sympy`). There is no Rust consumer until `wiring.py` is ported.** Callers needing SymPy objects, all in `wiring.py`: `shifted` :140, :147-148; `matches` :196; `_allowed` :440; `constant_value` :320, :604; and the shifts and times sa-port-61 mapped at :255-264 and :306, which I didn't reread. Rust supplies every one of these except `I` and `-I`. No approximation and no new heuristic was added.

## Landing bar

| Item | Result on 4095716 |
|---|---|
| 1. Suite by id, Rust with `SLICE_KNOWLEDGE=atoms`, against a base run in the same job on b45b72f with the same settings | 6,125 ids on both sides, 0 new, 0 gone, **0 changed**. 23 skipped, 18 xfailed |
| Three numbers | **5,960 passed, 77 kept on Python (needs internals), 46 failed on re-entry, plus 1 failure from 1b** (124 failed) |
| 2. Fresh dev, plain against atoms and against shadow | Answers and state MATCH: 1,985 queries |
| 2. Fresh fuzz, same | Answers and state MATCH: 3,000 queries |
| Fresh `value`, `rootof`, `rows`, same | MATCH: 3,742, 5,187 and 2,872 queries |
| Shadow, all five workloads | 9,918 compares, **0 mismatches** |
| Direct, `rows_cmp.py 3000 1` | 0 differences: 95 functions, 475 attributes, 853 `gen` calls, 801 `constant_value`, 1,418 `from_text` |
| Units: `test_knowledge_rows`, `_common`, `_realroots`, `_lazy` | 97 passed on the tested source |
| 3. Planted bugs | 8 of 9 caught by the comparison; the ninth can't change a compiled row. See below |
| 4. Quiet handler firings | The two named cases only: 39 rows, 2 tests, the same as the base. **0 findings** |
| 5. Known differences in answers or read state | **None measured.** The values kept on Python above are the same values by construction |

**Why the base was run here:** slice A's rows and 1b's rows came from runs without `SLICE_KNOWLEDGE=atoms`, and this port installs only under it. Against slice A's rows (`sa-port-60/l1/suite`, atoms off) the head also shows 0 new, 0 gone, 0 changed.

S's gate is met except for the 46 named stub failures, one cause. They stay listed in number 3, and the crate is unchanged for them.

**Passed, by firing:** 5,959 with no firing, and 1 with a firing on Rust, `tests/test_invariants.py::test_ci_stream_reports_only_what_replays` (`_consistent`, AttributeError, `'Solver' object has no attribute '_ok'` 34 and `'_rb_clauses'` 4), the named needs-internals case. No Python-side counter ran, as the bar allows; `port-1b.md` measured 0 tests firing on Python.

**The 1 failure:** `tests/test_lra_exhaustion.py::test_split_beyond_the_certificate_bound_counts_as_exhausted`, the same on the base; `port-1b.md` gives its cause. **`test_performance_smoke_300_vars` passed.**

## Reach: which workloads actually call this module

| Calls on Rust | dev | fuzz | value | rootof | rows | suite |
|---|---|---|---|---|---|---|
| `RowsGen` built | 27 | 3 | 12 | 3 | 95 | 443, over 7 workers |
| `gen(R, c)` | 283 | **0** | 3,574 | **0** | 1,562 | 1,339 |
| `constant_value` | 1,239 | 5,575 | **0** | **0** | 3,310 | 4,743 |
| of those, gone to Python | **0** | **0** | **0** | **0** | 906 | 902 |
| `rows:kept` | 12 | 0 | 0 | 0 | 0 | 25 |
| `rows:generator:kept` | 0 | 0 | 0 | 0 | 0 | 6 |
| shadow compares | 1,374 | 5,590 | 60 | 15 | 2,879 | not run |

**Fuzz makes 0 `gen` calls, so its MATCH says nothing about `gen`. Neither dev nor fuzz reaches a Python fallback in `constant_value`,** so only `rows`, the suite and `rows_cmp` do. Going to Python by the class of `c`: `rows` Float 434, NaN 152, oo 152, -oo 144, 0 at `1/number` 24; suite Float 373, oo 197, -oo 189, NaN 140, 0 at `1/number` 3. The suite's counts move between runs (`gen` 1,328, 1,362 and 1,339 over the three full runs, `rows:kept` 16, 16 and 25), and those runs were on different sources. I read that as tests landing on different workers with per-process caches, and didn't trace it. **The suite and plants are what make any MATCH mean something:** the table below shows 4 of the caught plants move no line on dev or fuzz.

**A limit of the shadow:** it compares `generator`'s attributes and each Rust-read `constant_value`, not the rules from a `gen(R, c)` call. Those are compared by `rows_cmp` directly and by answers and state in the fresh runs.

## Planted bugs

Each from its own build, and each row reports it loaded its own. The base row reads `no` in every column. Workload cells are answers changed; `0` means lines changed with no answer changed, `no` means no line changed.

| Plant | dev | fuzz | value | rootof | rows | `rows_cmp` | shadow (dev) |
|---|---|---|---|---|---|---|---|
| `rows-premise-sign` | 581 | 2,588 | 919 | 49 | 1,672 | caught | caught |
| `rows-int-off-by-one` | 2 | 0 | 11 | no | 54 | caught | caught |
| `rows-div-is-mul` | 1 | no | no | no | 3 | caught | caught |
| `rows-sub-is-add` | 0 | no | no | no | 4 | caught | caught |
| `rows-key-ignored` | no | no | no | no | 49 | caught | no |
| `rows-neg-dropped` | no | no | no | no | 2 | caught | no |
| `rows-exp-power-sign` | no | no | no | no | 2 | caught | caught |
| `rows-abs-dropped` | no | no | no | no | 0 | caught | no |
| `rows-plain-always` | no | no | no | no | no | no | no |
| control `common-contrapositive-sign` | 165 | 377 | no | no | 371 | no | caught |

**`rows-plain-always` can't change a compiled row:** 2 of the 95 functions have a shaped row, and both also have a term that isn't `x + c`, which already clears `plain`. I added `test_shaped_row_is_not_plain` and confirmed by hand on orion that it fails on this plant's build and passes when restored. `mutate_knowledge.py`'s unit column doesn't run that file, so its row still reads `no`.

**A real bug the comparison caught.** After the first rebase, `rows_kept` still called `_stack()`, which slice A moved to `term_live`, and raised NameError. On dev against plain: **719 answers and 731 lines moved,** 45 `_consistent` firings, and all 1,935 converting queries counted as `kept:class-no-row`. I read that as `convert.py:238`'s `except Exception` taking the same NameError, and didn't trace it further. The fix reads `term_live.current()`; the fixed build differs on 0 lines. Output: `~/sa-rust-ids-work/sa-port-63/short/` on orion. So a Rust-side `Exception` on this path isn't always loud: `rows_kept` itself sits outside the shim's `try`. Everything that calls Rust in the shim is inside one and raises `KnowledgeFault`, a BaseException.

## Quiet handlers

From the landing suite run, with 28 planted rows seen across the 7 workers on each of head and base.

| Test | Site | Type and text | Rows |
|---|---|---|---|
| `tests/test_invariants.py::test_ci_stream_reports_only_what_replays` | `_consistent` | AttributeError, `_ok`, `_rb_clauses` | 34, 4 |
| `tests/test_transfer.py::test_protocol_on_fuzz` | `Engine._build_context` | RuntimeError, `Already mutably borrowed` | 1 |

`test_protocol_on_fuzz` is the 46-stub cause, `tests/theory_harness.py:242`, by the planner's naming. It fails, so it isn't among the 5,960.

**Catches at `engine.py:1906` and `sympy_api.py:1107`, by `catch_count`:** 9 tests with a catch in each run, the same ids and values on head and base. By rows: `_consistent` Uninterpreted 7 and `consistent_by` Uninterpreted 3 (counted, re-raised), `_consistent` AttributeError 38 (the named case), and `complete_check` RuntimeError 1 (that `test_protocol_on_fuzz` row). All fresh runs: 0 unplanted handler rows on any workload or mode.

**The counters fire:** `fault` and `shadow:mismatch` were shown firing on a planted raise and a planted wrong value on this port, by `test_fault_fires_on_constant_value`, `_on_generator` and `test_mismatch_fires_on_constant_value`. `knowledge_quiet.py fire` saw each of its 4 plants. Its recount's planted raises escape with the counter at 0 where reached (`atom_units` on dev and fuzz, `units` on fuzz, at `sympy_api.py:1107`); the others print `not reached`, and the forced versions also escape. Those plants target conversion and units, not the rows functions; the rows functions rest on the tests above. The `fault: 719` in the recount's dev output is its own plants, as in `port-realroots.md`.

## Kept queries

`gen(R, c)` and `constant_value` go to Python in a kept query. A family first used by a kept query keeps Python-built attributes for the process, with the same values, and its later rules are Rust's. **This path now has a run on the head:** the suite reaches it (`rows:kept` 25, `rows:generator:kept` 6), dev reaches the first (12), and `test_family_first_used_by_kept_query` covers it directly.

## Inventory claims checked

- "Parser over Rust numbers": true, `rows.rs` `eval` and the parser.
- "`-1/E` and `exp(-1)` need the constant field": **`-1/E` is no longer in the compiled rows,** by a search of `_compiled_rows.py`: 0 matches. What needs the field is `E` and `exp(-1)`. `-1/E` still reads and is tested.
- "`generator` becomes the data reader": true for reading, but every value goes back out as SymPy, as above.
- Registry order: reading `E` or `pi` can't reorder `_CONSTANTS`, since both register at import. `sqrt(2)` would register a radical, so Rust declines it and no row uses it.

## Rebase

`rust-slice` moved three times under this port, and each move was checked by its diff.

| Incoming | Changes | Decision |
|---|---|---|
| 60493d6 to 955098a, slice A | `knowledge_live.py`, `live.py`, `rust_plugin.py`, `term/py.rs`, `term_live.py` | Executed here, full rerun. Conflict in `undo` only, and the `_stack` break above |
| 955098a to 9009865, pyset-order | `satassume/theories/transfer.py`, `transfer.rs`, `pyset.rs` removed | Executed here, full rerun. The `_common` precedent doesn't apply: these runs execute this diff |
| 9009865 to b45b72f, slice B | `term_live.py`, `rust_plugin.py`, `term/py.rs`, `term/relations.rs` | Executed here, full rerun. Clean rebase |
| b45b72f to 089c70d | `results/port-4b.md` only | Nothing executed, so no rerun. Tested SHA and landed SHA differ by that file and this report |

Earlier runs aren't evidence for the landing source: `a176a45` was stopped before its plants finished, and `51fda6d` and `09d3d7a` each ran the full job on a base that has since moved.

**One failure class moved in one run, and not on the landing source.** On `09d3d7a`, `suite_report.py` gave 45 re-entry and 2 other on head, against 46 and 1 on its base, with 0 outcomes changed. The test is `tests/test_lra_fuzz.py::test_fuzz_entails_and_implied`, which fails on both. In that run the test file's 120s watchdog (`tests/test_lra.py:540`, `no answer within 120s`) fired while Hypothesis was generating a case, and it surfaced as `FlakyStrategyDefinition`. Alone, 3 runs on each tree failed on `Already mutably borrowed` with no timeout, and the landing source's full run gives 46 and 1 on both sides. That job was running plants and fresh alongside two suites, so I read it as load, not measured beyond that. Output: `land3/retest/` on pareto1.

`HANDOFF-sa-port-61.md` lands, because `rust-slice` keeps earlier handoffs.

## Not run

- Moved to the backend PR list by the landing bar: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control, the boundary rescore and suite column, the final drop score and its lost rows, the suite split with Python's counter, `order:_rows`' evidence (not caught meanwhile), the `_forms` guard test, history and seed reruns, forced moves, the native path, and timing.
- Also not run: the suite with the shadow on, a suite column for the plants, the other `common-` plants, corpus fresh and leak, shuffled orders, and the quiet recount on `value`, `rootof` and `rows`. A Python-side suite on this source: `suite_report.py`'s Python column is `pareto1:~/sp51/out/land/suite-python`, from 1b's source.
- Machine: x86-64 only for the landing runs. orion (aarch64) ran the units and dev only.

## Standing rulings

- **Kept on Python with a reason:** `I` and `-I` in Pow's shapes; `Float`, `oo`, `-oo`, `nan` and the `zoo` case of `constant_value`; Sum, Product, Integral; queries under a non-default registry; R9 `enclose`.
- **Test-plugin shim, not a port:** the `_n_conflicts` view in `rust_plugin.py`, with the 64 tests it moved.
- **A public-API version of `test_incremental_matches_fresh`** and its family is still due during the engine port, at the latest.
- **Mutants 2, 5, 6, 7, 9 rest on the API fuzzer alone.** 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- **Section 8's limits still stand on the base:** PR 328's fuzz history and censuses aren't read, and suite2 is a floor.
- **Heuristics:** the port adds none.

## What changed

- `solver_rs/src/rows.rs`, new; `lib.rs`, its registration.
- `knowledge_live.py`: the install block for `generator` and `constant_value`, the shadow's comparison, and undo.
- `knowledge_fresh.py`, `knowledge_rows_wl.py`: the `rows` workload.
- `rows_cmp.py`: the direct comparison.
- `mutate_knowledge.py`: 9 plants, a `rows` workload column, and a `rows_direct` column.
- `test_knowledge_rows.py`: 51 tests, outside `tests/`, so the suite gains no id.
