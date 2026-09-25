# Agent report: phase 3, track A6 + A7 (satrefine speed: memos, suite wall time)

- **Date:** 2026-09-25
- **Branch:** `ri/speed-a67` (base b01b7a9 = refine-identities with B1–B9, satassume perf round 2, A1+A2, A4), merged with origin/refine-identities 1ecb4e8 at 5ab03c9.
- **Status:** done, gates pass. A6 kept as four memos of pure functions (two of them in the plan, two found in the new profile); the plan's third item, the `stated_bounds` memo, was measured and dropped. A7 done: suite wall time 112 s → 44–53 s at comparable load; the long checks are opt-in and need one new gate task (section 5).

## 1. Profile on the current head (b01b7a9)

cProfile, satassume backend, generated mode, `PYTHONHASHSEED=0`, one run pinned (load about 10: shares only). Battery refine, 22.8 s under the profiler:

| item | share | note |
|---|---|---|
| satassume `ask` (through the per-call memo) | 38% | out of scope |
| `subst` (xreplace with auto-evaluation) | **17%** | 22,291 calls, **2,931 distinct** (expr, binding) pairs in the whole battery |
| `Expr.cancel` in `_match`'s `n*unit + r` ratio | **9.7%** | 2,871 calls, **82 distinct** terms; 2,867 of 2,879 return an equal expression |
| `stated_finite`/`_stated` (from `_from_bounds`) | 6.2% | 6,609 calls, 1,473 distinct |
| matching (`bindings`/`_match`) | 17% incl. | |
| `refine_piecewise` | 9% incl. | mostly `decide` → `ask` |
| `count_ops` (orderings, `_distributed`) | 3% battery, **5.5% fixpoint** | same expressions measured again every pass |

Hypotheses already `True`: 583 of the 22,291 `subst` calls; once `subst` is memoized they cost a dictionary lookup, so no special case was added.

## 2. Changes

