# HANDOFF sa-port-245: state part 3. Gate item (i) done (scope fixed, 4d14638); items (ii), (iii), (iv) open

Branch port/state-part3, head = this commit, on origin/rust-slice 0192b35 (unchanged when checked 17:03Z 10 Nov).
Handed off between items, as the gate asks, at the context budget. Read this first, then HANDOFF-sa-port-242.md
(digest, probe table) and HANDOFF-sa-port-241.md (file:line map of the containers).

## Done (sa-port-245): gate item (i), commit 4d14638
1. Bisect. Worktrees at d8f9146, 0414c4f and 02354d4, each built, `live.py scope py|rust --check entry` with
   SLICE_MOVED=0, livecmp: all three MATCH with 171 sessions. So the cause is 7a18df2 (containers).
   Output: orion:~/sa-rust-ids-work/sa-port-245/bis/{d8f9146,0414c4f,02354d4}.cmp (worktrees removed).
2. Cause. It was Rust's behaviour, not Python's, so no question went to the planner. scope_wl's custom fact
   `relation_atom('lt', s, 1)` passes the Python int `1`: `Session.demand` holds the int, `Relations._xside` holds
   SymPy's `One`. 7a18df2 keyed the session's dicts by `rk_key` (the session's RelKeys ids), so a session dict and a
   Relations dict shared one object per equal class (`1 == One`, equal hashes; the first one interned wins, here the
   int). `_xside` then gave back the int, `_transfer_terms` (relations_core.rs:1778) saw no `Rational`, and
   `_number_basis(1)` with its `is_many` session (14 queries, 14 searches, 1 session) was lost. Reproduces with query 5
   alone in one second; counters on that query, 02354d4 against 7a18df2: rk:intern:input 4 -> 5, rel:number_basis 2 -> 1,
   ent:is_many 2 -> 1, link:calls 38 -> 72.
3. Fix (ses_cont.rs). `pending`, `pending_c`, `demand`, `literals`, `_groups` are `SesDict`: an insertion-ordered map
   keyed as a Python dict (`hash()`, then the same object or `==` with the held key on the left), each dict holding the
   key object first set in it. Nothing there reads or writes RelKeys; `_groups`' None and True need no reserved keys;
   no borrow is held while `__hash__`/`__eq__` run. relkeys.rs is (iii)'s again (`OrdMap::pop_last` removed; no diff
   against origin/rust-slice). Condition 2: nothing stopped on.
   - Counters 568 `sc:key_hash`, 569 `sc:key_eq` (calls into Python on a key). NAMES and COUNTS are 570 long.
   - Plant 446 `sc-key-shared` (SB_PLANTS index 15): `sd_set` also interns the key in RelKeys, the old fault.
     Caught by workload scope (session_count_diff 1, stats_diff 164, the original picture) and by
     test_session_boundary.py's keys case.
4. Second scope difference, found by the digest once the first was gone (moved_q, query 0, `eng0:splits`): an opaque
   split. Python's `_Split.__init__` returns at the first opaque conjunct, leaving `comps`, `parts`, `consistent`
   unset; Rust's `Split` gave `comps == []` and `consistent is None`. relevance.rs (SHARED FILE, name it in the report):
   an opaque Split's `comps` and `consistent` getters raise AttributeError. Not from this branch (the landed Split);
   only the extended digest reads those fields. No reader in satassume or the slice reads them on an opaque split.
5. scope's row in known_moved.json (7 engine points), by known_moved.py from a run with no other difference.
6. Checked at 4d14638's tree: `live.py scope` Python against Rust, digest on: MATCH, 171 sessions, stats_diff 0,
   moved_diff 0 (orion:~/sa-rust-ids-work/sa-port-245/fix1/scope.cmp2); with plant 446: DIFFER (scope-p446.cmp).
   test_session_boundary.py 16 passed (new: test_each_dict_holds_its_own_keys; plant 446 in test_plant_caught).
7. Every slice test file, one process per file, on this tree: STARTED detached, not fully read.
   orion:~/sa-rust-ids-work/sa-port-245/slice-i/{summary.txt,end.txt,<file>.log}; tree.txt was written before the
   commit (same files). Read summary.txt by `rg -v "exit 0"`. Seen so far, all known base failures: test_cf_diff.py
   (collection error), test_catch_count.py (3 failed), test_handler_count.py (2 failed). test_term_live.py (2) is the
   fourth known one. Anything else non-zero is new and belongs to 4d14638.

