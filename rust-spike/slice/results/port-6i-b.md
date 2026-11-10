# 6i, part (b): functions' slotted `_unary`, `nary` and `_in_unit_interval_units` on Rust (issue 323)

sa-port-212 wrote the port (6829d06). sa-port-214 fixed the test cases, added the direct guard tests, ran the probe and bar 1.
sa-port-216 read bar 1, rebased onto db7130a, ran bar 2 and landed it.

## What moved
- `term/fn_tpl.rs` (new) answers functions.py's slotted templates, dispatched as `Tpl::Slotted` (dispatch.rs:236-262, call
  :374-392). `wiring.template` tags them with `_satassume_slotted` (wiring.py:138-160):
  - `_unary`: slots `x + c` (tf6 `f6_shifted`), and for genocchi the slot `x/2` (tf6 `f6_halved`) plus `_genocchi_half_rules`.
  - asin/acos unit facts (`_unit_interval_units`).
  - `_value_units`: `expr.func(c)` stays a SymPy callback (`fn:value:sympy`), and `value_units` is called through the name
    functions.py bound.
  - `nary`.
- Slot objects are rebuilt by `term_live.scaffold`. With no query, or with an argument that isn't a term of the query, the
  Python template runs (`fn:python:{unary,nary}:{no-query,derived-arg}`).
- Plants 340-345 (`fn-*`). Control: `dispatch-slotted-off`.
- offline_data.json: only wiring.py's hash changed. Ownership TSV: the 5 functions.py rows are set to 6i(b).
- **Test edit (fe250ff):** test_knowledge_f6_fallback.py's two Float cases (acos-float, asin-float-out) had failed since
  6829d06. Here is why. At 80665b5 the Python `_unary` template ran inside dispatch.rs:242's fallback and called 6f's swapped
  `_unit_interval_units` on a Float, which counted `f6:unit_interval:float`. Now Rust's template owns the node, and the query
  goes like this:
  - conversion refuses the whole query (`refused:algebra: Float`, a kept reason) before any template runs;
  - Python's kept path answers it, where nothing is swapped.

  The cases now check that refusal count and Python's answer. They leave the loud list, because no callback runs for them.
  - **fn_tpl.rs's Float branch isn't reached from the engine.** Under a query, asin/acos carry the slot `x - 1`, and
    `f6_shifted` refuses a Float. With no query, the node goes to Python (`fn:python:unary:no-query`). So
    `f6:unit_interval:float` and the Float branch of `unit_interval` are not reached by any path. The branch stays as
    written and is named here.
- **New test, test_knowledge_fn_direct.py (14 tests).** It compares Rust's `Dispatch.clauses_for` with Python's
  `TemplateRegistry.clauses_for` by content, for each guard no workload reaches:
  - Float arguments with no query;
  - `log(x, 2)` (`fn:rust:unary:none`);
  - beta and besselj with three arguments (`fn:rust:nary:none`);
  - asinh with no query (`fn:rust:unary`);
  - log and polylog under a pushed query, with the argument a query term (`fn:rust:*`) or not
    (`fn:python:{unary,nary}:derived-arg`);
  - a Float query refused before any template (`fn:rust:unit_interval` 0).

  Each test asserts the exact `fn:` counter that fired. Rust's and Python's templates share `_common._CACHE` by pattern
  key, so the test clears it before each side. Otherwise the second side reads the first side's pattern, and a planted rule
  shows on both sides. The first draft of this test had that hole: it passed under both plants. With the cache cleared,
  `fn-unary-drop-last` fails exactly asinh and log(x), and `fn-nary-drop-last` fails exactly polylog(2, x). dispatch_direct.py
  compares the same way and may have the same hole. **Unchecked; a backend-PR-list item.**

## SHAs and landing
- Base: rust-slice 80665b5 for the first bar. Tested there: **fe250ff** (6829d06 + 4626fff + fe250ff).
- Held over the week rule (90% at 15:53 9 Nov; the architect: no landing until the 10 Nov 04:00 UTC reset). At 04:33Z 10
  Nov the week read 2%.
