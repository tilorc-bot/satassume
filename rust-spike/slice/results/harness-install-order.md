# Harness: live.py installs the backend before any workload builds its engine (issue 323)

sa-port-206, branch harness/install-order from rust-slice c3d0999; continued by sa-port-209 (rebased on 80665b5,
plus the planner's Q2 handler plant, d77d3db); landed db7130a by sa-port-218 (10 Nov). The planner's count-audit ruling (~12:30 9 Nov), item 1
only: a harness-only change. Item 2, install() refreshing an engine built before it or refusing loudly, is owed to state
part 3 and isn't touched here (no change under satassume/ or solver_rs/).

## The fix

`live.py` called `load(args.wl)` (c3d0999 :332) before `knowledge_live.from_env()` (:363) and `backend.install()`
(:368, `--check plain`). `scope_wl.queries()` runs its `install()`, which does
`sympy_api.default_engine().extensions = _default` and so builds the default engine. That engine took Python's
`with_closed_units(registry.clauses_for)` (engine.py:1330-1341) before knowledge_live bound `registry.clauses_for` to
Rust's `Dispatch.clauses_for` (knowledge_live.py:221), and kept it for the whole run, on `--check entry` (the bar's mode)
as on `--check plain`. The fix moves `pairs = load(args.wl)` to after the last install (the `engine.Solver = ... = cls`
block), on both modes, with a comment saying why. bar.sh and the helpers don't repeat the order: bar.sh only calls
live.py; registry_count.py and memo_trace.py install before they load; p1_fresh.sh's `live.load` only counts queries.

The order has been the same at every landing since the scope step: `load` before the first `from_env()` at 803d073,
1401d1f, 6526445, b838d3f, a2dc947, 4215655, 2742b66 and c3d0999 (323/354, 326/357, 332/363), and scope_wl's
`install()` builds the default engine at each.

**Which workloads build an engine while they load** (probe `loadprobe.py`: wraps `Engine.__init__`, then `live.load(WL)`,
each in a fresh process): only **scope** (1 engine, the default one, from scope_wl.py:32). dev, fuzz, ground, port, lra,
zero, cert, budget, f6, rootof, core, opaque, wiring, transfer:1:20 and transfer2:1:20 build none and bump no epoch.
**loop** (4 epoch bumps) and **value** (2) register functions while they load but build no engine. After the fix their
registrations come after `knowledge_live.from_env()` instead of before; Dispatch holds the shared `epoch.EPOCH` list, so
it sees them either way. Their outputs show it (below). No workload needs its engine built first.

## The probe: clauses_for on converted queries

audit.py (sa-port-203's module-wide sys.monitoring probe, copied with one change: `AUDIT_LIVE` names the live.py to run, so
c3d0999's live.py can be the control), scope on Rust, sa-port-203's 15 target files, PYTHONHASHSEED=0. Tree:
`~/dev/sa-port-19/satassume`, .so `rust-spike/slice/sa_solver.so` sha256 9aa3e190…, both recorded by audit.py.

| row (converted queries) | old order, plain | new, plain | old, entry | new, entry | twopass.py pass 1 / 2 |
|---|---|---|---|---|---|
| registry.py `clauses_for` (:226) | 518 | **0** | 518 | **0** | 0 / 0 |
| relations.py `with_closed_units.<locals>.clauses` (:426) | 518 | **0** | 518 | **0** | — |
| registry.py `_covers` (:123) | 132 | 22 | 132 | 22 | 22 / 0 |
| `_covers` genexpr (:129) | 30 | 5 | 30 | 5 | — |
| registry.py `_load` (:141) | 6 | 1 | 6 | 1 | 1 / 0 |
| `templates_for` (:194), `_split` (:265), `_redefines` (:62) | 28, 53, 2+2 | 0 | same | 0 | — |
| `__init__.py _applied_to_nan` (:162) | 28 | 0 | 28 | 0 | — |
| import: `default_specs` (:435), `with_closed_units` (:423) | 1, 1 | 0 | 1, 1 | 0 | — |

The old-order column reproduces sa-port-203's numbers exactly (518; `_covers` 132+30; `_split` 53; `templates_for` 28;
`_load` 6; `_redefines` 2+2; `_applied_to_nan` 28), so the counter is shown to fire where Python's path runs; it isn't a
false zero. These 12 rows are the whole difference between old and new (`audit/rowdiff-plain.txt`, both modes). What's left
on new is the registry's lazy first loads, which equal twopass.py's pass 1 (`_covers` 22, `_load` 1). No Python
`clauses_for` runs on a converted query.

