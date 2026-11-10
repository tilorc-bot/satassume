# 6i, part (c): core's derived-arg fallbacks on Rust (issue 323)

Work by sa-port-215 (377e188, 1d452e0, rebased as ce1790c and 1ada5a0) and sa-port-219 (bars, probe reading, plant
372's direct test, this report).

## What moved
- **Cause, found at db7130a** (`~/sa-rust-ids-work/sa-port-215/diag/`): every core.py call per query on a converted query
  was rows_tpl.rs's `split()` falling back to knowledge_core_live.py's kcl shells (`rows:python:NAME`), because an Add's
  argument had no input id. Those arguments were a new Rational from pow_call's `b + c` shift, a term Python had already
  learned (`q.derived`), a product rest (`kept_product`), and on loop a Pow Python built (`x**2`, from loop_wl.py's
  vocabulary extension `_pow`).
- **rows_tpl.rs** (`QIds`): ids for those arguments are learned the way term_live.term_id learns them
  (`rows:ids:number`, `rows:ids:derived`, `rows:ids:learned`). A product rest is built as domain.py's `kept_product`
  builds it, with SymPy's Mul (`scaffold:core:kept_product`, counted as scaffolding; `:none` when the Mul doesn't keep
  exactly the factors, which is no split, as Python's `kept_product` gives None). A derived Pow is read by its base and
  exponent (`rows:pow_bound:args`, tcore.rs `core_pow_bound_parts`). `_mul_factor_sets`' ct set `(c, kept_product(rest))`
  moves to Rust.
- **Plants** 370-373 (rows_tpl.rs PLANTS, added to knowledge_common_live.PLANTS): `rows-number-id-shift`,
  `rows-product-first`, `rows-pow-bound-args-swap`, `rows-mul-ct-drop`.
- **Tests:** test_core_derived_args.py (new): loop under the shadow, every direct split compared with Python's, answers
  with the pure-Python default's; plus sa-port-219's direct check of plant 372 (see Plants).
- **Shared files, kept minimal:** knowledge_common_live.PLANTS gains one line. knowledge_core_live.py's shells are
  unchanged; they stay as the fallback for args Rust can't read and for SLICE_KNOWLEDGE=py.
- **Ownership:** port-ownership.tsv's 7 core rows: finisher 6i(c) (377e188), `left`/`runs` refreshed from the probe;
  port-ownership.md has an "Updated by sa-port-219" paragraph.

BAR_HERE

PLANTS_HERE

## Per-query calls per core.py function, before (db7130a) and after (1d452e0)
Module-wide probe (sa-port-199's count7.py: every function in core.py traced, pass 1, `kind query`), 15 runs each: dev,
fuzz, the 11 WLS, dev-seed1 and fuzz-seed1. Before: `~/sa-rust-ids-work/sa-port-215/probe/probe-base` (db7130a,
`summ-base.txt`); it equals sa-port-199's claims at 2742b66 exactly. After: `probe/probe-cand`, rerun whole on 1d452e0's
final build (.so untouched until its end.txt; summary copied to `~/sa-rust-ids-work/sa-port-219/summ-cand.txt`). The rebase
onto c822173 and the stack on c59bb1a bring no core.py or rows_tpl.rs change (incoming diffs below).

| function | before, per workload | after |
|---|---|---|
| `_imag_term` (:235) | core 138, fuzz 72, opaque 14, f6 12, loop 12, dev 8, wiring 8 | **0** |
| `_coeff_term` (:88) | core 87, fuzz 40, opaque 11, f6 6, wiring 4, loop 3, dev 1 | **0** |
| `_half_split` (:58) | core 69, fuzz 24, opaque 7, f6 6, loop 5, wiring 4, dev 3 | **0** |
| `_bound_split` (:150) | core 69, fuzz 24, opaque 7, f6 6, loop 5, wiring 4, dev 3 | **0** |
| `_imag_split` (:252) | core 69, fuzz 24, opaque 7, f6 6, loop 5, wiring 4, dev 3 | **0** |
| `ipi_split` (:392) | core 3 | **0** |
| `_pow_bound_templates` (:533) | loop 3 | **0** |
| `_unit_power_units` (:498) | core 15 | core 15 (ruled callback) |
| `_imag_templates` (:288) | 0 everywhere | 0 everywhere (ruled callback) |

dev-seed1 and fuzz-seed1 equal dev and fuzz before and after. value, rootof, scope, zero, cert and budget are 0 before
and after. What's left outside `[query]`: `__getattr__` at import (2 per run, no query), and core.py on kept queries
only, the named kept reasons: dev `kept:out-of-scope` (`_imag_term` 4, `_bound_split`, `_half_split`, `_imag_split`,
`_mul_factor_sets`, `_pi_split`, `_quotient_templates`, `ipi_split` 2 each), f6 and opaque `kept:refused` (f6 14 calls,
opaque 23), the same before and after.

## Module count (STATUS "Counted modules", 19 of 32)
Checked against STATUS.md's list (19: euf, lra, transfer, lra_cert, realroots, atoms, registry, templates/__init__,
scope, table, _common, lra_adapter, sympy_api, special, rootof, nodes, physics, stats, solver), not recounted.
**core.py counts: 20 of 32**, on the module-wide probe above. None of core.py's Python runs per query on a converted
query except the two ruled callbacks. Footnote, as the 6f ruling words it, with fire counts:
"core.py: 2 named SymPy-arithmetic callbacks (`_unit_power_units` non-Rational exponent: core 15, 0 on the other 14
runs; `_imag_templates` all-number Add: 0 on all 15 runs, `rows:kept:_imag_templates:number` 0 in the bar), pending the
constfield question after 5c."
- What else still runs as Python on core's paths, and why it doesn't stop core.py counting (none of it is core.py code):
  - `Integer`/`const_value` (`rows:python`): `_common`'s named callback, footnoted there.
  - `constant_value` (`rows:python`, core 1, equal to base): `_rows_runtime.constant_value` (wiring), a Rational with a
    text rows_tpl.rs doesn't compile; 6g's, unchanged.
  - `Add`/`Mul` (`rows:python`, pow_call's construction, equal to base) and `scaffold:core:kept_product`: SymPy
    construction called from Rust, counted as scaffolding (table below).
- **Question for the planner (doesn't change core.py's count or footnote):** `scaffold:core:kept_product` builds the rest
  with SymPy's Mul and checks it as `kept_product` does (a Mul whose args are exactly Rust's factors). When it isn't, it
  gives no split (`:none`, core 14), which is Python's answer, rather than refusing the query as the scaffolding ruling
  says for a rebuilt form that differs. Is that check acceptable for this scaffold until the count reaches 0? Fire counts
  are in the scaffolding table.

