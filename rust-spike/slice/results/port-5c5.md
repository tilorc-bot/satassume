# Step 5c5: relations.py whole in Rust (issue 323)

## What moved
- **The five methods 5c4 left** (sa-port-118, f99a2e4): `Relations._adapter`, `_atom_selector`, `_atom_var`, `_note_sides`, `_eq_links`, in `solver_rs/src/relations_core.rs`, wired in `session_live.py` `_REL_METHODS`. Why 5c4 left them: port-ownership.md:76-77 gave them to 5c4 as "called back" rows, not as moves, and 5c4 moved only its "Python" row (:75).
- **relations.py's module functions** (sa-port-119, f6c2b78; wired here, 3b4e0c5): `zero_args`, `under_of`, `zero_twins`, `glue_atoms`, `sympy_atom`, `_own_term`, `_number_basis`, `_number_facts`, `_guarded_adapters`, `_terms_of`, `link_objects`, `closed_units`, `with_closed_units` (pyclass `ClosedUnits`), `default_specs`, `_missing` and `relational_name` are pyfunctions. `session_live.py` `_REL_FUNCS` patches the module attributes, plus the by-name imports in engine.py (`zero_args`, `under_of`, `glue_atoms`, `link_objects`), scope.py (`glue_atoms`) and sympy_api.py (`relational_name`). `undo` restores all of them. `_constant_term` has no pyfunction. Its one caller, `_share`, runs in Rust and uses Rust's own copy. Rust's internal calls to `sympy_atom`, `_own_term`, `_number_basis`/`_number_facts` and `_constant_term` are direct (`rel:cb_constant_term` is 0 in the suite).
- **Left Python's on purpose:** ref.py's by-name imports (`glue_atoms`, `_is_number`), because ref.py is the reference engine. Its call-time imports of `closed_units` and `default_specs` (ref.py:299, :544) read the module and so get Rust's. An Engine built before install keeps Python's `with_closed_units` closure.
- **Kept as types, with nothing to run:** `AdapterSpec` and `Uninterpreted`.
- **Correction to sa-port-118's finding:** `_termwise` is in Rust (`PyTermTable.termwise`, term/relations.rs:110, a5f4590, slice B), reached through term_live's wrapper (term_live.py:650). `rel:cb_termwise` counts that hop. port-ownership.md:70 stands.
- **relations.py now counts whole:** every port row is Rust, and the two declarations are kept as types. port-ownership.md:75-79 and the TSV are updated. 5c4's eight rows, which 5c4 left at "Python", now read "landed 5c4 064a1b4". Session counts whole at 5c6 and engine.py at 5c10. scope.py gets its own session after 5c5. The adapters step comes next and wasn't started.

