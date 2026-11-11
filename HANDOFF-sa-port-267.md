# HANDOFF sa-port-267: formula step (issue 323), eleventh part

Branch `port/formula`, head = this commit, on rust-slice **9151316**. **Unbarred, unlanded.** Handed off at the context
budget, between items. Gate item 1's ruling is committed with its tests and the suite is read; the lra cause is named
and sent to the planner as a question (report 73621ed, no fix). Plant 608 on the two-order harness, the relations.py
carrier, items 4b-4j and the bar are **not started**. Before this: HANDOFF-sa-port-266.md.

## Commit of this session
- `f848edd` the planner's ruling on the suite's `fm:twice` (gate for sa-port-267, (a) plus (b)):
  - (a) catch_count registers its wrapper (session_live.py `INSTRUMENTS`, `register_instrument`). While the class holds
    that wrapper over session_live's own `verdict`, context.rs `verdict_from` calls Rust's `verdict` directly with the
    entry's nodes, between the instrument's `before()` and, on an Exception, its `raised(token, exc)`.
  - (b) any other `verdict` on the class or the instance is the user's: called by name, inside a `formula::Patched`
    scope. What the entry behind it converts again is `fm:twice:patched` (counter 648); `fm:twice` stays the per-query
    rule's (the same object twice in one scope).
  - Plants 609 `fm-hand-instrument-by-name` and 610 `fm-hand-patched-direct`, each caught by a kept test in
    test_convert_once.py (9 tests pass; test_formula_nodes.py 15; test_catch_count.py + test_handler_count.py 5 with
    `-p rust_plugin -p handler_count` and `SLICE_SUITE_OUT` set; test_context_core.py 12 + 3 skipped,
    test_entry_core.py 23, test_relevance_core.py 34, test_discard_exempt.py 3). The other slice test files were
    **not rerun** on f848edd.
  - Only `verdict` got the scope. `context_session_from` (`_context_session`) and budget.rs `within_from`
    (`_within_budget`) call a patched method by name the same way and are unchanged: no ruling covers them.

## Gate item 1 (convert once): numbers on f848edd
Suite (pareto1, -n 8, `~/sa-rust-ids-work/sa-port-267/suite-f848edd`, tree.txt names the SHA and the .so):
**127 failed, 5,991 passed, 23 skipped, 18 xfailed**, the numbers of base 9151316 and of f42047a; no test's outcome
differs from base. `fm:twice` **0** (586 on f42047a), `fm:nosession` 0, `fm:twice:patched` 0 (it fires in the kept
test). Catch counts equal on head and base per test, site, type and text: 49 rows in 9 tests on both (complete_check
RuntimeError 1; verdict<_consistent AttributeError 38, Uninterpreted 7; verdict<consistent_by Uninterpreted 3).
Suite sums (base 9151316; f42047a): `fm:convert` 89,236 (-; 89,826), `fm:give` 89,980 (-; 82,344), `cls:eq` 457
(-; 722), `rk:intern:engine` 993,317 (993,870; 990,355), `rk:intern:input` 106,698 (106,780; 106,466), `ad:cbm_noid` 0
(612; 0), relations.py frames in converted queries 0 (615; 0). Why `cls:eq` fell from 722 was not looked into.
Passed was not split by firing this session.

Workloads on f848edd (pareto1, `wl-f848edd`, copied to orion under the same name; ended 01:51Z): `fm:twice`,
`fm:twice:patched`, `fm:nosession`, `same:eq`, `kept_product:mismatch` and `ad:cbm_noid` are 0 on all 20.

| workload | fm:convert | fm:give | cls:eq | rk:intern engine / input | PY_COMPILE fallback | _noncommutative_atoms |
|---|---|---|---|---|---|---|
| budget | 572 | 154 | 0 | 0 / 0 | 0 | 30 |
| cert | 122 | 122 | 0 | 902 / 192 | 0 | 61 |
| cls | 55 | 55 | 174 | 666 / 104 | 3 | 23 |
| core | 1,283 | 735 | 0 | 0 / 0 | 0 | 308 |
| dev | 1,665 | 1,678 | 0 | 4,067 / 511 | 17 | 840 |
| f6 | 1,018 | 120 | 0 | 0 / 0 | 0 | 8 |
| fuzz | 5,805 | 5,769 | 0 | 93,286 / 9,539 | 30 | 3,127 |
| ground | 33 | 33 | 0 | 486 / 57 | 2 | 18 |
| loop | 2,490 | 564 | 0 | 0 / 0 | 0 | 244 |
| lra | 7,265 | 5,853 | 0 | 64,243 / 9,324 | 0 | 1,743 |
| opaque | 61 | 61 | 0 | 0 / 0 | 0 | 31 |
| port | 39 | 39 | 0 | 337 / 61 | 6 | 22 |
| rootof | 737 | 736 | 0 | 0 / 0 | 0 | 369 |
| scope | 1,138 | 610 | 0 | 1,953 / 303 | 1 | 166 |
| transfer2:3:40 | 80 | 80 | 0 | 2,080 / 221 | 2 | 40 |
| transfer:7:60 | 124 | 124 | 0 | 2,476 / 209 | 17 | 64 |
| twin | 4 | 4 | 21 | 56 / 2 | 0 | 2 |
| value | 1,154 | 835 | 0 | 1,183 / 394 | 0 | 638 |
| wiring | 10,908 | 13,158 | 0 | 0 / 0 | 0 | 5,005 |
| zero | 1,394 | 1,321 | 0 | 18,338 / 1,027 | 94 | 724 |

