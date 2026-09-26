# Agent report: plan for phase 3 of refine-from-identities

- **Date:** 2026-09-25
- **Status:** plan. Phase 2 is finished (`2026-09-25-refine-identities-phase-2-results.md`). Branch `refine-identities` at f83f195 has phase 2 plus the satassume speed-up from `main` (b3d429b).
- **Scope:** satrefine only: `satrefine/handlers_identities/`, `satrefine/backend.py`, `tools/`, `tests/refine_identities/`. satassume is out of scope. What refine needs from satassume is listed in section 4 and goes to satassume issues.
- **Read this if:** you are running or joining phase 3. Also read `2026-09-24-read-before-running-agents-how-work-gets-lost.md` before you start agents.

Phase 3 has four tracks: speed first (A), then correctness (B), the switch to satassume-only (C), and cleanup (D). All numbers come from measurements taken on 2026-09-25 at f83f195. The raw notes are in the phase-3 input files named in section 7.

## 1. Where the time goes now

The target configuration is `SATREFINE_BACKEND=satassume`: every query goes to satassume, and SymPy's `ask` is kept only for matrices (section 4). Speed work is measured there. The default backend, `combined`, still sends 1,755 battery queries to SymPy. That is 40% of its time, and in 90% of those seconds SymPy answers None anyway. That fallback is going away, so it isn't optimised here.

Absolute times below are pinned to one fast core (`taskset -c 0`) and run one at a time.

| Workload | satassume backend | combined (reference) |
|---|---|---|
| battery `refine`, 1,736 cases | **14.8 s** | 27.8 s |
| differential, seed 2, 1,500 cases | 19.6 s of refine | |
| fixpoint, power_exp_log alone | 64.7 s | |
| test suite, 4 workers | | 128 s wall; about half of its CPU goes to generated-table and fixpoint tests |

Battery breakdown with the satassume backend (instrumented, 100% = 18.6 s):

| Part | Share | Note |
|---|---|---|
| satassume `ask` | 32% | fixed for phase 3; the per-call memo hits 53% |
| SymPy's own `Pow._eval_refine` / `exp._eval_refine` | **19%** | they call SymPy's `ask` directly, past the backend and memo; 2,058 calls, 179 fire |
| case splits | 16% | 50 of 255 succeed; the failed ones cost 14% |
| nodes refined again in another engine context | 12% | 21% of node steps; the context (a handler switched off, a split) is part of the cache key |
| matching | 10% | 148,120 calls; 48% fail on the head at the top |
| `subst` (xreplace plus auto-evaluation) | 10% | |
| pattern analysis redone on every match | 6% | `_is_unit_coefficient_form`, `Expr.cancel` |
| `stated_bounds`, `provable`, dispatcher, the rest | about 15% | |

- **Refusals** (inputs that stay unchanged) take 48% of battery time and 75% of differential time. Declining is as costly as rewriting.
- **Slowest cases:** the 50 slowest cases take 39% of the battery. The worst is `(x**a)**b` under `Q.even(a) & Q.imaginary(x)`: 0.9 s, 84% of it in six case splits, five of which fail.
- **The fixpoint has a different profile:** case splits take 60% of it. 695 identical splits repeat, and `endpoint_split` runs 2,560 times without ever succeeding.

## 2. Track A (first): satrefine speed

**Goal:**
- battery `refine` with the satassume backend at 14.8 s → **≤ 9 s**;
- differential and fixpoint at least 25% faster;
- the suite's wall time roughly halved.

Every change must keep the battery and differential outputs identical, or explain each difference in its commit. The candidates are ranked by measured gain. The first three were prototyped end to end, with all 1,736 outputs compared.

