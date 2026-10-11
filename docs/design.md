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

## Package layers

The package is cut into layers. Top-down (each layer imports only the
layers below it):

| Layer | Path | The decision it hides |
|---|---|---|
| 8 | `ref.py` | the reference implementation of [spec.md](spec.md) |
| 7 | `sympy_api.py` | the SymPy front end: how `ask`'s propositions become formulas |
| 6 | `engine.py` | sessions, discovery and caching: how a query is decided |
| 5 | `scope.py` | which of the relation machinery a query gets |
| 4 | `relations.py` | what relation atoms mean: normalisation of SymPy relations, their links to the unary vocabulary, which theories a session gets and which terms each sees |
| 3 | `theories/` (`lra/`, `euf/`, `transfer.py`) | how relation atoms are decided: one DPLL(T) theory per subpackage or module, told its atoms by `relations` |
| 2 | `knowledge/` (`rules`, `compile`, `extensions`, `domain`, `templates/`) | what is known about predicates and expression classes, and its clause encoding |
| 1 | `sat/` (`formula`, `solver`, `theory`) | propositional formulas and CDCL search, with the DPLL(T) theory contract; no vocabulary |
| 0 | `state/` (`epoch`, `memos`) | when kept state is invalidated: the registry epoch and the process-wide memo tables; owners register their own tables |

Outside the layers: `_compat.py` (imported only by the package
`__init__`, first) keeps the old flat module names importable during the
transition; see "Old module names" below. It imports nothing from the
package, and the layering test treats it as the top.

The rule counts every import, at module level, inside a function or
under `TYPE_CHECKING`, and module names given as strings (`importlib`,
`sys.modules`, `__name__ + ".x"`). Inside `theories` the theories do not
import each other. The lazy imports that keep SymPy, mpmath or rarely
needed code deferred stay lazy; they only point down.
`tests/test_layering.py` checks all of this on the AST of every module.

Why the cut is where it is:

* `relations` and `scope` sit above the theories, not in `theories/`.
  `relations` is the engine's glue to the theories: it is created per
  session, it reads the engine's node facts and the registered
  extensions, and it instantiates the adapters; it changed together with
  `engine` in 25 of its 51 commits on `main`, more than with any theory
  (`transfer` 9, `lra_adapter` 5, `euf_adapter` 4). `scope` reads only the
  query and decides how much of `relations` it gets; all four of its
  commits changed `sympy_api`, `relations` or `engine` too. So
  `theories/` holds the decision procedures and, next to each, its
  adapter from SymPy terms (`lra/lra_adapter.py`, `euf/euf_adapter.py`,
  which `relations` instantiates), and both modules keep their paths. `transfer` changed together with `relations` in 9 of its
  10 commits; it is still a theory (`TransferTheory`, the contract of
  `sat/theory.py`, reading atoms only), and `relations` is its one client,
  as `engine` is the main client of `compile`. Client and provider in
  adjacent layers change together; that is not a reason to merge them.
* `compile` is in `knowledge`, not `sat`: it encodes formulas over the
  predicate basis that `rules` defines (basis literals, definitional
  literals), and both `engine` and `ref` use it.
* `solver` and `theory` stay together in `sat` (4 of `theory`'s 6
  commits changed both): `theory` is the solver's hook contract.