## Rerun on the corrected order

`--check entry`, as bar.sh's extra phase runs it (Python, Rust with `--handlers`, livecmp.py), orion, same tree and .so:

| workload | old order (c3d0999) | new order (2b5c763) | Python jsonl old vs new | Rust jsonl old vs new |
|---|---|---|---|---|
| scope (169 q) | MATCH 12e06b0586faee40 | **MATCH 12e06b0586faee40** | byte-identical | byte-identical |
| loop (420 q) | MATCH 09238b2537e54383 | **MATCH 09238b2537e54383** | byte-identical | byte-identical |
| value (3,742 q) | MATCH 3ce3797a267d71a6 | **MATCH 3ce3797a267d71a6** | byte-identical | byte-identical |

All diffs 0 (answer, msg, session_count, end, stream, lra, stats), Rust made 0 Python solvers, reentry 0. So Rust's
`Dispatch.clauses_for` path through `with_closed_units` gives scope the same answers and the same state as Python's did.
The Python (reference) side is unchanged byte for byte. Rust-side quiet handler firings on all three: 0.

**Handler plants can't fire on Rust (a finding, not caused here).** To show the Rust-side handler zero means something,
`SLICE_PLANT_HANDLER` was planted on scope at the new order: on Python, `complete_check` gives 166 rows
(`Engine._build_context`, ValueError planted). On Rust, `complete_check`, `formula`, `verdict` and `assumption_lits` give
0 on scope, and `complete_check` gives 0 on dev too, where this change alters nothing. Since 5c10b, `_build_context`,
`verdict` and `_complete_check` run in Rust (session_live.py:894), so live.py's plants, which patch the Python methods,
are never reached on Rust. live.py's Rust-side handler count is therefore a zero that cannot fire at those sites on any
workload. The suite's handler count is a separate install and isn't affected. Fixed in this landing: see the next section.

## Rust-side handler plant (planner forward-chain-3b ~14:55 9 Nov, Q2), sa-port-209, d77d3db

The ruling puts this in the same landing as the fix: bar item 4 (quiet handler firings) had no live control on Rust at the
ported `_build_context`/complete-check and verdict sites since 5c10b, so **every Rust-side "0 handler rows" from live.py
since 5c10b, up to this run, was void at those sites.** Earlier bars aren't rerun; the head run below covers the current code.

