# Phase 2 baseline (plan steps 1.2 and 1.3)

- **Branch:** `ri/baseline`. It is `refine-identities` with `main` merged
  in (19fa712: satassume's LRA and EUF relation theories, and the
  shared-facts fix from PR #2), plus the commits listed in section 5.
- **Use:** these are the reference numbers for every later gate. Compare
  like with like: the same mode, the same seed, and `PYTHONHASHSEED=0`
  (section 4).
- **SymPy:** `/home/tilo/orion/sympy` at 6379c4da69, unchanged.

## 1. Battery scoreboard (`tools/refine_identity_scoreboard.py`, `PYTHONHASHSEED=0`)

Generated mode (the default). Hash seeds 0 and 1 give the same table.

| Family | Same | Other | Miss | Unchanged as required | Extra | Wrong | Crash |
| --- | --- | --- | --- | --- | --- | --- | --- |
| combinatorial | 64 | 0 | 3 | 40 | 0 | 0 | 0 |
| complex_parts | 150 | 8 | 4 | 79 | 1 | 0 | 0 |
| hyperbolic | 196 | 30 | 0 | 142 | 0 | 0 | 0 |
| integer_funcs | 67 | 0 | 0 | 31 | 0 | 0 | 0 |
| inverse | 124 | 2 | 0 | **160** | **16** | 0 | 0 |
| matrices | 50 | 0 | 3 | 53 | 0 | 0 | 0 |
| minmax_deltas | 65 | 0 | 0 | 23 | 0 | 0 | 0 |
| power_exp_log | 98 | 3 | 3 | 66 | 3 | 0 | 0 |
| trig | 216 | 0 | 0 | 36 | 0 | 0 | 0 |
| **Total** | **1,030** | **43** | **13** | **630** | **20** | **0** | **0** |

193 cases are numerically unchecked. Phase 1 had 189. The 4 extra
unchecked cases are the new inverse extras described below.

Live mode (`SATREFINE_IDENTITIES=live`). Hash seeds 0 and 1 give the same
table.

| Family | Same | Other | Miss | Unchanged as required | Extra | Wrong | Crash |
| --- | --- | --- | --- | --- | --- | --- | --- |
| combinatorial | 64 | 0 | 3 | 40 | 0 | 0 | 0 |
| complex_parts | 151 | 7 | 4 | 79 | 1 | 0 | 0 |
| hyperbolic | 196 | 30 | 0 | 142 | 0 | 0 | 0 |
| integer_funcs | 67 | 0 | 0 | 31 | 0 | 0 | 0 |
| inverse | 124 | 2 | 0 | 160 | 16 | 0 | 0 |
| matrices | 50 | 0 | 3 | 53 | 0 | 0 | 0 |
| minmax_deltas | 65 | 0 | 0 | 23 | 0 | 0 | 0 |
| power_exp_log | 99 | 2 | 3 | 66 | 3 | 0 | 0 |
| trig | 216 | 0 | 0 | 36 | 0 | 0 | 0 |
| **Total** | **1,032** | **41** | **13** | **630** | **20** | **0** | **0** |

### Differences from phase 1 (generated mode)

I ran the pre-merge commit (2fd72b8) the same way. The only change caused
by the merge is in the inverse family: 4 cases moved from "unchanged as
required" to "extra" (164 -> 160 unchanged, 12 -> 16 extra):

    acoth(coth(x)) | Q.ge(x, 1)  -> x
    acoth(coth(x)) | Q.gt(x, 0)  -> x
    acsch(csch(x)) | Q.ge(x, 1)  -> x
    acsch(csch(x)) | Q.gt(x, 0)  -> x

Cause: satassume now answers `ask(Q.zero(x), Q.gt(x, 0))` with False (the
LRA theory; `0 > 0` is false, so this is sound for any `x`). That proves
the rows' `~Q.zero(z)` condition. The rows' other condition, off the cut
lines, was already provable before the merge, and `refine(im(x),
Q.gt(x, 0))` was already `0`: the package already treats a relation
assumption as implying a real argument. Under that convention the results
are correct, since for real nonzero `x`, `acoth(coth(x)) = x` and
`acsch(csch(x)) = x`. The battery cannot check them numerically because
its sampler raises on relations at complex points. v3's test expects them
unchanged because v3 does not read `Q.gt(x, 0)` as real.

**This fails the "unchanged as required" gate by 4 cases.** They are
improvements, not errors. From now on the baseline is 630 unchanged-as-required
cases, and the gate compares against that. If the coordinator prefers v3's
conservatism here, the fix is a row condition in `inverse.py`. I did not
make that change.

The remaining difference, power_exp_log "other 3 -> 2, miss 3 -> 4" in one
run, is hash-seed noise and not caused by the merge (section 4).

## 2. Differential fuzz against v3 (`tools/refine_differential.py --cases 1500`, `PYTHONHASHSEED=0`)

| Mode | Seed | b fired | Only a | Only b | Same | Different results (equal / different / undecided) | Unsound a / b | Crash b |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| generated | 2 | 483 | 4 | 28 | 444 | 11 (8 / 0 / 3) | 2 / 2 | 0 |
| generated | 3 | 485 | 3 | 25 | 446 | 14 (9 / 1 / 4) | 3 / 4 | 0 |
| generated | 7 | 456 | 5 | 22 | 418 | 16 (11 / 0 / 5) | 1 / 1 | 0 |
| live | 2 | 481 | 5 | 27 | 444 | 10 (7 / 0 / 3) | 2 / 2 | 0 |
| live | 3 | 484 | 4 | 25 | 444 | 15 (10 / 1 / 4) | 3 / 4 | 1 |
| live | 7 | 455 | 6 | 22 | 417 | 16 (11 / 0 / 5) | 1 / 1 | 1 |

Here a is v3 (`handlers_v3`) and b is `handlers_identities`.

- The only numerically different result, and the only unsound result that
  v3 does not share, is `refine(log(exp(sqrt(x**2))), Q.imaginary(x)) -> 0`
  (seed 3, both modes). This is the known Abs-of-imaginary defect,
  `needs/test_checker_abs_of_imaginary_is_zero.py` and plan step 1.4.
  Every other unsound result is shared with v3: removable singularities at
  0, `acoth` at -1 and 0, and `binomial` at a pole.
- Crashes (live mode only): seed 7 is the known
  `atan2(y, k**y)` firing-cap crash. Seed 3 is
  `atan2(sqrt(z), x**x)`, the same class, and it crashes on the pre-merge
  commit too. I added it to `needs/test_checker_atan2_power_firing_cap.py`.
- Compared with phase 1 (one numerically different result, at seed 3, and
  the Abs-of-imaginary cases as the only unsound results unique to this
  side): no new unsound result and no new numerically different result.

## 3. Test suite (`tests/refine_identities`, `PYTHONHASHSEED=0`)

| Mode | Passed | Failed | Skipped | Xfailed | Time |
| --- | --- | --- | --- | --- | --- |
| generated | 2,182 | 6 | 1,917 | 30 | 22 min |
| live | 2,182 | 6 | 1,917 | 30 | 22 min |

All 6 failures are needs tests, which are open requests:
`needs/test_checker_abs_of_imaginary_is_zero.py` (2),
`needs/test_checker_atan2_power_firing_cap.py` (3, one of them new) and
`needs/test_baseline_hash_seed_dependence.py` (1, new). Every other test
passes.

## 4. The hash seed changes results (found here, not caused by the merge)

`refine(log(1/x), Q.zero(x))` gives `zoo` for hash seeds 0, 1, 5, 6 and 7,
and leaves the input unchanged for seeds 2, 3 and 4. This happens both
before and after the merge. With seed 0 the `arg` handler first rewrites
`arg(1/x) -> 0`, and then the `log` handler fires. That intermediate step is
questionable, since `arg(zoo)` is `nan`. With seed 2 neither handler fires.
So candidate order in the engine depends on hash order. The whole
scoreboard differs between seeds only in this case. The phase-1 numbers and
the first run here used random seeds, which is why power_exp_log showed
"other 3" in one run and "other 2 / miss 4" in another.

Needs test: `needs/test_baseline_hash_seed_dependence.py`, for the engine
owner. **Run every gate with `PYTHONHASHSEED=0`.**

## 5. What changed on `ri/baseline`

Before these changes, 10 tests failed in both modes: 5 needs tests and the
5 tests below. The first two failures were caused by the merge. The other
three (`test_specialize.py` twice, `test_generated.py` once) also fail on the
pre-merge commit.

- `test_ablate.py`: after Max's sign row is removed, finite sign facts
  still fire Max's relation row, because LRA now proves `Q.le(y, x)`. The
  test now uses an infinite `x`, where only the sign row applies. (Note for
  the minmax_deltas owner: for finite arguments the sign row is now
  covered by the relation row, so an ablation run may propose removing it.
  It is still needed for the infinite endpoint.)
- `test_engine_integer_funcs.py::test_ask_raising_is_not_provable`: the
  combined backend now answers `Q.lt(m, y)` under consistent sign facts
  instead of raising, so the test simulates the raise with a
  monkeypatched `_upstream.ask`.
- `test_specialize.py` (pre-existing): the generator produces
  `log(p*r) -> log(-p) + log(-r)` under `Q.negative(r)` alone. That is more
  general and correct, because `-r > 0`. The expectation is updated.
- `test_generated.py::...[complex_parts]` (pre-existing): importing the
  generated module evaluates `Abs(exp(z))` to `exp(re(z))`, so the in-memory
  rows differ from the rows as read back. The test now compares the rows
  as the module reads them back. The three affected rows are correct.
- `needs/test_checker_ask_poisons_plain_symbols.py`: the satassume part is
  fixed and tested on `main`. The refine check passes and moved to
  `test_earlier_calls_do_not_leak.py`. The SymPy root cause (`(0**n).is_finite`)
  is an upstream issue candidate (see `2026-09-24-satfix-report.md`) and is
  not tested here.
- New needs tests: `needs/test_baseline_hash_seed_dependence.py`, and one
  more case in `needs/test_checker_atan2_power_firing_cap.py`.

## 6. Commands

    export PYTHONHASHSEED=0 PYTHONPATH=.:/home/tilo/orion/sympy
    SATREFINE_IDENTITIES=generated|live uv run --no-project --with pytest --with mpmath --with hypothesis \
        python -m pytest -q -p no:cacheprovider tests/refine_identities          # about 20 min per mode
    SATREFINE_IDENTITIES=generated|live uv run --no-project --with pytest --with mpmath \
        python tools/refine_identity_scoreboard.py --show                         # about 5 min per mode
    SATREFINE_IDENTITIES=generated|live uv run --no-project --with pytest --with mpmath \
        python tools/refine_differential.py --seed 2|3|7 --cases 1500             # 10 to 13 min each
