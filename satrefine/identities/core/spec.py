"""A family as data: which table handlers serve which keys, and the tables it states.

A family module (``rules/*.py``, ``compat/matrices.py``) states its rows in
module-level tables (the maths; the names label the rows in the generated
modules' derivation comments and are what the tools read) and ends with
``SPEC = Family(...)``, which registers nothing: :func:`satrefine.identities.load`
registers :func:`build` of every family's spec.

``Family.handlers`` maps a key of ``satrefine.identities.compat.upstream.handlers_dict`` to a
part (:class:`Rules` or :class:`Identities`) or a tuple of parts, tried in
order (:func:`chain`).  :func:`build` makes each part's handler once, so a
part named under several keys is one handler object; a key with one part gets
that handler itself.  The other fields classify the family's rows into the
fixed table kinds: ``facts`` (identity rows, stated), ``exp_forms``
(exponential forms ``(L, W, domain)`` with ``L == exp(W)``, which
:func:`..rules._tables.derive` composes with the facts), ``rules`` (rule rows,
stated) and ``ranges`` (range rows ``(head(y), interval, condition)`` for the
floor of a bounded quantity).  Every row a handler uses is one of the stated
rows, derived from them (``derive(facts, exp_forms)``), or a stated row whose
generic head (an undefined function such as ``G``) is replaced by the key's
head (``tests/refine_identities/rules/test_family_specs.py``).

``assumed`` is a set of facts about the pattern variables (``Q.integer(n)``).
A fact belongs to every row whose left side holds all its variables, as a
theorem's "for n an integer" holds for every formula that follows.  The
family adds it to the row's condition, in place, so the module's tables are
complete rows for everything that reads them; such rows may omit their own
condition, ``(lhs, rhs)``.

A fact ``Eq(r, e1) | Eq(r, e2) | ...`` with a symbol ``r`` is a definition
instead: "r is e1 or e2 or ...".  A row holding ``r`` in its left side becomes
one row for each ``e``, with ``r`` replaced; the other facts then apply to
those rows.  ``ask`` never sees a definition.
"""
from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
from typing import Any, Callable

from sympy import And, Eq, Or, true

from .rewrite import identity_handler, rule_handler

Handler = Callable[[Any, Any], Any]


@dataclass(eq=False)
class Rules:
    """Rule rows ``(lhs, rhs, hypothesis[, unless])`` as one handler (:func:`.rewrite.rule_handler`)."""
    rows: list
    _: KW_ONLY
    by_binding: bool = False

    def handler(self) -> Handler:
        return rule_handler(self.rows, by_binding=self.by_binding)


@dataclass(eq=False)
class Identities:
    """Identity rows ``(lhs, rhs, domain[, unless])`` as one handler (:func:`.rewrite.identity_handler`)."""
    rows: list
    _: KW_ONLY
    measure: Any = None
    opaque: tuple | None = None
    splits: bool = True

    def handler(self) -> Handler:
        return identity_handler(self.rows, measure=self.measure, opaque=self.opaque, splits=self.splits)


@dataclass(eq=False)
class Family:
    """``handlers``: ``key -> part or tuple of parts``; the table kinds: ``facts``,
    ``exp_forms``, ``rules``, ``ranges`` (lists), ``assumed`` (a set of facts; see
    the module docstring)."""
    handlers: dict
    _: KW_ONLY
    facts: list = ()
    exp_forms: list = ()
    rules: list = ()
    ranges: list = ()
    assumed: set = ()

    def __post_init__(self):
        self.completed: dict = {}   # id(row as written) -> (row, completed rows); see complete_module
        if not self.assumed:
            return
        definitions = dict(d for d in map(_definition, self.assumed) if d)
        facts = [f for f in self.assumed if not _definition(f)]
        done = self.completed   # a row in several tables stays the same rows
        tables = [p.rows for parts in self.handlers.values()
                  for p in (parts if isinstance(parts, tuple) else (parts,))]
        for rows in {id(t): t for t in tables + [self.facts, self.rules] if isinstance(t, list)}.values():
            rows[:] = [done_row for row in rows for done_row in done.setdefault(
                id(row), (row, [assume(r, facts) for r in _define(row, definitions)]))[1]]


def complete_module(module) -> None:
    """Complete the module's own tables too: a table the family was given only as a slice
    or inside a concatenation (``INFINITE[0:2]``, ``[ZERO] + RULES``) still holds the rows
    as written, and the tools read the module's tables."""
    completed = module.SPEC.completed
    for value in vars(module).values():
        if isinstance(value, list) and any(id(row) in completed for row in value):
            value[:] = [c for row in value for c in (completed[id(row)][1] if id(row) in completed else [row])]


def _definition(fact) -> tuple | None:
    """``(r, [e1, e2, ...])`` when ``fact`` is ``Eq(r, e1) | Eq(r, e2) | ...`` for a symbol ``r``."""
    alternatives = fact.args if isinstance(fact, Or) else (fact,)
    if not all(isinstance(a, Eq) for a in alternatives):
        return None
    names = {a.lhs for a in alternatives}
    if len(names) != 1 or not next(iter(names)).is_Symbol:
        return None
    return names.pop(), [a.rhs for a in alternatives]


def _define(row: tuple, definitions: dict) -> list[tuple]:
    """``row``, once for each way of replacing its defined symbols by what they stand for."""
    rows = [row]
    for r, expressions in definitions.items():
        if r in row[0].free_symbols:
            rows = [tuple(t.xreplace({r: e}) if hasattr(t, 'xreplace') else t for t in row)
                    for row in rows for e in expressions]
    return rows


def assume(row: tuple, facts) -> tuple:
    """``row`` with the facts about its left side's variables in its condition."""
    lhs, rhs, *rest = row
    condition, unless = (rest or [true])[0], rest[1:]
    held = [f for f in facts if f.free_symbols <= lhs.free_symbols]
    return (lhs, rhs, And(*held, condition), *unless)


def chain(*handlers: Handler) -> Handler:
    """One handler from several: the first non-``None`` result wins.  Rule rows
    come before identity rows in every family, and because only the identity
    handler switches itself off while evaluating a candidate, nested nodes of the
    same head are still reduced by the rules inside a candidate."""
    def handler(expr: Any, assumptions: Any) -> Any:
        for h in handlers:
            out = h(expr, assumptions)
            if out is not None:
                return out
        return None
    handler.parts = handlers  # type: ignore[attr-defined]
    return handler


def build(family: Family) -> dict[str, Handler]:
    """``key -> handler`` for ``family``; each part is built once."""
    made: dict = {}
    out = {}
    for key, parts in family.handlers.items():
        parts = parts if isinstance(parts, tuple) else (parts,)
        for p in parts:
            if p not in made:
                made[p] = p.handler()
        out[key] = made[parts[0]] if len(parts) == 1 else chain(*(made[p] for p in parts))
    return out
