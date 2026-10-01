# Invariant harness (I1-I7)

`harness/invariants.py` checks the invariants below on generated
workloads; `python -m harness invariants` runs it, `tests/test_invariants.py`
is the CI-sized run, `harness/repros/invariants/` holds the shrunk cases.
Everything runs from the repository root with `PYTHONHASHSEED=0`.

An `ask(p, A)` result is *wrong* only if it is definite and contradicts
`p` in some model of `A`.  If `A` is inconsistent any response is
acceptable, so no checker reports a pair of answers unless the set is
consistent (below).  Losing definiteness is allowed under I1 only.

| inv | statement | checker | variant | reports |
|---|---|---|---|---|
| I1 | dropping any subset of the clauses never flips a definite answer, never turns None definite | `check_I1` | `dropping_clauses(seed, rate)`: a test-time patch of `Solver.add_clause`, `add_clauses`, `add_internal` (the template patterns' path) and `add_pattern` (compiled blocks) dropping each clause by a hash of its literals and the seed, rate 3-50 %; two seeds per query | definite -> other definite (`wrong`), None -> definite (`wrong`), None -> engine error (`crash`) |
| I2 | conjuncts, terms, extensions with no path through shared variables to the query or the set do not change the answer | `check_I2` | `Unrelated`: 1-30 conjuncts over fresh symbols (10 % `Dummy`) and fresh undefined functions (unary and binary), each satisfiable on its own and symbols disjoint across pieces, so `A & B` is consistent iff `A` is: a predicate on `u + T(v, ...)` where `u` occurs nowhere else, on `u*v`, `u**3`, `u**5`, `h(T)`, a linear combination `u + 2*v - 3`, scaled terms; a relation between two such terms or a real constant (`Float`, `Rational`, `E`, `10**12`, `GoldenRatio`; `I` only inside terms); a **closed fact** SymPy's own assumptions decide (`Q.irrational(sin(sqrt(2)))`, `~Q.imaginary(7)`, `Q.lt(2, pi)`, `Q.is_true(Lt(2, 3))`, negated when false); a relation to an infinity (`Q.eq(u, -oo)`, `Q.lt(u, oo)`, `Q.ne(u, zoo)`, `Q.infinite(u) & Q.extended_real(u)`); `Q.commutative(u)` or `~Q.commutative(nc)` for a `commutative=False` symbol; a fact consistent with a declared fresh symbol; `Or`/`Implies`/`Equivalent` of two pieces; `Q.is_true` around a *relational* only (over anything else it is documented out of scope). The material comes in three modes, recorded in the case (`mode`): `any` (40 %), `norel` (40 %: no relation anywhere, so that a change is not the relation family), `rel` (20 %: relations only). In 30 % of the checks (`I2_EXTENSION_RATE`) 1-3 *registered extensions* too (`Unrelated.extension`, `registered`): (a) a fresh predicate asserted on a fresh symbol, fresh `h(u)` or a pair of fresh symbols (polyadic, registered on `(Symbol, Symbol)`), whose handler relates it to one vocabulary literal on that term (`implies`, `iff`, `Or`), chains to a second fresh predicate, or returns `None`/`True`; (b) a *registration only*, nothing asserted: a fresh predicate on `Integer`, `Rational`, `Float`, `NumberSymbol`, `Add`, `Mul`, `Pow`, `Symbol`, `Basic`, `AppliedUndef` or a pair, its handler as in (a) or returning `False`; a vocabulary predicate on a fresh function class (no application of it exists); a vocabulary predicate on `Symbol`/`Basic` whose handler returns `None` (no clause, no path). The registry is restored afterwards; an exception inside a harness handler (`HANDLER_ERRORS`) makes the check inconclusive, never an engine crash; two variants per query | any change but an inconsistency report: definite vs definite (`wrong`), definite vs None (`depends`), error on one side (`crash`); not when the extended set is out of the documented scope (`in_scope`) |
| I3 | a definite answer under `A` stays under `A & B` | `check_I3` | `B` = `p` (answer True) or `negate(p)` (False), or a fact declared on a symbol of the query (`assumptions0`); the guard demands a model of `A & B` itself (anything goes when `A & B` is inconsistent) | flipped (`wrong`), None (`lost`), error (`crash`) |
| I4 | `ask(p, A)` is True exactly when `ask(~p, A)` is False | `check_I4` | `negate(p)`: `Not(p, evaluate=False)` (`Not(Not(q))` is `q`).  SymPy's `Not(rel)` *rewrites* a `Relational` (`Not(x >= a)` is `x < a`), which is not the negation when `x` can be non-real: every round-1 I4 report was that rewrite | both definite and not opposite (`wrong`), one definite and the other None (`lost`), error on one side (`crash`) |
| I5 | an equivalent restatement of the set gives the same answer | `check_I5` | 65 %: `restate` per conjunct: relation sides swapped (`lt(a, b)` -> `gt(b, a)`), the three spellings of a relation, a relation shifted (`rel(a, b)` -> `rel(a + c, b + c)` for a finite `c`, or `rel(-b, -a)`; scalar sides without `nan`), `Implies` as `Or` or as its contrapositive, `Equivalent` as two `Implies`, `Q.is_true` around an atom, `~eq` <-> `ne` (complements for every value; `~lt` is *not* `ge`), `zero(x)` <-> `eq(x, 0)` for a commutative non-matrix `x`, a predicate **split** by SymPy's own fact rules (`_SPLIT`: `real` as `negative | zero | positive`, `nonnegative` as `zero | positive`, `nonzero` as `positive | negative`, `positive` as `nonnegative & nonzero`, `zero` as `nonnegative & nonpositive`, `integer` as `even | odd`, `odd` as `integer & ~even`, `rational` as `real & ~irrational`, ...), a conjunct the predicate **implies** added (`_IMPLIED`: `positive(x)` -> `positive(x) & real(x)`, `prime` -> `+ integer`, `zero` -> `+ even`, `real` -> `+ hermitian`, ...: each pair is a rule of `sympy.core.assumptions._assume_rules`), the same predicate on a **transformed term** with the same truth for every scalar value (`_TERM_FORMS`: `positive(x)` <-> `positive(2*x)`, `<-> negative(-x)`, `zero(x)` <-> `zero(-x)`, `<-> zero(3*x)`, `even(x)` <-> `even(x + 2)`, `integer(x)` <-> `integer(x + 1)`, `real(x)` <-> `real(x + 1)`, `finite(x)` <-> `finite(2*x)`, ...), De Morgan on a negated `And`/`Or`; the negations inside are `negate` (never SymPy's rewrite).  35 % (`I5_SYNTAX_RATE`): `syntax_form`, the same conjuncts reordered, one duplicated, nested once or twice, built with `And(..., evaluate=False)` so that SymPy keeps the spelling; rebuilt from a seed, so the shrinker can drop conjuncts | as I2; not when the restated set is out of the documented scope |
| I6 | renaming symbols and functions to fresh names gives the same answer | `check_I6` | `rename`: fresh `Symbol`/`Dummy` with the same `assumptions0`, fresh `Function`s, names whose sort order differs, rebuilt by `_rebuild` (keeps the spelling of `Not`/`And`/`Or` nodes; `xreplace` would rewrite them); in the same process, and for 4 % of the checks in a fresh interpreter under `PYTHONHASHSEED` 1-3 (`checker.process_outcome`) | as I2 |
| I7 | changing a setting after queries gives the answers of a fresh engine with that setting | `check_I7` | 1-8 earlier stream queries in one engine, then `setattr(engine, setting, value)` (`discovery_budget`, `cone_threshold`, `transfer`, `cone_search`, `relevance`, `session_limit`, `keep_sessions`), against a fresh engine with the setting | as I2; always tagged `known:I7-settings` (plain attributes, not keyed on the registry epoch); one finding per run |

