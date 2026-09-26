"""Generate conditional rules from identity rows.

:func:`specialize` runs the identity engine on a row's left side under every
assumption profile drawn from a catalog and keeps the profiles where the
branch bookkeeping collapsed, minus profiles strictly stronger than another
with the same result and rules equal under a symmetry of the left side.
:func:`generate_family` runs it over a family's identity rows and keeps the
rules :func:`.verify.verify` confirms numerically; :mod:`.render` writes them
out as a module under ``satrefine/identities/generated/``.
"""
from __future__ import annotations

import itertools
from contextlib import nullcontext
import types
from typing import Any, Iterable

from sympy import And, Q, S, arg, expand, floor, im, true

from .. import _upstream
from . import hooks
from ..identities.core import hooks as _hooks
from ..identities.core.driver import live
from ..identities.core.rewrite import Row, refine
from .verify import verify

class Literal:
    """A catalog entry that substitutes a value for the variable instead of assuming
    something about it, so ``log(b**e)`` under ``Literal(-1)`` on ``e`` yields rules
    for ``log(1/b)``.  Literal exponents collapse bookkeeping that symbolic ones
    cannot (``floor(1/2 - e/4)`` for an imaginary base)."""
    __slots__ = ("value",)

    def __init__(self, value: Any):
        self.value = S(value)

    def __repr__(self) -> str:
        return f"Literal({self.value})"


CATALOG: list = [None, Q.positive, Q.negative, Q.nonnegative, Q.real, Q.imaginary,
                 Q.even, Q.odd, Q.integer, lambda v: Q.even(v/2), lambda v: Q.odd(v/2)]
"""Default per-variable assumption profiles.  A family's own catalog is in
:data:`.specs.CATALOGS` (a family module may still declare ``CATALOG``): a list
(every variable) or a dict ``{variable name: list}`` with ``None`` as the default key; entries are ``None``, a predicate or
predicate builder, or a :class:`Literal`."""


def _catalog_for(catalog: Any, v: Any) -> list:
    if isinstance(catalog, dict):
        return list(catalog.get(str(v), catalog.get(None, CATALOG)))
    return list(catalog)

def implies(strong: Any, weak: Any) -> bool:
    return all(_upstream.ask(a, strong) is True for a in And.make_args(weak))


records: dict = {}
"""``rule -> (lhs, domain, profile, trace)`` for every rule :func:`specialize` found:
the identity left side and domain it came from, the assumption profile, and the
rows that fired and ``ask`` queries answered ``True`` while the left side was
refined (:func:`.hooks.tracing`).  The derivation records of the generated
modules are rendered from it."""


def specialize(lhs: Any, domain: Any, catalog: Any = CATALOG) -> list[Row]:
    """The conditional rules of one identity left side.  Runs the live identity rows,
    or, when an observer supplies the tables (a staged generation, :mod:`.stages`),
    the family's own rows live and every other key through the tables installed so far."""
    staged = bool(_hooks.observer) and _hooks.observer[-1].tables is not None
    with (nullcontext() if staged else live()):
        return _specialize(lhs, domain, catalog)


def _specialize(lhs: Any, domain: Any, catalog: Any) -> list[Row]:
    vars_ = sorted(lhs.free_symbols, key=str)
    found: list[tuple[Any, Any, Any]] = []          # (lhs with literals, rhs, hypothesis)
    for choice in itertools.product(*[_catalog_for(catalog, v) for v in vars_]):
        literals = {v: c.value for c, v in zip(choice, vars_) if isinstance(c, Literal)}
        atoms = [c(v) for c, v in zip(choice, vars_) if c is not None and not isinstance(c, Literal)]
        profile = And(*atoms) if atoms else true
        L, D = lhs.xreplace(literals), domain.xreplace(literals) if literals else domain
        if L.is_Atom or L == lhs and literals:
            continue
        try:
            with hooks.tracing() as trace:
                rhs = refine(L, profile & D)
        except ValueError:                       # inconsistent profile
            continue
        if rhs == L or rhs.has(floor, im) or (rhs.has(arg) and not L.has(arg)):   # arg(p*r) -> arg(p) is a rule
            continue
        residual = [d for d in And.make_args(D) if d is not S.true
                    and not (atoms and _upstream.ask(d, profile) is True)
                    and _upstream.ask(d) is not True]
        found.append((L, expand(rhs), And(profile, *residual)))
        records.setdefault(found[-1], (lhs, domain, profile, trace))
    kept: list[tuple[Any, Any, Any]] = []
    for L, rhs, hyp in found:
        if any(L == L2 and rhs == rhs2 and implies(hyp, hyp2) for L2, rhs2, hyp2 in kept):
            continue
        kept = [(L2, rhs2, hyp2) for L2, rhs2, hyp2 in kept
                if not (L == L2 and rhs == rhs2 and implies(hyp2, hyp))]
        kept.append((L, rhs, hyp))
    out: list[tuple[Any, Any, Any]] = []
    for L, rhs, hyp in kept:
        perms = [dict(zip(vars_, q)) for q in itertools.permutations(vars_)]
        if any((L.xreplace(m), rhs.xreplace(m), hyp.xreplace(m)) in out for m in perms if L.xreplace(m) == L):
            continue
        out.append((L, rhs, hyp))
    return out


