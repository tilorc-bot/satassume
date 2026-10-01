"""The differential checker.

A *stream* is a list of items: ``Ask(prop, assum)`` queries and
``Event("register" | "unregister", id)`` changes of the extension registry
(see ``harness.registry``).  ``execute`` runs a stream through one
long-lived engine and, for every query, compares the answer with a *clean
reference* computed right after it:

* ``ReferenceLevel.ENGINE``: a fresh ``Engine`` of the same configuration
  in the same process.  This resets everything ``Engine`` owns (fact
  cache, answer memo, splits, sessions, failed sets, transfer bases) but
  keeps the module-level memos and SymPy's caches (``harness.state``);
* ``ReferenceLevel.MODULE``: as above after ``reset_module_state()`` (all
  module-level memos of the engine and SymPy's ``cacheit`` cache emptied);
* ``ReferenceLevel.PROCESS``: the single query in a fresh interpreter
  (``python -m harness repro``), optionally under another
  ``PYTHONHASHSEED``.  Used to confirm discrepancies, not per query.

Registrations in force when a query runs are the same for the engine
under test and for the reference (they are configuration, not history):
events are applied to the global registry as the stream is executed and
the registry is restored afterwards.

Several *orders* of one stream are run (``order_stream``): forward,
reverse, seeded shuffles, grouped by assumption set (maximal session
reuse), interleaved across sets (LRU churn) and repeated (memo hits).
Events pin their positions; only the queries between two events are
permuted.

A ``Discrepancy`` records the query, both answers and the prefix of the
stream that ran before it.  ``shrink`` reduces the prefix by ddmin to a
minimal sequence after which the query still answers differently from a
fresh engine, and ``write_repro`` saves it with the exact command to
replay it in a fresh process.
"""
from __future__ import annotations

import dataclasses
import json
import os
import random
import subprocess
import sys
import time
from enum import IntEnum
from typing import Any, Callable, Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple, Union

from . import registry as reg
from .outcomes import outcome
from .state import EngineConfig, reset_module_state
from .sympy_io import from_srepr, to_srepr


class Ask(NamedTuple):
    prop: Any
    assum: Any = True

    def __str__(self) -> str:
        return f"ask({self.prop}, {self.assum})"


class Event(NamedTuple):
    kind: str          # "register" | "unregister"
    reg_id: str

    def __str__(self) -> str:
        return f"{self.kind}({self.reg_id})"


Item = Union[Ask, Event]


class ReferenceLevel(IntEnum):
    NONE = 0
    ENGINE = 1
    MODULE = 2
    PROCESS = 3


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------

def item_to_json(it: Item) -> Dict[str, Any]:
    """srepr only: readable, and no opaque executable data in the files.
    srepr is rebuilt with evaluation, which can give another tree than an
    unevaluated original; such an item is marked ``"srepr_exact": false``."""
    if isinstance(it, Event):
        return {"kind": it.kind, "id": it.reg_id}
    d = {"kind": "ask", "prop": to_srepr(it.prop), "assum": to_srepr(it.assum)}
    try:
        exact = (from_srepr(d["prop"]), from_srepr(d["assum"])) == (it.prop, it.assum)
    except Exception:  # noqa: BLE001 - not rebuildable at all
        exact = False
    if not exact:
        d["srepr_exact"] = False
    return d


def item_from_json(d: Dict[str, Any]) -> Item:
    if d["kind"] == "ask":
        return Ask(from_srepr(d["prop"]), from_srepr(d["assum"]))
    return Event(d["kind"], d["id"])


KINDS = ("contradiction", "none-vs-definite", "raise-vs-definite", "raise-vs-none", "error")


def kind_of(warm: str, ref: str) -> str:
    """The class of a disagreement between two answers."""
    a, b = sorted((warm, ref))
    if a.startswith("Error") or b.startswith("Error"):
        return "error"
    if {a, b} == {"True", "False"}:
        return "contradiction"
    if "ValueError" in (a, b):
        return "raise-vs-none" if "None" in (a, b) else "raise-vs-definite"
    return "none-vs-definite"


def write_stream(path: str, items: Sequence[Item], meta: Optional[dict] = None) -> None:
    with open(path, "w") as f:
        json.dump({"meta": meta or {}, "items": [item_to_json(i) for i in items]}, f)


# --------------------------------------------------------------------------
# orders
# --------------------------------------------------------------------------

ORDERS = ("forward", "reverse", "shuffle", "grouped", "interleave", "repeat", "grouped-reverse")


def _segments(items: Sequence[Item]) -> List[Tuple[Optional[Event], List[Ask]]]:
    segs: List[Tuple[Optional[Event], List[Ask]]] = [(None, [])]
    for it in items:
        if isinstance(it, Event):
            segs.append((it, []))
        else:
            segs[-1][1].append(it)
    return segs


def _group_key(a: Ask) -> str:
    return to_srepr(a.assum)


