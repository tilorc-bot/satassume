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


def _classes() -> dict:
    global _noncommutative
    if not _CLASSES:
        import sympy
        from ...knowledge.domain import _noncommutative
        _CLASSES.update((getattr(sympy, name), op) for name, op in OPS.items())
    return _CLASSES


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
        """Whether each argument is a number (``exp(2)``, ``2**sqrt(2)``) or
        has a free symbol in ``classes`` (the symbols of the query's class
        atoms and equalities): every table entry that claims something
        reads a class fact of each argument (``POW``: of the base and the
        exponent), which an argument outside the scope has only by a zero
        fact (``0``, where the templates decide the functions) or a chain
        of rows from a class atom over its symbols."""
        oa = op_args(node)
        if oa is None:
            return False
        for a in oa[1]:
            if not (a.is_number or (classes and not classes.isdisjoint(a.free_symbols))):
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
