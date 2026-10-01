# Minimal repros of history-dependent answers (engine at c26e5e1)

All of them still reproduce at a186157, except G1-G6 (fixed by #51) and C,
C2-C5, C4b (fixed by #54), B, B2, E1c (fixed by the complete set check,
#73), and E1, E1b, L1, C6b, D (fixed by the writeback rule of #53:
`Engine(writeback="root-only")`, the default, and the opt-in
`"provenance"`; `Session.writeback`, `Engine._put_root_only`), now in `fixed/`; `tests/test_history.py` pins each file here as a strict xfail.

Each `NAME.py` runs standalone from the repository root
(`PYTHONHASHSEED=0 python harness/repros/NAME.py`); each `NAME.json` can be
re-run with `python -m harness repro harness/repros/NAME.json [--hashseed N]`.
All of them were confirmed in fresh interpreters under several hash seeds.
"engine" is the answer after the prefix in one long-lived default
`Engine`; "fresh" is the answer of a new `Engine` to the same query.

| repro | prefix | query | engine | fresh |
|---|---|---|---|---|
| A | `Implies(Q.transcendental(w*j**2), Q.transcendental(1/2))` under S | `Equivalent(Q.extended_nonpositive(j), Q.finite(p))` under S | ValueError | True |
| B | `ask(Q.algebraic(x + A), True)` | `ask(Q.algebraic(x + A), Q.algebraic(x + A))` | ValueError | True |
| B2 | `ask(Q.prime(I*n), True)` | `ask(Q.prime(I*n), Q.prime(I*n))` | ValueError | True |
| C | `ask(Q.positive(1/A), True)` | `ask(Q.finite(A), True)` | True | None |
| C2 | `ask(Q.positive(1/A), True)` | `ask(Q.infinite(A), Q.infinite(A))` | ValueError | True |
| C3 | the fuzzer's original one-query prefix for C | `ask(Q.finite(A), True)` | True | None |
| C4 | `ask(Q.positive(1/A), True)`; `ask(Q.zero(x*A), True)` | `ask(Q.zero(x), True)` | False | None |
| C4b | same two | `ask(Q.zero(x), Q.zero(x))` | ValueError | True |
| C5 | `ask(Q.positive(1/(x*A)), True)` | `ask(Q.finite(x), True)` | True | None |

with `A = Symbol('A', commutative=False)`, `x` a plain symbol, `n` integer, `j` even integer,
`w` nonzero, `p` positive, and
`S = Q.commutative(j) & Q.noninteger(I*j**2*w) & Q.extended_negative(I*j**4*w**2*(I*j**2*w - 1/(j**4*w**2)))`.

## Mechanisms (first analysis)

All three families come from one design fact: **what the engine knows at
decision level 0 depends on how much of the cone has been instantiated,
and instantiation is driven by the history of queries, not by the query.**
Two consequences follow.

### A. An inconsistent assumption set is detected only once some query escalated the session

Repro A no longer differs since #63 (it is in `fixed/`): the prefix query
raises in both engines, and the session under which a query raised is now
dropped, so the final query is answered from a fresh session, as a fresh
engine does.  Since #73 every assumption set gets one complete
consistency check when its session is built (`Engine._context_session`,
`Engine._complete_check`: the whole cone, propagation, then search,
memoized per set), so an inconsistent set raises for every query,
whatever the query and whatever ran before; the description below is of
the engine before that.

`Session.query_literal` (`satassume/engine.py`, lines 469-503) checks the
assumptions' consistency with unit propagation only (`solver.implied`).
Search runs only when the query literal is undecided, and escalation
(compiling the parked template clauses, visiting the derived nodes
`2*e`, `b - 1`, ...) happens only then (`Engine.ask`, lines 787-815), and
is permanent for the reused session (`Session.escalate`, 420-446).  So a
query that propagation decides is answered True/False under an
inconsistent set as long as no earlier query under the same set escalated
or searched; after one that did, the same query raises.  In repro A the
prefix query needed search, escalated the session, and the root-level
conflict is visible from then on.  A fresh engine answers True; the same
engine, ValueError.  The relevance path (`sympy_api._relevant`) does run a
searching consistency check, but only when the query touches a strict
subset of the set's components.

### B. A cached context-free fact contradicts an assumption that a lazily built session would accept

*Fixed by the complete set check (#73, see A): the set's own check
escalates the cone and finds the conflict, so both engines raise; B and B2
are in `fixed/`.*

`Session.node` compiles only the template clauses that mention a predicate
in the rule-base neighbourhood of what the query demands (`_split`,
`want_of`, engine.py 853-891) and parks the rest.  For `Q.algebraic(x + A)`
the Add pattern's `commutative` clause is parked, so a fresh session never
derives `~algebraic(x + A)` (which needs `algebraic -> complex ->
commutative` against `A`'s declared non-commutativity through the
pattern); the assumption is accepted and the query, implied by it, is True
without search.  A context-free query about the same node
(`Engine.is_`) escalates fully, derives `algebraic(x + A) = False` and
writes it to the engine's `DictCache`; every later session asserts cached
facts as unit clauses when it visits the node (engine.py 219-222), so the
assumption now conflicts at propagation and the query raises.  B2 is the
same with `prime(I*n)`.

### C. Facts about arguments derived from a parent's structure are cached on the arguments

*Fixed by #54 (#47) for the non-commutative cases below; the repros are in
`fixed/`.  The carrier (write-back of a parent's structural facts to its
arguments) remains; see C'.*

`Session.writeback` writes every root literal of every node of a session
to the engine's `DictCache`, arguments included, and the templates have
rules whose conclusions are about arguments (`_ADD_SUBTRACT`, the Mul
zero rule, `commutative(node) -> commutative(arg)`, ...).  Whenever a
*structural* fact about the parent refutes an upward rule's conclusion at
level 0, the refutation flows down to the arguments, and the cone of an
argument alone never contains it.  The trigger found by the fuzzer is a
non-commutative symbol `A`: SymPy makes every `Mul`/`Pow`/`Add` holding it
non-commutative, and the rule base has `zero -> even -> integer ->
rational -> real -> extended_real -> commutative`, so such a node is
never zero at level 0.  Then:

* `1/A`: the Pow pattern `infinite(b) & negative(e) -> zero(b**e)`
  (`templates/core.py`, line 397) gives `~infinite(A)`, i.e. `finite(A)`
  (`infinite == !finite`).  Repro C: `ask(Q.finite(A))` None fresh, True
  after any visit of `1/A` (also `A**-2`, `1/(A*B)`); C2: `ask(Q.infinite(A),
  Q.infinite(A))` True fresh, ValueError after;
* `1/(x*A)` for a *plain* `x`: the same gives `finite(x*A)`, and the Mul
  pattern's finiteness rules give `finite(x)`.  Repro C5:
  `ask(Q.finite(x), True)` None fresh, True after;
* `x*A` once `finite(A)` is cached (from `1/A`): the Mul zero rule
  `zero(x) & finite(A) -> zero(x*A)` with `~zero(x*A)` gives `~zero(x)`.
  Repro C4: `ask(Q.zero(x), True)` None fresh, False after
  `ask(Q.positive(1/A))` and `ask(Q.zero(x*A))`; C4b: `ask(Q.zero(x),
  Q.zero(x))` True fresh, ValueError after.  The fuzzer's s18 group is the
  same chain through `im`: `~zero(im(g(n)))` gives `~real(g(n))`, so
  `ask(~Q.prime(g(n)), True)` turns from None into True.

SymPy itself answers `(x*A).is_zero` and `(1/A).is_zero` with False and
`A.is_finite`, `x.is_zero` with None: the engine's structural facts agree
with SymPy, and its rules are SymPy's, but the combination derives facts
about plain symbols that SymPy never states, and stores them on the
symbols.  Every later query anywhere in the process, contextual or not,
then sees `x` as nonzero or finite.  A scan of 19 shapes without a
non-commutative factor (`1/x`, `1/n`, `1/sin(x)`, `1/(x + I)`,
`1/exp(x)`, `1/floor(x)`, `x**2`, ...) found no downward flow; the
non-commutativity is what supplies a structural refutation of `zero`.

## Side findings (not history dependence)

* `ask(Q.positive(Abs(A)), True)` raises `ValueError` in a fresh engine: a
  context-free query with no assumptions.  The `Abs` template asserts
  `nonnegative(Abs(A))` (hence `commutative`) while the structure makes
  `Abs(A)` non-commutative; the root conflict surfaces as
  `InconsistentAssumptions("rule base or cached facts are inconsistent")`.
* Repro A's set `S` is genuinely inconsistent (the `noninteger` conjunct
  forces `w` imaginary, under which the third conjunct's argument is never
  a negative real); the fresh engine's True is the answer that is wrong by
  the engine's own semantics, but the property under test is agreement.

### D. A binding discovery budget truncates a fresh cone; cached facts fill it in a warm engine

Configuration `budget` (`discovery_budget=5`; the default is 400).
`Session._discover` visits at most `discovery_budget` new nodes per query
and drops the rest of the frontier (engine.py 403-413), and `escalate`
has the same bound, so a fresh session for a query over a large cone is
incomplete and answers None.  In a long-lived engine, earlier queries
visited the missing subterms and their level-0 facts are asserted as
units, so the same query is decided.  Repro D (`budget`): after
`ask(Q.lt(1, sqrt(2)) | Q.ne(E, w + (I*w)**(1/3)*Abs(j)**(2/3)), True)`,
`ask(Q.noninteger((I*w)**(1/3)*Abs(j)**(2/3)), True)` is False, None in a
fresh engine; with the default budget both answer False.  The mechanism
applies to the default configuration for cones of more than 400 nodes.

## Second round (profiles and the cache audit)

| repro | prefix | query | engine | fresh | family |
|---|---|---|---|---|---|
| R1 | `ask(Q.real(f(y)), True)`; `register(undef_real)` | `ask(Q.real(f(y)), True)` | None | True | R (cache) |
| R2 | `register(undef_real)`; `ask(Q.real(f(y)), True)`; `unregister(undef_real)` | `ask(Q.real(f(y)), True)` | True | None | R (cache) |
| R3 | `register(undef_real)`; `ask(Q.real(f(y)), Q.positive(y))`; `unregister(undef_real)` | `ask(Q.real(f(y)), Q.positive(y))` | True | None | R (cache and session) |
| R4 | `register(big)`; `ask(hbig(m), True)`; `unregister(big)`; `register(big2)` | `ask(hbig(m), True)` | False | None | R (custom cache) |
| E1 | `ask(Q.lt(oo + x, 0), True)` | `ask(Q.extended_negative(oo + x), True)` | False | None | E |
| E1b | `ask(Q.ne(oo, -1) \| Q.imaginary(oo + nP), True)` | `ask(Q.extended_negative(oo + nP), True)` | False | None | E |
| E1c | `ask(Q.extended_negative(i + oo), S)`; `ask(Q.extended_negative(i + oo), True)` | `ask(Q.extended_negative(i + oo), True)` | False | None | E |
| C6b | `ask(Q.extended_nonnegative(acos(E)), True)` | `ask(Q.zero(E - 1), True)` | False | None | C' |
| L1 | `ask(Q.imaginary(...) \| ~Q.nonzero(inf + acos(-1/he)), Q.gt(-1/3, 1/(2*al)) & Q.infinite(acos(-1/he)))` | `ask(Q.nonzero(inf + acos(-1/he)), True)` | False | None | L |

with `y` real, `m` negative, `x` plain, `nP` declared `positive=False`,
`inf` declared infinite, `he` hermitian, `al` algebraic, `i` imaginary,
`S = (Q.extended_real(0) | Q.ge(pi, n)) & Q.infinite(-pi*(-k)**j) & Q.prime(-k**2*(-k)**j)`
(`n` integer, `k` positive integer, `j` even integer),
`E = -j**2*w - sqrt(2)*j - w*(1 + I)` (`j` even integer, `w` nonzero,
hence real), and the registrations of `harness/registry.py`
(`undef_real`: `real(f(e)) <- real(e)`; `big`: `hbig(s) -> positive(s) &
~integer(s)`; `big2`: `hbig(s) -> negative(s)`).

### R. Registration changes do not invalidate the fact caches or the sessions

Fixed by #63 (R1-R4 are in `fixed/` as regression tests): every engine
cache and session records the registry epoch it was filled under, which
every registration and unregistration bumps, and is dropped at the next
query.  The mechanism as found:

`sympy_api.ask` keys its answer memo by the registry version
(`_registry_state`) and clears it on any change, and `_FORMULAS` and the
splits memo follow.  Nothing does the same for `Engine.cache`,
`Engine.custom_cache` or `Engine._context_sessions`.  `Engine.is_`
returns whatever the cache holds for `(node, pred)`, `None` included (it
stores the None it computed), so a context-free query asked before a
registration keeps answering None after it (R1); a fact a registered
function derived (`real(f(y))` from `real(y) -> real(f(y))`) is written
back at level 0 and served after the function is unregistered (R2), and
asserted as a unit in every later session that visits the node; a
contextual session built while the function was registered keeps the
clauses it emitted (R3); a custom fact cached under one clause-generating
function is asserted under another function for the same predicate name
(R4: `~hbig(m)` from `hbig -> positive` against `m` negative, served when
`hbig -> negative` is the registered meaning).  The base stream with
`--custom` also finds the session variant: a vocabulary registration turns
the relevance split off, so a set that was answered under a part before
the registration is answered under the whole set (and raises) after it,
or the other way round (round-2 `fuzz --custom`, seed 2).

Answers of this family are wrong with respect to the registrations in
force: R1 loses a fact the current registration gives, R2-R4 keep facts
the current registrations do not give.

### E. The relation layer's root facts are written back

`Relations._link(e)` adds `extended_negative(e) <-> lt(e, 0)` (and the
positive and zero links) for every vocabulary-atom argument of a query or
assumption once the session has a relation atom, and `_order_infinite`
decides `lt(e, 0)` at the root when `e` has an `oo` summand (a side that
is `+oo` or undefined is never below anything).  The linked unary fact is
a root literal and `Session.writeback` caches it on `e`; the unary
templates alone do not derive it (`Add` with an `oo` term and an unknown
term), so a fresh engine answers None.  Sound, more definite.

In E1c (nightly `audit`, profile `base`, seed 103) the relation is inside
the prefix's assumption set (`Q.ge(pi, n)` in a disjunct), and the prefix
also asks the query context-free, so the answer memo holds a copy of the
written-back False: clearing the fact cache alone or the memo alone keeps
False, clearing both gives the fresh None (carrier `cache+answers`).
`family_of` drops the memo from a pair carrier `X+answers` when the prefix
asks the query itself, and tags by `X`.  Sound: `i + oo` is not an
extended real, so not extended negative.
Since #73 E1c no longer differs (it is in `fixed/`): `S` is inconsistent,
and its complete check (`Engine._complete_check`, in a session of its own
that writes nothing back) now raises before a session for the prefix query
is built, so nothing reaches the fact cache.  Mechanism E itself remains,
pinned by E1 and E1b.

### L. Learnt units are written back

`Solver.entails` learns clauses; a learnt clause of length one is a root
fact and is a consequence of the whole clause set of the session (the
guarded assumption clauses are satisfiable with the selector false, so
the consequence is context-free).  `writeback` caches it.  In L1 the
search under `infinite(acos(-1/he))` settles the case split on the
finiteness of `acos(-1/he)` and learns `~nonzero(inf + acos(-1/he))`
(`inf` infinite: the sum is infinite or `nan`, never a nonzero real),
which a fresh context-free cone cannot derive by propagation.  Sound.

### C'. Family C without a non-commutative symbol

The `acos` template links `zero(acos(x))` to the derived node `x - 1`.
With `x = E` not real (its imaginary part is `-w`, nonzero), `acos(E)` is
not real, so not extended nonnegative, so not zero, so `E - 1` is not
zero: cached on `E - 1`.  A fresh cone of `E - 1` alone (an `Add`) does
not derive it.  Sound; the same downward route as C, without the
non-commutativity that made C4 wrong.

## Third round (lazily switched-on capabilities, `harness/lazy.py`)

| repro | prefix (under the same set) | query | engine | fresh | family |
|---|---|---|---|---|---|
| G1 | `ask(Q.lt(x, 5), S)`, `S = Q.positive(x + y - 1)` | `ask(Q.positive(x + y), S)` | True | None | G |
| G2 | `ask(Q.lt(u, v), S)`, `S = Q.positive(x + y - 1) & Q.negative(x + y)` | `ask(Q.real(x), S)` | ValueError | True | G |
| G3 | `ask(Q.lt(x, 5), S)`, `S = Q.positive(x - pi)` | `ask(Q.positive(x - 3), S)` | True | None | G |
| G4 | `ask(Q.lt(n, 5), S)`, `S = Q.positive(n - 3)` | `ask(Q.positive(n - 2), S)` | True | None | G |
| G5 | `ask(~Q.eq(u, v), S)`, `S = Q.positive(2*x - 1)` | `ask(Q.positive(x - 1/2), S)` | True | None | G |
| G6 | `ask(x < y, S)`, `S = Q.positive(x + y - 1)` | `ask(Q.zero(u) \| Q.positive(x + y), S)` | True | None | G |
| G7 | `ask(Implies(Q.lt(q/2 + 1, 7), Q.nonpositive(3*q)), S)`, `S = Q.nonnegative(3*q) & Q.zero(3*q)` | `ask(Q.positive(sqrt(2) - 2 - q), S)` | False | None | G |
| Gp1 | `ask(Q.positive(w), S)`, `S = Q.eq(c, 1)` | `ask(Implies(Q.eq(w + 1, 1), Q.prime(f(z))), S)` | True | None | G' |
| Gp2 | `ask(Q.gt(3*q + 21, 7), S)`; `ask(Q.commutative(q), S)`, `S = ~Q.extended_nonpositive(q + 7)` | `ask(~Q.ne(q + 7, 2), S)` | False | None | G' |
| T1 | `ask(Q.eq(u, y), S)`, `S = Q.zero(u) & Q.positive(f(0))` | `ask(Q.positive(f(u)), S)` | True | None | T |
| T2 | `ask(Q.eq(u, v), S)`, `S = Q.zero(u) & Q.positive(f(0)) & Q.negative(f(u))` | `ask(Q.real(v), S)` | ValueError | None | T |
| T3 | `ask(Q.eq(u, oo), S)`, `S = Q.positive_infinite(u) & Q.positive(f(oo))` | `ask(Q.positive(f(u)), S)` | True | None | T |
| T4 | `ask(Q.eq(u, y), S)`, `S = Q.zero(u) & Q.zero(v) & Q.positive(f(v))` | `ask(Q.positive(f(u)), S)` | True | None | T |
| T5 | `ask(Q.is_true(Eq(u, y)), S)`, `S = Q.zero(u) & Q.positive(f(0) + 1)` | `ask(Q.positive(f(u) + 1), S)` | True | None | T |
| S1 | `ask(Q.real(w), S)`, `S = Q.eq(y, q) & Q.irrational(-1/(m*w*y))` | `ask(Q.eq(q, w), S)` | None | False | S |

S1 (reused-session glue, stage 5 of #53) uses `y` real, `q` rational, `m` nonnegative integer, `w` nonzero, and the harness default configuration with only `transfer=False` (it reproduces with the default settings except transfer=False; it was first found at seed 41 with small budgets, one kept session and relevance and cone search off); the fresh False is correct (`w` must be irrational).  It was found by the stage-3 review; no budget truncation is involved; stage 5 (selectors) is expected to fix it.

G1-G6 were fixed on `main` by #51 (the sign facts of two sums now reach
LRA in a fresh session, so a fresh engine answers them too): they moved to
`fixed/`, where `tests/test_history.py` checks that they keep agreeing.
The mechanism is not gone: G7 was found on `main` after #51 (`links`
profile, seed 13), and the `links` and `transfer` profiles still find G in
a few seeds out of twenty.

