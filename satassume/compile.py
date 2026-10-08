"""Compile :mod:`satassume.formula` objects to integer clauses.

A ``VarTable`` allocates one solver variable per atom.  Compilation is direct
for clausal shapes (implications between literals, disjunctions, exclusions)
and uses Tseitin auxiliary variables for nested structure.  Every generated
clause is a list of non-zero integers; ``-v`` is the negation of ``v``.
"""
from __future__ import annotations

import heapq
from typing import Any, Callable, Dict, List, Sequence

from .formula import And, Equivalent, Exclusive, Formula, Implies, Not, Or, P, TRUE, FALSE
from .rules import BASIS, BASIS_INDEX, DEF_LITS as _DEF_LITS, basis_lits


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


def _def(f):
    """``(definition, node)`` (definition as in ``DEF_LITS``) of a derived
    atom ``f``, or of a conjunction of literals of one node, one of them
    derived, that is a conjunction of basis literals
    (``nonnegative(x) & nonzero(x)``: ``extended_real & finite &
    !extended_negative & !zero`` of ``x``); such a conjunction is compiled
    as a derived atom, so that all its occurrences share one literal.  None
    otherwise."""
    if isinstance(f, P):
        d = _DEF_LITS.get(f.pred)
        return None if d is None else (d, f.expr)
    if not isinstance(f, And):
        return None
    lits, nodes, derived = set(), set(), False
    for a in f.args:
        pos = not isinstance(a, Not)
        if not pos:
            a = a.args[0]
        if not isinstance(a, P) or (a.pred not in BASIS_INDEX and a.pred not in _DEF_LITS):
            return None
        op, ls = basis_lits(a.pred, pos)
        if op != '&' and len(ls) > 1:
            return None
        derived |= a.pred in _DEF_LITS
        lits.update(ls)
        nodes.add(a.expr)
    if not derived or len(nodes) != 1:
        return None
    return ('&', tuple(sorted(lits, key=abs))), nodes.pop()