The fallback column is the same 172 as on f42047a (each `refuse:object`; owner: formula's next step, by the gate).
`_rust_call`'s two reasons are still **not shown to fire on a plant** (owed, gate item 2).

`fm:again` inside one ask on f848edd (orion, `again-q/`, `SA_FM_TRACK=query` with sa-port-265's cnt.sh): core 8, dev
30, f6 0, lra 408, rootof 1, scope 0, value 1, wiring 3, zero 5 (`fm:twice` 0 on each). On f42047a: core 143, f6 112,
wiring 31, lra 456, dev 30, zero 5. What is left belongs to the part 3 follow-up (one Hand per ask) by the ruling.
The other 11 workloads were not measured on this head (all 0 or 1 on f42047a).

Still owed for item 1: **plant 608 on the two-order harness** (`~/sa-rust-ids-work/sa-port-250/twoorder.py MODE
OUT.json`, run by `py.sh` with `TREE=`; it is a Python-backend script: it needs the Rust install, e.g.
`test_discovery_core._rust()` as test_convert_once.py does, and `sa_solver.formula_plant('fm-hand-kept')`; modes
`orig-first` and `twin-first` are the two orders). Not started.

## Gate item 3 (j1, lra): read and named, question open
j1 (`~/sa-rust-ids-work/sa-port-260/j1`, digest on 78962f7): 19 workloads MATCH, lra DIFFER (answer_diff 0, end 2,
stream 2, lra 2, stats 1,427, moved 2), plant 666 on f6 DIFFER (caught). scope MATCHes: its `engine:splits` difference
is gone.

**lra's cause (report 73621ed, question to the planner, no fix):** each differing query (73, 204, 585, 6) has a
term_live run that is refused and discarded, then run again. The discard (term_live.py `_Mark.rollback` :183)
restores the engine's stats and Python's tables; `_Mark._note` (:163) skips every Rust-native table (`Engine.splits`
and `Engine._verdict` are native `EngineMemo`s).
- q73 alone (`live.py lra MODE OUT --only 73 --check plain`): Python sessions 3, consistency_checks 1, set_checks 1;
  Rust 2, 0, 0. Rust does the check once, in the discarded run (`rv:consistent` 1, `ctx:verdict` 1); its counts are
  rolled back; the rerun finds that run's `_Split` in `Engine.splits` with its flag set (`rv:relevant` 2,
  `rv:split_new` 1). Python has no first run.
- q204: the first differing solver event (of 3,073) is `LRATheory.check`'s model: the same constant-field element
  with its terms in another order. **The native container that carries the order is not named.**
- Control: the four queries on Rust with `SLICE_TERM=py` (no first run) against Python: MATCH. Term path on: DIFFER.
This is the "rerun sees the first run's state" shape (#96), so it went to the planner first. lra stays an exact known
row in the bar until ruled. Files: `~/sa-rust-ids-work/sa-port-267/lra/` (trace73.py MODE [Q], q4*.cmp, d204-*.detail).

## Not started
Plant 608 on the two-order harness; gate item 2's rest (bis-order.txt on the head, the bisect on base to the carrier
test, the commit that removed it, `_rust_call`'s reasons on a plant); items 4b-4j; the bar. The report's standing rows
not measured this session: handler multiset, plant table, inventory, kept shares, `_SPLIT`/`_CACHE` rows, cache_det,
module-wide probes, answers against the reference, Formula callbacks per workload.

## File:line map (this head)
- context.rs: `Method` :65, `method_of` :75, `patched_method` :103, `context_session_from` :140, `verdict_from` :148,
  `ctx_verdict` :320, `verdict` :324.
- formula.rs: NAMES :62 (`fm:again` :83, `fm:twice:patched` :84), PLANTS :103 (607 :114, 608 :115, 609 :116, 610
  :117), SEEN :130, SCOPE :133, plant readers :169/:173, `convert_or` :504 (ticks :529/:530), `Hand` :592, `enter`
  :604, `enter_inner` :611, `node` :618, `give` :653, `Patched` :678, `Drop for Hand` :695, `formula_plant` :749,
  `formula_held` :765, `formula_track` :772.
- session_live.py: PY_COMPILE :25, OURS :936, INSTRUMENTS :941, `register_instrument` :944, `_install_context` :1134,
  `_rust_call` :1338, `_compile_formula` :1350, `_formula_literal` :1360. catch_count.py: `verdict_raised` :32,
  `counted_verdict` :38, the class patch :47, the registration :51.
- test_convert_once.py: `_main` :34, `over` :102-:111, the instrument group :113, the patched group :132, tests
  :177-:251 (instrument :207, patched :217, plants 609 :228, 610 :236, 607 :243, 608 :251).
- term_live.py: `_Mark._note` :163, `add` :171, `rollback` :183. session.rs `nid_in_formula` :1178, `refuse_object`
  :1188. entry.rs, relevance.rs, session_glue.rs, term_discard.py: as HANDOFF-sa-port-266.md (unchanged).

## Helpers and output
- orion `~/sa-rust-ids-work/sa-port-267/`: p1/ (sa-port-266's helpers with this session's paths; sum266.py also
  prints catch counts, outcomes and `fm:twice:patched`), suite-f848edd/, wl-f848edd/, again-q/, lra/, t-a/, t-b/, cc1/.
- pareto1 `~/sp19/sa-rust-ids-work/sa-port-267/` (p1/, suite-f848edd/, wl-f848edd/), tree
  `~/sp19/dev/sa-port-267-f848edd` with its x86-64 .so (built-f848edd.txt). Launch as in HANDOFF-sa-port-266.md, with
  `sa-port-267` in the path.
- Plants 609 and 610 and counter 648 are taken this session (611-629, 668-669; 649-659, 673-679 free).