## Scaffolding (port rulings: counted per step, to reach 0 before any backend PR)
From the bar's knowledge files (1d452e0 bar; equal in the stacked bar unless stated there).

| workload | `scaffold:core:kept_product` (`:none`) | `rows:python:Add` / `Mul` | other scaffolds (before = after) |
|---|---|---|---|
| core | 163 (14) | 96 / 96 | none |
| f6 | 82 | 0 / 0 | `rebuilt:f6` 45, `mismatch` 2 |
| dev | 33 | 6 / 3 | `rebuilt:glue_objects` 25, `rebuilt:f6` 3, `rebuilt:integer_form` 1 |
| wiring | 10 | 8 / 12 | none |
| loop | 2 | 6 / 3 | none |
| fuzz, value, rootof, opaque, scope, zero, cert, budget | 0 | 0 / 0 | none |

`rows:python:Add`/`Mul` equal base on every workload. `scaffold:core:kept_product` is new in this step (it was the
`_mul_factor_sets` and `_coeff_term` shells' own Mul before).

## Kept reasons (planner ruling, 03:42 UTC 8 Nov)
KEPT_HERE

## Fallbacks to Python inside ported code (planner's fallback-reporting ruling)
`registry:python` is dispatch.rs:242's fallback, `rows:python` is rows_tpl.rs:413's (the `split()` wiring_fn fallback,
:478 at 1d452e0), per template name, from the bar's knowledge files (`~/sa-rust-ids-work/sa-port-219/fbcounts.py`, 215's
script with `rows:kept:`, `ad:cbm_noid`, `rows:ids:`, `rows:pow_bound:` and `ctx:caught` added). Base: sa-port-209's bar
(`fb-base.txt`), candidate: the 1d452e0 bar (`fb-cand.txt`), both in `~/sa-rust-ids-work/sa-port-219/`.
**The core kcl shells are gone from `rows:python` on every workload.**

