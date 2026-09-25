# Agent report: engine, phase 2 step 2 (relation decider, Piecewise) and the atan2 firing cap

- **Date:** 2026-09-25
- **Branch:** `ri/engine2`, from `refine-identities` 2fd72b8. `origin/refine-identities`
  is merged in up to 8f0e147 (merge commit 1610aeb). Not merged into
  `refine-identities`; the coordinator does that. This branch supersedes
  `ri/piecewise`, which can be deleted.
- **Scope:** plan step 2 (items 1 to 3) and the atan2 part of step 1.4.
- **TL;DR:**
  - The atan2 firing-cap crashes are gone. The dispatcher now keeps a result
    cache for each top-level call and refines a chain of firings in a loop.
  - The engine decides `Piecewise` conditions itself, through an order
    vocabulary that includes the guard at infinity.
  - A candidate that still contains an undecided `Piecewise` is declined
    without a case split, and a table can switch case splits off.
  - minmax_deltas is now 5 `Piecewise` definitions plus 3 DiracDelta rules:
    13 rows down to 8, 45 code lines down to 30.
  - Engine code grew from 1,131 to 1,235 lines.
  - Two engine needs tests from other agents are fixed: the hash-seed
    dependence and a MatrixElement crash.
  - Gates against the shared baseline base-8f0e147: one battery case changes,
    in both modes. `log(1/x) | Q.zero(x)` moves from "other form" to "miss",
    because its `zoo` came from reasoning under inconsistent assumptions.
    Needs test filed.
  - The differential shows no new unsound or numerically different result,
    and 0 crashes, against 2 on the baseline.
  - Min/Max-heavy refusals are 4.4 times faster (25.8 s to 5.9 s over the
    23 battery refusals, pinned CPU). The speed-up comes from asking SymPy's
    slow `Q.eq` query only when the assumptions state a relation.

## 1. What changed

| File | Change |
| --- | --- |
| `_dispatch.py` | **Result cache** for each top-level call. Key: node, assumptions, mode, and engine state (`state`: identity handlers switched off, a split exploring). A node is cached only once it is finished, so a real loop still reaches the firing cap. **Iterative refinement:** a chain of firings is a loop in `_refine` instead of recursion, and every node of the chain is cached with the final result. **`own_args`:** keys whose handler refines the arguments itself (`Piecewise`). When a head rejects a refined child (`Max` of `nan` under inconsistent assumptions), the node is left as it was instead of crashing. |
| `_engine.py` | New `decide(cond, a)`, which is `provable(cond, a, order=True)`. Relation atoms (`Q.ge/gt/le/lt/eq/ne` and relationals such as `x >= y`) are decided through `ORDER`, the proof forms taken from `ri/piecewise`. A relation holds by a sign or infinite-endpoint form. Failing that, it holds by a relation form (`Q.le`, `Q.lt`, `Q.eq`, `Q.ne`, `u - v` zero or nonzero), and only when no argument is known infinite: that is the `-oo` guard. A relation is refuted when its negation holds. `Q.eq`/`Q.ne` atoms are asked only when the assumptions state a relation (section 4). In order mode, an `And` keeps looking for a refuting conjunct after an undecided one. Rule hypotheses (`order=False`) behave as before. `identity_handler(..., splits=True)`: a candidate with a `Piecewise` the input did not have is declined before any split, and `splits=False` turns splits off. A binding whose substitution SymPy rejects (`Piecewise` to `ITE`, `NotImplementedError`) is skipped. `_split_branches` offers no sign case when neither sign is consistent. |
| `_simple.py` | `refine_piecewise` decides each condition with `decide`. False drops the branch, true ends the list, and an undecided branch is refined under its own condition. The handler is registered in `own_args`, so SymPy's bare-`ask` condition refinement is never used. That refinement is weak on relations, raises on sign facts, and is wrong at `-oo`. `_affine` substitutes no scalar for a matrix. |
| `_specialize.py` | `family_modules` skips any module that declares `SPECIALIZE = False`. |
| `minmax_deltas.py` | 5 definitions (`FACTS`) with plain `Q.ge(a, b)` conditions and a `(nan, True)` default, plus the 3 DiracDelta `RULES`. Measure: arguments of the family heads, then size. Settings: `opaque=()`, `splits=False`, `SPECIALIZE = False`. |
| `tools/refine_identity_scoreboard.py` | Prints code lines for the engine and per family (`--lines` prints only these). It reproduces phase 1's count: families 483, engine 1,131 against the reported 1,132. |
| tests | New `test_engine_conditions.py` with 11 tests: decider, `-oo` guard, refutation after an undecided conjunct, undecided definition declining without a split, `splits=False`, the three atan2 firing-cap cases, repeated work done once, a head rejecting a refined child. Moved from needs: `test_engine_hash_seed.py` (was `needs/test_baseline_hash_seed_dependence.py`) and `test_engine_matrixelement_bounds.py` (was `needs/test_matfuzz_matrixelement_bounds_crash.py`). `test_minmax_deltas.py` takes the `ri/piecewise` additions. `test_ablate.py` now uses the DiracDelta rows, since Max has no rule rows any more. |

