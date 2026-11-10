# HANDOFF sa-port-221 (state step part 2, rest of (iii)(b)): (iii)(a)+(b) first move LANDED c822173; RelKeys + 9 sets WIP. Issue 323

## Landed
- Tested 022630c (bar pareto1 ~/sp19/sa-rust-ids-work/sa-port-217/bar-state-relations-iii-ab, clean); landed c822173 on
  rust-slice 06:09Z 10 Nov (report 5a3c218). Incoming diff db7130a..rust-slice: empty. Landing source = tested +
  HANDOFF-sa-port-217.md + harness/state.py (+2: `RELATION_ATOM_IMPL` in MODULE_CONFIG; fixes the bar's one new failure
  test_history.py::test_module_state_inventory_is_classified; passes on Python and Rust, orion).
- The other changed id, test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence, is the known
  id()-reuse failure (a28c548).

## WIP commit (after c822173, UNTESTED beyond the check below, NOT for landing as is)
RelKeys and the first 9 containers, the sets (`RS_NAMES`: linked, _bounded, _user_eq, _xpairs, _aux_eq, _link_eq, _xpart,
_xcounted, _xcand), per the RelKeys ruling. It builds. Check on orion (~/sa-rust-ids-work/sa-port-221/t1): test_relations_core,
test_query_core, test_relc_core, test_xfer_core, test_glue_plain, tests/test_scope.py: 126 passed, 3 failed, all in
test_relations_core.py (test_sharing_is_needed_and_works, test_same_core_python_methods_match,
test_a_patch_on_a_moved_method_reaches_nothing): a subprocess traceback through sympy_api._engine_ask :1131, cause not read.
Likely suspects: Python's own Relations methods (SLICE_REL=py over a core) writing `self.linked = set()` etc. in `__init__`
(the view's setter calls `set_rs_init` only for k == 0, so it re-inits all nine then; check order), or a reader needing a
set operation the view lacks.
- session.rs: `RelKeys`, `RelS`, `RS_NAMES`/`RS_*` after `RelC`; fields `relkeys`, `rels` on SessionCore; counters 350-358
  (rk:intern:input, rk:intern:engine, rk:term, rk:outlive, rk:migrate, rs:core, rs:view, rs:record, rk:dict:hit);
  pymethods `rs_field`, `set_rs_init`, `rs_snapshot` (test-only export), `rk_stats` before `relc_snapshot`; traverse/clear.
- relkeys.rs (new): `rk_key` (term id via `relations_core::term_of`, else intern by hash, counted by origin `RS_ORIGIN`;
  table switch or table after a tableless intern -> `go_dict_only`, counted rk:outlive/rk:migrate); `rs_init/rs_contains/
  rs_add/rs_len/rs_items`; `RSet` (Core or Python's set for a session with no core); `RelSetView` pyclass; plants
  `RS_PLANT0` = 269 + k (269-277; 278, 279 are the last in this step's range, so the other 21 containers need new plant
  numbers from the architect).
- relations_core.rs: rel_init skips the 9 Python sets when the session has a core and calls `rs_init`; every site of the
  9 sets goes through `RSet::of(rel, RS_*)` (calls rel.session + core_of each time; pass `c` directly later for speed);
  `mergeable` takes `&RSet`; `term_of`/`Linked` pub(crate); `Hooks::term_live()`.
- session_live.py: `_rel_sview`/`_REL_SVIEWS` before `_node`; installed beside `_REL_CVIEWS`.
- Not done for the sets: plant names in `_REL_STATE_PLANTS`, a test_relc_core.py-style digest test (`rs_snapshot` vs
  Python's sets), rk/rs counter readout per workload, the sessions that outlive their query (read rk:outlive per workload).
- Known exactness gap to name or close: a Python set joins `==`-equal objects of different classes (Float vs Integer); a
  term-id key and an id-less equal key of another class get different RelKeys keys. Needs a whole-tree check + guard test, or
  a fix, under the state rule.

## Not started
The 21 dicts/lists (IndexMap<u32, V>), adapters (ad:cb_factory), views for engine.py :1088-1129/:1177 and ref.py :408/:416,
(iii)(c) probe on c822173, the bar.
