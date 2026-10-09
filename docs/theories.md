# Relations and theory solvers

Relations (`Q.eq/ne/lt/le/gt/ge`, `Eq`, `x < 0`, `Q.is_true(x < 0)`) are
answered by theory solvers on the CDCL solver (DPLL(T)): linear real
arithmetic (LRA), equality with uninterpreted functions (EUF), and a
transfer theory that shares unary facts between equal terms. Sessions,
caches, relevance and the rule block are in [design.md](design.md),
timings in [performance.md](performance.md).

| Path | What |
|---|---|
| `satassume/sat/theory.py` | the theory contract (`TheorySolver`, `PropagatingTheory`), `EqualitySharing` |
| `satassume/sat/solver.py` | the hooks: `attach_theory`, `register_atom`, `_tpropagate`, `_theory_sync`, `_theory_decide`, `_theory_check`, `theory_models` |
| `satassume/relations.py` | normalisation (`relation_atom`), the per-session glue `Relations`, `AdapterSpec`, `default_specs`, `Uninterpreted` |
| `satassume/theories/lra/lra.py`, `lra_adapter.py` | simplex LRA with integrality; SymPy atoms to linear forms |
| `satassume/theories/lra/constfield.py` | exact numbers in `Q(pi, E, sqrt(2), ...)` for LRA |
| `satassume/theories/euf/euf.py`, `euf_adapter.py` | congruence closure; SymPy terms to EUF terms |
| `satassume/theories/transfer.py` | `TransferTheory`: unary facts across EUF classes |
| `satassume/engine.py` | `Session._custom`, `_relations`, `link_set`; `Engine(relations=, transfer=, uninterpreted=)` |
| `satassume/scope.py` | `theory_scope`, `affine_pair`, `transfer_wanted`, `extension_atoms`: the theory scope of a query (#97 P3) |
| `tests/theory_harness.py` | testing a theory: `TheoryCase` with `check_solve`/`check_entails`/`check_implied` against independent brute-force checkers (Fourier-Motzkin, naive congruence closure; never the code under test), `Recorder` and `check_protocol` for the protocol, `ForbidTheory` as a 60-line example, `relation_engine` and `dummy_specs` end to end; `tests/real_theory_fuzz.py` fuzzes the solver with the real LRA and EUF |

## The DPLL(T) interface

A theory implements `register_atom(v, payload)`, `assert_lit(lit)`,
`check()`, `push_level()`, `pop_level()`, and optionally `propagate()` and
`decide()`. The full contract is the module docstring of
`satassume/sat/theory.py`; the essentials:

| method | returns | called |
|---|---|---|
| `register_atom(v, payload)` | None | at root, any time, once per `(theory, v)`; the payload is opaque to the solver |
| `assert_lit(lit)` | None or `(False, clause)` | once per assignment of a registered variable while it stands |
| `check()` | None, `(True, model)` or `(False, clause)` | on a total assignment with everything reported, just before SAT |
| `push_level()` / `pop_level()` | None | in step with the solver's decision levels, including empty levels for assumptions already true; level 0 is never pushed or popped |
| `propagate()` | `(lit, reason)` pairs | after all current assignments were reported without conflict |
| `decide()` | a variable or None | when every other variable is assigned, before `check` |

Conflict clauses are theory-valid with every literal false; reason
clauses contain the implied literal and otherwise only false literals (the
solver raises `RuntimeError` otherwise). Conflicts become ordinary learnt
clauses and may be deleted, so a theory must be able to find a conflict
again. The one soundness rule: never a conflict or propagation that a
theory model refutes. Incompleteness is safe, because `Solver.entails`
gives a definite answer only from an unsatisfiable search.

The four-method core is that of SymPy PR 30537, plus `register_atom`
because sessions grow while the solver already has root facts. Reasons are
eager (no `provide_reason` callback as in SymPy PR 30098). Routing by
registration keeps the rule base's variables away from theories; the
no-theory path pays one attribute test per hook. `tests/test_theory_hooks.py`
pins the order of calls: each assignment is reported once per
level-lifetime, in trail order, after unit propagation; nothing is called
after a conflict until a `pop_level`; `implied` and the propagation stage
of `entails` never call `check`. A newly registered atom sets
`_tpending`, so the next sync at root asks the theories about it: an
implication about a fresh atom (a ground LRA atom, an EUF equality whose
sides are already equal) was otherwise delivered under an assumption level
and lost at the next pop.

**Lazy atoms and `decide()`.** `register_atom(..., mention=False)`
registers a rule-block variable without mentioning it: the block writes to
it above root only if something else mentions it, and the search does not
decide it. The theory still hears every value it gets, but `check` may see
it unassigned; `decide()` names an atom the theory needs decided, which the
solver decides in the phase its block implies. Only transfer uses this.

**Giving up.** A theory that meets a question it cannot decide (LRA with a
sign that exact arithmetic cannot settle, or an expression over the
constant field's size budget) must not guess. It sets `gave_up` and from
then on reports no conflict, no propagation and None from `check`. What it
reported earlier stays valid. The engine discards a cached session whose
theory gave up (`Engine._context_session`, `_gave_up`), and `sympy_api`
does not take such a session as evidence of consistency. Aborting the
whole query instead lost answers another theory finds:
under `Q.eq(x, (1 + sqrt(2))**2) & Q.eq(x, 3 + 2*sqrt(2)) &
Q.positive(f(3 + 2*sqrt(2)))`, `Q.positive(f((1 + sqrt(2))**2))` is True
through EUF although LRA cannot tell the two constants apart
(`tests/test_transfer_numbers.py`).

**Held assumption levels with theories.** `Solver._assume` keeps the
levels of a successful propagation under assumptions on the trail
(`_held`), and theories stay pushed at them between public calls. While
`_held` is set the trail is exactly what propagating the held assumptions
from root gives: a clause added meanwhile is propagated at the top held
level through `_tpropagate` (`_attach_held`), so theories hear of its
unit; a root change, a falsified clause, attaching a theory or registering
an atom drops the held levels; a search keeps them only if no learnt
clause was deleted. The fixpoint holds only up to the theories' own
history-dependent incompleteness (LRA's dirty set, EUF's queue), which
costs propagation strength in either direction. A theory whose
`propagate` depends on more than its asserted literals and registered
atoms would break the argument. This decided the design: without held
levels every relation session re-propagated its assumptions on every
query, and allowing them took the cost of an attached no-op theory from
+14.1% to +4.9% of the stream (Pi, e2aa724).

**Witness reuse.** A satisfiable answer may reuse an earlier model with
no theory call. `Solver._ring_hit` does so only under the same theories
and registration count (`_n_registered`: a second theory on a variable
adds a constraint without a new `_tmap` entry); lemmas learnt since are
theory-valid. `Solver._witness` is cleared by `attach_theory`,
`register_atom` and every clause addition. Stored models are Boolean
(`theory_models()` is read only by tests), which keeps integrality safe:
an LRA `check` model need not satisfy the integrality atoms, and a
satisfiable search only ever means None or "consistent".

## What relations mean

`relation_atom` normalises every relation to `eq(a, b)` (sides in
`default_sort_key` order) or `lt(a, b)`, each an ordinary custom variable:
`a > b` is `lt(b, a)`, `a != b` is `~eq(a, b)`, and `a <= b` is
`extended_real(a) & extended_real(b) & ~lt(b, a)` (no conjunct for a
Rational or infinite side; False for a `nan` side).

**Order relations are over the extended reals and assert that their sides
are extended reals** (#26, the owner's rule; examples in the README), so
`~(a < b)` is not `a >= b`, and `x < x + 1` under `Q.extended_real(x)` is
None (SymPy's `lra_satask`, which assumes finite reals, says True).

An `lt` atom `r` for `a < b` gets three groups of clauses
(`Relations._order_sides`, `_order_infinite`, `_interpret`):

1. *Sides*: `r -> extended_real(a)` and `r -> extended_real(b)`; a closed
   side known to be no extended real (`zoo`, `I`, `nan`) makes `r` false.
   This is as sound as the templates' `extended_real` rules, so #26 fixed
   them: a sum of extended reals is one only if no term is `+oo` or none
   is `-oo`, a product only if all factors are finite or all nonzero.
2. *Infinite terms*: `lra_adapter.order_sides` splits each side into
   coefficients times opaque terms plus an optional `oo`/`-oo` summand; a
   term pushes its side up (`positive_infinite` with `c > 0`,
   `negative_infinite` with `c < 0`) or down. A push up on the left or down
   on the right makes `r` false; a push down on the left or up on the
   right, unopposed, with every term extended real and every coefficient
   nonzero, makes `r` true. An undecidable coefficient sign emits nothing.
3. *Finite terms*: a guarded theory (LRA) never sees `r`. It gets a fresh
   variable `t`, and the engine adds `real(u1) & ... & real(uk) -> (r <->
   t)` over the opaque terms `u` of `a - b`, including terms that cancel
   (`x` in `x < x + 1`). An atom with an `oo` summand has no finite case
   and gets no `t`.

The guard makes an adapter that ignores SymPy's assumptions sound: give
every non-real term an arbitrary real value; the `t`s evaluated there are
LRA-consistent, and `t = r` wherever the guard holds.

`eq` is equality of values in any domain and asserts nothing about the
sides (`Eq(I, I)` and `Eq(oo, oo)` are True). It goes unconditionally to
EUF and, under the guard of clause 3, to LRA. More clauses in `Relations`
(#26, #51):

- `_eq_infinity`: `eq(e, oo) <-> positive_infinite(e)`, and for `-oo`;
- `_eq_links`, for user atoms with non-number sides, added the first time
  a query mentions the atom, also when the glue made it before (an
  interface equality, S1 of #53):
  `positive_infinite(a) & positive_infinite(b) -> eq(a, b)` (and
  `-oo`), `zero(a - b) -> eq(a, b)`, `nonzero(a - b) -> ~eq(a, b)`, and
  the same with `b - a`. A zero
  or nonzero difference is finite, so it is 0 exactly when the sides are
  equal and finite; equal infinite sides have a nan difference. Only a
  difference SymPy builds term by term counts (`_termwise`): after
  cancellation (`x - (x + y)` is `-y`) it is not the difference where the
  cancelled part is infinite, so `Q.eq(x, x + y)` under `Q.positive(y)`
  stays None;
- `_trichotomy`, for two atoms `lt(a, b)` and `lt(b, a)`:
  `extended_real(a) & extended_real(b) & ~lt(a, b) & ~lt(b, a) -> eq(a, b)`,
  so `Q.le(x, y) & Q.ge(x, y)` gives what `Q.eq(x, y)` gives (W2B4b), also
  for sides that may be infinite.

All three are switched per query (below, "Switched glue"): they carry the
selector of their atom.

`Eq` is reflexive and congruent even on terms that may evaluate to nan
(`Q.eq(e, e)` is True, as in SymPy's `ask`; documented in
`tests/test_verify_soundness.py`). The strict reading (`Eq(nan, nan)`
False) was built in PR #57 and closed (see the table at the end). Atoms
containing a literal `nan` are refused by EUF and LRA.

## The glue: `Relations`

Each `Session` has its own adapters and theories, held by a
`relations.Relations` object (`Session.relations`). It is created at
construction, from the query's theory scope (`scope.theory_scope`, #97 P3),
when:

- the assumptions or the query hold a relation atom (one in an extension
  fact of a custom atom counts, `scope.extension_atoms`; one in a node fact
  of a vocabulary predicate registered for a class does not: `Session._custom`
  then creates the glue at the atom and counts it, `stats["scope_misses"]`).
  The unary atoms of the assumptions become link candidates after the set's
  complete check (`Session.link_set`), so the check sees only the set's own
  glue;
- or two sign atoms (`positive`, `nonzero`, `extended_negative`, ...;
  `scope.SIGN_PREDS`) of the assumptions or the query are on different sums
  sharing a symbol (`scope.affine_pair`), as in `Q.negative(1 - x)` under
  `Q.positive(x - 1)`: only the glue links a sign fact to its linear form,
  so without it LRA never compares the two sums. Once the
  glue exists it links every unary atom's argument, not only those sums,
  which lets facts cross the components of the relevance split (#15; see
  [design.md](design.md), "Relevance").

Until then the unary path pays one `is not None` test (the first wiring,
with glue in every session, cost up to 10% on the unary microbenchmarks).
`Relations.process`, at the end of `literal_of`, `assume_formula` and
`Session.prepare_query`, interprets queued atoms with every adapter that accepts
them, adds links, shares equalities and engages transfer until nothing
changes; a user relation no theory interprets stays a free Boolean (the
default `uninterpreted="free"`), or raises `Uninterpreted` with
`Engine(uninterpreted="none")`.

**Links to the unary vocabulary** (`Relations._link`), for every argument
`e` of a user relation and, once the session has relations, every argument
of a vocabulary atom of the user's formulas (numbers excluded):

| clause | why it holds |
|---|---|
| `extended_positive(e) <-> lt(0, e)` | `0 < e` in the extended reals |
| `extended_negative(e) <-> lt(e, 0)` | same |
| `zero(e) <-> eq(e, 0)` | `Eq(e, 0)` holds iff `e` is zero, in any domain |

The rule base derives the rest. Link atoms get no clause 1 (implied), and
no clauses 2 when `e` is its own opaque term (#45).

**Switched glue** (#53 stage 5, when a session answered many queries).
Glue made for one query must not act in another; since #97 a session
serves its set's check and then one query, and the switching keeps the
check to the set's own glue: every clause that ties a
relation to unary atoms carries a selector, and each query assumes the
selectors of its own glue only (`Session.assumption_lits`):

- the links of a term carry the term's selector (`Relations.link_sel`,
  also on its integrality clauses); a query assumes those of the
  vocabulary-atom arguments and the sides of the interpreted relations of
  its proposition `p` and its assumptions `a` (`selectors_of`), and only
  if `p` or `a` holds a relation atom or an affine pair
  (`scope.affine_pair`): a unary query
  under a unary set gets no links however many relation queries the
  session answered before;
- the clauses of `_eq_infinity`, `_eq_links` and `_trichotomy` carry their
  atoms' selectors (`Relations.atom_sel`), assumed when the atom occurs in
  `p` or `a`;
- an equality's twins in the guarded theories (LRA's `a - b = 0`) carry
  the guard of a role of the atom (`Relations._add_role`): a user
  equality its atom selector, a link's `eq(e, 0)` the link's selector,
  `_trichotomy`'s equality both order atoms' selectors, an interface
  equality the share variables of its terms (below). EUF reads the atom's
  own variable, so an unswitched twin is a bridge: an equality LRA derives
  from the current query's bounds on the sides of an equality an earlier
  query made reaches EUF and transfer (`Q.prime(a)` under `Q.gt(a, 1) &
  Q.lt(a, 3) & Q.integer(a)` was True after `Q.eq(a, 2)` was asked, None
  fresh);
- predicate transfer carries one selector (`Relations.xfer_sel`, below),
  assumed iff `p` or `a` holds a relation atom, and each candidate term
  carries enable variables (`TransferTheory.switch`, below).

The selectors of `a` come first, after the set's own selector, and the
solver keeps their levels between queries (`Solver.implied(...,
hold=k)`); those of `p` follow. The other clauses of an atom
(`_order_sides`, `_order_infinite`, an order atom's LRA twin, which LRA
alone reads) constrain the atom given its sides and never a side given
the atom, so another query's relation atom is a free variable and they
stay unswitched; with its twins off, an equality is a variable EUF alone
reads, free too. A learnt clause that used a switched clause keeps its
negated selector, so it is inert where that selector is not assumed.

**Integrality** (#38): each linked `e` whose linear form LRA reads
(`lra_adapter.integer_form`) gets an integrality atom `i` with
`real(u1) & ... & real(uk) -> (integer(e) <-> i)` (under `e`'s link
selector); SymPy's `integer` implies finite, so the guard is exact. Also
when `e` is its own term: registering `integer(e)` itself as the atom
would let LRA round the bounds of every later query's linear forms on `e`
(`ask(Q.lt(2*n, 2), Q.lt(0, 2*n))` for an integer `n` was False after
`Q.zero(n)` was asked under the set, None fresh). `relations.INTEGERS =
False` turns it off.

**Equality sharing.** Theories are kept apart by atom kind and meet on
shared terms (`shared_terms()` of two adapters): `Relations._share`
creates `eq(a, b)` for each pair (`theory.EqualitySharing`), delayed theory
combination, complete because LRA and EUF are stably infinite, convex and
share no symbols. An interface equality is switched like the rest: its
twin holds under `IL(u) & IE(u)` for both terms `u`, variables that the
selectors of the links reading `u` (in LRA, in EUF) imply. A fresh
session's shared terms are exactly those of its links (a user relation's
sides are linked, and their link atoms read every term the relation's own
atoms read), so the interface equalities a query has are those a fresh
session for it creates. With real `x`, `y`, `ask(Q.eq(f(x), f(y)), (x <= y) &
(y <= x))` is True through LRA and sharing (for plain symbols the guard
leaves `x <= y` without order meaning in LRA, and `_trichotomy` gives the
equality instead). The
interface atoms are quadratic in the shared terms; Nelson-Oppen equality
propagation would pay only beyond a few dozen shared terms per session,
which no recorded query reaches. A pair with a non-rational constant term
gets no interface atom (a relaxation): `Q.eq(f(x), f(pi))` under
`Q.eq(2*x, 2*pi)` is None; on the refine stream these atoms decided no
query and cost about 10% of the decisions under assumption sets with
`pi`.

## LRA

`LRATheory` (`satassume/theories/lra/lra.py`) is the general simplex of Dutertre and de
Moura (CAV 2006): Bland's rule, exact arithmetic, delta-rationals for
strict bounds, one slack per linear form normalised to leading coefficient
1, a tableau kept across levels (backtracking restores bounds only), the
simplex run eagerly in `assert_lit`, disequalities decided in `check`.
`propagate` reports bound implications only for variables whose bounds
changed since its last call, and `pop_level` does not restore that dirty
set, so some implications are not repeated after a backtrack (propagation
strength only; `check` is complete).

`lra_adapter._lin` linearises `a - b` structurally (no `expand`): sums
are split, a numeric factor scales, and every other subexpression with
free symbols (`x*y`, `sin(x)`, `f(x)`) is an opaque term, an independent
real variable (a sound relaxation). An atom is not read if an argument is
not a scalar `Expr`; if it contains `nan`, `zoo`, or `oo` anywhere except
as a summand of an order side (`order_sides` reads that case); if a
coefficient is not a number of the field (`I*x`, `0.5*x`) or its sign is
undecidable; or if it contains a Float in a closed subexpression.

**Integrality and branch and bound** (#38). `Integral(terms, offset)` is
stored as `m*v + k` in Z on the variable of its form (not a bound) and
checked cheapest first: in `assert_lit` and `propagate`, the bounds of
`v` rounded with a delta-rational floor and ceiling (`v < 1` gives `v <=
0`), a conflict when the range holds no integer, or when a negated atom's
`v` is pinned to an integral value; in `check`, branch and bound after the
simplex (Dutertre and de Moura, SRI-CSL-06-01, ch. 4), each branch a
`push_level` with a literal-free bound, the conflict of two failed
branches being the union of their explanations plus the integrality
literal. At most `BRANCH_BUDGET = 16` branchings per `check`, then no
conflict; no cuts or GCD test (`x in Z & x + 1/2 in Z` without bounds
stays undecided). `Q.ge(k, 1)` for an integer `k > 0` is True.

**Constants.** `pi`, `E`, `exp(n)`, rational powers of rationals
(`sqrt(2)`) with `+ - * /` and integer powers, and every other closed real
constant with rigorous bounds (`log(2)`, `sin(1)`, `2**pi`;
`lra_adapter.GENERIC_CONSTANTS = True`) are exact numbers of
`satassume/theories/lra/constfield.py`, in constants and coefficients alike: `x <=
3*pi/2`, `x/pi`, `pi*x`, `log(2)*x`. So refine's `Q.integer(x/pi + 1/2)`
under `-pi/2 < x < pi/2` is False, with the endpoint tie decided exactly.

History: #14 (item 2) first made a closed constant an LRA *term* with
rational bounds `lo < c < hi` asserted once per session
(`Relations._bound`, `LRAAdapter.register_bounds`), from interval
arithmetic (`lra_adapter._interval`: mpmath's interval context at 128
bits, outward rounded, each transcendental step widened by `2**-120`
relative); `pi*x` stayed unread. #37 and #48 replaced that with the exact
field. The bounded-term path remains for a constant the field does not
read (over its size budget, or `GENERIC_CONSTANTS = False`), and
`_interval` now supplies the field's enclosures of generic constants
(`constant_enclosure`). A constant known real context-free still gets no
guard literal (hence no node) and no interface equality.

**The field** (#37, after de Moura and Passmore, CADE 2013, z3's `rcf`).
A constant is an indeterminate with a procedure that encloses its value
in rational intervals of any width (`pi` by Machin's formula and `E` by
its series in integer arithmetic, with explicit error bounds; `r**(1/b)`
by integer roots; generic constants by `constant_enclosure`). A number is
a rational function `n/d` in a normal form (lowest terms by an exact gcd,
monic denominator), so `pi/pi` is `Fraction(1)` and `hash` is structural;
a constant-free result is always a plain `Fraction`, so rational
workloads run the old code paths. Every question about values is answered
semantically: `sign` refines outward-rounded interval evaluations (64,
128, ... bits) until 0 is excluded and raises `Undecided` at `PREC_CAP =
4096`; `==` is True only for formally equal numbers, False for a proven
nonzero difference (formally for one transcendental constant: Lindemann,
Hermite), else `Undecided`; division checks its divisor. Nothing is
assumed about `pi` and `E` together, and algebraic constants are plain
indeterminates, so `Q.lt(sqrt(2)*x, 2)` under `x < sqrt(2)` is None (the
theory gives up). A size budget raises `TooLarge` (an `Undecided`), so a
pivot that blows up makes a query undecided instead of slow. `lra.py`
drops a coefficient only when it is `formally_zero`, computes every pivot
value before writing any, and never calls an `Element` integral by
default. Limits: two spellings of one value (`log(8)`, `3*log(2)`) are
unrelated indeterminates; values closer to 0 than about `2**-4096` are
undecided; generic-constant enclosures trust mpmath's interval functions
to within `2**-120` relative.

## EUF and predicate transfer

`EUFTheory` (`satassume/theories/euf/euf.py`) is incremental congruence closure after
Nieuwenhuis and Oliveras (2007): curried applications, union by size,
explanations from a proof forest, undo by trail. Disequalities and
distinct values are checked eagerly in `assert_lit`; `propagate` reports
equalities only. `EUFAdapter.term` interns Rationals as pairwise-distinct
values; `Add`, `Mul`, `Pow` and every `Application` as function heads
(no AC: `x*(y + 1)` and `x*y + x` are unrelated); everything else as an
opaque constant, in particular binders (`Sum`, `Integral`, `Lambda`, and
any class that overrides `free_symbols` or `bound_symbols`), since
congruence under a binder is unsound. Floats, `pi` and `oo` are opaque:
`Eq(0.1, 1/10)` is True in SymPy, so a Float as a distinct value could
refute a satisfiable assignment.

Other theories read EUF's classes directly, through two public read-only
attributes: `rep` (term to its class representative) and `members`
(representative to the terms of its class), plus the `on_merge` listener
called on every union. They are attributes rather than methods because
transfer reads them per literal. `members[r]` is only meaningful when `r`
is a representative: a union leaves the absorbed representative's list
unchanged (undo reads it back), so it goes stale, and clients read
`members[rep[t]]` (transfer does, or keeps representatives it got from
`on_merge` and re-checks them through `rep`).

`TransferTheory` (`satassume/theories/transfer.py`) closes the gap EUF leaves:
whenever EUF puts two terms in one class, every one of the 33 unary
predicates holds for one iff it holds for the other (enforced on the 14
basis variables of the node blocks; the 19 definitions follow from them), which is sound
because every predicate is a property of a value. It enforces
`eq(a, b) -> (P(a) <-> P(b))` without materialising it: its atoms are
node-block predicate variables with payload `(EUF term, predicate)`,
`propagate` copies the first assigned value in a class to the others with
reason `[P(b), ~P(a)] + ~explain(a, b)`, and `check` rescans as a
backstop. It keeps no derived state, so EUF's undo needs no hook (EUF
calls `on_merge` on every union). Examples: `Q.prime(x)` under `Q.eq(x,
2)`, `Q.positive(f(y))` under `Q.eq(x, y) & Q.positive(f(x))`, and
`Q.eq(x, y)` False under `Q.prime(x) & ~Q.integer(y)`.

`Relations._engage_transfer` attaches it once per session, at the first
relation atom of a user formula (an equality, or inequalities that may
give one: `Q.le(x, y) & Q.ge(x, y)`), unless `Engine(transfer=False)`.
Its lemmas carry the selector `Relations.xfer_sel`
(`TransferTheory.guard`, registered as an atom of the theory): while the
selector is not true the theory propagates, checks and decides nothing,
and it rescans every class with two or more members when the selector
turns true. A query assumes
it iff its proposition or its assumptions hold a relation atom, the
condition on which a fresh session engages transfer, so an earlier
equality query no longer lends transfer to a later unary one (family T
of #53). `Relations.sync_transfer` then registers only
*candidate* nodes, those EUF could ever merge: atom sides and terms EUF
reads with a same-head partner (another term EUF reads, or a structural
number argument of a vocabulary atom such as `sin(2)`) whose arguments
may merge. A side only of a link `eq(e, 0)` registers `polar` alone
(`zero(e)` decides the rest); a side only of interface equalities
registers nothing, so equalities LRA derives are not transferred (the
owner's choice). Candidacy grows with the session, so each candidate but
a rational number takes part in a query only as its enable variables say
(`TransferTheory.switch`): all predicates while it is a side of a user or
`_trichotomy` equality the query activates, or a congruent application
of terms the query activates (`Relations._congruence_pairs`), `polar`
alone while it is a link-only side. Otherwise a term that an earlier
equality made a side, or that an earlier node gave a congruent partner,
took every fact of its class (`Q.prime(f(a))` under `Q.eq(f(a) - b, 0) &
Q.eq(b, 2) & Q.eq(a, u)` was True after `Q.positive(f(u))` was asked,
None fresh). A Rational side is no node: its
fact basis is held as fixed facts of its term (`_number_basis`,
`TransferTheory.set_fixed`). Atoms are lazy (`mention=False`): every
literal a block did not imply itself is on the trail and reaches its
class, and each equal term's block implies the same closure, so nothing
is lost; `decide()` settles atoms of partial nodes (only some variables
registered), whose models could otherwise differ
(`test_models_respect_transfer`). Not covered: substitution into
structural templates (`Q.rational(x**y)` under `Q.eq(x, 1) &
Q.rational(y)` is None).

## Uninterpreted relations

A relation no theory reads (a Float, `AccumBounds(0, 1) < x`, `oo*x <
1`; `x < I` and `x < zoo` are read, as False) is kept a free Boolean
with its clause 1 by default (`Engine(uninterpreted="free")`), so the rest
of the assumptions answers and an inconsistent rest raises; this only
drops what the relation says, which is sound. `Engine(uninterpreted="none")`
is the old behaviour, opt-in: `ask` returns None
(`relations.Uninterpreted`). Measured at c8361d7, free changed
3 stream answers (None to False, correct), nothing on gate2 or the refine
scoreboard, for +3.2% on the Pi, and lost one combined-backend answer
(`Q.eq(nan, 1)`: the router no longer sees the unread relation, a signal
to keep before switching; on SymPy 1.14.0 that query raises `TypeError`
instead, #65). Before constants were read it was worth 498
stream answers and 6 scoreboard tests. Free is the default since #64.
Such a relation links nothing (`Relations.process` links the sides of a
user relation only once a theory interprets it); with the default
`sympy_api.RELATIONAL == "components"` it keys its sides like any relation,
so it joins the component of its terms (a Float side is a key) and an
unrelated query is answered without it. Out-of-scope applied predicates of the assumptions (matrix,
unregistered custom) are likewise opaque free atoms (`sympy_api.to_formula`
with `opaque`).

**Floats are deliberately not read** ([README, Known
gaps](../README.md#known-gaps)): SymPy compares `Float > Rational` exactly
but decides `Eq` at the Float's precision, so any fixed reading
contradicts it somewhere. A Float as a bounded unknown within its own
precision would be sound under both readings; it was not built.

## Open questions and known gaps

- #42, item 3 (answers depending on earlier queries through the lazily
  created glue: `Q.zero(k + x - 1)` under `Q.integer(k) & Q.integer(x) &
  Q.positive(k) & Q.positive(x)` was False after `Q.lt(k, 3)` and None
  fresh) is fixed by the switched glue (#53 stage 5): None either way.
  Linking every term in every session (fixing gap 1 below for real sides)
  would be a capability change, measured at +70% CPU in the #53 design
  prototype.
- #42, gaps 1 and 2: unless the sides are known real, `Q.positive(b - a)`
  does not prove `Q.negative(a - b)`, nor `Q.zero(a - b)` `Q.zero(b - a)`,
  nor `Q.eq(a, b)` with finite sides `Q.zero(a - b)`.

## Tried and dropped

| Idea | Measured | Why dropped |
|---|---|---|
| FactTheory: unary facts as a lattice-valued DPLL(T) theory replacing the rule block, exact closure per term | +56% on the Pi stream against 6b935d7, answers identical | every predicate literal crosses the Python theory interface (about 660,000 events per pass against the rule block's in-loop writes); held levels with theories, `_tpending` and the lazy rule-block writes came out of it |
| Engage EUF only on a user equality, defer the zero links (archived as tag `archive/relation-speed`) | -2.2% on the Pi against 66871eb after porting | under the 3% line; the first version lost congruence answers through the zero links (`ask(Q.zero(f(x)), Q.zero(x) & Q.zero(f(0)) & Q.lt(x, 1))`), and staying exact needed a subtle engagement argument |
| Wider sign-on-sum trigger (`scope.affine_pair`; `_affine_links` then): a sum and any term sharing a symbol | 14 more-definite stream answers instead of 4, +65% (#51, against a861432) | cost |
| Integrality link only in sessions mentioning an integer-family predicate | +2.4% instead of +3.75% (#38) | loses answers about declared-integer symbols (`Q.ge(k, 1)` under `Q.gt(k, 0)`) |
| Integrality atoms for opaque terms; nudging off an integer before branching; skipping clause 2 for terms real at the root; deduplicating clauses | no extra answer, or no measurable gain (#38, #45) | nothing to gain |
| Interface equalities and guard nodes for known-real constants | no stream answer; about 10% of decisions under `pi` sets | relaxation kept |
| Constant bounds from strict `evalf` | wrong answers in review (loose error for `sign`, `tan` near a pole, `log` near 1; OOM on `exp(exp(exp(5)))`) | interval arithmetic, then the exact field |
| Floats as their exact binary value | `ask(Q.eq(0.1, 1/10))` False, SymPy True | contradicts SymPy's `Eq` |
| Strict `Eq(nan, nan)` with nan-aware congruence (#57, branch `eq-nan`) | 0 answers on gate2 and the stream, +3% | contradicts SymPy on compound self-equalities; kept as a design |
| Transfer `decide()` on every unassigned atom, full nodes too | 2,372 extra decisions per pass | full nodes of one class complete alike; only partial nodes need it |
