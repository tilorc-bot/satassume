# Report: two prover gaps closed in satassume (refine-identities plan, step 5)

- **Date:** 2026-09-25
- **Branch:** `satassume-prover-gaps`, from `origin/main` at aae73f2. A PR against `main`
  is open and not merged.
- **Read this if:** you maintain `satassume/templates/` or the refine-identities rows for
  `power_exp_log` and `integer_funcs`.
- **TL;DR:** `ask` now shows that `(n - 1)/2` is an integer for odd `n`, and that `re` and
  `im` of `floor(y)` and `ceiling(y)` are integers for finite `y`.
  - Both are general rules in the structural templates, not special cases.
  - The satassume suite passes, and the corpus replay shows 0 wrong answers (10 new
    correct extra answers).
  - The benchmark shows no slowdown: the corpus replay takes 1.459 s against 1.478 s
    before, and 8 microbenchmarks are within 1%.
  - On the refine side, `log(x**n)` for negative `x` and odd `n` gets v3's form in live
    mode, and `exp(I*pi*n/2)` for odd `n` now folds.
  - The 4 Gaussian-integer rows of `integer_funcs` can fold into the 2 shift rows
    (17 rows to 13) with the battery unchanged. That edit is refine-side and was tested
    only in a scratch copy.

## 1. Parity of sums with half-integer coefficients

**The gap.** SymPy writes `(n - 1)/2` as `Add(-1/2, Mul(1/2, n))`. The `Add` template's
integer closure needs every term to be an integer, and `n/2` is not one for odd `n`. So
`Q.integer((n - 1)/2)` under `Q.odd(n)` was None.

**The general form.** Take a sum `N = c0 + sum(c_k*t_k)` with rational coefficients `c_k`
and terms `t_k`. Let `D` be the least common denominator of the coefficients. Then
`D*N = a0 + sum(a_k*t_k)` with integers `a_k = D*c_k`. If every `t_k` is an integer, `N`
is an integer iff `D` divides `a0 + sum(a_k*t_k)`.

The predicate vocabulary has residues only modulo 2 (`even`/`odd`), so this is decidable
from the terms' facts exactly when `D = 2`. For `D = 2` the numerator is an integer whose
parity is `a0` plus the number of odd `t_k` with odd `a_k` (mod 2). `N` is an integer iff
that parity is even, and `N` is rational either way. The template emits:

- all `t_k` integer implies `N` rational;
- for each parity assignment to the odd-coefficient terms (at most `MAX_HALF_ODD = 4` of
  them, so at most 16 rules), all `t_k` integer plus that assignment implies `N` integer
  or `N` not an integer.

The backward direction needs no extra rules. For example, `n` odd follows from
`(n - 1)/2` and `n` being integers: the solver refutes the other parity by search.

**Implementation.** `satassume/templates/core.py`, `_half_split`, `_half_rules` and
`_half_templates`, called from `add_templates`.

- **Which sums get the rule:** an `Add` whose coefficients have a denominator of 2 and
  none larger. The coefficient of a term is the first factor of a `Mul` with a Rational
  first factor; otherwise it is 1.
- **Derived nodes:** a term `c*x*y` gets `x*y` as a derived node, as `Pow` does with `2*e`.
- **Cost on every other sum:** one pass over the arguments with an `is_Rational` check.
- **Not covered:** denominators above 2, such as `(n - 1)/4` or `n/2 + m/3`. They need
  residues modulo `D`, which the vocabulary lacks; `n/2 + m/3` stays None, and a test
  records that. Products such as `n*(n + 1)/2` are also not covered: they need
  "consecutive integers" reasoning, not linear parity.

## 2. `re` and `im` of `floor` and `ceiling`

For finite `y`, SymPy rounds each part: `floor(y) = floor(re(y)) + I*floor(im(y))`. So
`re(floor(y))` and `im(floor(y))` are integers. The vocabulary has no Gaussian-integer
predicate, so the new template in `satassume/templates/functions.py`,
`parts_of_round_templates`, looks through one level of structure. It is registered for
`re` and `im`, applies only when the argument is `floor(y)` or `ceiling(y)`, and emits
`finite(y)` implies `integer(node)`.

With it, `ask(Q.integer(re(n)) & Q.integer(im(n)), ...)` is True for `n = floor(y)` or
`ceiling(y)` under `Q.finite(y)`, and also for any integer `n`. That is the hypothesis
the refine rows need (section 5).

## 3. Tests

`tests/test_prover_gaps.py` has 27 tests:

- the gap cases and their negations (even `n` gives False);
- the undecided cases (`Q.integer(n)` alone; `n/2 + m/3`);
- the backward direction, and that the sum is rational (and not an integer for even `n`);
- `exp(I*pi*(n - 1)/2)` real for odd `n`;
- `re`/`im` of `floor`/`ceiling` under `finite`, `complex` and `imaginary`, and None
  without facts;
- concrete values of `floor`/`ceiling` of complex numbers;
- a randomized check against values: 300 random half-coefficient sums over up to 3
  symbols with even/odd/integer facts. Every definite `integer`/`even`/`odd` answer (more
  than 200 of them) is checked at every combination of 5 values per symbol.

`tests/test_templates.py` gained 10 sums and 5 `re`/`im`-of-rounding expressions in its
three-valued soundness check against concrete values.

## 4. Suite, corpus and benchmark

- **Suite:** the full `tests/` directory, one file per process, before (aae73f2) and
  after. Every file passes in both. The only difference is the new tests:
  `test_templates.py` goes from 399 to 429, and `test_prover_gaps.py` adds 27. The
  xfails (euf_fuzz 2, relations 2, shared_facts 1) and the 1 skip are unchanged.