The `ri/piecewise` needs test `test_piecewise_conditions.py` was not carried
over as a file. Its two tests are now in `test_engine_conditions.py`. The
second one expected `Max(x, y)` for `Max(x, y, z)` with `z = +oo`, which is
wrong. The engine gives `Max(y, z)`, and the moved test asserts that.

Design choices:

- **No `Holds` node.** Tables write ordinary `Q.ge(a, b)` conditions. The
  dispatcher leaves a `Piecewise`'s arguments to the engine, so every table
  and every user input gets the decider. This also changes atan2's
  `Piecewise`: its conditions now go through the backend's `ask` plus stated
  bounds. Three differential cases now match v3 that did not before.
- **Rule hypotheses keep their meaning.** The order vocabulary applies only
  to `Piecewise` conditions. Changing `provable` for every relation atom
  would have changed rows in combinatorial, integer_funcs and matrices,
  which other agents own.
- **A cache, not a per-branch budget.** Engine state is part of the key, so
  each cached result equals what recomputing it would give. The one
  exception is the split budget: a cached result may have been computed
  with more budget left. That can only add rewrites.
- **For step 4.** The cache makes repeated candidate evaluation cheap within
  one call. `SPECIALIZE = False` is the opt-out for definition tables, and
  the fixpoint loop should respect it.

## 2. Size

| | before (2fd72b8) | after (1610aeb) |
| --- | --- | --- |
| minmax_deltas rows | 13 rules | 5 facts + 3 rules = 8 |
| minmax_deltas code lines | 45 | 30 |
| family code lines, all 9 | 483 | 468 |
| engine code lines | 1,131 | 1,235 (`_dispatch` 155, `_engine` 611, `_simple` 216, `_specialize` 198, `_tables` 41, `_wraps` 14) |

The engine grew by 104 lines:
- order vocabulary, `decide` and the relation-statement check: about 50
- result cache and iterative chain: about 45
- `own_args`, split opt-out and the two needs fixes: about 10

The plan expected about 35 lines for the decider. The cache is the cost of
the atan2 fix. Engine plus families: 1,614 lines before, 1,703 after.

## 3. Gates (`tools/refine_gates.sh`, PYTHONHASHSEED=0, against `/home/tilo/fable-rewrite/.claude/gates/base-8f0e147`)

Run: `/home/tilo/fable-rewrite/.claude/gates/engine2-1610aeb` (summary.txt).

**Suite:** 2,325 passed, 0 failed, 1,917 skipped, 30 xfailed. The baseline
suite exited 1. The 2 needs tests filed afterwards
(`needs/test_engine_reciprocal_of_zero.py`) fail by design.

**Battery:** identical per family to the baseline except power_exp_log, in both modes:

| power_exp_log | same | other | miss | quiet | extra |
| --- | --- | --- | --- | --- | --- |
| baseline generated | 98 | 3 | 3 | 65 | 4 |
| engine2 generated | 98 | 2 | 4 | 65 | 4 |
| baseline live | 100 | 1 | 3 | 65 | 4 |
| engine2 live | 100 | 0 | 4 | 65 | 4 |

The one case is `log(1/x) | Q.zero(x)`. Before, it gave `zoo` for some hash
seeds (0, 1, 5, 6, 7) and stayed unchanged for others. The `zoo` came from
the positive branch of a case split explored under `Q.zero(x)`. Those
assumptions are inconsistent, and the backend's answer there (`True` or a
`ValueError`) depended on the hash seed. The engine no longer explores a
branch when neither sign is consistent. The result is now the same for
every seed (unchanged), which is what the needs test asked for. This is
strictly a gate drop of 1 in power_exp_log, but the dropped answer was
derived from inconsistent assumptions. The sound route is a `Pow` row,
`b**e = zoo` for zero `b` and negative `e`. It belongs to power_exp_log,
which I do not own, so it is filed as
`needs/test_engine_reciprocal_of_zero.py`. Wrong and crash stay at 0.

**Differential** (identities vs v3, 1,500 cases):

