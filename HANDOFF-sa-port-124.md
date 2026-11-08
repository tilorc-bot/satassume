# HANDOFF sa-port-124: step "scope" (issue 323), scope.py whole on Rust

Branch `port/scope` in /home/tilo/dev/sa-port-7, from rust-slice 2ee0c8c. The code commit is **d7b6d4d** (pushed). The bar hasn't run.

## Done
- `solver_rs/src/scope_core.rs` (new) holds the six port rows: `Scope` (`ScopeRs` pyclass, :42; it keeps a 3-tuple's protocol: fields by name, index, slice and unpacking, `==`/hash as a tuple, so it equals Python's NamedTuple and a plain 3-tuple, plus repr, `_fields` and `_asdict`), `_custom_pred` :143, `linked_terms` :167 (frozen with `frozenset(set)`, so iteration order is Python's), `scope_of_atoms` :201, `extension_atoms` :240, `theory_scope` :281, `scope_install` :311 (it returns the Rust `EMPTY`).
- Callbacks into Python, each read from scope's globals at call time and counted:
  - `scope:cb_atoms_of`: Formula input. The formula step moves it.
  - `scope:cb_affine_pair`: C1's term_live wrapper over `PyTermTable.affine_pair`.
  - `scope:cb_transfer_wanted`: `sa_solver.transfer_wanted` on the default backend.
  - `scope:cb_facts_for`: the user's registered extensions.

  `_is_number` is relations_core's `free_is_number` (`rel:py_is_number` on fallback). `glue_atoms` is relations_core's `rel_glue_atoms`.
- Counters: session.rs NAMES :39-41 and constants 122-131 (:168-177), so COUNTS has 132 entries.
- Plants 90-95 (relations_core.rs :139-144, names :244-249): `scope-linked-empty` (Scope's getter), `linked-no-rel`, `scope-no-affine`, `theory-no-assume`, `custom-never`, `ext-shallow`.
- Wiring: session_live.py `_SCOPE_FUNCS` :692, `_SCOPE_IMPORTERS`, `_SCOPE_PLANTS` :701, `_install_scope` :706, called at :772 only when `_install_relations` ran (needs its hooks; `SLICE_SCOPE=py` keeps Python's). It patches:
  - scope's attributes, plus `EMPTY`;
  - engine.py's by-name `Scope`, `_EMPTY_SCOPE`, `scope_of_atoms` and `theory_scope`;
  - sympy_api's `_theory_scope`;
  - the `EMPTY` default arguments of `Session.__init__` and `Engine._fresh_session`.

  ref.py stays Python's, as for `_REL_FUNCS`. The from_env plant check is at :812.
- term_live.py:365 adds `term:no-query:<site>` beside `term:no-table:<site>`, so a no-table count can be split into "outside any query" and "inside a kept query".
- `test_scope_core.py`: `funcs` (:43) runs Python's and then Rust's version of each item, call by call. Each side is whole: nested wired names are Python's while Python's version runs. Order is compared too. It runs on test_relations_core's queries, the extra queries, and hand-built custom predicates two levels deep, through `theory_scope` and `Engine.ask`. Locally (orion): 7 passed. `bad` is empty, every `scope:*` counter fires, and each of the 6 plants fires and is caught by `funcs`. tests/test_scope.py, test_ref.py and test_p3_review2.py with `rust_plugin` and `handler_count`: 71 passed, 0 handler rows.

## Facts found
- 5c5's dev run (pareto1 sa-port-122/bar-5c5/live/dev-rust.knowledge.json) shows `term:no-table:affine_pair` 9 and `_is_number` 63, with `kept:out-of-scope` 24. On fuzz both are 0. So C1's `affine_pair` ran Python's body 9 times on dev, apparently inside queries that conversion keeps on Python (the ruled case). The new `term:no-query:` counter checks this on the bar's dev run. If it isn't 0, scope.py's Python runs per query outside the ruled case, and scope.py doesn't count whole.
- term_live's `linked-drop` plant (C1, on the `scope.linked_terms` wrapper) is now superseded: Rust's `scope_of_atoms` doesn't call the module attribute. Name it void-by-move in the report. `linked-no-rel` replaces it.

## Left
1. The bar on pareto1. The config is 5c5's (`~/sp19/sa-rust-ids-work/sa-port-122/bar-5c5/config.txt`) with these changes:
   - BASE = `~/sp19/sa-rust-ids-work/sa-port-122/bar-5c5/suite`;
   - PLANTS = the 6 scope plants;
   - TESTS = 5c5's TESTS plus `test_scope_core.py`.

   WLS=loop, SUITE_PLANTS=zero, DIRECT and N stay as they were. Then `PUSH=1 sh rust-spike/slice/p1/bar.sh land TESTED_SHA`.
2. REACHED-CODE: `custom-never` and `ext-shallow` probably fire 0 or MATCH on dev and fuzz (no custom predicates there). If so, bring a live.py workload built from `test_scope_core._custom` (custom predicates whose facts hold relation atoms), give it to WLS, and show the plants caught there.
3. Write results/port-scope.md in port-5c5.md's form. Update port-ownership.md:84-85 and :135 and the TSV's scope rows. Write the module count under the count rule. Then `agent report`.
