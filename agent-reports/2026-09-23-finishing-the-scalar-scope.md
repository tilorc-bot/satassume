# Agent report: finishing the scalar `ask()` scope

- **Date:** 2026-09-23
- **Status:** on `main` (`76e4585` → `d706803` plus this report); 474 tests
  pass; the in-scope corpus replay shows zero contradictions
- **Scope:** `satassume/rules.py`, `satassume/templates/*`,
  `satassume/engine.py`, `satassume/solver.py`, `satassume/compile.py`,
  the new `satassume/extensions.py`, `tools/compare.py`, the tests, the
  README and PLAN
- **Read this if:** you want to know how far the slice "unary scalar
  predicates on scalar expressions, SAT only" got against its definition
  of done, which SymPy answers were deliberately not reproduced and why,
  what made the engine 2.4x faster, and what is left
- **Stale after:** changes to the template set, `rules.py`, the query path
  in `engine.py`, or the recorded corpus
- **TL;DR:** in-scope misses went from 284 to 70 with zero contradictions
  (96.5% agreement, 16 extra answers); every one of the 70 is either a
  SymPy answer that is false for a concrete value (67) or needs `Abs` of a
  non-atomic base or a trigonometric identity (3). `satassume.register`
  is the counterpart of `Predicate.register`, with tests mirroring SymPy's
  four extensibility tests. The in-scope corpus now runs in 1.19 s against
  6.88 s for `sympy.ask`; satassume is slower on 51 of 2583 compared
  records (was 349, then 388 after the new templates), all undecided
  queries over `Pow` cones or first-seen constants. "Faster on each" is
  therefore not met; everything else in the definition of done is.

## 1. Numbers before and after

In-scope records (`tools/compare.py queries.jsonl --fresh-cache
--in-scope-only`), 2588 replayable of 2595:

| | Agree | Extra | None | Wrong | Raises |
|---|---|---|---|---|---|
| before (`76e4585`) | 2283 (88.2%) | 16 | 284 | 0 | 5 |
| after rule base + Add/Mul (`41fddc9`) | 2363 (91.3%) | 16 | 204 | 0 | 5 |
| after Pow + functions (`0172967`) | 2496 (96.4%) | 16 | 71 | 0 | 5 |
| after derived nodes (`f16f853`) and later | 2497 (96.5%) | 16 | 70 | 0 | 5 |

The 16 extra answers are the same records as before (checked by diffing
the `--show` output). The five raises are the documented semantic choice
on assumptions contradicting a symbol's declared facts.

Old-system records replayed through `Engine.is_` (informational): 6343
replayable, 6033 agree (95.1%, was 94.6%), 27 extra, 283 None, 0 wrong.

Time on the in-scope records, same process, `--time-sympy`:

| | satassume | `sympy.ask` | slower than SymPy |
|---|---|---|---|
| before, timing as it was | 2.35 s | 8.26 s | 349 |
| after the new templates, same timing | 2.89 s | 8.73 s | 388 |
| after the speed work, GC-controlled timing | 1.19 s | 6.88 s | 51 of 2583 |

The last row uses the timing `tools/compare.py` does now: garbage
collection frozen once and disabled inside both timed calls (a collection
landing on one side inflated trivial queries from 127 us to a 355 us
median with a 98 ms worst case), and `sympy.ask` retried on an evaluated
rebuild when it raises on the unevaluated one (22 records, an `Or` of
predicates rebuilt under `evaluate(False)` makes SymPy's CNF code raise
`IndexError` in 0.1 ms, which used to count as a SymPy "time"); five
records where SymPy still raises are not compared. The 51 slower records
(20 by more than 0.3 ms) are of two kinds: undecided queries over a `Pow`
cone with its derived nodes, six nodes and about 600 clauses through two
CDCL solves (1.5 to 2.7 ms against 0.9 to 1.8 ms), and constants asked
about for the first time in a process (their old-system properties are
read once, 160 to 250 us). Worst five: `Q.imaginary((2*I)**x) |
Q.imaginary(x)` 2.66 ms vs 1.76, `Q.nonzero(5**(2*I*pi*n)) |
Q.integer(n)` 2.44 vs 1.59, `Q.complex(x**y) | Q.complex(x) &
Q.complex(y)` 2.20 vs 0.85, `Q.real(x**(y/z)) | Q.positive(x) & Q.real(x)
& Q.real(y/z)` 2.08 vs 1.33, `Q.imaginary(x**y) | Q.negative(x) &
Q.rational(y) & Q.integer(2*y)` 2.02 vs 1.22.