| Commit | Change | Kept |
|---|---|---|
| 97111da | **`_ratio(term, unit)`**: `(term/unit).cancel()` of the `n*unit` form behind `lru_cache(4096)`. | yes |
| 97111da | **`subst` memo**: the substitution (symbols by `xreplace`, head wildcards by class) is `_substituted(expr, frozenset(binding items without REBUILD))` behind `lru_cache(8192)`; the partial-match rebuild (a closure, different per binding) is applied after the lookup, as before. An unhashable binding value falls back to the uncached function. | yes |
| 97111da, reverted in 04fddc4 | `_simple._stated` behind `lru_cache` (the plan's "memoize `stated_bounds`"; global rather than per call, since it depends on `(u, assumptions)` only). | **no:** 0–1.6% on battery and fixpoint, inconclusive on the differential (section 3) |
| 04fddc4 | **`_engine.size(e)`** = `count_ops(e)` behind `lru_cache(8192)`, used by `default_measure` and the three `_tables` orderings; **`_distributed`** of an expression behind `lru_cache(4096)`. | yes |
| e116c54 | A7, section 4. | yes |

All four memos cache pure functions of hashable SymPy objects: `cancel`, `xreplace`, `count_ops` and `expand_mul` give equal results for equal inputs, and none reads the tables, the engine state or `ask`. So results are the same whatever the order of calls, and there is nothing for the per-call reset to protect; this is why they are process-wide and bounded (`lru_cache`), unlike the `ask` memo.

## 3. Timing

Satassume backend, generated mode, `PYTHONHASHSEED=0`, each process pinned to one fast core; two sequences in opposite order on two cores, best of 2 per core. Reference = b01b7a9 (`git archive`), per-change trees = reference plus that change only. "diff" is the refine time inside the differential worker, seed 2, 1,500 cases (`refine_differential.worker` in process). "pel" is `_stages.generate_one(power_exp_log)` (the plan's fixpoint workload).

Per change (round 1, load 2.3–5.1; CPU 0 / CPU 1 for battery and diff, CPU 10 / 11 for pel):

| | battery | diff | pel |
|---|---|---|---|
| ref | 8.14 / 7.97 | 16.51 / 16.29 | 25.63 / 26.32 |
| ratio memo | 7.48 / 7.34 (−8.1% / −7.9%) | 15.85 / 15.39 (−4.0% / −5.5%) | 24.27 / 24.60 (−5.3% / −6.5%) |
| subst memo | 7.41 / 7.42 (−9.0% / −6.9%) | 16.43 / 15.41 (−0.5% / −5.4%) | 23.40 / 23.39 (−8.7% / −11.1%) |
| stated memo | 8.01 / 7.92 (−1.6% / −0.6%) | 16.45 / 15.82 (−0.4% / −2.9%) | 25.50 / 26.12 (−0.5% / −0.8%) |
| all three (97111da) | 6.81 / 6.53 (−16.3% / −18.1%) | 15.03 / 14.97 (−9.0% / −8.1%) | 21.46 / 22.09 (−16.3% / −16.1%) |

On top of 97111da (round 2, load 5.2–7.4, noisier): `size`/`_distributed` memos: battery 7.40/7.20 → 7.28/7.11 (−1.6% / −1.2%), pel 21.79/22.22 → 21.13/21.60 (−3.0% / −2.8%), diff 15.35/15.47 → 14.59/14.37 (−5.0% / −7.1%): kept on the differential. Removing the stated memo from 97111da: battery 7.40/7.20 → 7.42/7.29, pel 21.79/22.22 → 21.97/22.35, diff 15.35/15.47 → 16.18/15.09: no gain, dropped.

**Stacked, final (HEAD before the merge, e116c54; round 3, load 2.3–3.9; last pinned timing finished 22:13 UTC):**

| workload | ref (b01b7a9) | A6 | change |
|---|---|---|---|
| battery refine, 1,736 cases (CPU 0 / 1) | 8.83 / 8.55 s | 7.12 / 6.93 s | **−19.4% / −18.9%** |
| differential seed 2, refine time (CPU 0 / 1) | 15.43 / 15.04 s | 13.83 / 13.71 s | **−10.4% / −8.8%** |
| fixpoint power_exp_log (CPU 10 / 11) | 24.45 / 24.67 s | 19.31 / 19.95 s | **−21.0% / −19.1%** |

The battery pair ran next to the pel pair on the other fast cores and is about 8% slower in absolute terms than round 1, for both sides equally. Full fixpoint (`_stages.generate()`, combined backend, unpinned, two in parallel at load about 10): 102.0 s → 86.9 s with 97111da.

Against the phase-3 targets: battery 14.8 s (f83f195) → 6.9–7.1 s (target ≤ 9 s); fixpoint power_exp_log 64.7 s → 19.3 s (−70%, target −25%); differential refine 19.6 s → 13.7 s (−30%, target −25%; the 19.6 s was measured by the plan's profile script, not this one).

## 4. A7: suite

| Commit | Change |
|---|---|
| e116c54 | Marker **`full`** (`conftest.py`): a test with it is skipped unless `SATREFINE_FULL_TESTS=1`. Marked: `test_generated_module_is_up_to_date` for `power_exp_log`, `complex_parts` and `integer_funcs`, and battery case `1571:test_minmax_deltas.py::test_minmax_all_equal_keeps_one` of `test_battery_is_numerically_valid` (28–34 s in the sampler searching for a point with `x = y = z`, and then it skips anyway: "no satisfying sample"). |
| e116c54 | **Smoke test:** the fixpoint check of `inverse` (3–5 s, `SMOKE_FAMILY` in `test_generated.py`) stays in the default run. |
| e116c54 | **`shared` fixture** (`conftest.session_shared`): computes a value once per session and pickles it next to the basetemp all xdist workers of a run share, under an `fcntl` lock; the other workers wait and load it. `test_specialize.py`'s `rules` (`specialize_table(power_exp_log.IDENTITIES)`, 17–25 s) uses it and is session-scoped. Before, the module fixture ran once per worker that got one of its three tests (up to 3 × 25 s of CPU). Checked with `-n 3`: three setups at 17.8 s, one computation, 4 passed; `-n 0`: 4 passed. |

"The generated tables once per session": no default test builds them except through the per-family fixpoint checks above (each regenerates a different family, nothing to share) and the import of `satrefine` (0.5 s per worker).

Suite wall time, `tests/refine_identities`, `-n 4`, pinned to CPUs 0, 1, 10, 11, interleaved, same command as the gates' suite task:

| run | load before/after | ref (b01b7a9) | HEAD (e116c54) |
|---|---|---|---|
| 1 | 4.0 / 4.0 (ref), 4.0 / 4.2 (HEAD) | 111.7 s | 52.9 s |
| 2 | 4.2 / 3.1 (ref), 3.1 / 3.4 (HEAD) | 114.0 s | 44.3 s |

**−53% to −60%.** Counts: 2,464 passed, 1,917 skipped → 2,462 passed, 1,920 skipped (3 fixpoint tests and 1 battery case skipped by default; +1 new test, `test_smoke_family_generates`). Unpinned at load 7–10 the new suite took 53–89 s; the gates' suite (under their own load of 13–18) took 381 s at speed-a45.

The opt-in part, `SATREFINE_FULL_TESTS=1 pytest -n 4 -m full tests/refine_identities` (before the merge, e116c54, load 6.3): 3 passed, 1 skipped (the battery case, as before) in 31.7 s; power_exp_log 28.4 s, the battery case 27.6 s, integer_funcs 24.0 s, complex_parts 22.5 s.

## 5. Gate line to add (for the coordinator; `tools/refine_gates.sh` is owned by the fuzz-ext track)

After the `suite` task:

```
tasks+=("full|env SATREFINE_FULL_TESTS=1 timeout 2400 ${uvrun[*]} -m pytest -q -p no:cacheprovider -n 3 -m full tests/refine_identities")
```

Name `full`; exit 0 is a pass (like the termination task). Together with the default suite (which keeps `inverse`) it is the full fixpoint check of all four generating families. Until it is added, the gates' suite no longer checks the fixpoint of power_exp_log, complex_parts and integer_funcs.

## 6. Output identity

Reference b01b7a9, candidates 97111da (A6 round 1) and 04fddc4 (final A6; e116c54 changes only tests):

- **Battery** (1,736 result strings) and **differential seed 2** (the worker's records: status, result, checks), each in both identity modes under the satassume and the combined backend: **0 differences in all 8 comparisons**, for both candidates.
- **Full fixpoint** (`_stages.generate()`, all families to the fixpoint, combined backend): the same 75 rules (integer_funcs 11, complex_parts 40, power_exp_log 17, inverse 7), for both candidates.

## 7. Gates

`gates/speed-a67-5ab03c9` (the merge with origin/refine-identities 1ecb4e8; the summary names 77ac6e5, which adds only this report's draft) against `gates/default-merged-f3ee6c4`, JOBS=9, SLOTS=11, SUITE_WORKERS=4, started at load 2, 739 s.

- **Suite:** 66 failed, 2,516 passed, 1,920 skipped, 30 xfailed in 126 s (baseline: 66 failed, 2,518 passed, 1,917 skipped, in 162 s). The 66 failures are the same tests as in the baseline, all under `tests/refine_identities/needs/` (0 failures outside `needs/`). Passed −2 and skipped +3: the three `full` fixpoint tests and battery case 1571 (which ended in a skip anyway) are skipped by default, and `test_smoke_family_generates` is new.
- **Scoreboard, both modes:** identical except the engine line count, 1,664 → 1,684 (the memo helpers). wrong 0, crash 0; generated same 1,032 / other 41 / miss 13, live 1,033 / 40 / 13.
- **Differential seeds 2, 3, 7, both modes, and the satassume differential (seed 2, both modes):** identical except the times.
- **Matrix differential, both modes:** identical except the times.
- **Ext differential (seed 2, 1,000 cases, 20 s per-case timeout), both modes:** only the timeouts moved, on both sides: identities' timeouts 4 → 3 (generated) and 5 → 3 (live), each such case now finishing as unchanged; v3's (untouched code) moved as well, 4 → 2 and 3 → 2. Unsound, crash and inconsistent are unchanged (identities: 0, 0, 0). These are load effects of a 20 s cut-off, not output changes.
- **Termination tests:** 8 passed.
- **The opt-in tests on the merged head** (5ab03c9, `SATREFINE_FULL_TESTS=1 pytest -n 3 -m full`, load 2.5–3.2): 3 passed, 1 skipped (the battery case, as in the baseline) in 62.6 s; power_exp_log 27.0 s, complex_parts 22.8 s, integer_funcs 19.7 s, the battery case 32.3 s.

## 8. Open

- satassume `ask` is now about half of the battery's refine time and more of the fixpoint's (out of scope).
- Left in the differential's refine profile: `refine_piecewise` (26%, mostly `decide` → `ask` and SymPy's `Max`/`Min` construction) and `_stated`'s `_affine` on large arguments (7% under the profiler, but the memo did not show it in the pinned runs).
- `SLOW_SAMPLING` in `test_battery.py` names the case by its battery index; if `battery_v3.py` is regenerated with a different order, the marker silently stops applying (the case then runs by default again, 30 s).