def specialize_table(identities: Iterable[Row], catalog: Any = CATALOG) -> list[Row]:
    """Specialize every distinct left side of an identity table."""
    seen, rules = set(), []
    for lhs, _rhs, dom in identities:
        if (lhs, dom) in seen:
            continue
        seen.add((lhs, dom))
        rules += specialize(lhs, dom, catalog)
    return rules


# ----------------------------------------------------------------------------
# families
# ----------------------------------------------------------------------------

def _identity_parts(handler: Any) -> list:
    """The identity handlers inside ``handler`` (itself, or the parts of a ``chain``)."""
    if getattr(handler, "kind", None) == "identity":
        return [handler]
    return [p for part in getattr(handler, "parts", ()) for p in _identity_parts(part)]


_TABLE_ORDER = ("DEFINITIONS", "FACTS", "RULES", "SPLITS", "EXP_FORMS", "NEGATIVE_BASE", "IDENTITIES")


def row_tables(module: types.ModuleType) -> dict[str, list]:
    """``name -> rows``: the module-level lists of rows (3- or 4-tuples) of a family
    module, the names of :data:`_TABLE_ORDER` first, then the others by name."""
    tables = {n: v for n, v in vars(module).items()
              if isinstance(v, list) and v and all(isinstance(r, tuple) and len(r) in (3, 4) for r in v)}
    return {n: tables[n] for n in [n for n in _TABLE_ORDER if n in tables] + sorted(set(tables) - set(_TABLE_ORDER))}


def identity_keys(module: types.ModuleType) -> dict[str, list]:
    """``key -> identity handlers`` for the keys whose identity rows (possibly
    inside a chain) come from ``module``'s tables."""
    rows = {row for table in row_tables(module).values() for row in table}
    out = {}
    for key, h in _upstream.handlers_dict.items():
        parts = [p for p in _identity_parts(h) if any(r in rows for r in p.rows)]
        if parts:
            out[key] = parts
    return out


def generate_family(module: types.ModuleType) -> tuple[list[Row], list[str], dict[Row, bool | None]]:
    """The verified rules of a family module, the keys they serve, and every rule's verdict."""
    keys = identity_keys(module)
    from .specs import CATALOGS, EDGE_POINTS
    family = module.__name__.rsplit(".", 1)[-1]
    catalog = CATALOGS.get(family, getattr(module, "CATALOG", CATALOG))
    edges = EDGE_POINTS.get(family, ())
    rules: list[Row] = []
    for handler in dict.fromkeys(h for parts in keys.values() for h in parts):
        rules += specialize_table(handler.rows, catalog)
    verdicts = {rule: verify(*rule, edges=edges) for rule in rules}
    return [r for r in rules if verdicts[r] is True], sorted(keys), verdicts


def family_modules() -> list[types.ModuleType]:
    """The family modules of the package that register an identity handler, except
    those in :data:`.specs.NOT_GENERATED`."""
    from ..identities import family_modules as all_families
    from .specs import NOT_GENERATED
    out = []
    for mod in all_families():
        if identity_keys(mod) and mod.__name__.rsplit(".", 1)[-1] not in NOT_GENERATED:
            out.append(mod)
    return out