with `x`, `y` real, `n` integer, `q` nonnegative, `u`, `v`, `z` plain, `w`
nonzero, `c` complex, `f` an undefined function.  All confirmed in fresh interpreters
under hash seeds 0, 1, 2; carrier `sessions` in every case (clearing the
contextual sessions before the query restores the fresh answer; the fact
cache, the answer memo, the splits and the failed-set memo do not).

### G. The relation glue is switched on by the first relation atom of a session, and stays on

`Session._custom` (engine.py 342-349) creates the session's `Relations`
object when the first relation atom is *allocated*: by a relation in the
assumptions (then a fresh session has it too) or by a relation in any
query under the set.  From then on every user formula goes through
`Relations.process` (`Session._relations`, called from `assume_formula`,
`literal_of` and `Engine._literal` only while `self.relations is not
None`), which links every argument `e` of a vocabulary atom of the
assumptions and of the query (`note_formula`, `top`, `_link`): `extended_positive(e) <->
lt(0, e)`, `extended_negative(e) <-> lt(e, 0)`, `zero(e) <-> eq(e, 0)`.
The `lt` atoms are interpreted by LRA under the guard `real(u)` for the
opaque terms `u` of their linear forms (relations.py 484-505), so the
set's facts about `x + y - 1` and the query's about `x + y` meet in one
linear theory: `x + y - 1 > 0` gives `x + y > 0`.  Without the glue the
two nodes are unrelated `Add`s; the structural templates do not relate a
sum to its shift, scaling or difference (they do relate `x + 1` to `x`
for a declared sign, which is why the round-2 profile's observers were
answered either way).  Constants in a linear position get their bounds
(`_bound`) when first seen, so `x - pi > 0` gives `x - 3 > 0` (G3).  The
raise direction (G2): `positive(x + y - 1) & negative(x + y)` is
consistent for the templates and inconsistent for LRA, so the set is
accepted until a relation query under it brings the glue.