- rust-slice had moved 80665b5 → **db7130a** (the harness install-order fix and Q2's Rust handler plant, sa-port-218).
  `bar.sh land fe250ff` without PUSH, after the rebase, gave **incoming diff: `rust-spike/slice/live.py` (34 lines),
  `rust-spike/slice/test_live_handler_plant.py` (new, 66), and results/ only** (HANDOFF-sa-port-206/209,
  harness-install-order.md). live.py is the harness every live and extra phase runs, so it is guarded source: the bar was
  rerun on the rebased head **e817aa1** (code commits 469d6b1, 4d8f1ed, 186ae10 = 6829d06, 4626fff, fe250ff rebased; no
  edits). The rebased Rust and Python source is byte-identical to fe250ff's apart from the incoming diff.
- Tested for landing: **e817aa1** (bar 2 below). Landed: BAR2_LANDED.

## Bar 1 (pareto1, `~/sp19/sa-rust-ids-work/sa-port-214/bar-6ib` on fe250ff, base 80665b5)
Run 15:18Z-16:16Z 9 Nov under a shared lease; every phase exited 0 (build, tests, suite, live, plants, extra, suiteplants,
sum); seed1 was not run. `.so` sha256 0dc0110d…. Base suite rows: `sa-port-208/bar-s2/suite`. WLS: the 11. Tests phase:
**811 passed, 4 skipped**, exit 0. DIRECT: `relations_direct.py 300 0` exit 0; `dispatch_direct.py` exit 0, BAD 0, with
`registry:rust:_unary.<locals>.template` 6 and `nary` 1 reached. The summary is copied to
`~/sa-rust-ids-work/sa-port-216/bar-6ib/sum.txt`, the fallback counts to `.../sa-port-216/bar-6ib/fb-cand.txt` (base:
`.../sa-port-216/fb-s2.txt`, the S2 bar on bb92b07, by the same `fbcounts.py`).
1. **Suite by id:** 5,991 passed, 127 failed, 23 skipped (plus 18 xfailed), over 6,159 ids. **Against base: new 0, gone 0,
   changed outcome 0.** Passed splits into 5,990 with no handler firing and 1 with a firing:
   `tests/test_invariants.py::test_ci_stream_reports_only_what_replays`, the named case.
2. **Fresh dev and fuzz: answers and state MATCH** (Rust against Python, traced and untraced; Python against Python as the
   control). dev answers_sha 31cd0945c07f02a6, fuzz 173502b6ef285ad6. **All 11 extra workloads MATCH**, Rust against Python,
   each with its Python control MATCH.
3. **Plants caught:** five of the six are caught by the live comparison on the workload that reaches them; table below.
4. **Quiet handler firings on Rust: the handler multiset is the same as base.** 39 rows in 2 tests:
   - 34 × `_consistent` AttributeError `'Solver' object has no attribute '_ok'`, in test_ci_stream_reports_only_what_replays;
   - 4 × `_consistent` AttributeError `_rb_clauses`, in the same test;
   - 1 × `Engine._build_context` RuntimeError "Already mutably borrowed", in test_protocol_on_fuzz (the named 46-stub cause).

   **engine.py:1906's catches (`ctx:caught`): 0 on all 13 workloads** (dev, fuzz and the 11 WLS, from each
   `*-rust.session.json`). The live and extra handler files have 0 rows; TermFault in pytest.log: 0. These Rust-side zeros
   were **void** at the ported `_build_context`/verdict sites: bar 1 ran the old live.py, which set the handler plant before
   `backend.install()` (harness-install-order.md). Bar 2 runs the fixed live.py with `ctx-check-raise` as a live control.
5. **Known differences in answers or read state: none.**

