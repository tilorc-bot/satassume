# Specification: the answer of `ask(p, A)` as a function

What `satassume.sympy_api.ask(p, A)` computes, as a function of the
proposition `p`, the assumptions `A`, the registry (rules, templates,
extensions, theory adapters) and the engine settings. Every sentence is a
definition, a statement citing the function implementing it (file and
name, at commit `876f37d`), or a property naming the test or tool checking
it. Where issue #97's plan (package P3) changes the function, the paragraph
says "P3, to be implemented" and gives both. "Design" cites
`docs/design.md`, "theories" cites `docs/theories.md`.

Notation. `V` is `PREDICATES`, 33 unary predicate names (`rules.py`). A
*node* is a SymPy expression the session gives 33 solver variables
(`Session.base[node]`, `engine.py`). A *vocabulary atom* is `P(pred, expr)`
with `pred in PRED_INDEX`; a *relation atom* is `P("eq"|"lt", (a, b))`
(`RELATION_ATOMS`, `relations.py`); a *custom atom* is any other `P`
(`formula.py`; `atoms_of(f)` lists a formula's atoms).

## 1. Routing: what reaches the engine

Definition. `ask(p, A)` returns one of `True`, `False`, `None`, or raises
`ValueError`.

1. Answer memo: if `(p, A)` is in `Engine.answers` the memo entry is the answer
   (`sympy_api.ask`; cleared with `Engine.splits` when the registry epoch
   changes, `Engine._check_version`). A budget-limited answer is never memoized
   (`sympy_api.ask`, `last_budget_limited`), so a memo hit never is.
2. Constant route: if `_is_constant_proposition(p)` (every predicate of `p`
   built in, every argument a number without free symbols or `AppliedUndef`),
   the answer is `ask(p, True)`: `A` is ignored (`sympy_api._ask`). Section 9.
3. Relevance: else, if `Engine.relevance` and `A` is `And`, `Or`, `Not`,
   `Implies`, `Equivalent`, predicate or relation (other Booleans reach step 4
   unsplit), the answer is `_engine_ask(p, part)` (`sympy_api._ask`), memoized
   under `(p, part)`, with `part = _relevant(p, A, eng)` (section 7).
4. `_engine_ask(p, A)`: translate `p` by `_formula(p, rel)` and `A` by
   `_formula(A, rel, opaque=True)` (`rel`: the engine has relation specs);
   `Unsupported` gives `None`; `p` as `TRUE`/`FALSE` gives `True`/`False`; `A`
   as `FALSE` raises `ValueError`, as `TRUE` is no assumption. One vocabulary
   atom without assumptions goes to `Engine.is_(expr, pred)`, anything else to
   `Engine.ask(p, A)`. `InconsistentAssumptions` becomes `ValueError`,
   `Uninterpreted` `None` (`sympy_api._engine_ask`).

Property: an out-of-scope query returns `None` before the engine is touched,
and `out_of_scope(p, A)` names the category (`sympy_api.out_of_scope`,
`CATEGORIES`; `tests/test_sympy_api.py`). Note: `out_of_scope` takes no engine
and reports `"relation"` for a relation the default engine interprets (record
3135 below): it describes the engine without adapters.

## 2. Translation: the formulas of `p` and `A`

Definition. `to_formula(expr, relations, opaque)` maps a SymPy Boolean to a
formula over `P` atoms (`sympy_api.to_formula`, memoized by
`sympy_api._formula` in `_FORMULAS`): `Q.pred(e)` with `pred in V` becomes
the vocabulary atom `P(pred, e)`; `And`, `Or`, `Not`, `Implies`,
`Equivalent` become the formula connectives (`satassume/formula.py`);
a relation becomes `relation_atom` (theories, "What relations mean"):
`Eq(a, b)` is `eq(a, b)` with sides in `default_sort_key` order, `a < b` is
`lt(a, b)`, `a > b` is `lt(b, a)`, `a != b` is `~eq(a, b)`, `a <= b` is
`extended_real(a) & extended_real(b) & ~lt(b, a)` with no conjunct for a
Rational or infinite side (`relations.relation_atom`). With `opaque`, a
matrix or unregistered custom predicate in `A` becomes a free custom atom;
in `p` it is `Unsupported` (`sympy_api.to_formula`, the docstring's
"Opaque conjuncts").

## 3. Theory scope

Definition (P3, to be implemented). `theory_scope(A, p) = (glue, transfer,
linked_terms)` is a function of the two formulas' atoms:

- `glue` iff `A` or `p` holds a relation atom, or two sign atoms
  (`_SIGN_PREDS`, `engine.py`) of `A` and `p` together are on different
  `Add` nodes sharing a free symbol (the pair may be one atom of each formula);
- `transfer` iff `A` or `p` holds an `eq` atom;
- `linked_terms` is the set of arguments of vocabulary atoms and sides of
  relation atoms of `A` and `p`, numbers excluded (P3's text says "cones" and
  nothing on numbers; this spec and today's code use the atoms' arguments).

Today's code computes the same three facts in three places, per query:

- `glue`: `engine._links_wanted(atoms_of(A), atoms_of(p))` for the affine pair,
  or a relation atom in `Session.assumption_lits` (`a_rel or p_rel or
  _links_wanted(...)`); the budget's own link test is weaker (section 10, open
  point 1). The glue object itself is created lazily, by the first relation
  atom allocated (`Session._custom`, `Relations(...)`) or by
  `Session._affine_links` when the pair appears.
