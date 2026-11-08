# Handoff sa-port-161 (step 6g(c), issue 323)

**6g(c1) landed: 30f3309** on rust-slice (tested 85f4d87; landing rebase brought nothing). Report: the 6g(c1) section of
rust-spike/slice/results/port-6g.md (bar rows pareto1 `~/sp19/sa-rust-ids-work/sa-port-157/`, sum.txt).

**6g(c2) product: 14b76fd** on port/6g (over 30f3309), full bar running on pareto1 since 09:52 UTC 8 Nov:
`~/sp19/sa-rust-ids-work/sa-port-161/` (wait for its done.txt, then sum.txt). Config orion
`~/sa-rust-ids-work/sa-port-161/bar-run.sh` (pareto1 `~/sp19/bar-run-sa-port-161.sh`, bar.sh as `~/sp19/bar-sa-port-161.sh`):
sa-port-157's plus rows-mul-ipi-drop and rows-quot-swap, BASE = c1's bar suite rows `~/sp19/sa-rust-ids-work/sa-port-157/suite`.
Launcher log orion `~/sa-rust-ids-work/sa-port-161/bar-launcher.log` (pid in bar-launcher.pid). Other bars on pareto1 at
handoff: sa-port-158 (5c7 on bd46e54), sa-port-160 (Element._new E2 on 5b705df). First to finish lands; if one lands
first and its diff touches the push guard, rerun the bar on the rebased head.
This handoff file is doc-only at the repo root (outside the guard), so tested 14b76fd still covers the source.

## What 14b76fd adds
- rows_tpl.rs Family::Product calls `self.split(.., "_mul_factor_sets" / "_quotient_templates", expr)`; `direct_split`
  takes the Mul itself for these two (a 1-tuple to `QIds::ids`) and returns `(result, shown)`; `direct_rows` (product
  pair) then `direct_add` (c1's three Add splits).
- `_mul_factor_sets` direct: `core_mul_factor_sets`; any ct set goes to the shell (its rest is always the Mul's other
  >= 2 factors, `kept_product`); the (c, I, pi, s) set only when s is an input Mul (`q.one`), else the shell.
- `_quotient_templates` direct: `core_quotient_shape`, objects by `q.obj`, then `Common::facts` with the shell's key
  (`('mul_quot', const_key(a) or None)`), consts (`{0: a}` when a is an Atom and `core_is_number`), objects
  `(a, v, t, expr)`, node 3; gen is core's `_quotient_rules` (knowledge_core_live's Rust rules after install). The
  shadow gets the shape `(a, v, t)` or None; knowledge_core_live `shadow_split` compares it with `_quotient_shape_py`.
- py.rs `core_pq` pub(crate). Plants in both lists: rows-mul-ipi-drop, rows-quot-swap.
- test_knowledge_core_shapes: DIRECT maps `core:_mul_factor_sets`, `core:_quotient_templates`; new case
  `core-quotient-rules` (`Q.integer(x*y**-1)`, odd x, even y). 11/11 on orion.

## Orion checks (rows `~/sa-rust-ids-work/sa-port-161/c2/`, on 27075e4 = 14b76fd's source before the rebase)
- core 1636 q MATCH, dev 1985 q MATCH.
- Counts: core rows:rust mul 72 / quot 184, rows:python mul 158 / quot 46 (= core:_mul_factor_sets 158,
  core:_quotient_templates 46 from the shell); dev rust 46 / 63, python 36 / 19.
- rows-quot-swap fired 44 on core, DIFFER 18 answers / 72 end+stream (caught).
- rows-mul-ipi-drop fired 0 on core and dev: every direct `_mul_factor_sets` call there has no ipi set with an input
  Mul s (s is derived, e.g. x*y of I*pi*x*y, so it goes to the shell). Unless the bar finds a reach, report it void with
  that reason (the direct path then returns only `[expr.args]` on these workloads).
- shadow:direct counts for c1 on 85f4d87 (script `/tmp/claude-1000/-home-tilo-dev-satassume/33739a1f-8588-406e-9702-a842f7227440/scratchpad/shadowcount.py`, copy in
  `~/sa-rust-ids-work/sa-port-161/shadow-c1.txt`): half 5, bound 5 (2 split), imag 5 (1 split), mismatch 0. Rerun it
  on 14b76fd for c2's report (run from the clone root with rust-spike/slice on PYTHONPATH).

## Module count: 13 of 32, unchanged by c1 (and expected unchanged by c2: core.py's templates still run per query)
For c2's report, retrace with `~/sa-rust-ids-work/sa-port-161/rc.sh OUT WL core.py,wiring.py,functions.py` (clone path
already sa-port-5), core and dev, pass 1 `[query]` lines.

## Next after c2 lands
Power (rows_tpl.rs `wiring_fn` callers ~:583-845: `_exp_arg`, `ipi_split`, `_unit_angle`, `_unit_power_units`,
`_pow_bound_templates`, `ipi_rules`, `irrational_root`; tcore.rs `core_unit_angle`, `core_exp_arg`, `core_irrational_root`,
`core_pow_bound_shape`, `core_unit_power_units`), `constant_value` (~:448, ~:798), the template builders, then the 6e/6f
module shells (brief's map). Same pattern: add a `direct_rows` arm, the shadow via `shadow_split` (special-case its
compare in knowledge_core_live when the result is a template object, as for the quotient), plants in both lists, DIRECT
entries in test_knowledge_core_shapes.
