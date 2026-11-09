# HANDOFF sa-port-207 (state step part 2: (ii) and (iii) first part LANDED; rest of (iii) open), issue 323

## Landed
- (ii) transfer sites: **9e10f0d** on rust-slice at 13:47Z on 9 Nov. Tested 997a54f; incoming diff results/port-6i-a.md only;
  guard empty; week 88%. Group-D AFTER on 9e10f0d: relations path dev 578/8,542 = 6.8% (before 7.0%), fuzz 3,323/21,859 =
  15.2% (before 15.3%). Rows: orion ~/sa-rust-ids-work/sa-port-207/gd/run-9e10f0d/SUMMARY-rel.md.
- (iii) first part (glue_objects_plain + default-engine rewrap + budget.rs `installed()` fix): **cac82a9** on rust-slice at
  14:45Z. Tested ce1092c; landed = ce1092c + results/ commit; week 89%. Bar pareto1
  ~/sp19/sa-rust-ids-work/sa-port-207/bar-state-relations-iii1b (sum.txt, counts.txt, fb.txt): clean. Marker
  ~/dev/architect/markers/state-relations-iii1-landed touched. S2 (sa-port-208/210, bb92b07) is stacked on ce1092c.
- The first iii bar (83affaa) failed 4 tests in test_relations_core.py. Cause and fix: results/port-state-relations.md,
  "Sub-part (iii), first part", SHAs.

## Open: rest of (iii)
(a) scope's relations.py calls (the only workload with converted calls left; every other one reads 0 on the module-wide
probe, sa-port-205's pyc/b0f708d and pyc/rewrap). Callers found by cProfile on scope (scratch prof.py = live.py under cProfile,
print_callers on relations.py):
  1. relation_atom 385 <- scope_wl.py:29's extension lambda. scope_wl.py:19 does `from satassume.relations import
     relation_atom` at import, before term_live's install patches the module attribute (term_live.py ~:962), so the user's
     fact builder runs Python's original. That needs a ruling: is it input construction by user code (public helper), or
     should relations.relation_atom dispatch itself? The second means editing satassume/relations.py:511. Ask the planner;
     don't edit scope_wl to hide it.
  2. relation_atom 12, _is_number 392, _under_apps 11, _key 8, _structural_subterms 4 <- term_live's wrappers (relation_atom
     :389/:436, is_number :482/:498, under_apps :548/:576, subterms :644/:654, key :840/:863) falling back, all for the plain
     Python int 1 in that extension's `relation_atom('lt', s, 1)`: term_id (:283) gives None for a non-Basic (counters
     term:unknown:link:int 127, key:int 4, relation_atom:int 12; nothing else is unknown on scope). **Don't map int to a number
     id**: Python's `_is_number(1)` is False (an int has no is_number), and `_under_apps` and `_structural_subterms` skip
     non-Basic sides. `_key(1)` = default_sort_key -> sympify -> Integer's key. What's needed is a foreign-leaf row kind in
     Rust's term table (term/table.rs Kind :34, TermRow :134; term/py.rs number :516, sort_key :554) for an exact `int`:
     is_number_term false, no free symbols, no args, under_apps contributes nothing, structural_subterms empty, sort_key =
     Integer's. Don't record it in q.derived/q.rev, so scaffold never returns an int for an Integer id. eq_sides with such a
     side: refuse (counted) unless a workload reaches it.
(b) Relations' dicts to Rust-native state: rel_init relations_core.rs :2038; the field census is in HANDOFF-sa-port-205.md
    (scalar counters first: _xtcur, _xhn, _xhseen, _xslot, _xterm, _xnsides, _xsides_n into session.rs's per-Relations
    record as (ii) did; then the atom/term-keyed dicts). One plant per moved container; snapshot digest equal at the switch.
(c) The module-wide relations.py probe on all seven workloads (~/sa-rust-ids-work/sa-port-205/pyc/run.sh, summ.py; copy them
    to your own dir) with 0 converted calls before relations.py rejoins the count.

## Not done by 207
TSV owners / port-ownership.md: unchanged. relations.py's rows keep their owners. glue_objects (tsv :372, "landed C1
63e085d") could cite cac82a9 for the non-eq path. agent report: done (see the journal).

## File:line (cac82a9)
relations_core.rs: installed() :647, TERMS_OF_NO_ORDER :132, rel_init :2038, glue_objects_plain :3029. budget.rs :101.
test_glue_plain.py: the terms-of-no-order comparison in _child; test_plant_moves_a_case parametrized.
test_relations_core.py: test_module_function_plant_is_seen's list (terms-of-no-order moved out, with a note).
