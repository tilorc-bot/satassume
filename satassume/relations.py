"""Relation atoms (``Q.eq``, ``Q.lt``, ``x < y``, ...) and theory solvers.

A relation reaches the engine as one of two atom kinds, after
normalisation by :func:`relation_atom`:

* ``P('eq', Args((a, b)))`` for ``a == b`` (arguments in ``default_sort_key``
  order, so ``Eq(a, b)`` and ``Eq(b, a)`` share a variable);
* ``P('lt', Args((a, b)))`` for ``a < b``;

and ``a > b`` is ``lt(b, a)``, ``a != b`` is ``Not(eq(a, b))``,

    a <= b   is   extended_real(a) & extended_real(b) & ~lt(b, a),
    a >= b   is   extended_real(a) & extended_real(b) & ~lt(a, b)

(an ``extended_real`` conjunct is left out for a Rational, ``oo`` or
``-oo`` side, and the formula is False for a ``nan`` side, which is no
extended real although the rule base cannot say so).  Each atom gets one
solver variable like any non-vocabulary atom (``VarTable.custom``).

Meaning
-------
Order relations are over the extended reals and assert that their sides
are extended reals: ``a < b`` holds iff ``a`` and ``b`` are extended reals
and ``a < b`` there (``-oo`` < every finite real < ``oo``).  So
``Q.lt(x, 1)`` implies ``extended_real(x)``, ``x < oo`` is
``extended_real(x) & ~positive_infinite(x)``, ``x < zoo`` and ``I < 1``
are false, and ``~(a < b)`` is *not* ``a >= b``: it also holds when a side
is not an extended real (hence the ``extended_real`` conjuncts of ``<=``).
``Q.gt(x, 0)`` gives ``extended_positive(x)`` but not ``positive(x)``
(``x = oo``).

``eq`` is equality of values; it holds or fails in every domain (complex,
extended reals: ``Eq(I, I)`` is True, ``Eq(oo, oo)`` is True) and asserts
nothing about the sides; ``ne`` is its negation.  An equality with ``oo``
or ``-oo`` is linked to the unary vocabulary: ``eq(e, oo) <->
positive_infinite(e)``, ``eq(e, -oo) <-> negative_infinite(e)``
(:meth:`Relations._eq_infinity`); two sides at the same infinity, or with
a zero difference, are equal, and sides with a nonzero difference are not,
for a difference SymPy builds without cancelling terms
(:meth:`Relations._eq_links`).  It is given to theories
that interpret it unconditionally (EUF) and, for finite real terms, to
LRA (below).

An ``lt`` atom ``r`` for ``a < b`` gets these clauses
(:meth:`Relations._order_sides`, :meth:`Relations._order_infinite`):

1. *sides*: ``r -> extended_real(a)`` and ``r -> extended_real(b)``; a
   closed side the engine knows is no extended real (``zoo``, ``I``,
   ``1 + I``, ``nan``) makes ``r`` false outright.  This reads the node
   facts of the sides, so it is only as sound as the templates'
   ``extended_real`` rules (a sum or product of extended reals need not
   be one: ``oo - oo`` and ``0*oo`` are nan).
2. *infinite terms* (when the guarded adapter can split both sides into
   linear forms, :func:`satassume.theories.lra.lra_adapter.order_sides`): each side is
   ``sum(c_i * u_i) + k`` (rational ``c_i``, opaque terms ``u_i``, a
   rational ``k``, and possibly one ``oo`` or ``-oo`` summand).  A term
   pushes its side *up* if it is ``positive_infinite`` with ``c > 0`` or
   ``negative_infinite`` with ``c < 0`` (the ``oo`` summand always does),
   *down* in the other two cases.  In the extended reals a side with an
   up push is ``+oo`` or undefined (``oo - oo``), and with any non-real
   term it is no extended real either, so:

   * a push up in ``a`` -> ``~r``;  a push down in ``b`` -> ``~r``;
   * a push down in ``a``, no push up in ``a``, no push down in ``b``, every
     term an extended real -> ``r`` (``a = -oo``, ``b > -oo``);
   * a push up in ``b``, no push down in ``b``, no push up in ``a``, every
     term an extended real -> ``r`` (``b = +oo``, ``a < +oo``).

   The last two need every coefficient nonzero (a cancelling term would be
   ``oo - oo``); without that they are left out (incomplete, sound).
3. *finite terms* (LRA, unchanged): a *guarded* theory never sees ``r``
   itself.  The engine registers a fresh variable ``t`` with the theory
   and adds

       real(u1) & ... & real(uk)  ->  (r <-> t)

   for the opaque terms ``u`` of the linear form of ``a - b`` (``real``
   implies ``finite``).  With every term a finite real both sides are
   finite reals, where ``t`` is exact.  An atom with an ``oo`` summand has
   no finite case and gets no ``t``.  Closed real constants (``pi``) are
   terms with bounds (below) and never infinite.

When no term is ``+-oo`` and every term is real the atom is exactly ``t``;
when some term is infinite, clauses 2 decide it as far as the signs allow;
with a non-real term only clause 1 applies (the side may still be real:
``x + y`` with ``x = I``, ``y = 1 - I``).  ``eq`` atoms go to guarded
theories with the guard of clause 3 (LRA's ``a - b = 0``) and to unguarded
ones (EUF) directly.

An ``lt`` atom is *interpreted* when clause 1 decides it, when it has an
``oo`` summand and clauses 2 apply, or when a guarded theory registers it
(clause 3); otherwise it keeps clause 1 but is uninterpreted (below).

Links to the unary vocabulary
-----------------------------
For every argument ``e`` of a relation in the query or the assumptions,
and every argument of a vocabulary atom of the query or the assumptions
once the session has relations, the engine adds (``gt(e, 0)`` is the atom
``lt(0, e)``; each under the selector of ``e``, see "Switched glue"):

======================================  ======================================
clause                                  why it is sound
======================================  ======================================
``extended_positive(e) <-> gt(e, 0)``   ``0 < e`` in the extended reals
``extended_negative(e) <-> lt(e, 0)``   as above
``zero(e) <-> eq(e, 0)``                ``Eq(e, 0)`` holds iff ``e`` is zero,
                                        in any domain (``Eq(nan, 0)`` is
                                        False and ``nan`` is not zero)
======================================  ======================================

The rule base derives ``positive`` (``extended_positive & finite``),
``nonnegative``, ``nonzero`` and the rest from these three.  Numbers are
not linked (their unary facts are closed already).

Zero is an equality
-------------------
``zero(t)`` fixes the value of ``t`` exactly as ``eq(t, 0)`` does, and
the glue reads it so where that matters: a ``zero(t)`` (``t`` no number)
whose ``t`` occurs as an argument, at any depth, of an application of an
undefined function (``g(t, 1)``, ``g(Abs(h(t)))``) gets the *twin*
``eq(t, 0)`` as one more atom of the formula (:func:`zero_twins`,
:func:`glue_atoms`): the session allocates the twin with the formula
(``Session._ensure_atoms``), :meth:`Relations.process` gives it the
clauses and the ``"user"`` role of an equality of the formula (so ``t``
joins the EUF class of ``0`` and is a full transfer candidate, as for
``Q.eq(t, 0)``), and ``Session.assumption_lits`` counts it for the gate,
the selectors and :meth:`Relations.wants_transfer`.  ``Q.zero(t)`` and
``Q.eq(t, 0)`` then call for the same glue, in the set and in the
proposition (nightly family A).  Atoms carry no polarity, so
``~Q.zero(t)`` calls for the glue of ``Q.ne(t, 0)`` under the same
condition; ``Q.nonzero(t)`` (real and not zero) is a sign atom like
``Q.positive(t)``, which is no order atom either, and has no twin.

Where the condition is read.  The set's own twins (a ``zero(t)`` of
``a`` with ``t`` under an application of ``a``) are the set's glue, at
the root of its session: a function of ``a`` alone.  A query ``p`` reads
the ``zero`` atoms of ``p`` and of ``a`` against the applications of
``p`` and of ``a`` (``Session._glue_of``): a twin only the two together
call for (``a`` holds ``zero(n)``, ``p`` asks about ``g(n, 1)``; or ``p``
holds ``zero(n)`` and ``a`` mentions ``g(n)``) is the query's glue,
switched on by its selectors like a relation atom of ``p``.  Either way
it is a function of the formulas' atoms (their structure), never of what
the session holds, so a fresh session for ``(p, a)`` switches on the same
glue.  The discovery budget counts the twins of each formula in its cone
and those of the pair in ``Engine._within_budget``; the relevance layer
checks a set with a twin of its own whole (the set's own scope,
``scope.theory_scope``, which counts the twins).

Why only there.  What the twin adds over the link clause ``zero(t) <->
eq(t, 0)`` that every linked ``t`` already has (below) is (1) congruence
through the EUF class of ``0`` (``g(t) = g(0)``), (2) ``t`` as a transfer
candidate, which moves unary facts between the members of an EUF class,
and (3) switching the glue (links, LRA, transfer) on for a set or query
with no relation atom of its own.  (1) needs an application with ``t``
under it: without one no congruence involves ``t``.  (2) relates ``t`` to
the numbers ``0`` and to terms equal to ``t``; ``zero(t)`` already
fixes every unary fact of ``t`` through the rule base and ``0``'s are
closed, so with no application over ``t`` it moves nothing new (a term
equal to ``t`` comes from a relation atom, which switches the glue and
links ``t`` anyway).  (3) without an application over ``t``, ``t = 0``
reaches the other atoms only through the templates (which read
``zero(t)`` itself) or through LRA and the link clauses of ``t``, which a
relation atom or an affine pair switches on regardless of the spelling.
Shapes checked to agree outside the condition (default,
``relevance=False``, ``transfer=False``): ``zero(x)`` with
``positive(y - x) & negative(y)``, ``positive(y + x)``, ``eq(y, x)``,
``eq(y, x + 1)``, ``lt(y, x + 1)``, ``eq(u, x*v)``, ``zero(x - y)``,
``ge(y, x)``, and ``zero`` in the proposition against ``eq(x, y) &
zero(y)``, ``le(x, 0) & ge(x, 0)``, ``lt(x, y) & zero(y)``, ``eq(x*y,
0)``, ``eq(x, -y)``.  Every nightly family-A finding (G1-G5) has ``t``
under an application.  One shape where they still differ (by (3)): a
``zero(s)`` on a sum ``s`` whose bounds come from facts on its terms
only, with no relation atom and no affine pair: under ``integer(k) &
integer(x) & negative(k) & positive(x)``, ``Q.zero(k - x + 1)`` is None
(and ``~Q.zero``, ``Q.nonzero`` too) where ``Q.eq(k - x + 1, 0)`` is
False, since only LRA sees ``k - x + 1 <= -1``; three refine-stream
queries (12736, 12785, 12865) have it and no nightly finding.  Both
answers are sound; ``tests/test_zero_glue.py`` pins it (strict xfail).
Reading every ``zero(t)`` as a twin closed it but cost +56% on the
refine stream, where ``zero(x)`` is common: it switched the glue on for
many sets that never needed it.

No clause is new: the twin is tied to ``zero(t)`` by the link clause
``zero(t) <-> eq(t, 0)`` of ``t`` (under ``link_sel[t]``, which every
query with the twin assumes, since ``t`` is a side of it), sound in every
domain as the table says (``Eq(nan, 0)``, ``Eq(oo, 0)`` and ``Eq(zoo,
0)`` are False and none of them is zero; the vocabulary's ``zero`` is
the value 0, docs/design.md "Extended reals and ``nan`` in templates";
the same link already ties every linked ``t``).  Everything else
the twin brings is what a user ``eq(t, 0)`` brings, under its selectors,
so the I3 argument of "Switched glue" covers it, and what a query
switches on stays a function of its formulas' atoms.

Integrality
-----------
Each linked ``e`` whose linear form a guarded adapter reads
(:func:`satassume.theories.lra.lra_adapter.integer_form`: ``sum(c_i*u_i) + k`` with
rational ``c_i``, ``k`` and opaque or constant terms ``u_i``, as a side of
an LRA atom) also gets an integrality atom ``i`` ("the form is an
integer", :class:`satassume.theories.lra.lra.Integral`) and, with the guard of
clause 3,

    real(u1) & ... & real(uk)  ->  (integer(e) <-> i)

Sound: with every term a finite real, ``e`` is the form's value, a finite
real, and ``integer(e)`` holds iff that value is an integer (SymPy's
``integer`` implies finite, so ``oo`` is no integer, and an infinite term
fails the guard).  The same holds when the form is ``e`` itself (``x``,
``sin(x)``): ``i`` is still a fresh atom tied to ``integer(e)`` under the
guard ``real(e)`` and the link selector of ``e``, so the theory hears of
the integrality of ``e`` only in the queries that link ``e`` (bounds on
any linear form holding ``e`` are rounded with it: ``0 < 2*n < 2`` for an
integer ``n`` is refuted only where ``n`` itself is linked, as in a fresh
session).  The theory rounds bounds and branches (see
:mod:`satassume.theories.lra.lra`, "Integrality"), so ``Q.integer(t)`` is False under
``0 < t < 1`` and ``Q.ge(n, 1)`` is True for an integer ``n > 0``; the
``<-`` half gives True where the bounds pin ``e`` to an integer
(``Q.integer(x)`` under ``2 <= x <= 2``).  The opaque terms themselves
are not linked (a declared-integer ``n`` inside ``2*n + 1`` counts through
the linked sides only).  ``INTEGERS = False`` turns the link off.

Constant terms
--------------
``pi``, ``E`` and rational powers of rationals (``sqrt(2)``), with
``+ - * /``, are exact numbers of the LRA form (constants and coefficients:
``x <= 3*pi/2``, ``x/pi``; :mod:`satassume.theories.lra.constfield`), not terms.  So is
every other closed real constant with rigorous bounds (``log(2)`` of
``x <= log(2)``), as an indeterminate of the field, while
:data:`satassume.theories.lra.lra_adapter.GENERIC_CONSTANTS` is True (the default).
Without it, such a constant is
a term of the LRA form (see :mod:`satassume.theories.lra.lra_adapter`); its guard
``real(pi)`` is decided at the root by the rule base, and the first atom
that brings it in has the adapter register its rational bounds
``lo < pi < hi`` as two theory atoms asserted by unit clauses, once per
session (:meth:`Relations._bound`).  A constant the engine knows to be
real context-free (``Engine.is_``) gets no guard literal and hence no node
of its own: its ``real`` literal would be false at the root anyway.

Monotone functions
------------------
An application ``f(u)`` of a function :mod:`satassume.theories.mono` lists
(``exp``, ``log``, ``atan``, ``tanh``, ``sinh``, ``asinh``, ``cosh``,
``acot``, ``u**k`` with a Rational ``k``; ``Abs``, ``floor``, ``ceiling``
for rows only) is an opaque LRA term, so ``x > 1`` and ``log(x) > 0`` are
unrelated atoms for LRA.  ``_mono_step`` reads every atom LRA interprets
and *links* each application of a function with pieces (an interval of
the extended reals where ``f`` is strictly monotone) to LRA: an inert
enable variable ``e <-> MO(f(u)) & real(f(u)) & real(s)`` for the terms
``s`` of ``u``, registered with the theory as a ``lra.MonoLink``.  While
``e`` holds, LRA derives bounds through the link as it asserts bounds
(``LRATheory._mono_link``): a bound of ``u`` inside a piece ``u`` lies in
gives a bound of ``f(u)`` (``x >= 2 -> x**2 >= 4`` on ``[0, oo]``), a
bound of ``f(u)`` a bound of ``u`` through the table's inverse
(``log(x) > 0 -> x > 1``), and ``e`` alone the range of ``f`` (``exp(u)
> 0``, ``|atan(u)| < pi/2``), each with ``e`` and the bounds used as its
reason.  No atom and no clause is made per threshold.  Two kinds of
facts relate two LRA terms and stay clauses between relation atoms:

* pairs: ``a < b`` against ``f(a) < f(b)`` (or ``>`` on a decreasing
  piece), and ``f(a) < f(b)`` against ``a < b`` for a function increasing
  on the whole line;
* rows: the sandwich facts of ``Abs``, ``floor``, ``ceiling``
  (``floor(u) <= u < floor(u) + 1``), made where something other than a
  sign link reads the application (``_mono_open``).

Every clause and the enable variable carry ``~MO(f(u))``, a switch
variable implied by the term's link selector (``IL``), so MONO acts only
in the queries that read ``f(u)`` as an LRA term (see "Switched glue").
Pair atoms are tagged (``_mono_made``) so that a pair made from a pair
stops there.

Predicate transfer
------------------
When the relation atoms of the query make an equality (an ``eq`` atom, or
inequalities that give one: ``x <= y`` and ``y <= x``, see
:meth:`Relations._trichotomy`; ``satassume.scope.theory_scope``), the
session attaches, at construction, a
:class:`satassume.theories.transfer.TransferTheory`: the node blocks of the
candidate terms are registered with it under the nodes' EUF terms, so
terms in one EUF class share all unary facts (``Q.prime(x)`` from
``Q.eq(x, 2)``).  See :meth:`Relations._engage_transfer` and
:meth:`Relations.sync_transfer`.

Switched glue
-------------
Glue made for one query must not act in another (#53 stage 5, written
when a session answered many queries): an answer is a function of the
query, not of what the session met before.  Since #97 a session serves
the check of its set and then one query (``Engine._build_context``), and
the selectors keep the check to the set's own glue.  So every clause that ties relations to unary
atoms, and everything a theory does with an atom beyond reading its own
variable, carries a *selector* variable, and ``Session.assumption_lits``
assumes, for a query ``p`` under assumptions ``a``, only the selectors of
the glue ``p`` and ``a`` themselves call for:

* the link clauses of a term ``e`` (and its integrality clauses) carry
  ``link_sel[e]``; assumed for the vocabulary-atom arguments and the sides
  of the interpreted relation atoms of ``p`` and ``a``
  (:meth:`Relations.selectors_of`), only if ``p`` or ``a`` holds a
  relation atom (a ``zero(t)`` with ``t`` under an application counts as
  ``eq(t, 0)``, see "Zero is an equality") or an affine pair
  (``scope.affine_pair``: the ``glue`` of the query's theory scope);
* the clauses of :meth:`Relations._eq_infinity`, :meth:`Relations._eq_links`
  and :meth:`Relations._trichotomy` carry their atoms' ``atom_sel``;
  assumed for the relation atoms of ``p`` and ``a``.  The user-atom clauses
  of an equality are added the first time a query mentions it, also if the
  glue made the atom earlier;
* the guarded theories' twins of an equality (clause 3: LRA's ``a - b =
  0``) carry the guard of a *role* of the atom (:meth:`Relations._add_role`):
  a user equality its ``atom_sel``, a link's ``eq(e, 0)`` the link's
  selector, the equality of :meth:`Relations._trichotomy` both order atoms'
  selectors, an interface equality the share variables of its two terms
  (see :meth:`Relations._share`).  EUF reads the atom's own variable, so
  an unswitched twin would be a bridge: an equality LRA derives from the
  current query's bounds on the sides of an atom an earlier query made
  would reach EUF and predicate transfer;
* every lemma of predicate transfer carries ``xfer_sel``
  (``TransferTheory.guard``); assumed iff the relation atoms of ``p`` and
  ``a`` make an equality (:meth:`Relations.wants_transfer`, the
  ``transfer`` of the query's theory scope), the condition on which the
  session engaged transfer at construction.  Each
  candidate term but a rational number takes part only while its enable
  variables say so (``TransferTheory.switch``): all its predicates while
  it is a side of a user or trichotomy equality the query activates, or a
  congruent application of terms the query activates, ``polar`` alone
  while it is a link-only side (see :meth:`Relations.sync_transfer`).  A
  structural number argument of a vocabulary atom (``sin(2)``) has a
  selector of its own for that (``num_sel``).

When ``a`` holds a relation atom, its own selectors are on in every
query of its session: they are root units there (``Session._set_glue``),
and a query assumes only the selectors it adds.  The selectors and the
variables they imply are *inert* for the search (``Solver.set_inert``):
never decided, False where nothing assigned them, which is the extension
of the inertness argument (DESIGN I3) done by the solver itself.

The remaining clauses of an atom (clauses 1 and 2 above, and the twins of
an order atom, which LRA alone reads) constrain the atom given its sides,
never a side given the atom, so the relation atoms of other queries are
free variables and need no selector.  A learnt clause that used a
switched clause or lemma contains a negated selector (or enable variable,
implied by selectors) and is inert wherever it is not assumed.

A relation no theory interprets stays a free Boolean (the default
``Engine(uninterpreted="free")``); with ``uninterpreted="none"`` (opt-in,
the old behaviour) it raises :class:`Uninterpreted` and ``ask`` returns None.

Combining theories
------------------
Theories are kept apart by atom kind (each adapter accepts what it can
interpret; ``eq`` may go to several) and share equalities through
interface atoms: whenever a term becomes known to two adapters
(``shared_terms()``), the atom ``eq(a, b)`` is created for it and every
other shared term, and registered like any other relation atom, so each
theory sees the same Boolean (delayed theory combination; see
:class:`satassume.sat.theory.EqualitySharing`).  A pair with a constant term
that is not rational (``eq(pi, x)``) gets no interface atom.  Such an
atom passes an equality with the constant between the theories, e.g.
``x = pi`` derived by LRA from ``x <= pi <= x`` reaching EUF, where it
would give ``f(x) = f(pi)``; on the refine stream these atoms decided no
query and cost search (about 10% of the decisions under the assumption
sets with ``pi``).  Leaving them out is a relaxation, never unsound.

Adapters
--------
An adapter spec is ``(name, factory, guarded)``; ``factory()`` returns an
object with

* ``register(solver, var, atom) -> bool``: interpret the SymPy atom
  (``Q.lt(a, b)`` or ``Q.eq(a, b)``) and register ``var``
  with its theory (attaching the theory on first use); False if the atom
  is not interpreted;
* ``terms(atom) -> list`` (guarded adapters): the opaque terms of the
  atom, for the guard;
* optionally ``order_sides(atom)`` (guarded adapters): the linear forms of
  the two sides of ``Q.lt(a, b)`` with their ``oo`` summands, for
  clauses 2 (see :func:`satassume.theories.lra.lra_adapter.order_sides`);
* ``shared_terms() -> set``: every term the adapter's theory knows.

The default specs are the LRA and EUF adapters when their modules exist
(:func:`default_specs`).  With no spec at all the engine behaves exactly
as without relation support: ``sympy_api.ask`` returns None for relations.
"""
from __future__ import annotations

