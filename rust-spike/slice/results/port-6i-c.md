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

## SHAs and landing
- 6i(c) alone: code 377e188 + 1d452e0 on rust-slice db7130a (bar 1), rebased onto c822173 as port/6i-c 59ebd3c (not barred
  alone, kept as the fallback).
- **The stack (general stack ruling: one full bar, one push):** port/6i-c-stack = 6i(b)'s c59bb1a (port/6i-b on rust-slice
  c822173) + 6i(c)'s commits c81a3d8, 8228a8e (= 377e188, 1d452e0 cherry-picked, unedited) + the test commit.
  **Tested: 6f9c44a.** Landed: 6f9c44a's source plus results/ and HANDOFF commits only (outside bar.sh's push guard); the
  landed head and the incoming diff are in the landing `agent report` and in port-6i-b.md's landing lines.
- Incoming diffs before the stack: db7130a → c822173 is state part 2 (iii)(a) + (b) first move (relations.py,
  session_live.py, term_live.py, relations_core.rs, session.rs, term/{algebra,py,relations,table}.rs, tests, harness/state.py);
  no core.py, rows_tpl.rs or tcore.rs change. 6i(b) brings functions' fn_tpl.rs and dispatch.rs's `Tpl::Slotted`; no
  core.py or rows_tpl.rs change. Both are covered by the stack bar, which ran on the merged tree.

## Bar 1 (pareto1, `~/sp19/sa-rust-ids-work/sa-port-215/bar-6ic` on 1d452e0, base db7130a): 6i(c) alone
Base suite rows: sa-port-209's harness bar (db7130a's source). PLANTS: 370-373. Read by sa-port-219.
1. **Suite by id:** 5,991 passed, 127 failed, 23 skipped (plus 18 xfailed), over 6,159 ids. **Against base: new 0, gone 0,
   changed outcome 1:** `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`
   passed -> failed, the known id()-reuse failure (a28c548). Passed: 5,990 with no handler firing and 1 with a firing
   (`tests/test_invariants.py::test_ci_stream_reports_only_what_replays`, the named case).
2. **dev, fuzz and the 11 WLS MATCH**, answers and state.
3. **Plants:** 370, 371, 373 caught; 372 void (below).
4. **Handler multiset = base** (34 + 4 `_consistent`, 1 `Engine._build_context` "Already mutably borrowed" in
   test_protocol_on_fuzz). `ctx:caught` 0 on all 13 workloads, 1 in the suite (that test).
5. **Known differences: none.** Kept shares = base; `ad:cbm_noid` 0 and `rows:kept` 0 on every workload.

