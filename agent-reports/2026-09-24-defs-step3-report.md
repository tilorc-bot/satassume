# Phase 2 step 3: definitions for the plain families (agent "defs")

- **Date:** 2026-09-24 and 25
- **Branch:** `ri/defs`, from `origin/refine-identities` at `2fd72b8`,
  with `origin/main` `9dfc27d` (satassume prover gaps) and then
  `origin/refine-identities` `8f0e147` merged in
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

**Method.** `tools/refine_gates.sh` run on this branch at `307c304`, which
is `ri/defs` with `origin/refine-identities` `8f0e147` merged in. The
baseline is the coordinator's shared run of `8f0e147`
(`/home/tilo/fable-rewrite/.claude/gates/base-8f0e147`). Every run uses
`PYTHONHASHSEED=0`. Two notes on completeness:

- This branch's first run of differential generated seed 7 hit the
  30-minute timeout under load. I re-ran it with the updated tool, and it
  finished with exit 0.
- The baseline's generated seed 7 had also timed out and was not yet
  re-run when I compared. For that seed, only this branch's absolute
  numbers are available.

**Battery (scoreboard).** Identical to the baseline, family by family, in
both modes. integer_funcs has 67 same, 0 other, 0 miss, 31 quiet,
0 extra, 0 wrong, 0 crash in both modes. The totals are:

| mode | same | other | miss | quiet | extra | wrong | crash |
| --- | --- | --- | --- | --- | --- | --- | --- |
| generated | 1,030 | 43 | 13 | 629 | 21 | 0 | 0 |
| live | 1,033 | 40 | 13 | 629 | 21 | 0 | 0 |

**Test suite (`tests/refine_identities`, xdist).** 2,329 passed and 8
failed. The baseline has 6 failures, all needs tests, and all 6 fail here
too. The other 2 failures are my two new needs tests (section 5).

**Differential (seeds 2, 3, 7 at 1,500 cases, both modes).**

- No new unsound result, no numerically different result, and no new
  crash. Unsound counts for b are 2, 3, 1 in each mode, as in the
  baseline. "Different" is 0 everywhere.
- Live seed 3 has 1 crash and live seed 7 has 1 crash; both are in the
  baseline too (the atan2 firing cap).
- Live seeds 3 and 7 are identical to the baseline.
- Generated seed 3 differs only in timeouts: 2 in the baseline, 0 here.
- Seed 2 fires on 2 more inputs than the baseline in generated mode and
  on 3 more in live mode ("only b fires" +2 in each mode). Unsound and
  numerically different counts are unchanged. The per-case output was
  not kept (`--summary`), and the timeout counts also differ between the
  runs (load).
- An earlier full run on the pre-merge code, which printed examples,
  showed the single new firing at seed 3 was
  `frac(pi*z) | Q.zero(z) & Q.ge(z, 0) -> pi*z`, which is correct. It
  comes from the frac definition.
- Generated seed 7 here: 456 fired, 1 unsound (v3 also has 1), 0
  different, 0 crash.

**Ablation (`tools/refine_ablate.py integer_funcs`, run on the 9-rule
layout before the Gaussian merge).** All 9 rule rows are needed. The tool
ablates `RULES` only, so the 2 identity rows were checked by hand in live
mode: without the frac definition 8 of 142 integer_funcs tests fail, and
without the `G` row 11 fail.

Before this could run I fixed the tool (8 lines, commit "refine_ablate:
remove rows from every table of a chained key"):

- it removed rows only from a key's top-level handler, so for a `chain`
  (frac, Mod and Rem here, and power_exp_log) they stayed live;
- the first, unfixed run therefore reported 5 of 9 rows as droppable,
  and they were not;
- `tools/refine_ablate.py` is not in the engine's ownership list.

The Gaussian-integer merge then removed 2 of the 9 rules by construction.
The ablation was not re-run after that.

**Earlier comparisons, superseded by the run above.** These ran on the
older merges, against baselines built the same way:

- the 11-row version on satassume as of `2fd72b8`: battery identical in
  both modes; differential seeds 2 and 3 in both modes with the same
  counts except the one sound `frac` firing;
- the 9-row version with `main` `9dfc27d`: battery identical in both
  modes.

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

See section 2.

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

## 6. Commits on `ri/defs`

`git log --oneline --no-merges origin/refine-identities..ri/defs`: the
integer_funcs rows, generated table and tests, the needs tests, the
`refine_ablate.py` fix, and this report. Merges from `origin/main`
`9dfc27d` and from `origin/refine-identities` (`599af95`, `8f0e147`). The
merge conflict in `test_engine_integer_funcs.py` (both sides simulated the
raising `ask`) was resolved to `refine-identities`' version.
`combinatorial.py` is unchanged.
