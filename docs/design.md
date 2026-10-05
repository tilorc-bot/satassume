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
visited breadth-first; derived nodes wait in `deferred`. A query runs root propagation; if that leaves it
open and the session is `incomplete`, `escalate` compiles everything
parked and visits the derived nodes; only then does search run
(`Solver.entails` in `satassume/solver.py`, MiniSat-style CDCL under
solver assumptions, at most two searches). A template's query about the
node being built returns None (`Engine._constructing`).

The discovery budget (`discovery_budget`, 400) is a test on the query,
not a cap on a session (#53 task 6): before any session work,
`Engine._within_budget` weighs the structural cone `cone(p) | cone(a)`
(`Engine._struct`, `_cone_info`: every object the templates, derived
nodes and extension facts reach, and for a relation atom what its glue
can visit, `relations.glue_objects`; 1 per node, 2 for a node with both
compiled patterns and formulas). Over the budget the query is None
(`last_budget_limited`, `stats["budget_limited"]`), whatever is cached, and
a set over it is `unknown` without a check; within it, discovery and
escalation run uncapped, so no session is ever truncated and the answer is
that of the whole cone. Both are functions of the query, never of earlier
queries or the caches (sessions are no longer reused). On the corpus and
the stream the largest cone weighs 16, so no default query is
budget-limited.

### A session per query

`Engine.ask` builds the session of the query's assumption set
(`Engine._build_context`: `Session.assume_formula`, then the set's
complete consistency check), answers the proposition in it and discards
it (issue #97). `Session.assume_formula` guards every clause of the
formula by a fresh selector variable and passes the selector as a solver
assumption, so nothing derived under the assumptions reaches level 0,
hence the cache. What the engine keeps of a set between queries is a
function of the set alone: its verdict and, when its construction raised
`Uninterpreted`, the message.

### Cone sessions of `Engine.is_` (#116)

A context-free query `is_(node, pred)` that the fact cache does not answer
is answered in the *cone session* of `node` (`Engine._cone_session`): a
session over the whole cone of the node (`ensure(node, None)`, then
`escalate()`), built once per process and configuration and kept in
`engine._CONE_SESSIONS[cfg][node]`, where `cfg` is the registry epoch, the
settings fingerprint, the templates, the extension registry and the
relation specs (`Engine._cone_cfg`). Every engine of that configuration
shares it, and every later query about the node, whatever the predicate,
reads its answer there: the root value of the literal, else a complete
search (`Solver.entails`) (`Engine._cone_answer`). A new cone starts from
a copy (`Solver.clone`, `Session.adopt`) of the largest cached cone among
the node's kids, a sub-cone of it. The cone session also carries the
weight of its cone, so a hit skips the budget walk (`_cone_info`), and the
answers given in it, None included (`CONE_MEMO`).

Only pure propositional cones are cached: no custom or relation atom, no
Tseitin auxiliary, no theory, not truncated, no conflict at root. Any other
cone, and a cone that a search finds unsatisfiable, takes the per-query
path (a fresh session per query, demand-driven discovery, escalation only
when propagation does not decide), which answers or raises as before.

Why answers do not depend on earlier queries: let F be the clause set a
fresh session builds for the whole cone, a function of the node and `cfg`.
The cone session's clause database is F plus clauses and root units
derived from F by propagation and conflict analysis (all entailed by F),
and a copy of a child's cone holds the child's F, a subset of the
parent's. So it is equivalent to F. Its answers are True iff F entails
`pred(node)` (a root value is entailed; `entails` searches without a
conflict or time budget, so its SAT/UNSAT calls are exact), False iff F
entails the negation, None otherwise. That is the answer of the per-query
path too: propagation over part of F is sound for F, and when it does not
decide, that path escalates to all of F and searches it completely; if F is
unsatisfiable without a root conflict, both search and the cone is dropped
before anything learnt in it can be read. Learnt clauses, saved phases,
activities, stored models (`CONE_RING`) and the order of the watches change
which model a search finds and how fast, never whether one exists. The
state of a cone session is history-dependent (which queries searched in it,
which child it was copied from); its answers are not. `CONE_REUSE = False`
answers every search in a copy of the cone taken before any search (no
learnt clause, no root unit carried over; the stored models are kept),
at about +7% of the corpus `is_` time; without the models too it costs
about +20% (numbers in PR #119).

Earlier designs reused one session per assumption set (`keep_sessions`
= 16, LRU, replaced after `session_limit` = 2000 nodes, by a cone search
of a fresh session over the assumptions and the query's cone once more
than `cone_threshold` nodes polluted it, or when a theory in it gave up;
the four settings were removed in #97 P7),
and before that a single global session. Every reuse was a channel for
history dependence (the learnt clauses, the tableau basis and the branch
budget of integer branch and bound, giving up on constants, the glue of
earlier queries), each closed by a mechanism of its own (a cone search,
re-answering a query in a rebuilt session, dropping dead sessions,
holding writeback); issue #97 replaced them by the build per query, at
1.3x the cost on the refine stream and no cost on the corpus (the
per-query switching of the glue, #53 stage 5, was the last step of
reuse and the first of this design: a set's glue at the root, a query's
delta switched). The four settings stay as documented no-ops so that
configurations remain valid.

### Context-free fact cache: a memo of `is_`

`DictCache` (200,000 nodes, cleared when full) maps a node, by hash and
`==`, to its context-free facts; `custom_cache` holds custom-predicate
atoms. Since issue #97 (P2) the caches are pure memos of `Engine.is_`:
`is_(node, pred)` stores its own answer under `node`, True or False,
never None, keyed on the registry epoch and the settings fingerprint
`(templates, transfer, uninterpreted)` (`DictCache._epoch`, `_settings`;
`Engine._check_version` drops a cache whose epoch or fingerprint is not
the engine's, so a cache shared between engines of different settings
starts empty for each, and engines of the same settings share hits);
nothing else writes there (`Engine._put_result`
is the one writer), and no session reads there (a visited node asserts no
cached fact as a unit clause; a contextual session derives every fact
from its own clause set). The memo is sound because the session of
`is_(node, pred)` is exactly the one a fresh engine builds for the same
query: nothing of the engine's state enters a session, so its clause set
is a function of the node, the predicate, the registry and the settings,
and its answer is an entailment of that set (the harness `audit` mode and
`tests/test_writeback_provenance.py` check the memo against a fresh engine
per node). Structurally equal nodes share entries: a node's context-free
facts depend only on its structure and declared assumptions. An unsound
template still does not stay local: its consequences are memoized and
change later answers about other expressions (issue #47, below).

The `writeback` setting keeps its name: `"root-only"` (the default)
memoizes, `"none"` memoizes nothing (for measurement). The policies of
#53 stage 3, `"provenance"` (every root fact of a session whose provenance
lay in its node's cone, with owner tracking in the solver and a
provenance test per fact, `Session.writeback`, `_home_of`, `_walk`) and
`"all"` (every root literal, history-dependent), are removed and raise
`ValueError`; `_put_root_only`, which also wrote the queried node's other
root facts, went with them. What was lost: a contextual session no longer
starts from the memoized facts of its nodes (it propagates them again),
and `is_` memoizes one fact per session instead of the node's vocabulary;
the numbers are in the P2 report of issue #97.

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

### Constant propositions: context-free first

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

- a definite context-free answer never raises:
  `ask(Q.prime(7), Q.composite(7))` is True (`sympy.ask` trusts the
  assumption: False). Its padded form (`& (Q.complex(w) | ~Q.complex(w))`)
  takes the general path and raises. The invariant harness cannot report
  that pair: it reports neither a `ValueError` side nor an inconsistent
  set (`harness/INVARIANTS.md`, "The oracle").

Fallback on None (nightly family C): when the context-free answer is None
the proposition is answered under the assumptions like any other (the
general path, with relevance), and so raises for an inconsistent set. The
shortcut alone used to drop the assumptions about a constant not decided
context-free (`nan`, `pi + E`, Floats): `ask(Q.rational(pi + E),
Q.rational(pi + E))` was None but True once the proposition was padded
with a tautology over another symbol (invariant I5); likewise
`Q.positive(E**pi - pi**E)` and `Q.positive(g(1))` (`class g(Function)`)
under themselves. All are now True. Removing the shortcut altogether was
tried and rejected: the definite constant answers under inconsistent sets
would raise.

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

An assumption set is split into components, and a query is answered under
the components connected to it unless the whole set is inconsistent
(`sympy_api._relevant`, `_Split`, `_keys_rel`,
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
   whole set's verdict (`Engine.verdict`) if it has a relation or a keyless
   conjunct, else each component's, must not be inconsistent. The verdict comes from the one
   complete check every assumption set gets when its contextual session is
   built (`Engine._build_context`, `_complete_check`: in that session, at
   every construction of it, first or rebuilt, the whole cone escalated,
   propagation, then a search, so the session the queries use is built the
   same way every time; if the check makes a theory give up, a plain
   session without the check replaces it. Counted in `stats["set_checks"]`;
   `Engine._verdict` memoizes it per formula, to raise for an
   inconsistent set without building anything and to answer
   `Engine.verdict`, which keeps no session: the whole set of a split set
   is usually never queried, and its session would evict the parts'). It is
   three-valued: `inconsistent` (a conflict: every query under the set
   raises), `unknown` (no conflict, but a theory gave up, the set's cone is over the
   discovery budget (then no session is built) or the check failed; never raises, and certifies) and
   `consistent`. The switches `CHECK_SEARCH`, `CHECK_SEARCH_RELATIONS` and
   `CHECK_ESCALATE` are gone: the complete check always escalates and
   searches.
4. A certified set answers `ask(p, part)`. Any other set (inconsistent, out
   of scope as a whole, an exception) is answered under the whole `a`,
   None or `ValueError` included.

Keys of an expression: its free symbols, the classes of its undefined
function applications (`f(x)` and `f(y)` share `f`), the closed terms whose
facts SymPy does not decide context-free (Floats, `f(1)`, `pi - 3`,
undecidable constants; not Rationals nor the `K` constants of
`_const_free`, `pi`, `E`, `sqrt(2)`, `2*pi`, ...), and a closed term or
Rational that is a predicate's argument (`Q.polar(2)`, `Q.positive(pi)`).
A relation's keys are those of its sides, with the same rule for a closed
side: `x = 2` and `x < pi` key only `x`, `x = 1.5` keys `x` and `1.5`. No
split for a registered custom predicate, `Q.is_true` of a non-relational,
anything not a Boolean over applied predicates, a query without keys, a
set or query with a term a vocabulary predicate is registered for
(`_vocab_blocks`), and, with `RELATIONAL = "whole"`, a set or query with a
relation or a keyless conjunct.

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
- **Why components are independent** (for a relation-free set without
  sign atoms on sums sharing a symbol, the per-component checks equal a
  whole-set check and the part answers as the whole set would): templates
  relate a node only to its own subterms and derived nodes built from them
  and create no relation atoms; constants in templates are resolved in
  place, and a Rational is a node only as a predicate's direct argument,
  where it is a key; declared facts belong to the symbol's node, in one
  component; the `DictCache` holds root facts only; and without a relation
  no theory in the session merges terms. So components without shared keys
  share no solver variable. For a set with a relation, a keyless conjunct
  or such sign atoms (below), the theories can merge terms of different
  components (a common value, D3 in "What connects"), so this identity is
  not claimed: the whole set's verdict decides raising, and the part's
  answer is sound (entailed by a sub-conjunction) and never the other
  definite value, but may be less definite than the whole set's (None
  where value merging across components decided it before).
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
- **Sign facts on sums start the glue without a relation.**
  The theory scope of a query (`scope.theory_scope`, #97 P3; before that
  `Session._affine_links`, #51) has the relation glue without a relation
  atom when two sign atoms of the set and the query are on different sums
  sharing a symbol (`Q.positive(z - 1) & Q.negative(z - 3)`). The pair
  concerns one component, but once the glue exists `Relations.note_formula` makes the
  argument of every unary atom of the assumptions a link candidate, in
  every component: `zero(x)` and `zero(y)` both become `eq(·, 0)`, `x` and
  `y` merge in EUF and congruence merges their applications. So under
  `Q.zero(x) & Q.zero(y) & Q.zero(bj(y)) & Q.nonzero(bj(x)) & Q.positive(z - 1)
  & Q.negative(z - 3)` (`bj = besselj(1, ·)`) the whole set is inconsistent
  while each component is consistent on its own. `_relevant` therefore
  treats a set whose sign atoms on sums would start the glue
  (`theory_scope(a, None).glue`) like a relational one: the whole set's verdict
  decides raising, so every query under that set raises
  (`test_sign_sums_set_raises_for_any_component`). The part's answers stay
  sound; they may be less definite than the whole set's (`Q.zero(bj(x))`
  under the set without `Q.nonzero(bj(x))`: True as a whole, None under
  its part), as for a relational set.

### What connects

With a relation in the set or the query, the session is built with the
theories (`scope.theory_scope`: glue, and predicate transfer when the
relation atoms make an equality; nothing switches on later) and
every vocabulary argument `e` gets the link `zero(e) <-> eq(e, 0)`. In one
session, terms pinned to a common value merge in EUF, congruence carries
the merge to `sin(x)` and `sin(y)` (any head), and predicate transfer
shares their facts:

| how the common value arises | example that connects `x` and `y` |
|---|---|
| user equalities | `x = 2`, `y = 2`; also `x = 2` and `sin(2)` |
| `zero` and its link | `Q.zero(x)`, `y = 0` |
| values LRA derives, through interface equalities decided in search | `x + 1 = 3`, `2*x = 4`, `2 <= X <= 2`, `X = Y + 2 & Y = 0` against `y = 2` |
| values the rule base derives | `Q.nonnegative(x) & Q.nonpositive(x)` against `y = 0` |

A key made of Rationals cannot describe this: the joining value may come
from arithmetic, from order relations, or from no Rational at all. Hence
the three modes of `RELATIONAL`:

- `"components"` (default since #53 R2): a set or query with a relation
  splits by the keys above like a relation-free one; a common value does
  not connect. Raising is decided by the whole set's verdict
  (inconsistent: answered under the whole set, which raises; consistent or
  unknown: under the part). Answering under a sub-conjunction is sound by
  monotonicity whatever the verdict, so no argument about what the
  theories could merge is needed; keys only decide which answers are kept.
  The part's session holds only its component: its own theories, LRA
  branch budget, give-up and transfer engagement, so an unrelated
  relation, undecidable constant, integer block or equality no longer
  changes an answer (K1, K5, W2B3b/c, W2B4 in
  `tests/test_invariant_repros.py`). Keyless conjuncts (`Q.lt(1, 2)`,
  `Q.lt(pi, 4)`) join no component; the whole-set verdict covers them.
  **Behaviour change (decided, D3):** the rows above connect only within
  one component. `Q.positive(sin(x))` under
  `Q.eq(x, 2) & Q.eq(y, 2) & Q.positive(sin(y))` is answered under
  `Q.eq(x, 2)`: None now, True under `"whole"`. (With an undefined `f` in
  place of `sin`, the class of `f` is a key, `f(x)` and `f(y)` stay
  connected, and the answer stays True.) The answers lost are exactly
  those a common value carried between otherwise unrelated conjuncts.
- `"whole"` (ablation, the default before R2): a set or query with a
  relation, or with a keyless conjunct (only Rationals inside relations,
  `Q.lt(1, 2)`), is not split; its answers are the whole set's by
  construction, and unrelated conjuncts share one session's theories.
- `"rationals"` (ablation, measured, not used): relational sets split, with the
  Rationals on the sides of an equality, the 0 of `zero` and the Rationals
  inside closed terms as extra keys. It connects `x = 2` with `y = 2` but
  not the derived rows above, so it loses answers. Before landing it was
  worth about half a point of the replay on the Pi (-8.6% and -8.8%
  against -8.1% and -8.4% for `"whole"`); 167 of 3,244 split answers on
  the stream involved a relation. The mode remains as dormant code.

`RELATIONAL` is a module constant, not a setting: changing it needs
`_KEYS.clear()`, since keys depend on it (the tests' fixtures do this).

An opaque relation (one no theory interprets, a free atom with the default
`uninterpreted="free"`) links nothing: `Relations.process` links the sides
of a user relation only once a theory has interpreted it.

`tools/relevance_fuzz.py` (relevance on against off) is mostly relational:
at landing only about 5% of its queries went to a part, and it has no
relation-free mode nor a fresh recheck of `whole-only` differences.

## History independence

The property: an answer of `ask` is a function of the proposition, the
assumptions, the engine configuration and the registered extensions, never
of earlier queries, of what is cached or evicted, or of `PYTHONHASHSEED`.
State that could carry a dependence: a session's root facts written to
the cache and cached facts asserted as units (both gone with #97 P2: the
cache is a memo of `is_` that no session reads), one reused session per
assumption set (gone with #97 P1), caches that omit the registry (#63).

Issue #53 is the umbrella (seven defect groups); group 1, non-total
templates (`x*A`, `Abs(A)`), is fixed by #54 and #61. `harness/` (#55) checks the property
differentially and pins the known cases as strict xfails in
`tests/test_history.py` (fixed ones move to `harness/repros/fixed/`).
Landed since: caches and sessions keyed on the registry state (#63),
provenance writeback (stage 3; replaced by the pure memo of `is_` in #97
P2), one complete consistency check per set
(stage 4), the relation glue and predicate transfer switched per
query by selectors (stage 5, [theories.md](theories.md), "Switched
glue"), which fixed families G, G', T and S, and the session built per
query and discarded (#97 P1, "A session per query" above): the reused
session, the carrier of the remaining known families (the branch budget
and the constants of integer branch and bound, `tests/test_lra_exhaustion.py`),
no longer exists, and with it went the mechanisms that argued each
case (`_path_dependent`, the re-answer, the cone search, dead sessions,
held writeback).

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