import weakref
from fractions import Fraction
from typing import Any, Callable, List, NamedTuple, Optional

from .knowledge.extensions import Args
from .sat.formula import And, Not, P
from .knowledge.rules import BASIS_INDEX, NPRED, PRED_INDEX
from .theories.lra.constfield import Undecided, sign
from .sat.theory import EqualitySharing
from .theories.transfer import transfer_wanted
from .state.memos import PROCESS as _PROCESS

#: atom predicates the engine gives to theories
RELATION_ATOMS = frozenset({"eq", "lt"})

#: link ``integer(e)`` to an integrality atom of the guarded theories (see
#: "Integrality")
INTEGERS = True

#: monotone-function and range lemmas for applications that are LRA terms
#: (see "Monotone functions"; :mod:`satassume.theories.mono`)
MONO = True

_OPS = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}

#: kinds of the per-term variables of a session's glue (Relations._tvar)
_SD, _EN, _MC, _IE, _IL, _MO = range(6)


class AdapterSpec(NamedTuple):
    name: str
    factory: Callable[[], Any]
    guarded: bool


def _missing(e: ModuleNotFoundError, module: str) -> bool:
    """Whether ``e`` says that ``module`` (relative to this package) does
    not exist, not that a module it imports is missing."""
    return e.name == f"{__package__}.{module}"


def default_specs() -> List[AdapterSpec]:
    """The real adapters: an adapter module that does not exist is left
    out; one that exists but fails to import raises."""
    specs = []
    try:
        from .theories.lra.lra_adapter import LRAAdapter
    except ModuleNotFoundError as e:
        if not _missing(e, "theories.lra.lra_adapter"):
            raise
    else:
        specs.append(AdapterSpec("lra", LRAAdapter, True))
    try:
        from .theories.euf.euf_adapter import EUFAdapter
    except ModuleNotFoundError as e:
        if not _missing(e, "theories.euf.euf_adapter"):
            raise
    else:
        specs.append(AdapterSpec("euf", EUFAdapter, False))
    return specs


