
# Steps 6g(c3), 6g(c4), 6g(c5): the Pow family's splits, `constant_value`, and the Addition template builders from the query's table, landed as one stack (issue 323)

**One stack, three steps** (planner's 6g(c3)-(c5) stack go, 8 Nov ~14:00). Built by sa-port-163 (c3), sa-port-164 (c4,
c5's Rust) and sa-port-172 (c5's Python, the stack); rebased and barred by sa-port-175, landed by sa-port-187.

**Tested source: af63d20** on rust-slice 4215655 (5c10b): c3 46006f1 + 438e081, c4 2fafc05 + bfb60c5, c5 3f4cdc8 +
e64ec78, plus af63d20 (results/ only: the predecessor's handoff and this report's draft). **Landed** by `PUSH=1 bar.sh
land af63d20` with this report (results/ only on top); incoming diff at landing: INCOMING_AT_LANDING.

How it got there (each rebase brought guarded source the bar executes, so each got a full bar, as the rebase rule asks):
1. **0643e9c** on 3611952 (5c8): full bar `~/sp19/sa-rust-ids-work/sa-port-172/bar-6g-c3c5/` (exit 0 16:54:03Z),
   equal to base (5c8's rows) and to S1's rows on every item.
2. **d0374e9** on 2d12e81 (5c9a-c, 18 guarded files): its bar was stopped in its plants phase when rust-slice moved again
   (sa-port-175/bar-6g-c3c5r, partial, not used).
3. **2c2990c** on 67d108d (5c10a: session.rs, relations_core.rs, factcache.rs, term_live.py, session_live.py,
   memo_check.py, lib.rs, test_factcache_core.py): full bar `~/sp19/sa-rust-ids-work/sa-port-175/bar-6g-c3c5r2/`
   (exit 0 20:38:37Z, .so 909bacbd…), base 5c10a's rows: equal to base on every item (numbers as below).
4. **af63d20** on 4215655 (5c10b). Incoming diff 67d108d..4215655: handler_count.py, memo_check.py, session_live.py,
   solver_rs/src/{context.rs (new), engmemo.rs, lib.rs, relations_core.rs, session.rs}, test_context_core.py, plus
   results/ (port-5c10b.md, HANDOFF-sa-port-184.md, port-ownership.md/.tsv); 931 insertions, 18 deletions. The guard named
   the nine source files, all executed by the bar, so a **full bar ran on af63d20**: pareto1
   `~/sp19/sa-rust-ids-work/sa-port-187/bar-6g-c3c5r3/` (end.txt R3_END, written by the job; .so R3_SO), config =
   bar-6g-c3c5r2's plus 5c10b's test_context_core.py, base suite rows 5c10b's (`sa-port-186/bar-5c10b/suite`), KEPT_BASE
   bar-6g-c3c5r2. Orion short check before it: build OK, 116 passed (shapes, context, rows, engmemo, factcache, procmemo).

Completeness (checked on the bar's files before reading it): suite rows for all 6,159 ids; 13 workload comparisons (dev,
fuzz and 11 WLS), each with its Python control, plus seed1 on dev and fuzz; 56 plants x 13 workloads = 728 plant rows;
7 suite-plant runs; handler rows for the suite, live, extra and plant runs; every phase exit 0. Each step's plant table is
kept apart below, as the stack ruling asks.

## The bar (on af63d20)
1. **Suite by id against 5c10b's rows: R3_SUITE.** Passed split by firing: R3_SPLIT. Against the 2c2990c bar's rows:
   R3_VS_R2. Against the first stack bar (0643e9c, 5c8 base): the one changed id is
   `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` passed -> failed, the
   **known id()-reuse failure** (below), failed in the 5c10a and 5c10b base rows too. S's standing: S's gate is met except
   for the 46 named stub failures, one cause.
2. **Fresh dev and fuzz: answers and state MATCH** (answers_sha dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6; end, stream
   and lra diffs 0; Rust made 0 Python solvers), Python-vs-Python controls MATCH, traced-vs-untraced end states MATCH,
   seed1 MATCH. All 11 WLS MATCH with controls: f6 2,902, value 3,742, rootof 5,187, core 1,636, opaque 2,546, scope
   169, loop 420, zero 854, wiring 6,512, cert 61, budget 28 queries. The **lra-on path MATCH** (with_closed_units, the
   6g(a)/5c5 meeting point), with **with-closed-skip caught** on dev, fuzz, cert, core, f6, opaque and wiring.
3. **Plants:** every plant caught before is still caught, on the same workloads: the per-plant sets of workloads where it
   fires and where it's caught equal the first stack bar's for all 56 plants (R3_PLANTSAME). Per-step tables below.
   rows_tpl.rs PLANTS still caught as on S1; rows-pow-head-any void by construction (6g(b)).
4. **Quiet handler firings on Rust:** R3_HANDLERS
5. **Known differences:** none in answers or read state. Kept shares per reason equal base on every workload
   (R3_KEPT): out-of-scope dev 24/1,985 (1.21%), 0 elsewhere; refused f6 13/2,902 (Float 10), opaque 7/2,546, value
   15/3,742 (Float), wiring 1/6,512 (a callback on a derived term). No rise.

**The parts ruling's three 6g(a) conditions still hold.** Suite plants (against this run's suite): R3_SUITEPLANTS.
`dispatch-ignores-epoch`'s changed ids differ from run to run (0643e9c: 18, with test_unrelated_relation/test_verify_*;
2c2990c: 17, with test_transfer_fuzz x12): which test meets a stale dispatch entry depends on what ran before it in the
same xdist worker. Direct, on orion on af63d20 (`~/sa-rust-ids-work/sa-port-187/dispatch-direct-af63d20.txt`):
`dispatch_direct.py` plain exit 0 (user path 2, BAD 0); **dispatch-user-off caught** (user path 0, BAD 1, exit 1);
dispatch-ignores-epoch caught (BAD 3); dispatch-redefines-off caught (BAD 2). direct.txt (the bar's) equals S1's:
dispatch_direct exit 0, common_direct plain exit 0, 13 common plants exit 1.

**Shadow (test_knowledge_core_shapes, 23 cases, orion on af63d20, `~/sa-rust-ids-work/sa-port-187/shadow-af63d20.txt`):
shadow:mismatch 0, answers equal.** shadow:direct per name: `_half_split` 10, `_bound_split` 10, `_imag_split` 10,
`_mul_factor_sets` 18, `_quotient_templates` 20; c3: `_exp_arg` 17, `_unit_angle` 16, `ipi_split` 3, `irrational_root`
16, `_unit_power_units` 2, `_pow_bound_templates` 14, `ipi_rules` 2; c4: `constant_value` 60; c5: `_half_templates` 1,
`_bound_templates` 7, `_recip_templates` 7, `_imag_templates` 2.

## 6g(c3): the Pow family's seven splits direct

**Code** (46006f1, plant fix 438e081). rows_tpl.rs's Pow family computes `_exp_arg`, `_unit_angle`, `ipi_split`,
`irrational_root`, `_unit_power_units`, `_pow_bound_templates` and `ipi_rules` from the query's table through
`RowsTpl::split` / `direct_rows`, with tcore.rs's `ipi_rules` (:597). Each falls back to the shell (`rows:python:NAME`)
for no or a kept query, a derived argument or result, a product rest (`kept_product`), or a non-Rational exponent in
`_unit_power_units` (the shell's counted `as_real_imag` fallback). The shadow compares each result through
knowledge_core_live `shadow_split`. test_knowledge_core_shapes: seven DIRECT entries, six cases.

**Direct split** (rows:rust / rows:python on the af63d20 bar; before = S1's bar, all on Python; rust + python equals
before on every workload): 
- `_exp_arg`: dev 8/0; core 276/0; f6 1/0; loop 7/0; opaque 17/0; wiring 29/0
- `_unit_angle`: dev 8/0; core 276/0; f6 1/0; loop 7/0; opaque 17/0; wiring 27/0
- `ipi_split`: core 54/1; wiring 4/0
- `irrational_root`: dev 5/0; core 80/0; f6 1/0; loop 3/0; opaque 1/0; wiring 24/0
- `_unit_power_units`: core 18/15; wiring 3/0
- `_pow_bound_templates`: dev 8/0; core 243/0; f6 1/0; loop 4/3; opaque 17/0; wiring 24/0
- `ipi_rules`: core 14/0; wiring 3/0

**Plants, c3** (af63d20 bar: dev, fuzz and the 11 workloads, each against this run's Python; fired on the workloads
named, 0 on the rest):

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
| rows-exp-arg-none | wiring 2 |  |
| rows-unit-angle-shift | core 33, wiring 5 |  |
| rows-ipi-split-shift | core 54, wiring 3 |  |
| rows-irrational-false | core 16, wiring 2 |  |
| rows-unit-power-drop-last | core 18, wiring 3 |  |
| rows-pow-bound-drop-last | core 144, wiring 1 |  |
| rows-ipi-rules-drop-last | core 14, wiring 3 |  |

- **c3's -neg pair, replaced in this stack:** rows-unit-angle-neg and rows-ipi-split-neg fired (orion: core 33/54, wiring
  5/3) and MATCHed everywhere: negation keeps the parity, denominator and half-oddness that the rules read, so both were
  void by construction. Replaced in both lists (438e081) by rows-unit-angle-shift and rows-ipi-split-shift (plus 1, which
  flips parity); both are caught on core and wiring (table), 0 on dev and f6, whose queries don't reach these splits.
- rows-exp-arg-none is caught on wiring only (2); the other five c3 plants on core and wiring. dev and f6 fire 0 for
  all seven (their queries have no Pow of these shapes with an input exponent).
- **Moved items reached:** all seven splits are reached on core and wiring; `_exp_arg`, `_unit_angle`, `irrational_root`
  and `_pow_bound_templates` also on dev, f6, loop and opaque (counts above).

## 6g(c4): `constant_value` direct

**Code** (2fafc05, shapes cases bfb60c5). `RowsTpl::constant_value` / `direct_constant_value`: a Rational constant and
the compiled rows' seven texts are computed in Rust (`rows:rust:constant_value`); a Float, infinity or nan, `1/number` at
0, or another text goes to `_rows_runtime.constant_value` (`rows:python:constant_value`), counted by reason
(`rows:kept:constant_value:Float`, `:other`). Shadow: `shadow_split('constant_value', ...)` against
`_rows_runtime.constant_value`. Shapes cases: a Rational exponent's and a Rational base's compiled constants.

**Direct split:** 
- `constant_value`: dev 27/0; fuzz 6/0; cert 11/0; core 336/1; f6 24/0; loop 10/0; opaque 5/0; wiring 72/0; zero 2/0

**Plants, c4:**

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
| rows-constant-value-neg | dev 27, core 336, f6 24, wiring 72 | fuzz 6, cert 11, loop 10, opaque 5, zero 2 |

- **`rows:kept:constant_value:Float` counts 0 on every bar workload** (the f6/value/opaque Float queries are refused
  earlier, `refused:algebra: Float`, before rows run). Not a false zero: it fires on crafted queries (on 0643e9c's build:
  `Q.positive(0.5**x)` with x real: `rows:kept:constant_value:Float` 2, `rows:python:constant_value` 2, answers equal;
  `~/sa-rust-ids-work/sa-port-175/keptfire.txt`). **Floats stay on Python** (planner's default: SymPy's precision
  semantics).

## 6g(c5): the Addition template builders direct

**Code** (3f4cdc8 Rust, e64ec78 Python). `RowsTpl::add_tpl` / `add_tpl_parts`: `_half_templates`, `_bound_templates`,
`_recip_templates` and `_imag_templates` build the same facts key, consts, objects and node in Rust and hand
`Common::facts` a Rust generator (tcore.rs `half_rules` :228, `bound_rules` :252, `recip_rules` :274, `imag_rules` :299),
counted `rows:rust:NAME` (a call that returns no template counts too). A kept query, and `_imag_templates` with every `x`
a number (an Add of numbers, built with SymPy's arithmetic: `rows:kept:_imag_templates:number`, then
`rows:python:_imag_templates`), go to Python. knowledge_core_live: `ADD_TPL` (:31) and `_add_tpl_py` (:443), core's
builder run with `facts` captured, compared in `shadow_split` (:464) as (key, consts, objs, node, rules). Shapes cases:
`Q.integer(x/2 + y/2)` odd x, y; `Q.positive(1 + 2*x)` integer nonnegative x; `Q.positive(2 + 3/y)` positive y;
`Q.imaginary(I*x + I*y)` positive x, y.

**Direct split:** 
- `_half_templates`: dev 29/0; fuzz 73/0; cert 10/0; core 32/0; f6 26/0; opaque 4/0; wiring 1/0
- `_bound_templates`: dev 31/0; fuzz 45/0; core 120/0; f6 10/0; loop 4/0; opaque 8/0; wiring 6/0; zero 1/0
- `_recip_templates`: dev 31/0; fuzz 45/0; core 120/0; f6 10/0; loop 4/0; opaque 8/0; wiring 6/0; zero 1/0
- `_imag_templates`: core 8/0; wiring 4/0

**Plants, c5:**

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
| rows-half-tpl-flip | dev 29, fuzz 73, core 32, f6 26, opaque 4 | cert 10, wiring 1 |
| rows-bound-tpl-neg | dev 31, fuzz 45, core 120, f6 10, loop 4, opaque 8, wiring 6, zero 1 |  |
| rows-recip-tpl-neg | **void** on workloads: 0 on all 13 |  |
| rows-imag-tpl-sign | core 8, wiring 4 |  |

- **rows-recip-tpl-neg is void on every workload, with its reach:** it fires 0 on all 13 bar workloads and on orion's
  core, dev, f6 and wiring. `rows:rust:_recip_templates` counts every call (it equals `_bound_templates` on each
  workload, since core calls both on each bound split), but the plant's line runs only when `u` is `1/v` with `v` not a
  number, and no workload has a term `c0 + c1/v`. Its one reach is the shapes case `rows-recip-tpl-neg`
  (`Q.positive(2 + 3/y)`), where it **is caught** by the shadow: plain passes, planted fails with `shadow:mismatch` on
  `core:_recip_templates` (`~/sa-rust-ids-work/sa-port-175/plantshape-c5.txt`; the other three c5 plants are caught the
  same way there). Per the reached-code ruling the recip branch counts as not reached by a workload until one brings
  `c0 + c1/v`; it goes on the owed list with rows-mul-ipi-drop's reach.
- **`rows:kept:_imag_templates:number` counts 0 on every bar workload.** Not a false zero: `Q.imaginary(I*pi + I*E)` and
  `Q.imaginary(2*I + 3*I)` (unevaluated) each count 1 with `rows:python:_imag_templates` 1, answers equal (keptfire.txt).
  **I/-I values stay on Python** in `_rows_runtime` (this path builds them with SymPy's arithmetic; planner's ruling).

## The rest, for all three steps

**Module count (count rule): 14 of 32, unchanged.** Orion retrace on af63d20 (`rc.sh OUT WL
core.py,wiring.py,functions.py,registry.py`, pass 1 `[query]` lines; `~/sa-rust-ids-work/sa-port-187/rc-{dev,f6,core,wiring}.txt`):
- core.py still runs per query: `_bound_split`/`_half_split`/`_imag_split` from the knowledge_core_live shell for
  derived terms (dev 3 each, f6 6, core 69, wiring 4), `_coeff_term` (dev 1, f6 6, core 87, wiring 4), `_imag_term`
  (dev 8, f6 12, core 138, wiring 8), `ipi_split`/`pi_split` from functions.py's `_pi_trig` (dev 2/3, f6 130/100, core
  111/48, wiring 2/0), and `_unit_power_units` core 15 (the shell's fallback). So core.py doesn't count yet.
- wiring.py still runs per query on dev and f6: `_attributed.<locals>.template` (dev 6, f6 24) and
  `template.<locals>.<lambda>` (dev 31, f6 134), so it doesn't count yet.
- registry.py: no `[query]` line on the four (`_covers` and `_load` only at no-query), as before.
c3-c5 removed `_half_templates`, `_bound_templates`, `irrational_root` and the other moved splits from the per-query
trace (S1's retrace had `_half_templates` 29 and `_bound_templates` 31 on dev). Next, the 6e/6f shells (`_pi_trig` with
the plain `_unary` first) take `ipi_split`/`pi_split` off core's per-query list.

**Direct-split counts explained:** rows:rust:NAME + rows:python:NAME equals S1's rows:python:NAME (the shell, before) on
every workload for all twelve moved names. The Python remainder is: `ipi_split` core 1 and `_pow_bound_templates` loop 3
(derived argument or result; `core:derived:_pow_bound_templates` loop 3), `_unit_power_units` core 15 (the shell's own
fallback: a non-Rational exponent or e outside the table), `constant_value` core 1 (`1/number` at 0:
`rows:constant_value:python:Zero:1/number` 1). `core:derived` totals (dev 9, fuzz 72, core 207, f6 18, loop 18, opaque
21, wiring 12) are c1's three Add splits on derived terms and the loop 3 above.

**Rows scaffolding, owed before any backend PR until 0:** `scaffold:rebuilt` dev 29, fuzz 305, f6 45, opaque 15, value
221, zero 28 (`scaffold:rebuilt:f6` 45 as on S1); `scaffold:mismatch` f6 2; `rows:python:Mul`/`Add`/`Integer` core
96/96/740, dev 3/6/256, wiring 12/8/224, loop 3/6/60. Also owed: rows-mul-ipi-drop's reach (a workload whose s is an input
Mul; void on all 13 here, as on S1), rows-recip-tpl-neg's reach (`c0 + c1/v`), and the rest of the backend-PR list as c1.