Every I1-I6 check compares fresh engines (`EngineConfig.make()`), one
per answer: no history is involved, so none of the history families
(`harness/repros`, `KNOWN_FAMILIES`) can be what a finding shows; I7 is
the only checker with a history and every I7 finding is the known one.

## The oracle

A pair of answers is reported only when

1. the invariant as stated forbids it (the table);
2. neither answer is `ValueError` (an inconsistency report is allowed
   whatever the history, and the checker cannot tell whether the
   engine's report or its answer is the right one);
3. the assumption set is consistent: `sympy_api._consistent(A, fresh
   engine, search=True)` finds a model with full escalation and search,
   of `A` or of a set with the same models (the restated set for I5, the
   renamed one for I6) or of one whose consistency implies `A`'s (`A & B`
   for I2 and I3: `B` is satisfiable over fresh symbols, or `p`/`~p` as
   answered, or a declared fact).  When none can be decided (a set with a
   matrix or a relation no theory reads) the candidate is *not* reported
   (counted as `inconclusive`).

Severity classes: `wrong` > `depends` (definite vs None across a "same
answer" invariant) > `lost` (definiteness demanded by I3/I4) > `crash`.

### What a SymPy constructor may change

SymPy rewrites some of what the checkers build, and a rewrite is not
the same statement: `Not(rel)` flips the relation (wrong for non-real
values), `And` flattens, sorts and merges duplicates, `xreplace`
rebuilds every node with the evaluating constructor, and `srepr` output
evaluated back does the same.  The harness therefore builds every
negation with `negate` (`Not(p, evaluate=False)`), respells sets with
`evaluate=False`, renames with its own rebuild, and `sympy_io.from_srepr`
binds `And`/`Or`/`Not` to non-evaluating constructors (a canonical node
rebuilt that way equals the original; a non-canonical one keeps its
spelling), so every pinned case replays exactly what was checked.
Relations themselves are still SymPy's (`Lt(a, b)` may evaluate to a
Boolean when both sides are numbers: the same models), and `_QREL`
spellings (`Lt` <-> `Q.lt`) are taken as equivalent.