class Uninterpreted(Exception):
    """A relation of the query or the assumptions is interpreted by no
    theory; ``ask`` returns None (as without relation support)."""


# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------

def _key(e):
    from sympy.core.sorting import default_sort_key
    return default_sort_key(e)


def _ext_atoms(*sides) -> list:
    """``extended_real(e)`` for each side that is not a Rational, ``oo`` or
    ``-oo`` (those are extended reals)."""
    from sympy import S
    return [P("extended_real", e) for e in sides
            if not (getattr(e, "is_Rational", False) or e is S.Infinity
                    or e is S.NegativeInfinity)]


def _affine_strip(lhs, rhs):
    """``(s, t)`` for ``lhs = k*s + c`` and ``rhs = k*t + c`` with the same
    Rational ``c`` and the same nonzero Rational ``k`` (read off the sides
    with ``as_coeff_Add`` / ``as_coeff_Mul``), repeated to a fixed point;
    the sides unchanged otherwise.  A Float coefficient is left alone.

    ``eq(k*s + c, k*t + c)`` and ``eq(s, t)`` agree at every point of the
    extended domain: ``u -> k*u + c`` is injective on the complex numbers
    and on ``oo``, ``-oo``, ``zoo`` (``k*oo`` is ``oo`` or ``-oo`` by the
    sign of ``k``, ``zoo`` stays ``zoo``, adding ``c`` fixes each), sends
    ``nan`` to ``nan`` and nothing else to ``nan``; a ``nan`` side equals
    nothing (as :meth:`Relations._eq_links` assumes), so both relations
    are false when either side is ``nan``.  A pure function of the two
    sides, symmetric in them, and idempotent."""
    from sympy import Expr
    while True:
        if not (isinstance(lhs, Expr) and isinstance(rhs, Expr)):
            return lhs, rhs
        c1, s = lhs.as_coeff_Add()
        c2, t = rhs.as_coeff_Add()
        if c1.is_Rational and c2.is_Rational and c1 != 0 and c1 == c2:
            lhs, rhs = s, t
            continue
        k1, s = lhs.as_coeff_Mul()
        k2, t = rhs.as_coeff_Mul()
        if (k1.is_Rational and k2.is_Rational and k1 != 1 and k1 != 0
                and k1 == k2):
            lhs, rhs = s, t
            continue
        return lhs, rhs


def relation_atom(name: str, lhs, rhs):
    """The formula for relation ``name`` (``eq ne lt le gt ge``)."""
    if name in ("eq", "ne"):
        from sympy import S
        if not (_is_number(lhs) or _is_number(rhs)):
            # canonical under shared affine bijections: -x = -y, x + 1 =
            # y + 1 and 2*x = 2*y are all eq(x, y)
            lhs, rhs = _affine_strip(lhs, rhs)
        if lhs is S.NaN or rhs is S.NaN:
            # never sort with nan: default_sort_key would compare it
            # numerically (SymPy 1.14 raises); nan goes last
            a, b = (rhs, lhs) if lhs is S.NaN else (lhs, rhs)
        else:
            a, b = sorted((lhs, rhs), key=_key)
        atom = P("eq", Args((a, b)))
        return atom if name == "eq" else Not(atom)
    if name == "lt":
        return P("lt", Args((lhs, rhs)))
    if name == "gt":
        return P("lt", Args((rhs, lhs)))
    if name in ("le", "ge"):
        a, b = (lhs, rhs) if name == "le" else (rhs, lhs)     # a <= b
        from sympy import S
        if a is S.NaN or b is S.NaN:
            return False                  # nan is no extended real
        f = Not(P("lt", Args((b, a))))
        ext = _ext_atoms(a, b)
        return And(*ext, f) if ext else f
    raise ValueError(f"unknown relation {name!r}")


def relational_name(rel) -> str:
    """``eq ne lt le gt ge`` for a SymPy ``Relational``."""
    return _OPS[rel.rel_op]


_SYMPY_ATOMS = _PROCESS.table(f"{__name__}._SYMPY_ATOMS", "pure", 100_000)


def sympy_atom(atom: P):
    """``Q.eq(a, b)`` / ``Q.lt(a, b)`` for a normalised relation atom
    (memoized: a pure function of the atom)."""
    r = _SYMPY_ATOMS.get(atom)
    if r is None:
        from sympy.assumptions.ask import Q
        r = {"eq": Q.eq, "lt": Q.lt}[atom.pred](*atom.expr)
        if len(_SYMPY_ATOMS) >= _SYMPY_ATOMS.size:
            _SYMPY_ATOMS.clear()
        _SYMPY_ATOMS[atom] = r
    return r


def _is_number(e) -> bool:
    return bool(getattr(e, "is_number", False)) and not getattr(e, "free_symbols", True)


_ZERO_TWINS = _PROCESS.table(f"{__name__}._ZERO_TWINS", "pure", 100_000)
_UNDER_APPS = _PROCESS.table(f"{__name__}._UNDER_APPS", "pure", 100_000)


def _under_apps(e) -> frozenset:
    """The terms that occur in ``e`` (an atom's argument, or the tuple of a
    relation's sides) as an argument, at any depth, of an application of
    an undefined function (``AppliedUndef``): for ``g(Abs(h(y)), 1)``
    ``Abs(h(y))``, ``h(y)``, ``y`` and ``1``.  Memoized per ``e``."""
    r = _UNDER_APPS.get(e)
    if r is not None:
        return r
    from sympy import Basic, preorder_traversal
    from sympy.core.function import AppliedUndef
    out = set()
    for side in (e if isinstance(e, tuple) else (e,)):
        if not isinstance(side, Basic):
            continue
        for app in side.atoms(AppliedUndef):
            for arg in app.args:
                out.update(preorder_traversal(arg))
    r = frozenset(out)
    if len(_UNDER_APPS) >= 100_000:
        _UNDER_APPS.clear()
    _UNDER_APPS[e] = r
    return r


def zero_args(atoms) -> tuple:
    """The arguments ``t`` (no number) of the ``zero(t)`` atoms among
    ``atoms``, in first-seen order."""
    zs = ()
    for a in atoms:
        if a.pred == "zero":
            e = a.expr
            if e not in zs and not _is_number(e):
                zs += (e,)
    return zs


def under_of(atoms) -> frozenset:
    """The terms under an application in the atoms ``atoms``
    (:func:`_under_apps` of each)."""
    out = frozenset()
    for a in atoms:
        u = _under_apps(a.expr)
        if u:
            out = out | u
    return out


def zero_twin(e) -> P:
    """The twin ``eq(e, 0)`` of ``zero(e)`` (memoized per ``e``)."""
    tw = _ZERO_TWINS.get(e)
    if tw is None:
        from sympy import S
        tw = relation_atom("eq", e, S.Zero)
        if len(_ZERO_TWINS) >= 100_000:
            _ZERO_TWINS.clear()
        _ZERO_TWINS[e] = tw
    return tw


def zero_twins(atoms, context=(), cinfo=None) -> list:
    """The twins ``eq(t, 0)`` of the ``zero(t)`` atoms among ``atoms`` and
    ``context`` (``t`` no number) whose ``t`` occurs as an argument of an
    application in one of them (:func:`_under_apps`), in first-seen
    order: see "Zero is an equality" in the module docstring.  ``cinfo``:
    ``(zero_args(context), under_of(context))`` if the caller has them.
    A pure function of the two atom sequences."""
    if cinfo is None:
        czs = zero_args(context)
        cunder = None
    else:
        czs, cunder = cinfo
    zs = zero_args(atoms)
    if not zs and not czs:
        return []
    if cunder is None:
        cunder = under_of(context)
    under = under_of(atoms)
    if not under and not cunder:
        return []
    out = []
    for e in zs + czs:
        if (e in under or e in cunder):
            tw = zero_twin(e)
            if tw not in out:
                out.append(tw)
    return out


def glue_atoms(atoms, context=(), cinfo=None) -> tuple:
    """``atoms`` (of a user formula) and, after them, the twins
    (:func:`zero_twins`) of the ``zero`` atoms of it and of ``context``
    (the atoms of the assumption formula a query is asked under; ``()``
    for the assumption formula itself) that it lacks: the atoms the
    relation glue reads the formula by.  ``atoms`` itself if there is
    none."""
    twins = zero_twins(atoms, context, cinfo)
    if not twins:
        return atoms
    have = set(atoms)
    return tuple(atoms) + tuple(tw for tw in twins if tw not in have)


def _termwise(a, b, d) -> bool:
    """``d`` (SymPy's ``a - b``) is the sum of the terms of ``a`` and the
    negated terms of ``b``, up to how SymPy adds up the constants that are
    ``Number``s (``2``, ``oo``) or finite (``pi``, ``I``): no other term is
    cancelled, merged (``2*f(1) - f(1)``) or absorbed (``oo + x`` for a real
    ``x``).  Its value is then that of ``a`` minus that of ``b`` at every
    point."""
    from collections import Counter

    from sympy import Add

    def terms(e):
        return [t for t in Add.make_args(e)
                if not (t.is_Number or _is_number(t) and t.is_finite)]

    return Counter(terms(d)) == Counter(terms(a) + [-t for t in terms(b)])


def _constant_term(e) -> bool:
    """``e`` is a closed constant that is not a rational number (``pi``,
    ``sqrt(2)``): an LRA term with bounds, left out of equality sharing."""
    return _is_number(e) and not e.is_Rational


def _number_basis(engine, c, facts=False) -> tuple:
    """The predicates to register with the transfer theory for the number
    ``c``: a small set of its decided facts whose unit propagation under the
    rule base gives all of them, plus every predicate its facts leave open.

    A term merged with ``c`` receives the basis and its own rule block
    derives the rest, exactly the facts of ``c`` (the rule block propagates
    ``RULE_INTERNAL``, the same clauses as ``RULE_INSTANTIATED`` used here);
    a contradiction with a non-basis fact shows up in that block.  The open
    predicates are transferred as they are.  Memoized per engine and
    number in ``engine._xbasis``: a number's facts are context-free, but
    they are the engine's answers, so the engine drops the memo with its
    other set memos when its settings or the registry epoch change."""
    memo = engine._xbasis
    r = memo.get(c)
    if r is not None:
        return r[1] if facts else r[0]
    from .knowledge.rules import BASIS, RULE_INSTANTIATED, closure_mask, lit_bit, lits_mask
    decided, open_ = [], []
    for k, v in enumerate(engine.is_many(c, BASIS)):
        if v is None:
            open_.append(k)
        else:
            decided.append(k + 1 if v else -(k + 1))
    want = lits_mask(decided)

    def closes(lits):
        m = lits_mask(lits)
        d = closure_mask(RULE_INSTANTIATED, m)
        return d >= 0 and not want & ~(d | m)
    # greedy: a decided literal the closure of the basis so far does not
    # give joins it; the closure grows incrementally (unit propagation is
    # monotone: closing the closure plus a literal closes the set plus it)
    basis = []
    closed = 0                            # closure of ``basis``; -1: conflict
    for l in decided:
        bit = 1 << lit_bit(l)
        if closed >= 0 and closed & bit:
            continue
        basis.append(l)
        if closed >= 0:
            closed = closure_mask(RULE_INSTANTIATED, closed | bit)
    for l in list(basis):
        rest = [m for m in basis if m != l]
        if closes(rest):
            basis = rest
    if not closes(basis):                 # defensive: fall back to all
        basis = decided
    r = (tuple(sorted({abs(l) - 1 for l in basis} | set(open_))),
         tuple((abs(l) - 1, l > 0) for l in basis))
    memo[c] = r
    return r[1] if facts else r[0]


def _number_facts(engine, c) -> tuple:
    """``[(pred index, value), ...]``: the basis of the facts of number
    ``c`` (see :func:`_number_basis`)."""
    return _number_basis(engine, c, facts=True)


_INF_PREDS = frozenset({"extended_real", "positive_infinite", "negative_infinite"})