### Plants (bar 1)
`fired` reads the session report. sum.txt's "plant fired in the suite: 0" is **void for these plants**: the fn plants count
in Common's counts, not in `rel:plant_fired` (as 6i(a)'s outer plants). The suite catch is read from changed outcomes.
SUITE_PLANTS `zero` runs the suite only under plants that fired 0 on dev and fuzz.

| plant | fired (bar) | caught by | suite (against the plain suite) |
|---|---|---|---|
| `fn-unary-drop-last` (340) | dev 31, f6 75, opaque 45, value 309, zero 5 | dev, f6, opaque, value DIFFER; zero MATCH (5 fires, no answer moved) | not run (fires on dev) |
| `fn-nary-drop-last` (341) | f6 47 | f6 DIFFER | 14 changed (test_nan_arguments Falling/RisingFactorial, test_notmpl_elementary, test_notmpl_special) |
| `fn-unit-interval-flip` (342) | f6 18 | f6 DIFFER | 1 changed (`test_sympy_api.py::test_function_closures`) |
| `fn-value-drop` (343) | value 236 | value DIFFER | 1 changed, the planted-history test failed -> passed: the known id()-reuse flip, not a catch, so **void in the suite** |
| `fn-genocchi-half-flip` (344) | value 50 | value DIFFER | 0 changed: **void in the suite** |
| `fn-unary-shift` (345) | dev 2, f6 33, opaque 16, value 212 | dev, f6, opaque, value DIFFER | not run (fires on dev) |

Every fn plant fires 0 on fuzz, budget, cert, core, loop, rootof, scope and wiring, and those all MATCH, as expected. No
plant is void on every workload. Void cells: `fn-unary-drop-last` on zero (fires, MATCH); `fn-value-drop` and
`fn-genocchi-half-flip` in the suite.

