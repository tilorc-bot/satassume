# Handoff sa-port-155 (step 6g(c), issue 323)

6g(c1) **tested 4c3356d, not landed**. Its full bar is running on pareto1 (shared lease, launched 08:00 UTC, about 50 min,
sa-port-153's bar running beside it). Wait for pareto1 `~/sp19/sa-rust-ids-work/sa-port-155/done.txt`, read the `sum`
phase, then land: rebase rule, `bash rust-spike/slice/p1/bar.sh land 4c3356d` without PUSH, read the incoming diff, then
PUSH=1. If sa-port-153 (adapters C2) lands first and its diff touches the push guard, rerun the bar on the rebased head.
This handoff commit is doc-only at the repo root (outside the guard), so tested 4c3356d still covers the source.

## What 4c3356d does
rows_tpl.rs's Addition family computes `_half_split`, `_bound_split`, `_imag_split` straight from the query's TermTable
(tcore.rs) instead of through knowledge_core_live.py's shells via `wiring_fn`:
- `RowsTpl::split` and `direct_split` (rg them in rows_tpl.rs; end of file: `QIds`, `direct_split`, `sympy_one`).
- `Common::query` (common.rs, beside `kept`): term_live's innermost `_Query`, None if none or kept.
- `PyTermTable::tt` (py.rs) and `refuse` made pub(crate).
- Falls back to the shell (counted `rows:python:NAME`) wherever the shell does more than read input ids: no query or a
  kept one, an arg that isn't an input term of its own class (the shell's `core:derived`), a derived result id, or a
  product rest (the shell's `rest` → `kept_product` SymPy scaffolding). Direct calls count `rows:rust:NAME`.
- No shadow `check` on the direct path (the Python-against-Rust MATCH covers it). tcore.rs's source mutants
  (mutate_knowledge.py 'core-*') still reach it, since the direct path calls the same tcore functions.
- Plants (rows_tpl.rs PLANTS and knowledge_common_live.PLANTS): rows-half-parity, rows-bound-coeff-one,
  rows-imag-drop-last.

## Orion checks (rows ~/sa-rust-ids-work/sa-port-155/c1/)
- core (1572 q): MATCH. f6: MATCH. dev first 1500: MATCH.
- Counts (core, rc-core.txt by rc.sh): rows:rust half/bound/imag 53 each, rows:python 69 each = core:derived:* 69 each
  (args the shell also leaves on Python). f6 (f6-rust.knowledge.json): rust half 144 / bound 170 / imag 170; python
  half 32, bound 6, imag 6 (half's extra 26 are product rests or derived results).
- Plants on core: rows-half-parity fired 10 DIFFER (caught), rows-bound-coeff-one fired 39 DIFFER (caught),
  rows-imag-drop-last fired 0 on core and f6, even firing on any non-empty split: `core_imag_split` returned None every time.
  The bar shows whether dev/fuzz/wiring/the other workloads reach it; if none does, the imag split needs a workload query
  (an Add with an I-coefficient term, e.g. `x + I*y` with suitable assumptions, in knowledge_core_wl.py) under the gaps
  ruling, or the plant is reported void with that reason.
- The wiring-workload imag plant run on orion was left to finish detached (c1/wiring-*); not read.

## Module count: 13 of 32, unchanged by 6g(c1)
core.py still runs per query: `_half_templates`, `_bound_templates`, `_recip_templates`, `_imag_templates` (via
wiring_fn), the Mul/Pow shells, and pi_split/ipi_split from functions.py. Count against ~/dev/architect/STATUS.md's
"Counted modules" list. Trace for the report: `rc.sh OUT WL core.py,wiring.py,functions.py` (orion
~/sa-rust-ids-work/sa-port-155/rc.sh; registry_count.py --passes 1 --trace).

## For the 6g(c1) report (beyond the brief's MUST list)
- Planner's precision on equiv-one and ge2-drop (architect message, 8 Nov, also in addenda/sa-port-6d-plants-ruling.txt):
  say whether pure Python calls `Rules.equiv` / `ge2_alternatives` per query. Removal candidates only if it doesn't (or
  only offline/import); if it does, name where Rust gets the same result, which the MATCH covers. Not checked yet:
  `rg -n "equiv\(|ge2_alternatives" satassume/knowledge` and a trace on dev.

## Next parts (6g(c) map, unchanged from HANDOFF-sa-port-145.md)
Same pattern for the rest of `wiring_fn`'s callers: `_mul_factor_sets`/`_quotient_templates` (product), `_exp_arg`,
`ipi_split`, `_unit_angle`, `_unit_power_units`, `_pow_bound_templates`, `ipi_rules`, `irrational_root` (power), then the
template builders (`_half_templates` etc. call `facts`, which is already Rust's `Common::facts`). The 6e/6f module
shells: core.py:120, :183, :392, :400; functions.py:41, :100, :150, :214, :328, :360; special.py:88; nodes.py:30, :37;
rootof.py:45; physics.py `quantity_units`; stats.py:22; wiring.py:140, :147, :148, :189.

## Bar config
orion ~/sa-rust-ids-work/sa-port-155/bar-run.sh (pareto1 ~/sp19/bar-run-sa-port-155.sh, bar.sh as
~/sp19/bar-sa-port-155.sh): sa-port-145's plus the three new plants, BASE ~/sp19/sa-rust-ids-work/sa-port-145/suite.
Launcher output: orion ~/sa-rust-ids-work/sa-port-155/bar-launcher.log (pid in bar-launcher.pid).