The capability is per session: a cone search or `session_limit` replaces
the session, and the new one has no glue unless the assumptions have a
relation (checked: after enough pollution the observer answers None again,
as a fresh engine does).  The answer memo (`Engine.answers`) hides a
repeat of the *same* observer but not its negation or a compound with it.
The relevance layer answers a relation query under the whole set and a
unary one under its connected part: the dependence shows only when the
observer's part is the whole set (or with `relevance=False`).

### G'. The linked terms accumulate per query

With the glue on from the start (the set has a relation), which terms are
linked still depends on history: `_link_later` is called for every side
and vocabulary argument of every formula processed, and a linked term
stays linked.  In Gp1, `ask(Q.positive(w), Q.eq(c, 1))` links `w`
(`zero(w) <-> eq(w, 0)`); the later `Implies(Q.eq(w + 1, 1), Q.prime(f(z)))`
has LRA derive `w = 0` from `w + 1 = 1`, decide the linked `eq(w, 0)`,
hence `zero(w)`, against `w` declared nonzero: the antecedent is false and
the implication True.  A fresh session links `w + 1` (a side) but not
`w`, and LRA's `w = 0` reaches no unary atom.  Gp1 no longer differs
since R2 (component-scoped answering, #53; in `fixed/`): `Q.positive(w)`
is answered under its own part (`w` is not connected to `c`), so the
observer's session never linked `w`.  Gp2 is the same with the trigger in the prefix: a relation query
switches the glue on, `Q.commutative(q)` links `q` (whose declared
`nonnegative` then reaches LRA as `~lt(q, 0)`), and the later relation
`q + 7 = 2` is refuted; a fresh session links `q + 7` but not `q`.  The
campaign's `lazy` and `links` streams produced this shape ten times.  The `mention_only` probe
of `checker.attribute` (each prefix query replaced by `Q.commutative` of
the terms it mentions) reproduces the discrepancy, which is what the tag
`G'` records.

### T. Predicate transfer is engaged by the first equality atom of a session, and stays on

T2 no longer differs since #63 (it is in `fixed/`): its prefix query
raises in both engines (the set is inconsistent once transfer is
engaged), and #63 drops a session with the raise, so the final query runs
in a fresh session.  T1, T3, T4 and T5 no longer differ since R2
(component-scoped answering, #53; they are in `fixed/`): the prefix
equality's part does not hold the observer's application (`Q.eq(u, y)` is
answered under `Q.zero(u)` alone), so its session, not the observer's,
engages transfer.  The mechanism is unchanged within one component.

`Relations.process` (relations.py 409-411) sets `_want_transfer` for a
user `eq` atom (also `ne`: it is `Not(eq)`), and `_engage_transfer`
(723-743) attaches the EUF theory and a `TransferTheory` to the session's
solver, once.  From then on `sync_transfer` registers every node block
whose expression can join an EUF class (a side of a user equality, a
number, or an application congruent to another known application whose
arguments are sides or candidates) with the transfer theory, which
enforces `eq(a, b) -> (P(a) <-> P(b))` for every predicate.  The links
alone never engage it (`_aux_eq`, `_link_eq`), so a fresh session for
`Q.zero(u) & Q.positive(f(0))` has EUF classes `u ~ 0` (through the link
`zero(u) <-> eq(u, 0)`, once a relation atom exists at all) but no
transfer, and `Q.positive(f(u))` is None; after any equality query under
the set, `u` and `0` are sides at level 2, `f(u)` and `f(0)` are congruent
candidates, and `positive` is copied from `f(0)` to `f(u)`.  The class can
also come from `eq(u, oo) <-> positive_infinite(u)` (`_eq_infinity`, T3),
from two zero terms (T4), and congruence goes through `Add`/`Mul`/`Pow`
and every `Application` (T5).  The raise direction (T2): `negative(f(u))`
against `positive(f(0))` conflicts only once transfer is on.  Switching
the engine's `transfer` off makes the discrepancy vanish, which is what
the `without_transfer` probe of `checker.attribute` records.
