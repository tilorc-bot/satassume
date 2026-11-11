# HANDOFF sa-port-266: formula step (issue 323), tenth part

Branch `port/formula`, head = this commit, on rust-slice **9151316**. **Unbarred, unlanded.** Handed off at the context
budget, between items: gate 4a and a convert-once fix are committed with their tests; gate item 1 is **not closed** (one
question open, below); gate item 2's causes are named, the test-order bisect on base is started. Before this: HANDOFF-sa-port-265.md.

## Commits of this session
- `9c238a3` gate 4a: test_discard_exempt.py (3 tests, 10 s): a discarded run leaves `_CACHE` (counted exempt) and nothing
  else; plant 667 is named in another container and counted as left; `EXEMPT` names `_CACHE` only. fresh.py `--first N`.
  Sensitivity: with plant 666 the exempt count is 0 and the second test fails.
- `4d34c27` convert once: `is_` and `is_many` (entry.rs:605, :691) `hand.give` their session the cone's facts.
  test_convert_once.py has an `is` group (`fm:twice` 5/4/5 before, 0 after). test_convert_once.py, test_formula_nodes.py,
  test_entry_core.py: 43 passed.

## Gate item 1 (convert once)
Jobs read: t1 = 58 files, 55 exit 0; test_catch_count.py (3 failed), test_cf_diff.py (collection error),
test_handler_count.py (2 failed) are the known invocation rows (gate 4f). all.sh done (a1, a1q, b0, lra).

`fm:nosession` is 0 on all 20 workloads and in the suite (f42047a). `fm:twice` on f42047a was **not** 0:
core 135, f6 112, lra 48, wiring 28, suite 586 (113 tests); 0 on the other 16 workloads. One path on the workloads
(`cone_head`'s Hand converts, the session's `compile_loop::visit` converts again): fixed by `4d34c27`.

| workload | fm:convert b0 (78962f7) | f42047a | 4d34c27 | fm:twice f42047a | 4d34c27 | fm:again all / in one ask (f42047a) |
|---|---|---|---|---|---|---|
| core | 2,066 | 1,418 | 1,283 | 135 | 0 | 967 / 143 |
| f6 | 1,148 | 1,130 | 1,018 | 112 | 0 | 1,008 / 112 |
| wiring | 18,884 | 10,936 | 10,908 | 28 | 0 | 9,960 / 31 |
| lra | 17,887 | 7,313 | 7,265 | 48 | 0 | - / 456 |
| scope, dev | 1,763, 3,928 | 1,138, 1,665 | same | 0 | 0 | 283 / 0, 1,134 / 30 |

Other 14 workloads on f42047a (b0 -> a1; `fm:twice` 0; again all / in ask): budget 745 -> 572 (381/0), cert 491 -> 122
(30/0), cls 214 -> 55 (2/0), fuzz 23,098 -> 5,805 (1,388/0), ground 128 -> 33 (5/0), loop 3,079 -> 2,490 (339/0), opaque
124 -> 61 (30/0), port 148 -> 39 (6/0), rootof 1,474 -> 737 (368/1), transfer2:3:40 344 -> 80 (1/0), transfer:7:60 549 ->
124 (4/0), twin 22 -> 4 (0/0), value 2,311 -> 1,154 (319/1), zero 4,497 -> 1,394 (1,251/5). Not rerun on 4d34c27 (only
core, f6, wiring, lra, scope, dev were: rows' answer, message and engine counters equal to f42047a's; the files differ
bytewise, not looked into). `fm:again` in one ask was not remeasured after the fix.

