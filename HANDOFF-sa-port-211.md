# HANDOFF sa-port-211 (state step part 2, rest of (iii)): (iii)(a) done on the branch, unbarred; (iii)(b), (c) open. Issue 323

## Done (port/state-relations-iii, pushed; head = the commit carrying this file, code at e025aa5)
- f7e5f24 relation_atom dispatches itself (planner Q1, ~14:55 9 Nov, addenda/sa-port-relation-atom-handler-ruling.txt):
  satassume/relations.py `RELATION_ATOM_IMPL` slot read at call time by `relation_atom`; Python's body is `_relation_atom_py`.
  term_live's install fills the slot and still replaces the module attribute (for `__wrapped__`); undo empties it.
  Test `test_term_ids.py::test_a_name_imported_before_install_dispatches` (imports first, installs after) fails with the slot
  ignored (0 == 0 + 1), passes with it.
- e025aa5 int foreign leaf: `Kind::PyInt` (term/table.rs Kind), `TermTable::py_int` (term/algebra.rs, after `number`),
  sort_key for PyInt = Integer's of the value (algebra.rs sort_key), eq_sides doesn't strip an int side (term/relations.rs
  eq_sides), under_apps skips it (relations.rs under_apps), py.rs `py_int`. term_live.py: `_INT_SITES`, `_int_id`, `q.ints`
  /`q.int_ids` (kept apart from derived/rev), `_obj` reads q.ints, wrappers `_is_number`/`_under_apps`/subterms accept an
  exact int. The 'link' site still counts term:unknown:link:int (127 on scope) and gets no row: nothing in relations.py is
  called for it (probe), so left alone.
- Plant 265 `int-as-number` (bar channel SLICE_SESSION_PLANT; term_live from_env), counter 346 `term:int:<site>`.
  On scope (orion, ~/sa-rust-ids-work/sa-port-211/plant1): plant DIFFER (end 2, stream 2, stats 169, answers same), unplanted
  Rust MATCH against Python. Plant fires: term:int:relation_atom 385, _is_number 384, _under_apps 11.
- Module-wide relations.py probe at e025aa5 (orion, ~/sa-rust-ids-work/sa-port-211/pyc/all1, summ.py): 0 converted calls on
  dev, fuzz, zero, loop, cert, budget; scope 385, every one the frame of `relations.relation_atom` itself, the dispatch to
  Rust's wrapper (callers: scope_wl.py:29's extension via extensions.py:180 facts_for; cal/ in that dir). Before: 397 + 392
  + 385 + 11 + 8 + 4 (sa-port-211/pyc/dispatch, int1, int2 show the steps). answers_sha unchanged on all seven.
  OPEN QUESTION for the planner (not asked yet; put it in the report): does the dispatch frame count as public entry (user
  code's call, two lines, no term work), or must relations.py read literally 0?
- Tests: test_term_ids.py 172 passed on both backends; tests/test_relations.py, test_eq_canonical.py, test_zero_glue.py,
  slice test_scope_core/test_query_core/test_relations_core/test_glue_plain/test_compile_loop_core pass. test_term_live.py:
  2 fail (`_Mark` has no `facts`: regrown_past_the_mark, what_was_there_before_the_run) on the tree without these commits too
  (5c10a's Rust-native fact cache); not in the bar's TESTS list. Not chased.

## Not done
- The bar for (iii)(a): not started. At 15:00Z S2's bar had ended (14:54) and sa-port-210 is to land S2, then the harness fix
  (sa-port-209) lands; a full bar from here would block those landings (rule [91]). Week 89% at 14:29, 90% between 16:04
  and 18:09: if 90% has passed, push only and go on the closing list.
  Bar config: copy ~/sp19/sa-rust-ids-work/sa-port-207/run-bar-iii1b.sh on pareto1, OUT under sa-port-<you>, BASE = the
  iii1b bar's suite (~/sp19/sa-rust-ids-work/sa-port-207/bar-state-relations-iii1b/suite), PLANTS += int-as-number, same
  WLS (scope must be in it) and TESTS. Rebase on origin/rust-slice first (S2 and the harness fix will be there).
- (iii)(b) Relations' dicts to Rust-native state: untouched. rel_init relations_core.rs :2038, census HANDOFF-sa-port-205.md.
- (iii)(c): done for (a)'s part (above); rerun after (b).
- results/port-state-relations.md, TSV owners, port-ownership.md: unchanged.

## File:line (e025aa5)
- satassume/relations.py: RELATION_ATOM_IMPL :515, relation_atom :518, _relation_atom_py :526.
- term_live.py: _Query slots :74, ints :81; term_id :286 (int branch inside); _INT_SITES :382, _int_id :385; _relation_atom
  wrapper :413; _obj :482; install's py_disp/py_atom :982, undo :1009; from_env plant channel :1051.
- solver_rs/src/term: table.rs Kind (PyInt last); algebra.rs py_int (after number), sort_key PyInt branch; relations.rs
  eq_sides (int_side), under_apps (PyInt skip); py.rs py_int (before neg).
- test_term_ids.py: test_a_name_imported_before_install_dispatches; INT_SIDES and the three int tests at the end.
- Probe: ~/sa-rust-ids-work/sa-port-211/pyc/{run.sh,summ.py,callers.py}.