| mode, seed | b fired | only a / only b / same | different (equal / different / undecided) | unsound b | crash / timeout b |
| --- | --- | --- | --- | --- | --- |
| generated 2 | 483 | 4 / 28 / 445 | 10 (7 / 0 / 3) | 2 | 0 / 0 |
| generated 3 | 484 | 3 / 25 / 448 | 11 (8 / 0 / 3) | 3 | 0 / 0 |
| generated 7 | 456 | 5 / 22 / 418 | 16 (11 / 0 / 5) | 1 | 0 / 0 |
| live 2 | 482 | 5 / 28 / 445 | 9 (6 / 0 / 3) | 2 | 0 / 0 |
| live 3 | 484 | 3 / 25 / 448 | 11 (8 / 0 / 3) | 3 | 0 / 0 |
| live 7 | 456 | 5 / 22 / 418 | 16 (11 / 0 / 5) | 1 | 0 / 0 |

The unsound counts equal the baseline's: 2, 3 and 1 per seed. There are no
numerically different results. The baseline had 2 crashes: generated seed 3,
`Max(n**k, log x)` with a `nan` child; live seed 7, the atan2 firing cap. It
also had timeouts, because three gate runs were sharing the machine. All of
these are 0 here.

An earlier side-by-side run, before the merge and against 2fd72b8, compared
the two trees output by output. Every change was an improvement:
- the atan2 firing-cap crashes are gone
- `atan2(exp(n), sign(z))` at `z = 0` now gives `pi/2`, like v3
- `re(...cos(atan2(im z, re z)/2))` now gives v3's form
- `atan2(1/(y+1), 1/m)` and `asinh(sinh(1/sqrt(m)))` now fire, like v3

## 4. Refusal timings, Min/Max-heavy battery cases

Method: `bench-container` (image `benchmark-sympy:local`, CPU 10, domain
reservation), the orion SymPy checkout copied in, and the 88 battery cases
from `test_minmax_deltas.py`. Each case ran in a fresh process per tree; the
SymPy cache was cleared before every call; 1 warmup repetition was discarded
and 2 kept; 3 rounds alternated the tree order. Figures are per-case medians.
"Before" is `origin/refine-identities` 8f0e147 (rule rows); "after" is
1610aeb. Script: `time_minmax.py` in the session scratchpad (not committed).

| | before | after |
| --- | --- | --- |
| 23 refusals, total | 25.8 s | 5.9 s (4.4x faster) |
| 65 rewrites, total | 41.9 s | 12.6 s |
| `Max(x, y, z)`, three real arguments | 5.08 s | 0.46 s |
| `Max(x, y)`, `Q.real(x)` | 3.35 s | 0.36 s |
| `Max(x, y)`, `Q.positive_infinite(x)` | 2.48 s | 0.02 s |
| `Max(x, y)` and `Min(x, y)`, two real arguments | 1.67 s, 1.73 s | 0.19 s, 0.15 s |
| `KroneckerDelta(i, j)`, two integer arguments | 2.26 s | 0.10 s |
| `KroneckerDelta(i, j, (1, 3))`, `Q.eq(i, j)` | 0.25 s | 3.55 s (slower) |

Nearly all of the cost is SymPy's `Q.eq` query, about 0.6 s each on the
combined backend. The rule rows asked it for every ordered pair. The
decider asks `Q.eq`/`Q.ne` only when the assumptions state a relation.
Without that restriction the refusals took as long as before (25.4 s against
24.8 s, measured before the merge). The one slower case states `Q.eq`, so
the range conditions ask the relation atoms.

The experiment's numbers (about 2 ms per refusal, the basis of "Piecewise in
`opaque` is about 5x slower") were a measurement artifact. Its `Holds`
decider had a process-wide `lru_cache`, so repeated runs read cached
answers. In the same harness it measured 0.18 s for all refusals, and that
comes from the cache.

## 5. Open problems

- `needs/test_engine_reciprocal_of_zero.py`: `1/x` under `Q.zero(x)` should
  be `zoo` (a power_exp_log row). This restores the battery case above.
- `KroneckerDelta(x, z)` with `z` imaginary and `x` positive: v3 gives `0`,
  identities refuses (differential seed 2, before and after this branch).
  `ne` has no proof form for "one argument real, the other not". This is a
  stage-0 row candidate.
- The `Q.eq`/`Q.ne` restriction (asked only under stated relations) is a
  cost cut. An equality that follows from no stated relation, only from
  arithmetic, is still found through `Q.zero(u - v)`.

## 6. Commits on `ri/engine2`

3c04fc2, b08b2db, bf7b5ff, 1077318 (engine, minmax, tests); c74ca55
(report draft); merge of refine-identities; b2c1589 (hash seed,
MatrixElement, `Q.eq` cost); merge 1610aeb (refine-identities up to
8f0e147); the needs test; the final report commit.