**OPEN, a question for the architect/planner (not answered, nothing changed for it):** in the suite ~504 `fm:twice`
remain after the fix (the 24 affected test files rerun on orion: 504 without `-p handler_count`, 508 with; 100 tests;
largest tests/test_invariants.py::test_ci_stream_reports_only_what_replays 162). Cause: rust_plugin.py:117 installs
catch_count, whose `counted_verdict` replaces `Engine.verdict` on the class (catch_count.py:41). context.rs
`patched_method` (:66) then sees a `verdict` that is not `OURS`, so `verdict_from` (:119) calls it by name and
`ctx_verdict` (:277) starts a new `Hand`: the caller's nodes are dropped and converted again (Rust stacks:
`rv_relevant -> consistent -> verdict_from -> ctx_verdict -> within_from -> query_cone`, and `ent_ask -> verdict_from ->
ctx_verdict -> build_context -> theory_scope`). `ctx_verdict` uses `Hand::enter`, not `enter_inner`, so `fm:nosession`
stays 0 there. This is an instrument changing the path (RULINGS 14), and a user's own patched `verdict` would do the
same. Choices I see: (a) catch_count registers its wrapper so Rust keeps the direct call (the catch count at nested
verdicts is then lost or must move into Rust); (b) the by-name call is accepted and reported as an exact row, with
`enter_inner` in `ctx_verdict` so `fm:nosession` shows it; (c) the nodes reach the nested entry some other way (the
ruling says an argument, no cache). The suite was not rerun on 4d34c27 (expected 586 - 84).

Still owed for item 1: the suite on the head with `fm:twice` after that ruling; plant 608 on the two-order harness
(~/sa-rust-ids-work/sa-port-250/), not started.

## Gate item 2 (causes)
Suite on f42047a (pareto1, -n 8, with sa-port-240's relations.py probe and pyc266): 127 failed, 5,991 passed, 23 skipped,
18 xfailed; the failed set equals sa-port-263's suite-probe on 9151316 (127) and is part 3's bar set plus
tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence (the known id()-reuse test).
Base suite 9151316 with the same probes: 127 failed, 5,991 passed.

**term_live fallback (relations.py frames in a converted query):** suite on f42047a **0**; suite on base 9151316 **615**
(`_is_number` 275, `_key` 156, `_relation_atom_py` 114, `_affine_strip` 60, `_structural_subterms` 10), all in one
worker, 7 tests (5 of tests/test_relevance.py::test_split_relational_answer_is_the_part_answer, 341 the largest;
tests/test_transfer.py::test_transfer_answers 22; test_undefined_function_connects 2), not the test of ba1ca22's 42.
tests/test_relevance.py alone on base: 0. So it is path history dependence on base. Reproduced in one process on base:
that worker's first 217 tests in its order (`~/sa-rust-ids-work/sa-port-266/bis-order.txt`, with
`tl/probe.sh TREE OUT @bis-order.txt`) give 511 calls (bis/base-order). Base `ad:cbm_noid` in the suite is 612, absent on
the head. **Not done:** the same order on the head (expected 0), bisecting the order to the carrier test, and naming the
commit that removed it (candidates: a5fa1f6 / 425ca5e, the ad:cbm_noid fix). One suite run on the head at 0 does not
settle a history-dependent count: run the fixed order.

