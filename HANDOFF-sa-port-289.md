# HANDOFF sa-port-289 (B, formula's next step, issue 323): 3 of 6 items done, handing off before item (1)

Branch port/formula = origin/rust-slice 9595874 plus the commits below (pushed). Nothing is landed. The batch's one bar has not run.
Plants 622 and 623 and counter 720 are used. Plants 624-629 and 669 and counters 721-739 are still free (checked against
briefs/addenda/sa-port-siblings.txt).

| item | commit | state |
|---|---|---|
| Hand at eng.ask | 6a461f2 | done: fm:again within an ask is 0 (dev 30 -> 0, fuzz 0); plant 622; test_hand_per_ask.py |
| C2 rel_interpret direct calls | d25b1a7 | done: answers equal on 20 workloads; Group D before/after RUNNING (below) |
| C7 cb_noncomm = (2) `_noncommutative_atoms` native | the commit after d25b1a7 | done: plant 623; test_noncomm_native.py |
| (1) refuse:object | - | NOT STARTED. The planner gave the OK for session.rs, with conditions (below) |
| (3) bar.sh cbm_noid / bar_sum fired | - | not started (HANDOFF-sa-port-284.md has the map) |
| batch bar | - | not run (at the end, or near the budget) |

## Group D, pinned before/after C2 (running when I left)

Run by ~/sa-rust-ids-work/sa-port-289/gd/go289.sh (orion, detached). The end marker is gd/go-end.txt ("END step rc time").
It staged 6a461f2 and d25b1a7 on pareto1, ran job195 (profile samples) and post195 for both (gd/run-SHA/SUMMARY.md,
ana-dev.txt and ana-fuzz.txt give the per-function shares). It was then in the quiet lease (7 interleaved rounds,
bench-container CPU 2) and, last, med285.py writes gd/med-r1.md. Report the per-function shares, not only the totals (the gate
asks for this). The base numbers are results/gd-adapters-cost-med-r1.md on rust-slice. Tools are copied from sa-port-288's
gd, with paths rewritten to sa-port-289.

## Counts per workload (session counters; tools/cnt_rows.py; cnt-c2 = d25b1a7, cnt-c7 = the C7 build)

All under ~/sa-rust-ids-work/sa-port-289/. answers_sha is equal on all 20 workloads, and fm:twice and fm:nosession are 0 on both.
- ent:cb_noncomm (Python `_noncommutative`/`_noncommutative_atoms` callbacks from entry.rs), before -> after:
  budget 28>0, cert 182>30, cls 25>7, core 1634>0, dev 1209>6, f6 2913>0, fuzz 3556>97, ground 16>8, loop 384>0,
  lra 2047>1291, opaque 2397>0, port 23>5, rootof 4784>0, scope 169>3, transfer2:3:40 48>8, transfer:7:60 64>4, twin 4>1,
  value 3685>150, wiring 6175>0, zero 700>1. After the change, each remaining call is a `_NONCOMM` memo miss
  (`nc:memo_miss`, counter 720, has equal counts). It is the domain.py tree walk over SymPy classes, which stays Python:
  name it as an exception under the count rule.
