"""Staged derivation: the stage manifest and the fixpoint over the generated tables.

Every fact about a function is a hand-stated row (the family modules' tables:
the stage 0 rows) or a generated rule (``generated/<family>.py``).  Families
are generated in stage order (:data:`STAGES`); each family is specialized with
its own keys on their identity rows (:func:`._dispatch.live_for`) and every
other key through the tables generated so far (:func:`._dispatch.tables`), so a
later stage builds on the compiled rules of the earlier ones.  Rules are
verified before they are installed, every round.  A round regenerates the
families whose inputs (the other families' tables) changed since their last
generation; the loop stops when a round changes no table and fails loudly after
:data:`MAX_ROUNDS`.  Cycles between stages (``im(log w)`` needs ``log``,
``log``'s rules need ``im``) are what the later rounds are for.

Each generated rule carries a derivation record (:data:`._specialize.records`):
the identity row and profile it came from, the rows and generated rules that
fired while it was derived, and the ``ask`` queries answered ``True``.
"""
from __future__ import annotations

import time
import types
from typing import Any, Callable

from sympy import sympify

from . import _dispatch, _specialize
from ._engine import Row, rule_handler

STAGES: list[tuple[int, list[str]]] = [
    (1, ["integer_funcs", "complex_parts"]),   # floor and frac; re, im, arg, Abs, sign, conjugate
    (2, ["power_exp_log"]),                    # exp, log (and Pow, stage 3, stated in the same family)
    (4, ["trig", "hyperbolic"]),               # through their exponential forms
    (5, ["inverse"]),                          # the wraps
]
"""``(stage, families)`` in generation order; stage 0 is the stated rows of every family."""

MAX_ROUNDS = 5


def ordered_families() -> list[types.ModuleType]:
    """The generating family modules (:func:`._specialize.family_modules`) in stage order;
    a generating family missing from :data:`STAGES` is an error."""
    modules = {m.__name__.rsplit(".", 1)[-1]: m for m in _specialize.family_modules()}
    order = [name for _stage, names in STAGES for name in names if name in modules]
    missing = sorted(set(modules) - set(order))
    if missing:
        raise RuntimeError(f"families with identity rows missing from the stage manifest: {missing}")
    return [modules[name] for name in order]


def family_name(module: types.ModuleType) -> str:
    return module.__name__.rsplit(".", 1)[-1]


def install(rules: list[Row], keys: list[str], into: dict | None = None) -> None:
    """Register ``rules`` as the generated table of ``keys`` (the keys some rule's left side is headed by),
    as the generated module does on import."""
    into = _dispatch.generated_handlers if into is None else into
    heads = {lhs.func.__name__ for lhs, _, _ in rules}
    handler = rule_handler(rules)
    for key in keys:
        if key in heads:
            into[key] = handler


def generate_one(module: types.ModuleType) -> tuple[list[Row], list[str], dict]:
    """One family against the tables installed now: its keys live, every other key through its table."""
    keys = sorted(_specialize.identity_keys(module))
    _specialize.records.clear()
    with _dispatch.tables(), _dispatch.live_for(keys):
        rules, keys, verdicts = _specialize.generate_family(module)
    return rules, keys, verdicts


def generate(modules: list[types.ModuleType] | None = None, max_rounds: int = MAX_ROUNDS,
             log: Callable[[str], None] = print) -> dict[str, dict]:
    """Run the stages to a fixpoint from empty tables.

    Returns ``family -> {"rules", "keys", "verdicts", "records", "rounds", "seconds"}``
    (``seconds``: generation time per round).  The installed tables are restored
    afterwards."""
    modules = ordered_families() if modules is None else modules
    saved = dict(_dispatch.generated_handlers)
    _dispatch.generated_handlers.clear()
    out: dict[str, dict] = {}
    inputs: dict[str, Any] = {}
    try:
        for rnd in range(1, max_rounds + 1):
            changed = []
            for module in modules:
                fam = family_name(module)
                seen = tuple((f, tuple(out[f]["rules"])) for f in sorted(out) if f != fam)
                if inputs.get(fam) == seen:
                    continue
                t0 = time.time()
                rules, keys, verdicts = generate_one(module)
                seconds = time.time() - t0
                inputs[fam] = seen
                entry = out.setdefault(fam, {"rules": None, "rounds": [], "seconds": []})
                entry["seconds"].append(round(seconds, 1))
                log(f"round {rnd} {fam}: {len(rules)} rules in {seconds:.0f}s")
                if entry["rules"] != rules:
                    entry.update(rules=rules, keys=keys, verdicts=verdicts,
                                 records={r: _specialize.records.get(r) for r in rules})
                    entry["rounds"].append(rnd)
                    install(rules, keys)
                    changed.append(fam)
            if not changed:
                return out
        raise RuntimeError(f"no fixpoint after {max_rounds} rounds; still changing: {changed}")
    finally:
        _dispatch.generated_handlers.clear()
        _dispatch.generated_handlers.update(saved)


# ----------------------------------------------------------------------------
# derivation records
# ----------------------------------------------------------------------------

_TABLE_ORDER = ("DEFINITIONS", "FACTS", "RULES", "SPLITS", "EXP_FORMS", "NEGATIVE_BASE", "IDENTITIES")


def _key(row: Any) -> tuple:
    return tuple(sympify(t) for t in row[:3])


def row_labels(generated: dict[str, dict] | None = None) -> dict[tuple, str]:
    """``row -> "family.TABLE[i]"`` for the stated rows of every family module, and
    ``"family.generated[i]"`` for the rows of the generated tables in ``generated``."""
    import importlib
    import pkgutil
    from .. import handlers_identities as package
    labels: dict[tuple, str] = {}
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_") or info.ispkg:
            continue
        mod = importlib.import_module(f"{package.__name__}.{info.name}")
        tables = [n for n in _TABLE_ORDER if isinstance(getattr(mod, n, None), list)]
        tables += sorted(n for n, v in vars(mod).items() if n.isupper() and n not in tables and isinstance(v, list)
                         and v and all(isinstance(r, tuple) and len(r) in (3, 4) for r in v))
        for name in tables:
            for i, row in enumerate(getattr(mod, name)):
                if isinstance(row, tuple) and len(row) in (3, 4):
                    try:
                        labels.setdefault(_key(row), f"{info.name}.{name}[{i}]")
                    except Exception:  # noqa: BLE001  (a row SymPy cannot rebuild)
                        pass
    for fam, entry in (generated or {}).items():
        for i, row in enumerate(entry["rules"]):
            labels.setdefault(_key(row), f"{fam}.generated[{i}]")
    return labels


def record_lines(record: Any, labels: dict[tuple, str]) -> list[str]:
    """The comment lines of one derivation record."""
    if record is None:
        return ["# derivation: not recorded"]
    lhs, domain, profile, trace = record
    source = next((lab for key, lab in labels.items() if key[0] == lhs and key[2] == domain), None)
    fired = list(dict.fromkeys(labels.get(_key(row), f"{kind} {row[0]} -> {row[1]}")
                               for kind, row in trace if kind != "ask"))
    asks = list(dict.fromkeys(str(p) for kind, p in trace if kind == "ask"))
    lines = [f"# from {source or lhs} under {profile}"]
    if fired:
        lines.append("#   fired: " + ", ".join(fired))
    if asks:
        lines.append("#   asks: " + ", ".join(asks))
    return lines


__all__ = ["MAX_ROUNDS", "STAGES", "family_name", "generate", "generate_one", "install", "ordered_families",
           "record_lines", "row_labels"]
