# HANDOFF sa-port-274: formula step (issue 323), fifteenth part

Branch `port/formula`, head = this commit, on rust-slice **9151316**. **Unbarred, unlanded.** Handed off at the context
budget, between items. The gate's order was: carrier, 4g, plant table, the rest, bar. Done: the carrier (closed), 4g,
4b, and the plant table in part (602/603 replaced). Full text and numbers: rust-spike/slice/results/port-formula.md,
section "sa-port-274" (:580). Before this: HANDOFF-sa-port-270.md.

## Done this session
- **Carrier (closed), bbeb5bb.** The head has 0 converted relations.py calls in both orders. Plant 661 brings back 527
  (forward order only). Base 9151316 has 511 forward and 0 reversed. **The first SHA at 0 is a5fa1f6** (`same_class`
  on the query's own class table). The rows across two equal class objects stay in Rust and are counted `cls:eq` (369).
  All the calls are in test_relevance.py::test_split_relational_answer_is_the_part_answer, and only after the earlier
  tests of 266's order. sa-port-270's SymPy-cache guess is **not shown**: with the cache emptied before each test, the
  two files alone make 0 calls on base. The old SHAs were built with one name fixed (session.rs:1825 `PyBool`).
- **4g, b18b064.** The digest no longer replaces `Relations._interpret`/`_link`. relations_core.rs `rel_observe`
  (:51) sets an observer, which `observe` (:56) calls on entry to `rel_interpret`/`rel_link` (an atomic flag, off by
  default). moved_digest.py `_observe` (:133) uses that on Rust and `sys.monitoring` PY_START on Python's code objects.
  On cls, `sb:fwd_named`/`fwd_direct` go from 306/147 with the old digest to 0/453 with the new one, the same as digest
  off. The old digest also moved the `_WANT`/`_SPLIT` value hashes. The kept test is
  test_moved_digest.py:95 (3 pass). Still wrapped: `Relations/Session/Engine.__init__` (they call the original; no
  Rust site checks them).
- **Plants 612/613, 7ffe426.** 602 (speed-only) and 603 (order-only) are retired. In their place at the same sites:
  612 `fm-atoms-merge-pred` (formula.rs :291-:299) and 613 `fm-args-drop-last` (:346). **613 is caught**: answers
  change on cls, dev, scope, loop and wiring. **612 fires on all five but moves no answer or row**: only the kept test
  catches it (test_formula_nodes.py, 15 pass). That needs a workload, or a reason why `atoms_of`'s readers don't care
  (601, which drops an atom, is caught on 10).
- **4b, 9453f12.** `ad:cbm_noid` is 0 on cls; plants 660 and 661 make it 264, with answers unchanged. 662 leaves it at
  0. Kept test test_cbm_noid.py:290.
- **The plant table** (port-formula.md, the section's last table). 660 is caught by 4b. 605 and 663 are reached only
  in the suite (kept tests build them): footnote. **662 goes to the planner**: it changes which of two equal objects is
  held (R1), so no answer can move. It is caught only by R1's kept test, and the gate's classes (speed-only, redundant)
  don't fit it. 600, 611 and 664-667 are not classified (firing not read).

## Not done (in the gate's order)
1. The plant table: 612 on all 20 workloads; 600, 611 and 664-667 firing and their checks; 608 void on f6 (why);
   lra's 608 run (orion `~/sa-rust-ids-work/sa-port-270/fm-lra-p608/end.txt`, not read).
2. Gate (1): the discarded count per workload in the report (f6 13, opaque 7, value 15, wiring 1, lra 456, the other
   15 are 0; from 270's sweep, plain1/*.tot).
3. 4c, 4e, 4h, 4j; 4f's bar invocation; 4i's bar line.
4. The bar (fmrows phase with FM_WLS, FM_PLANTS now naming 612/613, not 602/603), then land.
- Seen, not looked into: between two processes of the same digest, the value hashes of `_CLOSED` and `_SYMPY_ATOMS`
  in `moved_eng` differ (keys and counts equal).
- Not run on this head: the suite, the 20 workloads, the slice files (only test_moved_digest.py, test_formula_nodes.py
  and test_cbm_noid.py, all pass).

## File:line map (this head)
- relations_core.rs: OBSERVING :46, `rel_observe` :51, `observe` :56; calls at the top of `rel_interpret` and
  `rel_link`. moved_digest.py: `Moved.__init__` :116, `_observe` :133, `sample` (search `def sample`).
- formula.rs: PLANTS :103 (612 :105, 613 :107), plant 612 :291-:299, plant 613 :346.
- test_moved_digest.py:95; test_cbm_noid.py:290; test_formula_nodes.py:163 (caught map).
- results/port-formula.md :580, the sa-port-274 section.
- Everything else: HANDOFF-sa-port-270.md's map.

## Helpers and output
- orion `~/sa-rust-ids-work/sa-port-274/`: g4/probe4g.py OUT WL (all session_counts; OLDDIR= preloads another
  moved_digest), g4/run.sh OUT WL... (digest on/off), g4/new/, b4/ (ad:cbm_noid per plant on cls), p612/ (plain, 612
  and 613 on five workloads; 270's fmrows.sh).
- pareto1 `~/sp19/sa-rust-ids-work/sa-port-274/`: p1/ (copies of 270's, with carrier270.sh and carrier2.sh pointed
  here), carrier/, carrier2/. Trees `~/sp19/dev/sa-port-274-{0993f1c,9151316,1e90a19,a5fa1f6,425ca5e}`; the three old
  ones carry the one-line build patch, so don't use them for anything else.
- Plants: 612 and 613 are taken; 602 and 603 are retired. Free: 614-629, 668-669; counters 649-659, 673-679.
