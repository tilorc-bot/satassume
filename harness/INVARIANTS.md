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
| I1 | dropping any subset of the clauses never flips a definite answer, never turns None definite | `check_I1` | `dropping_clauses(seed, rate)`: a test-time patch of `Solver.add_clause`, `add_clauses`, `add_internal` (the template patterns' path) dropping each clause by a hash of its literals and the seed, rate 3-50 %; two seeds per query | definite -> other definite (`wrong`), None -> definite (`wrong`), None -> engine error (`crash`) |
| I2 | conjuncts, terms, extensions with no path through shared variables to the query or the set do not change the answer | `check_I2` | `Unrelated`: 1-12 conjuncts over fresh symbols and fresh undefined functions, each satisfiable on its own (a predicate on `u + T(v, ...)` where `u` occurs nowhere else, on `u*v`, `u**k`, `h(T)`; a relation between two such terms with different bases or a finite constant; a fact consistent with a fresh declared symbol), symbols disjoint across pieces: `A & B` is consistent iff `A` is | any change but an inconsistency report: definite vs definite (`wrong`), definite vs None (`depends`), error on one side (`crash`) |
| I3 | a definite answer under `A` stays under `A & B` | `check_I3` | `B` = `p` (answer True) or `~p` (False), or a fact declared on a symbol of the query (`assumptions0`): `A & B` consistent iff `A` is | flipped (`wrong`), None (`lost`), error (`crash`) |
| I4 | `ask(p, A)` is True exactly when `ask(~p, A)` is False | `check_I4` | `Not(p)` | both definite and not opposite (`wrong`), one definite and the other None (`lost`), error on one side (`crash`) |
| I5 | an equivalent restatement of the set gives the same answer | `check_I5` | `restate`: relation sides swapped (`lt(a, b)` -> `gt(b, a)`), the three spellings of a relation, `Implies` as `Or`, `Equivalent` as two `Implies`, `Q.is_true` around an atom, reordered and duplicated conjuncts (SymPy re-sorts `And`, so the engine's own ordering is what is checked) | as I2 |
| I6 | renaming symbols and functions to fresh names gives the same answer | `check_I6` | `rename`: fresh `Symbol`/`Dummy` with the same `assumptions0`, fresh `Function`s, names whose sort order differs; in the same process | as I2 |
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
   engine, search=True)` finds a model with full escalation and search.
   When that cannot be decided (a set with a matrix or a relation no
   theory reads) the candidate is *not* reported (counted as
   `inconclusive`).  `A & B` for I2 and I3 is consistent iff `A` is, by
   construction.

Severity classes: `wrong` > `depends` (definite vs None across a "same
answer" invariant) > `lost` (definiteness demanded by I3/I4) > `crash`.

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
# a 24-query related stream through every checker, the I2 transfer family
python -m pytest -q tests/test_invariants.py

# nightly (20 minutes CPU on one core, self-bounded): 8 profiles x 5
# configs x the seeds, visited round robin in slices of 30 queries until
# the budget is spent; I1 and I2 run first on every query
python -m harness invariants --nightly --seeds 0-2 --out harness-results/invariants

# a subset, unbounded
python -m harness invariants --inv I1,I2 --profile transfer,links --config default,budget --seeds 0-4 --queries 120
```

Measured (this machine): a 30-query slice through all seven checkers
takes 2-16 s (`deep`, `relational` are the slow profiles); `--nightly
--minutes 2.5 --seeds 0` visited 34 slices.  The 20-minute run visits
roughly 250-300 slices, about 8,000 queries with two I1 drops each.
Exit status 1 on an unknown violation (`--fail-on unknown`) or any.

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
* **I7, `depends`**, known (`I7-settings`): one pinned case.
* I1, I3, I4, I5, I6: no violation in about 12,000 checks; the I1
  candidates seen were all under inconsistent sets (rejected by the
  guard).

## Not covered / ideas not done

* I1 does not drop the lazily loaded rule blocks (`Solver.mention_blocks`,
  `add_pattern`) nor learnt clauses; a patch of `add_pattern` filtering
  the block's clauses would cover the rule base.
* I2 adds conjuncts and terms only; registered extensions
  (`satassume.register`) with fresh predicates are not added.
* I6 skips terms above 1500 characters of srepr (SymPy rebuilds them in
  tens of seconds) and runs in-process only; the `PYTHONHASHSEED`
  dimension would be `checker.process_outcome` on a sample.
* I5 cannot vary what SymPy canonicalises (`And` order, duplicates,
  nesting); an engine-level entry taking a list of conjuncts would.
* The consistency guard loses candidates under sets the engine cannot
  decide (matrices, relations without a theory); a SymPy-side model
  check (`ask` with `satisfiable`) could rescue some.
* No Hypothesis variant of the checkers (the ddmin shrink is the only
  shrinking); no cross-process confirmation of the cases.
