# HANDOFF sa-port-215 → successor (6i(c), issue 323), 10 Nov ~04:55 UTC

Branch port/6i-c in ~/dev/sa-port-7, from origin/rust-slice db7130a (harness fix landed; marker harness-landed).
Code: 377e188 + 1d452e0 (= candidate, pushed). Handed off at context, with both jobs detached.

## Running (read these first)
- BAR on 1d452e0: pareto1 `~/sp19/sa-rust-ids-work/sa-port-215/bar-6ic`, end marker `end.txt` there (written inside the
  detached command), log `bar.out`; lease 76bb0398; orion launcher pid in `~/sa-rust-ids-work/sa-port-215/machine-run.pid`,
  launcher script `launch-bar.sh` (same dir). Config: BASE = sa-port-209/bar-install-order/suite (the latest landing's
  bar, d77d3db landed as db7130a); PLANTS = rows-number-id-shift rows-product-first rows-pow-bound-args-swap
  rows-mul-ct-drop; SUITE_PLANTS=zero; WLS = the 11; TESTS = 209's list + test_knowledge_rows.py + test_core_derived_args.py.
- CAND PROBE on the final build (.so md5 changes with each build; this is 1d452e0's): `~/sa-rust-ids-work/sa-port-215/probe/
  probe-cand/`, end marker `end.txt`; `python3 probe/summ.py probe/probe-cand`. Base: `probe/probe-base/` (db7130a) and
  `probe/summ-base.txt`. Do NOT rebuild the orion .so before probe-cand/end.txt exists.
- Base fallback rows (dispatch.rs:242 / rows_tpl.rs:413 / ad:cbm_noid per template): `~/sa-rust-ids-work/sa-port-215/
  fb-base-209.txt` (209's bar); `fbcounts.py` there, run it on the bar dir for the candidate.

## Findings so far
- Base (db7130a) per-query core.py calls = sa-port-199's claims, exactly: core _imag_term 138, _coeff_term 87,
  _half/_bound/_imag_split 69, _unit_power_units 15, ipi_split 3; fuzz 72/40/24 (and fuzz-seed1 same); loop
  _pow_bound_templates 3 (+split 5); dev 3, f6 6, opaque 7, wiring 4; 0 on value rootof scope zero cert budget.
- Cause (diag `~/sa-rust-ids-work/sa-port-215/diag/`): every fallback was an Add whose args lack an input id: a new
  Rational from pow_call's `b + c` shifts, or a term Python already learned (q.derived), plus product rests
  (kept_product) and on loop a Pow Python built (x**2).
- Interim candidate probe on 377e188 (before 1d452e0): core.py [query] = 0 on every workload except
  `_unit_power_units` 15 on core (ruled callback, kept). rows:python kcl shells left then: `_mul_factor_sets`
  (core 158, f6 65, dev 32, loop 6) and loop `_half_split` 1; 1d452e0 moves both (check on probe-cand).
- Still Python by design: `Integer`/`const_value` (named callback), `Add`/`Mul` (pow_call scaffolding, counted),
  `constant_value` (Float), `_unit_power_units` (non-Rational exponent) and `_imag_templates` all-number (ruled).
- core.py footnotes: don't change until the planner answers any unruled leftover (none known yet besides the two ruled).

## Left to do
1. Read the bar (five items) and probe-cand; fallback rows per template per workload (fbcounts.py on the bar dir) vs
   fb-base-209.txt; ad:cbm_noid stays 0 expected.
2. Plants 370-373: which fire and are caught where (bar plants/extra phases; suiteplants for zeros).
   372 (pow-bound args swap) is expected void on workloads (loop's 3 derived Pows are no-split both ways);
   test_core_derived_args.py is its guard test (reaches rows:pow_bound:args, compares with the shadow).
3. port-ownership.md "Updated by sa-port-215" paragraph (TSV finisher 6i(c) already set on 7 core rows in 377e188;
   update their `left`/`runs` text with the probe numbers).
4. Count under the count rule, against STATUS.md "Counted modules" (read it; don't quote from memory).
5. results/port-6i-c.md in port-6i-a.md's form, with every MUST STAY item; harness handler plant HAS landed (db7130a).
6. Land: rebase on origin/rust-slice, `bar.sh land TESTED` without PUSH, read incoming diff, then PUSH=1; no landing
   while another session's full bar runs (216 and 217 had bars on pareto1 at 04:46).

## FILE:LINE MAP (1d452e0)
rust-spike/slice/solver_rs/src/term/rows_tpl.rs: PLANTS 370-373 :87-90; split() :407 (fallback via wiring_fn :478);
enum Got :1346; QIds::ids :1364, learned :1385 (q.derived, Rational interning, Add/Mul raw_add/raw_mul), obj (q.rev),
rest :1454 (kept_product as SymPy construction, `scaffold:core:kept_product`); direct_split Pow-args path :1518;
direct_rows _mul_factor_sets :1610, _pow_bound_templates :1657. tcore.rs core_pow_bound_parts :494.
knowledge_common_live.py PLANTS :44-45. test_core_derived_args.py (new). knowledge_core_live.py shells unchanged.
Counters: rows:ids:{number,derived,learned}, rows:pow_bound:args, scaffold:core:kept_product(:none).