- `transfer`: `Relations.wants_transfer(atoms)` is true on an `eq` atom (and on
  an order atom whose reverse `_trichotomy` paired, which P3's syntactic test
  does not count: open point 1); engaged once per session
  (`Relations._engage_transfer`), switched on per query (`Relations.xfer_sel`,
  section 5.5).
- `linked_terms`: `Relations.note_formula(atoms)` records every vocabulary
  argument of a user formula as a link candidate; `Relations.process`
  links the sides of a user relation once a theory interprets it;
  `Relations._link(e)` skips numbers.

Property (P3's gate): with the scope on, an answer is the same as or more
definite than without it, never the other definite value
(`tools/relevance_fuzz.py`; the monotonicity argument is P3's report).

## 4. The node cone

Definition. For a cone object `o` (a node, a custom atom or a relation
atom), `kids(o)` is: for a node, every object its templates mention, the
direct arguments and derived nodes of its compiled patterns
(`Compiled.objs[i]` for `i in Pattern.used`, `i != Pattern.node`) and the
arguments of the atoms of its plain formulas and extension facts; for a
custom atom, the arguments of its extension facts; for a relation atom of
an engine with adapters, `relations.glue_objects(atom)`: both sides, the
link objects of each non-number side (`relations.link_objects`: the side,
its structural subterms EUF reads, the opaque terms of its linear forms,
its integrality form), and for `eq` the termwise differences of the sides
(`Engine._struct`, `engine._kid`).

Definition. `cone(o)` is the closure of `{o}` under `kids`
(`Engine._cone_info`). `cone(f)` of a formula is the union of the cones of
`_kid(a)` for its atoms `a`, plus, when `glue` holds, `link_objects(e)` for
every vocabulary argument `e` (`Engine._query_cone`, `_union`).

Definition. The derived nodes templates name: `2*e` of a power with
exponent `e`; `b - 1`, `b + 1` of a power's base; `x - 1` of `log(x)`,
`asin(x)`, `acos(x)`; `x*y` of a term `c*x*y` of a sum with half-integer
coefficients (`templates/core.py` `pow_templates`, `_half_templates`;
`templates/functions.py` `_minus_one`). They are kids whatever holds of
the base (record 1326: `x**y` has kids `2*y`, `x - 1`, `x + 1`).

Property: `cone` is a function of `o`, the registry and the settings, never
of a session (`Engine._struct` docstring; `Engine._cones`, `_kids` are
dropped with the registry epoch). A session visits at most `cone(p) |
cone(A)` plus, in a reused contextual session, what earlier queries left
(`Engine._within_budget` docstring; `harness/` checks history independence,
`tests/test_history.py`).

## 5. The clause set

The clause set of a query is the union of the following, over the session
that answers it (section 8 says which session).

### 5.1 Rule base per node

Definition. `RULE_INSTANTIATED` is the 79-clause minimization of the 110
clauses compiled from `RULES` (`rules.py`, `minimize_for_propagation`;
design, "Rule base"). Every visited scalar node gets one copy over its 33
variables, installed as a rule block (`Session._visit` step 2,
`Solver.register_block`, `Solver.set_rule_block` in `satassume/solver.py`),
unless the node's only template is a complete unit pattern
(`Pattern.complete`: the closed units decide every predicate the rule base
mentions), in which case the units stand alone.

### 5.2 Template clauses per node

Definition. For a node `n`, `registry.clauses_for(n)` is `(compiled,
formulas)`: for each template registered for a class in `type(n).__mro__`
(`TemplateRegistry.templates_for`, most specific first), its result, a
`Compiled` (a `Pattern` applied to concrete objects) or plain formulas
(`templates/registry.py`). A `Pattern` holds rules `(premises, conclusion)`
over slot literals `(k, pred, pos)` after `resolve` evaluated the constant
slots (`_common.resolve`, `_resolve_lit`): a literal a constant decides is
dropped (True) or kills the rule (False); a literal a constant cannot
decide drops the rule; a rule whose conclusion a constant falsifies becomes
the negation of its premises. `Compiled.formulas()` gives the rules as
`Implies`/`Or` formulas over `P` atoms (`_common.instantiate`).

Definition. The clauses of `n` in the session are the clauses of its
compiled patterns shifted by the base variables of `n`'s slot objects
(`Session._compile_patterns`, `_emit_pattern`) and the Tseitin clauses of
its plain formulas (`Session._compile`, `compile.compile_formula`), plus the
node facts of registered vocabulary extensions (`Extensions.node_facts`).

Definition. A node is visited with a demand set (`Session.ensure(node,
demanded)`); clauses mentioning no predicate in `want_of(demanded)`
(`engine.want_of`, `neighbourhood`) are parked in `pending_c`/`pending`,
derived nodes in `deferred`; `Session.escalate` compiles all of it. Section
8 says when; the clause set of the *answer* is always the full cone's
(escalation is uncapped within the budget, `_UNCAPPED`).

Property: every template rule is true at concrete values in Kleene logic
(`tests/test_templates.py`), total over non-commutative values
(`tests/test_noncommutative.py`, `tests/test_totality.py`, `tests/test_total_templates.py`, G7).

### 5.3 The memo of `is_` (no cached unit facts)

Definition. No clause set contains a cached fact: no session asserts an entry of `Engine.cache` or
`custom_cache` as a unit (since issue #97 P2). The caches are memos of `Engine.is_(node, pred)` (section 8, context-free):
key `(node, pred)` under the registry epoch and the settings fingerprint `(templates, transfer, uninterpreted)` (`DictCache._epoch`, `_settings`; `Engine._check_version` drops a cache on a mismatch, so a cache
shared between engines starts empty for an engine of other settings); value True or False, never None
(`_put_result`). Property: an entry is the answer a fresh engine of the same settings gives, since the session of `is_` builds the set of 5.1, 5.2, 5.5 for `node` alone (harness `audit`, G6; `tests/test_writeback_provenance.py`).

### 5.4 The assumption selector

Definition. `Session.assume_formula(A)` compiles `A`'s Tseitin clauses with
the fresh selector variable `s` added negated to each clause and returns
`[s]`; a query assumes `s` (`Session.assumption_lits`, first element).
Nothing derived under `s` reaches the root trail, hence the cache
(design, "Sessions per assumption set").

### 5.5 Glue and theory clauses (only when `glue`)

Definition. With `glue`, every linked term `e` gets the link clauses
`extended_positive(e) <-> lt(0, e)`, `extended_negative(e) <-> lt(e, 0)`,
`zero(e) <-> eq(e, 0)`, each guarded by the term's selector `link_sel[e]`
(`Relations._link`), and an integrality atom when LRA reads its linear form
(`Relations`, theories "Integrality", `relations.INTEGERS`). Every `lt` atom
gets the side clauses, infinite-term clauses and a guarded LRA twin
(`Relations._order_sides`, `_order_infinite`, `_interpret`); every `eq` atom
goes to EUF and, under the real guard, to LRA; `_eq_infinity`, `_eq_links`,
`_trichotomy` clauses carry their atoms' selectors (`Relations.atom_sel`).
Interface equalities between LRA and EUF terms are added by
`Relations._share`. Transfer lemmas `eq(a, b) -> (P(a) <-> P(b))` are
enforced by `TransferTheory` (`satassume/transfer.py`) under `xfer_sel`.

Definition. A query assumes, after `s`: the selectors of `A`'s links and
atoms (as root units when `A` has a relation atom, `Session._set_glue`;
else as one group selector, `Session._group_sel`), then the selectors of
`p`'s links and atoms not already on (`Relations.selectors_of`), then
`xfer_sel` when `transfer` holds (`Session.assumption_lits`). A clause
whose selector is not assumed is inert for the query (theories, "Switched
glue"). Property: the glue a query sees equals a fresh session's for
`(p, A)` (`harness` profiles `links`, `transfer`, gate G5).

### 5.6 Clauses of custom atoms

Definition. A custom atom asserts its cached value (`Engine.custom_cache`) and
its registered clause-generating functions' formulas (`Session._custom`,
`satassume/extensions.py`, `satassume.register`).

## 6. The literal of `p`

Definition. If `p` is a vocabulary atom `P(pred, e)`, its literal is
`base[e] + PRED_INDEX[pred]` after `Session.ensure(e, {pred})`
(`Engine._literal`). Otherwise it is the Tseitin literal of the formula
(`Session.literal_of`, `compile.formula_literal`), memoized in
`Session.literals`. In both cases the nodes of `p`'s vocabulary atoms are
visited (`Session._ensure_atoms`) and the glue is told about `p`
(`Session._relations` or `Session._affine_links`).

## 7. The verdict of `A` and the relevant part

Definition. `verdict(A)` is one of `INCONSISTENT`, `UNKNOWN`, `CONSISTENT`
(`Engine.verdict`): `UNKNOWN` without any session if `cone(A)` is over the
budget; otherwise the result of `Engine._complete_check` run in the
session built for `A` (`Engine._build_context`): escalate the whole cone,
propagate, `Solver.implied([s, ...])`, then one search `Solver.solve`;
`INCONSISTENT` on a conflict, `UNKNOWN` if no conflict but a theory gave
up, exhausted its branch budget or the session is incomplete, else
`CONSISTENT`. Memoized per formula in `Engine._verdict`.

Definition. `_Split(A)` divides the conjuncts of `A` into components by
shared keys, transitively (`sympy_api._Split`, keys by `_keys_rel`: free
symbols, `AppliedUndef` classes, closed terms not in `K`
(`_const_free`), closed terms or Rationals that are a predicate's direct
argument; a relation keys its sides). `part(p, A)` is the conjunction of
the components whose keys meet `keys(p)` (`_relevant`, `_Split.part`).

Definition. `_relevant(p, A)` returns `A` itself when: the split is opaque,
a vocabulary extension blocks it (`_vocab_blocks`), `p` has no keys, the
part is all of `A`, or `A` is not certified. Else it returns `part`.
Certification: when `A` has a relation atom or a keyless conjunct, or
`engine.affine_glue(A)` holds, `A` is certified iff `verdict(A)` is not
`INCONSISTENT` (`_consistent`); otherwise iff every component's verdict is
not `INCONSISTENT` (`_part_consistent`). With `RELATIONAL == "whole"` a
relational or keyless set is never split (`sympy_api.RELATIONAL`).

Property: answering under a sub-conjunction is sound by monotonicity, and
the whole set's verdict decides raising (design, "Why splitting is sound";
`tests/test_relevance.py`, `tools/relevance_fuzz.py`).

## 8. The answer as entailment

Definition. Let `C` be the clause set of section 5 over the session's
nodes `cone(p) | cone(A)` with the theories LRA (`satassume/lra*.py`),
EUF (`satassume/euf.py`) and transfer attached when `glue`, and `L` the
assumption literals of section 5.4 and 5.5. Let `q` be the literal of `p`.

- If `C & L` is unsatisfiable: `ask` raises `ValueError` (section 1.4).
- Else if `C & L |= q`: `True`; if `C & L |= ~q`: `False`; else `None`.

Today's code computes this in steps (`Engine._ask`): `Session.query_literal(q,
L, search=False)` reads the propagation closure (`Solver.implied(L)` raises on
conflict); if open and the session is incomplete, `escalate` and propagate
again; if still open, `Solver.entails(q, L)` searches, at most twice (design,
"Nodes, cones and discovery"). The session: for `Engine.is_` a fresh one over
`cone(e)`; for `Engine.ask` with assumptions the contextual session of `A`
(`Engine._context_session`, built by `_build_context`, LRU of `keep_sessions`,
replaced after `session_limit` nodes) or, when search is needed and it holds
more than `cone_threshold` nodes beyond `A`'s, a fresh session over `A` and
`cone(p)` (`Engine._ask`, `cone_search`). After a cone search, the clause
`~L | q` (or `~q`) is added to the replacement session so a repeat propagates
(`Session._emit` in `Engine._ask`); other paths add nothing.

Property: the answer does not depend on which session answered, on earlier
queries, on the caches or on `PYTHONHASHSEED` (design, "History independence";
gates G4 `tests/test_history.py`, G5 `harness fuzz`, G6 `harness audit`). Where
a reused session's answer could depend on its path (branch budget, give-up,
undecidable LRA constants: `engine._path_dependent`, `_cannot_give_up`), it is
re-answered in a rebuilt session (`Engine.ask`, `stats["exhaust_reanswers"]`).

Property: with `None` meaning "not entailed", the engine's answers agree
with SymPy's on the corpus with `none=0` contradictions (`tools/compare.py
--in-scope-only`, gate G3) and the frozen gate2 records change only at
#2186 and #2836 (`tools/gate2.py`, gate G2).

## 9. Undecidable constants

Definition. A constant is an atom with `is_number` (`_common.is_constant`,
`consts_of`). Its facts are `const_value(c, pred)`, SymPy's static `is_*`
properties plus the derived new-system predicates (`_common.const_value`).

Rules:

1. In a template, a literal about a constant that `const_value` does not
   decide drops the rule (`_resolve_lit` returning `None`); a constant never
   becomes a node through a template.
2. A constant that is a node (a predicate's direct argument, a relation
   side, or a symbol-free non-atom like `E**pi - pi**E`) gets
   `constant_units` closed under the rule base (`templates/atoms.py`,
   `_common.units`), or its structural templates; `polar` is undecidable for
   every number (`atoms.py` comment).
3. A constant proposition is answered without `A` (section 1.2), so
   `ask(Q.positive(E**pi - pi**E), Q.positive(E**pi - pi**E))` is `None`
   and `ask(Q.prime(7), Q.composite(7))` is `True` (design, "Constant
   propositions ignore the assumptions"; `tests/test_sympy_api.py`,
   `tests/test_lra_constants.py`).
4. In LRA, a comparison a pivot path cannot decide marks the theory
   `undecidable`; the query is then answered as a fresh engine would
   (`engine._cannot_give_up`, `_path_dependent`; `theories.md`, "LRA").
5. EUF interns Rationals as pairwise-distinct values; Floats, `pi`, `oo`
   are opaque constants (`euf_adapter.EUFAdapter.term`).

## 10. Budgets

Definition. `weight(cone)` sums the objects' weights: 1 per node, 2 per node
with both compiled patterns and plain formulas, 0 per custom or relation atom
(`Engine._struct`); it measures the clause set's size by nodes with their
clauses (section 5), not by clause count. `within_budget(p, A)` iff
`weight(cone(p) | cone(A)) <= discovery_budget` (400), links included when a
cone holds a relation atom or the cones hold two sign-atom sums with free
symbols (`Engine._within_budget`, `len(sums) >= 2`: no shared-symbol test,
weaker than `glue`).

Rules:

1. A query over the budget is `None` without session work
   (`Engine._over_budget`, `last_budget_limited`, `stats["budget_limited"]`),
   unless `A` fits the budget and `verdict(A)` is `INCONSISTENT`: then it
   raises (`Engine.ask`). `Engine.is_` over the budget is `None` whatever is
   cached.
2. A set over the budget has verdict `UNKNOWN` and builds no session
   (`Engine.verdict`).
3. A query within the budget runs discovery and escalation uncapped: no
   session of such a query is truncated (`Engine._note_budget` assertion).

Property: the budget is a function of the query, the registry and the settings
only (`Engine._within_budget` docstring; `tests/test_budget_cone.py`,
`tests/test_set_verdict.py`); largest corpus or stream cone: 16 (design).

## 11. Open points

1. The engine's per-query theory scope is three tests in three places (section 3); `theory_scope`
   as one function is P3. Differences: `wants_transfer` counts a `_trichotomy` pair (P3's test does
   not); the budget's link test (section 10) counts sign-atom sums over disjoint symbols (`glue` does not).
2. Glue is created at the first relation atom of *any* formula compiled in the session, extension facts
   included (`Session._custom`); selectors keep it inert, but `cone` counts `glue_objects` only for relation atoms of `p` and `A`.
3. `out_of_scope` ignores the engine's adapters (section 1).
4. The clause set is stated per session; `satassume.ref.ask_ref` (P5b) is the session-independent
   one the harness compares against. Section 8's "at most two searches" is design.md's; `Engine._ask` is the code.
5. Section 5.3's property (cached units change no answer) is checked by the harness, not
   proved here; the provenance rule is `Engine._put_result`.
6. Section 3's `glue` rule does not fire on a sign atom over a sum whose summand carries an
   `infinite`/`finite` atom, although 5.5's clauses decide it (`~Q.nonzero(oo + acos(-1/x))`
   under `Q.infinite(acos(-1/x))`); a relation atom unlocks the glue and the relevance split
   (1.3, 7) discards it: `ask_ref` answers under the whole set, the engine does not (repro
   `fixed/L1-learnt-unit-written-back` row 0, tag `relevance`). Sound, an accepted loss under 1.3; P3 follow-up.

## 12. Ten corpus records

Sampled from `queries.jsonl` with `random.seed(97)` over kind-stratified pools
(constant, unary, relational, Boolean, `old`), replacing one matrix record and
one `prop == true` record; shapes computed with `Engine._query_cone`,
`registry.templates_for`, `_relevant` and the section 3 definition. Scope is
`(glue, transfer, linked_terms)`.

| line | query | route | cone nodes (templates firing) | scope | literal | answer |
|---|---|---|---|---|---|---|
| 374 | `Q.negative(zoo)`, `True` | constant, `Engine.is_` | `zoo` (`constant_units`, 32 units) | `(F, F, {})` | `base[zoo]+negative` | False |
| 392 | `Q.positive_infinite(I*x)`, `Q.real(x)` | `Engine.ask`, part = whole | `I*x` (`mul_templates`, 16 rules), `x` (`symbol_units`) | `(F, F, {I*x, x})` | `base[I*x]+positive_infinite` | False |
| 636 | `Q.algebraic(1 + I)`, `True` | constant, `Engine.is_` | `1 + I` (`add_templates`, 9 rules; `1`, `I` resolved in place) | `(F, F, {})` | `base[1+I]+algebraic` | True |
| 1326 | `Q.rational(x**y)`, `Q.rational(y) & Q.eq(x, -1)` | `Engine.ask`, part = whole (relational) | `x**y` (`pow_templates`, 57 rules), derived `2*y`, `x - 1`, `x + 1` (`mul`/`add_templates`), `x`, `y`, `-1` (relation side), atom `eq(-1, x)` | `(T, T, {x, y, x**y})` | `base[x**y]+rational` | None |
| 1875 | `Q.odd(2*x)`, `Q.irrational(x)` | `Engine.ask`, part = whole | `2*x` (`mul_templates`, 41 rules), `x` | `(F, F, {2*x, x})` | `base[2*x]+odd` | False |
| 2369 | `Q.algebraic(log(x))`, `Q.algebraic(x)` | `Engine.ask`, part = whole | `log(x)` (`log_templates`, a name generated in `templates/functions.py`, + `function_commutative`, 18 rules), derived `x - 1` (`add_templates`), `x` | `(F, F, {log(x), x})` | `base[log(x)]+algebraic` | None |
| 2514 | `Implies(Q.real(x), Q.positive(x))`, `True` | `Engine.ask`, no assumptions | `x` (`symbol_units`) | `(F, F, {x})` | `literal_of(Implies(...))` | None |
| 2639 | old: `(x**2).is_imaginary` | `Engine.is_` | `x**2` (`pow_templates`, 32 rules), `x` | `(F, F, {x**2, x})` | `base[x**2]+imaginary` | None |
| 2968 | `Q.integer(x)`, `Q.integer(x)` | `Engine.ask`, part = whole | `x` (`symbol_units`) | `(F, F, {x})` | `base[x]+integer` | True |
| 3135 | `x < 0`, `x >= 0` | `Engine.ask`, part = whole (relational) | `x`, `0` (`constant_units`), atom `lt(x, 0)`; `A` is `extended_real(x) & ~lt(x, 0)` | `(T, F, {x})` | `literal_of(lt(x, 0))` (a relation atom is not a vocabulary literal) | False |

Every record's engine answer equals its recorded value; the heaviest union
`cone(p) | cone(A)` weighs 7 (record 1326), within budget; every verdict is
`CONSISTENT`; `structural_commutative` is registered for every class and emits
at most `commutative(e)` (`None` for `_STRUCTURAL` classes, matrices and
`Function` nodes with `Expr` arguments, which `function_commutative` covers).
