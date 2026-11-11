# HANDOFF sa-port-265: formula step (issue 323), ninth part

Branch `port/formula`, head = this commit, on rust-slice **9151316**. **Unbarred, unlanded.** Handed off at the context
budget, **after gate item 1's code and tests (this commit), before its suite numbers**; gate item 2 only started (read
and one probe, nothing changed). Tables: rust-spike/slice/results/port-formula.md, last section.

## Gate item 1 (convert once): what is in the commit
- session_glue.rs:120 passes the session's core as `nodes`. `rv_relevant`, `rv_consistent`, `rv_part_consistent` hold a
  `Hand` and pass it to `_theory_scope` (`theory_scope_from`) and `verdict` (`verdict_from`).
- A `Hand` keeps a refusal with the refused object (`Held::Refused`). `fm:twice` ticks before the walk.
- `fm:again` (counter 647): on only after `sa_solver.formula_track(True)`. `sa_solver.formula_held()`: formulas held by
  live entries. Plant 608 `fm-hand-kept` (H2's plant).
- test_convert_once.py: 5 kept tests (no twice in one entry; H1; H2; plant 607; plant 608). Plants 607 and 608 are out
  of test_formula_nodes.py's parametrization. Both files: 20 passed.
- scope, dev, zero: `fm:nosession` 0, `fm:twice` 0; `fm:convert` 1,138 / 1,665 / 1,394; per-query lines equal to
  sa-port-264's c1.
- Ruling on report ed9beca (planner ~00:52Z 11 Nov, by the architect): "at most one per distinct input object" is per
  query. `fm:again` across queries (scope 283, dev 1,134, zero 1,251) is reported as information; inside one ask (scope
  0, dev 30, zero 5) is the remaining violation and goes to the part 3 follow-up (one `Hand` per ask), not to formula.

## Gate item 1: what is still owed before it is done
1. Read the detached jobs (orion, started by me):
   - `~/sa-rust-ids-work/sa-port-265/t1` (tests.sh: every slice test file, one process each; `t1/tests.txt`, end marker
     `t1/end.txt`). At 00:56Z 38 of 58 read: 35 passed; test_catch_count.py 3 failed, test_cf_diff.py 1 collection
     error, test_handler_count.py 2 failed (the known invocation rows, gate 4f). **It ran on the tree before the
     results section was added, same source and .so as this commit.**
   - `all.sh` after it: `a1` (SA_FM_TRACK=1), `a1q` (SA_FM_TRACK=query), `b0` (before, TREE=sa-port-260/dg at 78962f7) on
     19 workloads, marker `all-19.txt`; then lra for a1q and b0, marker `all-end.txt`. Each dir has `WL.counts.json`,
     `exit.txt`. Wanted: `fm:nosession` 0 and `fm:twice` 0 on all 20, `fm:convert` before and after, `fm:again` both ways,
     and a1's per-query lines equal to a1q's.
2. The suite on this head (pareto, shared lease; x86-64 .so built on pareto1): `fm:nosession` and `fm:twice` summed
   from the rows' session counts. Under `-p handler_count` or catch_count a class-patched `Engine.verdict` is called by
   name (context.rs `patched_method`), a nested entry: if `fm:twice` is above 0 in the suite, look there first.
3. Plant 608 on the two-order harness (gate 4e's harness).

## Gate item 2 as far as it got
- The term_live fallback: on this head the test alone and tests/test_transfer.py as a file show **0** relations.py frames
  in a converted query (`tl/probe.sh TREE OUT pytest-args`; `tl/s1`, `tl/s2`; the probe fires on Python: `tl/s1py`).
  `tl/trace42.py` (the five queries, `_ids` returning None in a converted query): 0. Not decided: gone since ba1ca22, or
  only with the suite's history. Next: probe.sh on the full suite on this head (and on base if it is still 42).
- PY_COMPILE: session_live.py `_compile_formula` :1339. Three reasons to split: table not a `TableView`; `dv` not the
  session's `dvar`; `table.core.compile` False (`fm:refuse:*`). Not measured.

## File:line map (at this head)
- formula.rs: NAMES :62 (`fm:again` :83), PLANTS :103 (607 :113, 608 :114), ENTRIES/SEEN :122-124, TRACK :129, HELD :131,
  KEPT :133, `convert_or` :487 (`fm:twice` :494, `fm:again` :497), `Nodes` :544, `Hand` :554, `Held` :558, `enter` :566,
  `enter_inner` :573, `node` :580, `give` :615, `Drop` :637, `formula_plant` :690, `formula_held` :706, `formula_track` :713.
- session_glue.rs: `assume_formula` :78, the scope call :121. relevance.rs: `consistent_body` :618 (`verdict_from` :638),
  `consistent` :648, `part_consistent` :665, `relevant` :681 (`theory_scope_from` :760), the rv entries :791, :822, :827.
- test_convert_once.py: `_main` :24, tests :106-:140. test_formula_nodes.py :155.
- Unchanged by this session: HANDOFF-sa-port-264.md's map for session.rs, scope_core.rs, budget.rs, context.rs, entry.rs,
  session_live.py (`PY_COMPILE` :25, `_rust_call` :1327, `_compile_formula` :1339, `_formula_literal` :1349). term_live.py:
  `term_id` :332, `_ids` :445, `_relation_atom` :459, `_is_number` :555. sympy_api.py: `_formula` :496, `_ask_general` :576,
  `_engine_ask`'s calls :591, :595.

## Watch
- Helpers in `~/sa-rust-ids-work/sa-port-265/`: cnt.sh / cnt.py (SA_FM_TRACK=1 or =query; TREE= another tree), tests.sh
  OUT [FILES], all.sh, tl/probe.sh, tl/trace42.py, tl/trace42b.py, build0-4.log.
- j1 (`~/sa-rust-ids-work/sa-port-260/j1`) had no end.txt at 00:56Z; 7 MATCH written. HANDOFF-sa-port-260.md says how to
  read it.
- Plants 600-608 and 660-667 are used; 609-629 and 668-669 are free. Counters 630-647 and 670-672 are used; 648-659 and
  673-679 are free.
- test_transfer.py::test_protocol_on_fuzz and ::test_models_respect_transfer fail on Rust here and in the base rows
  (port-census/pr328-check/suite-rust/pytest.log).