def _own_term(sides, e) -> bool:
    """The order sides (:func:`satassume.theories.lra.lra_adapter.order_sides`) of
    ``0 < e`` or ``e < 0`` are ``0`` and ``e`` itself as the only term,
    with coefficient 1 and no ``oo`` summand."""
    (fa, ia), (fb, ib) = sides
    if ia or ib:
        return False
    if fa:
        fa, fb = fb, fa
    return not fa and len(fb) == 1 and fb.get(e) == 1


_CSIGNS = _PROCESS.table(f"{__name__}._CSIGNS", "pure", 100_000)


def _csign(e):
    """The sign (-1, 0, 1) of the closed constant ``e`` if it is a finite
    real the exact field reads (:func:`satassume.theories.lra.constfield.from_sympy`),
    decided rigorously; None otherwise.  Memoized per ``e``."""
    try:
        return _CSIGNS[e]
    except KeyError:
        pass
    from .theories.lra.constfield import from_sympy
    v = from_sympy(e, generic=True)
    r = None
    if v is not None:
        try:
            r = sign(v)
        except Undecided:
            pass
    _CSIGNS.put(e, r)
    return r


def _mono_guards(name):
    from .theories.mono import GUARDS
    return GUARDS[name]


# --------------------------------------------------------------------------
# per-session glue
# --------------------------------------------------------------------------