**PY_COMPILE fallback:** `_compile_formula` / `_formula_literal` falling to Python's compiler. All of them are one
reason: `table.core.compile` False / `literal` None from `refuse:object` (session.rs `nid_in_formula` :1178,
`refuse_object` :1188: an atom's expr in the formula is == to the object held for a node with no visit, and is not that
object). `_rust_call`'s two reasons (table not a `TableView`; `dv` not the session's) are 0 everywhere; **their zero is
not yet shown on a plant** (pyc266's LINE probe never fired; owed). `refuse:convert` and `refuse:depth` are 0.
- Suite f42047a: 3,771 fallbacks = `refuse:object` 3,771 (py_literal 2,809, py_compile 962; converted 2,476, noquery
  1,259, kept 36). Base 9151316: 3,786 (converted 2,492). By file: test_extended_order.py 1,348, test_transfer_fuzz.py
  1,167, test_eq_links.py 400, test_lra_exhaustion.py 271, test_eq_canonical.py 108.
- sa-port-263's 7,239 counted session_live.py calls made by Python's compiler during these fallbacks, not fallbacks.
- Per workload on f42047a (all in converted queries, each = `refuse:object`): zero 94, fuzz 30 (27 compile, 3 literal),
  dev 17, transfer:7:60 17 (14, 3), port 6, cls 3, ground 2, transfer2:3:40 2, scope 1; 0 on the other 11. Total 172.
- No fix made: which object a slot holds is the first-occurrence rule (RULINGS 5). Proposed owner: formula's next step.

`_noncommutative_atoms` (engine.py:170) calls on f42047a, converted / other: suite 39,330 / 7,393; wiring 5,005, fuzz
3,127, lra 1,309 / 434, dev 834 / 6, zero 724, value 638, rootof 369, core 308, loop 244, scope 166, transfer:7:60 64,
cert 61, transfer2:3:40 40, opaque 31, budget 30, cls 23, port 22, ground 18, f6 8, twin 2.

Suite sums on f42047a (base 9151316): `rk:intern:engine` 990,355 (993,870), `rk:intern:input` 106,466 (106,780), `cls:eq`
722, `ad:cbm_noid` 0 (612), `fm:convert` 89,826, `fm:give` 82,344.

## Not started
Gate item 3 (j1/end.txt exists since ~01:32Z; lra cause), items 4b-4j, the bar. The report's standing rows not
measured this session: handler multiset, plant table, inventory, kept shares, `scaffold:core:kept_product:mismatch`,
`same:eq`, `_SPLIT`/`_CACHE` rows, cache_det.

## File:line map (this head)
- entry.rs: `fresh_session` :453, `cone_head` :558, `is_` :568 (give :605), `ent_is_many` :620 (give :691), other gives
  :733, :801. context.rs: `patched_method` :66, `context_session_from` :111, `verdict_from` :119, `ctx_verdict` :277.
- session.rs: `nid_in_formula` :1178, `refuse_object` :1188, `convert` :1397, `compile` :2176, `literal` :2185.
- formula.rs: as HANDOFF-sa-port-265.md (unchanged). session_live.py: `OURS` :936, `_install_context` :1123, `_rust_call`
  :1326, `_compile_formula` :1338, `_formula_literal` :1349. catch_count.py: `counted_verdict` :32, the class patch :41.
  rust_plugin.py:117. term_live.py `_Mark.rollback` :183 (plant 667 :189). term_discard.py `EXEMPT` :48, `check` :121.
- test_convert_once.py: the `is` group :80-:87, tests :116-:150. test_discard_exempt.py. fresh.py `--first` :34, :108.

## Helpers and output
- orion `~/sa-rust-ids-work/sa-port-266/`: p1/ (pyc266.py: PY_COMPILE split and `_noncommutative_atoms`, plugin or
  `arm()`; pyc_wl.py; suite266.sh SHA OUT [pytest args]; wl266.sh SHA OUT WL...; sum266.py DIR; chk266.py), suite/,
  suite-base/, wl3/ (wl/ is void: the probe was armed before `PY_COMPILE` was filled; wl2/ refused at install), fix1/,
  tw*/ (traces), bis/, bis-order.txt, twice-tests.txt, d1/.
- pareto1 `~/sp19/sa-rust-ids-work/sa-port-266/` (same names), trees `~/sp19/dev/sa-port-266-f42047a` and `-9151316`,
  each with its x86-64 .so (built-SHA.txt). Launch: `machine run pareto1 --shared --wait 4h -r WHY -- setsid bash
  ~/sp19/sa-rust-ids-work/sa-port-266/p1/suite266.sh SHA OUT`. The suite takes 3 minutes, 20 workloads under 2.
- To see where a second conversion comes from: a Python `traceback.print_stack()` and a Rust `Backtrace` at formula.rs's
  `tick(TWICE)`, under an env switch, was enough (not committed).
- Plants and counters: none taken this session (609-629, 668-669; 648-659, 673-679 still free).
