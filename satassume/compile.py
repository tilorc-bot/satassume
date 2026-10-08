"""Compile :mod:`satassume.formula` objects to integer clauses.

A ``VarTable`` allocates one solver variable per atom.  Compilation is direct
for clausal shapes (implications between literals, disjunctions, exclusions)
and uses Tseitin auxiliary variables for nested structure.  Every generated
clause is a list of non-zero integers; ``-v`` is the negation of ``v``.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Sequence

from .formula import And, Equivalent, Exclusive, Formula, Implies, Not, Or, P, TRUE, FALSE
from .rules import BASIS, DEF_LITS as _DEF_LITS


def basis_formula(atom: P):
    """The atom of a derived predicate as its definition over basis atoms
    of the same node (``And``/``Or`` of basis atoms and their negations);
    a basis or custom atom itself."""
    d = _DEF_LITS.get(atom.pred)
    if d is None:
        return atom
    op, ls = d
    args = [P(BASIS[l - 1], atom.expr) if l > 0 else Not(P(BASIS[-l - 1], atom.expr)) for l in ls]
    return And(*args) if op == '&' else Or(*args)


def _derived(f) -> bool:
    return isinstance(f, P) and f.pred in _DEF_LITS


class VarTable:
    """Bijection between atoms and positive integers.

    Variables are allocated per *node*: the first time any atom of a node is
    seen, one variable per predicate is allocated contiguously, in
    ``PREDICATES`` order, so ``var(P(pred, node)) == base_of[node] +
    PRED_INDEX[pred]``.  Newly seen nodes are appended to ``new_nodes`` so a
    caller can discover children without a separate walk of the formula.

    An atom whose predicate is not in the vocabulary (a custom predicate,
    see :mod:`satassume.extensions`) gets a single variable of its own,
    outside any node block; such atoms are appended to ``new_custom``.

    ``slots[v]`` says what variable ``v`` stands for: ``None`` (an auxiliary
    variable), the custom atom ``P`` itself, or, for the ``NPRED`` variables
    of a node block, the shared pair ``(node, base)``; the atom of such a
    variable is ``P(PREDICATES[v - base], node)``, built only when asked for
    (:meth:`atom`): most of a block's atoms are never read, and creating 33
    of them per node was 5% of the replay.
    """

    def __init__(self):
        from .rules import BASIS, BASIS_INDEX
        self._preds = BASIS
        self._pidx = BASIS_INDEX
        self._npred = len(BASIS)
        self.base_of: Dict[Any, int] = {}
        self.slots: List[Any] = [None]
        self.new_nodes: List[Any] = []
        self.custom: Dict[P, int] = {}
        self.new_custom: List[P] = []
        self.naux = 0

    def node_base(self, node) -> int:
        b = self.base_of.get(node)
        if b is None:
            b = len(self.slots)
            self.base_of[node] = b
            self.slots.extend([(node, b)] * self._npred)
            self.new_nodes.append(node)
        return b

    def var(self, atom: P) -> int:
        """The variable of a basis or custom atom (a derived predicate has
        no variable of its own: see :func:`basis_formula`)."""
        idx = self._pidx.get(atom.pred)
        if idx is None:
            if atom.pred in _DEF_LITS:
                raise ValueError(f"derived predicate {atom.pred!r} has no variable")
            v = self.custom.get(atom)
            if v is None:
                v = self.custom[atom] = len(self.slots)
                self.slots.append(atom)
                self.new_custom.append(atom)
            return v
        return self.node_base(atom.expr) + idx

    def aux(self) -> int:
        v = len(self.slots)
        self.slots.append(None)
        self.naux += 1
        return v

    def atom(self, v: int) -> P | None:
        """The atom of variable ``v`` (None for an auxiliary variable)."""
        e = self.slots[v]
        if type(e) is tuple:
            node, b = e
            return P(self._preds[v - b], node)
        return e

    @property
    def atom_of(self) -> List[P | None]:
        """``atom_of[v]`` is :meth:`atom` ``(v)`` (index 0 is None); built on
        each access, for inspection."""
        return [None] + [self.atom(v) for v in range(1, len(self.slots))]

    def __len__(self):
        return len(self.slots) - 1

    def lit_name(self, lit: int) -> str:
        a = self.atom(abs(lit))
        s = repr(a) if a is not None else f"aux{abs(lit)}"
        return ("~" if lit < 0 else "") + s


def compile_formula(f, table: VarTable, emit: Callable[[List[int]], None]) -> None:
    """Assert ``f`` by emitting clauses through ``emit``."""
    if f is TRUE:
        return
    if f is FALSE:
        emit([])
        return
    if isinstance(f, P):
        if f.pred in _DEF_LITS:
            compile_formula(basis_formula(f), table, emit)
        else:
            emit([table.var(f)])
        return
    if isinstance(f, Not) and isinstance(f.args[0], P):
        if f.args[0].pred in _DEF_LITS:
            compile_formula(Not(basis_formula(f.args[0])), table, emit)
        else:
            emit([-table.var(f.args[0])])
        return
    if isinstance(f, And):
        for a in f.args:
            compile_formula(a, table, emit)
        return
    if isinstance(f, Or):
        for clause in _or_cnf(f, table, emit):
            emit(clause)
        return
    if isinstance(f, Implies):
        a, b = f.args
        if isinstance(a, And):
            compile_formula(Or(*[Not(x) for x in a.args], b), table, emit)
        else:
            compile_formula(Or(Not(a), b), table, emit)
        return
    if isinstance(f, Equivalent):
        args = f.args
        for i in range(len(args) - 1):
            compile_formula(Implies(args[i], args[i + 1]), table, emit)
            compile_formula(Implies(args[i + 1], args[i]), table, emit)
        return
    if isinstance(f, Exclusive):
        args = f.args
        for i in range(len(args)):
            for j in range(i + 1, len(args)):
                compile_formula(Or(Not(args[i]), Not(args[j])), table, emit)
        return
    if isinstance(f, Not):
        inner = f.args[0]
        if isinstance(inner, Not):
            compile_formula(inner.args[0], table, emit)
        elif isinstance(inner, And):
            compile_formula(Or(*[Not(a) for a in inner.args]), table, emit)
        elif isinstance(inner, Or):
            for a in inner.args:
                compile_formula(Not(a), table, emit)
        elif isinstance(inner, Implies):
            a, b = inner.args
            compile_formula(And(a, Not(b)), table, emit)
        else:
            emit([-_literal(inner, table, emit)])
        return
    raise TypeError(f"cannot compile {f!r}")


def _or_cnf(f: Or, table: VarTable, emit) -> List[List[int]]:
    """``f`` as clauses: one clause, except that a derived atom whose
    definition is a conjunction (``real``: ``extended_real & finite``), or
    the negation of one whose definition is a disjunction, splits it (an
    empty list: ``f`` holds)."""
    clause: List[int] = []
    parts: List[List[int]] = []       # conjunctions distributed over ``clause``
    for a in f.args:
        if a is TRUE:
            return []
        if a is FALSE:
            continue
        if isinstance(a, Or):
            sub = _or_cnf(a, table, emit)
            if not sub:
                return []
            if len(sub) == 1:
                clause.extend(sub[0])
                continue
            parts.append(sub)
            continue
        g = a
        neg = False
        if isinstance(a, Not) and _derived(a.args[0]):
            g, neg = a.args[0], True
        if _derived(g):
            op, ls = _DEF_LITS[g.pred]
            b = table.node_base(g.expr)
            lits = [b + l - 1 if l > 0 else -(b - l - 1) for l in ls]
            if neg:
                lits = [-l for l in lits]
                op = '|' if op == '&' else '&'
            if op == '|':
                clause.extend(lits)
            else:
                parts.append([[l] for l in lits])
            continue
        clause.append(_literal(a, table, emit))
    out = [clause]
    for part in parts:
        out = [c + d for c in out for d in part]
    return out


def formula_literal(f, table: VarTable, emit) -> int:
    """Public: a literal equivalent to ``f`` (Tseitin)."""
    return _literal(f, table, emit)


def _literal(f, table: VarTable, emit) -> int:
    """Return a literal equivalent to ``f``, introducing Tseitin variables as needed."""
    if isinstance(f, P):
        if f.pred in _DEF_LITS:
            return _literal(basis_formula(f), table, emit)
        return table.var(f)
    if isinstance(f, Not):
        inner = f.args[0]
        if isinstance(inner, P):
            if inner.pred in _DEF_LITS:
                return -_literal(basis_formula(inner), table, emit)
            return -table.var(inner)
        return -_literal(inner, table, emit)
    if isinstance(f, Implies):
        return _literal(Or(Not(f.args[0]), f.args[1]), table, emit)
    if isinstance(f, Equivalent) and len(f.args) == 2:
        a, b = f.args
        return _literal(And(Implies(a, b), Implies(b, a)), table, emit)
    if isinstance(f, Exclusive):
        lits = [_literal(a, table, emit) for a in f.args]
        pairs = [Or(Not(_Lit(x)), Not(_Lit(y))) for i, x in enumerate(lits) for y in lits[i + 1:]]
        return _literal(And(*pairs), table, emit) if pairs else _true_lit(table, emit)
    if isinstance(f, _Lit):
        return f.lit
    if f is TRUE:
        return _true_lit(table, emit)
    if f is FALSE:
        return -_true_lit(table, emit)
    if isinstance(f, And):
        lits = [_literal(a, table, emit) for a in f.args]
        if not lits:
            return _true_lit(table, emit)
        if len(lits) == 1:
            return lits[0]
        t = table.aux()
        for l in lits:
            emit([-t, l])
        emit([t] + [-l for l in lits])
        return t
    if isinstance(f, Or):
        lits = [_literal(a, table, emit) for a in f.args]
        if not lits:
            return -_true_lit(table, emit)
        if len(lits) == 1:
            return lits[0]
        t = table.aux()
        for l in lits:
            emit([-l, t])
        emit([-t] + lits)
        return t
    raise TypeError(f"cannot make a literal from {f!r}")


class _Lit(Formula):
    """Wrapper so already-allocated literals can appear inside formulas."""

    def __init__(self, lit: int):
        super().__init__(lit)
        self.lit = lit


def _true_lit(table: VarTable, emit) -> int:
    v = getattr(table, 'true_var', None)
    if v is None:
        v = table.true_var = table.aux()
        emit([v])
    return v
