# HANDOFF sa-port-222 (state step part 2, rest of (iii)(b)): sets DONE (5b8e09b); 15 dicts WIP; 5 lists not started. Issue 323

## Done, on port/state-relations-iii (unbarred, unlanded; rust-slice still c822173)
- 5b8e09b: the nine sets. The 3 test_relations_core failures were rk_key needing hooks under SLICE_REL=py (relkeys.rs: keys go
  by hash when `rel_install` hasn't run). Plants 269-277 `rs-<set>-drop` in `_REL_STATE_PLANTS` (relations_core.rs rel_plant).
  test_rs_core.py, 12 passed: digest equal at the switch 731834d3b9911a01 (469 queries: transfer:7:60, transfer2:3:40,
  fuzz[:200], scope); no set misses a class join; record method; each of the 9 plants moves it (`_bounded` is reached by no
  workload, see port-c2b.md, so it's driven by a direct `_guard` call).
- **Float/Integer gap CLOSED:** this SymPy has `Float(2) != Integer(2)`, but a Python set joins `2`/`Integer(2)`,
  `2.0`/`Float(2)` and `True`/`S.true`. relkeys.rs `is_joinable`: SymPy Number, BooleanAtom and Tuple key by hash, never by term
  id. Guarded by test_rs_core.py::test_no_set_misses_a_class_join plus the seeded record case.
- rk readout (test_rs_core, Rust): transfer:7:60 input 94 / engine 390 / term 1768; transfer2 140/376/1498; fuzz:200 67/919/3935;
  scope 0/191/564. **rk:outlive 0 and rk:migrate 0 on all four** (no session met a second query table). The bar's counts.txt
  will have them per workload, since the counters are in session_counts.

## WIP commit (after 5b8e09b): the 15 dicts, builds, NOT checked beyond the line below
RD_NAMES (session.rs, after RS_*): adapters, status, _guards, _link_lt, top, link_sel, atom_sel, num_sel, _roles, _info, _link_of,
_tv, _tsrc, _xside, _xheads. They're held per Relations in `RelS.d: [OrdMap; 15]`. relkeys.rs `OrdMap` is an in-crate
insertion-ordered map with Python dict order (the crate has no `indexmap`, and none is fetched offline). Keys come from RelKeys;
values stay Python objects.
- relkeys.rs (end of file): RD_ORIGIN, RD_PLANT0 = 390 (`rd-<dict>-drop`, 390-404, wired in rel_plant; NOT yet in
  `_REL_STATE_PLANTS`), SessionCore rd_get/rd_set/rd_del/rd_len/rd_clear/rd_items, `RDict` (Core | Py: get_item/get/item/
  set_item/contains/len/is_truthy/clear/items/values) for Rust sites, and the `RelDictView` pyclass (the full mapping protocol).
- session.rs: counters 520 rd:core, 521 rd:view, 522 rd:record (NAMES and COUNTS now 523; 423-519 reserved); pymethods
  rd_field / set_rd (record method for `rel.X = d`) / rd_snapshot (test-only); RelS values visited in __traverse__.
- relations_core.rs: rel_init `pdict` (has core: no Python dict); every dict site goes through `RDict::of(rel, RD_*)`
  (grep `RD_`); `top = self.top; self.top = {}` -> keys taken, then `clear()` (~:2338); `mergeable` takes `&RDict`.
  session_glue.rs :262-342 the same.
- session_live.py `_rel_dview` / `_REL_DVIEWS` before `_node`, installed with the others.
- Check (orion ~/sa-rust-ids-work/sa-port-222/t3): test_relations_core, test_rs_core, test_relc_core, test_query_core,
  tests/test_scope.py: **130 passed, 1 failed**: test_relations_core.py::test_same_core_python_methods_match (SLICE_REL=py over
  a core: 19 cases differ, first 'congruence'). Cause not read. Suspects: a Python reader in relations.py doing something the
  view does differently (e.g. `self._xheads.setdefault(k, [])` then mutating, `dict.get(k, default)` with a falsy value,
  `self.top` being reassigned then iterated, or iteration of `_xside` keys while it grows).

## Not done
1. Fix that failure. Add `rd-*-drop` to `_REL_STATE_PLANTS`. Write a test_rd_core.py (copy test_rs_core.py, using
   rd_snapshot, with items in insertion order, since `_xheads` is iterated). Show the digest equal at the switch and each plant
   moving it.
2. The 5 lists: queue, _pending_links, _xextra, _xpend (rel_init :2087-2125), and specs (keep as conversion? decide and name it).
   sharing is already a Rust pyclass (transfer_py.rs:259).
3. Readers: engine.py :1088-1129, :1177 and ref.py :408/:416 now read the views (RelDictView); confirm they're read-only use.
   Tests reading internals (test_relations_core `_rel_state` :278, test_query_core, test_switched_glue, test_verify_integration)
   go through the view or onto needs-internals.
4. (iii)(c) probe on the landed SHA; the bar; TSV owners; results section; report.