## Bar 2 (pareto1, `~/sp19/sa-rust-ids-work/sa-port-216/bar-6ib` on e817aa1, base db7130a)
Run 04:34Z-05:54Z 10 Nov under a shared lease; every phase exited 0 (build, tests, suite, live, plants, extra, suiteplants,
sum); seed1 was not run. `.so` sha256 0dc0110d…, the same as bar 1's (the rebase brought no Rust change). Base suite rows:
`sa-port-209/bar-install-order/suite` (the harness bar on d77d3db, db7130a's source). WLS: the 11. PLANTS: the six fn-*
plus `ctx-check-raise`, the live control for the Rust-side handler rows. Tests phase: **817 passed, 4 skipped**, exit 0 (bar
1's list plus test_live_handler_plant.py). DIRECT: `relations_direct.py 300 0` exit 0; `dispatch_direct.py` exit 0, BAD 0,
with `registry:rust:_unary.<locals>.template` 6 and `nary` 1 reached. Copies: `~/sa-rust-ids-work/sa-port-220/bar2`
(sum.txt, knowledge, session and handler files); fallback counts `.../sa-port-220/fb-bar2.txt`, base `.../fb-base209.txt`
(the harness bar's files by the same `fbcounts.py`); ctx counts by `.../sa-port-220/ctxcount.py`.
1. **Suite by id:** 5,991 passed, 127 failed, 23 skipped (plus 18 xfailed), over 6,159 ids. **Against base: new 0, gone 0,
   changed outcome 1:** `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence`
   passed -> failed, the known id()-reuse failure (a28c548), not a Rust difference. It flips both ways between runs: in
   this bar's suite plants it goes failed -> passed under `fn-nary-drop-last` and `fn-value-drop`, and stays failed under
   the other two. Passed splits into 5,990 with no handler firing and 1 with a firing:
   `tests/test_invariants.py::test_ci_stream_reports_only_what_replays`, the named case.
2. **Fresh dev and fuzz: answers and state MATCH** (Rust against Python, traced and untraced; Python against Python as the
   control). dev answers_sha 31cd0945c07f02a6, fuzz 173502b6ef285ad6, the same as bar 1. **All 11 extra workloads MATCH**,
   Rust against Python, each with its Python control MATCH.
3. **Plants caught:** the same five of six fn plants as bar 1, with the same fire counts, plus `ctx-check-raise` caught
   (DIFFER) on all 13 workloads; table below.
4. **Quiet handler firings on Rust: the handler multiset is the same as base** (ids whose caught rows differ: 0). 39 rows in
   2 tests:
   - 34 × `_consistent` AttributeError `'Solver' object has no attribute '_ok'`, in test_ci_stream_reports_only_what_replays;
   - 4 × `_consistent` AttributeError `_rb_clauses`, in the same test;
   - 1 × `Engine._build_context` RuntimeError "Already mutably borrowed", in test_protocol_on_fuzz (the named 46-stub cause).

   **engine.py:1906's catches (`ctx:caught`): 0 on all 13 workloads** (from each `*-rust.session.json`). The live and extra
   Rust handler files have 0 rows; TermFault in pytest.log: 0. **These zeros are not void:** bar 2 runs the fixed live.py,
   and under `ctx-check-raise` the same sites catch every complete check on every workload, each catch also a handler row
   (`Engine._build_context` ValueError "planted ctx-check-raise"):

   | workload | complete checks (plain) | `ctx:caught` plain | `ctx:caught` under the plant = handler rows |
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

   (The last column is the planted run's own count of complete checks, which is higher than the plain run's on fuzz, value
   and zero; cause not read. In every planted run `ctx:caught` equals its own `ctx:complete_check`.)
5. **Known differences in answers or read state: none.**

### Plants (bar 2)
Same reading as bar 1: `fired` reads the session report; the suite catch is read from changed outcomes against this run's
plain suite (sum.txt's "plant fired in the suite: 0" is void for the fn plants, which count in Common's counts).

| plant | fired (bar) | caught by | suite (against the plain suite) |
|---|---|---|---|
| `fn-unary-drop-last` (340) | dev 31, f6 75, opaque 45, value 309, zero 5 | dev, f6, opaque, value DIFFER; zero MATCH (5 fires, no answer moved) | not run (fires on dev) |
| `fn-nary-drop-last` (341) | f6 47 | f6 DIFFER | 15 changed: the same 14 as bar 1 (test_nan_arguments Falling/RisingFactorial, test_notmpl_elementary, test_notmpl_special) plus the planted-history test failed -> passed (the id()-reuse flip, not a catch) |
| `fn-unit-interval-flip` (342) | f6 18 | f6 DIFFER | 1 changed (`test_sympy_api.py::test_function_closures`) |
| `fn-value-drop` (343) | value 236 | value DIFFER | 1 changed, the planted-history test failed -> passed: the id()-reuse flip, so **void in the suite** |
| `fn-genocchi-half-flip` (344) | value 50 | value DIFFER | 0 changed: **void in the suite** |
| `fn-unary-shift` (345) | dev 2, f6 33, opaque 16, value 212 | dev, f6, opaque, value DIFFER | not run (fires on dev) |
| `ctx-check-raise` (Q2 control) | dev 833, fuzz 2,980, f6 6, value 636, rootof 368, opaque 31, core 300, scope 166, loop 244, zero 718, wiring 5,004, cert 61, budget 16 | DIFFER on all 13 | not run (fires on dev) |

Every fn plant fires 0 on fuzz, budget, cert, core, loop, rootof, scope and wiring, and those all MATCH. Void cells:
`fn-unary-drop-last` on zero (fires, MATCH); `fn-value-drop` and `fn-genocchi-half-flip` in the suite.

### Fallbacks and kept shares (bar 2)
`fbcounts.py` on bar 2 against the harness bar on d77d3db (db7130a's source) gives **exactly bar 1's deltas** and nothing
else: `registry:python` dev 126 → 95, f6 211 → 65, opaque 101 → 42, value 507 → 180, zero 43 → 38 (`_unary`/`nary` gone on
every workload); `fn:` as in bar 1 (value: `rust:unary` 309, `rust:genocchi_half` 50, `value_units` 236, **`value:sympy`
264**, 0 on the other 12); `registry:kept` f6 2 → 14, opaque 2 → 9, value 6 → 15; **value `scaffold:rebuilt` 221 → 269
(+48)**. Every `rows:python` count (rows_tpl.rs:413) equals base; **`ad:cbm_noid` 0 on all 13 workloads.** Scope's counts
differ from bar 1's (`registry:python` 26 → 33, `rows:python` 0 → 64) and equal the harness bar's: the install-order fix,
not this step, puts scope's queries on Rust. Kept shares: **every share equals base**, the same numbers as bar 1's list
below.

## Fallbacks to Python inside ported code (planner's fallback-reporting ruling, with its `ad:cbm_noid` addition)
From bar 1's knowledge files by `fbcounts.py` (prefixes `registry:python:`, `fn:`, `ad:cbm_noid`, `rows:python:`,
`registry:kept:`, `outer:`, `scaffold:`, `value:`, `realroots:`), against the S2 bar on bb92b07. **`_unary.<locals>.template`
and `nary.<locals>.template` are gone from dispatch.rs:242's `registry:python` on every workload.** Every `rows:python`
count (rows_tpl.rs:413's fallback to the kcl shells) equals the S2 bar's. **`ad:cbm_noid`: 0 on all 13 workloads.**

| workload | `registry:python` before (S2 bar) → after | names removed | `fn:` firings on Rust (after) |
|---|---|---|---|
| dev | 126 → 95 | `_unary` 31 | `rust:unary` 31 |
| f6 | 211 → 65 | `_unary` 97, `nary` 49 | `rust:unary` 75, `rust:nary` 47, `rust:unit_interval` 18 |
| opaque | 101 → 42 | `_unary` 59 | `rust:unary` 45 |
| value | 507 → 180 | `_unary` 327 | `rust:unary` 309, `rust:genocchi_half` 50, `value_units` 236, `value:sympy` 264 |
| zero | 43 → 38 | `_unary` 5 | `rust:unary` 5 |
| fuzz 38, rootof 27, core 35, scope 26, loop 31, wiring 75, cert 24, budget 469 | unchanged, by template | none | 0 |

The `fn:` counters are fn_tpl.rs's own (per Rust template call), not dispatch's per-registry count, so the columns don't
subtract one to one.

After, by template (`registry:python`, dispatch.rs:242): `_load` (the registry load) and atoms' input-fact templates
`symbol_units`/`constant_units` only, on every workload: dev 95 (`_load` 68, `constant_units` 12, `symbol_units` 15); f6 65
(54, 4, 7); opaque 42 (39, -, 3); value 180 (29, 150, 1); zero 38 (29, 3, 6); fuzz 38 (30, 6, 2); rootof 27 (26, -, 1);
core 35 (28, 1, 6); scope 26 (26); loop 31 (20, 5, 6); wiring 75 (35, -, 40); cert 24 (20, 1, 3); budget 469 (19, -, 450).

Other prefixes that moved, each explained:
- `registry:kept` rises on the kept (refused Float) queries, where the slotted templates now count as kept instead of
  Python: f6 2 → 14 (`_unary` 11, `nary` 1), opaque 2 → 9 (`_unary` 7), value 6 → 15 (`_unary` 9). The same move 6i(a)
  showed for multigamma. These are the named kept reason `refused`, whose shares equal base.
- `scaffold:rebuilt` on value 221 → 269 (+48; `rebuilt:f6` the same): fn_tpl.rs's slot objects `x + c` and `x/2` are built
  in the query's table and rebuilt in SymPy by `term_live.scaffold` (fn_tpl.rs:235), the temporary construction the
  scaffolding ruling allows on the slice branch, checked against Rust's form (`scaffold:mismatch` unchanged: f6 2, the
  `refused:scaffold` queries). It is 0 on every other workload's delta. **This step adds 48 scaffold rebuilds on value; the
  count must reach zero before any backend PR.**

What still falls back, and why:
- dispatch.rs:242: `_load` is :200's registry load; `symbol_units`/`constant_units` are atoms' input-fact templates.
- rows_tpl.rs:413: `Integer` and `const_value` (the named SymPy callback) on every workload, plus the kcl shells
  (`_bound_split`, `_half_split`, `_imag_split`, `_mul_factor_sets`, `_quotient_templates`, `Add`, `Mul`,
  `_pow_bound_templates`, `_unit_power_units`, `ipi_split`, `constant_value`) as before.
- So dispatch.rs:242 and rows_tpl.rs:413 don't yet report 0 outside named callbacks; 6i(b)'s templates no longer fall back.

## Kept reasons (planner ruling, 03:42 UTC 8 Nov), bar 1
Every share equals base (the S2 bar).
- Out-of-scope: dev 24/1,985 (1.21%); every other workload 0.
- Refused:
  - f6 13/2,902 (0.45%): `algebra: Float` 10, `lra: a callback on a derived term` 1, `scaffold: rebuilt form differs from
    Rust` 2;
  - value 15/3,742 (0.40%), all `algebra: Float`;
  - opaque 7/2,546 (0.27%): `algebra: infinity or nan` 5, `algebra: holds an infinity, nan or Float` 2;
  - wiring 1/6,512 (0.02%), `lra: a callback on a derived term`;
  - dev, fuzz, rootof, core, scope, loop, zero, cert, budget: 0.

## State: each container this step touches
None new. fn_tpl.rs holds no static, cache or memo: each answer is a pattern built per call from the term's reads and goes
into dispatch's per-query clause list. Rust's and Python's templates share `_common._CACHE` by pattern key (Python's
existing cache, unchanged). The live state comparison MATCHes on all 13 workloads.

## Earlier evidence (orion, not the bar)
- sa-port-212's quick live check on 6829d06: f6 and value MATCH, Rust against Python. All seven plant firings were caught:
  - f6: `fn-nary-drop-last` 47, `fn-unary-drop-last` 75, `fn-unary-shift` 33, `fn-unit-interval-flip` 18;
  - value: `fn-genocchi-half-flip` 50, `fn-unary-drop-last` 309, `fn-value-drop` 236.

  The control `dispatch-slotted-off` MATCHes on f6.
- On fe250ff's build, the knowledge test files f6_fallback, fn_direct, rows, value_units and wire gave 87 passed.

## Per-query calls into functions.py, before (80665b5) and after (fe250ff)
Module-wide probe: sa-port-212's count7.py traces every function in the file, pass 1, `kind query`, 15 runs each. Base is
`~/sa-rust-ids-work/sa-port-212/probe/base`. Candidate is `~/sa-rust-ids-work/sa-port-214/probe/cand`, run from the worktree
`sa-port-214/cand-tree` at fe250ff with its own .so (sha256 3dc0eb40…); the clone wasn't touched while it ran. Summary
from `fnsumm.py`.

| workload | before | after |
|---|---|---|
| dev, dev-seed1 | 46 each (`_unary` template 31, build 15) | **0** |
| f6 | 215 (`_unary` template 86, build 31; `nary` 48, build 32; unit-interval `units` 18) | **0** |
| opaque | 75 (template 52, build 23) | **0** |
| value | 986 (template 318, build 309, `_value_units` 309, genocchi `half` 50) | **0** |
| zero | 6 (5, 1) | **0** |
| fuzz, fuzz-seed1, rootof, core, scope, loop, wiring, cert, budget | 0 | 0 |

Calls outside queries are the same before and after:
- import-time registration (`[no-query]`);
- the kept Float queries (`[kept:refused]`: f6 10 refused queries, opaque 7, value 9). These are the named kept reason, not
  per-query Python on a converted query.

The number of raised queries per workload equals base (value 318, fuzz 207, zero 74, core 5, f6 2).

After, `registry:python` per workload (pass 1) is only `_load`, `constant_units` and `symbol_units`. `_unary` and `nary` are
gone from it on every workload.

## `fn:value:sympy` (planner's ruling, 9 Nov ~15:15): the check on the (func, c) pairs
- **Distinct pairs:** `vpairs.py` records each call into SymPy's `eval` of a VALUE_AT_INTEGER class inside a query, on the
  Rust backend with SymPy's cache off, one pass.
  - **value: 265 distinct `(func, c)` pairs** (288 calls). The functions are andre, catalan, factorial2, genocchi, partition
    and subfactorial. Each has about 44 arguments: -5..30, ±50, ±100, 150, ±199 and ±200.
  - f6, dev, opaque, zero, rootof and core: **0.**
  - Output: `~/sa-rust-ids-work/sa-port-214/vpairs-nocache.txt`.
- **They are not table misses.** offline_data.json already holds D's `value_units` table: every VALUE_AT_INTEGER function at
  every integer |c| <= 200, keyed by exact class. That is the whole domain where fn_tpl.rs calls `expr.func(c)`.
  test_knowledge_value_units.py checks the table against today's `_value_units`, row by row. But no engine code reads the
  table: `OfflineData` loads it, and fn_tpl.rs's `value` never looks it up.
- **So the set is small and fixed, and the generator already includes it.** Reading the table in fn_tpl.rs removes the
  callback for the tagged classes. A subclass isn't in the table and would keep the callback. This is the later small item
  the ruling describes. Until it's done, the callback is a named one, with these fire counts: probe c1 on 6829d06, 2
  passes: value 264, other workloads 0. Bar 1 (fe250ff), `fn:value:sympy` per workload: **value 264; dev, fuzz, f6, rootof,
  opaque, core, scope, loop, zero, wiring, cert, budget 0.**
- The TSV row for `_value_units` (functions.py:421) now reads "offline table plus per-query callback on a miss" (planner),
  noting that the table is unread today, so the callback fires on every call; port-ownership.md's section-2 note says the
  same. **Later small item:** fn_tpl.rs reads the table, which removes the callback for the tagged classes.

## Module count (STATUS "Counted modules", 19 of 32 at db7130a)
functions.py has 0 per-query Python on all 15 workloads (the module-wide probe above, every function in the file, on fe250ff;
the rebase brought no change to functions.py, fn_tpl.rs or dispatch.rs). With `fn:value:sympy` ruled a named callback, it
**counts: 20 of 32**, with this footnote: "functions.py: keeps `fn:value:sympy`, `expr.func(c)` on Rust's value-at-integer
facts, a named SymPy-semantics callback (value 264, 0 on the other 12 workloads; bar on fe250ff); offline_data.json's
`value_units` table covers every pair it is called with and is unread; reading it in fn_tpl.rs removes the callback for
the tagged classes." The other footnotes stand as in STATUS.

## Not run
- Moved to "before any backend PR", none quoted as met:
  - the mutant 2, 5, 6, 7, 9 rerun and mutlive's control;
  - the boundary rescore and suite column;
  - the final drop score and its lost rows;
  - the suite split with Python's counter;
  - `order:_rows`' evidence (not caught meanwhile);
  - the `_forms` guard test;
  - history and seed reruns (the bars' seed1 phase not run; the probe ran dev-seed1 and fuzz-seed1);
  - forced moves;
  - the native path;
  - timing.
- The module-wide probe was not rerun on e817aa1 (no functions.py or Rust change came in).
- The dispatch_direct.py shared-cache question: `_common._CACHE` is shared by pattern key, so dispatch_direct.py's
  side-by-side comparison may read one side's pattern on the other, as test_knowledge_fn_direct.py's first draft did.
  **Unchecked; a backend-PR-list item.**

Other notes, carried:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
- `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` is the known id()-reuse
  failure (a28c548), unedited.
- `test_performance_smoke_300_vars`: same outcome as base in bar 1's suite (changed outcome 0 overall); not chased.
- **Speed not measured.**
