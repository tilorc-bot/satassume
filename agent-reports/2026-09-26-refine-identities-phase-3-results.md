# Agent report: results of phase 3 of refine-from-identities

- **Date:** 2026-09-26
- **Status:** phase 3 is finished apart from track C, which waits on satassume. `refine-identities` is at 905be5d (gated as `.claude/gates/d-ext-merged-905be5d`). The plan was `2026-09-25-refine-identities-phase-3-plan.md`. The step reports are in `archive/`, listed in section 8.
- **Read this if:** you continue this work, review the branch, or decide what comes next (section 7).

## 1. Summary

| | Start of phase 3 (f83f195) | End (905be5d) |
|---|---|---|
| Battery `refine`, satassume backend, pinned | 14.8 s | about 7.0 s (at A6+A7; later steps were checked for no slowdown, not re-timed) |
| Fixpoint `power_exp_log`, pinned | 64.7 s | about 19.6 s |
| Suite wall time, 4 workers | about 113 s (283 s in the gates under load) | 44–53 s pinned (112 s in the gates under load) |
| Default refine package | `handlers` (the original) | `handlers_identities` |
| Known refine bugs (issue #10) | B1–B9 open | B1–B11 fixed |
| Battery vs v3, generated mode: same / other / miss | 1,032 / 41 / 13 | 1,042 / 41 / 3 |
| Battery: fired where v3 is unchanged / wrong / crash | 21 / 0 / 1 | 43 / 0 / 0 |
| Differences from v3 that are not reviewed and accepted | not tracked | 0 (73 + 14 accepted, with reasons, in `satrefine/tools/lib/accepted.py`) |
| Differential, identities fired, seeds 2 / 3 / 7 | 484 / 486 / 456 | 486 / 487 / 456; unsound unchanged, crash 0 |
| Differential with the satassume backend | ran the combined backend by mistake | runs satassume; crash 0 |
| Engine lines (scoreboard count) | 1,434 | 1,793 (online 1,438, offline 355) |

Speed targets (battery ≤ 9 s, differential and fixpoint −25%, suite halved) were met except the differential, which improved by about 25% in total across A1, A4 and A6 but was measured per step (−9%, −6%, −9%); most of its time goes on inputs that stay unchanged.

The engine-size target (fewer lines than at the start) was **not met**; see section 5.

## 2. Track A: speed

All timings pinned to a fast core (0, 1, 10 or 11), interleaved with the reference, best of 2 or more. Outputs were identical in every step (battery and differential records, both identity modes, satassume and combined backends; the fixpoint produced the same rules and byte-identical tables).

| Step | Change | Battery | Other |
|---|---|---|---|
| A1 | `Pow`/`exp._eval_refine` ask through the backend and the per-call memo (satrefine's own copies; SymPy unchanged) | −23% | differential −9% |
| A2 | patterns analysed once, when compiled | A1+A2 −30% | |
| A3 | head test before matching | +0.8%, dropped | |
| A4 | case splits: one shared dummy per symbol, early stop, a pre-test for splits that cannot succeed | −13.5% | fixpoint −54% |
| A5 | node cache keyed on engine state only when consulted | under 3%, reverted (code and argument in e3218da) | |
| A6 | memos of pure functions (`n*unit` ratio, `subst`, `count_ops`, `_distributed`) | −19% | fixpoint −20% |
| A7 | full fixpoint tests opt-in (marker `full`, a gate section of their own), shared specialize fixture | | suite wall −53 to −60% |

## 3. Track B: correctness

| Bug | Fix |
|---|---|
| B9 | Non-termination under contradicting facts (an empty stated interval proved every sign). Refine now terminates whatever `ask` answers: nesting, re-entry and work limits, argued in the driver/guard docstrings; a tripped limit returns the input (strict mode raises). |
| B1–B7 | A stated bound was taken as proof of finiteness. A bound now proves only `extended_real` and the `extended_*` signs; `real` and the finite signs also need infinity ruled out. |
| B8 | `acot`/`acoth` of a rewritten `-z` at z = 0 (SymPy's auto-evaluation). Refine builds such results unevaluated unless the argument is known nonzero. |
| B10 | `acsch(csch(Abs(z)))` fired at infinite z. The row now needs a finite or real z. |
| B11 | `HadamardProduct(X, X)` crashed the matcher, which dropped every copy of a repeated argument (also in `MatMul` scalars, `Max`/`Min`, unevaluated `Add`/`Mul`). |

**Fuzzers.** `refine_fuzz` had forced the combined backend, so every earlier "satassume-only" differential was not one; it now honours `SATREFINE_BACKEND`. The `--ext` family adds `Q.finite`/`Q.infinite`, bounds at infinity, `Piecewise`, `KroneckerDelta` and the inverse pairs, with ±oo and zoo check points and SymPy's conventions at infinity counted separately. It rediscovers B1–B7 without being pointed at them. The gates now also run the satassume differential, the ext and matrix differentials, the termination tests and the full fixpoint.

**Default switch.** `handlers_identities` is the default. The "31 failing tests" from the plan was an artefact: tests importing the old package re-registered its handlers, so counts depended on order (36, 77 or 114); `tests/refine/conftest.py` now forbids that. Of 115 failing tests, 36 tested the old package's internals, 28 were equal or better, 10 had wrong old expectations (e.g. `det(X) -> 1` for orthogonal X), and 33 were regressions; 31 of those are fixed. `tests/refine` has 0 failures.

**Extended reals.** The 14 rewrites the B1–B7 fix had lost (they fired only because x was wrongly assumed finite) fire again: `Abs`, `re`, `im`, `sign`, `conjugate` and the `asinh`/`atanh`/`acoth`/`acosh`/`asech` rows are stated over the extended reals where the identity holds at ±oo. `acsch` (B6) and `log(x**n)` at n = 0 (B5) stay finite-only. The combined backend got a guard against SymPy's `Q.extended_real(sqrt(z))` being True for negative z.

## 4. Track D: gap with v3, refactor

**Gap with v3:** every difference is reviewed. 41 other forms (mostly exact hyperbolic values), 3 misses where v3 is questionable at infinity (`binomial(n, n)`, `binomial(n, n - 1)`, `rf(x, k)`), and 43 cases that fire where v3 does not are accepted with reasons; the scoreboard prints open differences separately (0 now). New: the `conjugate` power match (`x**3*conjugate(x)`), `log(b**e) -> e*log(Abs(b))` for even e.

**Refactor (issue #13, steps 1–7):**

```
satrefine/
  identities/   online: core/ (driver, guard, hooks, match, measure, prove, rewrite, spec, split),
                rules/ (families as specs), generated/, compat/ (SymPy workarounds, matrices,
                backend routing, vendored dispatcher), config.py
  build/        offline: specialisation, fixpoint, verification, rendering
  tools/        offline: lib/ plus thin CLIs; one scoreboard
  testing/      fixtures and oracles
  reference/v3/ the v3 reference implementation (SATREFINE_HANDLERS=handlers_v3 still works)
```

- A test runs refine with `build/`, `tools/` and `testing/` unimportable; another checks `core/` names no specific SymPy function and imports nothing from rules or compat.
- Families are declarative specs registered explicitly; importing one registers nothing.
- Tests mirror the package; per-bug regressions are one table (`tests/refine_identities/regressions.py`, 139 rows), each run in both modes.
- `handlers` and `handlers_v2` were deleted; `git checkout 411038c` has them runnable with their tests.
- Old command lines (`tools/refine_*`, `handlers_identities`) still work through shims.

Every refactor step was gated identical to its baseline, and the generated tables regenerated byte-identical apart from module paths.

## 5. What was not met, and what is open

- **Track C** (SymPy's `ask` only for matrices): blocked on satassume #7, relations with non-rational bounds. #7 was rewritten to its current state: 31 refine cases (1 battery, 30 in one differential seed), all with `pi/2` bounds; dropping the uninterpreted relation would already answer 192 of their 194 queries.
- **Engine size:** 1,793 counted lines against 1,434. Like for like, the online engine grew by about 340 lines: the termination guard, the bounds fix, the memos, the case-split pre-test, the hook module and the matcher's power and multiset handling. The refactor removed duplicates and dead code, but the remaining cuts would remove features (the generated-table mode, about 384 lines; case splits, about 160). Accepted by the coordinator; the user can set a different target.
- **Two cases left open on purpose** (strict xfails with needs tests): `A[i, j] -> 0` under `Q.diagonal(A) & Q.ne(i, j)` (negative indices wrap), and `(x**y)**z -> Abs(x)**(y*z)` (wrong at x = 0, z = oo under SymPy's `zoo**oo = 0`).
- **One unexplained checker result:** the ext differential reports `acoth(coth(x**x)) -> x**x` as unsound at x = 3 (27.03 against 27). The rewrite holds for real positive `x**x`, and mpmath gives exactly 27 at 40 digits, so the discrepancy is in the checker, but its cause is not found yet.
- **Worse form, correct value:** `acoth(coth(Abs(x)))` under `Q.lt(x, 0)` now gives `acoth(-coth(x))` instead of `-x`.
- **Main's CI** runs `pytest tests` in one process against released SymPy; it cannot pass with refine's tests as they are (see section 7).

## 6. How the work was run

One coordinator and 18 Opus subagents in this session (after an earlier session that planned the phase and started B9) on separate worktrees, merged by the coordinator after gates. Lessons added to the rules during the phase (`.claude/phase3/agent-rules.md`):
- Fast cores are 0, 1, 10, 11 (2–5 slow, 6–9 medium, per `cpu_capacity`); the old note said 4–7.
- Never wait for or kill processes with `pgrep -f`/`pkill -f` patterns that also match the waiting shell; wait on a PID with `tail --pid`.
- Before gating, `git status --ignored` must list no source files, and the coordinator gates merges from a clean checkout: the repo's `.gitignore` had `build/`, which silently kept five `satrefine/build` modules out of a merge whose gates had passed in the agent's worktree (refine-identities was broken on clean checkouts for about an hour; fixed in d132bf3).
- Pytest skips directories named `build` by default; a conftest hook collects `tests/refine_identities/build/`.

## 7. Decisions for the user

- **Track C:** keep waiting for satassume #7, or let refine drop relations satassume cannot interpret (sound; about ten lines in `compat/backend.py`) and do C now.
- **SymPy issues:** B8 (`acot(-z)` at 0; draft in `archive/2026-09-25-phase3-bounds-report.md` §7, the user files it) and `Q.extended_real(sqrt(z))` True for negative z (draft in `archive/2026-09-26-phase3-d-extended-report.md`).
- **Long-term target** (stay on `ask`, replace v3, upstream): still open. It decides #13 steps 8–9 (a `Refiner` object for the global state, renames).
- **Merging into `main`:** recommended as a PR now that phase 3 is done, after main's CI runs each test directory in its own process with the SymPy branch refine needs.

## 8. Step reports (in `archive/`)

Termination (B9), bounds (B1–B8), A0 speed, A4/A5 speed, A6/A7 speed, fuzz extensions, default switch, matrix fixes, scalar fixes, refactor 1 (moves), refactor 2 (specs), refactor tools, refactor tests, refactor retire, D rows, D extended; all `2026-09-2[56]-phase3-*.md`.
