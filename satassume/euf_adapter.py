"""Map SymPy equality atoms to :class:`satassume.euf.EUFTheory` payloads.

``EUFAdapter.register(solver, var, atom)`` interprets ``Q.eq(a, b)``,
``Q.ne(a, b)``, ``Eq(a, b)`` and ``Ne(a, b)``.  The first time it sees a
solver it attaches the adapter's theory to it.  Then it registers ``var``
with the payload ``EqAtom(term(a), term(b), positive)``.  It returns False,
registering nothing, for any other atom and for atoms containing ``nan``.
``Eq(nan, nan)`` is False in SymPy, so reflexivity does not hold for nan.

Flattening (:meth:`EUFAdapter.term`)
------------------------------------

* A SymPy ``Rational`` (including ``Integer``) becomes ``theory.value(r)``.
  Distinct rationals are distinct values, so ``x = 1 & x = 2`` conflicts.
* An expression of a *function-like* class becomes
  ``theory.term(expr.func, [term(a) for a in expr.args])``, so congruence
  applies to it.  The function-like classes are ``Add``, ``Mul``, ``Pow``
  and every ``sympy.core.function.Application`` (undefined functions ``f(x)``,
  ``sin``, ``Abs``, ``Max``, ``Piecewise``, ...).  For each of these the
  value is a function of the values of the arguments.  Excluded: integral
  transforms (``LaplaceTransform`` and friends are ``Function``
  subclasses but bind a variable) and any class that overrides
  ``free_symbols`` or ``bound_symbols`` (see ``_structural``).
  ``Add`` and ``Mul`` are opaque, variadic heads applied to SymPy's
  canonical argument tuple.  There is no AC reasoning.  ``x + y`` and
  ``y + x`` are one term only because SymPy already sorts them;
  ``x*(y + 1)`` and ``x*y + x`` are unrelated terms, which is incomplete
  but sound.
* Everything else is one opaque constant keyed by the expression itself:
  symbols, ``Float``, ``pi``, ``oo``, ``zoo``, and above all binders
  (``Sum``, ``Integral``, ``Lambda``, ``Derivative``, ``Subs``, ...),
  relations, predicates and booleans.  Congruence over the arguments of a
  binder is unsound: from ``x = y``, ``Sum(x, (x, 1, 2))`` need not equal
  ``Sum(y, (x, 1, 2))``.  Floats are opaque because SymPy's
  ``Eq(Float, Rational)`` is value-based (``Eq(0.1, 1/10)`` is True), so
  keying a Float as a distinct value could refute a satisfiable
  assignment.

Structurally equal expressions (``==`` in SymPy) are mathematically equal,
so interning by expression is sound.
"""
from __future__ import annotations

from sympy import Add, Mul, Pow, Rational, nan
from sympy.assumptions.assume import AppliedPredicate
from sympy.assumptions.ask import Q
from sympy.core.basic import Basic
from sympy.core.function import Application
from sympy.core.relational import Equality, Unequality
from sympy.integrals.transforms import IntegralTransform

from .euf import EqAtom, EUFTheory

__all__ = ["EUFAdapter"]

_STRUCTURAL = (Add, Mul, Pow, Application)


_class_ok: dict[type, bool] = {}


def _inherits_from_basic(cls, name) -> bool:
    for c in cls.__mro__:
        if name in c.__dict__:
            return c is Basic
    return True


def _structural(expr) -> bool:
    """True iff congruence may look inside ``expr``: a function-like class
    that binds no variable.

    Decided per class, without walking the expression (so deep terms cost
    nothing and never hit the recursion limit): the class must be Add, Mul,
    Pow or an ``Application``, must not be an integral transform, and must
    inherit both ``free_symbols`` and ``bound_symbols`` from ``Basic``.
    Basic's ``free_symbols`` is the union over the arguments, so such a
    class binds nothing.  Any class that overrides either attribute (the
    transforms do) is opaque.
    """
    if not expr.args:
        return False
    cls = type(expr)
    ok = _class_ok.get(cls)
    if ok is None:
        ok = _class_ok[cls] = (
            issubclass(cls, _STRUCTURAL)
            and not issubclass(cls, IntegralTransform)
            and _inherits_from_basic(cls, "free_symbols")
            and _inherits_from_basic(cls, "bound_symbols"))
    return ok


