# Agent report: phase 3, track A0 (satrefine speed: A1, A2, A3; gates)

- **Date:** 2026-09-25
- **Branch:** `ri/speed-a0` (base 9819814 = ri/termination, merged with origin/refine-identities 3ad03bf at 881e47f).
- **Status:** done. A1 and A2 kept, A3 measured and dropped. Gates pass against `bounds-merged-3ad03bf`.

## What changed

| Commit | Change |
|---|---|
| 0770391 | **A1.** `_dispatch._step` calls satrefine's own copies of `Pow._eval_refine` and `exp._eval_refine` (`_pow_eval_refine`, `_exp_eval_refine`, looked up by the SymPy method they replace, so a subclass that overrides the hook keeps its own). They ask through `_upstream.ask`, i.e. the selected backend and the per-call memo. `ValueError` (inconsistent assumptions) makes the hook decline. `exp`'s copy keeps SymPy's quirk of asking without the assumptions. SymPy is unchanged; `_upstream.refine` (vendored) is unchanged. |
| 25ba478, d54ca58 | **A2.** `_engine._shape(pattern)` computes once per pattern what `_match` re-derived on every match (`_is_unit_coefficient_form`, including its `cancel`; the rest-symbol positions; whether an argument is a `part`), memoized in `_engine._shapes`. d54ca58 fixes a bug in the first version: it remembered the rest *symbol*, and `_match` picks the other arguments by identity (`a is not rest_sym`); after SymPy's cache dropped the symbol, an equal pattern built later consists of other objects and matched nothing. This caused order-dependent suite failures (`test_structure_beside_a_rest_symbol` after `test_complex_parts`; the complex_parts fixpoint test in the first gate run). The shape now stores positions. Regression test: `tests/refine_identities/test_engine_pattern_shapes.py`. |
| c071543, aa92c4d | **A3** (head test before `bindings` in both handler kinds) was implemented, measured at 0.8% on top of A1+A2, and removed (under the 3% bar, and it adds code). |
| 646d294, b7cdc6a | **Gates** (`tools/refine_gates.sh`): a differential with `SATREFINE_BACKEND=satassume` (seed 2, 1,500 cases, both modes); the termination tests (B9 adversarial-ask fuzz) as a named gate (default size; `TERMINATION_FUZZ=N` runs the large version, 570 s at N=150 on one core, too long for every gate run); the baseline comparison is now per `== ` section, so a baseline made before a gate existed prints `<section>: no baseline` for that section instead of a wall of added lines. |
| 576158c | After the merge: B8's one line in `_step` (`_simple.rebuild(expr.func, args, assumptions)`); `needs/test_bounds_acot_rebuild.py` passes and moved to `tests/refine_identities/`. |

**refine_fuzz / refine_differential backend:** the fix in 7a6b632 works. The differential's workers are subprocesses that inherit `SATREFINE_BACKEND`; a worker run with `SATREFINE_BACKEND=satassume` sent all 353 queries of 40 cases to `_IMPLEMENTATIONS["satassume"]`. `refine_differential.py` needed no change.

## Timing (pinned, before the merge, same base)

Battery `refine`, all 1,736 cases, `SATREFINE_BACKEND=satassume`, generated mode, `PYTHONHASHSEED=0`. Interleaved ref/candidates, one process on one fast core (`taskset -c 1`, then `-c 0`), 1-minute load 1.2 to 5.6. Reference = 9819814 in a scratch worktree.

Note on cores: `cpu_capacity` says the fast cores are 0, 1, 10, 11 (1024/984); 2 to 5 are the slow ones (279), 6 to 9 medium (905/866). The rules file says 4 to 7 are slow; that is wrong on this machine (a first run pinned to CPU 3 took 126 s).

| Run set | ref | A1 | A1+A2 | A1+A2+A3 |
|---|---|---|---|---|
| round 1 (CPU 1) | 15.38 | 11.81 | 10.66 | 10.66 |
| round 2 | 14.82 | 11.94 | 10.96 | 10.94 |
| round 3 | 15.09 | 11.40 | 10.40 | 10.32 |
| **best** | **14.82** | **11.40 (−23%)** | **10.40 (−30%)** | 10.32 (−0.8% on A1+A2) |

Final stack (A1 + A2 with the fix, d54ca58), CPU 0, three rounds: ref 14.56 / 14.43 / 14.38 s, cand 10.28 / 10.23 / 10.23 s: **14.38 → 10.23 s, −28.9%** (plan target −26%, 11 s).

Differential worker, seed 2, 1,500 cases, satassume (the whole identities worker: generation, refine and numeric checks): ref 28.60 / 28.67 s, final 25.97 / 26.00 s: **−9.2%**. (A1+A2+A3 earlier: 29.02 → 26.27 s.) Under the combined backend A1 gains nothing (worker refine 96.9 vs 97.3 s, unpinned): there the copies ask satassume first and SymPy after, as SymPy's own hook did not.

## Output identity (before the merge)

ref = 9819814, candidate = A1+A2+A3 (c071543). Battery (1,736 result strings) and the differential worker's records (seed 2, 1,485 compared cases: status, result, checks), each in both identity modes and under both the satassume and the combined backend: **0 differences in all 8 comparisons.** The final A1+A2 (d54ca58): battery in both modes and the differential (generated), satassume: 0 differences. The 9 differential inputs with inconsistent assumptions that raised in the prototype do not raise here (the copies catch `ValueError`); their results are unchanged.

## Gates

`gates/speed-a0-576158c` against `gates/bounds-merged-3ad03bf` (JOBS=9 SLOTS=11 SUITE_WORKERS=4):

- **suite:** 2,460 passed, 0 failed (baseline: 14 failed, all `needs/test_bounds_acot_rebuild.py`, now fixed and moved).
- **scoreboard, both modes:** unchanged (only the engine line count differs): wrong 0, crash 0, same/other/miss/quiet/extra per family identical.
- **differential seeds 2, 3, 7, both modes:** identical except seed 3 (both modes): identities unsound 3 → 2, and one "both fire, numerically different" appears: `acoth(sqrt(z**2))` under `Q.nonpositive(z)`, v3 `-acoth(z)`, identities now `acoth(-z)`. At z = 0 the input is `I*pi/2`; identities is right, v3 (SymPy's `acoth.eval` sign extraction) is wrong. This is B8 (the `_simple.rebuild` line), not A0.
- **new, no baseline:** satassume differential seed 2: generated fired 440, unsound 2, crash 0, inconsistent 0, numerically different 0; live fired 437, unsound 2, crash 0, numerically different 0 (v3: 407 fired, unsound 2, 24 inconsistent). Termination tests: 8 passed.

Earlier gate `gates/speed-a0-b7cdc6a` (before the merge, against `termination-9819814`): everything identical except the suite, which failed `test_generated_module_is_up_to_date[complex_parts]`: the A2 identity bug above, fixed in d54ca58.

## Open

- A3 dropped at 0.8%; A4 to A7 are for the next branches. The remaining large items in the profile are the failed case splits (A4) and repeated nodes in another context (A5).
- The rules file's statement about slow cores (4 to 7) should be corrected to 2 to 5.
- The large termination fuzz (`TERMINATION_FUZZ=150`) passed on this branch before the merge: 26,404 runs, outcomes only ok, loop (a tripped guard) and inconsistent.
