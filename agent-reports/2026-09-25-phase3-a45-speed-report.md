# Agent report: phase 3, track A4 + A5 (satrefine speed: case splits, node cache)

- **Date:** 2026-09-25
- **Branch:** `ri/speed-a45` (base eb106a6 = refine-identities with B9, B1–B8, satassume perf round 2, A1+A2).
- **Status:** done. A4 kept as three small changes to `_engine.case_split`. A5 was implemented, with its correctness argument, then measured and reverted: it stays under 3% on every workload. A split memo across calls was tried and dropped (0 gain). `endpoint_split` was left in the fixpoint (it never succeeds there, but costs 2.2%).

## 1. Profile on the current head (eb106a6)

Measured with split and step counters (`hk_prof`, which wraps `case_split`, `endpoint_split` and `_step`) and an instrumented copy of `case_split` (`hk_cs`). Satassume backend, generated mode, `PYTHONHASHSEED=0`. Shares only; the absolute numbers are in section 3.

| | battery | differential seed 2 | fixpoint power_exp_log |
|---|---|---|---|
| refine time (with the hooks) | 9.32 s | 16.0 s | 55.9 s |
| case splits, inclusive | 1.73 s (19%) | 1.56 s (10%) | **35.7 s (64%)** |
| failed splits | 1.53 s, 197 of 247 | 1.41 s, 230 of 302 | 35.1 s, 1,743 of 1,972 |
| identical split repeated in the same call | 36, 0.01 s | 14, 0.01 s | 330, **8.6 s** |
| identical split repeated from an earlier call | 32, 0.08 s | 14, 0.03 s | 74, 0.0 s |
| `endpoint_split` | 203 calls, 19 succeed, 0.18 s | 118 calls, 0.03 s | 2,560 calls, 0 succeed, 1.8 s |
| steps repeating a node in another engine state | 4,966 of 23,064 (22%) | 7,537 of 23,003 (33%) | 39,083 of 98,412 (40%) |

Where the failed splits go (battery): 1.56 of their 1.73 s is stage one, the exploration of each opaque node under each sign case. The 12 costliest failed splits are all of one kind: the imaginary-symbol path (`s = I*t`) creates a new `Dummy("t")` for every split, so the explorations in the next split of the same call refine different expressions and never hit the result cache. That is the 8.6 s of "identical split in the same call" in the fixpoint: the splits are identical up to the dummy.

## 2. Changes

| Commit | Change | Kept |
|---|---|---|
| 65a0e1c | **A4a: one real-part dummy per symbol.** `_real_part_dummy(s)` returns the same `Dummy("t")` for the same `s` (a module dict), so every split on an imaginary `s` in a call explores the same expressions and shares the dispatcher's result cache. Distinct symbols get distinct dummies, so a split on one nested in a split on another cannot capture it. The result is mapped back with `t -> -I*s` as before. | yes |
| 65a0e1c | **A4b: stop a node at its first failing case.** Stage one explored a node under every sign case, then checked whether any value was still opaque. It now stops at the first opaque value (or `ValueError`): the other cases cannot save the node. | yes |
| 65a0e1c | **A4c: linkage pre-test.** A split on `s` needs every opaque node of the candidate to collapse in every case. If no conjunct of the assumptions links a node's symbols to `s` (directly or through other symbols, `_linked`), the split is not explored. The argument is in `case_split`'s docstring: the assumptions then split into a part about the node's symbols and a part about `s`, so a sign case of `s` says nothing new about the node, and the node is what refining the candidate under the assumptions left opaque. Before the change, 529 of 529 such nodes stayed opaque (battery 20, power_exp_log generation 509), and exploring them took 5% of the battery and 17% of the generation. | yes |
| 044e6d6, e3218da, reverted in 2cb920d | **A5: node cache keyed on the flags a result read.** See section 5. | no: under 3% |
| (not committed) | **Split memo across the calls of one family's generation**, with the traced rows replayed on a hit. Full fixpoint 66 s → 67 s: the repeated splits the profile counts are between rounds (round 2 regenerates complex_parts and integer_funcs), not within a generation. Reusing them across rounds needs each split's table dependencies, which the per-call result cache hides. | no: 0 gain |
| — | **`endpoint_split` off in the fixpoint.** It never succeeds there (0 of 3,399 calls in the full fixpoint on the A4 code), but it costs 1.41 s of 63.3 s (2.2%), and dropping it needs a switch the battery must not see (19 successes there). | no: under 3% |
| e428be5 | Tests: `tests/refine_identities/test_engine_case_split_pretest.py` (`_linked`, the shared dummy, a split the pre-test skips, a relation that links). | |

