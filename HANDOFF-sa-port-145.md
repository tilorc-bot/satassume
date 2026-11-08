# Handoff sa-port-145 (step 6g, issue 323)

6g(b) **landed b838d3f** on rust-slice (tested 7e730df; report in results/port-6g.md, "Step 6g(b)"; rows pareto1
`~/sp19/sa-rust-ids-work/sa-port-145/`). 6g(c) not started. Branch port/6g = b838d3f. Nothing running.

## Module count after 6g(b): 12 of 32, unchanged
Trace on 7e730df (orion `~/sa-rust-ids-work/sa-port-145/trace/{dev,core,f6,wiring}.txt`, registry_count.py
--trace wiring.py,core.py,functions.py; read `pass1:trace` lines with `[query]`):
- wiring.py per query: wiring.py:189 `_attributed.<locals>.template` (dev 6, f6 24), :147-148 `_unary` slot lambdas
  called from functions.py (dev 31+33, f6 134+167). Nothing on the wiring workload.
- core.py per query: `_half_split`/`_bound_split`/`_imag_split`/`irrational_root`/`_unit_power_units` from
  knowledge_core_live.py (the shells call Python core too), `_half_templates`/`_bound_templates`/`ipi_split` called by
  the engine (Rust callbacks via `wiring_fn` show as `<-engine.py`), `pi_split`/`ipi_split` from functions.py.
- functions.py per query: `_unary`, `_pi_trig`, `_exp_ipi`, `_cosh_shift`, `nary` templates and their `build`s,
  `parts_of_round_templates` (via wiring.py:189), `_in_unit_interval_units`.

## 6g(c) file:line map
- rows_tpl.rs `RowsTpl::wiring_fn` (:283) is the one place Rust calls wiring-module names back; its callers: :319
  `_mul_factor_sets`, :327 `_quotient_templates`, :345/:347 `_half_split`/`_half_templates`, :349-355 `_bound_split`/
  `_bound_templates`/`_recip_templates`, :361/:363 `_imag_split`/`_imag_templates`, :421/:763 `constant_value`, :556/:648
  `_exp_arg`, :660 `ipi_split`, :691 `_unit_angle`, :733 `_unit_power_units`, :744 `_pow_bound_templates`, :800
  `ipi_rules`, :806 `irrational_root` (line numbers before 7e730df's +10/-4 plant edits; rg the names).
- knowledge_core_live.py:149-401: the shells; each converts args to ids in `q.table` (`ids_of` :79), calls
  `sa_solver.core_*`, converts back, shadow-checks against Python (`check` :143, `fallback` :110). Installed by setattr
  at :443 (`swap`, :424-433 for the rule tables). Going direct means rows_tpl.rs needs the query's table and id
  mapping on the Rust side: find how `query()` (:68) gets `q.table` and whether Common can hold it.
- 6g(c) module shells: core.py:120, :183, :392, :400; functions.py:41, :100, :150, :214, :328, :360; special.py:88;
  nodes.py:30, :37; rootof.py:45; physics.py `quantity_units`; stats.py:22; wiring.py:140, :147, :148, :189.
- Plants: rows_tpl.rs PLANTS (:29-50) and knowledge_common_live.PLANTS (:27-31) must list the same names.

## Bar config used (copy for 6g(c))
orion `~/sa-rust-ids-work/sa-port-145/bar-run.sh` (on pareto1 as `~/sp19/bar-run-sa-port-145.sh`, with
`~/sp19/bar-sa-port-145.sh` = p1/bar.sh). BASE for the next bar: this landing's suite rows,
`~/sp19/sa-rust-ids-work/sa-port-145/suite` (unless something landed after b838d3f). Took 51 min with 26 plants on
dev, fuzz and 9 workloads plus 4 suite plants. Plant runs on orion: copy `~/sa-rust-ids-work/sa-port-145/{short.sh,plants.sh}`.

## Notes
- Build while a run uses the clone: `cargo build --release` in solver_rs, then cp to sa_solver.so.new and mv.
- `python -I` drops PYTHONPATH; run tree scripts without it.
- registry_count.py's "5 raised" (core) and "2 raised" (f6) in both passes: also on 493cefc; not looked into.
