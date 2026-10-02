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
| I1 | dropping any subset of the clauses never flips a definite answer, never turns None definite | `check_I1` | `dropping_clauses(seed, rate)`: a test-time patch of `Solver.add_clause`, `add_clauses`, `add_internal` (the template patterns' path) and `add_pattern` (compiled blocks) dropping each clause by a hash of its literals and the seed, rate 3-50 %; three drops per query.  In 30 % of the checks (`I1_BLOCKS_RATE`; `blocks: true` in the case) the lazily loaded **rule blocks** too: `register_block` is replaced by `add_pattern(block, base, nvars)` (the solver's own statement of what a registered block behaves as) minus the dropped clauses; the reference of such a check is the same patch at rate 0 (eager blocks, nothing dropped; it agreed with the engine on every query tried), and the check is inconclusive when that reference differs from the engine's answer (the lazy block may be *less* definite in `implied`, which is not I1's statement) | definite -> other definite (`wrong`), None -> definite (`wrong`), None -> engine error (`crash`) |
| I2 | conjuncts, terms, extensions with no path through shared variables to the query or the set do not change the answer | `check_I2` | `Unrelated`: 1-30 conjuncts over fresh symbols (10 % `Dummy`) and fresh undefined functions (unary and binary), each satisfiable on its own and symbols disjoint across pieces, so `A & B` is consistent iff `A` is: a predicate on `u + T(v, ...)` where `u` occurs nowhere else, on `u*v`, `u**3`, `u**5`, `h(T)`, a linear combination `u + 2*v - 3`, scaled terms; a relation between two such terms or a real constant (`Float`, `Rational`, `E`, `10**12`, `GoldenRatio`; `I` only inside terms); a **closed fact** SymPy's own assumptions decide (`Q.irrational(sin(sqrt(2)))`, `~Q.imaginary(7)`, `Q.lt(2, pi)`, `Q.is_true(Lt(2, 3))`, negated when false); a relation to an infinity (`Q.eq(u, -oo)`, `Q.lt(u, oo)`, `Q.ne(u, zoo)`, `Q.infinite(u) & Q.extended_real(u)`); `Q.commutative(u)` or `~Q.commutative(nc)` for a `commutative=False` symbol; a fact consistent with a declared fresh symbol; `Or`/`Implies`/`Equivalent` of two pieces; `Q.is_true` around a *relational* only (over anything else it is documented out of scope). The material comes in three modes, recorded in the case (`mode`): `any` (40 %), `norel` (40 %: no relation anywhere, so that a change is not the relation family), `rel` (20 %: relations only). In 30 % of the checks (`I2_EXTENSION_RATE`) 1-3 *registered extensions* too (`Unrelated.extension`, `registered`): (a) a fresh predicate asserted on a fresh symbol, fresh `h(u)` or a pair of fresh symbols (polyadic, registered on `(Symbol, Symbol)`), whose handler relates it to one vocabulary literal on that term (`implies`, `iff`, `Or`), chains to a second fresh predicate, or returns `None`/`True`; (b) a *registration only*, nothing asserted: a fresh predicate on `Integer`, `Rational`, `Float`, `NumberSymbol`, `Add`, `Mul`, `Pow`, `Symbol`, `Basic`, `AppliedUndef` or a pair, its handler as in (a) or returning `False`; a vocabulary predicate on a fresh function class (no application of it exists); a vocabulary predicate on `Symbol`/`Basic` whose handler returns `None` (no clause, no path). The registry is restored afterwards; an exception inside a harness handler (`HANDLER_ERRORS`) makes the check inconclusive, never an engine crash; three variants per query.  **Blocks** (round 4, `I2_BLOCK_RATE` 40 % of the checks, `blocks: n` in the case): `Unrelated.block`, an unrelated *subsystem* of 2-4 conjuncts over 2-3 fresh symbols sharing symbols among themselves (sign atoms on sums and products sharing a symbol, order chains, equalities, disequalities, integrality), the symbols optionally declared (`integer`, `positive`, `real`), the constants optionally the query's own (`_consts_of`: symbol-disjoint, sharing a constant, is still unrelated); a witness assignment is chosen first (`harness.models.WITNESS_POOL`, respecting the declarations), each atom is kept in the polarity true at it, and the block is verified by evaluation (`harness.models.evaluate_at`) or not used; half of the time the blocks are the whole material.  **Out-of-scope material** (`OOS_RATE` 3 % of the pieces in `any` mode): a matrix atom, `Q.is_true` over a non-relation, an unregistered custom predicate on a fresh symbol | any change but an inconsistency report: definite vs definite (`wrong`), definite vs None (`depends`), error on one side (`crash`).  The engine's scope category is a *tag* (`scope` in the case: `in`, `matrix`, `custom`, `other`), never a veto |
| I3 | a definite answer under `A` stays under `A & B` | `check_I3` | `B` = `p` (answer True) or `negate(p)` (False), or a fact declared on a symbol of the query (`assumptions0`); the guard demands a model of `A & B` itself (anything goes when `A & B` is inconsistent) | flipped (`wrong`), None (`lost`), error (`crash`) |
| I4 | `ask(p, A)` is True exactly when `ask(~p, A)` is False | `check_I4` | `negate(p)`: `Not(p, evaluate=False)` (`Not(Not(q))` is `q`).  SymPy's `Not(rel)` *rewrites* a `Relational` (`Not(x >= a)` is `x < a`), which is not the negation when `x` can be non-real: every round-1 I4 report was that rewrite | both definite and not opposite (`wrong`), one definite and the other None (`lost`), error on one side (`crash`) |
| I5 | an equivalent restatement of the set gives the same answer | `check_I5` | 65 %: `restate` per conjunct: relation sides swapped (`lt(a, b)` -> `gt(b, a)`), the three spellings of a relation, a relation shifted (`rel(a, b)` -> `rel(a + c, b + c)` for a finite `c`, or `rel(-b, -a)`; scalar sides without `nan`), `Implies` as `Or` or as its contrapositive, `Equivalent` as two `Implies`, `Q.is_true` around an atom, `~eq` <-> `ne` (complements for every value; `~lt` is *not* `ge`), `zero(x)` <-> `eq(x, 0)` for a commutative non-matrix `x`, a predicate **split** by SymPy's own fact rules (`_SPLIT`: `real` as `negative | zero | positive`, `nonnegative` as `zero | positive`, `nonzero` as `positive | negative`, `positive` as `nonnegative & nonzero`, `zero` as `nonnegative & nonpositive`, `integer` as `even | odd`, `odd` as `integer & ~even`, `rational` as `real & ~irrational`, ...), a conjunct the predicate **implies** added (`_IMPLIED`: `positive(x)` -> `positive(x) & real(x)`, `prime` -> `+ integer`, `zero` -> `+ even`, `real` -> `+ hermitian`, ...: each pair is a rule of `sympy.core.assumptions._assume_rules`), the same predicate on a **transformed term** with the same truth for every scalar value (`_TERM_FORMS`: `positive(x)` <-> `positive(2*x)`, `<-> negative(-x)`, `zero(x)` <-> `zero(-x)`, `<-> zero(3*x)`, `even(x)` <-> `even(x + 2)`, `integer(x)` <-> `integer(x + 1)`, `real(x)` <-> `real(x + 1)`, `finite(x)` <-> `finite(2*x)`, ...), De Morgan on a negated `And`/`Or`; the negations inside are `negate` (never SymPy's rewrite).  Round 4: the relation rewrites come first and often (`_shift_relation`: shifted by a constant, shifted by a side of the relation itself (`a < c` -> `0 < c - a`, finite sides), scaled by a positive constant, negated and swapped), and **equivalences under a declared fact** (`_GIVEN`, `restate_given`: `positive(x)` <-> `gt(x, 0)` <-> `~nonpositive(x)` for `x` declared real, `<-> ge(x, 1)` declared integer, `even` <-> `~odd` declared integer, `irrational` <-> `~rational` declared real, `extended_*` <-> the finite predicate declared finite, `real` <-> `finite` declared extended real, `~lt(x, y)` <-> `ge(x, y)` both declared real; each proved by hand for the declared class, guarded by `assumptions0`, never by an `ask`, and checked at every admissible pool value by `test_given_restatements_agree_on_declared_values`).  35 % (`I5_SYNTAX_RATE`): `syntax_form`, the same conjuncts reordered, one duplicated, nested once or twice, built with `And(..., evaluate=False)` so that SymPy keeps the spelling; rebuilt from a seed, so the shrinker can drop conjuncts.  **The proposition** (round 4, `I5_PROP_RATE` 30 % of the first round, and always the second round of every query: `kind: prop`): `restate_prop`, `restate` on the proposition, or the proposition padded with a tautology (`p & (a | ~a)`) or a contradiction (`p | (a & ~a)`) over a fresh symbol `iw` (declared at random), `evaluate=False` | as I2; the scope is a tag |
| I6 | renaming symbols and functions to fresh names gives the same answer | `check_I6` | `rename`: fresh `Symbol`/`Dummy` with the same `assumptions0`, fresh `Function`s, names whose sort order differs, rebuilt by `_rebuild` (keeps the spelling of `Not`/`And`/`Or` nodes; `xreplace` would rewrite them); in the same process, and for 4 % of the checks in a fresh interpreter under `PYTHONHASHSEED` 1-3 (`checker.process_outcome`) | as I2 |
| I7 | changing a setting after queries gives the answers of a fresh engine with that setting | `check_I7` | 1-8 earlier stream queries in one engine, then `setattr(engine, setting, value)` (`discovery_budget`, `transfer`, `relevance`, `uninterpreted`; the no-op session-reuse settings were removed in #97 P7), against a fresh engine with the setting | as I2 (settings are keyed since the S fix: a setting change drops the engine's caches); one finding per run |

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
3. the assumption set is consistent (`consistent_by`): **the engine or a
   concrete model**.  `Engine.verdict` (a fresh engine, the set's
   complete check: full escalation and search) is `consistent` for `A` or
   for a set with
   the same models (the restated set for I5, the renamed one for I6) or of
   one whose consistency implies `A`'s (`A & B` for I2 and I3: `B` is
   satisfiable over fresh symbols, or `p`/`~p` as answered, or a declared
   fact).  When the engine finds none (it raises, or the set holds a
   Float, a matrix, a relation it cannot read), `harness.models.find_model`
   substitutes a grid of values for the symbols (`POOL`: exact rationals,
   algebraic and transcendental irrationals, a Float, non-real constants,
   the infinities; each respecting the symbol's declared assumptions, at
   most 300 assignments) and evaluates with the conservative evaluator
   (`evaluate_at`: order relations are False off the extended reals,
   `eq`/`ne` are structural on the evaluated sides, a vocabulary predicate
   is SymPy's `is_<name>` of the number, anything else is None, three-valued
   through the connectives).  A model found means consistent; none found
   stays inconclusive and the candidate is *not* reported.  The path is
   recorded in the case (`consistent_by`: `engine` / `model`); a model
   found after the engine said no is logged (`GUARD_DISAGREEMENTS`), never
   reported.

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
# wall time): 8 profiles x 6 configs (`default`, `budget`, `tight`,
# `notransfer`, `lean`, `boundary`; `reuse` and `whole` were dropped after
# round 3, they reported only what the others did; `boundary` has every
# setting at its smallest legal value: discovery budget 1, cone threshold
# 0, session limit 1, no session kept, caches of size 2) x the seeds,
# visited round robin in slices of 30 queries until the budget is spent;
# I1 (three drops) and I2 (three variants, one of them with blocks on
# average) run first on every query, I5 twice (the second on the
# proposition), I4 under every config; the last line printed is
# {"cpu_seconds", "rounds", "queries"}
python -m harness invariants --nightly --seeds 0-2 --out harness-results/invariants

