# HANDOFF sa-port-205 (state step part 2: (ii) transfer sites barred; (iii) first part barred; rest of (iii) open), issue 323

Branches (all pushed):
- port/state-relations-stack 997a54f = (ii) (19d5d04's code + 202's handoff) rebased onto 6i(a) b11b5a2 (sa-port-204's tested
  source, unlanded when this was written): the planner's "stack them" (bars due within 30 minutes). Bar: pareto1
  ~/sp19/sa-rust-ids-work/sa-port-205/bar-state-relations-ii (end.txt; base rows sa-port-200's bar-state-relations-i/suite).
- port/state-relations-iii 83affaa = (iii) first part on top of 997a54f. Bar: .../sa-port-205/bar-state-relations-iii1
  (base rows = the (ii) bar's suite).
- Landing order: 204's b11b5a2 first, then 997a54f, then 83affaa. Each tested source holds the one before, so after each
  landing `bar.sh land TESTED` should show an empty guard diff. If 204 doesn't land, rebase (ii) with
  `git rebase --onto origin/rust-slice b11b5a2` and rerun the bar (the guard will refuse otherwise).

## Done
- (ii) quick checks on orion at 19d5d04's rebuilt code: dev MATCH 31cd0945c07f02a6; xf:record 0, xf:session_view 0, xf:rel_view 0,
  xf:engage_core 35, xf:read_core 4,315, xf:solver_core 239; xf-solver-fresh planted on dev: DIFFER (40 answers), so it is
  caught on dev. test_xfer_core.py + test_relations_core.py 95 passed; tests/test_transfer.py + tests/test_relations.py 77
  passed, 3 failed (the base three: test_protocol_on_fuzz "Already mutably borrowed", test_models_respect_transfer,
  test_equality_sharing_is_needed_and_works). Fuzz quick check stopped (the bar's live phase covers it).
- (iii) first part:
  1. relations_core.rs `glue_objects_plain` (:3024; pyfunction `rel_glue_objects_plain` :3058): relations.py:1994's
     glue_objects without its eq branch; budget.rs :95-105 calls it for any relation atom other than a two-sided `eq` (the eq
     keeps term_live's `_glue_objects`, :692). Counter 344 gl:plain (session.rs :464), plant 263 gl-plain-no-link
     (relations_core.rs :395; session_live.py :893). dev gl:plain 27 = relations.py glue_objects' 27 before; plant fired 31 on
     dev, answers MATCH (void on dev: cone objects weigh only near the budget); test_glue_plain.py catches it.
  2. session_live.py `_rel_install` (:1076-1095): a default engine built before the install (scope_wl's `default_engine()` at
     load, live.py :332 before :359-368) held Python's `with_closed_units.<locals>.clauses`; it is rewrapped on
     rel_with_closed_units. test_glue_plain.py::test_default_engine_rewrapped. scope MATCH 12e06b0586faee40.
- Module-wide relations.py probe (pycalls.py, PYCALLS_FILE=satassume/relations.py; ~/sa-rust-ids-work/sa-port-205/pyc/run.sh,
  summ.py): at b0f708d: cert 0, zero 0 converted (were glue_objects 72, 2); scope: glue_objects 13 -> 0; after the rewrap
  (pyc/rewrap) scope with_closed_units 518 -> 0. dev/loop/budget/fuzz in pyc/b0f708d (run2.log; check done-*.txt).
  Left on scope, all term_live fallbacks to relations.py's originals (caller by trace, scratch trace_rel.py =
  proc_memo_trace.py with these targets): relation_atom 397 <- term_live relation_atom, _is_number 392 <- term_live is_number,
  _under_apps 11, _key 8, _structural_subterms 4. Cause to check first: `_ids` (term_live :375) gives None for a side with no
  id in the query's table, e.g. scope_wl's extension `relation_atom('lt', s, 1)` with a plain int 1 (scope_wl.py :28).

## Next
1. Read both bars (bar_sum.py output sum.txt), land in order with `agent usage` < 90% (PUSH=1 bar.sh land SHA).
2. Results: append (ii) and (iii)-first-part sections to results/port-state-relations.md (port-state-memoized.md's form);
   TSV owners + port-ownership.md; agent report.
3. (iii) rest: term_live fallbacks above (term ids for the sides with none); then Relations' dicts (rel_init :2033, 36
   containers keyed by P atoms / SymPy terms; field census below); relations.py rejoins only on the full module-wide probe
   with 0 converted calls on all seven workloads.

## Relations field census (rel_init's fields; string sites in relations_core.rs / session_glue.rs / other Rust | relations.py
## uses / engine readers outside relations.py / wiring (session_live+term_live) / test files)
status 5/1/0|5/2/0/0; queue 3/0/1|4/2/0/2; active 4/0/1|4/3/0/2; link_sel, atom_sel, num_sel 3-4/3/0|3-5/3/0/0-1;
the engine readers are engine.py :1088-1129 (glue sel stamps, run by session_glue.rs) and :1177, plus ref.py (reference).
Every other field (linked, _bounded, _guards, _link_lt, top, sharing, _pending_links, _xextra, _user_eq, _roles, _info,
_link_of, _tv, _tsrc, _xpairs, _xtcur, _xhn, _xhseen, _aux_eq, _link_eq, _xside, _xslot, _xterm, _xnsides, _xsides_n, _xpart,
_xheads, _xcounted, _xpend, _xcand): relations_core.rs 2-6 sites, relations.py only, no engine or wiring reader, tests
0-3 files (test_relations_core.py::_rel_state etc., needs-internals). The scalar counters (_xtcur, _xhn, _xhseen, _xslot,
_xterm, _xnsides, _xsides_n) are the cheap first move (into session.rs's per-Relations record, as (ii) did); the dicts are
keyed by P atoms and SymPy terms and need atom/term ids.
