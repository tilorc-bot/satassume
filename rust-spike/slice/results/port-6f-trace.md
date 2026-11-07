# Step 6f, part 1: import-time vs runtime for the six template modules (issue 323)

Source 0bc2e0f+ (port/6f on rust-slice 2540ca7). `f6_trace.py` (sys.monitoring PY_START on the six files; a call is
`import` when a `<module>` frame of the six or of wiring.py is on the stack), default Python engine, memos reset per query.
Rows: `~/sa-rust-ids-work/sa-port-110/trace/{dev,fuzz,value,rootof,core,f6}.json` on orion. Suite trace not run yet
(`pytest -p f6_trace`, F6_TRACE_OUT=dir).

**Import time, every workload:** only each module's `<module>` (constants: `MAX_VALUE_ARG`, `MAX_MULTIGAMMA_P`, slot indices
`X N M PS CR CS A B`). Data, not ported. Rust embeds the ones it needs.

**Not port items:** `special._register` has no caller in satassume or tests (0 everywhere; dead code). `functions._value_units`
is offline by the ownership ruling (D generated its table).

**Per-class factories (runtime, once per class per process, when wiring first builds a class's template; the counts are
classes):** `_unary`, `nary`, `_pi_trig`, `_exp_ipi`, `_cosh_shift`, `_genocchi_half`, `_in_unit_interval_units`. Proposed:
Python shells whose inner template/rules are swapped, as core's 4 shells.

**fuzz reaches none of the six modules; dev reaches functions.py only.** The f6 workload (`knowledge_f6_wl.py`, 2,518 + n-ary
queries, built from the code) reaches every item dev, fuzz, value, rootof and core don't. So 6f's runtime work isn't small:
`_unary`'s template is the template of every unary row (261 calls on dev, 3,231 on value).

Calls after import (inner functions by qualname; `build` is a `_CACHE` miss):

| item | dev | fuzz | value | rootof | core | f6 |
|---|---|---|---|---|---|---|
| `functions._cosh_shift` | 1 | 0 | 0 | 0 | 1 | 1 |
| `functions._cosh_shift.template` | 1 | 0 | 0 | 0 | 6 | 1040 |
| `functions._cosh_shift.template.<genexpr>` | 0 | 0 | 0 | 0 | 0 | 640 |
| `functions._cosh_shift.template.build` | 0 | 0 | 0 | 0 | 0 | 640 |
| `functions._cosh_shift_rules` | 0 | 0 | 0 | 0 | 0 | 640 |
| `functions._cosh_shift_split` | 1 | 0 | 0 | 0 | 6 | 1040 |
| `functions._exp_ipi` | 1 | 0 | 0 | 0 | 1 | 1 |
| `functions._exp_ipi.template` | 9 | 0 | 0 | 0 | 384 | 0 |
| `functions._exp_ipi.template.build` | 9 | 0 | 0 | 0 | 384 | 0 |
| `functions._genocchi_half` | 0 | 0 | 1 | 0 | 0 | 1 |
| `functions._genocchi_half.half` | 0 | 0 | 524 | 0 | 0 | 0 |
| `functions._in_unit_interval_units` | 0 | 0 | 0 | 0 | 0 | 2 |
| `functions._in_unit_interval_units.units` | 0 | 0 | 0 | 0 | 0 | 252 |
| `functions._parts_of_round_rules` | 0 | 0 | 0 | 0 | 0 | 192 |
| `functions._pi_trig` | 3 | 0 | 0 | 0 | 3 | 3 |
| `functions._pi_trig.template` | 9 | 0 | 0 | 0 | 384 | 1840 |
| `functions._pi_trig.template.build` | 0 | 0 | 0 | 0 | 372 | 736 |
| `functions._pi_trig_rules` | 0 | 0 | 0 | 0 | 372 | 736 |
| `functions._unary` | 22 | 0 | 6 | 0 | 13 | 49 |
| `functions._unary.template` | 261 | 0 | 3231 | 0 | 12 | 1372 |
| `functions._unary.template.build` | 256 | 0 | 3231 | 0 | 12 | 1372 |
| `functions._value_units` | 0 | 0 | 3231 | 0 | 0 | 0 |
| `functions.nary` | 1 | 0 | 3 | 0 | 0 | 16 |
| `functions.nary.template` | 0 | 0 | 0 | 0 | 0 | 384 |
| `functions.nary.template.build` | 0 | 0 | 0 | 0 | 0 | 384 |
| `functions.parts_of_round_templates` | 82 | 0 | 0 | 0 | 0 | 192 |
| `functions.shifted` | 3 | 0 | 2321 | 0 | 0 | 388 |
| `nodes._accum` | 0 | 0 | 0 | 0 | 0 | 50 |
| `nodes.accumbounds_templates` | 0 | 0 | 0 | 0 | 0 | 50 |
| `nodes.idx_units` | 0 | 0 | 0 | 0 | 0 | 40 |
| `nodes.idx_units.<lambda>` | 0 | 0 | 0 | 0 | 0 | 32 |
| `physics.quantity_units` | 0 | 0 | 0 | 0 | 0 | 40 |
| `physics.quantity_units.<lambda>` | 0 | 0 | 0 | 0 | 0 | 32 |
| `rootof._coefficients` | 0 | 0 | 0 | 4784 | 0 | 0 |
| `rootof._coefficients.<genexpr>` | 0 | 0 | 0 | 4784 | 0 | 0 |
| `rootof._facts` | 0 | 0 | 0 | 4784 | 0 | 0 |
| `rootof.crootof_units` | 0 | 0 | 0 | 4784 | 0 | 0 |
| `rootof.crootof_units.<lambda>` | 0 | 0 | 0 | 4784 | 0 | 0 |
| `special._doubled` | 0 | 0 | 168 | 0 | 0 | 0 |
| `special._multigamma_rules` | 0 | 0 | 168 | 0 | 0 | 0 |
| `special._multigamma_rules.build` | 0 | 0 | 168 | 0 | 0 | 0 |
| `special.multigamma_templates` | 0 | 0 | 168 | 0 | 0 | 0 |
| `special.multigamma_templates.<genexpr>` | 0 | 0 | 168 | 0 | 0 | 0 |
| `stats.randomsymbol_units` | 0 | 0 | 0 | 0 | 0 | 36 |
| `stats.randomsymbol_units.<lambda>` | 0 | 0 | 0 | 0 | 0 | 36 |