class EUFAdapter:
    """Turns SymPy equality atoms into EUF atoms of one :class:`EUFTheory`.

    One adapter (and theory) per solver.  :meth:`register` attaches the
    theory to the solver on first use.
    """

    def __init__(self, theory: EUFTheory | None = None):
        self.theory = theory if theory is not None else EUFTheory()
        self._terms: dict[Basic, int] = {}
        self._solver = None

    # ------------------------------------------------------------------

    @staticmethod
    def parse(atom):
        """``(lhs, rhs, positive)`` if ``atom`` is an equality atom EUF
        interprets, else None."""
        if isinstance(atom, AppliedPredicate):
            if atom.function == Q.eq:
                positive = True
            elif atom.function == Q.ne:
                positive = False
            else:
                return None
            args = atom.arguments
        elif isinstance(atom, Equality):
            positive, args = True, atom.args
        elif isinstance(atom, Unequality):
            positive, args = False, atom.args
        else:
            return None
        if len(args) != 2 or not all(isinstance(a, Basic) for a in args):
            return None
        if any(a.has(nan) for a in args):
            return None
        return args[0], args[1], positive

    def interprets(self, atom) -> bool:
        return self.parse(atom) is not None

    def register(self, solver, var: int, atom) -> bool:
        """Register solver variable ``var`` as ``atom`` with the theory.
        Returns False, registering nothing, if EUF does not interpret the
        atom."""
        parsed = self.parse(atom)
        if parsed is None:
            return False
        if self._solver is not solver:
            if self._solver is not None:
                raise ValueError("an EUFAdapter serves a single solver")
            if not any(t is self.theory for t in solver.theories()):
                solver.attach_theory(self.theory)
            self._solver = solver
        lhs, rhs, positive = parsed
        payload = EqAtom(self.term(lhs), self.term(rhs), positive)
        solver.register_atom(self.theory, var, payload)
        return True

    # ------------------------------------------------------------------

    def term(self, expr) -> int:
        """The theory term of SymPy expression ``expr`` (interned)."""
        terms = self._terms
        t = terms.get(expr)
        if t is not None:
            return t
        th = self.theory
        # iterative post-order, so deep expressions do not hit the
        # recursion limit
        stack = [(expr, False)]
        while stack:
            e, ready = stack.pop()
            if e in terms:
                continue
            if isinstance(e, Rational):
                terms[e] = th.value(e)
            elif _structural(e):
                if ready:
                    terms[e] = th.term(e.func, [terms[a] for a in e.args])
                else:
                    stack.append((e, True))
                    stack.extend((a, False) for a in e.args if a not in terms)
            else:
                terms[e] = th.term(e)
        return terms[expr]

    def term_of(self, expr) -> int | None:
        """The term of ``expr`` if the adapter has interned it, else None."""
        return self._terms.get(expr)

    def terms(self) -> dict:
        """Every interned SymPy expression, mapped to its term id."""
        return dict(self._terms)

    def shared_terms(self) -> set:
        """Candidate interface terms for combination with another theory.

        This is every SymPy expression interned so far: the sides of every
        registered atom and all their subterms, numbers included (``x`` and
        ``y`` for ``f(x) = f(y)``).  Opaque terms count too, but not their
        insides: for ``Sum(x, (x, 1, 2))`` only the Sum itself.  The
        combination layer intersects this set with the other theory's terms.
        An interface equality ``a = b`` is registered with
        ``register(solver, v, Q.eq(a, b))``.
        """
        return set(self._terms)