- **Corpus** (`tools/compare.py queries.jsonl --in-scope-only`): before, agree 2497,
  extra 16, none 70, error 5, wrong 0. After, agree 2487, extra 26, none 70, error 5,
  wrong 0. The 10 new extras are `Q.integer((-1)**x/2 + c)` for half-odd constants `c`
  under `Q.integer(x)` (5 queries, each recorded twice). These are correct:
  `(-1)**x = +-1`, so the numerator `+-1 + 2c` is even. SymPy answers None.
- **Benchmark:** `bench-container`, image `benchmark-sympy:local`, CPU slot 10 with its
  frequency domain reserved, `PYTHONHASHSEED=0`, base and new alternated
  (base, new, new, base) over 6 rounds.
  - Corpus replay time (satassume side): base 1.478 s, new 1.459 s (mean of 12 each).
  - `tools/bench.py` (300 repetitions, two passes each): every one of the 8 queries is
    within 1% (for example 51.8 against 52.0 us, and 127.5 against 128.8 us).
  - No regression on the `Add` hot path.

## 5. Effect on the refine side (scratch copies, no refine files edited)

The scratch copies were made from `refine-identities` at a4f920f (with ri/matfuzz merged)
and have satassume replaced:

- **A:** `main`'s satassume (aae73f2), the reference.
- **B:** this branch's satassume.
- **C:** B, plus the integer_funcs fold described below.
- **D:** B, with `generated/power_exp_log.py` regenerated.

Scoreboard families `power_exp_log`, `trig` and `integer_funcs` were run with
`PYTHONHASHSEED=0`. Columns are same as v3 / other form / miss / unchanged as required /
extra / wrong / crash.

| run | power_exp_log | trig | integer_funcs |
| --- | --- | --- | --- |
| A generated | 98/3/3/66/3/0/0 | 216/0/0/36/0/0/0 | 67/0/0/31/0/0/0 |
| B generated | 98/3/3/65/4/0/0 | same | same |
| C generated | 98/3/3/65/4/0/0 | same | same (13 rows instead of 17) |
| D generated | 98/3/3/65/4/0/0 | same | same |
| A live | 99/2/3/66/3/0/0 | same | same |
| B live | **100/1/3/65/4/0/0** | same | same |
| C live | 100/1/3/65/4/0/0 | same | same (13 rows instead of 17) |

Rows and forms that improve:

- **`log(x**n)` under `Q.negative(x) & Q.odd(n)`:** live mode now gives v3's
  `n*log(-x) + I*pi` (it was `log(-x**n) + I*pi`). This is the "same" +1 in B live.
  - Regenerating the table (D) changes the generated row to the clean form:
    `(log(b**e), log(-b**e) + I*pi, ...)` becomes `(log(b**e), e*log(-b) + I*pi, ...)`.
  - Generated mode still gives the old form, because the table puts the generic row
    `(log(x), log(-x) + I*pi, Q.negative(x))` before the power rows. That ordering
    belongs to the engine agent.
  - `log(x**3)` has the same issue in generated mode.
- **`exp(I*pi*n/2)` and `exp(I*pi*n/2 + x)` under `Q.odd(n)`:** these now fold to
  `(-1)**(n/2 + 3/2)*I` and `(-1)**(n/2 + 3/2)*I*exp(x)`. That is the "extra" +1: v3's
  test expects it unchanged, and the result is correct (`I**n = I*(-1)**((n-1)/2)`).
  - `exp(I*pi*(n - 1)/2)` now gives `(-1)**(n/2 + 3/2)`; before, it gave
    `-I*exp(I*pi*n/2)`.
  - One refine test encodes the old behaviour and now fails:
    `test_power_exp_log.py::test_relation_to_team[exp(I*pi*n/2 + x)|Q.odd(n)]`. It
    should be updated on the refine side.
- **integer_funcs, 4 rows fold (17 to 13).** In C, the shift rows' hypothesis
  `Q.integer(n)` becomes `Q.integer(re(n)) & Q.integer(im(n))` (a Gaussian integer). The
  two `floor(y) + x` / `ceiling(y) + x` shift rows and the two matching `frac` rows are
  then removed.
  - The battery is identical in both modes.
  - `test_integer_funcs.py` and `test_engine_integer_funcs.py` pass except for two
    tests. `test_table_size_and_registration` expects 17 rows. `test_ask_raising_is_not_provable`
    fails in A and B too; that is `main`'s relation work, and it is the baseline agent's
    item.
  - The row edit is for the refine-side owner:
    `(F(n + x), n + F(x), Q.integer(re(n)) & Q.integer(im(n)))` and
    `(frac(n + x), frac(x), Q.integer(re(n)) & Q.integer(im(n)))`.
- **`ceiling(re(floor(y)))` under `Q.finite(y)`** now gives `re(floor(y))`.
- **Trig:** no battery change. The shifts by odd multiples of `pi/2` (`sin(x + pi*n/2)`,
  `cos(pi*n/2)`, `tan(x + pi*n/2)`) already gave the same results in A and B.

## 6. Open

- Refine side, for its owners:
  - put the power rows before the generic negative-argument `log` row in the generated
    table (or regenerate with an order that does);
  - apply the integer_funcs fold;
  - update the `exp(I*pi*n/2 + x)` expectation.
- Denominators above 2 need residue predicates the vocabulary does not have. I did not
  add them.
- I did not run a refine differential with this satassume. On the satassume side,
  soundness rests on the template value checks and the randomized value test.
