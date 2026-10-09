"""Custom-predicate registrations the harness can switch on and off.

Registrations are part of the declared configuration, so a stream may
carry ``Register``/``Unregister`` events; the reference for a query is
computed under the registrations in force when the query runs.  Each
registration has an id so that repro scripts can name it.
"""
from __future__ import annotations

from typing import Callable, Dict, List, NamedTuple, Tuple

from satassume.knowledge.extensions import extensions
from satassume.sat.formula import Implies, Not, P


class Registration(NamedTuple):
    id: str
    pred: str
    classes: Tuple[type, ...]
    fn: Callable
    polyadic: bool = False


def _mersenne(n):
    from sympy import log
    return Implies(P('integer', log(n + 1, 2)), P('hmersenne', n))


def _big(s):
    # hbig(s) -> positive(s) & ~integer(s): a custom predicate that takes part
    # in propagation and search with vocabulary atoms about the same symbol
    return [Implies(P('hbig', s), P('positive', s)),
            Implies(P('hbig', s), Not(P('integer', s)))]


def _big_negative(s):
    # a *different* meaning for the same predicate name: hbig(s) -> negative(s).
    # Registered after ``big`` was unregistered, a fact the engine cached
    # for hbig under the old meaning is stale.
    return Implies(P('hbig', s), P('negative', s))


def _same(a, b):
    return True if a == b else None


def _undef_real(app):
    # a vocabulary predicate on a class: f(x) is real when x is real
    return Implies(P('real', app.args[0]), P('real', app)) if app.args else None


def _undef_positive(app):
    return Implies(P('hbig', app.args[0]), P('positive', app)) if app.args else None


def _all():
    from sympy import Integer, Symbol, Basic
    from sympy.core.function import AppliedUndef
    return [
        Registration("mersenne", "hmersenne", (Integer,), _mersenne),
        Registration("big", "hbig", (Symbol,), _big),
        Registration("big2", "hbig", (Symbol,), _big_negative),
        Registration("same", "hsame", (Basic, Basic), _same, polyadic=True),
        Registration("undef_real", "real", (AppliedUndef,), _undef_real),
        Registration("undef_big", "positive", (AppliedUndef,), _undef_positive),
    ]


REGISTRATIONS: Dict[str, Registration] = {r.id: r for r in _all()}
CUSTOM_PREDICATES: List[str] = sorted({r.pred for r in REGISTRATIONS.values()
                                       if not r.polyadic and r.pred.startswith("h")})
POLYADIC_PREDICATES: List[str] = sorted({r.pred for r in REGISTRATIONS.values() if r.polyadic})


def apply(reg_id: str) -> None:
    r = REGISTRATIONS[reg_id]
    extensions.register(r.pred, *r.classes)(r.fn)


def remove(reg_id: str) -> None:
    extensions.unregister(REGISTRATIONS[reg_id].pred)


def snapshot():
    return ({k: list(v) for k, v in extensions._handlers.items()},
            {k: list(v) for k, v in extensions._vocab.items()})


def restore(snap) -> None:
    handlers, vocab = snap
    extensions._handlers = {k: list(v) for k, v in handlers.items()}
    extensions._vocab = {k: list(v) for k, v in vocab.items()}
    extensions._node_cache.clear()
    extensions.version += 1


def active_ids() -> List[str]:
    out = []
    for rid, r in REGISTRATIONS.items():
        if any(f is r.fn for _, f in extensions._handlers.get(r.pred, ())):
            out.append(rid)
    return out
