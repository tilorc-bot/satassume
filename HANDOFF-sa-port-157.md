# Handoff sa-port-157 (step 6g(c), issue 323)

6g(c1): fix **85f4d87** (rebased over adapters C2 29ee93e), full bar on pareto1 `~/sp19/sa-rust-ids-work/sa-port-157`
(done.txt; config orion `~/sa-rust-ids-work/sa-port-157/bar-run.sh`, base C2b suite rows
`~/sp19/sa-rust-ids-work/sa-port-153/bar-C2b/suite`, cert added to WLS, test_cf_laurent.py to TESTS).
**Not landed.** The bar was launched 08:17 UTC (shared lease, launcher orion `~/sa-rust-ids-work/sa-port-157/bar-launcher.log`,
pid in bar-launcher.pid). Wait for pareto1 `~/sp19/sa-rust-ids-work/sa-port-157/done.txt`, read the `sum` phase and the
five items, then land: rebase rule, `bash rust-spike/slice/p1/bar.sh land 85f4d87` without PUSH, read the incoming diff,
then PUSH=1, and write the 6g(c1) section of rust-spike/slice/results/port-6g.md (the 6g(a)/(b) form). Other bars on
pareto1 at handoff: sa-port-158 (5c7 on bd46e54) and sa-port-160 (Element._new E2): first to finish lands. If one
lands first and its diff touches the push guard, rerun the bar on the rebased head.
sa-port-155's 4c3356d bar was stopped at the architect's request (not needed: the imag reach is shown below), so its
sum phase never ran.
This handoff file is doc-only at the repo root (outside the guard), so tested 85f4d87 still covers the source.

## What 85f4d87 adds over 4c3356d
- The shadow on the direct splits: knowledge_core_live.py `SHADOW_SPLIT` / `shadow_split` (set by `install(shadow=True)`),
  handed to Rust's Common as py_fns `_shadow_split` by knowledge_common_live.install (a copy of py_fns, not the
  setattr loop). rows_tpl.rs `RowsTpl::split` calls it on every direct result; it counts `shadow:direct:NAME` (and
  `:split` when the result is non-empty) and compares with Python's split via `mismatch`. common.rs `Common::shadow_split`.
- test_knowledge_core_shapes.py: `DIRECT` maps the split counters; a case passes on the shell's counter or
  `shadow:direct:NAME`. Mismatch check unchanged. 10/10 on orion.
- knowledge_core_wl.py: 64 rows of `I*x + c*I*y` Adds (gaps ruling). core 1636 q MATCH; rows-imag-drop-last fired 8,
  DIFFER 6 answers / 32 end+stream (orion `~/sa-rust-ids-work/sa-port-157/c1b/`).
- Counts on core (c1b/core-rust.knowledge.json): rows:rust half 66 / bound 69 / imag 69; rows:python half 72 /
  bound 69 / imag 69 (= core:derived:* 69 each, plus 3 half product rests or derived results).

## TASK 4 answer (for the report)
Pure Python never calls `Rules.equiv` per query: it has no caller in satassume/ (table.py:151-153 writes an equiv
row's two rules itself). `ge2_alternatives` is called only from table.py:141 (`_premise_alternatives`) for a row
with an `int>=2` premise (`Row._ge2`, table.py:70), and no table in satassume has one (`rg "GE2|int>=2" satassume`
hits only table.py). So equiv-one and ge2-drop are Python removal candidates, not port items.

## Module count: 13 of 32, unchanged
Traces (orion rc-core.txt, rc-dev.txt, `rc.sh OUT WL core.py,wiring.py,functions.py`, dev --limit 400): core.py per
query on core (`_bound_split<-knowledge_core_live` 69, `_bound_templates<-engine` 120) and dev (`_half_templates`
genexpr 86, `_bound_templates` 10); functions.py `_unary...template` on core; wiring.py `template.<lambda>` 9 on dev.

## Next: 6g(c2) product (map)
- rows_tpl.rs Family::Product in `call` (~:340): `wiring_fn("_mul_factor_sets")` then `wiring_fn("_quotient_templates")`.
- Shells: knowledge_core_live.py `mul_factor_sets` (~:290) and `quotient_templates` (~:310). mul_factor_sets builds
  `[expr.args, (c, rest), ((c,) if c != 1 else ()) + (I, pi, s)]`; rests via `rest()` (kept_product scaffolding for
  products; keep those on the shell, as c1 does). quotient_templates calls `core.facts(('mul_quot', const_key(a) or
  None), core._quotient_rules, consts, (a, v, t, expr), 3)`: Rust has `Common::facts` and `core_quotient_rules`.
- tcore.rs: `core_mul_factor_sets` :405 (MulSets), `core_quotient_shape` :424, `core_is_number` :86, `core_rational`.
- Plants to add (both PLANTS lists): one in each direct path that can move an answer (e.g. drop the ct set; swap
  a and v in the quotient). Existing rows-mul-sets-first stays.
- Then power (`_exp_arg`, `ipi_split`, `_unit_angle`, `_unit_power_units`, `_pow_bound_templates`, `ipi_rules`,
  `irrational_root`, rows_tpl.rs :583-841), `constant_value` (:448, :798), the template builders and the 6e/6f module
  shells (brief's map).