class Relations:
    """Relation atoms of one :class:`satassume.engine.Session`: their
    theories, guards, links and shared equalities."""

    def __init__(self, session, specs):
        # A weak proxy: the session owns this object and outlives every call
        # into it, and a strong back-reference would make session + solver +
        # clauses collectable only by a full garbage collection.
        self.session = weakref.proxy(session)
        self.specs = list(specs)
        self.adapters: dict = {}          # spec name -> adapter instance
        self.status: dict = {}            # atom -> interpreted by some theory
        self.queue: List[P] = []          # allocated, not yet interpreted
        self.linked: set = set()
        self._bounded: set = set()        # constant terms whose bounds are asserted
        self._guards: dict = {}           # terms -> guard literals (_guard)
        self._link_lt: dict = {}          # link atoms 0 < e, e < 0 -> e
        self.top: dict = {}               # vocabulary-atom arguments of user formulas
        self.active = False               # some relation atom exists
        self.sharing = EqualitySharing()
        self._pending_links: list = []
        #: linked term -> the selector guarding its link clauses (see
        #: "Switched glue"); assumed by the queries whose terms include it
        self.link_sel: dict = {}
        #: relation atom -> the selector guarding the clauses that tie it
        #: to unary atoms (_eq_infinity, _eq_links, _trichotomy); assumed
        #: by the queries that mention the atom
        self.atom_sel: dict = {}
        #: structural number arguments of vocabulary atoms (never linked,
        #: ``sin(2)``) -> the selector the queries mentioning them assume:
        #: such a node is a term of predicate transfer (a possible congruent
        #: candidate) only in those queries (_mention_number)
        self.num_sel: dict = {}
        self._xextra: list = []           # their expressions, for _xheads
        #: the selector guarding every lemma of predicate transfer (None
        #: until transfer is engaged, see _engage_transfer)
        self.xfer_sel: Optional[int] = None
        #: equality atoms that got their user-atom clauses (_eq_links): the
        #: first query mentioning the atom runs them, whoever made it
        self._user_eq: set = set()
        #: what a theory may do with an atom is switched per role too (see
        #: _add_role): relation atom -> its roles [(kind, guard)]
        self._roles: dict = {}
        #: interpreted atoms -> (theory twins [(t, guard)] of an equality,
        #: its LRA terms, its EUF terms), for roles added later
        self._info: dict = {}
        #: link atoms -> the term e of the link (_link)
        self._link_of: dict = {}
        #: per term, the variables of what the current query makes of it
        #: (_tvar: _SD, _EN, _MC, _IE, _IL; 0 until needed), and the guards
        #: implying each (term, kind)
        self._tv: dict = {}
        self._tsrc: dict = {}
        self._xpairs: set = set()         # head pairs done (_congruence_pairs)
        self._xtcur = 0                   # cursor into the adapter's terms
        self._xhn = 0                     # head-group growth seen so far
        self._xhseen = -1                 # ... by sync_transfer
        #: eq atoms the glue made (links ``eq(e, 0)``, interface equalities);
        #: they do not engage predicate transfer by themselves
        self._aux_eq: set = set()
        self._link_eq: set = set()        # the links' eq(e, 0), of _aux_eq
        #: sides of the equality atoms EUF interprets -> 2 (a user or
        #: extension atom, or a number) or 1 (only a link's eq(e, 0));
        #: interface equalities add nothing (see sync_transfer)
        self._xside: dict = {}
        #: predicate transfer (satassume.theories.transfer), engaged by the first
        #: user or template equality atom; None until then
        self.xfer = None
        self._xadapter = None
        self._xslot = 1                   # cursor into table.slots
        self._xterm = 0                   # cursor into the adapter's atom sides
        self._xnsides = -1                # _xside state seen by sync_transfer
        self._xsides_n = 0                # changes to _xside so far
        self._xpart: set = set()          # link-only sides (polar registered)
        self._xheads: dict = {}           # (func, nargs) -> EUF terms
        self._xcounted: set = set()       # the terms in _xheads
        self._xpend: list = []            # (node, base) not yet candidates
        self._xcand: set = set()          # candidate nodes (registered)
        #: MONO (_mono_step): atoms LRA read, not yet looked at
        self._mono_todo: list = []
        self._mono_ad = None              # the LRA adapter
        self._mono_seen: set = set()      # terms looked up in the table
        self._mono_apps: dict = {}        # application -> its mono.Spec
        self._mono_pairs: list = []       # (var, a, b) for lt(a, b), no number side
        self._mono_by_arg: dict = {}      # argument -> its applications
        self._mono_done: set = set()      # pair keys emitted
        #: atoms a pair made -> ("f", None) for an image, ("i", None) for
        #: the arguments' atom: a pair is not matched back from it
        self._mono_made: dict = {}
        #: terms whose sandwich rows are on (``_mono_open``)
        self._mono_opened: set = set()
        #: the theory scope the session was built for (satassume.scope):
        #: with ``glue`` the vocabulary-atom arguments of its formulas are
        #: linked from the start (``active``; the sides of its relation
        #: atoms once a theory interprets them, ``process``), with ``transfer``
        #: predicate transfer is engaged here, before any atom exists
        scope = self.scope = session.scope
        if scope.glue:
            # the formulas arrive after this (note_formula records their
            # vocabulary-atom arguments, process links them)
            self.active = True
            if scope.transfer:
                self._engage_transfer()

    # -- entry points used by the session ------------------------------
    def enqueue(self, atom: P) -> None:
        self.queue.append(atom)

    def note_formula(self, atoms) -> None:
        """Remember the vocabulary-atom arguments of a user formula."""
        for a in atoms:
            if a.pred in PRED_INDEX:
                e = a.expr
                if e not in self.linked:
                    self.top[e] = None

    def process(self, user_atoms=()) -> None:
        """Interpret queued atoms, add guards, links and shared equalities;
        raise :class:`Uninterpreted` if a relation among ``user_atoms`` has
        no theory and the engine was built with ``uninterpreted="none"``
        (by default such atoms stay free Booleans)."""
        s = self.session
        user = [a for a in user_atoms if a.pred in RELATION_ATOMS]
        # the sides of a user relation are linked once a theory interprets
        # it: an opaque relation (a free atom, uninterpreted="free")
        # activates no theory and links nothing
        unlinked = set()
        for a in user:
            st = self.status.get(a)
            if st:
                for side in a.expr:
                    self._link_later(side)
            elif st is None:
                unlinked.add(a)
        for a in user:
            if a.pred == "eq":
                # transfer is engaged at construction when the query's
                # scope makes an equality (transfer.transfer_wanted: an eq
                # atom or a _trichotomy pair, W2B4b) and switched on per
                # query (Session.assumption_lits, wants_transfer).  A user
                # equality outside the scope (a session built for the set
                # alone and asked an equality: tests, or an equality of a
                # node fact, Extensions.node_facts) still engages it, and
                # is counted (stats["scope_misses"])
                if self.xfer is None and not self._want_transfer and s.engine.transfer:
                    s.engine.stats["scope_misses"] += 1
                    self._want_transfer = True
                self._note_sides(a, 2)
                var = s.table.custom.get(a)
                if var is not None and a not in self._user_eq:
                    # the atom's role is a function of the query: its
                    # user-atom clauses are added the first time a query
                    # mentions it, even if the glue made it earlier (an
                    # interface equality: S1), under its selector
                    self._user_eq.add(a)
                    self._eq_links(var, a)
                    self._add_role(a, [-self._atom_selector(a)], "user")
        while True:
            s.discover()
            if self.queue:
                atom = self.queue.pop()
                ok = self.status[atom] = self._interpret(atom)
                # also for an opaque relation (ok False): the glue then links
                # every vocabulary argument of this session; the relevance
                # layer splits a set by component (sympy_api.RELATIONAL), so
                # that is only the session of the relation's component
                self.active = True
                if ok and atom in unlinked:
                    for side in atom.expr:
                        self._link_later(side)
                continue
            if self.active and self.top:
                top, self.top = self.top, {}
                for e in top:
                    if _is_number(e):
                        self._mention_number(e)
                    else:
                        self._link_later(e)
            if self._pending_links:
                self._link(self._pending_links.pop())
                continue
            if self._mono_todo and self._mono_step():
                continue
            if self._share():
                continue
            if self._want_transfer and self.xfer is None:
                self._engage_transfer()
            if self.xfer is not None and self._transfer_terms():
                continue
            break
        if self.xfer is not None:
            self.sync_transfer()
        if s.engine.uninterpreted == "free":
            return
        for a in user:
            if not self.status.get(a):
                raise Uninterpreted(f"no theory interprets {a}")

    def _mention_number(self, e) -> None:
        """A structural number that is an argument of a vocabulary atom of
        a user formula (``sin(2)`` of ``Q.positive(sin(2))``) takes part in
        congruence as a term EUF reads would (:meth:`_congruence_pairs`),
        under a selector of its own that the queries mentioning it assume
        (``selectors_of``).  Numbers are not linked, and a number node an
        earlier query left in the session must not find a congruent partner
        for the current one."""
        if e in self.num_sel:
            return
        from .theories.euf.euf_adapter import structural
        if not structural(e):
            return
        sel = self.num_sel[e] = self._fresh(inert=True)
        self._tsource(e, _IE, [-sel])
        self._xextra.append(e)

    def _link_later(self, e) -> None:
        if e not in self.linked and not _is_number(e):
            self.linked.add(e)
            self._pending_links.append(e)

    def _fresh(self, inert: bool = False) -> int:
        """A new auxiliary solver variable; ``inert`` (``Solver.set_inert``)
        for a selector and the variables selectors imply (see "Switched
        glue")."""
        s = self.session
        v = s.table.aux()
        s.solver.ensure_vars(v)
        if inert:
            s.solver.set_inert(v)
        return v

    # -- interpretation ------------------------------------------------
    def _adapter(self, spec):
        ad = self.adapters.get(spec.name)
        if ad is None:
            ad = self.adapters[spec.name] = spec.factory()
        return ad

    def _interpret(self, atom: P) -> bool:
        s = self.session
        solver = s.solver
        var = s.table.custom[atom]
        order = atom.pred == "lt"
        # a link atom 0 < e or e < 0 (see _link): clause 1 is implied by
        # the link and the rule base (extended_positive and
        # extended_negative imply extended_real); only its demand is kept
        link = self._link_lt.get(atom) if order else None
        if link is not None:
            s.ensure(link, {"extended_real"})
        elif order and self._order_sides(var, atom):
            return True                       # false: a side is no extended real
        if order:
            self._trichotomy(var, atom)
        if atom.pred == "eq":
            # _eq_links is a user atom's (Relations.process).  An extension
            # fact may make an equality (no template does): it gets these
            # clauses (switched by its atom selector, so inert unless a
            # query mentions the atom), its sides are visited and engage
            # transfer, EUF reads it, and its twins and its sides'
            # candidacy have no role until a query mentions it (_add_role):
            # what it gives a query does not depend on whether an earlier
            # query brought the node whose fact made it
            self._eq_infinity(var, atom)
        sat = sympy_atom(atom)
        ok = False
        eq = atom.pred == "eq"
        twins, lterms, eterms = [], [], []
        for spec in self.specs:
            ad = self._adapter(spec)
            if not spec.guarded:
                if ad.register(solver, var, sat):
                    ok = True
                    if eq and hasattr(ad, "node_term"):
                        eterms.extend(ad.interned(atom.expr))
                        if atom not in self._aux_eq:
                            # a user atom (engaged by the scope), or one a
                            # template or extension made: a candidate side,
                            # but no engagement, since transfer's selector
                            # is assumed only when the user atoms make an
                            # equality (wants_transfer), i.e. when the
                            # scope engaged it already
                            self._note_sides(atom, 2)
                        elif atom in self._link_eq:
                            self._note_sides(atom, 1)
                continue
            if order and hasattr(ad, "order_sides"):
                sides = ad.order_sides(sat)
                if sides is not None:
                    if link is not None and _own_term(sides, link):
                        # clauses 2 of 0 < u and u < 0 for an opaque term u
                        # are implied by the link: positive_infinite(u)
                        # implies extended_positive(u), negative_infinite(u)
                        # extended_negative(u); only their demand is kept
                        s.ensure(link, _INF_PREDS)
                    else:
                        self._order_infinite(var, sides)
                    if sides[0][1] or sides[1][1]:
                        ok = True             # an oo summand: no finite case
                        continue
            terms = ad.terms(sat)
            if terms is None:                 # not interpreted: no variable
                continue
            t = self._fresh()
            if not ad.register(solver, t, sat):
                continue
            ok = True
            guard = self._guard(ad, terms)
            lterms.extend(terms)
            if MONO and hasattr(ad, "integer_form"):
                self._mono_ad = ad
                self._mono_todo.append((atom, var))
            if eq:
                # an equality's twin is switched by its roles (_add_role):
                # with EUF reading the atom itself, an unswitched twin
                # would hand every equality LRA derives on the sides of an
                # atom some earlier query made to EUF (and back)
                twins.append((t, guard))
                continue
            s.emit(guard + [-var, t])
            s.emit(guard + [var, -t])
        info = self._info[atom] = (twins, lterms, eterms)
        for kind, g in self._roles.get(atom, ()):
            self._apply_role(atom, info, kind, g)
        return ok

    def _guard(self, ad, terms) -> list:
        """``[-real(u), ...]`` for the opaque terms ``u`` of a guarded
        theory atom (clause 3); a constant term gets its bounds asserted
        (once per session) and no literal when it is real at the root.
        Memoized per session and term list (never mutate the result)."""
        key = (ad, tuple(terms))
        guard = self._guards.get(key)
        if guard is not None:
            return guard
        s = self.session
        guard = self._guards[key] = []
        for u in terms:
            if _is_number(u):
                if u not in self._bounded:
                    self._bounded.add(u)
                    self._bound(ad, u)
                if s.engine.is_(u, "real") is True:
                    # real(u) holds at the root: its guard literal is
                    # false everywhere, and u needs no node here
                    continue
            s.ensure(u, {"real"})
            guard.append(-s.var("real", u))
        return guard

    def _link_integer(self, ad, e, g: int) -> None:
        """``guard -> (integer(e) <-> i)`` for the integrality atom ``i`` of
        ``e``'s linear form in the guarded adapter ``ad`` (see
        "Integrality"); called once per linked expression, ``g`` the
        negated link selector of ``e``.  Also when ``e`` is its own term
        (``x``, ``sin(x)``): registering ``integer(e)`` itself as the atom
        would make the theory see the integrality of ``e`` in every later
        query, linked or not, and the bounds on any linear form holding
        ``e`` would be rounded with it (``0 < 2*n < 2`` refuted for an
        integer ``n`` once a query linked ``n``)."""
        form = ad.integer_form(e)
        if form is None:
            return
        s = self.session
        i = self._fresh()
        ad.register_integer(s.solver, i, form)
        guard = self._guard(ad, form[1])
        z = s.var("integer", e)
        s.emit(guard + [-z, i, g])
        s.emit(guard + [z, -i, g])

    def _eq_infinity(self, var: int, atom: P) -> None:
        """``eq(e, oo) <-> positive_infinite(e)`` and ``eq(e, -oo) <->
        negative_infinite(e)``: ``Eq(e, oo)`` holds iff ``e`` is ``+oo``, in
        any domain (``Eq(zoo, oo)`` is False)."""
        from sympy import S
        a, b = atom.expr
        for inf, pred in ((S.Infinity, "positive_infinite"),
                          (S.NegativeInfinity, "negative_infinite")):
            if b is inf:
                e = a
            elif a is inf:
                e = b
            else:
                continue
            s = self.session
            if _is_number(e):
                v = s.engine.is_(e, pred)
                if v is not None:
                    s.emit([var] if v else [-var])
                    return
            s.ensure(e, {pred})
            p = s.var(pred, e)
            g = -self._atom_selector(atom)
            s.emit([-var, p, g])
            s.emit([var, -p, g])
            return

    def _trichotomy(self, var: int, atom: P) -> None:
        """``a <= b`` and ``b <= a`` give ``a = b`` (the extended reals are
        totally ordered): for the ``lt`` atom ``var`` of ``a < b`` whose
        reverse ``b < a`` exists,

            extended_real(a) & extended_real(b) & ~(a < b) & ~(b < a)
                -> eq(a, b)

        guarded by both atoms' selectors (on for a query that mentions
        both).  So ``Q.le(x, y) & Q.ge(x, y)`` puts ``x`` and ``y`` into one
        EUF class as ``Q.eq(x, y)`` does, also where LRA cannot derive the
        equality (sides that may be infinite).  Not for the two link atoms
        ``0 < e`` and ``e < 0`` of one term: there the links and the rule
        base give ``zero(e)``, i.e. ``eq(e, 0)``, already."""
        a, b = atom.expr
        s = self.session
        rev = P("lt", Args((b, a)))
        rvar = s.table.custom.get(rev)
        if rvar is None:
            return
        lk = self._link_lt
        if lk.get(atom) is not None and lk.get(atom) is lk.get(rev):
            return
        eqa = relation_atom("eq", a, b)
        if eqa not in s.table.custom:
            self._aux_eq.add(eqa)
        eq = self._atom_var(eqa)
        # its sides are transfer candidates like a user equality's (with a
        # number side, x <= 2 <= x gives x every fact of 2), and its
        # theories see it, in the queries that mention both atoms; those
        # switch transfer on as an equality does (wants_transfer)
        self._note_sides(eqa, 2)
        # a pair of user atoms is in the query's scope (transfer.transfer_wanted
        # counts it), which engaged transfer at construction; a pair with an
        # extension atom switches nothing on (wants_transfer ignores it)
        both = [-self._atom_selector(atom), -self._atom_selector(rev)]
        self._add_role(eqa, both, "tri")
        clause = both + [var, rvar, eq]
        for e in _ext_atoms(a, b):
            s.ensure(e.expr, {"extended_real"})
            clause.append(-s.var("extended_real", e.expr))
        s.emit(clause)

    def _add_role(self, atom: P, g: list, kind: str) -> None:
        """Give the relation atom ``atom`` a role under the guard ``g``
        (negated selectors, all true exactly in the queries that call for
        the role): ``"user"`` (a query mentions it), ``"link"`` (a link
        atom of a linked term), ``"tri"`` (the equality of
        :meth:`_trichotomy`), ``"iface"`` (an interface equality, see
        :meth:`_share`).  What a theory does with the atom beyond the
        atom's own variable happens under the guard of one of its roles
        (:meth:`_apply_role`); roles come in any order, before or after
        the atom is interpreted."""
        roles = self._roles.get(atom)
        if roles is None:
            self._roles[atom] = [(kind, g)]
        else:
            for k, h in roles:
                if k == kind and h == g:
                    return                      # a role it has already
            roles.append((kind, g))
        info = self._info.get(atom)
        if info is not None:
            self._apply_role(atom, info, kind, g)

    def _apply_role(self, atom: P, info, kind: str, g: list) -> None:
        """The clauses of one role of an interpreted atom, each with the
        role's guard ``g``:

        * an equality's twins in the guarded theories (LRA's ``a - b = 0``,
          clause 3 of the module docstring): EUF reads the atom's own
          variable, so an unswitched twin is a bridge between the
          theories, and an atom an earlier query made would hand an
          equality LRA derives from the current query's bounds to EUF (and
          back);
        * for a link atom of ``e``, the sources of the share variables of
          its terms (:meth:`_share`);
        * transfer candidacy (see ``sync_transfer``): a user or
          :meth:`_trichotomy` equality enables all predicates of its sides,
          a link's ``eq(e, 0)`` the ``polar`` predicate of ``e``.

        Order atoms keep their twins unswitched: LRA alone reads them, and
        clauses 1 and 2 constrain them given their sides."""
        twins, lterms, eterms = info
        s = self.session
        emit = s.emit
        if twins:
            var = s.table.custom[atom]
            for t, guard in twins:
                emit(guard + g + [-var, t])
                emit(guard + g + [var, -t])
        tsource = self._tsource
        if kind == "link":
            for u in lterms:
                tsource(u, _IL, g)
            for u in eterms:
                tsource(u, _IE, g)
        if atom.pred != "eq" or not eterms or kind == "iface":
            return
        # transfer candidacy: the variables are allocated when a candidate
        # is registered (_xswitch) or a congruence clause needs them
        if kind == "link":
            tsource(self._link_of[atom], _SD, g)
            tsource(atom.expr[0] if _is_number(atom.expr[0]) else atom.expr[1], _SD, g)
        else:
            for e in atom.expr:
                if not getattr(e, "is_Rational", False):
                    tsource(e, _EN, g)
                tsource(e, _SD, g)

    def _tsource(self, u, k: int, g: list) -> None:
        """``g -> v`` for the variable ``v`` of kind ``k`` of term ``u``
        (now if it exists, else once it is allocated, :meth:`_tvar`)."""
        key = (u, k)
        lst = self._tsrc.get(key)
        if lst is None:
            self._tsrc[key] = [g]
        elif lst[-1] is g:
            return              # the same guard again (a link's three atoms)
        else:
            lst.append(g)
        tv = self._tv.get(u)
        if tv is not None:
            if tv[k]:
                self.session.emit(g + [tv[k]])
            elif tv[_MC] and k < _MC:
                self._tvar(u, k)              # links itself to MC

    def _tvar(self, u, k: int) -> int:
        """The variable of kind ``k`` of term ``u``, true exactly in the
        queries that make it so (all guarded by selectors those queries
        assume, see "Switched glue"):

        * ``_SD``: ``u`` is a side of an equality the query activates (a
          user or :meth:`_trichotomy` equality, a link's ``eq(e, 0)``);
        * ``_EN``: transfer gives ``u`` all its predicates: a side of a
          user or trichotomy equality, or a congruent application
          (:meth:`_congruence_pairs`);
        * ``_MC``: ``_SD`` or ``_EN`` (``u`` may be merged, for congruence);
        * ``_IE``, ``_IL``: ``u`` is a term EUF, LRA reads from the link
          atoms of a linked term the query activates (see :meth:`_share`).
        """
        tv = self._tv.get(u)
        if tv is None:
            tv = self._tv[u] = [0, 0, 0, 0, 0, 0]
        v = tv[k]
        if v:
            return v
        v = tv[k] = self._fresh(inert=True)
        emit = self.session.emit
        if k == _MC:
            for j in (_SD, _EN):
                if tv[j]:
                    emit([-tv[j], v])
                elif (u, j) in self._tsrc:
                    self._tvar(u, j)            # links itself to v
            return v
        for g in self._tsrc.get((u, k), ()):
            emit(g + [v])
        if k in (_SD, _EN) and tv[_MC]:
            emit([-v, tv[_MC]])
        return v

    def _atom_selector(self, atom: P) -> int:
        """The selector of ``atom``'s clauses to unary atoms (allocated on
        first use), see "Switched glue"."""
        sel = self.atom_sel.get(atom)
        if sel is None:
            sel = self.atom_sel[atom] = self._fresh(inert=True)
        return sel

    def _eq_links(self, var: int, atom: P) -> None:
        """Two sufficient conditions of ``eq(a, b)`` and one of its negation, for
        a user or extension atom (not the glue's):

        * ``positive_infinite(a) & positive_infinite(b) -> eq(a, b)``, and the
          same for ``negative_infinite`` (``Eq(oo, oo)`` is True);
        * ``zero(a - b) -> eq(a, b)``: a zero difference is finite, so both
          sides are finite and equal (``oo - oo`` is nan, not zero);
        * ``nonzero(a - b) -> ~eq(a, b)``: equal finite sides have a zero
          difference and equal infinite ones a nan difference, neither
          nonzero.

        These hold in every domain (the sides may be complex).  The
        difference is taken both as ``a - b`` and as ``b - a`` (``Q.zero(j -
        i)`` for ``Eq(i, j)``; both always, so that the clauses are a
        function of the atom and not of the nodes an earlier query left in
        the session), and only when SymPy built it term by term (:func:`_termwise`): its
        value is then the value of ``a`` minus that of ``b`` at every point
        (an extended sum does not depend on grouping: a ``nan`` term, or
        infinities in different directions, make it nan).  SymPy cancels and merges
        common terms (``x - (x + y)`` is ``-y``, ``(x + f(1)) - (y + f(1))``
        is ``x - y``, ``(2*f(1) + x) - (f(1) + y)`` is ``f(1) + x - y``),
        and the result is not the difference where a cancelled part is
        infinite or nan: ``x = oo``, ``f(1) = oo`` gives equal sides with a
        nonzero ``x - y``, and ``f(1) = g(1) = oo`` gives sides
        ``x + f(1) - g(1)`` and ``y + f(1) - g(1)`` that are nan (so not
        equal) with a zero ``x - y``.  Not for a side that is a number: an
        infinite one is :meth:`_eq_infinity`'s, and ``eq(e, 0)`` is
        ``zero(e)`` by the links."""
        a, b = atom.expr
        if _is_number(a) or _is_number(b):
            return
        s = self.session
        g = -self._atom_selector(atom)

        def emit(clause):
            s.emit(clause + [g])
        s.ensure(a, {"positive_infinite", "negative_infinite"})
        s.ensure(b, {"positive_infinite", "negative_infinite"})
        for pred in ("positive_infinite", "negative_infinite"):
            emit([-s.var(pred, a), -s.var(pred, b), var])
        for p, q in ((a, b), (b, a)):
            d = p - q
            if _is_number(d) or not _termwise(p, q, d):
                continue
            s.ensure(d, {"zero", "nonzero"})
            emit([-s.var("zero", d), var])
            emit([-s.var("nonzero", d), -var])

    # -- order atoms over the extended reals (clauses 1 and 2) ----------
    def _closed_extended_real(self, e):
        """``extended_real`` of a closed side, context-free (``nan`` is
        none); None if unknown or not closed."""
        if getattr(e, "is_Rational", False):
            return True
        if not _is_number(e):
            return None
        from sympy import S
        if e is S.NaN:
            return False
        return self.session.engine.is_(e, "extended_real")

    def _order_sides(self, var: int, atom: P) -> bool:
        """Clause 1 for the ``lt`` atom ``var``: ``var -> extended_real``
        of each side.  True if a side is known to be no extended real
        (``var`` is then false and the atom decided)."""
        s = self.session
        need = []
        for e in atom.expr:
            v = self._closed_extended_real(e)
            if v is False:
                s.emit([-var])
                return True
            if v is None:
                need.append(e)
        for e in need:
            s.ensure(e, {"extended_real"})
            s.emit([-var, s.var("extended_real", e)])
        return False

    def _order_infinite(self, var: int, sides) -> None:
        """Clauses 2 for the ``lt`` atom ``var`` with side forms
        ``((form_a, inf_a), (form_b, inf_b))`` (``form``: term ->
        coefficient; ``inf``: +1/-1 for an ``oo``/``-oo`` summand, else 0)."""
        s = self.session
        emit = s.emit
        push = []                             # per side: (up lits, down lits, const up, const down)
        ext = []                              # -extended_real(u) for every term
        exact = True
        seen = set()
        for form, inf in sides:
            up, down = [], []
            for u, c in form.items():
                if _is_number(u):
                    continue                  # a bounded real constant: finite
                if type(c) is Fraction:
                    sg = 1 if c > 0 else -1 if c else 0
                else:
                    try:
                        sg = sign(c)          # c involves constants (pi*x)
                    except Undecided:
                        return                # unknown sign: no clauses 2 (a relaxation)
                if not sg:
                    exact = False             # cancels: oo - oo if infinite
                    continue
                s.ensure(u, {"extended_real", "positive_infinite", "negative_infinite"})
                p, n = s.var("positive_infinite", u), s.var("negative_infinite", u)
                (up if sg > 0 else down).append(p)
                (down if sg > 0 else up).append(n)
                if u not in seen:
                    seen.add(u)
                    ext.append(-s.var("extended_real", u))
            push.append((up, down, inf > 0, inf < 0))
        (up_a, down_a, cup_a, cdown_a), (up_b, down_b, cup_b, cdown_b) = push
        if cup_a or cdown_b:                  # a = +oo or b = -oo: nothing is below/above
            emit([-var])
            return
        for l in up_a:                        # a is +oo or undefined
            emit([-l, -var])
        for l in down_b:                      # b is -oo or undefined
            emit([-l, -var])
        if not exact:
            return
        # a = -oo (a push down, none up), b > -oo, everything extended real
        rest = up_a + down_b + ext + [var]
        if cdown_a:
            emit(rest)
        else:
            for l in down_a:
                emit([-l] + rest)
        # b = +oo, a < +oo
        rest = down_b + up_a + ext + [var]
        if cup_b:
            emit(rest)
        else:
            for l in up_b:
                emit([-l] + rest)

    def _bound(self, ad, c) -> None:
        """Assert the rational bounds of the constant term ``c`` (``pi``,
        ``sqrt(2)``) as root facts of the theory: true for its value, so
        unconditional (no guard)."""
        register = getattr(ad, "register_bounds", None)
        if register is None:
            return
        s = self.session
        for v in register(s.solver, c, self._fresh):
            s.emit([v])

    # -- monotone functions (MONO, satassume.theories.mono) ---------------
    def _mono_step(self) -> bool:
        """Read the atoms LRA interpreted since the last call: link every
        new application of a listed function among their terms to LRA
        (:meth:`_mono_app`), open the sandwich rows of the applications an
        atom other than a sign link reads, and relate the pairs ``a < b``
        of applications of one function.  True if it made atoms (the
        caller loops)."""
        todo, self._mono_todo = self._mono_todo, []
        n = len(self.session.table.custom)
        apps = self._mono_apps
        ad = self._mono_ad
        link_of, aux = self._link_of, self._aux_eq
        for atom, var in todo:
            terms = ad.terms(sympy_atom(atom)) or ()
            for t in terms:
                self._mono_term(t)
            if apps and atom not in link_of and atom not in aux:
                for t in terms:
                    if t in apps:
                        self._mono_open(t)
            if atom.pred == "lt":
                a, b = atom.expr
                if not _is_number(a) and not _is_number(b):
                    self._mono_pairs.append((var, a, b))
                    self._mono_pair(var, a, b)
            elif atom.pred == "eq" and len(terms) == 1 and terms[0] in apps:
                self._mono_eq(atom, var, terms[0])
        return len(self.session.table.custom) != n

    def _mono_eq(self, atom, var: int, app) -> None:
        """``a*f(u) + b = 0`` (``a``, ``b`` real constants, ``a != 0``)
        makes ``f(u)`` real: ``~MO(f(u)) | ~atom | real(f(u))``.  The atom
        asserts no realness of its sides as an order atom does, and the
        link of ``f(u)`` needs it (``log(x) = 1`` then gives ``x = E``)."""
        form = self._mono_ad.integer_form(atom.expr[0] - atom.expr[1])
        if form is None or len(form[1]) != 1:
            return
        s = self.session
        s.ensure(app, {"real"})
        s.emit([-self._tvar(app, _MO), -var, s.var("real", app)])

    def _mono_term(self, t) -> None:
        """Register ``t`` if it is an application of a listed function
        (once per term)."""
        if t in self._mono_seen:
            return
        self._mono_seen.add(t)
        from .theories.mono import spec
        sp = spec(t)
        if sp is not None:
            self._mono_apps[t] = sp
            self._mono_app(t, sp)

    def _mono_app(self, app, sp) -> None:
        """A new application ``f(u)``: its ``MO`` switch (implied by its
        link selector, and implying those of the terms of ``u``), the LRA
        link of ``f(u)`` to the linear form of ``u`` (:meth:`_mono_link`),
        the applications among the terms of ``u`` (``exp(x)`` in
        ``log(exp(x) + 1)``), its rows and its pairs."""
        mo = self._tvar(app, _MO)
        self._tsource(app, _MO, [-self._tvar(app, _IL)])
        u = sp.arg
        form = self._mono_ad.integer_form(u)
        if form is not None:
            for t in form[1]:
                self._tsource(t, _MO, [-mo])
            for t in form[1]:
                self._mono_term(t)
                self._mono_open(t)
        if app in self._mono_opened:
            self._mono_rows(app, sp)
        if sp.pieces:
            self._mono_by_arg.setdefault(u, []).append(app)
            if form is not None and form[0].terms and all(
                    type(c) is Fraction for _t, c in form[0].terms):
                self._mono_link(app, mo, form)
        for var, a, b in self._mono_pairs:
            if a == u or b == u or a == app or b == app:
                self._mono_pair(var, a, b)

    def _mono_link(self, app, mo: int, form) -> None:
        """Register the LRA link ``app = f(u)`` (``form`` the integer form
        of ``u``) on a fresh inert *enable* variable ``e``: ``e <-> MO(app)
        & real(app) & real(s)`` for the opaque terms ``s`` of ``u``.  While
        ``e`` holds (``real(s)`` is left out where ``real(app)`` implies
        it: ``Spec.real_arg``), the LRA values of ``app`` and of ``u``'s terms are
        their values, so LRA may derive bounds of ``app`` from those of
        ``u`` and back (``lra.LRATheory._mono_link``), each with ``e`` in
        its reason: no atom and no clause per threshold."""
        from .theories.mono import link_map
        fm = link_map(app)
        if fm is None:
            return
        s = self.session
        ad = self._mono_ad
        sp = self._mono_apps[app]
        terms = form[1]
        if sp.real_arg and len(terms) == 1:
            # real(f(u)) gives real(u), u = a*s + b: real(s)
            ga = self._guard(ad, [app])
            if ga:
                s.ensure(terms[0], {"real"})
                s.emit([-mo, ga[0], s.var("real", terms[0])])
            terms = ()
        guard = self._guard(ad, list(terms) + [app])
        e = self._fresh(inert=True)
        s.emit([-e, mo])
        for g in guard:
            s.emit([-e, -g])
        s.emit([e, -mo] + guard)
        ad.register_mono(s.solver, e, app, form, fm)
        if fm.covered:
            return
        u = sp.arg
        for i, piece in enumerate(sp.pieces):
            if piece.lo == "-oo" and piece.hi == "oo":
                continue
            # p <-> e & (u in the piece): the sign of u places it there
            g = self._mono_guard(u, piece.guard())
            pe = self._fresh(inert=True)
            s.emit([-pe, e])
            for x in g:
                s.emit([-pe, -x])
            s.emit([pe, -e] + g)
            ad.register_mono_piece(s.solver, pe, e, i)

    def _mono_open(self, t) -> None:
        """Switch on the sandwich rows of the application ``t`` (``Abs``,
        ``floor``, ``ceiling``; now, or when it is registered): wanted where
        something other than a sign link reads ``t`` (an atom, or the
        argument of an application).  A sign link (``0 < floor(u)`` of
        ``Q.positive(floor(u))``) gets the templates' facts; on the refine
        stream these links made most of the rows and decided nothing."""
        if t in self._mono_opened:
            return
        self._mono_opened.add(t)
        sp = self._mono_apps.get(t)
        if sp is not None:
            self._mono_rows(t, sp)

    def _mono_rows(self, app, sp) -> None:
        """Emit the rows of ``app`` (guarded by its ``MO`` switch)."""
        u = sp.arg
        g = [-self._tvar(app, _MO)]
        for row in sp.rows:
            f = relation_atom("lt", row.lhs(u, app), row.rhs(u, app))
            v = self._mono_var(f)
            self.session.emit(self._mono_guard(u, _mono_guards(row.guard)) + g
                              + [v if row.positive else -v])

    def _mono_var(self, f, made=None) -> int:
        """The variable of a relation atom the rows or pairs need (made if
        new, and then recorded as ``made``: ``_mono_made``)."""
        v = self.session.table.custom.get(f)
        if v is None:
            if f.pred == "eq":
                self._aux_eq.add(f)
            v = self._atom_var(f)
            if made is not None:
                self._mono_made[v] = made
        return v

    def _mono_guard(self, e, lits) -> list:
        """The negations of the basis literals ``lits`` of ``e``."""
        s = self.session
        if not lits:
            return []
        s.ensure(e, {p for p, _ in lits})
        return [-s.var(p, e) if pos else s.var(p, e) for p, pos in lits]

    def _mono_pair(self, var: int, a, b) -> None:
        """``a < b`` (``var``): with ``f(a)`` and ``f(b)`` applications of
        one listed function, the lemmas of each piece between ``var`` and
        the atom comparing ``f(a)`` and ``f(b)``; with ``a = f(x)`` and
        ``b = f(y)`` and ``f`` increasing on the whole line, between
        ``var`` and the atom ``x < y`` (made)."""
        apps, by_arg = self._mono_apps, self._mono_by_arg
        for fa in by_arg.get(a, ()):
            for fb in by_arg.get(b, ()):
                spa, spb = apps[fa], apps[fb]
                if spa.family != spb.family:
                    continue
                key = ("p", var, fa, fb)
                if key in self._mono_done:
                    continue
                self._mono_done.add(key)
                for piece in spa.pieces:
                    f = (relation_atom("lt", fa, fb) if piece.dir > 0
                         else relation_atom("lt", fb, fa))
                    self._mono_pair_lemmas(piece, var, self._mono_var(f, ("f", None)),
                                           a, b, fa, fb)
        spa, spb = apps.get(a), apps.get(b)
        if (spa is not None and spb is not None and spa.family == spb.family
                and self._mono_made.get(var, ("",))[0] != "f"
                and len(spa.pieces) == 1 and spa.pieces[0][:2] == ("-oo", "oo")):
            key = ("q", var)
            if key not in self._mono_done:
                self._mono_done.add(key)
                piece = spa.pieces[0]
                if piece.dir < 0:         # f(a) < f(b) iff b's argument is below
                    a, b, spa, spb = b, a, spb, spa
                p = self._mono_var(relation_atom("lt", spa.arg, spb.arg), ("i", None))
                self._mono_pair_lemmas(piece, p, var, spa.arg, spb.arg, a, b)

    def _mono_pair_lemmas(self, piece, p: int, q: int, a, b, fa, fb) -> None:
        """``p`` is ``a < b``, ``q`` the atom of ``f(a)``, ``f(b)`` in the
        same order on ``piece``: ``p & G -> q``, ``q & G -> p`` with the
        piece's guard on both arguments.  In the first clause ``a < b``
        puts ``b`` in a piece up to ``oo`` once ``a`` is in it, and ``a``
        in a piece from ``-oo`` once ``b`` is: one guard does there, none
        on the whole line (the atom says both are extended reals)."""
        gl = piece.guard()
        ga, gb = self._mono_guard(a, gl), self._mono_guard(b, gl)
        mo = [-self._tvar(fa, _MO), -self._tvar(fb, _MO)]
        emit = self.session.emit
        up, down = piece.hi == "oo", piece.lo == "-oo"
        fwd = [] if up and down else ga if up else gb if down else ga + gb
        emit([-p, q] + fwd + mo)
        emit([-q, p] + ga + gb + mo)

    # -- links to the unary vocabulary ----------------------------------
    def _atom_var(self, f) -> int:
        """Variable of a normalised relation atom (allocated if new; its
        interpretation is queued by the session)."""
        return self.session.table.var(f)

    def _link(self, e) -> None:
        from sympy import S
        s = self.session
        s.ensure(e, {"extended_positive", "extended_negative", "zero"})
        pos, neg = s.var("extended_positive", e), s.var("extended_negative", e)
        zero = s.var("zero", e)
        gta, lta = relation_atom("lt", S.Zero, e), relation_atom("lt", e, S.Zero)
        self._link_lt[gta] = self._link_lt[lta] = e
        gt = self._atom_var(gta)
        lt = self._atom_var(lta)
        eqa = relation_atom("eq", e, S.Zero)
        if eqa not in self.session.table.custom:
            self._aux_eq.add(eqa)
            self._link_eq.add(eqa)
        eq = self._atom_var(eqa)
        sel = self.link_sel[e] = self._fresh(inert=True)
        g = -sel
        gl = [g]            # one guard object: _tsource drops repeats of it
        for f in (gta, lta, eqa):
            self._link_of[f] = e
            self._add_role(f, gl, "link")
        emit = s.emit
        emit([-pos, gt, g])
        emit([-gt, pos, g])
        emit([-neg, lt, g])
        emit([-lt, neg, g])
        emit([-zero, eq, g])
        emit([-eq, zero, g])
        if INTEGERS:
            for spec in self.specs:
                if spec.guarded:
                    ad = self._adapter(spec)
                    if hasattr(ad, "integer_form"):
                        self._link_integer(ad, e, g)

    # -- switched glue: what a query activates ----------------------------
    def wants_transfer(self, atoms) -> bool:
        """Predicate transfer acts in a query whose relation atoms
        (``atoms``, of the proposition and the assumptions) make an
        equality: an ``eq`` atom (``ne`` is its negation), or an order atom
        and its reverse that :meth:`_trichotomy` related (``Q.le(x, y) &
        Q.ge(x, y)`` answers as ``Q.eq(x, y)``, W2B4b).  The same atoms
        engage it at the session's construction
        (:func:`satassume.theories.transfer.transfer_wanted`, the same syntactic test),
        so a fresh session has it exactly then; a function of the atoms."""
        return transfer_wanted(atoms)

    def selectors_of(self, atoms) -> list:
        """The selectors a formula whose atoms are ``atoms`` activates once
        links are on: those of the links of its terms and of its relation
        atoms' clauses to unary atoms, in allocation order."""
        sel, nsel, status = self.link_sel, self.num_sel, self.status
        out = set()
        asel = self.atom_sel
        for a in atoms:
            if a.pred in PRED_INDEX:
                e = a.expr
                if e in sel:
                    out.add(sel[e])
                elif e in nsel:
                    out.add(nsel[e])
            elif a.pred in RELATION_ATOMS:
                if status.get(a):
                    # the sides of an opaque relation are not linked (see
                    # process): neither are they here
                    out.update(sel[e] for e in a.expr if e in sel)
                if a in asel:
                    out.add(asel[a])
        return sorted(out)

    # -- equality sharing -------------------------------------------------
    #
    # Interface equalities grow with the session (EqualitySharing.update
    # returns the new pairs only), and an interface atom eq(a, b) is shared
    # by two theories: an unswitched one is a bridge, through which an
    # equality LRA derives from the current query's bounds reaches EUF (and
    # transfer) for a pair a fresh session does not have, because one of
    # the terms is known to one theory only through an atom of an earlier
    # query.  So its twin is switched by the role "iface" (_apply_role),
    # whose guard holds iff both terms are shared in a fresh session for
    # the current query: IL(u) & IE(u) for u = a, b (_tvar), implied by the
    # selector of every link whose LRA atoms, whose eq(e, 0), read u.  That
    # is exact: in a fresh session every LRA atom of a user relation, of
    # _trichotomy and of an interface equality has the terms of the link
    # atoms of its sides (each side is linked, and its linear form is the
    # sum of theirs), and every equality EUF reads has the terms of the
    # links' eq(e, 0) of its sides (numbers aside, which are never paired);
    # so the shared terms of a fresh session are those of its links, the
    # links L(p, a) the query activates.  (Relation atoms an extension
    # makes have no role: their terms count only where a link has them,
    # in a fresh session too.)  The atom itself stays a variable EUF reads:
    # with its twins off, a free one (I3: an EUF equality not forced by the
    # asserted ones is false in the extending model, a forced one changes
    # no class).
    #
    # Transfer candidacy (_xside, _xcand) grows with the session too, and
    # it is not harmless: a term of the current query that an earlier
    # equality made a side (or an earlier node made a congruent
    # application) would take every fact of its class, where a fresh
    # session gives a link-only side polar alone and leaves an application
    # without a partner out.  So every candidate but a rational number
    # takes part only as its _EN/_SD variables say (TransferTheory.switch,
    # sync_transfer): the candidacy rule applied to the atoms and terms the
    # query activates.
    def _share(self) -> bool:
        if len(self.adapters) < 2:
            return False
        sets = [set(ad.shared_terms()) for ad in self.adapters.values()]
        pairs = self.sharing.update(sets)
        for a, b in pairs:
            if _is_number(a) and _is_number(b):
                continue
            if _constant_term(a) or _constant_term(b):
                continue
            eqa = relation_atom("eq", a, b)
            if eqa not in self.session.table.custom:
                self._aux_eq.add(eqa)
            self._atom_var(eqa)
            self._add_role(eqa, self._share_guard(a) + self._share_guard(b), "iface")
        return bool(pairs)

    def _share_guard(self, u) -> list:
        """``[-in_lra(u), -in_euf(u)]``: ``in_lra(u)`` is implied by the
        selector of every link whose LRA atoms have the term ``u``,
        ``in_euf(u)`` by that of every link whose ``eq(e, 0)`` EUF reads
        with ``u`` among its terms (``EUFAdapter.interned``)."""
        return [-self._tvar(u, _IL), -self._tvar(u, _IE)]

    # -- predicate transfer (satassume.theories.transfer) -------------------------
    #
    # Engaged once per session, at construction, when the scope of the
    # session's query makes an equality (satassume.scope, ``transfer``);
    # the glue's own equalities (the links' eq(e, 0), the interface
    # equalities) and those templates or extensions make never engage it.
    # ``_want_transfer`` remains for a user equality outside the scope (a
    # session built for a set alone and then asked an equality: counted
    # as a scope miss by ``process``).
    # Engaging attaches the EUF adapter's theory (if not yet) and a
    # TransferTheory; from then on every node block of the session is
    # registered with it (its expression interned as an EUF term, so
    # congruence applies to it), and every expression EUF interns for an
    # atom is visited as a node (so x = 2 finds the facts of 2).

    _want_transfer = False

    def _congruent(self, node) -> bool:
        """``node`` may become congruent to another known application of
        the same head: argument by argument, the two are the same
        expression or both may be merged (a side or a candidate, and not
        two distinct Rationals: EUF keeps those apart, but a Float or an
        irrational number is an opaque term that may equal a Rational or
        another spelling of the same value), and at least one pair
        differs."""
        others = self._xheads.get((node.func, len(node.args)))
        if not others or len(others) < 2 or (
                self._xadapter.term_of(node) is None and node not in self.num_sel):
            return False
        cand, xside = self._xcand, self._xside
        args = node.args
        for o in others:
            if o is node or o == node:
                continue
            differ = False
            for a, b in zip(args, o.args):
                if a == b:
                    continue
                if not ((a in cand or a in xside) and (b in cand or b in xside)) \
                        or (a.is_Rational and b.is_Rational):
                    break
                differ = True
            else:
                if differ:
                    return True
        return False

    def _note_sides(self, atom, level) -> None:
        xs = self._xside
        for e in atom.expr:
            lv = 2 if _is_number(e) else level
            if xs.get(e, 0) < lv:
                xs[e] = lv
                self._xsides_n += 1

    def _engage_transfer(self) -> None:
        s = self.session
        if not s.engine.transfer:
            return
        ad = None
        for spec in self.specs:
            if not spec.guarded:
                a = self._adapter(spec)
                if hasattr(a, "node_term"):
                    ad = a
                    break
        if ad is None:
            return
        from .theories.transfer import TransferTheory
        solver = s.solver
        ad.attach(solver)
        th = TransferTheory(ad.theory)
        solver.attach_theory(th)
        # every lemma is guarded by a selector the queries with a relation
        # atom assume (Session.assumption_lits); registered as the
        # theory's atom, so the theory follows its value level by level
        sel = self._fresh(inert=True)
        th.guard(sel)
        solver.register_atom(th, sel, ("enable",))
        self.xfer_sel = sel
        self._xadapter = ad
        self.xfer = th
        s.xfer = self

    def _transfer_terms(self) -> bool:
        """Visit the sides of the atoms EUF registered since the last call
        (numbers included), and the structural terms EUF reads that share
        their head with another one (the possible congruent candidates of
        ``sync_transfer``, so that a fresh session has their nodes too);
        True if a node was visited."""
        from itertools import islice
        from sympy import Basic, Expr, Rational
        from .theories.euf.euf_adapter import structural
        s = self.session
        ad, th = self._xadapter, self.xfer
        visited = False
        sides = self._xside
        n = len(sides)
        if self._xterm < n:
            new = list(islice(sides, self._xterm, n))
            self._xterm = n
            for e in new:
                if isinstance(e, Rational):
                    # a rational's facts are closed and context-free: the
                    # theory holds a basis of them for its term instead of a
                    # node (no visit, no variables, no change to the
                    # session's search)
                    t = ad.term_of(e)
                    if t is not None:
                        th.set_fixed(t, _number_facts(s.engine, e))
                    continue
                if isinstance(e, Expr) and e not in s.base:
                    s.ensure(e)
                    visited = True
        new = ad.terms_since(self._xtcur)
        extra = self._xextra
        if new or extra:
            self._xtcur += len(new)
            if extra:
                new.extend(extra)
                extra.clear()
            heads, counted = self._xheads, self._xcounted
            grown = {}
            for e in new:
                if e not in counted and isinstance(e, Basic) and structural(e):
                    counted.add(e)
                    k = (e.func, len(e.args))
                    h = heads.get(k)
                    if h is None:
                        heads[k] = [e]
                    else:
                        h.append(e)
                        grown[k] = None
            if grown:
                self._xhn += 1
                base = s.base
                for k in grown:
                    for e in heads[k]:
                        if isinstance(e, Expr) and e not in base:
                            s.ensure(e)
                            visited = True
        return visited

    def sync_transfer(self) -> None:
        """Register with the transfer theory the predicate variables of the
        nodes whose terms EUF could put into a class with another term, and
        hand it their enable variables (``TransferTheory.switch``).

        A term joins a class only through a union: as the side of an atom,
        or as an application congruent to another one with the same head
        (function and arity) whose arguments were merged.  So a node is a
        *candidate* (all ``NPRED`` = 14 basis variables registered) iff it is a side of a user,
        :meth:`_trichotomy` or extension equality atom, a number side, or a
        term EUF reads (:meth:`_transfer_terms` visits those) whose head
        occurs on another term EUF reads, the arguments of the two being
        the same or sides or candidates, not two rationals.  Two kinds of
        sides are left out on purpose:

        * a side ``e`` only of the link ``eq(e, 0)``: ``e`` joins the class
          of ``0`` only when that atom holds, and then the link clause makes
          ``zero(e)`` true, from which the rule base decides every predicate
          but ``polar`` exactly as the facts of the number ``0`` (itself a
          candidate) do; so only ``polar`` is registered for ``e``;
        * a side only of interface equalities (equality sharing): those are
          how equalities LRA derives reach EUF, which transfer leaves out.

        That is what a session registers; which candidates take part in a
        query is the same rule applied to the atoms that query activates
        (see "Switched glue"): every candidate but a rational number is
        switched by its ``_EN`` (all predicates) and ``_SD`` (``polar``)
        variables (:meth:`_tvar`), set by the roles of the atoms
        (:meth:`_apply_role`) and, for congruence, by the clauses of
        :meth:`_congruence_pairs`.  A rational's facts are closed: it
        always takes part (it joins a class only through an equality the
        query activates).

        Candidacy only grows, so the nodes not (fully) registered are kept
        and looked at again on the next call.  This runs at root-safe points
        (the end of :meth:`process`, the start of ``Session.query_literal``).
        """
        s = self.session
        slots = s.table.slots
        xside = self._xside
        i, n = self._xslot, len(slots)
        nside = self._xsides_n
        if i >= n and nside == self._xnsides and self._xhn == self._xhseen:
            return
        from sympy import Basic, Rational, nan
        from .theories.euf.euf_adapter import structural
        pend = self._xpend
        while i < n:
            e = slots[i]
            if type(e) is tuple and e[1] == i:
                node = e[0]
                if isinstance(node, Basic) and not node.has(nan):
                    pend.append((node, i))
                i += NPRED
            else:
                i += 1
        self._xslot = n
        self._xnsides = nside
        self._xhseen = self._xhn
        cand = self._xcand
        part = self._xpart
        ad = self._xadapter
        solver, th = s.solver, self.xfer
        polar = BASIS_INDEX["polar"]
        changed = True
        while changed and pend:
            changed = False
            keep = []
            for node, b in pend:
                lv = xside.get(node, 0)
                if lv == 2 or (structural(node) and self._congruent(node)):
                    cand.add(node)
                    changed = True
                    t = ad.node_term(node)
                    solver.ensure_vars(b + NPRED - 1)     # one _grow, not NPRED
                    rational = isinstance(node, Rational)
                    if rational:
                        preds = _number_basis(s.engine, node)
                        full = len(preds) == NPRED
                    else:
                        preds = range(NPRED)
                        full = True
                    for k in preds:
                        if k != polar or node not in part:
                            solver.register_atom(
                                th, b + k, (t, k) if full else (t, k, True), False)
                    if not rational:
                        self._xswitch(node, t)
                    continue
                if lv == 1 and node not in part:
                    part.add(node)
                    t = ad.node_term(node)
                    solver.register_atom(th, b + polar, (t, polar, True), False)
                    self._xswitch(node, t)
                keep.append((node, b))
            pend[:] = keep
        self._congruence_pairs()

    def _xswitch(self, node, t: int) -> None:
        """Hand the transfer theory the enable variables of candidate
        ``node`` (term ``t``), registered as its atoms."""
        solver, th = self.session.solver, self.xfer
        for v in th.switch(t, self._tvar(node, _EN), self._tvar(node, _SD)):
            solver.register_atom(th, v, ("on",))

    def _congruence_pairs(self) -> None:
        """For two terms ``F``, ``G`` EUF reads with one head, whose
        differing arguments may all be merged (see ``sync_transfer``):

            IE(F) & IE(G) & MC(x) & MC(y) ... -> EN(F)   (and EN(G))

        over the differing argument pairs ``(x, y)`` (:meth:`_tvar`): the
        rule of ``sync_transfer`` for congruent candidates, restricted to
        the terms and sides the query activates.  A pair whose arguments
        cannot be merged yet is looked at again on a later call."""
        xside, cand, done = self._xside, self._xcand, self._xpairs
        emit = self.session.emit
        tvar = self._tvar
        for group in self._xheads.values():
            if len(group) < 2:
                continue
            for j in range(1, len(group)):
                G = group[j]
                for F in group[:j]:
                    key = (F, G)
                    if key in done:
                        continue
                    diff = []
                    ok = True
                    for x, y in zip(F.args, G.args):
                        if x == y:
                            continue
                        if x.is_Rational and y.is_Rational:
                            ok = None
                            break
                        if not ((x in cand or x in xside) and (y in cand or y in xside)):
                            ok = False
                            break
                        diff.append((x, y))
                    if ok is None or (ok and diff):
                        done.add(key)
                    if not ok or not diff:
                        continue
                    body = [-tvar(F, _IE), -tvar(G, _IE)]
                    for x, y in diff:
                        body.append(-tvar(x, _MC))
                        body.append(-tvar(y, _MC))
                    emit(body + [tvar(F, _EN)])
                    emit(body + [tvar(G, _EN)])


