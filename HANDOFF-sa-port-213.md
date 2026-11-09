# HANDOFF sa-port-213 (state step part 2, rest of (iii)): (iii)(a) + (b) first move on the branch, unbarred, unlanded (week 90%). Issue 323

## State
- port/state-relations-iii rebased on rust-slice 80665b5 (S2); code at 6ed06b9; pushed. Nothing landed (week reached 90% ~15:45Z
  9 Nov; architect: no landing until the reset 10 Nov 04:00Z).
- (a): a5f57ce (relation_atom dispatch), f593984 (int foreign leaf). Planner ruled (~15:05 9 Nov,
  ~/dev/architect/briefs/addenda/sa-port-relations-entry-ruling.txt): the dispatch frame is public entry; relations.py counts,
  footnoted, once (iii) lands at a clean bar with the module-wide probe rerun on the landed SHA.
- (b) first move: 7899a6a + 6ed06b9, the seven scalar cursors in SessionCore.relc. Digest equal at the switch, dev/fuzz MATCH,
  plant 268 caught on fuzz; details in results/port-state-relations.md, last section.

## Read first
1. results/port-state-relations.md, section "Sub-part (iii)(a) and (iii)(b) first move".
2. This file's Next and map.

## Next
1. If rust-slice moved (harness fix, sa-port-209 or successor): rebase, rebuild, rerun test_relc_core.py and test_term_ids.py,
   re-copy rust-spike/slice/p1/bar.sh to pareto1 ~/sp19/bar-sa-port-213.sh (or your own name) if it changed.
2. Bar: pareto1 ~/sp19/sa-rust-ids-work/sa-port-213/run-bar-iii-ab.sh (edit OUT for your dir; PLANTS += int-as-number,
   rc-xterm-stale, rc-hseen-stale, rc-xslot-skip; TESTS += test_rule_tables.py, test_relc_core.py), BASE =
   ~/sp19/sa-rust-ids-work/sa-port-207/bar-state-relations-iii1b/suite. Run as
   machine run pareto1 --shared --wait 4h -r WHY -- setsid bash .../run-bar-iii-ab.sh BASE. ~56 min. Land per the week rule.
   Expected void plants: rc-xterm-stale, rc-hseen-stale (idempotence guards; caught by test_relc_core.py); rc-xslot-skip void on
   dev, caught on fuzz.
3. The rest of (iii)(b): 30 containers on rel (rel_init sets them): lists _xpend, _xextra, _pending_links, queue; sets linked,
   _bounded, _user_eq, _xpairs, _aux_eq, _link_eq, _xpart, _xcounted, _xcand; dicts status, _guards, _link_lt, top, link_sel,
   atom_sel, num_sel, _roles, _info, _link_of, _tv, _tsrc, _xside, _xheads, adapters; object sharing. Keyed by P atoms and SymPy
   terms: they need atom/term ids that last for the session (term_live's ids are per query), which is the design question.
   Engine readers outside relations.py: status, queue, active, link_sel/atom_sel/num_sel (engine.py :1088-1129 glue sel
   stamps via session_glue.rs, :1177; ref.py). Pattern to copy: the cursors (record in SessionCore, view + record method in
   session_live, snapshot export + digest test like test_relc_core.py, one plant per container).
4. (iii)(c): module-wide relations.py probe on all seven workloads after (b) (~/sa-rust-ids-work/sa-port-211/pyc/run.sh; edit O=).
5. TSV owners / port-ownership.md (glue_objects tsv :372 can cite cac82a9), agent report.

## File:line (6ed06b9)
- solver_rs/src/session.rs: RelC/RC_NAMES/RC_INIT/XTCUR.. :651; relc_init/relc_get/relc_put :705; views relc_field,
  set_relc_field, relc_snapshot :1426; counters 347-349 rc:* in the names table and RC_CORE consts after GL_PLAIN.
- solver_rs/src/relations_core.rs: plants 266-268 :397 (names in the plant match after gl-plain-no-link); transfer_terms
  :1720; sync_transfer :1818; rel_init :2058; rel_note_sides :2413.
- session_live.py: _rel_cview/_REL_CVIEWS :229; install sets them next to _REL_XVIEWS; _REL_STATE_PLANTS lists rc-*.
- test_relc_core.py: switch digest, record method, counters, plants.
- Probe outputs: ~/sa-rust-ids-work/sa-port-213/pl1 (cmp.txt, cmp2.txt).