class VarTable:
    """Bijection between atoms and positive integers.

    Variables are allocated per *node*: the first time any atom of a node is
    seen, one variable per basis predicate is allocated contiguously, in
    ``BASIS`` order, so ``var(P(pred, node)) == base_of[node] +
    BASIS_INDEX[pred]`` (derived predicates have no variable of their own).  Newly seen nodes are appended to ``new_nodes`` so a
    caller can discover children without a separate walk of the formula.

    An atom whose predicate is not in the vocabulary (a custom predicate,
    see :mod:`satassume.extensions`) gets a single variable of its own,
    outside any node block; such atoms are appended to ``new_custom``.

    ``slots[v]`` says what variable ``v`` stands for: ``None`` (an auxiliary
    variable), the custom atom ``P`` itself, or, for the ``NPRED`` variables
    of a node block, the shared pair ``(node, base)``; the atom of such a
    variable is ``P(BASIS[v - base], node)``, built only when asked for
    (:meth:`atom`): most of a block's atoms are never read, and creating all
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


def compile_formula(f, table: VarTable, emit: Callable[[List[int]], None], dv=None) -> None:
    """Assert ``f`` by emitting clauses through ``emit``.

    ``dv`` (optional, a session's :meth:`~satassume.engine.Session.dvar`):
    ``dv(dn, need)`` gives the shared definitional literal of a derived
    atom, with the direction(s) ``need`` of its definition emitted
    (``'pos'``: literal -> definition, ``'neg'``: definition -> literal,
    ``'both'``; ``'negunit'``: as ``'neg'``, or None to expand the
    atom instead).  With it, a derived atom that the clauses cannot just
    expand into basis literals (a conjunction under a wide disjunction, a
    negated conjunction) gets the same variable wherever it occurs (the
    assumptions, the proposition, relations), so a unit on one occurrence
    propagates to the others; without it, Plaisted-Greenbaum variables
    private to each occurrence."""
    if f is TRUE:
        return
    if f is FALSE:
        emit([])
        return
    if isinstance(f, P):
        if f.pred in _DEF_LITS:
            compile_formula(basis_formula(f), table, emit, dv)
        else:
            emit([table.var(f)])
        return
    if isinstance(f, Not) and isinstance(f.args[0], And) and dv is not None:
        dn = _def(f.args[0])
        if dn is not None:
            # a negated conjunction of one node: as a negated derived atom
            v = dv(dn, 'negunit')
            if v is not None:
                emit([-v])
                return
    if isinstance(f, Not) and isinstance(f.args[0], P):
        if f.args[0].pred in _DEF_LITS:
            if dv is not None and _DEF_LITS[f.args[0].pred][0] == '&':
                # a negated conjunction: the atom's shared literal if the
                # session wants it (``dv`` answers None otherwise), so
                # that an occurrence of it in the proposition is decided
                # by propagation
                v = dv(_def(f.args[0]), 'negunit')
                if v is not None:
                    emit([-v])
                    return
            compile_formula(Not(basis_formula(f.args[0])), table, emit, dv)
        else:
            emit([-table.var(f.args[0])])
        return
    if isinstance(f, And):
        for a in f.args:
            compile_formula(a, table, emit, dv)
        return
    if isinstance(f, Or):
        for clause in _or_cnf(f, table, emit, dv):
            emit(clause)
        return
    if isinstance(f, Implies):
        a, b = f.args
        if isinstance(a, And):
            compile_formula(Or(*[Not(x) for x in a.args], b), table, emit, dv)
        else:
            compile_formula(Or(Not(a), b), table, emit, dv)
        return
    if isinstance(f, Equivalent):
        args = f.args
        for i in range(len(args) - 1):
            compile_formula(Implies(args[i], args[i + 1]), table, emit, dv)
            compile_formula(Implies(args[i + 1], args[i]), table, emit, dv)
        return
    if isinstance(f, Exclusive):
        args = f.args
        for i in range(len(args)):
            for j in range(i + 1, len(args)):
                compile_formula(Or(Not(args[i]), Not(args[j])), table, emit, dv)
        return
    if isinstance(f, Not):
        inner = f.args[0]
        if isinstance(inner, Not):
            compile_formula(inner.args[0], table, emit, dv)
        elif isinstance(inner, And):
            compile_formula(Or(*[Not(a) for a in inner.args]), table, emit, dv)
        elif isinstance(inner, Or):
            for a in inner.args:
                compile_formula(Not(a), table, emit, dv)
        elif isinstance(inner, Implies):
            a, b = inner.args
            compile_formula(And(a, Not(b)), table, emit, dv)
        else:
            emit([-_literal(inner, table, emit, dv)])
        return
    raise TypeError(f"cannot compile {f!r}")


#: most clauses :func:`_or_cnf` makes by distributing conjunctions
MAX_DISTRIBUTE = 16
#: most conjunctions :func:`_or_cnf` weighs one by one (more cannot all
#: be distributed: each has two clauses or more)
MAX_EXACT = 8


def _or_cnf(f: Or, table: VarTable, emit, dv=None) -> List[List[int]]:
    """``f`` as clauses: one clause, except that a derived atom whose
    definition is a conjunction (``real``: ``extended_real & finite``), or
    the negation of one whose definition is a disjunction, splits it (an
    empty list: ``f`` holds); past :data:`MAX_DISTRIBUTE` clauses the
    largest conjunctions get Tseitin variables instead."""
    clause: List[int] = []
    parts: List[List[int]] = []       # conjunctions distributed over ``clause``
    srcs: Dict[int, tuple] = {}       # id(part) -> (derived atom, negated)
    for a in f.args:
        while isinstance(a, Not) and isinstance(a.args[0], Not):
            a = a.args[0].args[0]           # Implies(And(.., Not(p)), ..)
        if a is TRUE:
            return []
        if a is FALSE:
            continue
        if isinstance(a, Or):
            sub = _or_cnf(a, table, emit, dv)
            if not sub:
                return []
            if len(sub) == 1:
                clause.extend(sub[0])
                continue
            parts.append(sub)
            continue
        g, neg = (a.args[0], True) if isinstance(a, Not) else (a, False)
        g = _def(g)
        if g is not None:
            (op, ls), node = g
            b = table.node_base(node)
            lits = [b + l - 1 if l > 0 else -(b - l - 1) for l in ls]
            if neg:
                lits = [-l for l in lits]
                op = '|' if op == '&' else '&'
            if op == '|':
                clause.extend(lits)
            else:
                part = [[l] for l in lits]
                srcs[id(part)] = (g, neg)
                parts.append(part)
            continue
        clause.append(_literal(a, table, emit, dv))
    # per conjunction: distribute it over ``clause`` or give it a
    # definitional variable ``t`` (Plaisted-Greenbaum: only ``t`` implies
    # each of its clauses, the direction an asserted disjunction needs),
    # whichever gives fewer literals by the estimate below; past
    # MAX_DISTRIBUTE clauses always the variable, so the output stays linear
    # in ``f``.  Distributing parts p_1..p_m over ``clause`` gives
    # N = prod |p_i| clauses of N*|clause| + sum_i N/|p_i| * lits(p_i)
    # literals; the variable costs lits(p) + |p| + 1.
    if parts:
        info = [[len(part), sum(len(d) for d in part), part] for part in parts]

        def cost(info, extra):
            n = 1
            for m, _, _ in info:
                n *= m
            return n, n * (len(clause) + extra) + sum(n // m * l for m, l, _ in info)

        chosen = []
        if len(info) > MAX_EXACT:
            # more conjunctions of at least two clauses each than can stay
            # below MAX_DISTRIBUTE anyway: the largest get variables right
            # away (the greedy choice below would pick them one by one, at
            # cubic cost), the MAX_EXACT smallest go to the exact choice
            keep = set(map(id, heapq.nsmallest(MAX_EXACT, info, key=lambda i: (i[0], i[1]))))
            chosen = [i[2] for i in info if id(i) not in keep]
            info = [i for i in info if id(i) in keep]
        while info:
            n, best = cost(info, len(chosen))
            pick = None
            for j, (m, l, _) in enumerate(info):
                rest = info[:j] + info[j + 1:]
                c = cost(rest, len(chosen) + 1)[1] + l + m
                if c < best or (n > MAX_DISTRIBUTE and (pick is None or c < pick[1])):
                    if pick is None or c < pick[1]:
                        pick = (j, c)
            if pick is None:
                break
            chosen.append(info.pop(pick[0])[2])
        for part in chosen:
            src = srcs.get(id(part)) if dv is not None else None
            if src is not None:
                # the derived atom's shared literal, one direction
                g, neg = src
                t = dv(g, 'neg' if neg else 'pos')
                clause.append(-t if neg else t)
                continue
            t = table.aux()
            for c in part:
                emit([-t] + c)
            clause.append(t)
        parts = [part for _, _, part in info]
    out = [clause]
    for part in parts:
        out = [c + d for c in out for d in part]
    return out


def formula_literal(f, table: VarTable, emit, dv=None) -> int:
    """Public: a literal equivalent to ``f`` (Tseitin); ``dv`` as for
    :func:`compile_formula`."""
    return _literal(f, table, emit, dv)


def _literal(f, table: VarTable, emit, dv=None) -> int:
    """Return a literal equivalent to ``f``, introducing Tseitin variables as needed."""
    if isinstance(f, P):
        if f.pred in _DEF_LITS:
            if dv is not None:
                return dv(_def(f), 'both')
            return _literal(basis_formula(f), table, emit, dv)
        return table.var(f)
    if isinstance(f, Not):
        inner = f.args[0]
        if isinstance(inner, P):
            if inner.pred in _DEF_LITS:
                if dv is not None:
                    return -dv(_def(inner), 'both')
                return -_literal(basis_formula(inner), table, emit, dv)
            return -table.var(inner)
        return -_literal(inner, table, emit, dv)
    if isinstance(f, Implies):
        return _literal(Or(Not(f.args[0]), f.args[1]), table, emit, dv)
    if isinstance(f, Equivalent) and len(f.args) == 2:
        a, b = f.args
        return _literal(And(Implies(a, b), Implies(b, a)), table, emit, dv)
    if isinstance(f, Exclusive):
        lits = [_literal(a, table, emit, dv) for a in f.args]
        pairs = [Or(Not(_Lit(x)), Not(_Lit(y))) for i, x in enumerate(lits) for y in lits[i + 1:]]
        return _literal(And(*pairs), table, emit, dv) if pairs else _true_lit(table, emit)
    if isinstance(f, _Lit):
        return f.lit
    if f is TRUE:
        return _true_lit(table, emit)
    if f is FALSE:
        return -_true_lit(table, emit)
    if isinstance(f, And):
        if dv is not None:
            dn = _def(f)
            if dn is not None:
                return dv(dn, 'both')
        lits = [_literal(a, table, emit, dv) for a in f.args]
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
        lits = [_literal(a, table, emit, dv) for a in f.args]
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
