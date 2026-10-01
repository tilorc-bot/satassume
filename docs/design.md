# Design of the satassume engine

How `satassume.sympy_api.ask` gets from a SymPy proposition to an answer,
and why the semantic choices along the way are what they are. Scope,
routing rule and corpus results are in the [README](../README.md); the
relation theories (DPLL(T), LRA, EUF, predicate transfer, constants in LRA)
are in [theories.md](theories.md); measurements over time are in
[performance.md](performance.md).

## Scope and the non-fallback principle

The engine answers unary scalar predicates from one rule base, one set of
structural templates and one incremental CDCL solver (README, "Routing
rule"). Out-of-scope input returns None before the engine is touched; that
is scoping, and the caller routes such input to SymPy's existing path.
Inside the engine there is no fallback to SymPy's `_eval_is_*` handlers,
`satask` or `sympy.ask`; an early prototype had one, and it was removed: it
hides every template gap from `tools/compare.py`, and the engine exists to
replace those handlers, not to wrap them.

## Pipeline

`sympy_api.ask(p, a)` does, in order:

1. **Answer memo** `Engine.answers` (100,000 entries), keyed by the SymPy
   objects `(p, a)` and cleared, with `Engine.splits`, when
   `_registry_state` (extension registry and version, theory adapters)
   changes.
2. **Constant route**, then **relevance** (below; memoized as `(p, part)`).
3. `_engine_ask`: `to_formula` (memoized in `_formula`) translates both
   sides, `Unsupported` gives None; a single atom without assumptions goes
   to `Engine.is_`, anything else to `Engine.ask`. `InconsistentAssumptions`
   becomes `ValueError`; `Uninterpreted` (no theory reads a relation), None.

### Rule base (`satassume/rules.py`)

One list of 48 rules in the old system's string syntax over the 33
predicates of `PREDICATES`: the rules of `sympy/core/assumptions.py`, the
new-system predicates, and `hermitian == real`, `antihermitian == zero |
imaginary`, which is what SymPy's generic scalar handlers compute (the rule
base is instantiated only for scalar nodes). The 110 compiled clauses are
reduced to 79 (`RULE_INSTANTIATED`) by `minimize_for_propagation`, which
drops a clause only when, for each of its literals, falsifying the others
lets the rest derive it by unit propagation: same models, same
propagation. Dropping clauses that are merely implied would have moved
answers from propagation to search. The solver installs these clauses once
as a rule block (`Solver.set_rule_block`, `register_block` per node) and
propagates it by its exact closure, writing implied literals above the
root only for variables something mentions (see that docstring).

### Structural templates (`satassume/templates/`)

`registry.py` maps SymPy classes to template functions along the MRO;
`atoms.py` gives unit facts for symbols and fixed-value atoms, `core.py`
covers `Add`, `Mul` and `Pow`, `functions.py` the elementary functions,
rounding, `factorial` and a generic `Function` template.

- A rule is an index-based spec `(premises, conclusion)` over literals
  `(k, pred, pos)` (`_common.py`). Specs depend only on the node's pattern
  (class, arity, positions of constants); `resolve` evaluates the constants
  once per pattern, and the result is precompiled into slot-space clauses
  (`Pattern`, `Compiled`) that a visit only shifts by base variables. A
  literal a constant cannot decide (`polar(2)`) drops the rule
  (`_resolve_lit`), so constants never become nodes through templates.
- A template mentions the node, its direct arguments and a few derived
  nodes built from them where the vocabulary cannot say a fact otherwise:
  `2*e` of a power, `x - 1` of `log`/`acos`/`asin`, `b - 1` and `b + 1` of
  an integer base, `x*y` of a term `c*x*y` in a sum with half-integer
  coefficients (`_half_templates`).
- SymPy objects enter only here: a `Symbol`'s `assumptions0`, the `is_*`
  properties of atoms with a fixed value (`is_constant`, `constant_units`)
  and the structural `is_commutative` (`structural_commutative`).
- `tests/test_templates.py` evaluates every rule at concrete values, in
  Kleene logic over SymPy's values of the atoms; none may be False.

### Nodes, cones and discovery (`satassume/engine.py`)

A `Session` holds a solver and a `VarTable` giving each visited node 33
variables. `Session.node` registers the rule block, asserts the node's
cached context-free facts as units and emits its template clauses, but
only those about the rule-base neighbourhood of what the query asks
(`want_of`); the rest is parked (`pending_c`, `pending`). Children are
visited breadth-first up to `discovery_budget` (400) new nodes; derived
nodes wait in `deferred`. A query runs root propagation; if that leaves it
open and the session is `incomplete`, `escalate` compiles everything
parked and visits the derived nodes; only then does search run
(`Solver.entails` in `satassume/solver.py`, MiniSat-style CDCL under
solver assumptions, at most two searches). A template's query about the
node being built returns None (`Engine._constructing`).