Microbenchmarks (`tools/bench.py`, 200 repetitions): 39 to 134 us against
268 to 1115 us for SymPy on the seven propagation cases; the case-split
case `Q.negative(y) | Q.positive(y) | Q.nonzero(y) & Q.real(y)` went from
586 us to 32 us because a repeated compound proposition now reuses its
Tseitin literal and the answer of a cone search is kept in the reused
session.

## 2. What was added (priority 1)

Every rule has a soundness test in `tests/test_templates.py` (concrete
values for the symbols, Kleene evaluation against the old system's
values), the API tests in `tests/test_sympy_api.py` pin the corpus
records per class, and the volume budgets held except `x + y` (38 → 45
formulas, budget raised to 46 with the reason in the test).

* **Rule base.** `hermitian == real` and `antihermitian == zero |
  imaginary`, which is what SymPy's generic scalar handlers compute
  (`HermitianPredicate` on `object` asks `Q.real`, `AntihermitianPredicate`
  returns True for zero and otherwise asks `Q.imaginary`). This decides
  the hermitian/antihermitian units of every number and constant.
* **Add.** An infinite term that is not `-oo` makes the sum infinite
  unless another term is `-oo` (and symmetrically); the nan cases
  (`oo - oo`, `oo + zoo`, `oo*I - oo*I`) are "unknown" and do not violate
  the rule. A nonzero real term plus imaginaries is not imaginary. A sum
  of positive even integers is composite.
* **Mul.** A composite factor times integers is not prime; an irrational
  factor times nonzero rationals is irrational; an imaginary factor times
  reals is imaginary or zero; for two factors with one imaginary, the
  product is real iff the other is imaginary or zero and imaginary iff
  the other is a nonzero real (`I*(1 + I)` is neither); the sign of a
  product of three or four factors with any number of negative factors.
* **Pow.** Gelfond-Schneider for an algebraic base and an algebraic
  imaginary exponent: never imaginary, real iff `|b| == 1` (so `3**I` and
  `2**I` are not real); `I`, `-I`, `-1` to an imaginary exponent are
  positive, and to a numeric exponent `a + I*t` decided exactly from `a`
  (`I**(2 + I)` negative real, `I**(3 + I)` imaginary); `exp(u)**e`
  positive for imaginary `u`, `e`; `E**(I*pi*c*s)` as a root of unity or a
  point on the unit circle in terms of `s`; `b**(p/q)` for positive
  rational `b` irrational unless `b` is a perfect `q`-th power (integer
  arithmetic, `sqrt(2)`); real base with rational exponent imaginary iff
  the base is negative and `2*e` is an odd integer; constant `|b| > 1` or
  `< 1` with signed infinite exponents; `x**1 == x`; composite base with
  integer exponent not prime; `1/x` irrational for irrational `x`; an
  integer other than 0 and `+-1` to a negative integer power not an
  integer (derived nodes `b - 1`, `b + 1`).
* **Functions.** `exp(I*pi*c*s)` as above and `exp(0) == 1`; `log(x)`
  with the derived node `x - 1` (zero iff `x == 1`, positive iff `x > 1`,
  which also settles `log(7)` and `log(x + 2)` for positive `x`); `acos`
  likewise; `asin`/`acos` of rational and float constants by exact
  comparison with `+-1`; a `cot` template (transcendental for algebraic
  nonzero arguments by Lindemann-Weierstrass, `zoo` at 0); `acot` and
  `atan` of imaginary arguments not real; `acot` of an algebraic argument
  not algebraic; `sin`/`cos` of a finite argument finite.