def _permute(asks: List[Ask], order: str, rng: random.Random) -> List[Ask]:
    if order == "forward":
        return list(asks)
    if order == "reverse":
        return asks[::-1]
    if order == "shuffle":
        out = list(asks)
        rng.shuffle(out)
        return out
    if order == "grouped":
        return sorted(asks, key=_group_key)
    if order == "grouped-reverse":
        return sorted(asks, key=_group_key, reverse=True)
    if order == "interleave":
        groups: Dict[str, List[Ask]] = {}
        for a in asks:
            groups.setdefault(_group_key(a), []).append(a)
        out: List[Ask] = []
        lists = list(groups.values())
        while lists:
            nxt = []
            for lst in lists:
                out.append(lst.pop(0))
                if lst:
                    nxt.append(lst)
            lists = nxt
        return out
    if order == "repeat":
        return list(asks) + list(asks)
    raise ValueError(f"unknown order {order!r}")


def order_stream(items: Sequence[Item], order: str, seed: int = 0) -> List[Item]:
    rng = random.Random(seed)
    out: List[Item] = []
    for ev, asks in _segments(items):
        if ev is not None:
            out.append(ev)
        out.extend(_permute(asks, order, rng))
    return out


# --------------------------------------------------------------------------
# execution
# --------------------------------------------------------------------------

def apply_event(ev: Event) -> None:
    if ev.kind == "register":
        reg.apply(ev.reg_id)
    elif ev.kind == "unregister":
        reg.remove(ev.reg_id)
    else:
        raise ValueError(ev)


def reference(item: Ask, config: EngineConfig, level: int, hashseed: Optional[int] = None) -> str:
    """The clean answer of ``item`` at ``level`` (under the registrations
    currently in force)."""
    if level == ReferenceLevel.PROCESS:
        return process_outcome(item, config, hashseed=hashseed)
    if level == ReferenceLevel.MODULE:
        reset_module_state()
    return outcome(item.prop, item.assum, config.make())


@dataclasses.dataclass
class Row:
    index: int
    item: Ask
    warm: str
    ref: Optional[str]
    ms: float = 0.0

    @property
    def mismatch(self) -> bool:
        return self.ref is not None and self.warm != self.ref


def execute(items: Sequence[Item], config: EngineConfig,
            ref_level: int = ReferenceLevel.ENGINE, engine=None,
            on_row: Optional[Callable[[Row], None]] = None,
            ref_for_last: bool = False) -> Tuple[List[Row], Any]:
    """Run ``items`` through one engine (``engine`` or a new one of
    ``config``).  Every ``Ask`` gives a ``Row`` with the engine's answer and
    the reference at ``ref_level`` (None at level NONE, except that
    ``ref_for_last`` always references the last query, at level ENGINE).
    The extension registry is restored afterwards."""
    snap = reg.snapshot()
    eng = engine if engine is not None else config.make()
    rows: List[Row] = []
    last = max((i for i, it in enumerate(items) if isinstance(it, Ask)), default=-1)
    try:
        for i, it in enumerate(items):
            if isinstance(it, Event):
                apply_event(it)
                continue
            t0 = time.perf_counter()
            warm = outcome(it.prop, it.assum, eng)
            ms = (time.perf_counter() - t0) * 1000
            ref = None
            if ref_level:
                ref = reference(it, config, ref_level)
            elif ref_for_last and i == last:
                ref = reference(it, config, ReferenceLevel.ENGINE)
            row = Row(i, it, warm, ref, ms)
            rows.append(row)
            if on_row is not None:
                on_row(row)
    finally:
        reg.restore(snap)
    return rows, eng


# --------------------------------------------------------------------------
# discrepancies, shrinking, repros
# --------------------------------------------------------------------------

@dataclasses.dataclass
class Discrepancy:
    config: EngineConfig
    order: str
    index: int
    item: Ask
    warm: str
    ref: str
    ref_level: int
    prefix: List[Item]
    source: str = ""
    shrunk: Optional[List[Item]] = None
    shrunk_warm: Optional[str] = None
    shrunk_ref: Optional[str] = None
    confirmations: Dict[str, Any] = dataclasses.field(default_factory=dict)

    group_size: int = 1

    @property
    def kind(self) -> str:
        return kind_of(self.warm, self.ref)

    def summary(self) -> str:
        n = len(self.prefix) if self.shrunk is None else len(self.shrunk)
        fam = self.confirmations.get("family")
        tag = f" family={fam} carrier={'+'.join(self.confirmations.get('carrier') or ['?'])}" if fam else ""
        return (f"[{self.config.name}/{self.order}#{self.index} {self.kind}] {self.item}: "
                f"engine={self.warm} reference={self.ref} (prefix {n} items"
                f"{'' if self.shrunk is None else ', shrunk'}; {self.group_size} in this group){tag}")

    def to_json(self) -> Dict[str, Any]:
        seq = self.prefix if self.shrunk is None else self.shrunk
        return {
            "config": self.config.to_dict(), "kind": self.kind, "group_size": self.group_size,
            "order": self.order, "index": self.index, "source": self.source,
            "item": item_to_json(self.item), "warm": self.warm, "ref": self.ref,
            "ref_level": int(self.ref_level),
            "prefix": [item_to_json(i) for i in seq],
            "full_prefix_len": len(self.prefix),
            "shrunk": self.shrunk is not None,
            "confirmations": self.confirmations,
        }