### Sessions per assumption set

`Engine._context_session` keeps one session per assumption formula
(`keep_sessions` = 16, LRU; replaced after `session_limit` = 2000 nodes or
when a theory in it gave up). `Session.assume_formula` guards every clause
of the formula by a fresh selector variable and passes the selector as a
solver assumption, so nothing derived under the assumptions reaches level
0, hence the cache, while the session and its learnt clauses serve every
later query under the same assumptions.

Search decides every variable of a session, so its cost grows with what
earlier queries left there. When a query needs search and the session
holds more than `cone_threshold` (3) nodes beyond the assumptions' (closed
irrational constants not counted), it searches a fresh session over the
assumptions and its own cone, which then replaces the reused one, with the
clause `selector -> answer` so a repeat propagates. `Engine.is_` always
uses a fresh session over its own cone. A single global session was tried
first and dropped: its search cost grew with everything asked before.

### Context-free fact cache and writeback

`DictCache` (200,000 nodes, cleared when full) maps a node, by hash and
`==`, to its context-free facts; `custom_cache` holds custom-predicate and
relation atoms. `Session.writeback` stores every literal of the root trail
there, and `Engine.is_` stores its answer, None included. Structurally
equal nodes share entries: a node's context-free facts depend only on its
structure and declared assumptions. This is sound only if every root
literal holds whatever the assumptions: the selector keeps the assumptions
off the root, and the templates must be sound for every value. An unsound
template does not stay local: its root consequences are cached and change
later answers about other expressions (issue #47, below).

## Semantic decisions

### SymPy's `_assumptions` are never read or written

The first default cache stored facts in each node's `_assumptions`. That
imported SymPy's cached handler output as unconditional facts, and some is
wrong: `Pow._eval_is_algebraic` returns True for a zero base without
looking at the exponent, so `(0**n).is_finite` is True (still in SymPy
1.14.0; `0**-1` is `zoo`), after which `ask(Q.positive(0**n),
Q.negative(n) & Q.nonnegative(x))` raised "inconsistent assumptions".
Writing was worse: a `Symbol`'s `_assumptions` is the `StdFactKB` of
`Symbol._canonical_assumptions`, shared by every symbol with the same
assumptions, so a fact derived about `n` held for every plain symbol. So
SymPy objects enter only through the templates, and derived facts live in
the engine's `DictCache` (`ObjectCache` is an alias); the switch had no
measurable cost (bench-container at 07e0bd5). `tests/test_shared_facts.py`
pins the defect; the SymPy bug is not filed upstream.

### Constant propositions ignore the assumptions

`_is_constant_proposition`: every predicate is built in (vocabulary or
relation) and every argument has no free symbols, is a number and contains
no `AppliedUndef` (also not inside `Integral`, `Sum` or `Subs`). Such a
proposition goes to the context-free path: a constant's facts do not
depend on the assumptions, and a relation no theory reads in the
assumptions no longer sinks the query. Custom predicates are excluded, as
the assumptions may be all that is known about them. Answering through
SymPy's old `is_*` properties instead was tried and dropped: it lost 23
gate2 answers (`Q.algebraic(asin(7))`, `Q.imaginary(exp(pi*I/2))`).
Accepted consequences (recorded on #12):

- it never raises: `ask(Q.prime(7), Q.composite(7))` is True (`sympy.ask`
  trusts the assumption: False);
- assuming an undecidable constant fact does not answer it:
  `ask(Q.positive(E**pi - pi**E), Q.positive(E**pi - pi**E))` is None, and
  so is `Q.positive(g(1))` under itself for `class g(Function)` (not an
  `AppliedUndef`, unlike `Function('f')(1)`).

### Inconsistent assumptions raise `ValueError`

`Session.query_literal` checks `implied(assumptions)` before reading the
answer, even when the query is decided at the root, as `sympy.ask` does; a
conflict there or in `entails` raises `InconsistentAssumptions`, turned
into `ValueError`. Facts a symbol was declared with are facts of its node,
so assumptions contradicting them are inconsistent:
`ask(Q.commutative(x), ~Q.commutative(x))` raises, where SymPy's handler
path trusts the assumption (the five "raises" of the README). Keeping this
or trusting the assumption is still the owner's call; no issue tracks it.

It raises only for conflicts it finds: under a set whose conflict only
search reveals, a query decided by propagation answers while one that
searches raises, and which is which can depend on history (#53, group 5).

### Extended reals and `nan` in templates

Templates are theorems about the value of the node under SymPy's
conventions (`1/0 = zoo`, `0**0 = 1`), and `nan` counts as no value: the
soundness oracle makes every predicate implying a number False for `nan`,
leaves `finite`, `infinite` and `commutative` unknown, and skips points
where a direct argument is `nan`. So:

- `extended_real` is not closed under `Add` (`oo - oo`) or `Mul` (`0*oo`);
  an infinite term that is not `-oo` makes a sum infinite only if no other
  term is `-oo` (and symmetrically);
- `1**e` rules need a finite exponent; a zero factor makes a product zero
  only if the other factors are finite (`Q.finite(x*y)` under `Q.zero(y) &
  Q.infinite(x)` is None);
- functions are not declared finite or complex for infinite arguments
  (`re(oo) = oo`, `exp(oo) = oo`, `sin(oo*I) = oo*I`, `log(oo) = oo`); 37
  of the README's 70 deliberate misses come from this.

### Non-commutative symbols

`commutative` is a property of the value: every number, `oo` and `zoo`
included, is commutative, and a non-commutative symbol stands for a value
that is not a number (think of a 2x2 matrix). A product, sum, power or
function of such values can still be a number (`0*A`, `A*A**-1`, `A**2 == 1`
for a reflection, `A - B` at `B = A`, `det(A)`), and a product can be zero
without a zero factor (`A*B`, `A**2` for nilpotent `A`). The downward rules
`commutative(node) -> commutative(arg)` ignored this; with `zero ->
commutative` in the rule base they made `x*A` never zero and `Abs(A)`
inconsistent, and through writeback changed later answers about `x`
(issues #47, #59). Fixed in #54 and #61:

| template | rule now |
|---|---|
| Mul, downward | only when every other factor is a nonzero number (`2*A`, `-A` keep it) |
| Mul, zero product has a zero factor | only with at most one non-commutative factor (all commutative above `MAX_ONEOUT` = 6 factors) |
| Add, downward | only when every other term is a finite number, up to `MAX_ONEOUT` terms |
| Pow, downward | dropped, except `1/b` a nonzero number implies `b` commutative |
| Pow, nonzero power | needs `commutative(b)` |
| Function, downward | dropped; the upward rule stays, but not for `Function(..., commutative=False)` |

These rules need commutative premises, which nothing asserted for terms no
template relates to their arguments (`Max`, `Integral`, `Piecewise`,
`Trace`, `M[0, 0]`, ...; the first version of #54 lost 72 answers on them).
`structural_commutative` emits `commutative(e)`, never its negation, when
SymPy's `is_commutative` is True for `e` and every scalar ingredient;
`e` alone is not enough, since `Subs(x, x, A)` claims True.

The answers differ from `sympy.ask`, which reads commutativity
structurally: `Q.zero(A*B)` and `Q.zero(A - B)` are None (SymPy: False);
`Q.zero(x*A)` under `Q.zero(x)` is None (SymPy: True; `0*(A + oo)` is nan),
True with `Q.finite(A)` added. `tests/test_noncommutative.py` model-checks
the templates over 2x2 matrices. Open: `re`, `im`, `sign`, `log` of
non-commutative arguments (#62); a static totality check (PR #58).

## Relevance

A relation-free assumption set is split into components, and a query is
answered under the components connected to it once the whole set is known
to be consistent (`sympy_api._relevant`, `_Split`, `_keys_rel`,
`_part_consistent`, `_consistent`; switch `RELATIONAL`; off with
`Engine(relevance=False)`; `tests/test_relevance.py`). At landing (99e8827)
the refine stream replay was 8.3% and 8.8% faster on the Pi than
`c8361d7`, answers and errors identical. The saving comes from sharing:
every set with the same relevant part shares memo entries and session.

1. `_Split` divides the conjuncts of `a` into components by shared keys,
   transitively (memoized in `Engine.splits`, 20,000 entries; `_KEYS`
   memoizes keys, 100,000).
2. The query's part is the union of the components whose keys meet its
   own. If that is all of `a`, nothing changes.
3. Otherwise the set is certified once: `to_formula` must succeed and the
   set's verdict (`Engine.verdict`), or each component's if it has no
   relation, must not be inconsistent. The verdict comes from the one
   complete check every assumption set gets when its contextual session is
   built (`Engine._context_session`, `_complete_check`: a session of its
   own, the whole cone escalated, propagation, then a search; memoized per
   formula in `Engine._verdict`, counted in `stats["set_checks"]`). It is
   three-valued: `inconsistent` (a conflict: every query under the set
   raises), `unknown` (no conflict, but a theory gave up, the cone hit the
   discovery budget or the check failed; never raises, and certifies) and
   `consistent`. The switches `CHECK_SEARCH`, `CHECK_SEARCH_RELATIONS` and
   `CHECK_ESCALATE` are gone: the complete check always escalates and
   searches.
4. A certified set answers `ask(p, part)`. Any other set (inconsistent, out
   of scope as a whole, an exception) is answered under the whole `a`,
   None or `ValueError` included.

Keys of an expression: its free symbols, the classes of its undefined
function applications (`f(x)` and `f(y)` share `f`), every closed subterm
that is not a Rational (`pi`, `sqrt(2)`, `2*pi`, Floats, `oo`, `f(1)`), and
a Rational that is a predicate's argument (`Q.polar(2)`). No split for a
predicate outside the vocabulary, `Q.is_true` of a non-relational, anything
not a Boolean over applied predicates, a query without keys, any set while
a vocabulary predicate is registered for a class (`Extensions._vocab`),
and, with `RELATIONAL = "whole"`, a set or query with a relation or a
keyless conjunct.

### Why splitting is sound

- **Answers.** A part is a subset of the conjuncts; whatever it entails,
  the whole set entails, provided the whole set is satisfiable. Keys only
  decide whether an answer is *lost*; connecting more is always safe.
- **Errors.** For an unsatisfiable set SymPy's contract is `ValueError`. A
  part answers only after the check certifies the set, and the check looks
  at least as far as a query would: propagation, escalation of an
  incomplete session, and search. The search is needed: a Boolean conflict
  propagation misses, `(p | i) & (p | ~i) & (~p | i) & (~p | ~i)` over
  `Q.positive(y)`, `Q.integer(y)`, made the old path raise for
  `Q.positive(x)` under it `& Q.real(x)` while a propagation-only check
  certified the set. The search costs 0 to 0.5% of the replay.
- **Why components are independent** (so the per-component check equals a
  whole-set check and the part answers as the whole set would): templates
  relate a node only to its own subterms and derived nodes built from them
  and create no relation atoms; constants in templates are resolved in
  place, and a Rational is a node only as a predicate's direct argument,
  where it is a key; declared facts belong to the symbol's node, in one
  component; the `DictCache` holds root facts only; and without a relation
  no theory in the session merges terms. So components without shared keys
  share no solver variable.
- **Closed non-Rational terms connect.** They became keys when `pi` was a
  bounded LRA variable (`x < pi` and `pi < y`, with `x` and `y` pinned on
  either side, are each consistent and together not). Since #48 `pi` and
  the other closed real constants are exact numbers of the LRA form, so for
  them the key is only conservative; a Float's rationality is still open,
  and `f(1)` is a free EUF term. Rationals have every fact decided
  context-free (except `polar`), so without relations they connect nothing.
- **The invariant.** A session whose set and query hold no relation has no
  theory relating terms of different components. A feature that brings a
  theory into such a session must connect only terms sharing a key, or
  turn the split off.
- **Known gap: sign facts on sums break the invariant.**
  `Session._affine_links` (#51) starts the relation glue without a relation
  atom when two sign atoms are on sums sharing a symbol
  (`Q.positive(z - 1) & Q.negative(z - 3)`), and `_relevant` does not treat
  such a set as relational. The trigger concerns one component, but once
  the glue exists `Relations.note_formula` makes the argument of every
  unary atom of the assumptions a link candidate, in every component:
  `zero(x)` and `zero(y)` both become `eq(·, 0)`, `x` and `y` merge in EUF
  and congruence merges their applications. Fresh engines,
  `PYTHONHASHSEED` 0 to 2, `bj = besselj(1, ·)`:

  | query | assumptions | whole set | relevance |
  |---|---|---|---|
  | `Q.zero(bj(x))` | `Q.zero(x) & Q.zero(y) & Q.zero(bj(y)) & Q.positive(z - 1) & Q.negative(z - 3)` | True | None |
  | `Q.positive(z)` | the same `& Q.nonzero(bj(x))` | `ValueError` | True |

  Without the `z` conjuncts both sides agree. The part's
  answers stay entailed by the part; identity with the whole set and the
  error set break. Sets of sign facts on sums alone do not show it (it
  needs pinned terms and applications of them). Treating such a pair of
  sign atoms as a relation in `_relevant` would restore the invariant.

### What connects

With a relation in the set or the query, the session has the theories and
every vocabulary argument `e` gets the link `zero(e) <-> eq(e, 0)`. Terms of
different components then merge in EUF whenever they are pinned to a
common value, congruence carries the merge to `sin(x)` and `sin(y)` (any
head), and predicate transfer shares their facts:

| how the common value arises | example that connects `x` and `y` |
|---|---|
| user equalities | `x = 2`, `y = 2`; also `x = 2` and `sin(2)` |
| `zero` and its link | `Q.zero(x)`, `y = 0` |
| values LRA derives, through interface equalities decided in search | `x + 1 = 3`, `2*x = 4`, `2 <= X <= 2`, `X = Y + 2 & Y = 0` against `y = 2` |
| values the rule base derives | `Q.nonnegative(x) & Q.nonpositive(x)` against `y = 0` |

A key made of Rationals cannot describe this: the joining value may come
from arithmetic, from order relations, or from no Rational at all. Hence
the two modes of `RELATIONAL`:

- `"whole"` (default): a set or query with a relation, or with a keyless
  conjunct (only Rationals inside relations, `Q.lt(1, 2)`), is not split;
  its answers are the whole set's by construction.
- `"rationals"` (measured, not used): relational sets split, with the
  Rationals on the sides of an equality, the 0 of `zero` and the Rationals
  inside closed terms as extra keys. It connects `x = 2` with `y = 2` but
  not the derived rows above, so it loses answers. Before landing it was
  worth about half a point of the replay on the Pi (-8.6% and -8.8%
  against -8.1% and -8.4% for `"whole"`); 167 of 3,244 split answers on
  the stream involved a relation. The mode remains as dormant code; changing `RELATIONAL`
  needs `_KEYS.clear()`, since keys depend on it.

`tools/relevance_fuzz.py` (relevance on against off) is mostly relational:
at landing only about 5% of its queries went to a part, and it has no
relation-free mode nor a fresh recheck of `whole-only` differences.

## History independence

The property: an answer of `ask` is a function of the proposition, the
assumptions, the engine configuration and the registered extensions, never
of earlier queries, of what is cached or evicted, or of `PYTHONHASHSEED`.
State that can carry a dependence: writeback, cached facts asserted as
units, one reused session per assumption set, caches that omit the registry.

Issue #53 is the umbrella (seven defect groups); group 1, non-total
templates (`x*A`, `Abs(A)`), is fixed by #54 and #61. `harness/` (#55) checks the property
differentially and pins the known cases as strict xfails in
`tests/test_history.py`. Open PRs: #58 (totality gate), #63 (caches and
sessions keyed on the registry state). The later stages proposed on #53 (restricted
writeback, one complete consistency check per set, glue and transfer behind
selectors) are not PRs yet. Still different on `main` (warm, then fresh):

```python
# x, u plain symbols, f = Function('f')
ask(Q.lt(oo + x, 0)); ask(Q.extended_negative(oo + x))   # False; fresh: None
C = Q.zero(u) & Q.positive(f(0))
ask(Q.eq(u, 0), C); ask(Q.positive(f(u)), C)             # True; fresh: None
```

## Beyond the current scope

The long-term goal is to replace SymPy's old `expr.is_*` system with the
same engine (README; [PLAN.md](../PLAN.md)) through `Engine.is_`, which
nothing hooks into SymPy yet. After landing `ask` (route in-scope
`sympy.ask` calls, `Predicate.register` as a shim over
`satassume.register`), that needs:

- a per-object cache with a dictionary-lookup hit path (on five core test
  files only 250 k of 6.07 M `is_*` accesses reached `_ask`), holding
  engine facts only, copying before the first write on every shared fact
  base, and fed by history-independent writeback (#53);
- a cheaper miss path: the old `_ask` computes one fact lazily, the engine
  a node's whole block and cone (118 us per node visit against a 95 us
  average old miss at 744893c, not re-measured since the rule block); if
  parity is out of reach, replacing handlers only where the engine is
  faster is the alternative, and a different design;
- re-entrancy: `Mul.flatten` and `Add` query `is_zero`, `is_commutative`
  and `is_infinite` while building expressions (`_constructing` is a
  start; `sympy/core/tests` with the engine installed is the check);
- coverage of 435 `_eval_is_*` methods in 46 files (no templates yet for
  `Piecewise`, `Sum`, `Product`, `Integral`, special and combinatorial
  functions, `Mod`, `Min`/`Max`; numeric facts such as `_monotonic_sign` as
  clause-generating functions emitting units), and a review of every
  output in SymPy's suite that changes where the old system was wrong.
