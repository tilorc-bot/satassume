# Agent report: irrational constants as bounded LRA variables, stage 1, build

- **Date:** 2026-09-25
- **Status:** built and gated on branch `irrational-lra` (base
  `stage-constants` 58b6e39, which is main 73ade63 minus its report
  commit). x86 dev host, SymPy `/home/tilo/sympy`, `PYTHONHASHSEED=0`.
  No timing claims.
- **Headline:** a closed real constant in a linear position (`pi` of
  `x <= 3*pi/2`) is now an LRA term with rigorous rational bounds asserted
  once per session. On the refine stream that gives **106 more definite
  answers (90 distinct, 26 sets), 24 new ValueErrors (the 3 expected sets,
  SymPy raises on all 24), nothing less definite, no flips**. gate2: 0
  changed. The refine scoreboard's **6 relation losses against `pi` are
  gone** (satassume 417 -> 423 passed of 474; no free Booleans needed).
- **One departure from the owner's design, for the owner to decide:
  Floats stay unreadable.** Reading a Float as its exact binary value
  turns `ask(Q.eq(0.1, 1/10))` from None into False, and SymPy's `ask`
  says True (section 3). The instruction was to report rather than guess,
  so the build keeps Floats as today.
- **Read this if:** you review or land item 2 of
  `2026-09-25-next-steps.md`, or decide the Float question.

## 1. Design

`satassume/lra_adapter.py`:

- `_lin`'s no-free-symbols branch calls the new `_closed`: a `Rational` goes
  to the constant; a closed `Add` is split; a rational factor is pulled
  out with `as_coeff_Mul` (`3*pi/2` is `3/2 * pi`); what is left must have
  no `Float` in it and `constant_bounds(c)` must return bounds, else the
  atom is unreadable as before. The rest `c` becomes a term of the form,
  keyed by the expression, so `pi/2`, `pi` and `-3*pi` share one variable.
- A closed non-rational factor of a product *with* free symbols
  (`pi*x`, `sqrt(2)*x`, `0.5*x`) still raises: nonlinear, unreadable.
- `constant_bounds(c)` (memoized per constant, module-level like
  `_INTERPRETED`): None unless `c.is_number`, `c.is_extended_real is True`
  and `c.is_finite is True`. Then `c.evalf(30, strict=True)` and
  `c.evalf(45, strict=True)` (strict: evalf raises `PrecisionExhausted`
  instead of returning fewer correct digits); both must be real Floats and
  nonzero, and they must agree within 1/16 of the margin. The interval is
  the 30-digit value widened by `2**-63` relative (about 1e-19, some 1e10
  times the error evalf claims) and rounded outward to a grid of `2**-72`
  relative: `lo < c < hi`, with numerators of about 22 digits. An exact
  zero that is not syntactically zero (`pi*(sqrt(2+sqrt(3)) - (sqrt(2)+sqrt(6))/2)`)
  makes strict evalf fail, so it gets no bounds and stays unreadable.
- `LRAAdapter.register_bounds(solver, term, new_var)` registers the two
  payloads `-c < -lo` and `c < hi` on fresh variables and returns them.

`satassume/relations.py`:

- `Relations._interpret`, for each term `u` of a guarded atom: if `u` is a
  number (`_is_number`) and not yet in `self._bounded`, `_bound(ad, u)` has
  the adapter register the bounds on fresh aux variables and emits them as
  unit clauses (unguarded: the constant's value satisfies them whatever
  else holds). Once per session and constant.
- The guard `real(u)` for `u = pi` is decided at the root by the rule base
  (checked: `pi, E, sqrt(2), log(2), sin(1), pi**2, 2**pi, exp(-3)` are all
  `real` context-free). For a constant the engine cannot prove real
  (`zeta(3)`), the guard stays open and the bridge floats: sound, weaker.
- Numbers are still not linked (`_link_later` skips them); the bounds
  carry the sign. `pi` joins `LRAAdapter.shared_terms`, so equality sharing
  can add `eq(pi, t)` interface atoms (numbers pair with numbers are
  skipped as before).

