# Handoff sa-port-190 (6g(c6), issue 323): `_pi_trig` + plain `_unary` in Rust, built and checked on orion, not barred

The 6g c3+c4+c5 stack landed as **eac4537** (tested af63d20; report 8c14b08; marker touched 23:17Z).

## c6 state (this commit, on eac4537)
- rows_tpl.rs: `Family::Unary`, `Family::PiTrig`, `UnaryRows`, `Plain` (Rows | Py, the untagged `_cosh_shift` called back,
  `rows:python:_cosh_shift`); `unary_rules` (gen's rules + tf6::pi_trig_rules, `rows:rust:_pi_trig_rules`); `unary_call`,
  `pi_trig_call` (end of file); `pi_split` in ONE and in direct_pow's ipi_split arm (`imag = name == "ipi_split"`).
  Counters: rows:rust:_unary, rows:rust:_pi_trig, rows:rust:pi_split, rows:rust:_pi_trig_rules.
- Plants (rows_tpl.rs PLANTS and knowledge_common_live.py PLANTS): rows-pi-split-shift, rows-pi-trig-flip,
  rows-unary-key-none, rows-unary-drop-last (the last added for a workload catch of the Unary family).
- functions.py tags `_satassume_rows` (unary: slots and units None; pi_trig: `(.., cos_, split_ is ipi_split)`) and
  `template._satassume_plain`; wiring.py imports pi_split; offline_data.json regenerated (`--check` same 484dac49…).
- knowledge_core_live.py: shadow_split branches `pi_split` and `_unary`/`_pi_trig` (`_functions_tpl_py`: Python's template
  with functions.facts captured, `_pi_trig_rules` unwrapped). test_knowledge_core_shapes.py: 6 new cases (29 total).

## Evidence (orion, ~/sa-rust-ids-work/sa-port-190/)
- tests.txt: bar's TESTS list 749 passed, 3 skipped (before rows-unary-drop-last was added; rerun it).
- plantshape-c6.txt: the first three plants each pass plain and FAIL (shadow mismatch) planted.
- quick/: f6 and core py vs rust MATCH. Plants: pi-split-shift fired f6 92 / core 42, DIFFER both; pi-trig-flip fired
  f6 38 / core 21, DIFFER both; unary-key-none fired 0 on both (no constant argument reaches the plain unary: void on
  workloads, caught by its shapes case). rows-unary-drop-last fired f6 40 / core 22, DIFFER both (quick/plant-*-rows-unary-drop-last.*).
- Counts f6: rows:rust:_pi_trig 92, pi_split 100, ipi_split 130, _unary 8, rows:python:_cosh_shift 130,
  registry:rust:_pi_trig 230; core: _pi_trig 97, pi_split 48, ipi_split 109 (rows:python:ipi_split 2), _unary 6,
  `core:_pi_split` 57 (the shell, from `_exp_ipi` and the 2 fallbacks).

## Next
1. Rerun the TESTS list (with rows-unary-drop-last in); commit; module-count retrace (rc.sh, see brief).
2. Bar on pareto1 only after sa-port-189's 5c10c bar (pareto1 lease 'sa-port-189 bar 5c10c', from ~23:20, ~02:00) ends
   and it lands: rebase on rust-slice, config = job3.sh's plus the four new plants, BASE = the last landing's suite.
   Check STATUS.md's 90% line and `agent usage` first (90% projected 03:24-06:26 on 9 Nov).