- ctx:cb_helpers (context.rs `verdict`'s `_noncommutative_atoms` call): 0 on all 20 workloads after the change.
  Before: budget 4, cls 2, core 9, dev 64, f6 4, fuzz 315, ground 3, lra 375, opaque 1, port 3, rootof 1,
  transfer:7:60 4, value 2, wiring 191, zero 25.
- fm:convert rises where the atoms now come from the entry's node rather than from Python's atoms_of: budget +5,
  fuzz +54, lra +144, value +316, wiring +1, zero +42. results/fm_rows.json is updated in the C7 commit from the fm3 run.
- refuse:object (before item (1), on these SHAs): dev 17, fuzz 30, zero 94, transfer:7:60 17, transfer2:3:40 2, cls 3, scope 1,
  ground 2, port 6, and 0 on the others. The suite count is still unmeasured.
- ctx:caught is 0 on all 20 workloads. I didn't confirm that this counter is the engine.py:1906 quiet catch: check it before
  reporting it as that count.

## Item (1): the planner's OK (forward-chain-3b, ~16:10Z 11 Nov, verbatim)

"OK to edit session.rs for item (1), on these conditions.
(a) Stay out of A's hunks. Run `git diff 172d690 3070c52 -- '*session.rs'` (A's port/part3-followup, unlanded: the F1 serial near :850 and the SesDict identity memo). If your fix needs any of those lines, stop and hand off with the overlap named. Don't take A's commits into your branch.
(b) Keep it to the refuse:object path and node_base. The occurrence index on F::Atom is fine if objs[nid] ends up holding the object Python itself keeps (R1: first occurrence in the query's input). Show it with a kept test where two ==-equal but distinct objects come in both orders, and Rust holds the same one Python does, with a plant on that test.
(c) Check 720-739 against briefs/addenda/sa-port-siblings.txt before using it. If it isn't free there, ask the architect for a range.
(d) Each item is its own commit, as before. Your report states session.rs's changed line ranges, so A's successor can rebase.
If (a) blocks you, take your fallback: refuse:object stays a named exception with per-workload counts, and you go on to (3).
Tilo can overrule."

(c) is checked: the range is free. For (a), A's hunks (on 172d690's line numbers) are :15 (use), :104 (NAMES: don't add
counters to session.rs's NAMES; put them in formula.rs's NAMES as 720 is), :530, :716, :741, :1221 (the join hook inside
`nid_of`, which reads `objs[n]` as "first"; a fix that rewrites objs[nid] changes what that hook compares, so look at it
first), and :2306.

## FILE:LINE MAP (on this branch; rust-spike/slice/ unless noted)

- solver_rs/src/formula.rs: `ASK` thread-local and `formula_ask` (rg `fn formula_ask`); `Hand::enter` shares ASK only for
  the outermost entry; `release()`; plant 622 `HAND_PER_ENTRY`, plant 623 `planted_nc_memo`, counter 720 `NC_MEMO_MISS`
  (NAMES index 22).
- term_live.py `_ask_once` (end of `_install`): the top-level ask runs inside `sa_solver.formula_ask`.
- solver_rs/src/entry.rs: `noncommutative_term` (memo read; miss -> domain `_noncommutative`) and `noncommutative_atoms`
  (atoms from the Hand), right after `fn noncommutative`. ent_ask makes its Hand before the noncomm check.
  context.rs `verdict` calls `crate::entry::noncommutative_atoms`.
- solver_rs/src/relations_core.rs: `ad_register` / `ad_has` / `ad_interned` / `ad_order_sides` (rg `fn ad_`), before `rel_interpret`.
  solver_rs/src/adapters.rs: register (LRA, EUF), order_sides (LRA), interned (EUF) are pub(crate).
- Item (1): session.rs (A's file; the OK is above) `REFUSE_OBJECT`, `nid_of`, `nid_in_formula`, `refuse_object`,
  `custom_in_formula`, `to_f`, `convert`, `St::node_base`, `PyCx::node_base`. Find each with rg, because the line numbers in
  HANDOFF-sa-port-284.md are from 50f1421 and the file hasn't changed since. compile.rs `trait Cx` / `F`.
  test_session_limits.py:393 reads c['refuse:object'] > 0.
- Item (3): p1/bar.sh tests phase (runs test_cbm_noid.py on Python; run it on Rust), p1/bar_sum.py plants (the fired column
  misses term plants). Add test_hand_per_ask.py and test_noncomm_native.py to the bar's TESTS.
- Tools: fm_again_split.py (committed), ~/sa-rust-ids-work/sa-port-289/tools/cnt_rows.py and cnt.sh (counts per workload
  for a given .so), so/ (c2-d25b1a7.so, c7.so for aarch64 orion).
- Quiet-failure catches (engine.py:1906): not counted yet, see ctx:caught above.