# a subset, unbounded
python -m harness invariants --inv I1,I2 --profile transfer,links --config default,budget --seeds 0-4 --queries 120
```

Measured (round 4, fc1ad99, this machine): `--nightly --minutes 2.5`
with one seed visits 18-19 slices (540-570 queries with their derived
ones; 2,000 I1 checks, 2,000 I2 checks (three variants, 40 % with
blocks), 680 each of I3/I4/I6/I7, 1,360 I5) in 150 s of CPU, about 8 s
per slice including the fingerprints and the shrinks.  The 20-minute run
visits roughly 140-150 slices, about 4,500 queries, 16,000 I1 checks and
16,000 I2 checks; the family cap per run keeps the shrinking from
repeating: with the cap (seed 13) the same 2.5 minutes visited 24
slices (720 queries, 2,200 I1 and I2 checks), 122 candidates were
family repeats (not shrunk), 4 of the 25 reports were pinned matches
(tagged, not shrunk), and the constant classes are kept out of the
family key (the same mechanism with another constant is one family).  Round 3 (d21e655): 2-8 s per slice,
150-180 slices in 20 minutes.  At most five reports per invariant and *one* of one shape
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

## Scope tag (round 4: the veto is gone)

`scope_of(prop, assum)` is `sympy_api.out_of_scope` allowing the
"relation" category, recorded in every I2/I5 case (`scope`: `in`,
`matrix`, `custom`, `other`).  The engine's documented scope is not an
exemption in the invariants: an answer that changes because an unrelated
matrix atom, `Q.is_true` over a non-relation or an unregistered predicate
was added is an I2 violation (the engine answers None for the whole set
by its contract, and the contract is what the invariant judges), and the
same for I5.  Rounds 2-3 vetoed such cases; round 4 reports them, with
the kinds `oos:matrix`, `oos:is_true`, `custom`.

## Families, fingerprints and the budget

Before a candidate is shrunk it is **fingerprinted** (`fingerprint`):
its variant is replayed under probes that switch one mechanism off
(`PROBES`: `relevance=False`, `transfer=False`, `uninterpreted="none"`,
no cone sessions, the discovery budget lifted to 400, relations off),
and the probes under which the difference vanishes are the fingerprint
(`"none,norel"`, `"-"` for none; the probe `none` makes unread
assumption atoms sink the answer instead of staying opaque, the engine
default since the opaque-conjuncts change; before it the probe was
`free`, the other direction).  The **family key** is (invariant,
severity, base, variant answer, kinds (I2) or variant kind (I5), fingerprint):
two cases with the same answer shape but different fingerprints are
different families.  The key is matched against the pinned cases of the
same shape (`harness/repros/invariants`, fingerprinted lazily once per
process): a match is reported *once per run*, tagged `known:pinned:<stem>`,
and never shrunk; any other family is reported and shrunk at most
`FAMILY_RUN_CAP` (2) times per run, whatever the profile or
configuration (`family_repeat` in the slice's `inconclusive` counts the
rest).  The per-slice caps of round 3 (five per invariant, one per shape
and kinds) still hold; the fingerprint lets a new family through the
shape cap.  Cost: a fingerprint is six replays of the pair, 10-100 ms
on the shrunk cases seen.

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
  every config).  Fixed (nightly family A): the glue reads `Q.zero(t)` as
  the equality `t = 0` (`relations.glue_atoms`); both cases are in `fixed/`.
* **I3, `lost`** (round 2, pinned: `I3-declared-fact-loses-definiteness-budget`):
  `ask(Q.negative(1/(z0 + 1)), Q.positive(he) | Q.negative_infinite(-3/sqrt(f(z0))))`
  is False under the `budget` config and None once `~Q.irrational(z0)`
  (declared: `z0` is zero) is added: the discovery budget family of
  round 1's I3 case.
* **I7, `depends`**: fixed (settings are inputs; the pinned case is in `fixed/`).
* I1, I3, I6: no violation in about 20,000 checks; the I1 candidates
  seen were all under inconsistent sets (rejected by the guard).  I1
  also turns a few consistent definite answers into `ValueError`
  (fewer clauses, yet an inconsistency report): not a violation as I1
  is stated, so not reported.

## Round 4 (the review's recommendations)

Implemented, in the review's order: **1** unrelated blocks with verified
witnesses (`Unrelated.block`, `harness/models.py`; 40 % of the I2 checks,
`blocks` in the case, the kind `block` when conjuncts of the material
share a symbol); **2** the consistency guard with the concrete-model path
(`consistent_by`, `find_model`, `consistent_by` in the case,
`GUARD_DISAGREEMENTS` logged); **3** the `in_scope` veto removed from
`check_I2`/`check_I5` (`scope` is a tag; out-of-scope material back in
the unrelated material at `OOS_RATE`); **4a** the proposition restated
(`restate_prop`, the second I5 round of every query), **4b** equivalences
under a declared fact (`_GIVEN`, `restate_given`, self-checked at
declared values), **4c** the relation rewrites first and likely
(`_shift_relation`: constant shift, shift by a side, positive scaling,
negated-swapped); **6** the `boundary` preset, `reuse` and `whole`
dropped from the nightly; **7** fingerprints, the family key, pinned
cases matched once per run and never shrunk, any family at most twice
per run; **8** three I2 variants and two I5 rounds per query; **5** the
classified constant pool (`harness.models.CONSTANTS`: `rational`,
`algebraic`, `transcendental`, `float`, `unsettled` (forms SymPy's exact
evaluation cannot settle: `cos(1)**2 + sin(1)**2 - 1`, `log(2) + log(3)
- log(6)`, ...), `nonreal`, `infinite`; `_FINITE_CONSTS` is built from
it, relation sides use the real classes only, and an I2 case records the
classes present in its material as `const:<class>` kinds).  Everything
in "Keep" is kept.

### Status after the opaque default (`uninterpreted="free"`)

The harness's `EngineConfig` follows the engine default
(`uninterpreted="free"`: an unread assumption conjunct is an opaque
atom); the old behaviour is the preset `none` (which replaces the
preset `free`).  The pinned cases had stored the old default in their
`config`; they now replay with `"free"` (`budget`, `boundary`, `tight`
too: those presets only change other fields).  The guard
(`consistent_by`) still runs the engine with `"none"`: a model of the
opaque abstraction is not a model of the set.  Moved to `fixed/`:

* out-of-scope material (W2A3): `I2-matrix-atom-conjunct-loses-definite`,
  `I2-unregistered-predicate-conjunct-loses-definite`, `-loses-true`,
  `I2-compound-with-unregistered-predicate-loses-definite`;
* the padded proposition (K4): `I5-proposition-padded-with-contradiction-lost`;
* the unread unrelated relation (K2): `I2-closed-relation-conjunct-loses-definite`,
  `I2-context-free-fact-lost-with-unrelated-conjunct`,
  `I2-definite-lost-with-unrelated-conjuncts`,
  `I2-definite-lost-with-unrelated-relation`,
  `I2-self-assumption-lost-with-unrelated-conjunct`,
  `I5-constant-relation-conjunct-restated`.

### Status after the complete set check (#73)

Every assumption set gets one complete check when its contextual
session is built (`Engine.verdict`: the whole cone escalated,
propagation, search, in the session the set's queries then use).  The
guard reads that verdict: only `consistent` is a model (`unknown`, a
theory that gave up or a cone cut by the discovery budget, is none).
The three `budget` cases (`discovery_budget=5`) no longer violate at
that budget and move to `fixed/`:
`I2-predicates-only-exhaust-discovery-budget`,
`I3-declared-fact-loses-definiteness-budget` (K7),
`I5-implied-conjunct-rescues-budget`.  The families are shifted, not
fixed: the check's escalation only moves where the budget cuts (task 6 /
R2).  Failing variants stay pinned:
`I2-predicates-only-exhaust-discovery-budget-budget2`
(`discovery_budget` 2) and `I5-implied-conjunct-rescues-budget-budget1`
(`discovery_budget` 1) here; K7c (the I3 family, no failing budget with
the original set), H2b, W2B3b and W2B3c in
`tests/test_invariant_repros.py`.

### Status after the budget became a test on the query's cone (#53 task 6)

A query is budget-limited iff the weight of its structural cone
`cone(p) | cone(a)` (templates, derived nodes, extension facts, relation
glue) exceeds `discovery_budget`, decided before any session work
(`Engine._within_budget`): such a query is None, a set over the budget is
`unknown`, and every other query runs discovery and escalation uncapped
(no session is ever truncated).  The answer and `last_budget_limited` are
functions of the query.  Fixed and moved to `fixed/`:
`I2-predicates-only-exhaust-discovery-budget-budget2`,
`I5-implied-conjunct-rescues-budget-budget1`,
`I5-proposition-negated-swapped-boundary-budget`; K7c, K8, W2A4 and H2b
are unpinned.  What remains is by design ("above the discovery budget
the answer is None", issue #72): the budget weighs the set the engine is
asked under, so whenever the relevance layer does not split it down to
the query's component (`relevance=False`, a vocabulary registration in
force, opaque or keyless sets) unrelated material counts, and any
restatement of a set may weigh differently; between the two weights the
spellings differ.  The heavier one is None, flagged `last_budget_limited`,
never a wrong value, and each answer is a function of (p, a, config,
registry) (`tests/test_budget_cone.py`, H2's residual).  The invariant
harness therefore exempts a pair from I2, I3 and I5 when a side's answer
is a budget-limited None (not from I4: p and Not(p) have the same cone;
not from soundness I1), and counts the exempt pairs in its report.

The findings below describe the cases as found.

### Findings of round 4 (`harness/repros/invariants/`, all `depends`)

* **I2, out-of-scope material** (three pinned:
  `I2-matrix-atom-conjunct-loses-definite`,
  `I2-unregistered-predicate-conjunct-loses-definite`, `-loses-true`,
  and `I2-compound-with-unregistered-predicate-loses-definite`):
  `ask(False, Q.extended_real(j))` is False and None with
  `Q.symmetric(M)` (a fresh 2x2 `MatrixSymbol`) added; `ask(Q.finite(j),
  True)` (`j` declared) is True and None with an unregistered predicate on
  a fresh symbol added; the same with the predicate inside an `Or`.  The
  engine answers None for the whole set by its documented contract
  (`sympy_api.out_of_scope`), and the invariant does not exempt it: a
  proposition that is `False` is False under every consistent set.
  Fingerprint `-` (no mechanism switch removes it).  Reported in every
  slice before pinning; once per run now.
* **I5, shifted relations** (two pinned: `I5-shifted-equality-self-
  assumption-lost`, `I5-shifted-order-relation-self-assumption-lost`):
  `ask(Q.eq(sqrt(r), g(sqrt(r)/c)), Q.eq(sqrt(r), g(sqrt(r)/c)))` is True
  (the set is the proposition) and None with the set spelled
  `Q.eq(-g(sqrt(r)/c), -sqrt(r))` or `Q.eq(sqrt(r) + 1, g(sqrt(r)/c) + 1)`;
  `ask(Q.lt(T, z), Q.lt(T, z))` (`T` a sum with `1/ep` and
  `sqrt(3)*pi/2`) is True and None with the set `Q.lt(T - 2, z - 2)`.
  The relation glue does not normalise a shifted or negated relation to
  the one asked (every config, including `default`; fingerprint `-`:
  not transfer, not relevance, not the budget).  The rewrite branches of
  round 3 sat behind several coin flips; recommendation 4c reached them
  in the first slice.
* **I5, the proposition** (pinned: `I5-proposition-negated-swapped-
  boundary-budget`): `ask(Q.lt(T, z), Q.lt(T, z))` under `boundary`
  (discovery budget 1) is True and None with the proposition spelled
  `Q.lt(-z, -T)`; fingerprint `budget` (lifting the budget removes it).
* **I5, the proposition padded** (pinned:
  `I5-proposition-padded-with-contradiction-lost`):
  `ask(Q.hermitian(2 + sqrt(2)*(3 + pi)), Q.is_true(True))` is True and
  None with the proposition spelled `p | (Q.extended_negative(iw) &
  ~Q.extended_negative(iw))` (a contradiction over a fresh symbol, the
  same models); `Q.prime(I)` is False and None padded with a tautology.
  The set `Q.is_true(True)` is one the engine's guard does not read: the
  concrete-model path decided it (`consistent_by: model`, trivially).
* **I5, the proposition evaluated by SymPy** (pinned:
  `I5-proposition-evaluated-by-sympy-gains-true`): `ask(Q.ne(3*m - 1/(3*m),
  -1/(3*m)), ~Q.commutative(-1/(3*m)) | Q.composite(3*m - 1/(3*m)))` is
  None under `boundary` (found at `discovery_budget` 1; pinned at 400
  since task 6 of #53, where the budget-limited None is exempt and the
  mechanism persists); the proposition spelled `Ne(...)` evaluates to
  `True` in SymPy (the difference is `3*m`, `m` declared nonzero: a sound
  evaluation from the declaration) and the answer is True.  The
  `Lt`/`Q.lt` spellings are taken as equivalent (above); this is the
  pinned `I5-constant-relation-conjunct-restated` mechanism on the
  proposition side.
* **I2, `crash`** (pinned: `I2-unsettled-constant-in-relation-raises-undecided`):
  `ask(Q.zero(g(n) + 2), Q.zero(n))` is None and raises
  `satassume.constfield.Undecided` ("cannot show Element(sin(pi/7)**2 +
  cos(pi/7)**2 + -1) nonzero") with the unrelated conjunct
  `Equivalent(Q.lt(u, oo), v - 1 + sin(pi/7)**2 + cos(pi/7)**2 >= 1.0e-9)`
  added: `relations._link_integer` tests `payload.offset` for truth and
  `constfield.Element.__bool__` raises on an unsettled constant; the
  exception escapes `ask`.  Found by the constant pool in the CI stream
  on its first run (`default` config; fingerprint `norel`).
* **I2, blocks**: in the first runs every block finding was the
  known relation family (`None -> False` with a block holding a relation,
  fingerprint `norel`, the kinds `block, relation`); no new mechanism
  yet.  The witnesses verify (57 of 60 blocks built; the rest discarded).
* **Guard disagreements**: none logged in the runs (every reported case
  was decided by the engine, `consistent_by: engine`); the model path
  decided no reported case, so no report rests on it.

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
* **I1 with the rule blocks as clauses**: 1,890 checks (every I1 check
  of 540 queries over six profiles under `default`, `budget`, `lean`,
  `I1_BLOCKS_ALL=1`), 498 inconclusive (an inconsistency report on one
  side, or the eager reference differing), no violation: dropping among
  the block clauses loses definiteness only.
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

* I1 drops the rule blocks only as clauses (`blocks: true`, the eager
  form); the lazy closure propagator itself (`_BlockClosure`) and learnt
  clauses are not dropped.
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
  (`positive(x) & integer(x)` as `prime(x) | composite(x) | eq(x, 1)`)
  is not generated.  The proposition is restated (round 4) but not
  across the proposition and the set.
* I2's unrelated material never includes a second application of a
  function of the query; the blocks hold no undefined function (the
  witness could not be verified) and no infinity.
* The model path of the guard cannot read a matrix atom, a custom
  predicate or an undefined function (None: inconclusive), so a
  candidate whose set the engine refuses *and* holds one of these is
  still not reported.
* The fingerprint probes are six fixed switches; a family that two
  mechanisms produce under the same switches has one key.
* No classified constant pool in the generators (recommendation 5).
* No Hypothesis variant of the checkers (the ddmin shrink is the only
  shrinking); no cross-process confirmation of the cases.
