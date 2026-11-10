# HANDOFF sa-port-226: state part 3, sub-part 2 done; 1, 3, 4, 5, 6 open

Branch port/state-part3 (from origin/rust-slice c822173), head d44b817 (code) + this handoff. Unbarred, unlanded; landing waits for (iii) (sa-port-222/225).

## Done: sub-part 2, install() refuse + install list (d44b817)
- Chosen: REFUSE (shorter). session_live.py:1190 `refuse_built_engines(who)` (gc scan for engine.Engine), called first in
  session_live.install() (:1201) and backend.install() (backend.py:108). The rewrap of a pre-built default engine's
  `with_closed_units` in `_install_relations` (:1087) is removed (dead under refuse). Refresh would need every binding
  Engine.__init__ takes (satassume/engine.py:1318-1341) rewrapped.
- rust-spike/slice/test_install_order.py: install list by attribute diff across live.py --check plain's install sequence:
  194 entries, test per entry (test_install_list_entry[...]); public: DictCache/ObjectCache (via DictCache.__new__,
  session_live.py:1017) and relation_atom (RELATION_ATOM_IMPL slot, term_live.py:993); engine-first test
  test_engine_first_refused; plants 420 inst-no-refuse, 421 inst-slot-skip, 422 inst-cache-new-skip, 423 inst-importer-skip
  all caught (test_plants_are_caught[...]). 197 passed on orion.
- OPEN FINDING: satassume/knowledge/templates/_rows.py still holds Python's `generator` and `constant_value` after install
  (rows authoring layer, `_rows.rules` :377 -> generator :382). Unverified whether reached at run time after install. Named
  in NAMED_HOLDERS, not cleared. limits.py and table.py also hold Python's helpers (Rules, facts, units, consts_of,
  pattern_key, lits): ruled kept (limits on Python; table kept paths only).
- Slice tests after the change: test_relations_core 88, test_discovery_core 10, test_session_limits 242,
  test_live_handler_plant 6, test_term_ids 172 passed; test_term_live 2 failed (_Mark has no `facts`), same 2 on base.

## Open
1. Inventory (sub-part 1): Session containers and session-lasting state, satassume/engine.py:304 class Session
   (:311 self.solver), Engine fields :1313-1400, session_live.py install() :1201 (properties table/base/xfer, Relations views).
3. Session.solver boundary + the rewrap test: under refuse, [108]'s rewrap test IS test_engine_first_refused (rewrap removed).
   Session.solver readers: OWED [100] (relations.py :1689/:1812/:1851, engine.py :2145/:2248; recheck lines).
4. Public-entry dispatch list: from test_install_order.py's public rows: DictCache, ObjectCache, relation_atom (+ P etc. via
   p_install, which refuses after satassume.sat.formula is imported). Write it up with the per-entry test ids.
5. SessionCore-shape sub-parts: wait for (iii) incl. 225 to land; rebase.
6. Readouts [108]: memo cost, scope fallback rise, session-lasting ids per workload; rk:intern:engine per workload.
- Bar: not run (suite, dev/fuzz, plants on workloads). The refusal guard runs in every bar workload's install: any workload
  that builds an Engine before the installs now raises (none expected after db7130a).