**Kept on Python with reason:** `_rows_runtime`'s I/-I values (c5: `rows:kept:_imag_templates:number`) and Floats (c4:
`rows:kept:constant_value:Float`), both 0 on workloads and shown to fire (not false zeros); queries under a non-default
registry; `enclose`; `const_value` (named callback; `rows:python:const_value` dev 256, fuzz 136, core 740, f6 380).

**equiv-one and ge2-drop (precision ruling):** unchanged from 6g(c1): pure Python never calls `Rules.equiv` per query (no
caller in satassume/; table.py:153 writes an equiv row's two rules itself) and calls `ge2_alternatives` only from
table.py:141 for an `int>=2` premise, which no table has. So both are Python removal candidates, not port items;
common_direct.py catches both (exit 1).

**Known id()-reuse failure, owed:** `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`
fails on Rust from 5c10a (67d108d) on: reused object ids, a test artifact (sa-port-185, report a28c548: 50 of 50 fail
under Rust at 67d108d, a keep-alive variant passes 50 of 50). Test not edited. It is failed in the base rows too (5c10a's
and 5c10b's), so it isn't a changed outcome here.

**Not run:** moved to "before any backend PR", none quoted as met: the mutant 2, 5, 6, 7, 9 rerun and mutlive's control;
the boundary rescore and suite column; the final drop score and its lost rows; the suite split with Python's counter;
`order:_rows`' evidence (not caught meanwhile); the `_forms` guard test; history reruns (seed1 was run); forced moves;
the native path; timing. The rows plants on the suite. **Speed not measured.** Mutants 2, 5, 6, 7, 9 still rest on the
API fuzzer alone; 10 of the 25 boundary mutants have no real-engine catch, and the boundary suite column wasn't run. The
`_n_conflicts` view in rust_plugin.py is a test-plugin shim (64 tests). No evaluator asked for.