* `constfield` and `lra_bounds` are in `theories/lra/`: only LRA (and
  `relations`, through the LRA adapter's linear forms) reads them.
* `templates/` is in `knowledge`: it is the third source of clauses for a
  node, next to the rule base and the extensions (`rules` and
  `templates/_common` changed together in 6 of 9 commits).
* `engine`, `sympy_api` and `ref` stay modules at the top. Splitting
  `engine` is class-level work; `satassume.sympy_api` is the most
  imported path (SymPy and satrefine import it).

### Where SymPy is imported

SymPy is the input language. Only the modules whose job is to read SymPy
objects import it at module level:

* `knowledge/templates/` (the knowledge per SymPy expression class) and
  `knowledge/domain.py` (which SymPy terms are commutative scalars);
* the theory adapters, which turn SymPy terms into a theory's terms:
  `theories/lra/lra_adapter.py`, `theories/lra/lra_bounds.py` (bounds of
  SymPy constants; mpmath only inside functions), `theories/euf/euf_adapter.py`;
* `sympy_api.py`, the front end.

`relations.py` and `theories/lra/constfield.py` import SymPy only inside
the functions that receive or return SymPy objects. Every other module
imports neither SymPy nor mpmath: `state`, `sat`, `rules`, `compile`,
`extensions`, the decision procedures `lra/lra.py`, `lra/lra_cert.py`,
`euf/euf.py` and `transfer.py`, `scope`, `engine` and `ref`. The engine
handles SymPy objects (it visits expression trees) without importing
SymPy: it imports `templates` and `domain` inside functions. So `import
satassume` loads no SymPy, and each theory is a SymPy-free decision
procedure plus an adapter. `tests/test_layering.py` checks the imports
and, in a fresh interpreter, that importing the package and every module
outside the list above loads neither SymPy nor mpmath.

### Old module names (transitional)

The flat module names before the package move (`satassume.rules`,
`satassume.templates.core`, ...) still import, as the moved module
objects themselves, with a `DeprecationWarning` (`satassume/_compat.py`),
so monkeypatching through an old name still patches the real module.
As before the move, importing a module by its new name also enters its
old name in `sys.modules` (`import satassume.sympy_api` makes
`sys.modules["satassume.rules"]` the rules module), `satassume.rules` is
an attribute of the package, and the few names the old modules had and
the moved ones do not (`memos.engine_memos`, `euf_adapter._structural`,
`relations._optional`) are still served, with a warning. What does not
carry over: a function's `__module__` and a module's `__name__` are the
new names. The aliases are for code written against the flat layout
that runs against a later checkout: branches opened before the move, scripts, an older checkout's
tools. Nothing in this repository uses them (`tests/test_layering.py`
checks the package, `tests/`, `harness/`, `tools/` and `benchmarks/`).
They are removed after the class-level follow-up of the move (PLAN.md,
"Package move: remove the flat aliases").

## Pipeline

`sympy_api.ask(p, a)` does, in order:

1. **Answer memo** `Engine.answers` (100,000 entries), keyed by the SymPy
   objects `(p, a)` and cleared, with `Engine.splits`, when
   the registry epoch (`satassume/state/epoch.py`: extension registries,
   templates, the engine's extensions and theory adapters) changes
   (`Engine._check_version`).
2. **Constant route**, then **relevance** (below; memoized as `(p, part)`).
3. `_engine_ask`: `to_formula` (memoized in `_formula`) translates both
   sides, `Unsupported` gives None; a single atom without assumptions goes
   to `Engine.is_`, anything else to `Engine.ask`. `InconsistentAssumptions`
   becomes `ValueError`; `Uninterpreted` (no theory reads a relation), None.

### Rule base (`satassume/knowledge/rules.py`)

The vocabulary (`PREDICATES`, 33 predicates: what a query may mention) is
wider than what is encoded. A node gets one solver variable per **basis**
predicate (`BASIS`, 14: `algebraic complex composite even
extended_negative extended_positive extended_real finite imaginary integer
polar prime rational zero`). The other 19 are **definitions**
(`DEFINITIONS`): each is a conjunction or a disjunction of basis literals,
exactly equivalent to the predicate under SymPy's rule base, for example
`real = extended_real & finite`, `nonnegative = extended_real & finite &
!extended_negative`, `odd = integer & !even`, `antihermitian = zero |
imaginary`. One is a single literal (`infinite = !finite`), and
`commutative` is the empty conjunction (true of every term in scope, see
"Non-commutative symbols"). `hermitian == real` and `antihermitian == zero | imaginary`
are what SymPy's generic scalar handlers compute; the rule base is
instantiated only for scalar nodes.

`RULES` are 21 rules in the old system's string syntax over the basis
only; `tests/test_rules.py` checks that, under the definitions, their
models are exactly those of SymPy's rules over the whole vocabulary
(`sympy/core/assumptions.py` plus `sympy/assumptions/facts.py`). Their 24
compiled clauses (`RULE_CLAUSES`) are reduced to 22 (`RULE_INSTANTIATED`) by
`minimize_for_propagation`, which drops a clause only when, for each of its
literals, falsifying the others lets the rest derive it by unit
propagation: same models, same propagation. Dropping clauses that are
merely implied would move answers from propagation to search. The solver
installs these clauses once as a rule block (`Solver.set_rule_block`,
`register_block` per node) and propagates it by its exact closure. `polar`
is in no rule (`RULE_FREE`).

#### Where a derived predicate goes

A derived predicate never reaches the solver as a variable of its own
node block. Its literal is rewritten into basis literals wherever a clause
is formed, and how depends on its polarity in that clause:

* **Templates** (`templates/_common.Pattern`): a rule's literals are
  expanded by `rules.expand_clause` / `cnf_of(pred, pos)`. A conjunction in
  positive position (`... -> positive(x)`) splits the rule into one clause
  per conjunct; a conjunction in negative position (a premise
  `positive(x) -> ...`) becomes a disjunction inside the one clause. A
  disjunctive definition behaves the other way round. Premises such as
  `~positive_infinite(x_i)` of the wide Add rules *distribute*: each is two
  literals, so a rule over n of them is 2**n clauses. A rule whose
  expansion would exceed `MAX_EXPAND` (16) clauses is not expanded but
  handed over as a formula (`Pattern.wide`, `Compiled.wide_formulas`).
* **Formulas** (assumptions, the proposition, wide template rules;
  `compile.compile_formula`): a derived atom is its basis formula. In a
  disjunction (`_or_cnf`) conjunctions are distributed up to
  `MAX_DISTRIBUTE` (16) clauses; past that the largest conjunctions get
  Tseitin variables (Plaisted-Greenbaum, one direction only): past
  `MAX_EXACT` (8) conjunctions the largest get variables at once, and
  among the rest a greedy loop gives a variable to one conjunction at a
  time while that lowers the estimated literal count.
* **Queries** (`Session.query_lit`): `pred(node)` is a basis variable, a
  single basis literal, or `(op, literals)`, the definition over the
  node's block, decided by `query_literal` / `_query_all` without a new
  variable or clause.
* **Shared definitional literals** (`Session.dvar`, `Session._dvar`): a
  derived atom that a formula cannot just expand into basis literals (a
  conjunction under a disjunction, a negated conjunction) gets one variable
  per `(definition, node)`, shared by every occurrence (assumptions,
  proposition, relations), with only the direction(s) of its definition
  that the occurrence needs (`'pos'`: variable -> definition, `'neg'`:
  definition -> variable, `'both'`). Linked literals also get the binary
  clauses the rule base gives between definitions of one node
  (`rules.def_implications`, e.g. `positive -> nonnegative`), so a unit on
  one propagates to the others as with a variable per predicate.
  `Session.var` (relations, `is_`) always asks for `'both'`.
* **The shared-variable threshold** (`engine._NEG_SHARED` = 8): an asserted
  *negated* conjunction (`~nonnegative(x)`) is normally expanded into the
  disjunction of negated basis literals. Only when the assumption set has
  at least 8 derived atoms of two or more basis literals does it get its
  shared literal instead (`dvar(atom, 'negunit')`), so that a wide
  proposition over the same atoms is settled by propagation rather than
  one search conflict per atom. This is a function of the set alone.

#### What these encodings do not preserve

The clause sets are equivalent to the old per-predicate encoding (same
models), but unit propagation is weaker wherever a derived literal was
distributed or replaced by a one-direction Tseitin variable. Code that
decides by propagation alone must stay sound when propagation finds less:
in particular it must not take "no conflict by propagation" as proof that
an assumption set is consistent (a set inconsistent only through the
Add-with-`oo` rules and the relation glue propagates cleanly under the
basis; see "Inconsistent assumptions raise `ValueError`").

#### Adding a predicate or a template rule

* A new predicate goes into `PREDICATES` and into exactly one of `BASIS`
  or `DEFINITIONS` (the module asserts the partition). Prefer a
  definition: it costs no variable per node and no rule clause. It must be
  a single conjunction or disjunction of basis literals, exactly equivalent
  under the rule base; `tests/test_rules.py` checks this against SymPy's
  rules over the whole vocabulary (`FULL_RULES`), so state its SymPy rules
  there. A basis predicate needs
  its rules in `RULES` over basis predicates only.
* A template rule may mention any predicate of the vocabulary; it is
  expanded over the basis as above. Count the clauses: a derived
  conjunction as a premise (or a derived disjunction as a conclusion)
  multiplies them, and past `MAX_EXPAND` the rule becomes a formula with
  Tseitin variables, which propagates less. Prefer basis literals where
  the rule allows it (`extended_positive` rather than `positive` when
  finiteness is stated elsewhere).
* Keep the definitions exact: the relation glue (`relations.py`), the
  relevance layer and `def_implications` read `DEF_LITS` and assume that a
  derived literal and its basis formula are interchangeable.
* Check answers against the reference: `satassume.ref.ask_ref` builds the
  whole clause set eagerly and is the specification. Run the differential
  fuzz (`harness/reffuzz.py` on `wip/ci-fuzz`, including inconsistent sets with `oo`,
  `zoo`, `finite`/`infinite`, `extended_*` predicates and relations) and
  the wide-shape tests (`tests/test_wide_derived.py`).

#### Adding a theory

* Put it in its own package `satassume/theories/<name>/`: the decision
  procedure (a class implementing the contract of `satassume/sat/theory.py`,
  importing no SymPy) and, if it reads SymPy terms, an adapter module
  `<name>_adapter.py` with the interface of `EUFAdapter` (`parse`,
  `interprets`, `register`, `attach`, and what `relations` reads of its
  terms: `shared_terms`, `interned`, `term_of`, `terms_since`,
  `node_term`).
  It may import `state`, `sat` and `knowledge`, not the other theories.
* List the adapter in `relations.default_specs` (an explicit relative
  import, an `AdapterSpec(name, factory, guarded)`; a missing module is
  skipped). An engine can also be given its own specs
  (`Engine(relations=...)`, `Engine.relation_specs`) without touching
  `default_specs`.
* Add the adapter module to `SYMPY_AT_IMPORT` in `tests/test_layering.py`
  if it imports SymPy at module level. The layer rules need no change:
  every `theories/<name>/` package imports only itself.
* Mention it in the `theories/__init__.py` docstring and in the tables of
  this section and of README.md, "Layout".

`default_specs` names the adapters instead of discovering them (by
scanning `theories/` or by entry points) on purpose: a discovered adapter
is a dependency that import analysis cannot see, which is what the
string lookup `importlib.import_module("satassume.lra_adapter")` was
before the package move, and the default theories of an engine are a
decision that should be visible in one place.

### Structural templates (`satassume/knowledge/templates/`)

`registry.py` maps SymPy classes to template functions along the MRO;
`atoms.py` gives unit facts for symbols and fixed-value atoms, `core.py`
covers `Add`, `Mul` and `Pow`, `functions.py` the elementary functions,
rounding and `factorial` (an undefined function such as `f(x)` has no
template).

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
  an integer base, `x*y` of a product `c*x*y` with a Rational `c`
  (`_mul_factor_sets`).
- SymPy's own facts about objects enter only here: a `Symbol`'s `assumptions0`, the `is_*`
  properties of atoms with a fixed value (`consts_of`, `constant_units`).
  `commutative` has no template: it is true by definition (see
  "Non-commutative symbols").
- `tests/test_templates.py` evaluates every rule at concrete values, in
  Kleene logic over SymPy's values of the atoms; none may be False.

### Nodes, cones and discovery (`satassume/engine.py`)

A `Session` holds a solver and a `VarTable` giving each visited node 14
variables (one per basis predicate). `Session.node` registers the rule block
and emits its template clauses, but only those about a basis predicate the
query demands of the node (`want_of`); the rest is parked (`pending_c`,
`pending`). No cached fact enters a session as a clause (see
"Context-free fact cache" below). Children are
visited breadth-first; derived nodes wait in `deferred`. A query runs root propagation; if that leaves it
open and the session is `incomplete`, `escalate` compiles everything
parked and visits the derived nodes; only then does search run
(`Solver.entails` in `satassume/sat/solver.py`, MiniSat-style CDCL under
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
`Uninterpreted`, the message. `Engine.is_` uses a fresh session over its
own cone as well.

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
delta switched). The four settings were documented no-ops from P1 to P7;
the constructor now refuses them (`TypeError`).

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
is the one writer), and no session takes its entries as clauses (a
visited node asserts no cached fact as a unit clause; a contextual
session derives every fact from its own clause set). The memo is sound
because the session of `is_(node, pred)` is the one a fresh engine
with the same settings builds for the same query: what enters a session
from the engine's state is the engine's own context-free answers (the
glue's `engine.is_` calls on closed numbers in `relations.py`, which may
be answered from this cache, and the numbers' transfer bases built from
them, `Engine._xbasis`), each a function of the registry and the
settings, and dropped with the other set memos when either changes. So
its clause set
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

`is_constant_proposition`: every predicate is built in (vocabulary or
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

`Session.query_literal` checks the assumptions before it returns any
answer, even when the query is decided at the root, as `sympy.ask` does:
`implied(assumptions)` first, and when propagation settles the query,
`Solver.consistent` (the last model if it satisfies them, else a search),
the check `entails` makes on its own propagation path. A conflict in
either raises `InconsistentAssumptions`, turned into `ValueError`.
Propagation alone is not enough: under the basis encoding a set such as
`Q.extended_positive(x+z+oo) & Q.finite(x+z+oo)` with a relation query
propagates without conflict (the Add-with-`oo` rules distribute their
derived premises) and only a model shows it is inconsistent. Facts a symbol was declared with are facts of its node,
so assumptions contradicting them are inconsistent:
`ask(Q.commutative(x), ~Q.commutative(x))` raises, where SymPy's handler
path trusts the assumption (the five "raises" of the README). Keeping this
or trusting the assumption is still the owner's call; no issue tracks it.

Whether a query raises therefore depends on the clauses of its session
(the set's cone, the query's cone and their glue), not on whether
propagation or search decided it. The relevance split (below) still
answers under the relevant part of a set whose own verdict is consistent,
so a set that is inconsistent only with a relation query's glue can
answer a query about an unrelated part (as before #137).

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

The table is history: `commutative` is now true by definition
(`rules.DEFINITIONS`: no basis variable, no rule, no template), so these
premises hold and the rules apply to every term. That is sound only for
numbers, so terms with a non-commutative subterm never reach the rule base:
`sympy_api` puts a vocabulary predicate of such an argument out of scope
(category `"matrix"`; an opaque atom in the assumptions), and `Engine`, used
directly, answers None for `is_`/`is_many` on such a term and for `ask`
when a vocabulary atom of the proposition or the assumptions has one
(`engine._noncommutative`), and `verdict` is `UNKNOWN` for a set with one. A function registered for `commutative`
(`extensions.register`) is refused with a ValueError: there is no variable
it could set. `structural_commutative` and `function_commutative` are gone.

The answers differ from `sympy.ask`, which reads commutativity
structurally: through `sympy_api`, `Q.zero(A*B)` and `Q.zero(A - B)` are
None (out of scope, category `"matrix"`; SymPy: False). `tests/test_noncommutative.py`
model-checks the templates over 2x2 matrices and checks the Engine's
None answers. Open: `re`, `im`, `sign`, `log` of
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
cache is a memo of `is_` that no session takes as clauses), one reused session per
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
