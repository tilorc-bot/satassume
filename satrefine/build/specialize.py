"""Generate conditional rules from identity rows, verify them, write them out.

:func:`specialize` runs the identity engine on a row's left side under every
assumption profile drawn from a catalog and keeps the profiles where the
branch bookkeeping collapsed, minus profiles strictly stronger than another
with the same result and rules equal under a symmetry of the left side.
:func:`verify` checks a generated rule numerically at a sample point of its
hypothesis and at every edge point that satisfies the hypothesis.
:func:`write_family` writes a family's verified rules as a plain rule-table
module under ``generated/``; :func:`satrefine.identities.rules._tables.compile_rule`
is the in-memory equivalent.
"""
from __future__ import annotations

import itertools
import pathlib
from contextlib import nullcontext
import types
from typing import Any, Callable, Iterable

from sympy import And, AppliedPredicate, I, N, Q, S, arg, expand, floor, im, nan, true, zoo

from .. import _upstream
from ..identities import family_module_name
from ..identities.core import driver as _dispatch
from ..identities.core.driver import generated_handlers, live
from ..identities.core.rewrite import Row, bindings, refine, rule_handler, subst
from ..testing.harness import _numerically_equal, _sample_satisfies

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
"""Default per-variable assumption profiles.  A family module may declare its
own ``CATALOG``: a list (every variable) or a dict ``{variable name: list}``
with ``None`` as the default key; entries are ``None``, a predicate or
predicate builder, or a :class:`Literal`."""


def _catalog_for(catalog: Any, v: Any) -> list:
    if isinstance(catalog, dict):
        return list(catalog.get(str(v), catalog.get(None, CATALOG)))
    return list(catalog)

SAMPLE = {Q.positive: 2.3, Q.negative: -1.7, Q.nonnegative: 0.6, Q.real: 0.6, Q.imaginary: 1.9*I,
          Q.complex: 1.2 + 0.7*I, Q.even: 4, Q.odd: 3, Q.integer: 5}

EDGE_POINTS: tuple = (S.Zero, S.One, S.NegativeOne, I, -I)
"""Values every generated rule is checked at when they satisfy its hypothesis;
a family module adds its branch-cut points in ``EDGE_POINTS``."""


def implies(strong: Any, weak: Any) -> bool:
    return all(_upstream.ask(a, strong) is True for a in And.make_args(weak))


records: dict = {}
"""``rule -> (lhs, domain, profile, trace)`` for every rule :func:`specialize` found:
the identity left side and domain it came from, the assumption profile, and the
rows that fired and ``ask`` queries answered ``True`` while the left side was
refined (:func:`._dispatch.tracing`).  The derivation records of the generated
modules are rendered from it."""


def specialize(lhs: Any, domain: Any, catalog: Any = CATALOG) -> list[Row]:
    """The conditional rules of one identity left side.  Runs the live identity rows,
    or, inside a staged generation (:mod:`._stages`), the family's own rows live and
    every other key through the tables installed so far."""
    with (nullcontext() if _dispatch.staged() else live()):
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
            with _dispatch.tracing() as trace:
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


def sample_point(hyp: Any, symbols_needed: Iterable) -> dict | None:
    point = {}
    for ap in And.make_args(hyp):
        if isinstance(ap, AppliedPredicate) and ap.function in SAMPLE and ap.arguments[0].is_Symbol:
            point[ap.arguments[0]] = SAMPLE[ap.function]
    for s in symbols_needed:                     # a variable without a hypothesis: any complex value
        point.setdefault(s, SAMPLE[Q.complex])
    return point


def _agree(lhs: Any, rhs: Any, point: dict) -> bool | None:
    left, right = lhs.subs(point), rhs.subs(point)
    if left in (nan, zoo) or right in (nan, zoo):
        return left == right
    try:
        return _numerically_equal(left, right)
    except Exception:  # noqa: BLE001
        return None


def verify(lhs: Any, rhs: Any, hyp: Any, edges: Iterable = ()) -> bool | None:
    """``True``/``False`` at one sample point of the hypothesis and at every edge point
    (:data:`EDGE_POINTS` plus ``edges``) satisfying it; ``None`` if no point is known."""
    syms = sorted(lhs.free_symbols, key=str)
    point = sample_point(hyp, syms)
    verdict: bool | None = None
    if point is not None and _sample_satisfies(hyp, point):   # a profile on b/2 gives b no sample
        verdict = _agree(lhs, rhs, point)
        if verdict is False:
            return False
    values = list(dict.fromkeys((*EDGE_POINTS, *edges)))
    for combo in itertools.product(values, repeat=len(syms)):
        sample = dict(zip(syms, combo))
        if not _sample_satisfies(hyp, sample):
            continue
        ok = _agree(lhs, rhs, sample)
        if ok is False:
            return False
        if ok is True and verdict is None:
            verdict = True
    return verdict


# ----------------------------------------------------------------------------
# families and generated modules
# ----------------------------------------------------------------------------

def _identity_parts(handler: Any) -> list:
    """The identity handlers inside ``handler`` (itself, or the parts of a ``chain``)."""
    if getattr(handler, "kind", None) == "identity":
        return [handler]
    return [p for part in getattr(handler, "parts", ()) for p in _identity_parts(part)]


