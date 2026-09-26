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
head (``tests/refine_identities/test_family_specs.py``).
"""
from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
from typing import Any, Callable

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
    ``exp_forms``, ``rules``, ``ranges`` (lists; see the module docstring)."""
    handlers: dict
    _: KW_ONLY
    facts: list = ()
    exp_forms: list = ()
    rules: list = ()
    ranges: list = ()


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