# --------------------------------------------------------------------------
# what the glue can visit: the structural weight of relation atoms
# --------------------------------------------------------------------------
#
# ``Engine._struct`` (the discovery budget's test on a query's structural
# cone, ``Engine._cone_info``) asks these for the nodes the glue of a
# session can visit beyond the templates: a relation atom's sides (clauses
# 1, ``_eq_infinity``, ``_transfer_terms``), the differences of
# ``_eq_links``, the opaque terms its guarded adapters read (clauses 2 and
# 3, ``_guard``, ``_order_infinite``), and, for every side and every
# vocabulary argument of a user formula once the glue runs, the link
# ``_link(e)``: ``e``, the terms of its linear form (``_link_integer``
# and the link atoms ``0 < e``, ``e < 0``, ``e = 0``) and the structural
# subterms EUF reads from ``eq(e, 0)`` (``_transfer_terms`` visits those
# that share a head with another term EUF reads).  Interface
# equalities (``_share``) are between terms the adapters already read, and
# their guards are those terms again.  An over-estimate is harmless (a
# query just over the budget answers None); keep these in step with the
# glue above.


def _guarded_adapters(specs, memo: dict) -> list:
    """One adapter per guarded spec, used only to read linear forms (it
    never registers anything); kept in ``memo`` by spec name."""
    out = []
    for spec in specs:
        if spec.guarded:
            ad = memo.get(spec.name)
            if ad is None:
                ad = memo[spec.name] = spec.factory()
            out.append(ad)
    return out


