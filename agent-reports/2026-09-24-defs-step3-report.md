# Phase 2 step 3: definitions for the plain families (agent "defs")

- **Date:** 2026-09-24
- **Branch:** `ri/defs` (from `origin/refine-identities` at `2fd72b8`)
- **TL;DR:** integer_funcs goes from 17 rule rows to 11 rows (2 identity
  rows, 9 rules). The battery is unchanged in both `SATREFINE_IDENTITIES`
  modes, with 0 wrong and 0 crash. Only one of the four definitions the
  plan named pays for itself: `frac(x) = x - floor(x)`. Combinatorial
  through `gamma` does not pay: each of its four families keeps every row
  when its definition is added (the numbers are in section 3), so it is
  left unchanged. Matrices is untouched.

## 1. integer_funcs: what changed

| | before | after |
| --- | --- | --- |
| rows (FACTS + RULES) | 0 + 17 | 2 + 9 |
| generated rules | 0 | 11 (all verified) |
| family code lines (no blanks, comments or docstrings) | 49 | 52 |
| generation time (`refine_specialize.py --write --family integer_funcs`) | n/a | 173 s on a loaded machine (load 18 on 12 cores) |

Rows:

- **`frac(x) = x - floor(x)`**, an identity row with domain
  `Q.finite(x) | Q.real(x)`. It fires only when `floor` collapses and the
  count of `frac` nodes drops. It replaces `frac` of an integer (through
  floor's integer row) and `frac(x) = x` on `[0, 1)` (through the
  interval reasoning behind `floor`). It also gives `frac(x) = x - k` on
  `[k, k + 1)`, which v3 does not.
- **Shift rows over a generic head, now shared with `frac`:**
  `F(n + x) = F(x) + F(n)` (and the two Gaussian-integer rows in the same
  form). `F(n)` then reduces to `n`, `n` or `0`, so `frac`'s own three
  shift rows are gone.
- **`G(a, b) = b*G(sign(a/b), 2)/2` for odd `2*a/b`**, shared by `Mod` and
  `Rem` (`Mod(+-1, 2) = 1`, `Rem(+-1, 2) = +-1`). It is an identity row
  with `sign` opaque and replaces `Mod`'s `b/2` row and `Rem`'s two
  `+-b/2` rows. The engine and the generator need a concrete head, so the
  module instantiates the row per head with `_instance` (one `replace`);
  the stated row is counted once. Beyond v3, the sign split gives
  `Rem(a, b) -> Abs(b)/2` for positive `a`.
- The other rules are unchanged: floor/ceiling of an integer, `Mod`/`Rem`
  of a multiple, `Mod` shift, `Mod` and `Rem` inside the period, and
  `Mod = Rem` for equal signs.

Lost against phase 1 (not in the battery, the tests or v3):
`Mod(a, b) -> b/2` for odd `2*a/b` when neither the sign of `a` nor the
sign of `b` is known. The `G` row needs `sign(a/b)` decided, or a sign
split on a single symbol whose cases agree, and the engine does not nest
splits.

### Definitions tried and not used (measured)

- **`ceiling(x) = -floor(-x)`**: every ceiling row is already a floor row
  through the generic head `F`, so the definition removes no row, and its
  shifts would need a fold from `-floor(-u)` back to `ceiling(u)`.
- **`Mod(a, b) = a - b*floor(a/b)`** (domain: real `a`, real nonzero `b`):
  with it in place of the Mod rows, 7 tests fail and it derives none of
  them.
  - The half-integer case would need a floor row for half-integers.
  - The shift leaves `x - b*floor(x/b)`. That needs a fold back to `Mod`,
    plus a complex domain, because `Mod(x + 2*n, 2) = Mod(x, 2)` also
    holds in SymPy for complex `x`.
  - `floor(a/b) = 0` for `0 <= a < b` is beyond the interval reasoning in
    `_simple.py`, which handles only affine arguments with numeric
    coefficients.
  - SymPy's `Mod` does not follow the formula for non-real arguments:
    checked on a 16 x 19 grid, every real/real pair agrees; complex pairs
    are left unevaluated or reduced Gaussian-style (`Mod(-3*I, 2*I) = -I`).
- **`Rem` by truncation** (`a - b*sign(a/b)*floor(Abs(a/b))`): it runs
  into the same obstacles. Its only derivable case is what the `G` row
  now states.
- **frac's shifts through the definition, folded back**: the definition
  is false at `+-oo` (`frac(oo) = AccumBounds(0, 1)`, `oo - floor(oo) =
  nan`), so its domain must be finite `x`. The test and battery shifts
  have an unconstrained `x`, so they would be lost. The shared shift rows
  hold at infinity, so they stay.

