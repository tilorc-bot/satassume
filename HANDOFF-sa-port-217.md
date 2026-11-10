# HANDOFF sa-port-217 (state step part 2, rest of (iii)): bar on 022630c running, unlanded; RelKeys ruled, not started. Issue 323

## State
- port/state-relations-iii is rebased on rust-slice db7130a (harness install-order fix + Q2 Rust handler plant, sa-port-218).
  Head 022630c, pushed (this handoff commit sits on top and touches no code). Code is as at 6ed06b9, carried by the rebase:
  (iii)(a) f5dfa60 + 7282317, and the (iii)(b) first move 00746b8 + 76123df.
- Incoming diff from 80665b5 to db7130a: live.py (SLICE_PLANT_HANDLER after the installs), test_live_handler_plant.py, and
  results/. No Rust, satassume/ or session_live.py change. The rebuild is clean.
- Short check after the rebase, on orion: test_relc_core.py, test_term_ids.py and test_live_handler_plant.py, 183 passed.
- Bar: pareto1, script ~/sp19/sa-rust-ids-work/sa-port-217/run-bar-iii-ab.sh (bar.sh copied as ~/sp19/bar-sa-port-217.sh,
  identical to rust-spike/slice/p1/bar.sh). Clone ~/sp19/dev/sa-port-217-iii; OUT
  ~/sp19/sa-rust-ids-work/sa-port-217/bar-state-relations-iii-ab, marker end.txt.
  - BASE: ~/sp19/sa-rust-ids-work/sa-port-209/bar-install-order/suite, the latest landed bar: 5,992 passed, 126 failed.
  - TESTS: sa-port-213's list plus test_live_handler_plant.py. PLANTS: 213's list, which includes int-as-number and rc-*.
  - Phases at 04:53Z: build, tests, suite and live were done; plants, extra, suiteplants and sum were still to run.
    Expected end ~05:40Z.
  - I stopped my machine-run waiter at handoff, so its shared lease lapses ~05:15Z while the detached job keeps running.
- Expected void plants: rc-xterm-stale and rc-hseen-stale (idempotence guards; caught by test_relc_core.py). rc-xslot-skip is
  void on dev and caught on fuzz.
- An earlier bar on 3c73106 was killed after its build phase, on the architect's word that rust-slice had moved. Its output
  was deleted.
- Landing: rule [91] blocks it while sa-port-215's 6i(c) bar (~/sp19/sa-rust-ids-work/sa-port-215/bar-6ic/end.txt,
  ~06:20Z) or sa-port-216's 6i(b) bar runs.

## RelKeys (rest of (iii)(b)): ruled, not started
- The question is report fd0857d; the note is ~/sa-rust-ids-work/sa-port-217/q-container-ids.txt. The ruling is
  ~/dev/architect/briefs/addenda/sa-port-relkeys-ruling.txt: option B, refined.
  - RelKeys lives in SessionCore and holds strong refs.
  - It reuses the query table's term ids, with no new hash. Only keys with no id get interned. Name any sessions that
    outlive their query.
  - Interns are counted rk:intern:input (conversion) and rk:intern:engine (scaffolding, target 0 before any backend PR).
  - Sets become HashSet<u32>; dicts become IndexMap<u32, V>. _xheads is the only iterated container; no set is iterated
    (grep at 022630c).
  - Adapters: default specs hold the Rust adapters; a user-supplied spec's Python adapter is the named exception, counted
    ad:cb_factory. sharing is already a Rust pyclass (transfer_py.rs:259).
  - Read-only views go to the engine.py :1088-1129 and :1177 readers and to ref.py :408/:416. Tests that read internals go
    through a view or onto needs-internals. The snapshot digest is shown equal at the switch.

## Next
1. Read end.txt and sum.txt. State the five bar items. Wait for the other bars' end markers, then
   `bash rust-spike/slice/p1/bar.sh land 022630c` (no PUSH). Read the incoming diff, and rerun the bar only if it touches
   guarded source. Then PUSH=1. Touch no marker unless the architect names one.
2. RelKeys and the 30 containers, per the ruling, copying the cursors' pattern (test_relc_core.py).
3. (iii)(c): the module-wide relations.py probe on all seven workloads, on the landed SHA.

## File:line (022630c; the code lines are as at 6ed06b9)
- solver_rs/src/session.rs: RelC :651; relc_init/relc_get/relc_put :705; relc_field/set_relc_field/relc_snapshot :1426.
- solver_rs/src/relations_core.rs: plants 266-268 :397; transfer_terms :1720; sync_transfer :1818; rel_init :2058-2110
  (the containers); status reads :1365, :2256, :2298; _tv :1570/:1588; _xside :1658/:1728/:1849/:1912; top :2143/:2307.
- solver_rs/src/procmemo.rs:34 PyKeyMap: the hash/== pattern that the ruling's option A would have used. Don't copy it.
- satassume/relations.py: writers :885-1610 (queue :885, status :938, num_sel :986, adapters :1010, _info :1092,
  _guards :1107, _roles :1224, _tsrc :1285, _tv :1313, atom_sel :1337, _link_lt/link_sel/_link_of :1502-1514); _fresh :995.
- session_live.py: _rel_xview :205, _rel_cview :229, _REL_STATE_PLANTS ~:912, install ~:1195.
- test_relations_core.py::_rel_state :278 (needs-internals candidates).