def _reproduces(prefix: Sequence[Item], item: Ask, config: EngineConfig,
                ref_level: int = ReferenceLevel.ENGINE) -> Tuple[bool, str, str]:
    """Run ``prefix`` then ``item`` in a fresh engine; True if the answer
    differs from the reference computed right after (under the same
    registrations)."""
    snap = reg.snapshot()
    try:
        eng = config.make()
        for it in prefix:
            if isinstance(it, Event):
                apply_event(it)
            else:
                outcome(it.prop, it.assum, eng)
        warm = outcome(item.prop, item.assum, eng)
        ref = reference(item, config, ref_level if ref_level else ReferenceLevel.ENGINE)
    finally:
        reg.restore(snap)
    return warm != ref, warm, ref


def ddmin(seq: List[Item], test: Callable[[List[Item]], bool], max_tests: int = 2000) -> List[Item]:
    """Zeller's ddmin: a 1-minimal subsequence of ``seq`` for which
    ``test`` holds (``test(seq)`` must hold)."""
    n = 2
    tests = 0
    while len(seq) >= 2 and tests < max_tests:
        chunk = max(1, len(seq) // n)
        subsets = [seq[i:i + chunk] for i in range(0, len(seq), chunk)]
        reduced = False
        for i, sub in enumerate(subsets):
            if test(sub):
                tests += 1
                seq, n, reduced = sub, 2, True
                break
            tests += 1
        if reduced:
            continue
        if n > 2 or len(subsets) > 2:
            for i in range(len(subsets)):
                comp = [x for j, s in enumerate(subsets) if j != i for x in s]
                tests += 1
                if test(comp):
                    seq, n, reduced = comp, max(n - 1, 2), True
                    break
        if reduced:
            continue
        if n >= len(seq):
            break
        n = min(n * 2, len(seq))
    return seq


def shrink(d: Discrepancy, max_tests: int = 2000, progress: Optional[Callable[[str], None]] = None) -> Discrepancy:
    """Shrink the prefix of ``d`` to a minimal sequence after which the
    query still answers differently from a fresh engine.  Also tries to
    drop the assumptions of prefix queries (a context-free query pollutes
    less state) so the repro is easier to read."""
    ok, warm, ref = _reproduces(d.prefix, d.item, d.config, d.ref_level)
    if not ok:
        # not reproducible from the prefix alone (an order-independent
        # instability?): keep the full prefix, say so
        d.shrunk = None
        d.confirmations["reproduces_from_prefix"] = False
        return d
    d.confirmations["reproduces_from_prefix"] = True

    def test(seq: List[Item]) -> bool:
        return _reproduces(seq, d.item, d.config, d.ref_level)[0]

    seq = ddmin(list(d.prefix), test, max_tests)
    # try simplifying the remaining prefix queries: drop assumptions, or
    # replace the proposition by the query's own
    changed = True
    while changed:
        changed = False
        for i, it in enumerate(seq):
            if not isinstance(it, Ask):
                continue
            for cand in (Ask(it.prop, True), Ask(d.item.prop, it.assum)):
                if cand == it:
                    continue
                trial = seq[:i] + [cand] + seq[i + 1:]
                if test(trial):
                    seq, changed = trial, True
                    break
    d.shrunk = seq
    _, d.shrunk_warm, d.shrunk_ref = _reproduces(seq, d.item, d.config, d.ref_level)
    if progress:
        progress(f"shrunk {len(d.prefix)} -> {len(seq)} items")
    return d


# --------------------------------------------------------------------------
# attribution: which engine state carries the dependence
# --------------------------------------------------------------------------

#: engine-level state the attribution clears one at a time (``harness.state``)
STATE_PARTS = ("cache", "sessions", "answers", "splits", "failed")


def clear_state(eng, part: str) -> None:
    if part in ("cache", "all"):
        eng.cache.store.clear()
        eng.custom_cache.store.clear()
    if part in ("sessions", "all"):
        eng._context_sessions.clear()
    if part in ("answers", "all"):
        eng.answers.clear()
    if part in ("splits", "all"):
        eng.splits.clear()
    if part in ("failed", "all"):
        eng._failed.clear()
    if part not in STATE_PARTS + ("all",):
        raise ValueError(part)


def attribute(d: Discrepancy) -> Dict[str, Any]:
    """Re-run the (shrunk) prefix, clear one engine state, ask the query:
    the answer after clearing each part.  A part whose clearing restores
    the reference answer *carries* the dependence (``carrier``); with
    ``all`` cleared the answer must be the reference's (else the dependence
    is outside the engine object: a module memo, or SymPy's cache)."""
    seq = d.prefix if d.shrunk is None else d.shrunk
    ref = d.shrunk_ref if d.shrunk_ref is not None else d.ref
    out: Dict[str, str] = {}
    for part in STATE_PARTS + ("all",):
        snap = reg.snapshot()
        try:
            eng = d.config.make()
            for it in seq:
                if isinstance(it, Event):
                    apply_event(it)
                else:
                    outcome(it.prop, it.assum, eng)
            clear_state(eng, part)
            out[part] = outcome(d.item.prop, d.item.assum, eng)
        finally:
            reg.restore(snap)
    carrier = [p for p in STATE_PARTS if out[p] == ref]
    if not carrier and out["all"] == ref:
        # held redundantly: try pairs (the cache and the session both hold
        # a fact, for instance)
        import itertools
        for a, b in itertools.combinations(STATE_PARTS, 2):
            snap = reg.snapshot()
            try:
                eng = d.config.make()
                for it in seq:
                    if isinstance(it, Event):
                        apply_event(it)
                    else:
                        outcome(it.prop, it.assum, eng)
                clear_state(eng, a)
                clear_state(eng, b)
                out[a + "+" + b] = r = outcome(d.item.prop, d.item.assum, eng)
            finally:
                reg.restore(snap)
            if r == ref:
                carrier = [a + "+" + b]
                break
    d.confirmations["without"] = out
    d.confirmations["carrier"] = carrier
    d.confirmations["outside_engine"] = out["all"] != ref
    if _lazy_shape(d):
        # a relation query in the prefix, none in the query: the session's
        # relation glue or its predicate transfer answers; which one is
        # decided by replaying with transfer switched off
        d.confirmations["without_transfer"] = _replay(d, d.config.replace(transfer=False))
    if "sessions" in carrier:
        # does the prefix act by merely *mentioning* its terms in the
        # session (the relation glue links every term a query under the
        # set mentions, for good), rather than by what it derived or
        # learnt?  Replay with each prefix query replaced by one that only
        # visits the same terms
        d.confirmations["mention_only"] = _replay(d, d.config, _mention_only(seq))
    d.confirmations["family"] = family_of(d)
    return out


def _mention_only(seq: Sequence[Item]) -> List[Item]:
    """Each query of ``seq`` replaced by ``Q.commutative`` of every term its
    vocabulary atoms mention, and by its relation atoms alone (bare, one
    query each: they are what switches the relation glue on and links
    their sides), under the same assumptions: the terms are visited and
    linked, and nothing is derived from the query's Boolean structure."""
    from sympy import Q
    from sympy.logic.boolalg import And
    from .lazy import atom_args, relation_atoms
    out: List[Item] = []
    for it in seq:
        if isinstance(it, Event):
            out.append(it)
            continue
        for r in relation_atoms(it.prop):
            out.append(Ask(r, it.assum))
        terms = [t for t in dict.fromkeys(atom_args(it.prop)) if getattr(t, "free_symbols", None)]
        if terms:
            out.append(Ask(And(*[Q.commutative(t) for t in terms]) if len(terms) > 1
                           else Q.commutative(terms[0]), it.assum))
    return out


def _replay(d: Discrepancy, config: EngineConfig, seq: Optional[Sequence[Item]] = None) -> str:
    """The engine's answer after the (shrunk) prefix, or ``seq``, under
    ``config``."""
    if seq is None:
        seq = d.prefix if d.shrunk is None else d.shrunk
    snap = reg.snapshot()
    try:
        eng = config.make()
        for it in seq:
            if isinstance(it, Event):
                apply_event(it)
            else:
                outcome(it.prop, it.assum, eng)
        return outcome(d.item.prop, d.item.assum, eng)
    finally:
        reg.restore(snap)


def _lazy_shape(d: Discrepancy) -> bool:
    """The trigger/observer shape of the lazily switched-on capabilities
    (``harness.lazy``): the query has no relation atom, some prefix query
    under the same assumptions has one, and the assumptions have none."""
    from .lazy import has_relation
    seq = d.prefix if d.shrunk is None else d.shrunk
    if has_relation(d.item.prop) or has_relation(d.item.assum):
        return False
    return any(isinstance(it, Ask) and it.assum == d.item.assum and has_relation(it.prop)
               for it in seq)


def _noncommutative(d: Discrepancy) -> bool:
    from sympy import Basic
    seq = (d.prefix if d.shrunk is None else d.shrunk) + [d.item]
    for it in seq:
        if isinstance(it, Ask):
            for e in (it.prop, it.assum):
                if isinstance(e, Basic) and any(getattr(s, "is_commutative", True) is False
                                                for s in e.free_symbols):
                    return True
    return False


def _repeats_query(d: Discrepancy) -> bool:
    """The (shrunk) prefix asks the query itself, under the same
    assumptions: the answer memo then holds the query's own earlier answer."""
    seq = d.prefix if d.shrunk is None else d.shrunk
    return any(isinstance(it, Ask) and it == d.item for it in seq)


def _effective_carrier(d: Discrepancy) -> List[str]:
    """The carrier ``attribute`` found, without the answer memo when the
    memo only repeats an answer another part carries: with the carrier a
    pair ``X+answers`` and the query itself in the prefix, the memo holds
    that earlier answer of the query, which ``X`` made history-dependent
    (clearing ``X`` alone leaves the memoised copy, clearing the memo alone
    leaves ``X``).  The mechanism is ``X``'s."""
    carrier = list(d.confirmations.get("carrier") or [])
    if len(carrier) == 1 and "+" in carrier[0]:
        parts = carrier[0].split("+")
        if "answers" in parts and len(parts) == 2 and _repeats_query(d):
            return [p for p in parts if p != "answers"]
    return carrier


def _oo_summand(e) -> bool:
    """``e`` has a sum with an ``oo`` or ``-oo`` summand: the argument whose
    sign the extended-order clauses decide at the root (family E)."""
    from sympy import Add, Basic, oo
    return isinstance(e, Basic) and any(t in (oo, -oo) for a in e.atoms(Add) for t in a.args)


def _relation_in_prefix(d: Discrepancy) -> bool:
    """Some prefix query has a relation atom in its proposition or in its
    assumption set: what creates the relation layer's links in a session."""
    from .lazy import has_relation
    seq = d.prefix if d.shrunk is None else d.shrunk
    return any(isinstance(it, Ask) and (has_relation(it.prop) or has_relation(it.assum))
               for it in seq)


#: family tags (``family_of``) of the defects documented in
#: ``harness/repros/README.md``; ``new:...`` and ``?`` are not known
#: G, G' and T left with #53 stage 5 (the relation glue and predicate
#: transfer are switched per query: harness/repros/fixed)
KNOWN_FAMILIES = frozenset({"A", "B", "B/A", "B/C", "C", "C'", "D", "K", "E", "L"})


def is_known_family(fam: str, audit: bool = False) -> bool:
    """Whether ``fam`` is a documented family: one of ``KNOWN_FAMILIES``,
    family C with a second carrier (``C+...``), or a registration change
    kept by any carrier (``R:...``).  With ``audit``, a cached fact that
    is definite where a fresh engine answers None (``new:cache-none-vs-
    definite``) counts as known too: every such flow the audit met was a
    sound write-back of the E, L or C' kind."""
    if fam in KNOWN_FAMILIES or fam.startswith("C+") or fam.startswith("R:"):
        return True
    return audit and fam.startswith("new:cache-none-vs-definite")


def family_of(d: Discrepancy) -> str:
    """A heuristic tag: the known families at c26e5e1 (``A`` an inconsistent
    set detected only after a session escalated, ``B`` a cached fact against
    a lazily accepted assumption, ``C`` a parent's structural fact cached on
    its arguments, ``D`` a binding discovery budget, ``G`` the relation glue
    a prefix relation query switched on in the session, ``T`` the predicate
    transfer an equality query engaged) or ``new:<carrier>-<kind>`` for
    anything the known mechanisms do not explain.  Needs ``attribute``."""
    if d.confirmations.get("carrier") is None:
        return "?"
    carrier = _effective_carrier(d)
    kind = d.kind
    budget = d.config.discovery_budget < 400
    if d.confirmations.get("outside_engine"):
        return "new:outside-engine-" + kind
    seq = d.prefix if d.shrunk is None else d.shrunk
    if any(isinstance(it, Event) for it in seq):
        # a registration change in the minimal prefix: the answer depends on
        # registrations no longer (or not yet) in force, kept by the carrier
        return "R:" + ("+".join(carrier) or "?") + "-" + kind
    if "sessions" in carrier and _lazy_shape(d):
        # the relation glue (G) or predicate transfer (T) of the reused
        # session, switched on by the prefix's relation query and not in a
        # fresh session of the same assumptions
        wt = d.confirmations.get("without_transfer")
        ref = d.shrunk_ref if d.shrunk_ref is not None else d.ref
        tag = "T" if wt == ref else "G"
        return tag if carrier == ["sessions"] else tag + "+" + "+".join(c for c in carrier if c != "sessions")
    if carrier == ["sessions"]:
        if kind.startswith("raise"):
            return "A"
        if budget and kind == "none-vs-definite":
            return "D"
        asks = [it for it in seq if isinstance(it, Ask)]
        if kind == "none-vs-definite" and asks and all(it.assum == d.item.assum for it in asks):
            if d.confirmations.get("mention_only") == d.warm:
                # the prefix acts by merely mentioning its terms: the relation
                # glue links them (the set or the query has a relation, so
                # the glue exists in a fresh session too, but it links only
                # the terms the set and the query mention)
                return "G'"
            # the reused session of this very set answers more definitely
            # (learnt and cone-memo clauses of its earlier queries): the
            # documented class
            return "K"
        return "new:sessions-" + kind
    if carrier == ["cache+sessions"]:
        # the fact is in the cache and asserted in the reused session
        if kind.startswith("raise"):
            return "B" if not _noncommutative(d) else "B/C"
        return "C" if _noncommutative(d) else "new:cache+sessions-" + kind
    if "cache" in carrier:
        if kind.startswith("raise"):
            return "B" if len(carrier) == 1 else "B/A"
        if budget and kind == "none-vs-definite":
            return "D"
        if _noncommutative(d):
            return "C" if len(carrier) == 1 else "C+" + "+".join(c for c in carrier if c != "cache")
        if kind == "none-vs-definite":
            # a fact a fresh cone does not derive, written back by an earlier
            # query: through the relation layer's links and extended-order
            # clauses (E: the query is about a sum with an oo summand, or a
            # relation in the prefix, in a query or in its assumption set,
            # created the links), a unit learnt by a contextual search (L),
            # or a parent's derived node (C')
            if _oo_summand(d.item.prop) or _relation_in_prefix(d):
                return "E"
            asks = [it for it in seq if isinstance(it, Ask)]
            if any(it.assum is not True for it in asks):
                return "L"
            return "C'"
        return "new:cache-" + kind
    if not carrier:
        return "new:multi-" + kind
    return "new:" + "+".join(carrier) + "-" + kind


# --------------------------------------------------------------------------
# cache audit: every cached fact against a fresh engine's context-free answer
# --------------------------------------------------------------------------

def audit_cache(items: Sequence[Item], config: EngineConfig, source: str = "",
                progress: Optional[Callable[[str], None]] = None,
                max_findings: int = 5) -> Tuple[List[Discrepancy], Dict[str, Any]]:
    """Run ``items`` through one engine, then compare every fact its cache
    holds with what a fresh engine derives context-free for the same node
    (one fresh engine per node: the node's own closure).  A cached fact a
    fresh engine does not derive is a fact that flowed into the node from
    outside its own cone (a parent's structure, family C) and makes
    ``ask(Q.<pred>(node), True)`` history-dependent.  Each such node gives a
    ``Discrepancy`` whose prefix is the stream up to the query that first
    wrote the fact (found by replay), ready for ``shrink``/``attribute``."""
    from .generators import predicate
    progress = progress or (lambda s: None)
    snap = reg.snapshot()
    try:
        eng = config.make()
        for it in items:
            if isinstance(it, Event):
                apply_event(it)
            else:
                outcome(it.prop, it.assum, eng)
        store = {node: dict(facts) for node, facts in eng.cache.store.items()}
        bad: List[Tuple[Any, str, bool, Optional[bool]]] = []
        nfacts = 0
        for node, facts in store.items():
            if getattr(node, "is_number", False) and not getattr(node, "free_symbols", None):
                continue
            fresh = config.make()
            for pred, v in facts.items():
                if v is None:
                    continue
                nfacts += 1
                try:
                    r = fresh.is_(node, pred)
                except Exception as e:  # noqa: BLE001
                    r = f"Error:{type(e).__name__}"
                if r is not v:
                    bad.append((node, pred, v, r))
        stats = {"nodes": len(store), "facts": nfacts, "bad": len(bad)}
        found: List[Discrepancy] = []
        seen_nodes: set = set()
        for node, pred, v, r in bad:
            if node in seen_nodes or len(found) >= max_findings:
                continue
            seen_nodes.add(node)
            # the query that first wrote the fact
            eng2 = config.make()
            first = None
            for i, it in enumerate(items):
                if isinstance(it, Event):
                    apply_event(it)
                    continue
                outcome(it.prop, it.assum, eng2)
                if eng2.cache.get(node, pred) is v:
                    first = i
                    break
            if first is None:
                continue
            item = Ask(predicate(pred)(node), True)
            warm = outcome(item.prop, item.assum, eng2)
            ref = reference(item, config, ReferenceLevel.ENGINE)
            if warm == ref:
                continue
            d = Discrepancy(config, "audit", first + 1, item, warm, ref, ReferenceLevel.ENGINE,
                            list(items[:first + 1]), source=source)
            found.append(d)
            progress(f"  audit: {pred}({node}) cached {v}, fresh {r}; first written by query {first}")
    finally:
        reg.restore(snap)
    return found, stats


def repro_script(d: Discrepancy) -> str:
    """A standalone Python script reproducing ``d`` (prefix then query in
    one engine, against a fresh engine)."""
    seq = d.prefix if d.shrunk is None else d.shrunk
    lines = [
        "# Reproduces a history-dependent answer of satassume.sympy_api.ask.",
        "# Run from anywhere inside a satassume checkout, or from its root (needs sympy):",
        "#   PYTHONHASHSEED=0 python this_file.py",
        "import os, sys",
        "_d = os.path.dirname(os.path.abspath(__file__))",
        "while not os.path.exists(os.path.join(_d, 'harness', '__init__.py')):",
        "    if os.path.dirname(_d) == _d:       # not inside a checkout: try the cwd",
        "        _d = os.getcwd()",
        "        break",
        "    _d = os.path.dirname(_d)",
        "sys.path.insert(0, _d)",
        "from harness.checker import Ask, Event, execute, ReferenceLevel",
        "from harness.state import EngineConfig",
        "from harness.sympy_io import from_srepr",
        f"config = EngineConfig(**{d.config.to_dict()!r})",
        "items = [",
    ]
    for it in seq + [d.item]:
        if isinstance(it, Event):
            lines.append(f"    Event({it.kind!r}, {it.reg_id!r}),")
        else:
            lines.append(f"    Ask(from_srepr({to_srepr(it.prop)!r}), from_srepr({to_srepr(it.assum)!r})),")
    lines += [
        "]",
        "rows, eng = execute(items, config, ref_level=ReferenceLevel.NONE, ref_for_last=True)",
        "last = rows[-1]",
        "print('engine after prefix:', last.warm, '  fresh engine:', last.ref)",
        f"assert last.warm == {d.warm!r} and last.ref == {d.ref!r}, (last.warm, last.ref)",
    ]
    return "\n".join(lines) + "\n"


def write_repro(d: Discrepancy, directory: str, stem: str) -> Tuple[str, str]:
    os.makedirs(directory, exist_ok=True)
    jpath = os.path.join(directory, stem + ".json")
    ppath = os.path.join(directory, stem + ".py")
    with open(jpath, "w") as f:
        json.dump(d.to_json(), f, indent=1)
    with open(ppath, "w") as f:
        f.write(repro_script(d))
    return jpath, ppath


# --------------------------------------------------------------------------
# fresh-process execution (confirmation and hash-seed variation)
# --------------------------------------------------------------------------

def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_in_process(items: Sequence[Item], config: EngineConfig, hashseed: Optional[int] = None,
                   ref_level: int = ReferenceLevel.ENGINE, timeout: int = 1800) -> List[Dict[str, Any]]:
    """Execute ``items`` in a fresh interpreter (``python -m harness exec``)
    and return its rows (``index``, ``warm``, ``ref``)."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=_scratch()) as f:
        json.dump({"config": config.to_dict(), "items": [item_to_json(i) for i in items]}, f)
        path = f.name
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(0 if hashseed is None else hashseed)
    cmd = [sys.executable, "-m", "harness", "exec", path, "--ref-level", str(int(ref_level))]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=_repo_root(), env=env, timeout=timeout)
    os.unlink(path)
    if p.returncode != 0:
        raise RuntimeError(f"harness exec failed:\n{p.stderr[-4000:]}")
    return json.loads(p.stdout.strip().splitlines()[-1])


def _scratch() -> str:
    d = os.environ.get("HARNESS_SCRATCH") or os.path.join(_repo_root(), ".harness-tmp")
    os.makedirs(d, exist_ok=True)
    return d


def process_outcome(item: Ask, config: EngineConfig, hashseed: Optional[int] = None) -> str:
    rows = run_in_process([item], config, hashseed, ref_level=ReferenceLevel.NONE)
    return rows[0]["warm"]


def confirm(d: Discrepancy, hashseeds: Iterable[int] = (0, 1, 2)) -> Discrepancy:
    """Re-run the (shrunk) prefix and the query in fresh interpreters, one
    per hash seed; record engine and reference answers per seed."""
    seq = (d.prefix if d.shrunk is None else d.shrunk) + [d.item]
    for hs in hashseeds:
        rows = run_in_process(seq, d.config, hashseed=hs, ref_level=ReferenceLevel.NONE)
        last = rows[-1]
        d.confirmations[f"hashseed={hs}"] = {"warm": last["warm"], "ref": last["ref"]}
    return d


# --------------------------------------------------------------------------
# the checker
# --------------------------------------------------------------------------

@dataclasses.dataclass
class Report:
    config: EngineConfig
    queries: int = 0
    mismatches: int = 0
    discrepancies: List[Discrepancy] = dataclasses.field(default_factory=list)
    outcomes: Dict[str, int] = dataclasses.field(default_factory=dict)
    pairs: Dict[str, int] = dataclasses.field(default_factory=dict)
    kinds: Dict[str, int] = dataclasses.field(default_factory=dict)
    groups: int = 0
    ref_instability: List[Dict[str, Any]] = dataclasses.field(default_factory=list)
    seconds: float = 0.0
    orders: List[str] = dataclasses.field(default_factory=list)
    engine_state: Dict[str, Any] = dataclasses.field(default_factory=dict)
    #: the first mismatch of any kind: order, index in that order, number
    #: of queries run so far (all orders), kind; and the first one reported
    #: (not of an ignored kind)
    first_hit: Optional[Dict[str, Any]] = None
    first_reported: Optional[Dict[str, Any]] = None

    def to_json(self) -> Dict[str, Any]:
        return {"config": self.config.name, "queries": self.queries, "mismatches": self.mismatches,
                "kinds": self.kinds, "groups": self.groups,
                "outcomes": self.outcomes, "pairs": self.pairs,
                "ref_instability": len(self.ref_instability), "seconds": round(self.seconds, 2),
                "orders": self.orders, "first_hit": self.first_hit, "first_reported": self.first_reported,
                "families": sorted({d.confirmations.get("family", "?") for d in self.discrepancies}),
                "discrepancies": [d.summary() for d in self.discrepancies]}


class Checker:
    """Run a stream in several orders through a long-lived engine of
    ``config``, each answer against a reference at ``ref_level``.

    ``ref_check_every``: every k-th query also gets a MODULE-level
    reference; a difference between the two references is a memo
    dependence and is reported separately.

    Mismatches are grouped by (assumption set, kind): one inconsistent
    session makes every later query under it disagree.  The first of each
    group is kept as a ``Discrepancy`` (with the group's size), at most
    ``max_discrepancies`` groups per order are shrunk (``shrink_them``),
    rarer kinds first (``KINDS`` order).  ``ignore_kinds`` are counted in
    ``Report.kinds`` but not reported as discrepancies."""

    def __init__(self, config: EngineConfig, ref_level: int = ReferenceLevel.ENGINE,
                 orders: Sequence[str] = ("forward",), seed: int = 0,
                 ref_check_every: int = 0, max_discrepancies: int = 5,
                 shrink_them: bool = True, source: str = "",
                 progress: Optional[Callable[[str], None]] = None,
                 dedupe: bool = True, ignore_kinds: Sequence[str] = (),
                 attribute_them: bool = True):
        self.ignore_kinds = set(ignore_kinds)
        self.attribute_them = attribute_them
        self.config = config
        self.ref_level = ref_level
        self.orders = list(orders)
        self.seed = seed
        self.ref_check_every = ref_check_every
        self.max_discrepancies = max_discrepancies
        self.shrink_them = shrink_them
        self.source = source
        self.progress = progress or (lambda s: None)
        self.dedupe = dedupe

    def run(self, items: Sequence[Item]) -> Report:
        rep = Report(self.config, orders=self.orders)
        t0 = time.perf_counter()
        seen: set = set()
        for k, order in enumerate(self.orders):
            ordered = order_stream(items, order, self.seed + k)
            groups: Dict[Any, Discrepancy] = {}

            def on_row(row: Row, ordered=ordered, groups=groups, order=order):
                rep.queries += 1
                rep.outcomes[row.warm] = rep.outcomes.get(row.warm, 0) + 1
                key = f"{row.warm}/{row.ref}"
                rep.pairs[key] = rep.pairs.get(key, 0) + 1
                if self.ref_check_every and rep.queries % self.ref_check_every == 0:
                    r2 = reference(row.item, self.config, ReferenceLevel.MODULE)
                    if r2 != row.ref:
                        rep.ref_instability.append({"item": str(row.item), "engine_ref": row.ref,
                                                    "module_ref": r2})
                if row.mismatch:
                    rep.mismatches += 1
                    kind = kind_of(row.warm, row.ref)
                    rep.kinds[kind] = rep.kinds.get(kind, 0) + 1
                    hit = {"order": order, "index": row.index, "queries": rep.queries, "kind": kind}
                    if rep.first_hit is None:
                        rep.first_hit = hit
                    if kind in self.ignore_kinds:
                        return
                    if rep.first_reported is None:
                        rep.first_reported = hit
                    gkey = (to_srepr(row.item.assum), kind)
                    d = groups.get(gkey)
                    if d is not None:
                        d.group_size += 1
                        return
                    d = Discrepancy(self.config, order, row.index, row.item, row.warm,
                                    row.ref, self.ref_level, list(ordered[:row.index]),
                                    source=self.source)
                    groups[gkey] = d
                    self.progress(f"  mismatch: {d.summary()}")

            execute(ordered, self.config, self.ref_level, on_row=on_row)
            rep.groups += len(groups)
            kept = 0
            for gkey, d in sorted(groups.items(), key=lambda kv: KINDS.index(kv[1].kind)):
                if self.dedupe:
                    if gkey in seen:
                        continue
                    seen.add(gkey)
                if kept >= self.max_discrepancies:
                    break
                kept += 1
                if self.shrink_them:
                    shrink(d, progress=self.progress)
                    if self.attribute_them:
                        try:
                            attribute(d)
                        except Exception as e:  # noqa: BLE001 - attribution is diagnostic only
                            d.confirmations["attribute_error"] = f"{type(e).__name__}: {e}"
                        self.progress(f"  attributed: {d.summary()}")
                rep.discrepancies.append(d)
            self.progress(f"order {order}: {len(ordered)} items, {len(groups)} mismatch groups "
                          f"({time.perf_counter() - t0:.1f}s)")
        rep.seconds = time.perf_counter() - t0
        return rep
