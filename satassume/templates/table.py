"""Rule tables: templates written as data (issue #97, P6).

A *table* is a sequence of rows and sections.  A :class:`Row` is one rule
schema ``premises -> conclusion`` over named slots, with a guard (``when``:
names of conditions on the node's pattern, all of which must hold) and
optional predicate iteration (``preds``: the row once per predicate, with
``'$p'`` in a literal standing for it and ``'flip:$p'`` for its sign flip,
``SIGN_FLIP``).  A :class:`Section` quantifies its rows over the arguments of
an n-ary node (``each``: every argument ``k`` with ``rest`` the others;
``pairs``: every pair ``k < l``; ``negsets``: every set ``neg`` of ``m``
arguments, ``2 <= m < n``, with ``rest`` the others), in the order of the
loop, so the emitted rule list is the one the hand-written function
emitted.

A literal is ``(slot, pred)`` or ``(slot, pred, False)``.  A slot is an
integer, a name the caller binds to an index (``'N'``, ``'B'``, ``'k'``), or
a *group* name bound to several indices (``'*'``, ``'rest'``, ``'neg'``):
a group literal stands for the literal on each of them (the builder
:func:`._common.lits`), a conjunction in the premises and a disjunction in
the conclusion.  The pseudo-predicate ``'int>=2'`` in a premise expands to
the alternatives of :func:`._common.ge2_alternatives`, one rule each.  A row
with ``kind='equiv'`` is ``premises -> (a <-> b)`` as two rules in the order
of :meth:`._common.Rules.equiv`; a :class:`Sub` row runs another table.

The interpreter :func:`expand` yields ``(row, premises, conclusion)``; the
template functions hand the specs to :class:`._common.Rules`, and
``tools/totality.py`` uses the row names to say which rows produced the
clauses of a non-total block.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from itertools import combinations
from typing import Any

from ._common import SIGN_FLIP, Rules, ge2_alternatives, lits

__all__ = ['Row', 'Section', 'Sub', 'count_rows', 'expand', 'iter_rows', 'rules_of']

GE2 = 'int>=2'


class Row:
    """One rule schema: ``And(prem) -> Or(concl)`` (``kind='rule'``) or
    ``prem -> (concl[0] <-> concl[1])`` (``kind='equiv'``)."""
    __slots__ = ('_concl', '_ge2', '_prem', 'concl', 'kind', 'name', 'note', 'preds', 'prem', 'when')

    def __init__(self, name: str, prem, concl, when=(), preds=None, kind='rule', note=''):
        self.name = name
        self.prem = tuple(prem)
        concl = tuple(concl)
        if concl and not isinstance(concl[0], tuple):
            concl = (concl,)                 # a single literal
        self.concl = concl
        self.when = (when,) if isinstance(when, str) else tuple(when)
        self.preds = preds
        self.kind = kind
        self.note = note
        if kind == 'equiv' and len(concl) != 2:
            raise ValueError(f"{name}: an equiv row has two literals")
        self._compile()

    def _compile(self):
        """Normalize the literals for the interpreter (called again by
        whoever replaces ``prem`` or ``concl``, e.g. a mutation test)."""
        self._prem = tuple(_norm(s) for s in self.prem)
        self._concl = tuple(_norm(s) for s in self.concl)
        self._ge2 = any(s[1] == GE2 for s in self.prem)

    def __repr__(self):
        return f"Row({self.name!r})"

    def text(self) -> str:
        """The row as one line: ``[when] premises -> conclusion``."""
        def lit(l):
            s = f"{l[1]}({l[0]})"
            return s if len(l) < 3 or l[2] else "~" + s
        prem = " & ".join(lit(l) for l in self.prem) or "True"
        sep = " <-> " if self.kind == 'equiv' else " | "
        concl = sep.join(lit(l) for l in self.concl)
        if self.kind == 'equiv':
            concl = f"({concl})"
        head = f"[{', '.join(self.when)}] " if self.when else ""
        over = f" for $p in {len(self.preds)} preds" if self.preds else ""
        return f"{self.name}: {head}{prem} -> {concl}{over}"


class Section:
    """Rows quantified together over the arguments (see the module doc)."""
    __slots__ = ('over', 'rows', 'when')

    def __init__(self, over: str, rows, when=()):
        if over not in ('each', 'pairs', 'negsets'):
            raise ValueError(over)
        self.over = over
        self.when = (when,) if isinstance(when, str) else tuple(when)
        self.rows = tuple(rows)


class Sub:
    """Run ``table`` with its own guards, the context ``ctx(parent_ctx)``
    and the slots ``slots(parent_ctx, parent_slots)``."""
    __slots__ = ('ctx', 'guards', 'name', 'slots', 'table', 'when')

    def __init__(self, name, table, guards, ctx: Callable, slots: Callable, when=()):
        self.name = name
        self.table = table
        self.guards = guards
        self.ctx = ctx
        self.slots = slots
        self.when = (when,) if isinstance(when, str) else tuple(when)


def _holds(when, guards, ctx) -> bool:
    for g in when:
        if not guards[g](ctx):
            return False
    return True


def _norm(spec):
    """``(slot, pred, pos, mode)``: mode 1 for ``'$p'``, 2 for ``'flip:$p'``."""
    pred = spec[1]
    mode = 1 if pred == '$p' else 2 if pred == 'flip:$p' else 0
    return (spec[0], pred, spec[2] if len(spec) > 2 else True, mode)


def _lits(spec, slots, cur):
    """The literals of one (normalized) row literal: one per index of its
    slot."""
    k, pred, pos, mode = spec
    if mode:
        pred = cur if mode == 1 else SIGN_FLIP.get(cur, cur)
    v = k if type(k) is int else slots[k]
    if type(v) is int:
        return [(v, pred, pos)]
    return lits(v, pred, pos)


def _premise_alternatives(row, slots, cur):
    """The premise lists of a row (more than one only for ``int>=2``)."""
    if not row._ge2:
        prem = []
        for spec in row._prem:
            prem += _lits(spec, slots, cur)
        return (prem,)
    alts = [[]]
    for spec in row._prem:
        if spec[1] == GE2:
            k = spec[0] if type(spec[0]) is int else slots[spec[0]]
            alts = [a + list(g) for a in alts for g in ge2_alternatives(k)]
        else:
            ls = _lits(spec, slots, cur)
            alts = [a + ls for a in alts]
    return alts


def _row_specs(row: Row, slots, cur):
    out = []
    for prem in _premise_alternatives(row, slots, cur):
        if row.kind == 'equiv':
            (a,), (b,) = (_lits(row._concl[0], slots, cur), _lits(row._concl[1], slots, cur))
            # Rules.equiv: cond -> (a <-> b) as two rules
            out.append(([*prem, a], [b]))
            out.append(([*prem, b], [a]))
        else:
            concl = []
            for spec in row._concl:
                concl += _lits(spec, slots, cur)
            out.append((prem, concl))
    return out


def _rows(rows, guards, ctx, slots) -> Iterator[tuple[Any, list, list]]:
    for row in rows:
        if isinstance(row, Sub):
            if _holds(row.when, guards, ctx):
                sctx = row.ctx(ctx)
                yield from expand(row.table, row.guards, sctx, row.slots(ctx, slots))
            continue
        if row.when and not _holds(row.when, guards, ctx):
            continue
        fast = row.kind == 'rule' and not row._ge2
        for cur in (row.preds or (None,)):
            if fast:
                prem = []
                for spec in row._prem:
                    prem += _lits(spec, slots, cur)
                concl = []
                for spec in row._concl:
                    concl += _lits(spec, slots, cur)
                yield row, prem, concl
                continue
            for prem, concl in _row_specs(row, slots, cur):
                yield row, prem, concl


def _bindings(over, A):
    n = len(A)
    if over == 'each':
        for k in A:
            rest = [j for j in A if j != k]
            b = {'k': k, 'rest': rest}
            if len(rest) == 1:
                b['l'] = rest[0]
            yield {}, b
    elif over == 'pairs':
        for k, l in combinations(A, 2):
            yield {}, {'k': k, 'l': l, 'rest': [j for j in A if j != k and j != l]}
    else:   # negsets
        for m in range(2, n):
            for neg in combinations(A, m):
                yield {'m': m}, {'neg': list(neg), 'rest': [j for j in A if j not in neg]}


def expand(table, guards: dict[str, Callable], ctx: dict[str, Any],
           slots: dict[str, Any]) -> Iterator[tuple[Any, list, list]]:
    """``(row, premises, conclusion)`` for every rule the table emits, in
    table order.  ``slots['*']`` is the list of argument indices for
    sections."""
    for item in table:
        if isinstance(item, Section):
            if not _holds(item.when, guards, ctx):
                continue
            for extra_ctx, b in _bindings(item.over, list(slots['*'])):
                c = {**ctx, **extra_ctx} if extra_ctx else ctx
                yield from _rows(item.rows, guards, c, {**slots, **b})
        else:
            yield from _rows((item,), guards, ctx, slots)


def rules_of(table, guards, ctx, slots, R: Rules | None = None):
    """Feed the expanded table to ``Rules.rule``; return ``R.rules``."""
    if R is None:
        R = Rules()
    for _, prem, concl in expand(table, guards, ctx, slots):
        R.rule(prem, concl)
    return R.rules


def iter_rows(table):
    """Every :class:`Row` of a table (sections and sub-tables flattened)."""
    for item in table:
        if isinstance(item, Section):
            yield from item.rows
        elif isinstance(item, Sub):
            yield from iter_rows(item.table)
        else:
            yield item


def count_rows(table) -> int:
    return sum(1 for _ in iter_rows(table))