| # | Change | Measured gain | Notes |
|---|---|---|---|
| A1 | Send the `ask` calls from `Pow`/`exp._eval_refine` through the backend and the per-call memo. Use satrefine's own copy of those two methods, so SymPy isn't changed. | **−19%** battery | 0 output changes. Must catch `ValueError` (9 fuzz inputs with inconsistent assumptions). The alternative, skipping them and leaving it to the handlers, gives −23% but turns 4 differential results into worse forms (`-n**k` → `(-n)**k`). Don't take it without fixing those. |
| A2 | Analyse each pattern once, when the row is compiled, not on every match. | −7.6% | 0 output changes |
| A3 | Test the head function before matching. | −2% | 0 output changes; small, but free |
| | A1 + A2 + A3 together | **−26%** (11.0 s) | differential −12%, fixpoint −13%; same fixpoint rules |
| A4 | Failed case splits: a cheap pre-test that tells whether a split can succeed, and a cache of identical splits within a call and within a fixpoint round. Drop `endpoint_split` from the fixpoint if it never succeeds. | up to 14% battery, up to 59% fixpoint (the cache alone 14%) | upper bound; must not change which splits succeed |
| A5 | Key the node cache on engine state only when that state affected the result, for example when the handler switched off during a candidate check was actually consulted. | up to 12% (differential 13%) | needs a correctness argument: a result may be reused only when the switched-off handler could not have fired |
| A6 | Cheaper `n*unit` ratio; skip `subst` on hypotheses already known True; memoize `stated_bounds` per call. | about 4%, part of 10%, up to 3.6% | |
| A7 | Suite: build the generated tables and the `_specialize` fixture once per session, and share them across workers; move full fixpoint runs to an opt-in marker, with a smaller smoke test in the default run. | suite wall about −50% (estimate) | the gates keep a full fixpoint check |

**Not worth doing:** a cache of `ask` answers shared across calls gains about 0 with the satassume backend, and it brings back the order-dependence risk raised in issue #8.

**Rules for this track:**
- **A/B timing:** pinned (`taskset -c <fast cpu>`; fast CPUs are 0, 1, 10 and 11; 2–5 are slow and 6–9 medium, per `cpu_capacity`), interleaved (reference, candidate, reference, candidate), best of 2 or more, at a 1-minute load under about 8.
- **Report:** gains are given on the battery with the satassume backend, and on one differential seed.
- **Keep or drop:** keep a change only if it shows at least 3%, or if it simplifies the code at no cost. If candidates stack less than their individual gains suggest, measure them together again.
- **Tooling:** `satrefine/tools/refine_fuzz.py` currently forces the combined backend, so the differential ignores `SATREFINE_BACKEND`. Fix that first, since track A and track C both need differential runs with the satassume backend.

## 3. Track B: correctness

All confirmed bugs are in issue #10.

| Bug | What | Status |
|---|---|---|
| B9 | Refine can recurse without bound when the engine's own facts contradict each other; `RecursionError` with the SymPy fallback off. | **In progress on `ri/termination`:** termination guaranteed for any `ask` answers, contradiction handling, and a fuzz test with adversarial `ask` answers. |
| B1–B7 | `_from_bounds` treats a stated bound as proof of finiteness: `Q.gt(x, 1)` proves `Q.real`/`Q.positive`/`Q.nonzero` although `x = oo` is allowed. Seven wrong results (Piecewise, KroneckerDelta, `sign(exp(-x))`, `log(x**n)`, `acsch(csch(x))`, `RisingFactorial`). | Next. A bound proves only `extended_real` and the `extended_*` signs. `real` and the finite signs need a finite bound on the relevant side. Recheck Eq/Ne/Lt decided from bounds the same way. |
| B8 | `acot`/`acoth` of a rewritten `-z` is wrong at `z = 0`; SymPy's auto-evaluation pulls out the sign. | Guard on the refine side (build the result unevaluated unless the argument is known nonzero), and report it to SymPy. |

After B1–B9, extend the fuzzers so this kind of bug is found without being looked for:
- `Q.infinite`/`Q.finite` and relations with infinite bounds in `satrefine/tools/refine_fuzz.py`;
- `Piecewise`, which has no fuzz or differential coverage and isn't in the battery;
- the inverse pairs `acot(cot)`, `acoth(coth)`, `asech(sech)` and `acsch(csch)`, which are never generated;
- matrices (`--matrices`) in the gates.

Also check, and document or fix, two borderline cases where the input has no value at the point:
- live mode: `Abs(x*y)` under `Q.zero(y) & Q.infinite(x)` → `0`;
- `log(1/x)` under `Q.extended_positive(x)` → `-log(x)`, which differs from SymPy's `log(0) = zoo` convention at `x = oo`.

## 4. Track C: satassume-only, with SymPy for matrices

**Milestone:** the combined backend asks SymPy only for matrix queries. A one-line change to `_combined_ask` did this on 2026-09-25 and was gated. Measured against the current baseline:
- the battery loses 1 case;
- the differential fires about 4% less;
- there was 1 crash per run: B9.

