# Agent report: engine, phase 2 step 2 (relation decider, Piecewise) and the atan2 firing cap

- **Date:** 2026-09-25
- **Branch:** `ri/engine2` (from `refine-identities` at 2fd72b8). Not merged; the
  coordinator merges. `ri/piecewise` is superseded by this branch and can be deleted.
- **Scope:** plan step 2 (all three items) and the atan2 part of step 1.4.
- **TL;DR:** the dispatcher now caches results within one top-level call, so
  the atan2 case (and its two crashes in the differential runs) no longer
  reaches the firing cap. The engine decides `Piecewise` conditions itself.
  Relations are proved from signs and from stated relations, and the relation
  proofs are ignored for an argument known to be infinite. A candidate that
  still contains an undecided `Piecewise` is declined without a case split,
  and a table can switch case splits off. minmax_deltas is now 5 `Piecewise`
  definitions and 3 DiracDelta rules (13 rows down to 8, 45 code lines down to
  30). Battery results match the baseline case for case in both modes (hash
  seed fixed). The differential runs show no new unsound or numerically
  different result and remove 3 crashes. Refusals of Min/Max-heavy cases are
  about 100 times faster (section 4). Engine code went up by 92 lines
  (1,131 to 1,223).

## 1. What changed

| File | Change |
| --- | --- |
| `_dispatch.py` | **Result cache** per top-level call, keyed on the node, the assumptions, the mode and the engine state (`state`: identity handlers switched off, a split exploring). A node is cached only when finished, so a real loop still reaches the cap. **Refinement is iterative**: a chain of firings is a loop in `_refine`, not recursion, and every node in the chain is cached with the final result. **`own_args`**: keys whose handler refines the arguments itself (`Piecewise`). A node whose head rejects a refined child (`Max` of `nan` under inconsistent assumptions) is left as it was instead of crashing. |
| `_engine.py` | `provable(cond, a, order=False)`. New `decide(cond, a)`, which is `provable` with `order=True`: the relation atoms `Q.ge/gt/le/lt/eq/ne` and relationals (`x >= y`) are decided through the order vocabulary `ORDER` (the proof forms from `ri/piecewise`). A relation holds if a sign or infinite-endpoint form holds. Failing that, the relation forms (`Q.le`, `Q.lt`, `Q.eq`, `Q.ne`, difference zero or nonzero) are used only when no argument is known infinite (the `-oo` guard). A relation is refuted when its negation holds. In order mode an `And` goes on looking for a refuting conjunct after an undecided one. Rule hypotheses (`order=False`) behave as before. `identity_handler(..., splits=True)`: a candidate with a `Piecewise` the input did not have is declined before any split. `splits=False` switches case splits off. A binding whose substitution SymPy rejects (`Piecewise` → `ITE` `NotImplementedError`) is skipped. `_switched_off` records the busy flags in `_dispatch.state`. |
| `_simple.py` | `refine_piecewise` decides each condition with `decide`: false drops the branch, true ends the list, and an undecided branch is refined under its condition. It is registered in `own_args`, so SymPy's bare-`ask` refinement of conditions (weak on relations, raising on sign facts, wrong at `-oo`) is never used. |
| `_specialize.py` | `family_modules` skips a module that declares `SPECIALIZE = False`. |
| `minmax_deltas.py` | 5 definitions (`FACTS`) with plain `Q.ge(a, b)`-style conditions and a `(nan, True)` default, plus the 3 DiracDelta `RULES`. Measure: arguments of the family's heads, then size. `opaque=()`, `splits=False`, `SPECIALIZE = False`. |
| `tools/refine_identity_scoreboard.py` | Prints code lines (engine and per family; `--lines` alone). This reproduces phase 1's count (families 483, engine 1,131 against the reported 1,132). |
| tests | New `test_engine_conditions.py` (10 tests: the decider, the `-oo` guard, refutation past an undecided conjunct, the undecided definition declining without a split, the `splits=False` opt-out, both atan2 firing-cap cases, repeated work done once, a head refusing a refined child). `test_minmax_deltas.py` takes the `ri/piecewise` additions (beyond-v3 range cases, undefined inputs stay). `test_ablate.py` now uses the DiracDelta rows (Max no longer has rule rows). `needs/test_checker_atan2_power_firing_cap.py` moved into `test_engine_conditions.py`. |

The `ri/piecewise` needs test (`test_piecewise_conditions.py`) was not
carried over as a file. Its two tests are in `test_engine_conditions.py`.
Its second test expected `Max(x, y)` for `Max(x, y, z)` with
`z = +oo`, which is wrong. The engine gives `Max(y, z)`, and the test checks that.

Design choices:

- **No `Holds` node.** Tables write ordinary `Q.ge(a, b)` conditions. Because
  the dispatcher leaves a `Piecewise`'s arguments to the engine, SymPy never
  sees the conditions, and any table (or user input) gets the decider. This
  also changes atan2's `Piecewise`: its conditions are now decided through the
  backend's `ask` plus stated bounds, not SymPy's bare `ask`. Two differential
  cases now match v3 (section 3).
- **Rule hypotheses keep their semantics.** The order vocabulary is used only
  for `Piecewise` conditions (`decide`). Changing `provable` for every relation
  atom would have changed the combinatorial, integer_funcs and matrices rows,
  which other agents own. Those families can later switch by writing
  definitions.
