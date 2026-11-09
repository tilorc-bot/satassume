# 6i, part (b): functions' slotted `_unary`, `nary` and `_in_unit_interval_units` on Rust (issue 323)

sa-port-212 wrote the port (6829d06). sa-port-214 fixed the test cases, added the direct guard tests, ran the probe and the bar,
and landed it.

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
- Base: rust-slice 80665b5. Tested: **fe250ff** (6829d06 + 4626fff + fe250ff). **Not landed:** the week reading was 90%
  at 15:53 (`agent usage`), and the architect said at ~15:58: no landing until the reset (10 Nov 04:00 UTC). This goes on the
  closing list. Branch port/6i-b is pushed.
- Incoming diff: **empty** at 15:53. origin/rust-slice was still 80665b5, which is an ancestor of fe250ff. This was checked by
  `git merge-base`, not by `bar.sh land`.

## The bar (pareto1, `~/sp19/sa-rust-ids-work/sa-port-214/bar-6ib` on fe250ff): RUNNING at handoff
Started 15:18Z under a shared lease ('sa-port-214 6i(b) bar on fe250ff'), with machine run pid 1811453 on orion. The end
marker is **pareto1:/home/tilo/sp19/sa-rust-ids-work/sa-port-214/bar-6ib/end.txt**. The wrapper is
`~/sp19/sa-rust-ids-work/sa-port-214/run-bar-6ib.sh` (orion copy `~/sa-rust-ids-work/sa-port-214/run-bar-6ib.sh`).
- Base suite rows: `~/sp19/sa-rust-ids-work/sa-port-208/bar-s2/suite`.
- PLANTS: the six `fn-*`. WLS: the 11. SUITE_PLANTS: `zero`. TESTS: sa-port-208's list plus test_knowledge_fn_direct.py
  and test_knowledge_rows.py. DIRECT: `relations_direct.py 300 0` and `dispatch_direct.py`. N: 6.

Read from the bar at 15:59Z:
- phases build, tests, suite, live and plants exited 0;
- tests: **811 passed, 4 skipped**;
- DIRECT exited 0: dispatch_direct BAD 0, with `registry:rust:_unary.<locals>.template` 6 and `nary` 1 reached.

Still running: extra (the 11 WLS), suiteplants and sum. **The bar's five items are not yet read:** the suite by id, MATCH,
plants, handler multiset with ctx:caught, and fallbacks with kept shares. The successor reads them from sum.txt and fills in
the sections below, in port-6i-a.md's form.

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
  passes: value 264, other workloads 0. The bar's per-workload counts are for the successor to read.
- The TSV row for `_value_units` should read "offline table plus per-query callback on a miss" (planner). Strictly, today it
  is "callback on every call; the table is unread". **Not yet edited in the TSV:** the successor does it with the count.

## Module count
functions.py has 0 per-query Python on all 15 workloads. With `fn:value:sympy` ruled a named callback, it **counts**, with
this footnote: "`fn:value:sympy`: `expr.func(c)` on Rust's value-at-integer facts, value 264 (2 passes), 0 elsewhere; the
offline table covers it and is unread". The total is the current STATUS count plus one. The successor states it against
STATUS once the bar is read.

## Not run / open at handoff
- The bar's extra, suiteplants and sum phases (running). Every bar item is therefore unread, and nothing here is quoted as
  met.
- `bar.sh land` and the landing: held by the week rule.
- Moved to "before any backend PR", none quoted as met:
  - the mutant 2, 5, 6, 7, 9 rerun and mutlive's control;
  - the boundary rescore and suite column;
  - the final drop score and its lost rows;
  - the suite split with Python's counter;
  - `order:_rows`' evidence (not caught meanwhile);
  - the `_forms` guard test;
  - history and seed reruns (the probe ran dev-seed1 and fuzz-seed1);
  - forced moves;
  - the native path;
  - timing.
- Not re-shown: a `ctx:caught` firing on a planted raise. Rust-side handler zeros are void at the ported
  `_build_context`/verdict sites until the harness session's handler plant lands.
- The dispatch_direct.py shared-cache question (above).

Other notes, carried:
- S's standing: S's gate is met except for the 46 named stub failures, one cause.
- The `_n_conflicts` view in rust_plugin.py is a test-plugin shim, not a port (64 tests).
- `tests/test_relations.py::test_equality_sharing_is_needed_and_works` is unedited and still named needs-internals.
- `tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` is the known id()-reuse
  failure (a28c548), unedited.
- **Speed not measured.**