def _terms_of(ad, sat, order: bool) -> set:
    k = set()
    if order and hasattr(ad, "order_sides"):
        sides = ad.order_sides(sat)
        if sides is not None:
            for form, _inf in sides:
                k.update(form)
    terms = ad.terms(sat)
    if terms:
        k.update(terms)
    return k


def _structural_subterms(e) -> list:
    """The structural proper subterms of ``e`` EUF interns for it
    (``EUFAdapter.interned``): ``_transfer_terms`` may visit them, once
    ``eq(e, 0)`` is read by EUF and another term shares their head."""
    try:
        from .theories.euf.euf_adapter import structural
    except ImportError:         # no EUF adapter: nothing is visited for it
        return []
    from sympy import Basic, Rational
    out, seen = [], set()
    stack = list(e.args) if isinstance(e, Basic) and structural(e) else []
    while stack:
        x = stack.pop()
        if x in seen or isinstance(x, Rational) or not isinstance(x, Basic) \
                or not structural(x):
            continue
        seen.add(x)
        out.append(x)
        stack.extend(x.args)
    return out


def link_objects(e, specs, memo: dict) -> set:
    """The nodes ``Relations._link(e)`` can visit: ``e``, the opaque terms
    of its linear form in every guarded adapter (numbers included,
    conservatively: ``_guard`` skips a constant real at the root), and the
    structural subterms EUF reads (:func:`_structural_subterms`)."""
    k = {e}
    if _is_number(e):
        return k
    k.update(_structural_subterms(e))
    try:
        from sympy import S
        for ad in _guarded_adapters(specs, memo):
            if INTEGERS and hasattr(ad, "integer_form"):
                form = ad.integer_form(e)
                if form is not None:
                    k.update(form[1])
            for atom in (relation_atom("lt", S.Zero, e), relation_atom("lt", e, S.Zero),
                         relation_atom("eq", e, S.Zero)):
                k.update(_terms_of(ad, sympy_atom(atom), atom.pred == "lt"))
    except Exception:       # noqa: BLE001 (a side the adapters cannot read)
        pass
    return k


def glue_objects(atom: P, specs, memo: dict) -> set:
    """The nodes the glue of the relation atom ``atom`` can visit (see
    above), the atom itself excluded."""
    k = set()
    sides = tuple(atom.expr)
    for e in sides:
        k.add(e)
        if not _is_number(e):
            k.update(link_objects(e, specs, memo))
    if atom.pred == "eq" and len(sides) == 2:
        a, b = sides
        if not (_is_number(a) or _is_number(b)):
            for p, q in ((a, b), (b, a)):
                try:
                    d = p - q
                    if not _is_number(d) and _termwise(p, q, d):
                        k.add(d)
                except Exception:   # noqa: BLE001 (sides that do not subtract)
                    pass
    if specs:
        try:
            sat = sympy_atom(atom)
            for ad in _guarded_adapters(specs, memo):
                k.update(_terms_of(ad, sat, atom.pred == "lt"))
        except Exception:   # noqa: BLE001 (sides the adapters cannot read)
            pass
    k.discard(atom)
    return k
