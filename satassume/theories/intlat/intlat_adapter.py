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
``2.0`` is never integral (a Float is no integer, and a Float term makes
every form above it a Float).
"""
from __future__ import annotations

from fractions import Fraction

from ...knowledge.rules import BASIS_INDEX
from .intlat import CONST, IntLatTheory

_INT = BASIS_INDEX["integer"]
_EVEN = BASIS_INDEX["even"]
_DEMANDED = frozenset((_INT, _EVEN))
_HALF = Fraction(1, 2)


def linear(node) -> bool:
    """Whether ``node`` is a linear node (a sum, or ``c*t`` with a nonzero
    Rational ``c``): the adapter reads its form through it."""
    if getattr(node, "is_Add", False):
        return bool(node.args)
    if getattr(node, "is_Mul", False):
        args = node.args
        return len(args) >= 2 and args[0].is_Rational and not args[0].is_zero
    return False


import os
_X = os.environ.get("INTLAT_X", "")
_MENTION = os.environ.get("INTLAT_M", "1") == "1"


def owns(node) -> bool:
    """Whether a session tells the theory ``node``: every linear node
    (``templates.core.intlat_owns``: the templates have no integrality or
    parity rows for it)."""
    return linear(node)


def _rat(c) -> Fraction:
    return Fraction(int(c.p), int(c.q))


def coeff_rest(node):
    """``(c, t)`` for a linear product ``c*t``: ``t`` the product of the
    other factors (one factor: that factor itself)."""
    args = node.args
    rest = args[1:]
    return args[0], (rest[0] if len(rest) == 1 else node.func(*rest))


class IntLatAdapter:
    """The theory of one session and the linear nodes it was told."""

    def __init__(self, session):
        self.session = session
        self.theory = IntLatTheory()
        session.solver.attach_theory(self.theory)
        self.terms = {}         # term -> column
        self.forms = {}         # linear node -> its form
        self.done = set()       # nodes whose atoms are registered

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

    def sync_derived(self) -> None:
        return None

    # -- forms ---------------------------------------------------------------
    def form(self, e):
        """The form of ``e`` (dict column -> Fraction, the constant at
        :data:`CONST`); registers the atoms of every term on the way."""
        f = self.forms.get(e)
        if f is not None:
            return f
        acc: dict = {}
        self._lin(e, Fraction(1), acc)
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
            if e.is_Add:
                for a in e.args:
                    self._lin(a, c, acc)
                return
            k, t = coeff_rest(e)
            self._lin(t, c * _rat(k), acc)
            return
        col = self.term(e)
        acc[col] = acc.get(col, 0) + c

    def term(self, e) -> int:
        col = self.terms.get(e)
        if col is None:
            col = self.terms[e] = len(self.terms)
            self._register(e, ({col: Fraction(1)}, True))
        return col

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
        m = _MENTION
        reg(th, b + _INT, (f, exact), mention=m)
        reg(th, b + _EVEN, ({k: x * _HALF for k, x in f.items()}, exact), mention=m)

    def add(self, node) -> None:
        """Tell the theory the linear node ``node``."""
        if node in self.done or _X == "noreg":
            return
        f = self.form(node)
        self._register(node, f)