- **Cache rather than a per-branch budget.** Each result stays exactly what
  recomputing it would give (the engine state is in the key), so no result can
  change except by getting cheaper. The one exception is the split budget
  (`MAX_SPLITS`): a cached result may have been computed with more budget
  left. That can only add rewrites and does not affect soundness. The fixed-seed
  battery shows no change.
- For step 4: the cache and the `state` key are what a staged generator
  needs to run candidate evaluation repeatedly at low cost. `SPECIALIZE = False`
  is the opt-out for definition tables, which the fixpoint loop should respect.

## 2. Size

| | before | after |
| --- | --- | --- |
| minmax_deltas rows | 13 rules | 5 facts + 3 rules = 8 |
| minmax_deltas code lines | 45 | 30 |
| family code lines (all 9) | 483 | 468 |
| engine code lines | 1,131 | 1,223 (`_dispatch` 154, `_engine` 605, `_simple` 213, `_specialize` 198, `_tables` 41, `_wraps` 14) |

The engine grew by 92 lines: the order vocabulary and `decide` (about 45),
the result cache and the iterative chain (about 45), and `own_args` and the
split opt-out (a few). The plan expected about 35 lines for the decider. The
cache is the price of the atan2 fix. Counted as engine plus families, the
total is 1,614 before and 1,691 after.

## 3. Gates

**Battery** (1,736 cases; scoreboard `--show`). With `PYTHONHASHSEED=0` the
output of every case is the same before and after, in both modes (diff of the
`--show` output is empty):

| mode | same | other | miss | quiet | extra | wrong | crash |
| --- | --- | --- | --- | --- | --- | --- | --- |
| generated | 1,030 | 43 | 13 | 634 | 16 | 0 | 0 |
| live | 1,032 | 41 | 13 | 634 | 16 | 0 | 0 |

(minmax_deltas: 65 same, 23 quiet, before and after.) Without a fixed hash
seed, one case varies from run to run in both trees: `log(1/x) | Q.zero(x)`
gives `zoo` or stays unchanged depending on `PYTHONHASHSEED`, the same way
in the base and the new tree (seeds 1 to 6: zoo, unchanged, unchanged,
unchanged, zoo, zoo in both). This is not a regression, but it means scoreboard comparisons need a fixed
hash seed.

**Differential** (`refine_differential.py --seed S --cases 1500`,
`PYTHONHASHSEED=0`, identities vs v3). The side-by-side runs of the base and
new trees differ only in these lines:

| seed, mode | base | new |
| --- | --- | --- |
| 2 generated | 11 different results (0 numerically different) | 10: `re(...cos(atan2(im z, re z)/2))` now equals v3's form |
| 2 live | 478 fired, 10 different | 479 fired, 9 different: the same case, plus `atan2(2*pi*k, k + pi)` under inconsistent assumptions (vacuous) |
| 3 generated | 1 crash (`Max(n**k, log x)`, nan), 17 different | 1 crash (same; run before the fix in 1077318), 16 different: `atan2(exp(n), sign(z))` at `z = 0` now `pi/2` like v3 |
| 3 live | 2 crashes (atan2 firing cap, the Max one) | 1 crash (the Max one, fixed later in 1077318); `atan2(1/(y+1), 1/m)` now fires like v3 |
| 7 generated | identical | identical |
| 7 live | 1 crash (atan2 firing cap), 444 fired | 0 crashes, 445 fired: `asinh(sinh(1/sqrt(m)))` now fires like v3 |

The unsound counts are unchanged (seed 2: 2, seed 3: 4, seed 7: 3 on the
identities side, the same inputs as before), and there is no new numerically
different result. The `Max` crash under inconsistent assumptions was fixed
after the seed 3 runs; its test is `test_a_head_refusing_a_refined_child_leaves_the_node`.

**Tests** (`tests/refine_identities`, both modes): 2,192 passed, 9 failed,
1,917 skipped, 30 xfailed. All 9 failures predate this branch:
6 needs tests owned elsewhere (`test_checker_abs_of_imaginary_is_zero.py`,
`test_checker_ask_poisons_plain_symbols.py`) and 3 generation tests
(`test_generated_module_is_up_to_date[complex_parts]`,
`test_specialize.py::test_expected_rules_are_generated` and
`::test_generated_rules_verify_or_are_flagged`). The last 3 fail the same way
on the base tree 2fd72b8: the generator no longer produces
`log(p*r) -> log(-p) + log(-r)` for negative `p`, `r`. Most likely an `ask`
change, not this branch. Step 4 should look at it before regenerating anything.

## 4. Refusal timings, Min/Max-heavy battery cases

BENCH_TABLE_PLACEHOLDER

## 5. Open problems

- The 3 pre-existing generation test failures (section 3).
- The scoreboard and differential depend on `PYTHONHASHSEED` for at least
  one case. Use a fixed seed for before/after comparisons (the tools could
  set it).
- `KroneckerDelta(x, z)` with `z` imaginary and `x` positive: v3 gives `0`,
  identities refuses (differential seed 2, before and after). `ne` has no
  proof form for "one real and one non-real". A stage-0 row candidate.
- No needs tests filed.

## 6. Commits

3c04fc2, b08b2db, bf7b5ff, 1077318, and the report commit, all on `ri/engine2`.