The A4 changes do not change which splits succeed: 50 of 247 succeed on the battery and 229 of 1,972 on power_exp_log, before and after.

## 3. Timing

TIMING-PLACEHOLDER

## 4. Output identity

Reference eb106a6, candidate A4 (2cb920d; e428be5 adds only a test).

- **Battery** (1,736 result strings) and **differential seed 2** (the worker's 1,485 records: status, result, checks), each in both identity modes under the satassume and the combined backend: **0 differences in all 8 comparisons.**
- **Fixpoint:** `tools/refine_specialize.py` (all families, to the fixpoint) prints the same rules (75 verified rules, 77 lines of output), and `--write` writes byte-identical `generated/*.py` files, derivation-record comments included.

GATES-PLACEHOLDER

## 5. A5: the node cache conditioned on the flags a result read

**What it did.** The dispatcher's result cache keyed on the node, the assumptions, the mode, `live_keys` and the engine state (`_dispatch.state`: the identity handlers switched off, a split exploring). A5 took the state out of the cache key. Every read of an engine flag went through `_dispatch.read_flag`, which adds the flag to the read set of the innermost `_refine`. A finished `_refine` passes its read set to its caller, and a cache hit passes on the read set stored with the entry. An entry stores the result, the flags read and the state it started in, and it is reused when every flag it read has the same value now. The first version (044e6d6) stored `(flag, value)` pairs; the second (e3218da) stores flag ids plus the starting state, which is cheaper and needs no correction for the blocks the computation itself switches on.

**Correctness argument** (in `_dispatch`'s docstring in e3218da, "The result cache"):
- A computation of `_refine(expr, assumptions)` depends on the cache key; on the handler tables (fixed during a call); on `ask` (memoized per call); on the nested results it looks up (by induction, what recomputing them gives); and on the engine flags. A flag matters only where it is read.
- A flag changes only inside a `_switched_off` block, which turns it on and back off. Every such block is entered right after the same frame read the flag as off: an identity handler returns at once when its flag is on, and a split is tried only when no split is exploring.
- So each read returns either the flag's value when the computation started or, inside that computation's own block for the flag, `True`. When every flag read has its starting value again, a recomputation reads the same values in the same order and takes the same path, so it gives the same result. A result computed while a handler was switched off is reused where the handler is on only if the handler was never consulted.
- The split budget and the firing counters were never in the key, and they still aren't. `consulted` and `tracing` see a node only when it is computed, as before.

**The re-entry guard (B9).** The guard keeps the full key, state included (`(expr, context, engine_state)` in `call.active`). A computation in progress has not finished reading, so its read set is not known yet. With the full key, B9's argument is unchanged: the same key means the same computation, so a re-entry can never finish. A cache hit returns a completed result and never involves a node in progress. The depth and firing limits don't depend on the cache, so the termination argument holds as before.

**Why it was dropped.** It removes the steps it aimed at: battery 21,989 → 18,132, and fixpoint power_exp_log 72,130 → 49,673 (repeats in another state 29,492 → 6,130). But those steps were cheap: most are a switched-off handler returning at once over children already cached. Measured against A4 alone (pinned, best of 2, interleaved):

| | A4 | A4 + A5 (e3218da) | |
|---|---|---|---|
| battery | 8.62 s | 8.60 s | 0% |
| differential seed 2, refine | 15.51 s | 15.12 s | −2.5% |
| fixpoint power_exp_log | 24.26 s | 25.02 s | +3% |

In the fixpoint it also leaves split budget for other, costlier splits: calls that exhaust the 8-split budget fall from 133 to 110, and split time rises from 6.6 s to 7.9 s. The first version was no better (battery −0.8%, differential −1.8%, fixpoint +3% to +6%). With the 3% rule, A5 is reverted, and its code stays in the history (e3218da) with the argument.

## 6. Open

- The remaining split cost is real failures. In the full fixpoint, failed splits are still 24 s of 63 s. The costliest nodes (`floor(-(arg(p) + arg(I*t))/(2*pi) + 1/2)` under a case of `p`, with `p`, `r` of `log(p*r)`) contain the split symbol, and only a split on two symbols at once could resolve them. The pre-test can't rule them out.
- Splits repeated between fixpoint rounds (1,185 in the full fixpoint, 5.9 s, all with the same result) could be reused if each split recorded the tables it depended on, including those behind the per-call result cache. That needs the read-set machinery of A5 applied to `consulted`.
- `endpoint_split` never succeeds in the fixpoint (0 of 3,399), for 2.2% of its time.
