# HANDOFF sa-port-118: 5c5 part one (the five methods) at f99a2e4, bar running on pareto1; module functions not started (issue 323)

Clone /home/tilo/dev/sa-port-7, branch port/5c5 (pushed), from rust-slice 064a1b4 (5c4's landing).

## Running
The bar on f99a2e4, started 01:18Z: `machine run pareto1 --shared` (orion PID 626672, `~/sa-rust-ids-work/sa-port-118/bar-5c5a.machine.pid`,
launcher log `~/sa-rust-ids-work/sa-port-118/bar-5c5a.launch.log`). **Wait for `pareto1:~/sp19/sa-rust-ids-work/sa-port-118/bar-5c5a/done.txt`**
(about 20 min), then read its `sum.txt`. Config: BASE = sa-port-115/bar-5c4/suite (5c4's rows), PLANTS = adapter-fresh selector-no-memo
atom-var-skew drop-note-sides drop-eq-links-zero, WLS=loop, SUITE_PLANTS=zero, TESTS = 5c4's ten files, DIRECT = `relations_direct.py 300 0`.
It tests the five methods only. The module functions will need their own bar run after they move.

## Done (f99a2e4)
- `_adapter`, `_atom_selector`, `_atom_var`, `_note_sides`, `_eq_links` (relations.py:992, 1317, 1325, 1475, 1654) run in
  relations_core.rs ("step 5c5" section, before `register`), wired in session_live.py `_REL_METHODS` (SLICE_REL=py keeps Python's).
  Containers stay Python's. `_fresh` and `session.table.var` are called by name. `_eq_links` uses `c.var_direct`/`c.emit_direct` for
  `s.var`/`s.emit`, as `rel_trichotomy` does, builds `p - q` with SymPy's `-`, and calls Python's `_termwise` back (counted `rel:cb_termwise`).
- Counters `rel:adapter`, `rel:atom_selector`, `rel:atom_var`, `rel:note_sides`, `rel:eq_links`, `rel:cb_termwise` (session.rs 90-95).
  On test_relations_core.py `run`: 812 / 53 / 310 / 133 / 24 / 18.
- Plants (relations_core.rs 70-74), one per method, in `test_dropped_clause_is_seen`: each fires and moves a case. orion:
  test_relations_core.py + test_query_core.py 87 passed.
- `_adapter` was ported, not deferred: it's the dict memo around `spec.factory()`, so it isn't only the adapter boundary.

## Why 5c4 left the five
port-ownership.md:76-77 gave them to 5c4 as "called back" rows, not as moves, and 5c4 moved only its "Python" row (:75).

## Finding for the record
port-ownership.md:70 lists `_termwise` as "landed B b45b72f", but b45b72f is a report-only commit, and no Rust code implements `_termwise`
(rg finds it only in relations.py and tools-rust/coarse.py). It is still Python, now counted as `rel:cb_termwise`. The module-function step
should port it or record it as kept on Python, with the reason (it reads SymPy's `Add.make_args`, negation and `is_finite`).

## Left for 5c5
Module functions, port-ownership.md:78-79 (15 "Python" and 4 "called back"): `AdapterSpec` :379, `_missing` :385, `closed_units` :395,
`with_closed_units` :423, `default_specs` :435, `Uninterpreted` :456, `relational_name` :542, `sympy_atom` :550, `zero_args` :595,
`under_of` :607, `zero_twins` :630, `glue_atoms` :659, `_constant_term` :692 (called back from `rel_share`, `rel:cb_constant_term`),
`_number_basis` :698, `_number_facts` :752, `_own_term` :761, `_guarded_adapters` :1922, `_terms_of` :1935, `link_objects` :1970.
Also `_termwise` :673 (above). The `.add_function` list and `register` are at the end of relations_core.rs. Plants go in `rel_plant`'s
match plus session_live.py `_REL_PLANTS` (:448). Note that b8dda68 added `drop-share-tri` there, so check the tuple's tail before editing it.
