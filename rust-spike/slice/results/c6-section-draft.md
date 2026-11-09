
# Step 6g(c6): `_pi_trig` and the plain `_unary` as rows_tpl.rs families, `pi_split` direct (issue 323)

Built by sa-port-190 (64df0db/82c833f), rebased, barred and landed by sa-port-191.

**Tested source: 7890bf3** = rust-slice b384ec1 (5c10c) + 1f0d3bc (c6 source, was 64df0db) + 7890bf3 (results/ only:
the predecessor's handoff). Rebase of 82c833f onto b384ec1 clean. **Landed** by `PUSH=1 bar.sh land 7890bf3` with this
report (results/ only on top); incoming diff at landing: @@INCOMING@@.

Incoming diff at the rebase (eac4537..b384ec1, 5c10c): engmemo.rs, relations_core.rs, session.rs, test_cones_core.py and
@@OTHERS@@ (649 insertions, 35 deletions in guarded source). The bar ran on the rebased source, so it covers them.

Orion checks on 7890bf3 before the bar: build OK; the bar's TESTS list plus 5c10c's test_cones_core.py, `-n 4`: **759
passed, 3 skipped** (`~/sa-rust-ids-work/sa-port-191/tests.txt`; 749 + test_cones_core's 10 = 759). plantshape
(`plantshape.txt`): rows-pi-split-shift, rows-pi-trig-flip and rows-unary-key-none each pass plain and FAIL planted
(shadow mismatch on `core:pi_split`/`core:_pi_trig`, `core:_pi_trig`, `core:_unary`). rows-unary-drop-last has no shapes
case (it is a workload plant, caught on f6 and core).

**Code** (1f0d3bc). rows_tpl.rs `Family::Unary` (`functions._unary(tag, gen)` with neither slots nor units: key `(tag,
const_key(x) or None)`, objects `(x, expr)`, node 1, `gen`'s rules) and `Family::PiTrig` (`_pi_trig(tag, gen, cos_,
split_, plain)`: `pi_split`/`ipi_split` straight from the query's table; no split: the plain template, in Rust when it
is a tagged `_unary`, else the untagged plain `_cosh_shift` called back and counted `rows:python:_cosh_shift`; a split:
key `(tag, None, 'pi', c, has_s, const_key(s) or None)`, rules `gen`'s plus tf6's `pi_trig_rules`). `pi_split` joins
ONE and direct_pow's ipi_split arm. functions.py tags `_satassume_rows`/`_satassume_plain`; wiring.py imports
`pi_split`; offline_data.json regenerated. knowledge_core_live: `shadow_split` branches for `pi_split` and
`_unary`/`_pi_trig` (`_functions_tpl_py`: Python's template with `functions.facts` captured). Six shapes cases (29 total).

## The bar (on 7890bf3)
@@BAR@@

**Shadow (test_knowledge_core_shapes, 29 cases, orion on 7890bf3, `~/sa-rust-ids-work/sa-port-191/shadow.txt`):
shadow:mismatch 0, answers equal.** shadow:direct per name: `_half_split` 11, `_bound_split` 11, `_imag_split` 11,
`_mul_factor_sets` 21, `_quotient_templates` 24, `_exp_arg` 17, `_unit_angle` 16, `ipi_split` 3, `irrational_root` 16,
`_unit_power_units` 2, `_pow_bound_templates` 14, `ipi_rules` 2, `constant_value` 61, `_half_templates` 1,
`_bound_templates` 7, `_recip_templates` 7, `_imag_templates` 2; c6: `pi_split` 7, `_pi_trig` 4, `_unary` 3.

**The parts ruling's three 6g(a) conditions still hold.** Direct, on orion on 7890bf3
(`~/sa-rust-ids-work/sa-port-191/dispatch-direct.txt`): `dispatch_direct.py` plain exit 0 (user path 2, BAD 0);
**dispatch-user-off caught** (user path 0, BAD 1, exit 1); dispatch-ignores-epoch caught (BAD 3, exit 1);
dispatch-redefines-off caught (BAD 2, exit 1). @@SUITEPLANTS@@

**Module count (count rule): 14 of 32, unchanged.** Orion retrace on 7890bf3 (`rc.sh OUT WL
core.py,wiring.py,functions.py,registry.py`, pass 1 `[query]` lines; `~/sa-rust-ids-work/sa-port-191/rc-{dev,f6,core,wiring}.txt`,
diffed against sa-port-187's on af63d20):
- Gone from the per-query trace: `_pi_trig.<locals>.template` (f6 230, core 104, dev 4 before) and its build; `core.py:pi_split`
  from functions (f6 100, core 48, dev 3 before) entirely; `ipi_split` from functions on f6 (130 before).
- Left: `ipi_split` from functions only through `_exp_ipi` (core 55, wiring 2, dev 1) and from session_live (core 2, the
  fallbacks); `_cosh_shift.<locals>.template` f6 130, core 1, dev 1 (the untagged plain, called back), and the plain
  `_unary.<locals>.template` it calls (f6 50, core 1, dev 1); the slotted `_unary` from the engine (f6 86, dev 31),
  `nary` (f6 48), `_exp_ipi` (core 56, wiring 2, dev 1), `parts_of_round_templates` + `_attributed` (f6 24, dev 6), and
  core.py's `_bound_split`/`_half_split`/`_imag_split` (dev 3, f6 6, core 69, wiring 4), `_coeff_term`, `_imag_term`,
  `_unit_power_units` core 15, as on af63d20. So functions.py, core.py and wiring.py still don't count; registry.py has
  no `[query]` line, as before. (The engine.py -> session_live.py caller names in the trace come from 5c10c.)
