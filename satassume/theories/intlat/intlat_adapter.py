"""Session nodes onto :class:`.intlat.IntLatTheory` (issue #149, T2).

A *linear node* is a sum, or a product whose first factor is a nonzero
Rational (``c*t``, ``-x``, ``x/2``): :func:`owns`.  Its form is read
through linear nodes down to the first non-linear subterms, the *terms*
(``x``, ``x*y``, ``sin(x)``, ``pi``, ``2.0``); a Rational is a constant
of the form.  The theory gets, for every linear node a session visits
and for each of its terms, the node's ``integer`` and ``even`` basis
variables as atoms: ``integer(e)`` is the form of ``e`` integral,
``even(e)`` the form of ``e/2`` (``zero`` is even, ``odd`` is ``integer &
!even``, ``rules.DEFINITIONS``).

The product ``t`` of the factors after the coefficient of ``c*x*y`` is a
node of its own (``x*y``, visited here), so the form of ``c*x*y`` is
``c*t``.  A number other than a Rational is a term like any other: the
session knows its predicates (``integer(pi)`` is false at the root), and
a Float is the number it denotes (``2.0 - 2`` evaluates to the Integer
0), as in the templates.  A product of three or more factors is linear
only if the product of the factors after its coefficient, built, keeps
those factors (:func:`linear`); otherwise it is a term.
"""
from __future__ import annotations

from fractions import Fraction

from ...knowledge.rules import BASIS_INDEX
from .intlat import CONST, IntLatTheory, Poly

_INT = BASIS_INDEX["integer"]
_EVEN = BASIS_INDEX["even"]
_DEMANDED = frozenset((_INT, _EVEN))
_HALF = Fraction(1, 2)
_ONE = Fraction(1)
#: ``templates.core.MAX_ADD_SMALL`` (that module loads SymPy; the test of
#: ownership checks the two agree)
MAX_ADD_SMALL = 3
#: a product term with more base terms is not read as a product
MAX_BASES = 3


def linear(node) -> bool:
    """Whether ``node`` is a linear node (a sum, or ``c*t`` with a nonzero
    Rational ``c``): the adapter reads its form through it."""
    if getattr(node, "is_Add", False):
        return bool(node.args)
    if getattr(node, "is_Mul", False):
        args = node.args
        if not (len(args) >= 2 and args[0].is_Rational and not args[0].is_zero):
            return False
        # c*t reads t as the product of the other factors: only if that
        # product, built, is those factors (an unevaluated
        # Mul(1/3, x, 3/x) or Mul(1/3, x, 0) would read as 1 or
        # 0, but is nan at x = 0 or oo); the guard of
        # templates.core._mul_factor_sets
        if len(args) == 2:
            return True
        t = _rest(node)
        return t.func is node.func and t.args == args[1:]
    return False


def _rest(node):
    """The product of the factors of node after the first."""
    rest = node.args[1:]
    return rest[0] if len(rest) == 1 else node.func(*rest)


def _fractional(a) -> bool:
    """Whether the summand ``a`` is a non-integer Rational or has one as
    its coefficient (``x/2``, ``2*x/3``)."""
    if a.is_Rational:
        return a.q != 1
    if a.is_Mul:
        c = a.args[0]
        return bool(c.is_Rational) and c.q != 1
    return False


def owns(node) -> bool:
    """Whether a session tells the theory ``node``: a sum of more than
    ``MAX_ADD_SMALL`` terms (the templates enumerate parities up to that
    arity) or with a non-integer coefficient, and a product whose
    coefficient is a non-integer Rational.  The templates have no
    integrality or parity rows of their own for those (no half-integer
    split of a sum, no ``coeff.half`` row of ``x/2``, no even closure of a
    long sum): the theory decides them for any arity and any rational
    coefficients.  The linear nodes inside an owned node's form are told
    too (:meth:`IntLatAdapter.form`)."""
    if node.is_Add:
        args = node.args
        return len(args) > MAX_ADD_SMALL or any(
            _fractional(a) for a in args if not a.is_Rational)
    if node.is_Mul:
        c = node.args[0]
        return bool(c.is_Rational) and c.q > 2 and linear(node)
    return False


def _factors(e, k: int, out: list) -> bool:
    """Append ``(kind, factor, power)`` for the factors of ``e**k``: ``e``
    read through products (the value of a product, evaluated or not, is
    the product of its arguments' values) and powers with a positive
    Integer exponent, down to Rationals (``'q'``), linear nodes
    (``'lin'``, read only if their form is exact) and terms (``'t'``).
    False if a factor is something else (a number that is not a
    Rational: a Float, ``pi``, ``I``; a negative or symbolic power)."""
    if e.is_Rational:
        out.append(('q', e, k))
        return True
    if e.is_number:
        return False
    if e.is_Pow:
        b, x = e.args
        if not (x.is_Integer and x > 0):
            return False
        return _factors(b, k * int(x), out)
    if linear(e):
        out.append(('lin', e, k))
        return True
    if e.is_Mul:
        return all(_factors(a, k, out) for a in e.args)
    out.append(('t', e, k))
    return True


def _rat(c) -> Fraction:
    return Fraction(int(c.p), int(c.q))


def coeff_rest(node):
    """``(c, t)`` for a linear product ``c*t``: ``t`` the product of the
    other factors (one factor: that factor itself), whose arguments are
    those factors (:func:`linear`)."""
    return node.args[0], _rest(node)