Constant-only propositions (the coordinator's requirement): `sympy_api`
answers them on the context-free path (`Engine.is_` -> `_is_custom` ->
`literal_of`), which interprets the atom through `Relations._interpret`
like any other, so the bounds are asserted there too. Checked:
`ask(Q.lt(pi, 4))` is True, `ask(Q.lt(pi, 4), Q.lt(pi, 3))` is True,
`ask(Q.gt(pi, 22/7))` is False, `ask(Q.lt(pi, 355/113))` is True, and
`pi` against a rational 1e-25 below it is None. None of these occurs in the
stream or gate2, so they add nothing to the ab/gate2 counts below.

Docstrings updated: `lra_adapter` (the rules list, a new "Constants"
section, the Float rule) and `relations` (a "Constant terms" section).

## 2. Changed answers (refine stream, 13,877 queries, main 73ade63 -> irrational-lra)

Replayed with one process per checkout (same loop as `tools/ab.py`), every
answer dumped and diffed:

| main -> irrational-lra | queries | distinct | sets |
|---|---:|---:|---:|
| None -> True | 56 | | |
| None -> False | 50 | | |
| more definite, total | **106** | 90 | 26 |
| None -> ValueError | **24** | 24 | 3 |
| anything else (less definite, flips, other errors) | **0** | | |

Stage 0's oracle predicted 105 and 24. Its Float atoms do not matter here:
every Float query also has a `pi` atom, and those sessions stay
Uninterpreted because of the Float (section 3).

**SymPy's `ask` (5 s alarm) on the 90 distinct more-definite answers:** 60
agree, 30 SymPy None, 0 contradict. By class of the proposition (queries):

| proposition | answer | queries | SymPy |
|---|---|---:|---|
| `Q.real(x)` | True | 16 | agrees |
| `Q.extended_real(...)` of an expression | True | 14 | agrees |
| `Q.infinite(...)` | False | 13 | agrees |
| `Q.extended_real(x)` / `Q.infinite(x)` | True / False | 8 + 8 | agrees |
| `Q.zero(x)` | False | 7 | agrees |
| `Q.nonnegative/negative/nonpositive/positive/imaginary(x)` | | 7 | agrees |
| `Q.integer(im(x)/pi)` and variants (`-im(x)/pi`, `im(x)/(2*pi)`) | True | 13 | None |
| `Q.zero(x)` | False | 13 | None |
| `Q.positive(x)`, `Q.nonnegative(x)` given `-pi/2 >= x & x <= pi/2` | False | 2 | None |
| `Q.zero(x - 2*pi)`, `Q.nonnegative(x - 2*pi)` given `4 <= x <= 6` | False | 2 | None |
| `Q.imaginary(x - 2*pi*floor(x/(2*pi) + 1/2))` given `nonnegative(x) & x <= pi` | False | 1 | None |
| `Q.extended_real(Abs(x)/pi + 1/2)` given `0 <= Abs(x) <= pi/2` | True | 1 | None |

All 30 SymPy-None answers read by hand, all correct:

- `integer(im(x)/pi)` etc.: every such set has `nonnegative`, `positive`,
  `nonpositive` or `negative(x)`, so `x` is real, `im(x) = 0`, and `0/pi`
  is an integer.
- `zero(x)` False given `pi/2 <= x <= 3*pi/2` (and `[-3pi/2, -pi/2]`,
  `[pi, 2pi]`, `(0, pi)`, `(0, pi/2)`, `x <= -pi/2`, ...): if `x = 0`
  then `x` is real, the relations have their meaning, and `0` is outside
  the interval.
- `positive(x)` / `nonnegative(x)` False given `x <= -pi/2`: either makes
  `x` real and `>= 0`.
- `zero(x - 2*pi)` / `nonnegative(x - 2*pi)` False given `4 <= x <= 6`:
  either makes `x - 2*pi`, hence `x`, real, and then `x >= 2*pi > 6`.
- `imaginary(x - 2*pi*floor(...))` False: `x` is real (nonnegative), so
  the expression is real, and a real number is not imaginary.
- `extended_real(Abs(x)/pi + 1/2)` True: `Abs(x)` is always extended real.

**The 24 new ValueErrors** (SymPy's `ask` raises on all 24). The sets are
inconsistent without the constant (`x` negative and positive, or positive
and zero); they raise now only because the session gets built at all.

| assumption set | queries | propositions |
|---|---:|---|
| `Q.negative(x) & Q.positive(x) & Q.gt(t, -pi/2) & Q.lt(t, pi/2) & Q.nonnegative(x*tan(t))` | 9 | `extended_real(t/pi + 1/2)`, `infinite(t/pi + 1/2)`, `integer(im(t)/pi)`, `integer(re(t)/pi)`, `integer(t/pi + 1/2)`, `integer(t/pi)`, `real(t)`, `zero(t)`, `zero(tan(t))` |
| `Q.negative(x) & Q.positive(x) & Q.gt(t, -pi/2) & Q.lt(t, pi/2) & Q.negative(x*tan(t))` | 9 | the same nine |
| `Q.positive(x) & Q.zero(x) & Q.gt(t, -pi/2) & Q.lt(t, pi/2) & Q.nonzero(x*tan(t))` | 6 | `imaginary(tan(t))`, `negative(tan(t))`, `positive(tan(t))`, `positive(x)`, `zero(t)`, `zero(tan(t))` |

## 3. Floats: not read (owner's call)

The design said: read a Float as its exact rational value, and report if
that changes existing answers. It does, against SymPy:

| query | main | exact reading | `sympy.ask` |
|---|---|---|---|
| `Q.eq(Float(0.1), Rational(1, 10))` | None | False | **True** |
| `Q.gt(Float(0.1), Rational(1, 10))` | None | True | **False** |
| `Q.eq(x, 0.5)` given `Q.eq(x, 1/2)` | None | True | None |
| `Q.eq(2, 2.0)` | None | True | True |

SymPy itself has no single meaning: `Float(0.1) > Rational(1, 10)` is True
(exact binary value) while `Eq(Float(0.1), Rational(1, 10))` is True
(equality at the Float's precision), and `Float('1.571') < 1571/1000` and
`Eq(Float('1.571'), 1571/1000)` are both True. Any fixed reading
contradicts one of them (the exact reading makes `ask(Q.eq(0.1, 1/10))`
False where SymPy says True; the existing test
`test_euf_adapter.py::test_engine_numbers_of_different_types_never_wrong`
caught it). So a Float anywhere in a closed subexpression keeps the atom
unreadable, exactly as on main (`x < 0.5`, `x < 0.5*pi`, `x < pi + 0.25`).

Options for the owner:

1. Keep this (no Float semantics). Cost: the stream's Float sessions
   (four Floats, all next to `pi`) stay Uninterpreted.
2. Exact binary value, accepting `ask(Q.eq(0.1, 1/10)) = False` against
   SymPy's True.
3. A Float as an unknown within its own precision (a bounded term, like
   `pi`, with bounds `v*(1 -+ 2**(1-prec))`): sound under both of SymPy's
   readings, never decides `Eq(0.1, 1/10)` or `0.1 > 1/10`, and gives
   `x <= 4.712 -> x < 5`. About ten lines in `_closed`; not built.

## 4. Gates

| check | result |
|---|---|
| suite (3 chunks, each under 250 s) | 1032 + 621 + 140 passed; only failures the known `test_shared_facts.py::test_cached_sympy_fact_does_not_make_assumptions_inconsistent` (2 params); 1 XPASS (`test_sympy_zero_power_is_not_finite_for_a_plain_exponent`, non-strict, not from this change) |
| new `tests/test_lra_constants.py` | 32 tests pass (unit tests plus two hypothesis fuzzers of 150 examples each) |
| constant fuzz, seeded (`python tests/test_lra_constants.py SEED0 N`) | 6,000 cases (seeds 0-5999): **0 wrong**, 126 unchecked |
| `tests/real_theory_fuzz.py` | 4,000 seeds each of `lra`, `euf`, `both`: 0 mismatches, 0 implied-misses |
| `tools/solver_diff_fuzz.py` | not run: no solver file changed |
| `tools/ab.py /home/tilo/satassume /home/tilo/satassume-wt-irr --rounds 1 --allow-more-definite` | ref 443 more definite, cand 549 (= 443 + 106); "REF AND CAND DIFFER" never printed; exits 1 on the 24 errors, which it counts as mismatches (by design) |
| `tools/gate2.py /home/tilo/satassume-wt-irr --allow-more-definite` | **changed 0** (0 in scope); 1 more definite, the pre-existing transfer answer `Q.prime(x)` given `Q.prime(y) & Q.eq(x, y)` that stage 0 already saw against the frozen file |
| refine scoreboard (recipe of `2026-09-25-refine-capability-baseline.md`, `irrational-lra` merged with `eb106a6`, SymPy 6379c4da69) | satassume 423 passed / 49 failed (baseline 417 / 55); losses against sympy 46 = 45 matrix + 1 stale (`test_kronecker_reversed_assumption_order`); **the 6 relation losses against `pi` are gone** (`test_refine_inverse_trig` 11/11, `test_atan_rule_at_closed_interval_endpoints`, `test_quoted_rule_outputs` pass). sympy 463, combined 467, as in the baseline. Not run with `REFINE_BASELINE_ENGINE_KW` (free Booleans): nothing was left for it to win |

**The constant fuzz** draws 1-4 relations over 1-3 real symbols with
constants from `pi, E, sqrt(2), log(2), sin(1), pi**2, 2**pi, exp(-3)`
(rational multiples, sums), rational offsets, rationals within 1e-2, 1e-6
or 1e-25 of a constant, and `c - near(c)` (about 0). The oracle replaces
every constant with its 60-digit value and runs the Fourier-Motzkin check
of `test_lra_fuzz.py`. A definite answer must equal the oracle's.
"Unchecked" counts engine None where the oracle is definite, and an
answer where the oracle says the assumptions are inconsistent (the engine
missed an inconsistency closer than the bounds, so every answer is
entailed): all of those come from the 1e-25 comparisons, as intended.

Commands (from `/home/tilo/satassume-wt-irr`, env `PYTHONHASHSEED=0`):

    PYTHONPATH=.:/home/tilo/sympy .venv/bin/python -m pytest -q -p no:cacheprovider <chunk>
    cd tests; PYTHONPATH=..:/home/tilo/sympy:. ../.venv/bin/python test_lra_constants.py 0 3000
    cd tests; PYTHONPATH=..:/home/tilo/sympy:. ../.venv/bin/python real_theory_fuzz.py 0 1000 both
    .venv/bin/python tools/ab.py /home/tilo/satassume /home/tilo/satassume-wt-irr --rounds 1 \
        --allow-more-definite --more-definite-out OUT.jsonl
    .venv/bin/python tools/gate2.py /home/tilo/satassume-wt-irr --allow-more-definite

The per-query diff and SymPy check were two scratch scripts (replay and
dump every answer per checkout; `sympy.ask` with a 5 s alarm on each
distinct change), not committed; their outputs are in the session
scratchpad (`irr/changed.json`, `irr/verified.json`).

## 5. Risks

- **evalf's error bound is trusted.** `strict=True` is SymPy's own
  guarantee, backed here by a 45-digit cross-check and a margin about 1e10
  times the claimed error. It is not interval arithmetic. A constant for
  which evalf is confidently wrong in the 19th digit would make the bounds
  wrong. mpmath `iv` was not used: it covers few SymPy functions.
- **Cost.** Each new constant costs two evalf calls (memoized per process)
  and two theory atoms per session. `pi` in `shared_terms` adds
  interface equalities `eq(pi, t)` when EUF also knows terms. ab showed the
  candidate slower on this dev host (one round, shared machine: no claim);
  the Pi timing is the owner's.
- **Distinct spellings of one value** (`log(8)/log(2)` and `3`,
  `sqrt(2)*sqrt(3)` if not auto-simplified and `sqrt(6)`) are unrelated
  variables whose bounds overlap: sound, but equalities between them are
  never proved.
- **Realness comes from two places.** The adapter reads a constant only
  if SymPy says `is_extended_real is True`; the bridge's guard uses the
  engine's own `real(c)`. Where the engine cannot prove it (`zeta(3)`), the
  bridge floats: weaker, sound. The bounds are asserted unguarded, which
  rests on SymPy's `is_extended_real` being right and on evalf returning a
  real Float (a complex result gets no bounds).
- **New ValueErrors** in 3 stream sets: correct (SymPy raises too), but
  they change the error set of any acceptance rule that pins errors
  (`tools/ab.py` fails on them by design).
- **Floats**: see section 3; the stream's Float sessions gain nothing.

## 6. Commits (`irrational-lra`)

- `lra_adapter: closed real constants as bounded LRA terms, Floats exact; relations: assert the bounds once per session`
- `tests: constants in linear relations (unit tests, fuzz against 60-digit values); docstrings`
- `lra_adapter: Floats stay unreadable (SymPy reads them exactly in < but at precision in Eq); tests use pi*x as the unreadable example`
- `untrack the .venv symlink added by mistake`
- this report
