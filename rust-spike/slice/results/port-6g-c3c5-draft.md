
# Steps 6g(c3), 6g(c4), 6g(c5): the Pow family's splits, `constant_value`, and the Addition template builders from the query's table, landed as one stack (issue 323)

**One stack, three steps** (planner's 6g(c3)-(c5) stack go, 8 Nov ~14:00). Built by sa-port-163 (c3), sa-port-164 (c4,
c5's Rust) and sa-port-172 (c5's Python, the stack). First tested source **0643e9c** on rust-slice 3611952 (5c8): c3
544be25 + fc939a2, c4 0a7e799 + b08e689, c5 48d0d05 + 0643e9c. Its full bar (pareto1
`~/sp19/sa-rust-ids-work/sa-port-172/bar-6g-c3c5/`, end.txt `exit 0 2026-11-08T16:54:03Z` written by the job; .so
ba519c3f…) equalled base on every item. rust-slice had moved to 2d12e81 (5c9a e0ec542, 5c9b 2553a68, 5c9c 2d12e81, all
with source diffs), so the stack was rebased clean onto 2d12e81 by `bar.sh land 0643e9c` (sa-port-175): c3 72d4e12 +
8fd1e5e, c4 aced0b3 + cd90852, c5 044bd51 + **d0374e9**. The push guard named 18 guarded files from 5c9a-c (engmemo.rs,
procmemo.rs, memos.rs, session.rs, relations_core.rs, relevance.rs, budget.rs, compile_loop.rs, constfield.rs, lib.rs,
session_live.py, term_live.py, memo_check/memo_trace/proc_memo_trace.py, test_engmemo_core.py, test_procmemo_core.py,
satassume/state/memos.py), all executed by the bar, so a **second full bar ran on d0374e9**, the tested source
(`~/sp19/sa-rust-ids-work/sa-port-175/bar-6g-c3c5r/`, end.txt RBAR_END; .so RBAR_SO): the stack's config plus 5c9b/c's
test_procmemo_core.py and test_engmemo_core.py, base suite rows 5c9c's (`sa-port-181/bar-5c9c/suite`), KEPT_BASE the
first stack bar. **Landed:** LANDED_SHA. Each step's plant table is kept apart below, as the stack ruling asks.

## The bar (on d0374e9; the first stack bar on 0643e9c in brackets where it differs)
RBAR_ITEMS

## 6g(c3): the Pow family's seven splits direct

**Code** (72d4e12, plant fix 8fd1e5e). rows_tpl.rs's Pow family computes `_exp_arg`, `_unit_angle`, `ipi_split`,
`irrational_root`, `_unit_power_units`, `_pow_bound_templates` and `ipi_rules` from the query's table through
`RowsTpl::split` / `direct_rows`, with tcore.rs's `ipi_rules` (~:597). Each falls back to the shell (`rows:python:NAME`)
for no or a kept query, a derived argument or result, a product rest (`kept_product`), or a non-Rational exponent in
`_unit_power_units` (the shell's counted `as_real_imag` fallback). The shadow compares each result through
knowledge_core_live `shadow_split`. test_knowledge_core_shapes: seven DIRECT entries, six cases.

**Direct split** (rows:rust / rows:python on the d0374e9 bar; before = S1's bar, all on Python; rust + python equals
before on every workload): C3_COUNTS

**Plants, c3** (bar on d0374e9: dev, fuzz and the 11 workloads, each against this run's Python; orion runs of core, dev,
f6 and wiring on fc939a2 in brackets):

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
C3_TABLE

- **c3's -neg pair, replaced in this stack:** rows-unit-angle-neg and rows-ipi-split-neg fired (orion: core 33/54, wiring
  5/3) and MATCHed everywhere: negation keeps the parity, denominator and half-oddness that the rules read, so both were
  void by construction. Replaced in both lists (8fd1e5e) by rows-unit-angle-shift and rows-ipi-split-shift (plus 1, which
  flips parity); both are caught on core and wiring (table), 0 on dev and f6, whose queries don't reach these splits.
- The other five c3 plants are caught on core and wiring only; dev and f6 fire 0 (their queries have no Pow of this
  shape with an input exponent).

## 6g(c4): `constant_value` direct

**Code** (aced0b3, shapes cases cd90852). `RowsTpl::constant_value` / `direct_constant_value`: a Rational constant and
the compiled rows' seven texts are computed in Rust (`rows:rust:constant_value`); a Float, infinity or nan, `1/number` at
0, or another text goes to `_rows_runtime.constant_value` (`rows:python:constant_value`), counted by reason
(`rows:kept:constant_value:Float`, `:other`). Shadow: `shadow_split('constant_value', ...)` against
`_rows_runtime.constant_value`. Shapes cases: a Rational exponent's and a Rational base's compiled constants.

**Direct split:** C4_COUNTS

**Plants, c4:**

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
C4_TABLE

- **`rows:kept:constant_value:Float` counts 0 on every bar workload** (the f6/value/opaque Float queries are refused
  earlier, `refused:algebra: Float`, before rows run). Not a false zero: it fires on crafted queries on 0643e9c's build
  (`Q.positive(0.5**x)` with x real: `rows:kept:constant_value:Float` 2, `rows:python:constant_value` 2, answers equal;
  `~/sa-rust-ids-work/sa-port-175/keptfire.txt`).

## 6g(c5): the Addition template builders direct

**Code** (044bd51 Rust, d0374e9 Python). `RowsTpl::add_tpl` / `add_tpl_parts`: `_half_templates`, `_bound_templates`,
`_recip_templates` and `_imag_templates` build the same facts key, consts, objects and node in Rust and hand
`Common::facts` a Rust generator (tcore.rs `half_rules` :228, `bound_rules` :252, `recip_rules` :274, `imag_rules` :299),
counted `rows:rust:NAME` (a call that returns no template counts too). A kept query, and `_imag_templates` with every `x`
a number (an Add of numbers, built with SymPy's arithmetic: `rows:kept:_imag_templates:number`, then
`rows:python:_imag_templates`), go to Python. knowledge_core_live: `ADD_TPL` (:31) and `_add_tpl_py`, core's builder run
with `facts` captured, compared in `shadow_split` as (key, consts, objs, node, rules). Shapes cases: `Q.integer(x/2 +
y/2)` odd x, y; `Q.positive(1 + 2*x)` integer nonnegative x; `Q.positive(2 + 3/y)` positive y; `Q.imaginary(I*x + I*y)`
positive x, y.

**Direct split:** C5_COUNTS

**Plants, c5:**

| plant | caught (DIFFER) on, fired | fired, MATCH |
|---|---|---|
C5_TABLE

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

## The rest, for all three steps

COMMON_TAIL

- **Known id()-reuse failure, owed:** `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`
  fails on Rust from 5c10a (67d108d) on: reused object ids, a test artifact (sa-port-185, report a28c548: 50 of 50 fail under
  Rust at 67d108d, a keep-alive variant passes 50 of 50). Test not edited. It is failed in the base rows too (5c10a's), so
  it isn't a changed outcome here.