class IntLatAdapter:
    """The theory of one session and the linear nodes it was told."""

    def __init__(self, session):
        self.session = session
        self.theory = IntLatTheory()
        self.attached = False   # attached at the first node told
        self.terms = {}         # term -> column
        self.forms = {}         # linear node -> its form
        self.done = set()       # nodes whose atoms are registered
        self.parked = []        # owned nodes not wanted yet (:meth:`wanted`)

    # -- the engine's node-theory protocol (Session.node_theories_sync) ----
    @staticmethod
    def kinds(cls: type) -> bool:
        return bool(getattr(cls, "is_Add", False) or getattr(cls, "is_Mul", False))

    @staticmethod
    def over_cap(node) -> bool:
        return owns(node)

    @staticmethod
    def selects(node) -> bool:
        return owns(node)

    def sync_derived(self) -> bool:
        """Tell the parked nodes that are wanted now; True iff one was."""
        parked = self.parked
        if not parked:
            return False
        self.parked = []
        told = False
        for n in parked:
            if self.wanted(n):
                self.tell(n)
                told = True
            else:
                self.parked.append(n)
        return told

    def wanted(self, node) -> bool:
        """Whether the session needs ``node``'s integrality: as the
        templates' demand-driven compilation (``Session.node``), which
        parks a pattern clause until it mentions a demanded predicate of
        its node or the session escalates.  The rows the theory replaces
        mention the node's ``integer`` or ``even``: so the theory is told
        the node once one of those is demanded of it, or once nothing is
        parked any more (after an escalation; ref.py's session compiles
        everything)."""
        s = self.session
        demand = getattr(s, "demand", None)
        if demand is None or not s.incomplete:
            return True
        d = demand.get(node)
        return d is not None and (_INT in d or _EVEN in d)

    # -- forms ---------------------------------------------------------------
    def form(self, e):
        """The form of ``e`` (dict column -> Fraction, the constant at
        :data:`CONST`); registers the atoms of every term on the way."""
        f = self.forms.get(e)
        if f is not None:
            return f
        acc: dict = {}
        if e.is_Add:
            for a in e.args:
                self._lin(a, _ONE, acc)
        else:
            k, t = coeff_rest(e)
            self._lin(t, _rat(k), acc)
        g = {k: x for k, x in acc.items() if x}
        # a term whose coefficients cancel (``x + 2*(y - x/2)`` built
        # unevaluated) still makes ``e`` infinite or nan when it is: the
        # form is exact only if it keeps every term
        exact = all(k in g for k in acc if k != CONST)
        f = self.forms[e] = (g, exact)
        return f

    def _lin(self, e, c: Fraction, acc: dict) -> None:
        if e.is_Rational:
            acc[CONST] = acc.get(CONST, 0) + c * _rat(e)
            return
        if linear(e):
            f = self.form(e)
            self._register(e, f)
            g, exact = f
            if not exact:
                # read through the node's arguments, so that the
                # cancelled terms stay in the outer form's term set
                if e.is_Add:
                    for a in e.args:
                        self._lin(a, c, acc)
                else:
                    k, t = coeff_rest(e)
                    self._lin(t, c * _rat(k), acc)
                return
            for k, x in g.items():
                acc[k] = acc.get(k, 0) + c * x
            return
        col = self.term(e)
        acc[col] = acc.get(col, 0) + c

    def term(self, e) -> int:
        col = self.terms.get(e)
        if col is None:
            col = self.terms[e] = len(self.terms)
            self._register(e, ({col: Fraction(1)}, True))
            self._define(e, col)
        return col

    def _define(self, e, col: int) -> None:
        """Tell the theory the term ``e`` (column ``col``) as a product of
        integral forms, if it is one (:class:`.intlat.Poly`)."""
        if not (getattr(e, "is_Mul", False) or getattr(e, "is_Pow", False)):
            return
        if not e.is_commutative:
            return
        parts: list = []
        if not _factors(e, 1, parts):
            return
        # registered only once the whole product reads (a rejected
        # product adds no atoms)
        facs: list = []
        for kind, a, k in parts:
            if kind == 'q':
                facs.append(({CONST: _rat(a)}, k))
            elif kind == 'lin':
                f, exact = self.form(a)
                if not exact:
                    return
                facs.append((f, k))
            else:
                facs.append(({self.term(a): _ONE}, k))
        bases = sorted({k for f, _ in facs for k in f if k != CONST})
        if not bases or len(bases) > MAX_BASES:
            return
        factors = []
        for f, k in facs:
            if any(x.denominator != 1 for x in f.values()):
                return
            factors.append((tuple(int(f.get(b, 0)) for b in bases),
                            int(f.get(CONST, 0)), k))
        self.theory.define_poly(Poly(col, tuple(bases), factors))

    def _register(self, e, fe) -> None:
        if e in self.done:
            return
        self.done.add(e)
        s = self.session
        # visited (or visited now) with the rows about these predicates
        # compiled (the engine's demand-driven compilation; ref.py's
        # session compiles everything)
        b = s.node(e, _DEMANDED) if hasattr(s, "demand") else s.node(e)
        reg = s.solver.register_atom
        th = self.theory
        f, exact = fe
        reg(th, b + _INT, (f, exact))
        reg(th, b + _EVEN, ({k: x * _HALF for k, x in f.items()}, exact))

    def add(self, node) -> None:
        """The engine visited the owned node ``node``: tell the theory, or
        park it until it is :meth:`wanted`."""
        if node in self.done:
            return
        if self.wanted(node):
            self.tell(node)
        else:
            self.parked.append(node)

    def tell(self, node) -> None:
        """Tell the theory the linear node ``node``."""
        if node in self.done:
            return
        if not self.attached:
            self.session.solver.attach_theory(self.theory)
            self.attached = True
        self._register(node, self.form(node))
