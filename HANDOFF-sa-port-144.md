# Handoff sa-port-144 (step 6g(b), issue 323)

Branch port/6g, head 493cefc (WIP, pushed; this file is the commit after it), on rust-slice 6526445. 6g(b) is not at
the bar; 6g(c) not started. Context budget reached, nothing blocked.

## Done (493cefc, on 66615fa)
- `power` ported: rows_tpl.rs `Family::Power` (`power_rows`, `RowsTpl::pow_call`, `pow_build`, `atom_number`,
  `const_key`), `ShapeItem::Head` in `matches` (now a `RowsTpl` method, `_exp_arg` called back). wiring.py:347 tags
  `pow_templates` with `_satassume_rows = ('power', 'pow', gen, False, False)`; offline_data.json source hash redone
  (body unchanged). Called back, counted `rows:python:<name>`: `_exp_arg`, `ipi_split`, `_unit_angle`, `ipi_rules`
  (handed a Rust `rule` closure), `irrational_root`, `_unit_power_units`, `_pow_bound_templates`, `constant_value`;
  scaffolding `rows:python:Mul` (`Mul(k, e)`) and `rows:python:Add` (`b + c`). Counters `rows:power`, `rows:pow_build`.
- 7 power plants (rows_tpl.rs PLANTS and knowledge_common_live.PLANTS): rows-pow-key-same, -times-skip, -head-any,
  -irrational-skip, -ipi-skip, -unit-drop, -of-constant-skip.
- Hidden-gap workload `knowledge_wiring_wl.py` (`live.py wiring`, live.py:273 tuple). NOTE: `knowledge_rows_wl.py` is a
  different, older workload (_rows_runtime, knowledge_fresh.py); don't confuse them.
- reach1 (sa-port-142's, `~/sa-rust-ids-work/sa-port-142/reach1/`): dev, opaque, core, f6 MATCH (old build). At 0 on all
  four: registry:rust:Max/Min/Piecewise_rows_templates, rows:wide, rows:wide_formulas, rows:clauses,
  rows:piecewise_values, rows:python:_imag_templates. fuzz/value/rootof were still running (old build, 66615fa).
- First wiring version (4848 queries, `~/sa-rust-ids-work/sa-port-144/w1/`, build 493cefc's rows_tpl.rs): MATCH
  (answers_sha 9afca434f776b88d both). Reached: Max 13, Min 13, Piecewise 5, add 9, mul 16, pow 11, rows:wide 9,
  wide_formulas 16, clauses 1792, piecewise_values 5, _imag_templates 4, common:wide 7. Not reached then: ipi_split,
  _unit_power_units (SymPy builds `E**x` as `exp`); the workload now adds unevaluated powers (6512 queries).
- Rules.equiv / ge2_alternatives (6d's equiv-one, ge2-drop): no runtime caller on Rust's path. rows_tpl.rs calls neither;
  table.py inlines equiv and calls ge2_alternatives, but its only runtime caller is core.ipi_rules, which on Rust is
  sa_solver.core_ipi_rules (port-6d.md). So they are Python removal candidates (ruling), unless w2 shows them firing.
  wide-drop (Common.instantiate's wide, via registry `_split` -> Compiled.wide_formulas): common:wide 7 on wiring, so
  w2's common-wide-drop run says whether it's caught there.

## Running when I stopped (orion, detached, mine; the clone must not be rebuilt or edited until it ends)
`~/sa-rust-ids-work/sa-port-144/w2/` (plants.sh, pid in w2.pid): wiring (6512) Python, Rust, then each of the 21 rows
plants plus common-wide-drop, common-equiv-one, common-ge2-drop, 4 at a time (~35-40 min from 05:44 UTC). Ends with
`w2/plants-done.txt`. Per plant: `wiring-cmp<PLANT>.txt` (last line MATCH/DIFFER) and
`wiring-rust<PLANT>.knowledge.json` (`counts['plant:fired']`). Read the baseline `wiring-cmp.txt` first (power reached:
rows:power, rows:python:ipi_split, rows:python:_unit_power_units). A plant that fires and MATCHes is void: find the
workload or query that catches it (dev/core reach add/mul/pow), or say why it can't matter.
Also `trace/wiringall.txt` (registry_count.py wiring --trace wiring.py, full): may or may not have finished.

## Count (not yet stated in a report)
wiring.py doesn't count yet: per-query Python left in it (registry_count.py --trace wiring.py, pass 1, 1500 queries):
dev: `_attributed.<locals>.template` (wiring.py:189, the AFTER_ROWS wrapper) 6, `template.<locals>.<lambda>` 29 and its
genexpr 31 (the `_unary` slot lambdas, wiring.py:147-148, called from functions.py; nary's :140 likewise). core, f6 and
wiring (first 1500): none. These go with 6g(c)'s functions.py shells. So after 6g(b) the count stays 12 of 32 unless
6g(c) removes them; core.py also still runs per query through knowledge_core_live's shells (rows:python:_half_split etc.).

## Left
1. Read w2; plants table (fired / caught) per plant; void ones caught elsewhere or named. Then the bar on pareto1:
   copy `~/sa-rust-ids-work/sa-port-123/bar-run.sh` (orion) and pareto1's `~/sp19/sa-rust-ids-work/sa-port-131/config.txt`;
   BASE = the latest landing's suite rows (check `git log origin/rust-slice`: if 5c7-tests or adapters landed, theirs,
   else 6d's `~/sp19/sa-rust-ids-work/sa-port-134/bar-5c6/suite` as 6d used); WLS = f6 value rootof core opaque scope
   wiring; PLANTS = the 21 rows plants + dispatch-ignores-epoch dispatch-redefines-off dispatch-user-off with-closed-skip;
   SUITE_PLANTS as 6g(a)'s; TESTS as 6d's config.txt plus any 6g(a) tests. Rebase first (LANDING ORDER).
2. Land, report (port-6g.md gets a 6g(b) section), the count with the trace above.
3. 6g(c): knowledge_core_live.py:149-377 are the core shells (`half_split`, `bound_split`, `recip_templates`,
   `imag_split`, `imag_templates`, `mul_factor_sets`, `quotient_templates`, `unit_angle`, `exp_arg`, `ipi_rules`,
   `irrational_root`, `unit_power_units`, `pow_bound_templates`, installed by setattr at :443): rows_tpl.rs's
   `wiring_fn` calls should go straight to the `sa_solver.core_*` they wrap. Then functions.py/special.py/nodes.py/
   rootof.py/physics.py/stats.py shells (brief's map) and wiring.py:140/:147/:148/:189.

## Notes
- Build safely while a run uses the clone: `cargo build --release` in solver_rs, then `cp ... sa_solver.so.new && mv`
  (build_solver.sh's cp rewrites the loaded .so in place).
- registry_count.py's pass 2 shows dispatch {} (memo); read pass 1 for per-query calls. core showed "5 raised" on both
  passes there (not looked into; check against the base before calling it a finding).