## Not run (say so in the report)
- The other 15 workloads on 4d14638. Their known_moved.json rows were taken at e82147a, when the session dicts still
  interned in RelKeys; they should be unchanged (the rows are _SPLIT/_CACHE counts) but nothing shows it yet. The bar's
  workload run does.
- The suite, the full bar, the module-wide probe, memo cost, Group D.

## Not done: the gate's remaining items, each its own commit
(ii) core_of -> `_table_get`. Not started; no edit in the tree. Plan: session_live.py:183 `_table_set` also stores
   `self.__dict__['_core'] = view.core`; session.rs:923 `core_of` reads `_core` (a plain instance attribute, no Python
   frame) and falls back to `table.core`; compile_loop.rs:28 and discovery.rs:18 have their own copies of core_of, point
   them at session.rs's. Optional, same mechanism: a `table_of(s)` reading `_table_view` for the 11 other
   `getattr("table")` sites in compile_loop.rs (5), session_glue.rs (4: :89, :116, :353, :364), query.rs (2: :251, :313).
   relations_core.rs's six stay (condition 2) and are named. Then the module-wide probe (pycalls.py; command in
   HANDOFF-sa-port-241.md) and `_table_get` per workload; the before/after table is in HANDOFF-sa-port-242.md.
(iii) Container plants 439-445 in test_session_boundary.py, each caught or classified. The file's CHILD script has
   CASES :70, trunc :104 (a session cut by `escalate(1)`: the place where pending, pending_c and deferred are not
   empty), keys :148. Add per-container rows (keys with their class, values, in order) after `_build_context`, after the
   asks and in trunc before and after `escalate(1)`; `sc_snapshot` (session.rs:1806) against the views; a write through
   a view read back natively (sc:record); sc:core, sc:view, sc:record > 0; one child with SLICE_DISC=py SLICE_LOOP=py
   SLICE_GLUE=py. Plant 420 (test_engine_first_refused) is reported the same way.
(iv) Bar on the merged tree and land, as the gate says. Add to the bar's lists: plant sc-key-shared in PLANTS, scope
   in WLS. bar.sh:99 runs TESTS in one pytest process; slice files need one process per file (slice-i/run.sh does it).
   Group D in seconds (RULINGS.md line 12).
Also still open from the brief's TASK line: relations' reference held by the core; results/port-state-part3.md
sub-part 5 section (add: the scope cause and fix, plant 446, counters 568-569, the Split getters).

## FILE:LINE MAP (at this head; the rest is HANDOFF-sa-port-242.md's and HANDOFF-sa-port-241.md's)
- rust-spike/slice/solver_rs/src/ses_cont.rs: header :1-17 (the cause), :44 KEY_SHARED_PLANT, :54 SesDict, :86 sd_find,
  :116 sd_set, :221 enum Ses, :227 Ses::of, :626 snapshot
- session.rs: :17 NAMES[570], :530 SC_KEY_HASH, :539 COUNTS, :718 SB_PLANTS (16 names, 431 + index), :724 sb_planted,
  :734 sb_plant, :923 core_of, :1806 sc_snapshot
- relevance.rs: :421 struct Split, :533 unset, :541 consistent getter, comps getter below it
- relations_core.rs (not touched): :1763 transfer_terms, :2821 number_basis
- rust-spike/slice/session_live.py: :179 _table_get, :183 _table_set, :1075 _SB_PLANTS, :1358 install()
- rust-spike/slice/test_session_boundary.py: :29 PLANTS, :31 KEY_PLANTS, :70 CASES, :104 trunc, :148 keys, :182 _child,
  :231 test_each_dict_holds_its_own_keys, :256 test_plant_caught
- rust-spike/slice/scope_wl.py :36 queries (query 5 is `(Q.gt(x, 1), mine(x))`); known_moved.json, known_moved.py
- satassume/relations.py :713 _number_basis, :1709 _transfer_terms; satassume/sympy_api.py :864 class _Split (:887 the
  early return)
- Outputs: orion:~/sa-rust-ids-work/sa-port-245/{bis,fix1,slice-i}
- Ranges left: plants 447-449 and 460-469; counters 570-579 and 690-699