**Prerequisites:**
1. B9 fixed (track B).
2. satassume interprets relations with `pi` and other non-rational bounds, or at least doesn't drop the whole query. That is item 3 of satassume issue #7. The battery case it costs is `sqrt(asin(sin(x))**2)` with a `pi/2` bound. The differential cases are listed by the gates once refine_fuzz honours the backend.
3. The differential with the satassume backend shows no crash and no new unsound result. Every lost rewrite is either traced to a satassume gap and filed on #7, or accepted with a reason.

Matrix predicates stay on SymPy until satassume models them. That is out of scope here.

## 5. Track D: gap with v3, and cleanup

Of the cases where the battery differs from v3 (13 misses, 41 other forms, same in both modes):
- **40 are as good or better on our side,** mostly hyperbolic evaluations. Record them in the scoreboard as accepted, so they stop looking like open work.
- **5 are cases where v3 is questionable**, for example `binomial(n, n)` and `rf(x, k)` at infinity, and `sign(x**2*conjugate(x))`, which should be `sign(x)`. Record them as accepted.
- **6 are engine limits:**
  - `conjugate(x)` isn't matched as a power with exponent 1 (`x**3*conjugate(x)` ×2, `x*conjugate(x)**2`);
  - `X[i, j]` under diagonal or symmetric needs an index order that `ask` can't decide (×3).
  Fix the first. The second waits for matrix support.
- **3 need new rows:** `log(x**-2)` and `log(x**n)` for even `n` give `e*log(Abs(b))`. `(-1)**(...)` is low value.

**Engine cleanup** (1,434 code lines in the engine, against 478 in the families):
- **Remove dead code:** `_simple.refine_floor`, `_specialize.write_family`, the dispatcher path for non-SymPy results, and 7 unused imports.
- **Merge duplicates:** `default_measure`/`node_measure`; three copies of the relation predicate list; the table filters in `_specialize` and `_stages`.
- **Re-implemented bound parsing:** `stated_bounds` re-implements v3's bound parsing. Rewrite it on top of the relation decider, together with the B1–B7 fix.
- **Coverage:** `_stages` has only 31% test coverage because the fixpoint runs only from the tool. Give it a small test.

Target: fewer engine lines at the end of phase 3 than at its start, with no behaviour change beyond tracks B and C.

### Refactor (first part of track D)

Issue #13 has the design: separate general algorithms from the rule families, online code from offline code (generation, tools, benchmarks), and current-state code (SymPy workarounds, matrices, backend routing) from the rest, and move satrefine's tools into `satrefine/`. Steps 1–7 of the issue are in phase 3, before the other track D items. They start when A6+A7, the fuzz extensions and the default switch are merged. Steps 8–9 (explicit state, renames) come after phase 3.

Steps 1–2 are done on `ri/refactor` (report `2026-09-26-phase3-refactor-1-report.md`): satrefine's tools are in `satrefine/tools/` (run as `python -m satrefine.tools.<name>`; `tools/refine_*` are shims for phase 3), the engine in `satrefine/identities/` and the generation in `satrefine/build/`.

## 6. Order, agents and gates

1. **Now:** B9 (`ri/termination`); see "Finishing B9" below.
2. **Track A**, in three branches one after another, since all touch the dispatcher and matcher:
   - A0: the refine_fuzz backend fix, plus A1–A3;
   - A4 + A5;
   - A6 + A7.
   B1–B8 can run in parallel with the A0 branch, since the files hardly overlap: `_engine.py`'s `_from_bounds` and `_simple.py` for B, against the dispatcher and matching for A. The coordinator merges, and each branch is gated against the latest baseline.
3. **Then** the fuzz extensions and track D. Track C when satassume item 3 lands.
4. **Finally**, a results report as for phase 2, and archiving of the step reports.

**Gates:** `satrefine/tools/refine_gates.sh` with `JOBS=9 SLOTS=11 SUITE_WORKERS=4`, against the newest baseline under `.claude/gates/`. They also get:
- a differential with the satassume backend, once refine_fuzz honours it;
- the adversarial-`ask` fuzz from B9 in the suite.

**Agents:** Opus, one fresh agent per assignment, with a handoff note when context reaches about 300k tokens. No tool call over about 4 minutes. Pinned timings for anything that decides a change.

### Finishing B9