## SHAs
Tested **3b4e0c5**: port/5c5 rebased on rust-slice 7e2ece0 (6f's landing; the rebase was done before testing). Rows are on pareto1 at `~/sp19/sa-rust-ids-work/sa-port-122/bar-5c5/` (`sum.txt`, `commands.txt`). The `.so`'s sha256 is c755bd75…, and the base is 5c4's suite rows (`sa-port-115/bar-5c4/suite`). The landing source is the commit carrying this file. Between it and 3b4e0c5 are only this report and port-ownership.md/.tsv: docs, which no run executes. The incoming diff at landing was empty: rust-slice was still 7e2ece0.

**6g(a) meeting point (planner ruling, sa-port-6g-parts-ruling.txt):** `with_closed_units` wraps `engine.clause_templates`, which 6g(a) replaces. 5c5 lands first, so 6g(a), landing second, shows the lra-on path MATCH.

## The bar (sa-port-122/bar-5c5)
1. **Suite by id against 5c4's rows:** 5,958 passed, 126 failed, 23 skipped, 18 xfailed, 6,125 ids. New 0, gone 0, changed outcome 0. Passed: 5,957 with no firing and 1 with a firing (`test_ci_stream_reports_only_what_replays`). S's standing: S's gate is met except for the 46 named stub failures, one cause.
2. **Fresh dev, fuzz and loop:** answers and state MATCH, with every control MATCHing. Answers are unchanged: dev 31cd0945c07f02a6 (1,985 q), fuzz 173502b6ef285ad6 (3,000 q), loop 09238b2537e54383 (420 q). Rust runs made 0 Python solvers.
3. **Plants:** see the table below. 19 of 20 are caught, and one is void (`constant-term-never`).
4. **Quiet handlers, suite:** 39 rows in 2 tests, the same multiset as base:
   - `_consistent` AttributeError: 34 on `_ok` and 4 on `_rb_clauses` (the named needs-internals case);
   - `Engine._build_context` "Already mutably borrowed": 1, in `test_protocol_on_fuzz` (the 46-stub cause).

   `caught` rows per id match base. **Quiet catches at engine.py:1906: 1**, in the suite, as on base. There are 0 on dev, fuzz and loop: the 12 handler files have 0 rows, and so do all 40 dev/fuzz plant handler files. TermFault 0.
5. **Known differences in answers or read state:** none. Tests: 503 passed (5c4's ten files, with the new direct tests), and `relations_direct.py` exited 0.

## Plants (fired; D = DIFFER)
| plant | item | dev | fuzz | loop | caught by |
|---|---|--:|--:|--:|---|
| adapter-fresh | _adapter | 3,162 D | 80,339 D | 0 | dev, fuzz |
| selector-no-memo | _atom_selector | 50 D | 1,831 D | 0 | dev, fuzz |
| atom-var-skew | _atom_var | 324 D | 22,269 D | 0 | dev, fuzz |
| drop-note-sides | _note_sides | 872 D | 22,438 D | 0 | dev, fuzz |
| drop-eq-links-zero | _eq_links | 30 D | 94 D | 0 | dev, fuzz |
| own-term-false | _own_term | 548 D | 7,013 D | 0 | dev, fuzz, run test |
| basis-all | _number_basis | 2 D | 6 D | 0 | dev, fuzz, funcs |
| sympy-atom-swap | sympy_atom | 121 D | 1,941 D | 0 | dev, fuzz, run test |
| closed-units-none | closed_units | 6 D | 1 D | 0 | dev, fuzz, run test |
| with-closed-skip | with_closed_units | 231 D | 326 D | 0 | dev, fuzz, run test |
| specs-no-euf | default_specs | 1,222 D | 2,999 D | 385 | dev, fuzz, run test |
| zero-args-empty | zero_args | 872 | 775 | 338 | funcs |
| guarded-none | _guarded_adapters | 226 | 11,684 | 0 | funcs |
| terms-of-no-order | _terms_of | 393 | 19,981 | 0 | funcs |
| link-objects-bare | link_objects | 183 | 9,142 | 0 | funcs |
| under-of-empty | under_of | 0 | 0 | 0 | suite (39 changed), funcs |
| glue-no-twins | glue_atoms | 0 | 0 | 0 | suite (43 changed), funcs |
| relname-swap | relational_name | 0 | 0 | 0 | suite (9 changed), funcs |
| zero-twins-first | zero_twins | 0 | 0 | 0 | funcs (fired 4,013 in the suite, 0 changed) |
| constant-term-never | _constant_term | 0 | 0 | 0 | **void** |

"run test" is `test_relations_core.py::test_dropped_clause_is_seen`, and "funcs" is `test_module_function_plant_is_seen`. `funcs` runs Python's and Rust's version of each wired function on the same arguments, call by call: on the run's queries, on queries with zero atoms under applications, on hand-built twin atoms, and on `_number_basis`/`_number_facts` over twelve constants. It's in the repo, it compares Python against Rust, and each plant there fires and is caught.

**Fired but MATCH on dev and fuzz** (zero-args-empty, guarded-none, terms-of-no-order, link-objects-bare): the workloads reach the code, but the dropped result doesn't change a clause or an answer. `terms-of-no-order` only changes the budget cone's estimate. `guarded-none` and `link-objects-bare` feed the relevance cone, which the stream doesn't see. `funcs` catches each of them on the function's result. The suite wasn't run under them, because `zero` selects only plants that fire 0 on both workloads.

**Void:** `constant-term-never`. `_constant_term` runs 127,530 times in the suite but is never true at `_share`: no adapter pair shares a closed constant. LRA's shared terms never include one (probed on four queries with `pi` and `sqrt(2)`). The dummy and order adapters in `test_relations_core.py::_constant` don't either. Nothing catches it. The branch is a Python removal candidate, to check with Python's own runs, or else a workload is owed with an adapter that shares constants. All 20 plants are void on loop except `specs-no-euf` and `zero-args-empty`, which fire there and MATCH. Loop reaches no `Relations` method.

## Reached (and by which workload)
Suite counters (sum of 9 worker files): own_term 109,980, constant_term 127,530, number_basis 21,637, sympy_atom 621,019, zero_args 394,738, under_of 87,473, zero_twins 167,860, glue_atoms 165,895, guarded_adapters 142,080, terms_of 261,474, link_objects 148,922, closed_units 1,310,324, with_closed_units 1,300,528, default_specs 54,965, relational_name 1,315, adapter 782,630, atom_selector 56,995, atom_var 304,467, note_sides 144,170, eq_links 32,809.

On dev and fuzz, each item whose plant fires is reached there: the 15 in the first two groups of the table. The dev/fuzz counter files weren't summed in this report. `under_of`'s non-empty case, `zero_twins`' twin case, `glue_atoms`' twins and `relational_name` are reached by neither dev nor fuzz. The suite and `funcs` reach each of them, and both catch the plants (except `zero-twins-first`, which only `funcs` catches). **Owed (REACHED-CODE):** a live.py workload for these four, if the planner wants one beyond `funcs`. It would be queries with a zero atom under an application, which is 5c4's owed `drop-prep-twins` workload, plus SymPy relationals given to `ask`.

## Owed-list additions
- `constant-term-never` is void: either a Python removal candidate (the `_constant_term` skip in `_share`) or a workload with an adapter that shares closed constants.
- A live.py workload for zero twins under applications and SymPy relationals, which covers 5c4's `drop-prep-twins` too.
- Unchanged from 5c4: drop-twins-var and drop-lo-discover (Python removal candidates), drop-lo-memo's wrong-value plant, and the real-EUF sharing case for tests/test_relations.py.

## Not run
Moved to "before any backend PR", and none quoted as met:
- the mutant 2, 5, 6, 7, 9 rerun and mutlive's control;
- the boundary rescore and suite column;
- the final drop score and its lost rows;
- the suite split with Python's counter;
- `order:_rows`' evidence (not caught meanwhile);
- the `_forms` guard test;
- history and seed reruns (seed1 not run);
- forced moves;
- the native path;
- timing.

Also not run: the suite under the 4 plants that fired but MATCHed on dev and fuzz (`zero` doesn't select them; `funcs` catches them).

Other notes:
- Mutants 2, 5, 6, 7, 9 still rest on the API fuzzer alone. 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run.
- **Speed not measured.**
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- The public-API `test_incremental_matches_fresh` family is still owed: a test-only step before 5c7 (pure Python first, adds only, and a Python failure is a finding against main).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals (patch on moved `_share`/`_trichotomy`; replaced by `test_relations_core.py::test_sharing_is_needed_and_works`). This step doesn't touch it.