## Shrinking

`shrink` runs `checker.ddmin` over the conjuncts of the set, then over
the unrelated conjuncts (I2) and the history (I7), keeping the guarded
violation; the result is written as `NAME.json` (srepr) and `NAME.py`
(standalone: `PYTHONHASHSEED=0 python NAME.py` replays it and asserts
the violation).

## Commands and budgets

```bash
export PYTHONHASHSEED=0
# CI (10-11 s wall, measured at 3b20064 on a quiet machine): pinned cases
# (strict xfail), planted defects, a 24-query related stream (plus its
# derived queries) through every checker, the I2 transfer family, the
# negation and syntax-form guards, the value-level guard of the I5
# restatements (every restatement agrees with the original at sample
# values under SymPy's own ask)
python -m pytest -q tests/test_invariants.py

# nightly (20 minutes CPU on one core, self-bounded: the budget is user +
# system CPU of the process and its finished children, `os.times`, not
# wall time): 8 profiles x 7 configs (`default`, `budget`, `tight`, `reuse`, `whole`, `notransfer`, `lean`) x the seeds, visited round robin in
# slices of 30 queries until the budget is spent; I1 (three drops) and
# I2 (two variants) run first on every query; the last line printed is
# {"cpu_seconds", "rounds", "queries"}
python -m harness invariants --nightly --seeds 0-2 --out harness-results/invariants

# a subset, unbounded
python -m harness invariants --inv I1,I2 --profile transfer,links --config default,budget --seeds 0-4 --queries 120
```

Measured (round 3, d21e655, this machine): a 30-query slice (plus its
derived queries, about 40 queries) through all seven checkers takes
2-8 s of CPU (`base`, `declared` fast; `related`, `deep`, `relational`
slow); `--nightly --minutes 1.2 --seeds 36` visited 11 slices (450
queries, 1,350 I1 checks, 900 I2 checks) in 73 s; `--minutes 2.5`
visited one full round of 8 profiles x 5 configs (570-900 queries).
The 20-minute run visits roughly 150-180 slices, about 6,000-7,000
queries.  At most five reports per invariant and *one* of one shape
(invariant, severity, base answer, variant answer) per slice (the I2
definite -> None family would otherwise spend the budget on shrinking),
and for I2 one per shape *and kind of unrelated material*
(`extra_kinds`, recorded in the case as `kinds`: `closed`, `inf`,
`commutative`, `relation`, `declared`, `pred`, `compound`,
`ext:<class>:<shape>`), so that the same shape reached by different
material is reported, and the kinds tell families apart.  Exit status 1 on an unknown violation
(`--fail-on unknown`) or any.

## Generators

The streams are the existing ones (`harness/generators.py`,
`harness/profiles.py`: `base`, `related`, `declared`, `deep`,
`relational`, `focus`, `links`, `transfer`); each `Ask` is checked once
(repeats skipped).  `run_stream` adds **derived queries** to every
stream (`derived_asks`, `WIDEN_RATE` 35 % of the queries): the
proposition combined with a conjunct of its set (`And`, `Or` with the
negation, `Implies`, `Equivalent`), wrapped in `Q.is_true` (a relational
or applied predicate), negated, a conjunct asked back or negated, or a
relation between two scalar terms of the query (or a term and `0`, `1`,
`-1`, `oo`).  Every checker runs on them: they reach propositions the
profiles do not (compound propositions for I4, relations as propositions
for I2).  The variants are the checkers' own (`Unrelated`, `restate`,
`rename`, `dropping_clauses`).

## Scope filter

`in_scope(prop, assum)` is `sympy_api.out_of_scope` allowing the
"relation" category: a variant set holding a matrix atom, an unregistered
custom predicate, `Q.is_true` over a non-relational or a non-Boolean is
None by the documented contract, and I2/I5 do not report it (the
generators avoid producing such sets; the filter is the safety net).