Runtime form: plain `identity_handler` rows with an ordering (the count of
the row's head nodes). A result comes back in the user's function, or the
row does not fire. No fold-back machinery is needed, because the domains
above rule out every case where a fold would have paid.

### Known gap: `floor(x) + frac(x)`

Under `Q.real(x)`, `floor(x) + frac(x)` is still not rewritten to `x`,
in both modes. Refinement works one node at a time, and the `frac(x)`
node never sees the `floor(x)` term. A rule over sums (key `Add`,
`floor(x) + frac(x) -> x` matched as two terms of a longer sum) would
close the gap. No `Add` handler exists today, and adding one would run
the matcher on every sum, so I did not add it.

## 2. Gates

The baseline is `2fd72b8`, measured in this worktree before any change.

**Battery (full scoreboard).** Generated and live mode are both identical
to the baseline in every family: integer_funcs 67 same, 0 other, 0 miss,
31 quiet, 0 extra, 0 wrong, 0 crash, and all other families unchanged.

One case moved between runs: `log(1/x) | Q.zero(x)` (power_exp_log) came
out as `zoo` or unchanged depending on `PYTHONHASHSEED`. The same flip
reproduces on the baseline (seeds 0 and 1 give `zoo`, seeds 2 and 3 give
`log(1/x)`, on both the base and this branch). Reruns with
`PYTHONHASHSEED=0` match the baseline exactly in both modes. That
hash-order dependence is a pre-existing engine issue.

**Tests (`tests/refine_identities`).** 2194 passed and 13 failed. All 13
failures also occur on the baseline or come from needs tests:

- 8 are the existing needs tests.
- 2 are my new needs tests (below).
- `test_generated_module_is_up_to_date[complex_parts]`,
  `test_specialize::test_expected_rules_are_generated` and
  `test_specialize::test_generated_rules_verify_or_are_flagged` fail
  identically on the baseline `2fd72b8` when run alone. The
  `log(p*r) -> log(-p) + log(-r)` rule is no longer generated. This is
  not caused by this branch, but the engine owner should know.

**Ablation (`tools/refine_ablate.py integer_funcs`).** All 9 rule rows are
needed, and none is droppable. The tool ablates `RULES` only, so the 2
identity rows were checked by hand in live mode: without the frac
definition 8 of 142 integer_funcs tests fail, and without the `G` row 11 fail.

Before this could run I fixed the tool: it removed rows only from a
key's top-level handler. For a `chain` (frac, Mod and Rem here, and
power_exp_log) the rows stayed live, so rows looked droppable when they
were not. The first run reported 5 of 9 rows as droppable. The tool now
walks `chain` parts (commit "refine_ablate: remove rows from every table
of a chained key"). `tools/refine_ablate.py` is not in the engine's
ownership list; the change is 8 lines.

**Differential, seeds 2, 3, 7 at 1,500 cases, both modes, against the
baseline:** see section 4.

## 3. combinatorial: measured "not worth it"

Prototype: each definition was added as an identity row with `gamma`
opaque (`factorial(n) = gamma(n + 1)`,
`binomial = gamma(n+1)/(gamma(k+1)*gamma(n-k+1))`,
`rf = gamma(x+k)/gamma(x)`, `ff = gamma(x+1)/gamma(x-k+1)`, each with its
pole-free domain). Then each function's own rows were removed, keeping
the shared `k = 0`/`k = 1` rows. Failing tests of `test_combinatorial.py`
(110 tests):

| function | rows | tests failing with definition, without rows | rows the definition replaces |
| --- | --- | --- | --- |
| factorial | 2 | 5 | 0 |
| binomial | 4 | 9 | 0 |
| RisingFactorial | 3 | 7 | 0 |
| FallingFactorial | 3 | 4 | 0 |

Why none are replaced:

1. **Relation hypotheses.** The rows' hypotheses are relations (`n == k`,
   `x == 1`, `k == 0`), and the identity engine does not substitute
   proven equalities, so `binomial(n, k)` under `Q.eq(n, k)` never
   reaches `gamma(n+1)/(gamma(n+1)*gamma(1))`.
2. **Poles.** Every zero and pole row lives where the gamma ratio is not
   the definition (`rf(-2, 2) = 2`, while `gamma(0)/gamma(-2)` is `nan`),
   so the domain excludes exactly those cases.
3. **Folds.** Where the ratio does collapse, v3 wants either the gamma
   form itself (the `rf` gamma row) or factorials, which needs the
   `gamma -> factorial` rows anyway.

The prototype was reverted; `combinatorial.py` is unchanged.

## 4. Differential

(filled in below)

## 5. Needs tests filed

- `tests/refine_identities/needs/test_defs_case_split_zero_point_raises.py`
  (engine): the case split evaluates the left side at `s = 0`, and
  `Rem(a, 0)` raises `ZeroDivisionError` out of `refine`. integer_funcs
  works around it with `Q.nonzero(b)` in the domain (true anyway).
- `tests/refine_identities/needs/test_defs_render_one_symbol.py`
  (generator): `render_module` writes `x, = symbols('x')` for one symbol,
  and that breaks the import of the whole `generated` package. I hit it
  when integer_funcs' table was `frac(x) -> 0` alone; the table now has
  more symbols.

## 6. Commits

See `git log origin/refine-identities..ri/defs`.
