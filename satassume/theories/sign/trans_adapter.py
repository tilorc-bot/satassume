"""Session nodes onto :class:`.trans.TransTheory` (issue #149, T6).

As :mod:`.sign_adapter` (the shared :class:`.sign_adapter.ClassAdapter`):
a term is a session node with the seven basis variables of :data:`.trans.PREDS`
registered as theory atoms and the four of :data:`.trans.ONESIDED` as
read-only ones, or an atomic number with a fixed atom set.  Constants are
read exactly: ``1`` is ``ONE``, another integer ``ZI`` (``0`` is ``Z0``), a
non-integer rational ``Q1``; ``E``, ``pi``, ``I``, ``oo`` from their static
``is_*`` facts (``TR``, ``TR``, ``AC``, ``IR``); a ``Float`` only for
``finite``, ``extended_real`` and ``zero``, as :mod:`.closure_adapter`.

The nodes told (:meth:`TransAdapter.selects`): the applications of the 13
functions of :data:`.trans.FUNCS`, ``E**x`` (as ``exp(x)``) and every other
``Pow`` whose exponent is not a rational constant (``x**y``, ``2**x``,
``x**sqrt(2)``; not ``x**2`` or ``1/x``, where the templates' rows say all
the theory would).  Never a term with a non-commutative subterm (it may be
a matrix: ``domain._noncommutative``).
"""
from __future__ import annotations

from .sign_adapter import ClassAdapter
from .trans import (ALL, ONE, ONESIDED, ONESIDED_MASK, OPS, POW, PRED_MASK, PREDS, Q1,
                    TransTheory, Z0, ZI)

_FLOAT_READ = frozenset(("finite", "extended_real", "zero"))

#: SymPy function class -> map op id (built on first use: the module
#: loads no SymPy)
_CLASSES: dict = {}
_noncommutative = None
classed = None


def _classes() -> dict:
    global _noncommutative, classed
    if not _CLASSES:
        import sympy
        from ...knowledge.domain import _noncommutative, classed
        _CLASSES.update((getattr(sympy, name), op) for name, op in OPS.items())
    return _CLASSES


def _applied(e) -> bool:
    """Whether ``e`` has a subterm other than a symbol, a number or a sum,
    product or power (a function application: ``floor(x)``, ``f(1)``)."""
    stack = [e]
    while stack:
        t = stack.pop()
        if t.is_Symbol or t.is_number:
            continue
        if t.is_Add or t.is_Mul or t.is_Pow:
            stack.extend(t.args)
            continue
        return True
    return False


def op_args(node):
    """``(op, args)`` of a node the theory takes, else None."""
    op = _classes().get(type(node))
    if op is not None:
        if len(node.args) != 1:
            return None
        args = node.args
    elif getattr(node, 'is_Pow', False):
        b, e = node.args
        if type(b).__name__ == 'Exp1':
            op, args = OPS['exp'], (e,)
        elif getattr(e, 'is_Rational', False):
            return None             # x**2, 1/x, sqrt(x): the rows decide them
        else:
            op, args = POW, (b, e)
    else:
        return None
    if _noncommutative(node):
        return None
    return op, args


class TransAdapter(ClassAdapter):
    THEORY = TransTheory
    PREDS = PREDS
    PRED_MASK = PRED_MASK
    ALL = ALL
    ONESIDED = ONESIDED
    ONESIDED_MASK = ONESIDED_MASK
    #: the theory's premises are mostly what the query mentions already;
    #: the other rows of a term stay parked until the escalation (fewer
    #: clauses per query: ~/th/A6/scripts/measure_trans.py)
    DEMAND = False
    #: told the nodes it selects that :meth:`engages` takes under the
    #: query's class scope (``scope.class_symbols``)
    GATED = True

    @staticmethod
    def kinds(cls: type) -> bool:
        return cls in _classes() or bool(getattr(cls, 'is_Pow', False))

    @staticmethod
    def engages(node, classes: frozenset) -> bool:
        """Whether the theory is told ``node`` under the class scope
        ``classes`` (:func:`satassume.scope.class_symbols`): iff no argument
        is *plain*, an arithmetic expression (sums, products and powers)
        that is not a number, whose free symbols are outside ``classes``
        and carry no class assumption of their own (``Symbol('n',
        integer=True)``).  Every table entry that claims something reads a
        class fact of each argument (``POW``: of the base and the
        exponent), and a plain argument has none: its class facts could
        only come from a class atom or an equality over its symbols, or
        from a ``zero`` atom of one of them, and those put the symbols in
        ``classes``.  An argument with a function application anywhere in
        it (``floor(x)``, ``sign(x)``, ``f(1)``, ``f(x) + 1``) is never
        plain: its class facts may come from template rows or from EUF.
        A node left out waits in the session (``Session._parked``) until
        the scope widens.  What this costs is measured, not proved: a
        class fact of a plain argument by another chain (a sign fact
        ``x - 1`` neither positive nor negative); the audit of PR #154
        found none."""
        oa = op_args(node)
        if oa is None:
            return False
        for a in oa[1]:
            if not (a.is_number or _applied(a) or any(
                    s in classes or classed(s) for s in a.free_symbols)):
                return False
        return True

    @staticmethod
    def over_cap(node) -> bool:
        return op_args(node) is not None

    @classmethod
    def selects(cls, node) -> bool:
        return op_args(node) is not None

    @classmethod
    def const_mask(cls, c) -> int:
        if getattr(c, 'is_Rational', False):
            if not getattr(c, 'is_Integer', False):
                return 1 << Q1
            return 1 << (Z0 if c.p == 0 else ONE if c.p == 1 else ZI)
        return super().const_mask(c)

    @staticmethod
    def _const_fact(c, pred):
        if getattr(c, 'is_Float', False) and pred not in _FLOAT_READ:
            return None
        return getattr(c, 'is_' + pred, None)

    def __init__(self, session):
        super().__init__(session)
        self.oneside_terms = set()

    def add(self, node) -> None:
        """Tell the theory the function application or power ``node``."""
        if node in self.done:
            return
        oa = op_args(node)
        if oa is None:
            return
        self.done.add(node)
        op, args = oa
        if op == POW:
            # the read-only atoms separate ONE from ZI: only the POW table
            # reads that (Gelfond-Schneider's base not in {0, 1})
            b = args[0]
            if b not in self.oneside_terms:
                self.oneside_terms.add(b)
                tb = self.terms.get(b)
                if tb is not None and b in self.session.base:
                    self._oneside(self.session.base[b], tb)
        t = self.term(node)
        self.theory.add_node(op, t, [self.term(a) for a in args])


__all__ = ['TransAdapter', 'op_args']