def _module_rows(module: types.ModuleType) -> set:
    """Every row of the module's tables (``FACTS``, ``IDENTITIES``, ...)."""
    rows: set = set()
    for v in vars(module).values():
        if isinstance(v, list) and v and all(isinstance(r, tuple) and len(r) in (3, 4) for r in v):
            rows.update(v)
    return rows


def identity_keys(module: types.ModuleType) -> dict[str, list]:
    """``key -> identity handlers`` for the keys whose identity rows (possibly
    inside a chain) come from ``module``'s tables."""
    rows = _module_rows(module)
    out = {}
    for key, h in _upstream.handlers_dict.items():
        parts = [p for p in _identity_parts(h) if any(r in rows for r in p.rows)]
        if parts:
            out[key] = parts
    return out


def generate_family(module: types.ModuleType) -> tuple[list[Row], list[str], dict[Row, bool | None]]:
    """The verified rules of a family module, the keys they serve, and every rule's verdict."""
    keys = identity_keys(module)
    catalog = getattr(module, "CATALOG", CATALOG)
    edges = getattr(module, "EDGE_POINTS", ())
    rules: list[Row] = []
    for handler in dict.fromkeys(h for parts in keys.values() for h in parts):
        rules += specialize_table(handler.rows, catalog)
    verdicts = {rule: verify(*rule, edges=edges) for rule in rules}
    return [r for r in rules if verdicts[r] is True], sorted(keys), verdicts


def table_order(rules: Iterable[Row]) -> list[Row]:
    """The order of a generated table: left sides with structure before a head of bare
    symbols (``log(b**e)`` before ``log(x)``, which would match ``log(x**n)`` too), then
    literal-specialized rows (fewer symbols) first; stable otherwise."""
    return sorted(rules, key=lambda r: (all(t.is_Symbol for t in r[0].args), len(r[0].free_symbols)))


def render_module(family: str, rules: list[Row], keys: list[str], notes: dict | None = None) -> str:
    """The generated module.  Only keys some rule's left side is headed by are
    registered: a key whose identity rows generated nothing (``Pow``, whose fact
    pays off on structured inputs the catalog does not produce) keeps its live
    rows, since a table for the key would switch them off."""
    rules = table_order(rules)
    syms = sorted({s for row in rules for t in row for s in t.free_symbols}, key=str)
    heads = {lhs.func.__name__ for lhs, _, _ in rules}
    keys = [k for k in keys if k in heads]
    lines = [
        f'"""Generated by ``python -m satrefine.tools.refine_specialize --write`` from',
        f"``{family_module_name(family)}``; do not edit.",
        "",
        "A plain rule table: ``RULES`` rows are ``(lhs, rhs, hypothesis)``; each",
        "row was verified numerically at generation time (see ``satrefine.build.specialize``).",
        *(["The comment above a row is its derivation record (see ``satrefine.build.stages``): the",
           "identity row and profile it came from, the rows that fired, the asks used."] if notes else []),
        '"""',
        "from sympy import *  # noqa: F401,F403",
        "from sympy import Q",
        "",
        "from satrefine.identities.core.driver import generated_handlers as handlers_dict",
        "from satrefine.identities.core.rewrite import rule_handler",
        "",
    ]
    if syms:
        comma = "," if len(syms) == 1 else ""   # symbols('x,') is a tuple, symbols('x') a Symbol
        lines.append(f"{', '.join(map(str, syms))}{comma} = symbols('{' '.join(map(str, syms))}{comma}')")
        lines.append("")
    lines.append("RULES = [")
    for lhs, rhs, hyp in rules:
        lines += [f"    {line}" for line in (notes or {}).get((lhs, rhs, hyp), ())]
        lines.append(f"    ({lhs}, {rhs}, {hyp}),")
    lines.append("]")
    lines.append("")
    for key in keys:
        lines.append(f"handlers_dict['{key}'] = rule_handler(RULES)")
    lines.append("")
    return "\n".join(lines)


def generated_path(family: str) -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent / "identities" / "generated" / f"{family}.py"


def write_family(module: types.ModuleType) -> tuple[pathlib.Path, list[Row], dict[Row, bool | None]]:
    family = module.__name__.rsplit(".", 1)[-1]
    rules, keys, verdicts = generate_family(module)
    path = generated_path(family)
    path.write_text(render_module(family, rules, keys))
    return path, rules, verdicts


def family_modules() -> list[types.ModuleType]:
    """The family modules of the package that register an identity handler, except
    those declaring ``SPECIALIZE = False`` (definitions that are cheap to evaluate
    live and have no bookkeeping to collapse, such as ``minmax_deltas``)."""
    from ..identities import family_modules as all_families
    out = []
    for mod in all_families():
        if identity_keys(mod) and getattr(mod, "SPECIALIZE", True):
            out.append(mod)
    return out


__all__ = ["CATALOG", "EDGE_POINTS", "Literal", "SAMPLE", "family_modules",
           "generate_family", "generated_handlers", "generated_path", "identity_keys", "render_module",
           "sample_point", "specialize", "specialize_table", "table_order", "verify", "write_family"]