## Findings at f055b7b (`harness/repros/invariants/`)

* **I2, `depends`** (three pinned cases, and the same family under
  every profile): a fact about `f(0)` under `zero(z)` asked about `f(z)`
  (`ask(Q.zero(f(y) - 1), Q.zero(y) & Q.nonzero(f(0) - 1))`) is None in
  a fresh engine and definite (correctly) once an unrelated *relation*
  conjunct is present; the reverse family: a definite answer
  (`ask(~Q.infinite(f(-o)), Q.infinite(f(-o)))` = False,
  `ask(Q.extended_nonzero(7 - 2*o), Q.extended_nonzero(2*o + pi))` =
  True) becomes None with unrelated conjuncts.  The unrelated relation
  switches the set from the relevance-split path to the whole-set
  path with the relation glue and transfer engaged (the mechanism of
  history family T, but without any history: a fresh engine, one query).
  The lost-definiteness direction is large: in a 2.6-minute run over
  every profile 39 of 88 slices reported one, including a set asked
  back as the proposition (`ask(~Q.extended_nonzero(r),
  ~Q.extended_nonzero(r))` = True; None with `Q.gt(u, h(k(0)))` added)
  and a context-free fact (`ask(Q.commutative(f(_d) + 1), Q.finite(r))`).
  Nine cases are pinned; the nightly reports up to five per slice.
* **I4**: no violation.  Round 1 reported five (one pinned), all of
  them SymPy's rewrite of `Not(rel)` (`-nP >= -1/3` under `Q.complex(nP)`,
  `z/2 > oo`, `z**3 > oo`, `z >= oo` under `Q.negative_infinite(...)`,
  `sqrt(j)/2 + k/2 + 8 >= -oo` under `Q.positive(sin(j)/2)`): with the
  logical negation every one is consistent and correctly answered.  The
  pinned case is removed; `tests/test_invariants.py::
  test_negation_is_not_sympys_rewrite` keeps the round-1 cases as a guard.
* **I5, `depends`** (pinned): `ask(Q.even(j), ~Q.lt(2.0*sqrt(2), 0))` is None; the
  same conjunct spelled `~Lt(2.0*sqrt(2), 0)` evaluates to `True` in
  SymPy and the answer is True (`j` is declared even).  A constant
  relation conjunct the theories do not read makes the engine give up on
  a declared fact.
* **I5, `depends`** (round 2, two pinned: `I5-zero-as-eq-engages-transfer*`):
  `ask(~Q.real(-g(x)), Q.zero(x) & Q.infinite(2*g(0)))` is None; with
  `Q.zero(x)` spelled `Q.eq(x, 0)` it is True (correctly: `g(x)` is
  `g(0)`).  The relation spelling engages the relation glue and transfer,
  the predicate spelling does not: the I2 transfer family reached through
  a restatement.  Nine cases in a 2,800-query I5 run (`transfer` profile,
  every config).
* **I3, `lost`** (round 2, pinned: `I3-declared-fact-loses-definiteness-budget`):
  `ask(Q.negative(1/(z0 + 1)), Q.positive(he) | Q.negative_infinite(-3/sqrt(f(z0))))`
  is False under the `budget` config and None once `~Q.irrational(z0)`
  (declared: `z0` is zero) is added: the discovery budget family of
  round 1's I3 case.
* **I7, `depends`**, known (`I7-settings`): one pinned case.
* I1, I3, I6: no violation in about 20,000 checks; the I1 candidates
  seen were all under inconsistent sets (rejected by the guard).  I1
  also turns a few consistent definite answers into `ValueError`
  (fewer clauses, yet an inconsistency report): not a violation as I1
  is stated, so not reported.

## Findings of round 3 (db45182)

* **I5, `depends`** (pinned: `I5-implied-conjunct-rescues-budget`):
  `ask(Q.real(m - 2 + GoldenRatio), Q.transcendental(m) & ~Q.extended_negative(T))`
  (`m` declared negative, `T` a large term) is None under the `budget`
  config and True once `Q.finite(m)`, which `Q.transcendental(m)` implies
  (and the declaration too), is added: the discovery budget runs out
  before the implied fact is found; the restatement that adds an implied
  conjunct reaches it.  The same mechanism as the I3 budget case, through
  an equivalent restatement.
* **I2, `depends`** (pinned: `I2-closed-relation-conjunct-loses-definite`;
  `kinds: closed`): `ask(Q.ne(m, d), Q.zero(d))` is True and None with
  the closed fact `~Q.gt(-2/3, 2.5)` added (no symbol at all in the
  conjunct).  The round-2 family of the unrelated relation, reached with
  a relation over constants only; the nightly reports each `kinds` once
  per slice (`closed`, `relation`, `compound`, `ext:...` seen in 2.5
  minutes).