## The stack bar (pareto1, `~/sp19/sa-rust-ids-work/sa-port-219/bar-6ic-stack` on 6f9c44a): 6i(b) + 6i(c), the landing bar
Run 06:22Z-07:32Z 10 Nov under shared lease f30bc65d; every phase exited 0 (build, tests, suite, live, plants, extra,
suiteplants, sum); seed1 was not run. `.so` sha256 a1e0710c…. Base suite rows: `sa-port-217/bar-state-relations-iii-ab/suite`
(022630c, c822173's landing bar; the same base as 6i(b)'s bar 3). WLS: the 11. PLANTS: 370-373 plus `ctx-check-raise`;
SUITE_PLANTS `zero`. Tests phase: 215's list plus test_core_derived_args.py, test_relc_core.py and
test_knowledge_fn_direct.py: **889 passed, 4 skipped**, exit 0. DIRECT: `relations_direct.py 300 0` exit 0;
`dispatch_direct.py` exit 0, BAD 0, with `registry:rust:_unary.<locals>.template` 6 and `nary` 1 reached. Read by
sa-port-224; fallback counts `~/sa-rust-ids-work/sa-port-224/fb-stack.txt` (and `fb-6ib3.txt`, bar 3), fn and ctx counts
`fn-ctx.txt`, by 219's `fbcounts.py` with `fn:` added and 220's `ctxcount.py`.
1. **Suite by id:** 5,992 passed, 126 failed, 23 skipped (plus 18 xfailed), over 6,159 ids. **Against base: new 0, gone 0,
   changed outcome 2, both explained:**
   - `tests/test_history.py::test_module_state_inventory_is_classified` failed -> passed: the base rows are 022630c's,
     where it failed; c822173 (the commit landed on top of them) fixed it by classifying `relations.RELATION_ATOM_IMPL`.
     6i(b)'s bar 3 shows the same change on the same base.
   - `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` failed -> passed: the
     known id()-reuse test (a28c548), which flips both ways between runs (failed in bar 1, in bar 3 and in the base; passed
     here and in this bar's own suite-plant run). Not a Rust difference; unedited.

   Passed splits into **5,991 with no handler firing and 1 with a firing:**
   `tests/test_invariants.py::test_ci_stream_reports_only_what_replays`, the named case.
2. **Fresh dev and fuzz: answers and state MATCH** (Rust against Python, traced and untraced; Python against Python as the
   control). dev answers_sha 31cd0945c07f02a6, fuzz 173502b6ef285ad6, as every bar since 6i(a). **All 11 extra workloads
   MATCH**, Rust against Python, each with its Python control MATCH.
3. **Plants caught:** 370, 371 and 373 by the live comparison; 372 void on workloads and suite, caught by its direct test;
   `ctx-check-raise` caught on all 13 workloads. Table below. 6i(b)'s fn plants were not in this bar: they are in bar 3
   (port-6i-b.md).
4. **Quiet handler firings on Rust: the handler multiset is the same as base** (ids whose caught rows differ: 0). 39 rows in
   2 tests:
   - 34 × `_consistent` AttributeError `'Solver' object has no attribute '_ok'`, in test_ci_stream_reports_only_what_replays;
   - 4 × `_consistent` AttributeError `_rb_clauses`, in the same test;
   - 1 × `Engine._build_context` RuntimeError "Already mutably borrowed", in test_protocol_on_fuzz (the named 46-stub cause).

   **engine.py:1906's catches (`ctx:caught`): 0 on all 13 workloads** (from each `*-rust.session.json`), **1 in the suite**
   (test_protocol_on_fuzz, the row above; 41,477 complete checks). The live and extra Rust handler files have 0 rows;
   TermFault in pytest.log: 0. **These zeros are not void:** under `ctx-check-raise` (the Rust-side handler plant, landed with
   db7130a) the same sites catch every complete check on every workload, each catch also a handler row:

   | workload | complete checks (plain) | `ctx:caught` plain | `ctx:caught` under the plant |
   |---|---|---|---|
   | dev | 833 | 0 | 833 |
   | fuzz | 2,952 | 0 | 2,980 |
   | f6 | 6 | 0 | 6 |
   | value | 319 | 0 | 636 |
   | rootof | 368 | 0 | 368 |
   | opaque | 31 | 0 | 31 |
   | core | 300 | 0 | 300 |
   | scope | 166 | 0 | 166 |
   | loop | 244 | 0 | 244 |
   | zero | 665 | 0 | 718 |
   | wiring | 5,004 | 0 | 5,004 |
   | cert | 61 | 0 | 61 |
   | budget | 16 | 0 | 16 |

   (The same numbers as 6i(b)'s bar 2 and bar 3. In every planted run `ctx:caught` equals its own `ctx:complete_check`,
   which is higher than the plain run's on fuzz, value and zero; cause not read.)
5. **Known differences in answers or read state: none.**

## Plants (the stack bar; bar 1 gave the same fire counts and verdicts)
`fired` reads the session report on the workloads. In the suite, sum.txt's "plant fired in the suite: 0" is **void for these
plants**: the suite's count files hold session counters only (`rel:plant_fired`), and the rows plants count in Common's
counts, as the fn and outer plants do. The suite catch is read from changed outcomes against this run's plain suite.
SUITE_PLANTS `zero` runs the suite only under plants that fired 0 on dev and fuzz, which here is 372 alone.

| plant | fired (bar) | caught by | suite |
|---|---|---|---|
| `rows-number-id-shift` (370) | core 159, loop 11, wiring 7, dev 4 | core DIFFER; dev, loop, wiring MATCH (fires, no answer or state moved) | not run (fires on dev) |
| `rows-product-first` (371) | core 163, f6 82, dev 33, wiring 10, loop 2 | dev, core, f6, loop, wiring DIFFER | not run (fires on dev) |
| `rows-pow-bound-args-swap` (372) | loop 3 | nothing: loop MATCH | 0 changed. **Void on workloads and suite.** |
| `rows-mul-ct-drop` (373) | core 132, f6 56, dev 17, wiring 9, loop 2 | dev, core, f6, loop, wiring DIFFER | not run (fires on dev) |
| `ctx-check-raise` (Q2 control) | dev 833, fuzz 2,980, f6 6, value 636, rootof 368, opaque 31, core 300, scope 166, loop 244, zero 718, wiring 5,004, cert 61, budget 16 | DIFFER on all 13 | not run (fires on dev) |

- **372 is void on every workload and in the suite.** Loop's derived Pows are `b**2` (loop_wl.py's extension `_pow`), which
  split the same with base and exponent swapped or not. test_core_derived_args.py's first test didn't catch it either
  (fired 3, shadow:mismatch 0). It is caught only by sa-port-219's direct test
  `test_pow_bound_args_swap_plant_is_caught` (an extension-derived `1/(3*x + 2)`: fired 1, the shadow catches it; the test
  sets `K.PLANT`, since SLICE_SESSION_PLANT isn't read under pytest). That test ran in the stack bar's tests phase.
  **So `core_pow_bound_parts`' argument order has no workload or suite evidence, only that test.**
- Void cells elsewhere: 370 on dev, loop and wiring (fires, MATCH); it is caught on core only.
- Every rows plant fires 0 on fuzz, value, rootof, opaque, scope, zero, cert and budget, and those MATCH.

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

## Module count (STATUS "Counted modules", 19 of 32; 21 with the stack)
Checked against STATUS.md's list (19: euf, lra, transfer, lra_cert, realroots, atoms, registry, templates/__init__,
scope, table, _common, lra_adapter, sympy_api, special, rootof, nodes, physics, stats, solver), not recounted.
**core.py counts: 20 of 32**, on the module-wide probe above (and with functions.py from 6i(b), landed in the same push,
**21 of 32**; functions.py's footnote is in port-6i-b.md). None of core.py's Python runs per query on a converted
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
Stack bar, Rust runs. **Every share equals base.** The bar's own base (217's bar) ran only loop, zero, cert, scope and
budget as extra workloads, so its summary prints "base not found" for the other six; those are compared with 6i(b)'s bar 2
and bar 1 here (port-6i-b.md), and all 13 equal 6i(b)'s bar 3.
- Out-of-scope: dev 24/1,985 (1.21%); every other workload 0.
- Refused:
  - f6 13/2,902 (0.45%): `algebra: Float` 10, `lra: a callback on a derived term` 1, `scaffold: rebuilt form differs from
    Rust` 2;
  - value 15/3,742 (0.40%), all `algebra: Float`;
  - opaque 7/2,546 (0.27%): `algebra: infinity or nan` 5, `algebra: holds an infinity, nan or Float` 2;
  - wiring 1/6,512 (0.02%), `lra: a callback on a derived term`;
  - dev, fuzz, rootof, core, scope, loop, zero, cert, budget: 0.

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

## The stacked tree: fallback counts in one build
`fbcounts.py` on the stack bar (`fb-stack.txt`) equals 1d452e0's bar (`fb-cand.txt`) plus exactly 6i(b)'s deltas, and equals
bar 3 (`fb-6ib3.txt`) plus exactly 6i(c)'s deltas above. In the one build, per workload:
- **dispatch.rs:242 (`registry:python`):** dev 95 (`_load` 68, `constant_units` 12, `symbol_units` 15); fuzz 38 (30, 6, 2);
  f6 65 (54, 4, 7); value 180 (29, 150, 1); rootof 27 (26, -, 1); core 35 (28, 1, 6); opaque 42 (39, -, 3); scope 33 (27, 2,
  4); loop 31 (20, 5, 6); zero 38 (29, 3, 6); wiring 75 (35, -, 40); cert 24 (20, 1, 3); budget 469 (19, -, 450). Only
  `_load` and atoms' input-fact templates; `_unary` and `nary` are 0 everywhere.
- **rows_tpl.rs:413 (`rows:python`):** dev 521 (`Integer` 256, `const_value` 256, `Add` 6, `Mul` 3); fuzz 272 (136, 136);
  f6 760 (380, 380); value 1,208 (604, 604); rootof 16 (8, 8); core 1,688 (740, 740, `Add` 96, `Mul` 96,
  `_unit_power_units` 15, `constant_value` 1); opaque 48 (24, 24); scope 64 (32, 32); loop 129 (60, 60, `Add` 6, `Mul` 3);
  zero 72 (36, 36); wiring 478 (`Integer` 224, `const_value` 234, `Add` 8, `Mul` 12); cert 208 (104, 104); budget 80 (40,
  40). No kcl shell on any workload.
- **`ad:cbm_noid`: 0 on all 13 workloads.** (In the suite runs' session counts it is not 0 and varies between runs of the
  same source: 19 in the stack's plain suite, 910 in its suite under the void plant 372, 376 in bar 3's, 208 in the base's.
  Earlier reports gave the workload zeros only. Cause of the variation not read; named for the planner.)
- `registry:kept`: dev 4, f6 14, opaque 9, value 15 (6i(b)'s move on refused queries); `rows:kept` 0 everywhere.
- `fn:` (6i(b)): dev `rust:unary` 31; f6 `rust:unary` 75, `rust:nary` 47, `rust:unit_interval` 18; opaque `rust:unary` 45;
  zero `rust:unary` 5; value `rust:unary` 309, `rust:genocchi_half` 50, `value_units` 236, **`value:sympy` 264**; 0 on the
  other eight.
- Scaffolding in the one build: `scaffold:core:kept_product` and `rows:python` `Add`/`Mul` exactly as the table above;
  value `scaffold:rebuilt` 269 (6i(b)'s +48 over 221); the other scaffolds as base.
- **Module-wide probe on the stacked build** (sa-port-224; count7.py through 215's run1.sh, every function in core.py and
  functions.py traced, pass 1, `kind query`, the same 15 runs; orion, the clone's stack build of 6f9c44a's source,
  `~/sa-rust-ids-work/sa-port-224/probe-stack`, all 15 exit 0): **core.py 0 on every run except `_unit_power_units` core 15;
  functions.py 0 on all 15 runs.** So both modules' counts hold in the merged tree, not only on each step alone. The
  summary line per workload was checked against the db7130a base probe, where it reproduces the "before" columns.

## Not run
- Moved to "before any backend PR", none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control; the boundary
  rescore and suite column; the final drop score and its lost rows; the suite split with Python's counter; `order:_rows`'
  evidence (not caught meanwhile); the `_forms` guard test; history and seed reruns (the bars' seed1 phase not run; the
  probes ran dev-seed1 and fuzz-seed1); forced moves; the native path; timing.
- 6i(c) alone on c822173 (port/6i-c 59ebd3c) has no bar of its own: the stack bar covers it together with 6i(b).
- Plants 370, 371 and 373 in the suite (they fire on dev, so SUITE_PLANTS `zero` skips them); 372 has no workload or suite
  catch (its direct test only).
- `ad:cbm_noid` was not re-shown firing on its own plant in this step.
- The dispatch_direct.py shared-cache question: `_common._CACHE` is shared by pattern key, so dispatch_direct.py's
  side-by-side comparison may read one side's pattern on the other. **Unchecked; a backend-PR-list item.**

Other notes, carried:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
- `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` is the known id()-reuse
  failure (a28c548), unedited; it passed in the stack bar's suite and failed in bar 1's and bar 3's.
- Scope's MATCH rests on the fixed install order (db7130a's live.py), as every bar since the harness fix.
- `test_performance_smoke_300_vars`: same outcome as base in the stack bar's suite; not chased.
- **Speed not measured.**