Cause: live.py set `SLICE_PLANT_HANDLER` before `backend.install()`, and session_live's `_install_context` then replaced
the patched rows with context.rs's (keeping the plant as "Python's" in `PY_CONTEXT`). The fix moves the plant to after
every install, next to `load()`. Then context.rs calls the patch by name (its `ctx:cb_patched` route) and relevance.rs calls
`Engine.verdict` by name (`rv:cb_verdict`), so the raise reaches Rust's own handlers, context.rs `build_context`
(engine.py:1906's) and relevance.rs `_consistent`, which write handler_count's rows through `rust_handled`. The Rust-side
plant inside context.rs's complete check already existed (`SLICE_SESSION_PLANT=ctx-check-raise`, plant 221), so no
Rust source changed.

Head run (rebased head, orion, `--check entry`, `~/sa-rust-ids-work/sa-port-209/plant/`): handler rows per plant, Python
against Rust. The rows (site, type, text, query) are identical between backends as sorted lists wherever both are listed.

| plant | site | scope Python | scope Rust | dev Python | dev Rust |
|---|---|---|---|---|---|
| none | — | 0 | 0 | 0 | 0 |
| `complete_check` (live.py) | `Engine._build_context` | 166 | **166** (`ctx:cb_patched` 166, `ctx:caught` 166) | 833 | **833** |
| `assumption_lits` (live.py) | `Engine._build_context` | — | 166 | — | — |
| `verdict` (live.py) | `_consistent` | 0 | 0 | 46 | **46** (`rv:consistent_caught` 46) |
| `ctx-check-raise` (Rust, plant 221) | `Engine._build_context` | n/a | 166 | n/a | 833 |
| `formula` (live.py) | `_consistent` | — | 0 | — | — |

- Scope never reaches `_consistent` (`rv:consistent` 0 unplanted), so its verdict zero is no evidence; dev reaches it 64 times.
- The planted dev runs MATCH Python against Rust (answers_sha 31cd0945c07f02a6, every diff 0).
- `formula` stays void on Rust: its guard raises only when the caller frame is `_consistent`, which is relevance.rs on
  Rust (no Python frame). Not needed for the ruling (the `_consistent` site is covered by `verdict`); left as is.
- `test_live_handler_plant.py` (in the bar's TESTS): the three live.py plants and ctx-check-raise reach Rust's handler with
  rows equal to Python's, and unplanted rows are empty on both, on scope `--limit 12` and five dev queries. On the previous
  live.py (plant before install) it fails 4 of 6, so it guards this order.
- The bar adds `ctx-check-raise` to PLANTS, so its handler rows are recorded on dev, fuzz and all 11 workloads.

## Rebase and short check at the new head (sa-port-209)

Rebased on rust-slice 80665b5 (S2 landed fd367ce, on (iii) part 1 cac82a9), no conflicts; rebuilt on orion. scope MATCH
12e06b0586faee40, every diff 0, Python solvers made by Rust 0. Probe (audit.py, scope, entry): registry `clauses_for` 0 and
`with_closed_units` closure 0 on converted queries, `_covers` 22, `_load` 1: the same as at 2b5c763.

## Bars whose scope MATCH rested on the old order

Every landing since 6g(a) (f65cc68) with scope in its bar. f65cc68 itself predates the scope workload; 5c7 (17442af),
5c8 (3611952) and 5c9a (e0ec542) didn't run scope. In each listed bar the scope comparison ran Python's
`with_closed_units(registry.clauses_for)` on the Rust side too (518 calls per run at c3d0999), so its scope MATCH didn't
exercise Rust's dispatch through that path. The rerun above shows the answers and state are the same on Rust's path at
c3d0999; it doesn't re-run any earlier landing.

| landing (report commit) | report | scope line as written |
|---|---|---|
| 803d073 (step scope) | port-scope.md:35-37 | "Fresh dev, fuzz, loop and scope: answers and state MATCH … The new workload's answers are scope 12e06b0586faee40 (169 q)." |
| 1401d1f (5c6) | port-5c6.md:31-33 | "Fresh dev and fuzz, plus loop and scope: answers and state MATCH … scope 12e06b0586faee40 (169 q)." |
| 6526445 (6d, landed 1e44a7c) | port-6d.md:53-55 | "whole engine Python against Rust: … and scope (169) MATCH, each with its Python control MATCH." |
| 44f4762 (before 5c7, landed bb3df19, rebar after 6d) | port-5c7-tests.md:75-77 | "Fresh dev and fuzz, plus loop, scope and zero: answers and state MATCH … scope 12e06b0586faee40 (169 q), all as 5c6 and 6d" |
| f92a360 (adapters B+C1, landed 4dd2ed9) | port-adapters.md:133-136 | "The eight extra workloads MATCH: … scope 12e06b0586faee40" |
| b838d3f (6g(b)) | port-6g.md:155 | "f6, value, rootof, core, opaque, scope, loop, zero and wiring (new, 6,512): MATCH, each with a Python control." |
| 9c8d981 (adapters C2, landed 29ee93e) | port-adapters.md:301-304 | "The ten extra workloads MATCH, each with a Python control: … scope 12e06b0586faee40" |
| 30f3309 (6g(c1)) | port-6g.md:260 | "f6, value, rootof, core (1,636), opaque, scope, loop, zero, wiring and cert: MATCH, each with a Python control." |
| a2dc947 (6g(c2)+Element._new stack, landed f1e4a74) | port-elemnew.md:63-65 | "The 11 workloads MATCH with controls" |
| 2553a68 (5c9b) | port-5c9b.md:40-42 | "Fresh dev and fuzz, plus loop, zero, cert and scope: answers and state MATCH … scope 12e06b0586faee40 (169 q)." |
| 2d12e81 (5c9c) | port-5c9c.md:52-54 | same wording as 5c9b, scope 12e06b0586faee40 (169 q) |
| 67d108d (5c10a) | port-5c10a.md:50-52 | same wording, scope 12e06b0586faee40 (169 q) |
| 4215655 (5c10b) | port-5c10b.md:43-45 | same wording, scope 12e06b0586faee40 (169 q) |
| eac4537 (6g(c3)-(c5)) | port-6g.md:418-421 | "All 11 WLS MATCH with controls: … scope 169 … The lra-on path MATCH (with_closed_units, …" |
| b384ec1 (5c10c; report 2f2dad7) | port-5c10c.md:53-56 | "Fresh dev and fuzz, plus loop, zero, cert and scope: answers and state MATCH … scope 12e06b0586faee40 (169 q), all equal to 5c10b's." |
| 9529850 (5c10d; report efd33cc) | port-5c10d.md:58-60 | "Fresh dev and fuzz, plus loop, zero, cert, scope and budget: answers and state MATCH, stats_diff 0 everywhere" |
| cec872d (6g(c6), landed in 2742b66) | port-6g.md:641-644 | "All 11 WLS MATCH with controls: … scope 169 … The lra-on path MATCH, with with-closed-skip …" |
| 2742b66 (6g(c6)-(c9)) | port-6g.md:775-778 | "All 11 WLS MATCH with controls: … scope 169 …" |
| a8a4bae (state part 1) | port-state-memoized.md:53-56 | "Fresh dev and fuzz, plus loop, zero, cert, scope and budget: answers and state MATCH, lra_diff 0 and stats_diff 0 everywhere" |
| c3d0999 (state part 2 (i)) | port-state-relations.md:44 | "loop, zero, cert, scope and budget all MATCH." |
| 693fef9 (6i(a), tested b11b5a2) | port-6i-a.md:55 | "All 11 extra workloads MATCH, Rust against Python." (added by sa-port-209) |
| 9e10f0d (state part 2 (ii), tested 997a54f) | port-state-relations.md:207 | "loop, zero, cert, scope and budget all MATCH." (added by sa-port-209) |

After those, (iii) part 1 (cac82a9, tested ce1092c, port-state-relations.md:283) and S2 (fd367ce, tested bb92b07,
port-s2.md:150) still ran scope with the old live.py, but ce1092c's session_live install rewraps a default engine built
before it on Rust's `with_closed_units`, so their scope runs compared Rust's path product-side (518 -> 0, sa-port-206's
probe). They rested on that rewrap rather than on Python's path. From this landing on, no bar workload builds its engine
before the install, so no bar exercises that rewrap: it needs its own "build first, then install" test, owed to state part 3
with item 2 of the install-order ruling.

Two rows name the path scope didn't take on Rust. 6g(c3)-(c5) (port-6g.md:421-422) and 6g(c6) (:644-645) say
"lra-on path MATCH (with_closed_units, …), with with-closed-skip caught on dev, fuzz, cert, core, f6, opaque and wiring".
scope isn't in that list, which fits: on scope `with_closed_units` was Python's closure, so a plant in Rust's couldn't
reach it. The other workloads weren't affected, since none of them builds an engine while it loads.

## The bar and the landing

**LANDED db7130a** on rust-slice (sa-port-218, 2026-11-10T04:32:48Z, `PUSH=1 bar.sh land d77d3db`, log
`~/sa-rust-ids-work/sa-port-218/land.txt` on orion), fast-forward 80665b5..db7130a. Tested source **d77d3db**; landed
source db7130a differs from it only in results/ (this file and HANDOFF-sa-port-209.md); the push guard listed nothing.
**Incoming diff: empty** (rust-slice was still 80665b5, the base the bar ran on; the rebase was a no-op), so by the
planner's rebasing rule no rerun or short check was needed.

Bar on pareto1, `~/sp19/sa-rust-ids-work/sa-port-209/bar-install-order`, 15:04Z-15:55Z, every phase exit 0 (seed1 not run).
Tested source **d77d3db** (branch head after it changes only results/). .so sha256 5ee060a2…. BASE = S2's bar suite
(`sa-port-208/bar-s2/suite`). PLANTS = the six ad-lra-* plus `ctx-check-raise`; WLS all 11; TESTS = S2's 29 files +
test_live_handler_plant.py; DIRECT relations_direct.py 300 0; N=6.

1. **Suite by id against base:** 6,159 ids, new 0, gone 0, changed outcome 1:
   `test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence` failed -> passed. That's
   the known id()-reuse test (sa-port-185), and it flips back in this bar's suite-plant run (passed -> failed). Passed
   5,992: no firing 5,991, with a firing 1 (`test_ci_stream_reports_only_what_replays`, the named case); failed 126, as base.
   Tests 752 passed, 4 skipped; DIRECT exit 0.
2. **Fresh dev and fuzz:** answers and state MATCH (dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6, every diff 0, Python
   controls MATCH, traced and untraced). All 11 WLS MATCH with Python controls, scope now on the corrected order.
3. **Planted bugs caught:** ad-lra-kind-key and ad-lra-pair-swap DIFFER on dev, fuzz, cert, scope and zero; scope is
   now caught on Rust's own path. ctx-check-raise DIFFERs on all 13 workloads. ad-lra-not-expr fires only on scope (4),
   void there as before; it fired 0 in the suite.
4. **Quiet handler firings:** suite 39 rows in 2 tests, multiset equal to base (`_consistent` AttributeError 34+4 in
   test_ci_stream_reports_only_what_replays; `_build_context` "Already mutably borrowed" 1 in test_protocol_on_fuzz, the
   named cause). Live, unplanted: **0 on all 13 workloads on both backends**, and now with a live control on Rust:
   ctx-check-raise's rows at `Engine._build_context` are dev 833, fuzz 2,980, budget 16, cert 61, core 300, f6 6, loop 244,
   opaque 31, rootof 368, scope 166, value 636, wiring 5,004, zero 718 (each equal to the plant's fired count).
5. **Known differences in answers or read state:** none.

Kept shares: equal to base on every workload (out-of-scope dev 24/1,985 (1.21%), 0 elsewhere; refused f6 13, opaque 7,
value 15, wiring 1, as base). Fallbacks (sa-port-204's fbcounts.py, `~/sp19/sa-rust-ids-work/sa-port-209/fb.txt` against
`fb-base.txt` from S2's bar): equal to base on 12 workloads. **scope changes, as this fix should make it:**
registry:python 26 -> 33 (`_load` 27, `constant_units` 2, `symbol_units` 4) and rows:python 0 -> 64 (`Integer` 32,
`const_value` 32). scope now runs Rust's Dispatch, so its fallbacks to Python show where before they were hidden in
Python's own path. Every template named already falls back on other workloads (budget: symbol_units 450, Integer and
const_value 40 each), and the owners are as in port-6i-a.md. ad:cbm_noid 0 everywhere; ad:lra_not_expr scope 4 (the
native not-an-Expr path, as before).

Tested SHA d77d3db; landed SHA db7130a; incoming diff (80665b5..origin/rust-slice at landing) empty.

## Not run here

Suite plants beyond the bar's; seed1; mutant reruns; timing; any rerun of an earlier landing's bar on its own source. Item 2
of the install-order ruling (install() refreshing or refusing loudly) and the build-first-then-install test of (iii) part
1's rewrap: owed to state part 3. The `formula` live.py plant stays void on Rust (see above).

## Outputs

`~/sa-rust-ids-work/sa-port-206/` on orion: `old/` and `new/` (the reruns, with head.txt and tree.txt), `audit/`
(the probe's JSON, `rowdiff-plain.txt`), `probe/load.txt` (which workloads build an engine), `plant/` (handler plants),
`audit.py`, `audit_run.sh`, `runwl.sh`, `oldlive/live.py` (c3d0999's, for the control).

sa-port-209: `~/sa-rust-ids-work/sa-port-209/` on orion (`new/` scope check, `audit/new-entry.json` probe, `plant/` the
Q2 head run, `plant.sh`, `runwl.sh`, `audit_run.sh`, `bar.launch`); pareto1 `~/sp19/sa-rust-ids-work/sa-port-209/`
(`bar-install-order/`, `fb.txt`, `fb-base.txt`).