* **I2, `depends`, no relation involved** (pinned:
  `I2-predicates-only-exhaust-discovery-budget`; `mode: norel`):
  `ask(~Q.nonpositive(-t), Q.nonpositive(1 - t))` (`t` real, nonzero) is
  False under the `budget` config (discovery budget 5) and None with
  three unrelated *predicate* conjuncts (`Q.real(u2 + u4 + u5 + 1/u3)`,
  an `Implies` over a closed fact and `Q.commutative(u7)`, an `Or` of
  two predicates) and a vocabulary handler returning None: the unrelated
  nodes consume the discovery budget before the query's own nodes are
  discovered (the mechanism of history family D, with no history and no
  relation: the relevance split does not keep the unrelated predicates
  out).  516 relation-free checks under `default`, `lean` and `tight`
  (budget 12) found no change: the budget of 5 is what makes it visible.
* **Registration only, no change**: 3,080 checks of ten registration-only
  extensions (vocabulary handlers returning None on `Symbol`, `Basic`,
  `AppliedUndef`, a vocabulary handler on a fresh function class, fresh
  predicates on `Basic`, `Symbol`, `Integer`, `Add`, a polyadic one, a
  `chain`) over 7 profiles' queries and their derived queries: no answer
  changed.  The registry epoch alone does not move a fresh engine's
  answer; the asserted extension families are the ones reported.
* I2 `crash`: every engine error seen with the widened material was the
  harness's own polyadic handler (`P` takes an `Args` tuple); fixed and
  guarded (`HANDLER_ERRORS`).  No engine crash in 1,900 nightly queries.

## Not violations (do not report)

* A set with a *matrix* atom or an *unregistered custom* predicate:
  `sympy_api.out_of_scope` documents both and the engine answers None
  for the whole set, so a definite answer "lost" to such a conjunct is
  the documented contract, not I2.  `Unrelated` generates neither;
  every custom predicate it asserts is registered (`registered`).
* `Not(rel)` built by SymPy is a different statement (above).
* `Q.nonzero(x)` is *not* `Q.ne(x, 0)` (nonzero implies real) and
  `Q.positive(x)` is not `Q.gt(x, 0)` for a non-real `x`: `restate`
  uses neither.

## Observed, not pinned

* Round 2 noted that the first registration of a fresh predicate name
  in a process answered None where the same registration made again
  answered True (`ask(Q.negative_infinite(u), Q.iuh1p(u))`, handler
  `iuh1p(t) -> negative_infinite(t)`).  Round 3 could not reproduce it
  in isolation: in a fresh process the first registration answers True,
  also after the same query was asked unregistered first (None, the
  documented out-of-scope answer) and after an unrelated query; three
  registrations in a row agree.  Not pinned; whatever the round-2 process
  had done before (thousands of queries, many registrations restored
  through `harness.registry.restore`) is the missing ingredient.

## Not covered / ideas not done

* I1 does not drop the lazily loaded rule blocks (`Solver.mention_blocks`:
  propagated without clauses) nor learnt clauses.
* I2's extensions: a handler never raises, never returns a clause over
  the *query's* symbols (that would be a path), and never relates two
  registered predicates to each other; the chain shape mentions an
  unregistered second predicate inside a clause only.
* I2 does not share a *function symbol* between the unrelated conjuncts
  and the query (`f(u)` next to `f(x)`): the engine's congruence clauses
  would link them, so it is not "no path".
* I6 skips terms above 1500 characters of srepr (SymPy rebuilds them in
  tens of seconds); the hash-seed dimension is a 4 % sample only.
* I5 cannot vary what SymPy canonicalises (`And` order, duplicates,
  nesting); an engine-level entry taking a list of conjuncts would.
* I5's restatements are per conjunct; a restatement across conjuncts
  (`positive(x) & integer(x)` as `prime(x) | composite(x) | eq(x, 1)`),
  and restatements of the *proposition* (I4 is the only one) are not
  generated.
* I2's unrelated material never includes a `Q.is_true` over a
  non-relational, a matrix or an unregistered predicate (documented out
  of scope), nor a second application of a function of the query.
* The consistency guard loses candidates under sets the engine cannot
  decide (matrices, relations without a theory); a SymPy-side model
  check (`ask` with `satisfiable`) could rescue some.
* No Hypothesis variant of the checkers (the ddmin shrink is the only
  shrinking); no cross-process confirmation of the cases.
