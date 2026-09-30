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
| I2 | conjuncts, terms, extensions with no path through shared variables to the query or the set do not change the answer | `check_I2` | `Unrelated`: 1-12 conjuncts over fresh symbols and fresh undefined functions, each satisfiable on its own (a predicate on `u + T(v, ...)` where `u` occurs nowhere else, on `u*v`, `u**3`, `u**5`, `h(T)`; a relation between two such terms with different bases or a finite constant; a fact consistent with a fresh declared symbol), symbols disjoint across pieces: `A & B` is consistent iff `A` is; in 30 % of the checks (`I2_EXTENSION_RATE`) 1-3 *registered extensions* too (`Unrelated.extension`, `registered`): a fresh predicate `iuhNp` registered on `Symbol` or `Basic` whose handler relates it to one vocabulary literal on the same term (`implies`, `iff` or `Or`), asserted on a fresh symbol in the added conjuncts so that the handler runs; the registry is restored afterwards; two variants per query | any change but an inconsistency report: definite vs definite (`wrong`), definite vs None (`depends`), error on one side (`crash`) |
| I3 | a definite answer under `A` stays under `A & B` | `check_I3` | `B` = `p` (answer True) or `negate(p)` (False), or a fact declared on a symbol of the query (`assumptions0`); the guard demands a model of `A & B` itself (anything goes when `A & B` is inconsistent) | flipped (`wrong`), None (`lost`), error (`crash`) |
| I4 | `ask(p, A)` is True exactly when `ask(~p, A)` is False | `check_I4` | `negate(p)`: `Not(p, evaluate=False)` (`Not(Not(q))` is `q`).  SymPy's `Not(rel)` *rewrites* a `Relational` (`Not(x >= a)` is `x < a`), which is not the negation when `x` can be non-real: every round-1 I4 report was that rewrite | both definite and not opposite (`wrong`), one definite and the other None (`lost`), error on one side (`crash`) |
| I5 | an equivalent restatement of the set gives the same answer | `check_I5` | 65 %: `restate` per conjunct: relation sides swapped (`lt(a, b)` -> `gt(b, a)`), the three spellings of a relation, `Implies` as `Or` or as its contrapositive, `Equivalent` as two `Implies`, `Q.is_true` around an atom, `~eq` <-> `ne` (complements for every value; `~lt` is *not* `ge`), `zero(x)` <-> `eq(x, 0)` for a commutative non-matrix `x`, De Morgan on a negated `And`/`Or`; the negations inside are `negate` (never SymPy's rewrite).  35 % (`I5_SYNTAX_RATE`): `syntax_form`, the same conjuncts reordered, one duplicated, nested once or twice, built with `And(..., evaluate=False)` so that SymPy keeps the spelling; rebuilt from a seed, so the shrinker can drop conjuncts | as I2 |
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
# CI (about 10 s wall): pinned cases (strict xfail), planted defects,
# a 24-query related stream through every checker, the I2 transfer family,
# the negation and syntax-form guards
python -m pytest -q tests/test_invariants.py

# nightly (20 minutes CPU on one core, self-bounded: the budget is user +
# system CPU of the process and its finished children, `os.times`, not
# wall time): 8 profiles x 5 configs x the seeds, visited round robin in
# slices of 30 queries until the budget is spent; I1 (three drops) and
# I2 (two variants) run first on every query; the last line printed is
# {"cpu_seconds", "rounds", "queries"}
python -m harness invariants --nightly --seeds 0-2 --out harness-results/invariants

# a subset, unbounded
python -m harness invariants --inv I1,I2 --profile transfer,links --config default,budget --seeds 0-4 --queries 120
```

Measured (this machine): a 30-query slice through all seven checkers
takes 2-16 s (`deep`, `relational` are the slow profiles).  Round 1's
runs stopped after 485-569 s of user CPU because the budget was wall
time on a loaded machine; it is CPU now, and each query does more (three
I1 drops, two I2 variants).  Exit status 1 on an unknown violation
(`--fail-on unknown`) or any.

## Generators

The streams are the existing ones (`harness/generators.py`,
`harness/profiles.py`: `base`, `related`, `declared`, `deep`,
`relational`, `focus`, `links`, `transfer`); each `Ask` is checked once
(repeats skipped).  The variants are the checkers' own (`Unrelated`,
`restate`, `rename`, `dropping_clauses`).

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

* The first registration of a fresh predicate name in a process can
  answer None where the same registration made again answers True
  (`ask(Q.negative_infinite(u), Q.iuh1p(u))` with the handler
  `iuh1p(t) -> negative_infinite(t)`): a history effect of the registry
  epoch on a fresh engine.  Out of I2's reach (the query is about the
  extension); a registration-history checker could pin it.

## Not covered / ideas not done

* I1 does not drop the lazily loaded rule blocks (`Solver.mention_blocks`:
  propagated without clauses) nor learnt clauses.
* I2's extensions are one handler per fresh predicate on `Symbol` or
  `Basic`; polyadic predicates, handlers on `AppliedUndef` or on
  numbers, and handlers returning Python bools are not generated.
* I2 does not share a *function symbol* between the unrelated conjuncts
  and the query (`f(u)` next to `f(x)`): the engine's congruence clauses
  would link them, so it is not "no path".
* I6 skips terms above 1500 characters of srepr (SymPy rebuilds them in
  tens of seconds); the hash-seed dimension is a 4 % sample only.
* I5 cannot vary what SymPy canonicalises (`And` order, duplicates,
  nesting); an engine-level entry taking a list of conjuncts would.
* The consistency guard loses candidates under sets the engine cannot
  decide (matrices, relations without a theory); a SymPy-side model
  check (`ask` with `satisfiable`) could rescue some.
* No Hypothesis variant of the checkers (the ddmin shrink is the only
  shrinking); no cross-process confirmation of the cases.
