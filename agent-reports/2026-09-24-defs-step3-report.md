# Phase 2 step 3: definitions for the plain families (agent "defs")

- **Date:** 2026-09-24 and 25
- **Branch:** `ri/defs`, from `origin/refine-identities` at `2fd72b8`,
  with `origin/main` at `9dfc27d` merged in (satassume prover gaps, PR #3)
- **TL;DR:** integer_funcs drops from 17 rule rows to 9 rows (2 identity
  rows and 7 rules). Of the 8 rows removed:
  - 6 come from definitions and shared rows;
  - 2 come from the new satassume, which proves `re` and `im` of
    `floor(y)` are integers.

  The battery is identical to the baseline in both `SATREFINE_IDENTITIES`
  modes, measured against the same satassume version (0 wrong, 0 crash).
  Of the four definitions in the plan, only `frac(x) = x - floor(x)` pays.
  Combinatorial through `gamma` does not pay: each function keeps every row
  (numbers in section 3), so it is unchanged. Matrices is untouched.

## 1. integer_funcs

| | phase 1 (`2fd72b8`) | after |
| --- | --- | --- |
| rows (FACTS + RULES) | 0 + 17 | 2 + 7 |
| generated rules | 0 | 11, all verified |
| family code lines (excluding blanks, comments, docstrings) | 49 | 52 |
| generation time (`refine_specialize.py --write --family integer_funcs`) | none | 173 to 210 s at load 18 to 20 on 12 cores |

### Rows

- **`frac(x) = x - floor(x)`**, an identity row.
  - Domain: `Q.finite(x) | Q.real(x)`, or a Gaussian integer. `ask`
    does not derive finiteness from stated bounds or from integral
    `re`/`im`, so those cases are spelled out.
  - It fires only when `floor` collapses and the count of `frac` nodes
    drops.
  - It replaces `frac` of an integer (through floor's integer row) and
    `frac(x) = x` on `[0, 1)` (through the interval reasoning in
    `_simple.py`).
  - Beyond v3, it gives `frac(x) = x - k` on `[k, k + 1)`.
- **One shift row over a generic head, now shared with `frac`**:
  `F(n + x) = F(x) + F(n)` for `n` an integer or a Gaussian integer
  (`Q.integer(re(n)) & Q.integer(im(n))`). `F(n)` then reduces to `n`,
  `n` or `0`.
  - This replaces `frac`'s own three shift rows.
  - With satassume `9dfc27d` it also replaces the four
    `floor(y)`/`ceiling(y)` rows (2 shared by floor and ceiling, 2 for
    frac). Floor's integer row takes Gaussian integers too.
- **`G(a, b) = b*G(sign(a/b), 2)/2` for odd `2*a/b`**, shared by `Mod`
  and `Rem`.
  - It uses `Mod(+-1, 2) = 1` and `Rem(+-1, 2) = +-1`.
  - It is an identity row with `sign` opaque, and it replaces `Mod`'s
    `b/2` row and `Rem`'s two `+-b/2` rows.
  - The engine and the generator need a concrete head, so the module
    instantiates the row per head with `_instance` (one `replace`); the
    stated row is counted once.
  - Beyond v3, the sign split gives `Rem(a, b) -> Abs(b)/2` for
    positive `a`.
- **Unchanged rules**: floor/ceiling of an integer; `Mod`/`Rem` of a
  multiple; `Mod` shift; `Mod` and `Rem` inside the period; `Mod = Rem`
  for equal signs.

**Lost against phase 1** (not in the battery, the tests or v3):
`Mod(a, b) -> b/2` for odd `2*a/b` when the signs of both `a` and `b` are
unknown. The `G` row needs `sign(a/b)` decided, or a sign split on one
symbol whose cases agree, and the engine does not nest splits.

### Runtime form

Each definition is a plain `identity_handler` row with an ordering (the
count of the row's head nodes). The result comes back in the user's
function, or the row does not fire. No fold-back machinery is needed:
the domains below rule out every case where a fold would have paid.

### Definitions tried and not used (measured)

- **`ceiling(x) = -floor(-x)`**: every ceiling row is already a floor row
  through the generic head `F`, so the definition removes nothing. Its
  shifts would also need a fold from `-floor(-u)` back to `ceiling(u)`.
- **`Mod(a, b) = a - b*floor(a/b)`** (domain: real `a`, real nonzero `b`):
  with it in place of the Mod rows, 7 tests fail. It derives none of the
  rows it replaces:
  - the half-integer case needs a floor row for half-integers;
  - the shift leaves `x - b*floor(x/b)`. That needs a fold back to `Mod`
    and a complex domain, because SymPy also has
    `Mod(x + 2*n, 2) = Mod(x, 2)` for complex `x`;
  - `floor(a/b) = 0` for `0 <= a < b` is beyond the interval reasoning,
    which handles only affine arguments with numeric coefficients.

  SymPy's `Mod` does not follow the formula for non-real arguments. On a
  16 x 19 grid every real/real pair agrees; complex pairs stay unevaluated
  or are reduced Gaussian-style (`Mod(-3*I, 2*I) = -I`).
- **`Rem` by truncation** (`a - b*sign(a/b)*floor(Abs(a/b))`): it hits
  the same obstacles. Its only derivable case is what the `G` row states.
- **frac's shifts through the definition, folded back**: the definition
  is false at `+-oo` (`frac(oo) = AccumBounds(0, 1)`, while
  `oo - floor(oo)` is `nan`). Its domain must therefore be finite `x`,
  and the shifts of an unconstrained `x` in the tests and battery would be
  lost. The shared shift rows hold at infinity.

### Known gap: `floor(x) + frac(x)`

`floor(x) + frac(x)` under `Q.real(x)` is still not rewritten to `x`, in
either mode. Refinement is per node, and the `frac(x)` node never sees the
`floor(x)` term. A rule over sums (key `Add`, `floor(x) + frac(x) -> x`
matched as two terms of a longer sum) would close the gap. No `Add`
handler exists, and adding one would run the matcher on every sum, so I
did not add it.

## 2. Gates, against the same satassume version

Baseline: `2fd72b8` merged with `origin/main` `9dfc27d`, built in a
scratch clone. This branch has the same merge.

**Battery (full scoreboard, `PYTHONHASHSEED=0`)**: in both generated and
live mode, every family is identical to the baseline.

| family | same | other | miss | quiet | extra | wrong | crash |
| --- | --- | --- | --- | --- | --- | --- | --- |
| integer_funcs | 67 | 0 | 0 | 31 | 0 | 0 | 0 |

- The merge of `main` itself moves inverse (quiet 164 to 160, extra 12
  to 16) and power_exp_log, in the baseline as well as here. This is
  satassume's doing, not this branch's.
- `PYTHONHASHSEED` is fixed because one power_exp_log case depends on it
  on the baseline too: `log(1/x) | Q.zero(x)` gives `zoo` for seeds 0
  and 1 and stays unchanged for seeds 2 and 3. That is a pre-existing
  hash-order dependence in the engine.
- Before the merge (on satassume as of `2fd72b8`) the 11-row version was
  also identical to that baseline in both modes.

**Tests (`tests/refine_identities`)**: 2200 passed, 13 failed. None of
the failures come from this branch:

- 5 existing needs tests;
- my 2 new needs tests (section 5);
- 6 that fail identically on the merged baseline:
  - `test_ablate::test_ablate_removes_the_row_from_handler_and_module`:
    `Max(x, y)` still refines to `x` with its row ablated;
  - `test_power_exp_log::test_relation_to_team[exp(I*pi*n/2 + x)|Q.odd(n)]`;
  - `test_generated_module_is_up_to_date[power_exp_log]` and
    `[complex_parts]`;
  - `test_specialize::test_expected_rules_are_generated` and
    `test_generated_rules_verify_or_are_flagged`. The
    `log(p*r) -> log(-p) + log(-r)` rule is no longer generated; these
    two and `[complex_parts]` already fail on `2fd72b8` without the
    merge.

`test_engine_integer_funcs.py::test_ask_raising_is_not_provable` failed
after the merge, because satassume now proves `Q.lt(m, y)` from
`Q.positive(y) & Q.negative(m)`, so the rule legitimately fires. The test
now simulates the raising `ask` with a monkeypatch.

**Ablation (`tools/refine_ablate.py integer_funcs`, 9-row pre-merge
layout)**: all 9 rule rows are needed. The tool ablates `RULES` only, so
the 2 identity rows were checked by hand in live mode: without the frac
definition 8 of 142 integer_funcs tests fail, and without the `G` row 11
fail.

Before this could run I fixed the tool (8 lines, commit "refine_ablate:
remove rows from every table of a chained key"):

- it removed rows only from a key's top-level handler, so for a `chain`
  (frac, Mod and Rem here, and power_exp_log) they stayed live;
- the first, unfixed run therefore reported 5 of 9 rows as droppable,
  and they were not;
- `tools/refine_ablate.py` is not in the engine's ownership list.

**Differential** (seeds 2, 3, 7 at 1,500 cases, both modes, against the
merged baseline, `PYTHONHASHSEED=0`): see section 4.

## 3. combinatorial: measured "not worth it"

The prototype added each definition as an identity row with `gamma`
opaque, each with its pole-free domain:

- `factorial(n) = gamma(n + 1)`
- `binomial = gamma(n+1)/(gamma(k+1)*gamma(n-k+1))`
- `rf = gamma(x+k)/gamma(x)`
- `ff = gamma(x+1)/gamma(x-k+1)`

It then removed each function's own rows, keeping the shared `k = 0`/`k =
1` rows. Failing tests of `test_combinatorial.py` (110 tests, satassume as
of `2fd72b8`):

| function | rows | tests failing with the definition and without the rows | rows the definition replaces |
| --- | --- | --- | --- |
| factorial | 2 | 5 | 0 |
| binomial | 4 | 9 | 0 |
| RisingFactorial | 3 | 7 | 0 |
| FallingFactorial | 3 | 4 | 0 |

Why none are replaced:

- **Relation hypotheses.** The rows' hypotheses are relations (`n == k`,
  `x == 1`, `k == 0`), and the identity engine does not substitute proven
  equalities. So `binomial(n, k)` under `Q.eq(n, k)` never reaches
  `gamma(n+1)/(gamma(n+1)*gamma(1))`.
- **Poles.** Every zero and pole row lives where the gamma ratio is not
  the definition (`rf(-2, 2) = 2`, but `gamma(0)/gamma(-2)` is `nan`), so
  the domain excludes exactly those cases.
- **Target forms.** Where the ratio does collapse, v3 wants either the
  gamma form itself (the `rf` gamma row) or factorials, which needs the
  `gamma -> factorial` rows anyway.

The prototype was reverted; `combinatorial.py` is unchanged.

## 4. Differential

(filled in below)

## 5. Needs tests filed

- `tests/refine_identities/needs/test_defs_case_split_zero_point_raises.py`
  (engine): the case split evaluates the left side at `s = 0`, where
  `Rem(a, 0)` raises `ZeroDivisionError`, and the error escapes `refine`.
  integer_funcs works around it with `Q.nonzero(b)` in the domain, which
  is true anyway.
- `tests/refine_identities/needs/test_defs_render_one_symbol.py`
  (generator): for a single symbol, `render_module` writes
  `x, = symbols('x')`, which breaks the import of the whole `generated`
  package. I hit it when integer_funcs' table was `frac(x) -> 0` alone;
  the table now has more symbols.
