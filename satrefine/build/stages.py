"""Staged derivation: the stage manifest and the fixpoint over the generated tables.

Every fact about a function is a hand-stated row (the family modules' tables:
the stage 0 rows) or a generated rule (``generated/<family>.py``).  Families
are generated in stage order (:data:`STAGES`); each family is specialized with
its own keys on their identity rows and every other key through the tables
generated so far (the stages' own dict of installed tables, supplied to the
driver by an observer, :func:`..identities.core.driver.observing`), so a
later stage builds on the compiled rules of the earlier ones.  Rules are
verified before they are installed, every round.  A round regenerates the
families whose inputs changed since their last generation: the tables at the
keys the dispatcher looked up while generating them (what the observer's
``tables`` was asked for); the loop stops when a round changes no table and fails loudly after
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

from ..identities.core import driver as _dispatch
from ..identities.core.rewrite import Row, rule_handler
from . import specialize as _specialize
from .render import table_order

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


def install(rules: list[Row], keys: list[str], into: dict) -> None:
    """Register ``rules`` in ``into`` as the generated table of ``keys`` (the keys some rule's left side
    is headed by), as the generated module does on import."""
    heads = {lhs.func.__name__ for lhs, _, _ in rules}
    handler = rule_handler(table_order(rules))
    for key in keys:
        if key in heads:
            into[key] = handler
        else:
            into.pop(key, None)          # the family no longer has a table for it


def generate_one(module: types.ModuleType, consulted: set | None = None,
                 installed: dict | None = None) -> tuple[list[Row], list[str], dict]:
    """One family against the tables in ``installed`` (default: the committed ones the driver
    uses): its keys live, every other key through its table.  ``consulted`` collects the keys
    whose table the dispatcher looked up."""
    own = set(_specialize.identity_keys(module))
    installed = _dispatch.generated_handlers if installed is None else installed
    consulted = set() if consulted is None else consulted

    def tables(key: str) -> Any:
        if key in own:
            return None
        consulted.add(key)
        return installed.get(key)
    _specialize.records.clear()
    with _dispatch.observing(tables=tables):
        return _specialize.generate_family(module)


def generate(modules: list[types.ModuleType] | None = None, max_rounds: int = MAX_ROUNDS,
             log: Callable[[str], None] = print) -> dict[str, dict]:
    """Run the stages to a fixpoint from empty tables.

    Returns ``family -> {"rules", "keys", "verdicts", "records", "rounds", "seconds"}``
    (``seconds``: generation time per round).  The tables are installed in a dict of
    the stages' own, not in the driver's."""
    modules = ordered_families() if modules is None else modules
    installed: dict = {}             # key -> the handler of the table generated for it so far
    out: dict[str, dict] = {}
    inputs: dict[str, dict] = {}     # family -> {key it looked up: the handler installed there then}
    for rnd in range(1, max_rounds + 1):
        changed = []
        for module in modules:
            fam = family_name(module)
            if fam in inputs and all(installed.get(k) is v for k, v in inputs[fam].items()):
                continue                     # no table it looked up has changed: same result
            t0 = time.time()
            consulted: set = set()
            rules, keys, verdicts = generate_one(module, consulted, installed)
            seconds = time.time() - t0
            inputs[fam] = {k: installed.get(k) for k in consulted}
            entry = out.setdefault(fam, {"rules": None, "rounds": [], "seconds": []})
            entry["seconds"].append(round(seconds, 1))
            log(f"round {rnd} {fam}: {len(rules)} rules in {seconds:.0f}s")
            if entry["rules"] != rules:
                previous = entry.get("records", {})
                entry.update(rules=rules, keys=keys, verdicts=verdicts,
                             records={r: previous[r] if r in previous else (rnd, _specialize.records.get(r))
                                      for r in rules})
                entry["rounds"].append(rnd)
                install(rules, keys, installed)   # a new handler for each key whose table changed
                changed.append(fam)
        if not changed:
            return out
    raise RuntimeError(f"no fixpoint after {max_rounds} rounds; still changing: {changed}")


# ----------------------------------------------------------------------------
# derivation records
# ----------------------------------------------------------------------------

def _key(row: Any) -> tuple:
    return tuple(sympify(t) for t in row[:3])


def row_labels(generated: dict[str, dict] | None = None) -> dict[tuple, str]:
    """``row -> "family.TABLE[i]"`` for the stated rows of every family module, and
    ``"family.generated[i]"`` for the rows of the generated tables in ``generated``."""
    import importlib
    from ..identities import families, family_module_name
    labels: dict[tuple, str] = {}
    for family in families():
        for name, rows in _specialize.row_tables(importlib.import_module(family_module_name(family))).items():
            for i, row in enumerate(rows):
                try:
                    labels.setdefault(_key(row), f"{family}.{name}[{i}]")
                except Exception:  # noqa: BLE001  (a row SymPy cannot rebuild)
                    pass
    for fam, entry in (generated or {}).items():
        for i, row in enumerate(entry["rules"]):
            labels.setdefault(_key(row), f"{fam}.generated[{i}]")
    return labels


def record_lines(record: Any, labels: dict[tuple, str]) -> list[str]:
    """The comment lines of one derivation record ``(round, (lhs, domain, profile, trace))``."""
    rnd, record = record if isinstance(record, tuple) and len(record) == 2 else (None, record)
    if record is None:
        return ["# derivation: not recorded"]
    lhs, domain, profile, trace = record
    source = next((lab for key, lab in labels.items() if key[0] == lhs and key[2] == domain), None)
    fired = list(dict.fromkeys(labels.get(_key(row), f"{kind} {row[0]} -> {row[1]}")
                               for kind, row in trace if kind != "ask"))
    asks = list(dict.fromkeys(str(p) for kind, p in trace if kind == "ask"))
    lines = [f"# {f'round {rnd}: ' if rnd else ''}from {source or lhs} under {profile}"]
    if fired:
        lines.append("#   fired: " + ", ".join(fired))
    if asks:
        lines.append("#   asks: " + ", ".join(asks))
    return lines