Two facts about the SymPy oracle came up: the old system says
`(I**(3 + I)).is_imaginary` is False (the value is `-I*exp(-pi/2)`), and
it raises `ZeroDivisionError` on `cot(0, evaluate=False)`; both are
excluded from the oracle-based samples with a comment.

### Rules deliberately not added

The 70 remaining misses, with the value that refutes SymPy's answer:

| Records | SymPy says | Refuted by |
|---|---|---|
| `Q.imaginary(I*x)`, `Q.imaginary(x*y)` under `Q.real` (4) | True | `x = 0` or `y = 0` gives 0 |
| `Q.hermitian(I*x)` under `Q.real(x)` / `Q.hermitian(x)`, `Q.antihermitian(I*x)` under `Q.antihermitian(x)`, `Q.antihermitian(x)` under `Q.real(x)` (4) | False | 0 is real and antihermitian (SymPy's own handler says so) |
| `Q.imaginary(x + y)`, `Q.imaginary(x + y + z)`, `Q.imaginary(x + I)` with a real term (6), the `antihermitian` versions (4) | False | the real term may be 0 |
| `Q.imaginary(x + y)` for two imaginaries, `Q.imaginary(x + I)` for imaginary `x` (4) | True | `I + (-I) = 0` |
| `Q.integer(sqrt(2)*x)` for integer `x` (1) | False | `x = 0` |
| `Q.imaginary(x**y)` for negative `x`, rational `y`, `Q.integer(2*y)` (2) | True | `y = 1` |
| `Q.nonzero(5**(2*I*pi*n))` for integer `n` (1) | False | `n = 0` gives 1 |
| `Q.real`/`Q.complex` of `re(x)`, `im(x)` (8), `Q.complex` of `Abs`, `exp`, `E**x`, `sin`, `cos` (14), `Q.finite` of `sin`, `cos` and combinations (10) | True | `re(oo) = oo`, `Abs(oo) = oo`, `exp(oo) = oo`, `sin(oo*I) = oo*I` |
| `Q.finite(log(x))` for nonzero `x` (1) | True | `log(oo) = oo` |
| `Q.finite(2**x)` for infinite `x` (1) | False | `2**-oo = 0` |
| `Q.complex(x**y)`, `Q.algebraic(x**y)` for complex/algebraic `x`, complex/rational `y` (4) | True | `0**-1 = zoo` |
| `Q.finite(x*y)` for zero `y`, infinite `x` (1) | True | `0*oo = nan` |
| `Q.positive(acot(x))` for real `x` (1) | True | `acot(-1) = -pi/4` |
| `Q.positive(acos(x))` for `x` in `[-1, 1]` (1) | True | `acos(1) = 0` |
| `Q.imaginary((2*I)**x)` for imaginary `x` (2) | False | `x = I*pi/(2*log(2))` gives `I*exp(-pi**2/(4*log(2)))` |
| `Q.real((3*I)**I)`, `Q.real((1 + I)**I)` (2) | False | correct, but needs `Abs(b) != 1` of a non-atomic base, i.e. constructing `Abs(3*I)`, `Abs(1 + I)` whose evaluation runs old-system handlers |
| `Q.prime(cos(1)**2 + sin(1)**2 + 12345678901234567890)` (1) | True | correct, needs `cos**2 + sin**2 == 1` |

Each refutation was checked by evaluating SymPy on the instance
(`ask(Q.finite(nan))` is None, `ask(Q.antihermitian(0))` is True, ...).

## 3. Extensibility (priority 2)

`satassume/extensions.py`: `register(pred, *classes)` attaches a function
`f(*args)` returning True, False, None or formulas over `P` atoms. A
custom predicate gets one solver variable per argument tuple, allocated
by `VarTable` outside the 33-predicate node blocks, so it takes part in
propagation and search like any atom and is cached in the engine's own
dictionary (never written to `_assumptions`). A vocabulary predicate
registered on a new class makes objects of that class ordinary nodes
(rule base included, so `prime` gives `integer`). Polyadic predicates are
atoms keyed by an `Args` tuple. `ask()` treats a registered name as in
scope with its registered arity; unregistered custom predicates stay out
of scope. `tests/test_extensibility.py` mirrors SymPy's
`test_key_extensibility`, `test_type_extensibility`,
`test_custom_AskHandler` (the Mersenne handler calls `ask` re-entrantly,
and a second version returns the clause `integer(log(n + 1, 2)) ->
mersenne(n)` and lets the engine visit `log(n + 1, 2)`) and
`test_polyadic_predicate`.

## 4. Speed (priority 3)

Profiling showed a node visit at 767 us (`x + y`): 45 template formulas
built as objects, walked for their atoms, compiled one by one and inserted
through the sanitising `add_clause`; the 110 rule clauses at 95 us; and
constants' 30 unit facts each propagated separately. Changes, in order of
effect:

1. templates hand the engine **precompiled clause patterns** in slot
   space (`Pattern`/`Compiled` in `templates/_common.py`), resolved once
   per pattern; a visit shifts them by the slot variables' bases and
   inserts them in bulk (`Solver.add_internal`), with units assigned and
   propagated once at the query. `registry.facts_for` still returns
   formulas for the tests and the extensions;
2. a rule with a literal about a constant that the constant cannot decide
   (`polar(2)`) is dropped at resolution, so constants never become nodes
   through templates;
3. the rule base is **minimised for propagation**: a clause is dropped
   when, for each of its literals, falsifying the others makes the rest
   derive it by unit propagation (110 → 79 clauses; the test checks
   identical propagation from every literal and pair, and identical
   models). Removing merely implied clauses would have moved answers from
   propagation to search;
4. `Clause` is a plain list with class-level defaults (C-speed
   construction); `_grow` is batched;
5. a constant's unit facts are closed under the rule base once per
   constant, from a reduced set of properties; when the closure decides
   every predicate the rule base mentions, the rule base is skipped;
6. common patterns are built once at engine construction (a few
   milliseconds, like SymPy's precomputed known facts);
7. search decides every variable of a session, so a query that needs
   search in a reused session holding other queries' nodes runs in a
   fresh session over its own cone; the answer is recorded in the reused
   session as `selector -> answer` (entailed) so repeats propagate;
   Tseitin literals of compound propositions are cached per session.

A node visit is now 118 us (`x + y`), 36 us for a constant; the rule base
is 39 us of it, at the floor of a pure-Python loop creating 79 list
objects. `tools/compare.py --dump-times FILE` writes per-record timings.

## 5. Open items

* **"Faster on each" is not met** on 51 of 2583 records. They need a
  cheaper search (two solves over about 600 clauses in pure Python) or
  cheaper derived nodes, not more template work. Candidates: restrict
  decisions to the query's cone within a session (needs a completeness
  argument or a fallback), a native propagation core, or deciding
  undecided `Pow` queries without visiting `b +- 1` when `integer` is not
  in the demanded neighbourhood.
* The 70 misses stay unless the maintainer wants the engine to reproduce
  SymPy's answers that are false for zero or infinite values; the report
  above is the list to decide on.
* The semantics of assumptions contradicting declared facts (raise, as
  now, or trust the assumption) is still the maintainer's call.
* The `Predicate.register` shim inside SymPy itself belongs to landing the
  slice; `satassume.register` is what it would delegate to.
* `Engine.__init__` used to fall back silently to "no templates" when the
  template package failed to import, which hid a broken import for a
  while; it now falls back only when SymPy itself is absent and raises
  otherwise.
