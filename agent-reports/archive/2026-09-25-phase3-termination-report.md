# Agent report: phase 3, B9 (refine non-termination)

- **Date:** 2026-09-25
- **Status:** done, merged into `refine-identities` (fa03fb2) from `ri/termination` at 9b73ddb. The agent's harness blocked it from writing this file; the coordinator recorded its final report here.
- **Gates:** `.claude/gates/termination-9b73ddb` against `satperf-f83f195`.

## Root cause (verified, with one correction to #10)

satassume answers None to `Q.negative(k)`, `Q.positive(k)`, `Q.negative(-k)` and `Q.positive(-k)`, and `_from_bounds` then proved all four. The cause is a single empty interval, not "stated fact plus bounds": `_simple.stated_bounds` folds the stated `Q.negative(k)` (upper bound 0) and `Q.gt(k, pi/2)` (lower bound pi/2) into one interval, and every sign followed from it.

- `log(x) -> log(-x) + I*pi` alternates with `log(p*r) -> log(p) + log(r)` (p = -1). Each firing nests one level deeper, two Python frames per level; the stack runs out after about 493 levels.
- Only in generated mode. In live mode the identity handler's rewrite measure refuses both rewrites.

## Termination guarantee (argued in the `_dispatch` module docstring)

Per top-level call:
1. **Nesting:** at most `MAX_DEPTH = 100` nested `_refine` calls (the battery nests at most 25).
2. **Re-entry:** a node can't be refined again, under the same assumptions and engine state, while its own refinement is running. `ask` is memoized per call, so that would repeat forever; B9 is caught at its second level.
3. **Work:** the chain (500) and per-call (50,000) caps stay, plus a 200,000-firing cap that includes case and endpoint splits.

The calls form a tree of bounded depth with a bounded number of firings, so every call terminates. A Python `RecursionError` is handled the same way. A tripped limit poisons the call. By default refine returns its input unchanged and logs it in `_dispatch.loop_events`; with `SATREFINE_STRICT_LOOPS=1` it raises `RefineLoopError`. The test conftest, scoreboard and differential run strict.

## Contradictions inside the engine (documented in `_from_bounds`)

- **Bounds against bounds (B9):** fixed; an empty interval proves nothing, in `stated_bounds` and `full_bounds`.
- **Bounds against `ask`:** not detected; it needs inconsistent assumptions, costs a query per proof, and the guard makes it terminate.
- **Relation decider, `ask` contradicting itself:** left to the guard.
- **`ask` raising "inconsistent":** a top-level refine returns its input (otherwise the battery case `floor(x) | Q.negative(x) & Q.positive(x)` crashed after the bounds fix). Nested calls pass it up, which is how a case split drops a branch.

## Tests (`tests/refine_identities/test_engine_termination.py`, 8 tests, about 7 s)

- B9 in both modes with an always-None oracle (fails on f83f195), and with the real satassume backend in a subprocess.
- Fuzz over a battery sample and differential cases with oracles always None, always True, random, P and ~P both True, and real, plus contradictory sign facts. Each call must return (or raise `RefineLoopError` only when strict) within 20 s.
- Re-entry, the nesting limit, Python's own limit, a swallowed trip, no leftover state.
- Large mode (`SATREFINE_TERMINATION_FUZZ=1500`, run once): 45,304 calls, 0 failures, 220 guard trips (98 always-True, 74 both-True, 48 random), 1,533 s.

## Differential with the fallback off

`tools/refine_fuzz.py` forced the combined backend at import, so earlier "satassume-only" differentials ran combined. It now honours `SATREFINE_BACKEND`.

| | f83f195 | 9b73ddb |
|---|---|---|
| Crashes, generated (seeds 2 / 3 / 7) | 1 / 1 / 1 (B9 RecursionErrors) | 0 |
| Crashes, live | 0 | 0 |
| refine raising "inconsistent" | 4 / 5 / 7 per mode | 0 |
| Unsound | 2 / 3 / 1 | identical lists |
| Numerically different | 0 | 0 |

Side finding: the differential's consistency filter lets through about 10 relation-vs-sign contradictions per seed.

## Gates

- Suite: 2390 passed (+8), 30 xfailed.
- Scoreboard: per-family counts identical in both modes except integer_funcs crash 1 -> 0 (now "quiet"); wrong 0.
- Differential (combined): identities fires once less per run (484→483, 486→485, 456→455); each changed case has an empty stated interval, e.g. `atan2(2*pi*k, k + pi)` under `Q.nonpositive(k) & Q.gt(k, 1)`. Unsound unchanged, numerically different and crashes 0.

## Timing (pinned, interleaved, best of 2–3, load 2–10, noise about ±3%)

- Battery: 28.23 s vs 28.08 s (CPU 0), 29.23 s vs 27.74 s (CPU 1).
- `ask` always None: 49.70 s vs 51.27 s (CPU 2), 50.92 s vs 49.36 s (CPU 3).

The guard's cost is below the noise.