An agent started the fix on 2026-09-25, on branch `ri/termination`, in worktree `.claude/worktrees/ri-termination`, created from f83f195. Its task was:
- **Root cause:** find it and verify it; don't take the diagnosis in #10 on trust.
- **Termination:** make refine terminate for any `ask` answers, with no `RecursionError`, and argue the guarantee in the docstrings.
- **Contradictions:** handle the engine proving both a fact and its negation.
- **Tests:** add
  - the reproduction, in both modes;
  - a fuzz test against adversarial `ask` answers (always None, always True, random, contradictory), quick in the suite, with a larger opt-in mode;
  - a direct test of the nesting guard.
- **Differential:** run it with the satassume backend (seeds 2, 3, 7, both modes).
- **Gates:** gate against `.claude/gates/satperf-f83f195`, into `.claude/gates/termination-<sha>`.

**If the branch has `.phase2-done` in its worktree, the agent finished:**
1. Read its commits, `git log f83f195..ri/termination`, and the report it wrote under `agent-reports/`, if any.
2. **Check the fix itself,** not only the tests: the reproduction must terminate. Do not accept a raised recursion limit as the fix.

   ```
   PYTHONHASHSEED=0 PYTHONPATH=.:/home/tilo/orion/sympy SATREFINE_HANDLERS=handlers_identities SATREFINE_BACKEND=satassume
   refine(factorial(log(k)), Q.negative(k) & Q.gt(k, pi/2))
   ```

   It must terminate quickly in both `SATREFINE_IDENTITIES` modes.
3. **Check the gates** in `.claude/gates/termination-<sha>/summary.txt` against the baseline:
   - no new wrong results, crashes or lost rewrites;
   - no new differential unsound or crash cases;
   - the suite fails only on `needs/` tests.

   If the gate run is missing or stale, run it:

   ```
   JOBS=9 SLOTS=11 SUITE_WORKERS=4 nohup satrefine/tools/refine_gates.sh .claude/gates/termination-<sha> .claude/gates/satperf-f83f195 > ....log 2>&1 &
   ```

4. **If both checks pass, merge:** `git merge --no-ff ri/termination` into `refine-identities`, with the trailers, push, remove the worktree, and delete the branch. The gate run becomes the new baseline for track A.
5. **If the agent reported refine bugs** from the satassume-backend differential and didn't fix them, add them to issue #10.

**If there is no `.phase2-done`:** the agent was interrupted, for example by a cleared session.
1. Check whether anything is still running, with `pgrep -af ri-termination`.
2. If nothing is, start a fresh agent on the same worktree:
   - it continues from the branch's commits and `git status`;
   - it has the task above, and follows the rules in `/home/tilo/fable-rewrite/.claude/phase3/agent-rules.md`;
   - it first writes down what is already done.

   Don't discard uncommitted work in the worktree without reading it.

## 6a. Decisions taken on 2026-09-25 (evening)

- **Track C:** the satassume side is asked, on issue #7, to schedule relations with non-rational bounds (`pi`, floats, `oo`). Phase 3 does C once that lands. Issue #7 was rewritten to its current state.
- **B8 upstream:** the user files the SymPy issue from the draft in `2026-09-25-phase3-bounds-report.md`, section 7.
- **Long-term target:** not decided; phase 3 finishes as planned.
- **Default refine:** switch to `handlers_identities` in phase 3 and fix or update the tests that then fail (branch `ri/default`).
- **Merging into `main`** (coordinator's recommendation, not yet the user's decision): not during phase 3. `main`'s CI runs `pytest tests` in one process against released SymPy, while refine needs the SymPy branch in `orion/sympy` and one process per test directory. Revisit at the end of phase 3.

## 7. Out of scope, and decisions for the user

**Out of scope:**
- satassume's internals, including the review items in #8;
- Gröbner bases;
- deriving trig and hyperbolic through definitions (rejected in phase 2);
- more row reduction for its own sake.

**Decisions for the user, not blocking phase 3:**
- **Make `handlers_identities` the default refine?** It's selectable today. Switching makes 31 more `tests/refine` tests fail (3 → 34), a mix of real behaviour changes and tests of the old code. Each would need triage.
- **The long-term target.** The repo's documents describe `refine` staying on top of `ask`, with no plan to upstream to SymPy or to replace v3. If either is the goal, it changes what phase 3 should finish with.

**Inputs** (in `/home/tilo/fable-rewrite/.claude/phase3/`, not in git; the agent rules shared by all agents are in `agent-rules.md` there):
- the bug list with reproductions;
- the profile;
- the list of cases where we differ from v3;
- the engine size and coverage notes.

The bug reproductions are copied into issue #10.
