# HANDOFF sa-port-212: 6i(b), port/6i-b at 4626fff (from 80665b5), not barred

## Done
- **6829d06**: `term/fn_tpl.rs` (new) answers functions.py's slotted `_unary` (slots `x + c`; genocchi's `x/2` plus
  `_genocchi_half_rules`; asin/acos unit facts; `_value_units` with `expr.func(c)` kept as a callback `fn:value:sympy`) and
  `nary`. dispatch.rs gets `Tpl::Slotted`, recognised by `_satassume_slotted`, which `wiring.template` (wiring.py :138-160)
  sets. Slots come from tf6 `f6_shifted` and the new `f6_halved`, rebuilt by `term_live.scaffold`. No query or a derived
  argument runs the Python template (`fn:python:{unary,nary}:{no-query,derived-arg}`). Plants 340-345 (`fn-*`, in
  knowledge_common_live.PLANTS and common.rs set_plant), control `dispatch-slotted-off` (knowledge_live.PLANTS).
  offline_data.json: only wiring.py's hash changed (`gen_offline_data.py` regenerated it). Ownership TSV: 5 functions.py rows
  set to 6i(b), plus an "Updated by sa-port-212" paragraph in port-ownership.md.
- **4626fff (WIP)**: test_knowledge_f6_fallback.py gains a `genocchi-8` case (`fn:value:sympy`, raise planted in
  `genocchi.eval`). **Open:** its acos-float and asin-float-out cases now fail (4 failures: counted and loud for each).
  Neither `f6:unit_interval:float` nor `fn:rust:unit_interval` counts. Find where those Float queries go now: the Python
  template on the kept path, Rust's `unit_interval` (Float through `_mpf_`, fn_tpl.rs), or neither. Fix it in the code or
  the test, and name the test edit in the report. The other 71 tests in f6_fallback, value_units, wire and rows pass.

## Measured (orion, ~/sa-rust-ids-work/sa-port-212/)
- **Base probe, complete:** `probe/base` (15 workloads, run from the worktree `base-tree` at 80665b5 with base.so e1fcf0f6…).
  `python3 fnsumm.py probe/base` gives functions.py's per-query calls per workload: dev 46 (`_unary` template 31, build 15),
  f6 215 (template 86, build 31, `nary` 48 and its build 32, `units` 18), opaque 75 (52, 23), value 986 (template 318,
  build 309, `_value_units` 309, `half` 50), zero 6 (5, 1); every other workload 0. dev-seed1 equals dev; fuzz-seed1 is 0.
  The brief's claims hold, plus opaque and zero. Base fallback counts are in ~/sa-rust-ids-work/sa-port-210/fb.txt (S2 bar).
  fbcounts.py here adds the `fn:` and `ad:cbm_noid` prefixes.
- **Candidate probe on 6829d06, f6 and value only:** `probe/c1`. functions.py has 0 per-query calls on both. `_unary`
  and `nary` are gone from `registry:python` (f6: `_load` 54, `constant_units` 4, `symbol_units` 7; value: `_load` 29,
  `constant_units` 150, `symbol_units` 1). Counts: f6 `fn:rust:unary` 75, `nary` 47, `unit_interval` 18; value `unary`
  309, `genocchi_half` 50, `fn:value:sympy` 264, `fn:value_units` 236. Neither workload hits a `fn:python:*` fallback.
- **Quick live check (q1/summary.txt):** f6 and value MATCH, Rust against Python. Every plant fired and was caught (DIFFER):
  f6 `fn-nary-drop-last` 47, `fn-unary-drop-last` 75, `fn-unary-shift` 33, `fn-unit-interval-flip` 18; value
  `fn-genocchi-half-flip` 50, `fn-unary-drop-last` 309, `fn-value-drop` 236. The `dispatch-slotted-off` control MATCHes on f6.

## Next
1. Fix the Float cases (above). Add a direct test for any guard no workload reaches: the Float branch, the nary arity none,
   the `fn:python:*` fallbacks. Called through `K.DISPATCH[0]` / `registry.clauses_for` with no query on the stack, a
   template isn't kept, so it reaches fn_tpl.rs. Compare against `TemplateRegistry.clauses_for(K.registry, expr)`.
2. Candidate probe on the final build, all 15 workloads: `probe/runall.sh TREE OUT` with todo.txt's first word changed to
   cand. Run it from a worktree of the tested SHA with its .so copied in, never from the clone while you build. Then
   `fnsumm.py`.
3. Bar on pareto1, as in ~/sa-rust-ids-work/sa-port-208/run-bar-s2.sh: PLANTS = the six `fn-*` plants, WLS = the 11, TESTS =
   that list, SUITE_PLANTS=zero, BASE = ~/sp19/sa-rust-ids-work/sa-port-208/bar-s2/suite. Week was 89% at 14:29; the 90%
   range in STATUS was 16:04-18:09, and the bar takes about 1h30m.
4. Count: functions.py has 0 per-query calls on f6 and value. It counts if the planner rules `fn:value:sympy` a named
   callback (the same kind as special.py's multigamma value). `_value_units` was "not port (offline)" under the 6f ruling,
   but it runs per query (value 309), so it is ported here: that is the question for the planner, with fire counts.