| workload | `rows:python` before → after | removed |
|---|---|---|
| core | 2,105 → 1,688 | `_bound_split` 69, `_half_split` 72, `_imag_split` 69, `_mul_factor_sets` 158, `_quotient_templates` 46, `ipi_split` 3 |
| f6 | 878 → 760 | `_bound_split` 6, `_half_split` 32, `_imag_split` 6, `_mul_factor_sets` 65, `_quotient_templates` 9 |
| dev | 625 → 521 | `_bound_split` 18, `_half_split` 20, `_imag_split` 11, `_mul_factor_sets` 36, `_quotient_templates` 19 |
| fuzz | 378 → 272 | `_bound_split`, `_half_split`, `_imag_split` 34 each, `_mul_factor_sets` 2, `_quotient_templates` 2 |
| loop | 161 → 129 | `_bound_split`, `_half_split`, `_imag_split` 6 each, `_mul_factor_sets` 6, `_pow_bound_templates` 3, `_quotient_templates` 5 |
| zero | 119 → 72 | `_bound_split`, `_half_split`, `_imag_split` 11 each, `_mul_factor_sets` 7, `_quotient_templates` 7 |
| opaque | 69 → 48 | `_bound_split`, `_half_split`, `_imag_split` 7 each |
| wiring | 510 → 478 | `_bound_split` 4, `_half_split` 5, `_imag_split` 4, `_mul_factor_sets` 13, `_quotient_templates` 6 |
| value, rootof, scope, cert, budget | unchanged | none (no shell before) |

After, `rows:python` by template: `Integer` and `const_value` (the named callback) on every workload; core
`_unit_power_units` 15 (ruled callback) and `constant_value` 1 (`_rows_runtime`'s, as base); `Add`/`Mul` scaffolding
(table above). Nothing else. `rows:kept:*` 0 on every workload.
`registry:python` (dispatch.rs:242) is unchanged against base on every workload in the 1d452e0 bar: dev 126, fuzz 38, f6
211, value 507, rootof 27, core 35, opaque 101, scope 33, loop 31, zero 43, wiring 75, cert 24, budget 469; by template
`_load`, `symbol_units`/`constant_units` (atoms' input-fact templates), and `_unary`/`nary` (6i(b)'s; see the stacked bar).
`registry:kept`: dev 4, f6 2, opaque 2, value 6, as base. **`ad:cbm_noid`: 0 on every workload** (it was shown firing on its
own plant in state part 2 (i); not re-shown here).
So rows_tpl.rs:413 now reports 0 outside named callbacks and counted scaffolding. dispatch.rs:242 still runs atoms'
input-fact templates and `_load`, as 6i(a) reported, and 6i(b)'s templates until 6i(b) lands.

## State: each container this step touches
None. `QIds` lives for one split call: the ids it learns go into the query's term table the way term_live.term_id's do,
and the bar's state comparison covers that table. No static, cache or memo is added. The live state comparison MATCHes
on all 13 workloads.

NOTRUN_HERE

