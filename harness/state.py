"""What outlives a query, and how to build a clean reference.

Engine-level state (one ``Engine``, see ``satassume/engine.py``):

* ``cache`` (``DictCache``, 200k nodes, cleared when full): context-free
  facts written back from the level-0 trail of every session, contextual
  sessions included; asserted as unit clauses whenever a node is visited;
* ``custom_cache``: the same for custom-predicate atoms;
* ``answers`` (``AnswerMemo``, 100k, cleared when full, cleared with the
  registry version): ``(prop, assumptions) -> answer`` of ``sympy_api.ask``,
  also keyed by the relevant part of the assumptions;
* ``splits`` (20k): per assumption set its component split and whether the
  whole set was found consistent; per component whether it is consistent
  (``(_OK, part)``);
* ``_context_sessions``: always empty since #97 P1.  A contextual query
  builds the session of its set (``Engine._build_context``: the set's
  clauses and its one complete check), answers in it and discards it, so
  no solver state (visited nodes, learnt clauses, held levels, the witness
  ring, the relation glue and theory state) outlives a query.  The
  ``keep_sessions``, ``session_limit``, ``cone_search`` and
  ``cone_threshold`` settings of the earlier reuse design were removed in
  #97 P7 (no code path read them); the presets that set them are kept as
  the equivalent live configurations;
* ``_verdict`` (20k): per assumption set the verdict of its complete
  check (a function of the set and the settings);
* ``_failed``: assumption sets whose session raised ``Uninterpreted``
  (dropped with every other cache when the registry epoch moves on);
* ``_xbasis`` (set by ``relations._number_basis``): per number, its basis
  of facts for predicate transfer;
* ``stats``, ``_constructing``.

Module-level state (survives ``Engine()``; see ``MODULE_STATE``): the
``to_formula`` memo, the relevance key memo, the template pattern caches,
the compiled-clause split memo, the rule tables, the LRA bounds and
interpretation memos, the EUF class test memo, the ``sympy_atom`` memo,
the extension registry's per-class memo, and SymPy's own ``cacheit`` cache.
All of these are documented as pure memos; the checker can clear them
between reference queries (``ReferenceLevel.MODULE``) to test that claim.

Declared configuration (must be identical on both sides of a comparison):
the ``Engine`` keyword arguments, the sizes of the bounded caches, the
registered extensions (``satassume.extensions.extensions``), the template
registry and the theory adapters.
"""
from __future__ import annotations

import dataclasses
import importlib
import sys
from typing import Any, Dict, List, Tuple

from satassume.engine import AnswerMemo, DictCache, Engine

# --------------------------------------------------------------------------
# engine configuration
# --------------------------------------------------------------------------

#: settings of the earlier session-reuse design, no-ops since #97 P1 and
#: removed from ``Engine`` in #97 P7 (``EngineConfig.from_dict`` ignores them;
#: ``check_I7`` replays a recorded variant over one of them as the no-op it was)
REMOVED_SETTINGS = frozenset({"session_limit", "keep_sessions", "cone_search",
                              "cone_threshold"})

@dataclasses.dataclass(frozen=True)
class EngineConfig:
    """The declared configuration of an ``Engine`` (its keyword arguments
    plus the sizes of its bounded caches).  ``make()`` builds one."""

    name: str = "default"
    discovery_budget: int = 400
    transfer: bool = True
    uninterpreted: str = "free"
    relevance: bool = True
    relations: str = "default"
    cache_size: int = 200_000
    custom_cache_size: int = 200_000
    answers_size: int = 100_000
    splits_size: int = 20_000

    def make(self) -> Engine:
        eng = Engine(cache=DictCache(self.cache_size),
                     discovery_budget=self.discovery_budget,
                     transfer=self.transfer,
                     uninterpreted=self.uninterpreted,
                     relevance=self.relevance,
                     relations=self._relation_specs())
        eng.custom_cache = DictCache(self.custom_cache_size)
        eng.answers = AnswerMemo(self.answers_size)
        eng.splits = AnswerMemo(self.splits_size)
        return eng

    def _relation_specs(self):
        if self.relations == "default":
            return None
        if self.relations == "none":
            return []
        from satassume.relations import default_specs
        return [s for s in default_specs() if s.name == self.relations]

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EngineConfig":
        # repro files written before #97 P7 carry the removed no-op
        # settings; they selected no code path, so dropping them replays
        # the same configuration
        d = {k: v for k, v in d.items() if k not in REMOVED_SETTINGS}
        return cls(**d)

    def replace(self, **kw) -> "EngineConfig":
        return dataclasses.replace(self, **kw)


def config_of(eng: Engine, name: str = "of-engine") -> EngineConfig:
    """The configuration an existing engine was built with (read back from
    its attributes), for a reference engine that matches it."""
    specs = [s.name for s in eng.relation_specs]
    from satassume.relations import default_specs
    default = [s.name for s in default_specs()]
    if specs == default:
        rel = "default"
    elif not specs:
        rel = "none"
    elif len(specs) == 1:
        rel = specs[0]
    else:  # pragma: no cover - a custom adapter list; the closest we can do
        rel = "default"
    return EngineConfig(
        name=name,
        discovery_budget=eng.discovery_budget,
        transfer=eng.transfer,
        uninterpreted=eng.uninterpreted,
        relevance=eng.relevance,
        relations=rel,
        cache_size=eng.cache.maxsize,
        custom_cache_size=eng.custom_cache.maxsize,
        answers_size=eng.answers.maxsize,
        splits_size=eng.splits.maxsize,
    )


#: Configurations.  ``default`` is what ``sympy_api.default_engine()``
#: builds.  The others stress one mechanism each: the bounded caches at
#: sizes a short stream crosses, and the switches that select the code
#: paths (relevance, transfer, theories).  #97 P7 removed the session-reuse
#: settings (``session_limit``, ``keep_sessions``, ``cone_search``,
#: ``cone_threshold``: no code path read them since #97 P1); the presets
#: that set them keep their names and their live settings, so every preset
#: still runs and repro files naming them still replay.
PRESETS: Dict[str, EngineConfig] = {
    "default": EngineConfig(),
    # every bounded cache small enough that a stream of a few hundred
    # queries crosses it many times (P7: dropped session_limit=6,
    # keep_sessions=1, cone_threshold=0, no-ops; kept for the small caches)
    "tight": EngineConfig(name="tight", discovery_budget=12, cache_size=64,
                          custom_cache_size=16, answers_size=32, splits_size=8),
    # once: sessions never replaced by cone sessions.  P7: it set only
    # removed no-ops (cone_search=False, session_limit=10_000,
    # keep_sessions=64), so it is the default configuration; kept so that
    # runs and repros naming it stay valid
    "reuse": EngineConfig(name="reuse"),
    # once: every search in a fresh cone session.  P7: it set only the
    # removed no-op cone_threshold=-1, so it is the default configuration
    # (every query now runs in a session of its own); kept by name
    "cone": EngineConfig(name="cone"),
    # whole assumption set always (no relevance split)
    "whole": EngineConfig(name="whole", relevance=False),
    # no transfer between congruent applications (the relation glue alone)
    "notransfer": EngineConfig(name="notransfer", transfer=False),
    # a small discovery budget and the whole set: every optimisation that
    # drops clauses engaged at once (P7: dropped the no-ops
    # cone_search=False, cone_threshold=0)
    "lean": EngineConfig(name="lean", discovery_budget=12, relevance=False),
    # no predicate transfer between equal terms
    "notransfer": EngineConfig(name="notransfer", transfer=False),
    # relations out of scope (the scalar slice alone)
    "norel": EngineConfig(name="norel", relations="none"),
    # unread assumption atoms sink the answer to None (the pre-opaque
    # default; the engine default keeps them as free Booleans)
    "none": EngineConfig(name="none", uninterpreted="none"),
    # the discovery budget binds on ordinary expressions
    "budget": EngineConfig(name="budget", discovery_budget=5),
    # every setting at its smallest legal value at once: one node of
    # discovery per demand, every bounded cache of size 2 (P7: dropped the
    # no-ops cone_threshold=0, session_limit=1, keep_sessions=0)
    "boundary": EngineConfig(name="boundary", discovery_budget=1, cache_size=2,
                             custom_cache_size=2, answers_size=2, splits_size=2),
    # once: sessions replaced constantly.  P7: it set only removed no-ops
    # (session_limit=3, keep_sessions=1), so it is the default
    # configuration; kept by name
    "churn": EngineConfig(name="churn"),
    # the fact cache is cleared every few nodes, the memos every few answers
    "evict": EngineConfig(name="evict", cache_size=16, custom_cache_size=4,
                          answers_size=8, splits_size=2),
}


def preset(name: str) -> EngineConfig:
    try:
        return PRESETS[name]
    except KeyError:
        raise SystemExit(f"unknown config {name!r}; choose from {', '.join(PRESETS)}")


# --------------------------------------------------------------------------
# module-level state
# --------------------------------------------------------------------------

# the modules that create or adopt process-wide memos (``satassume.memos``),
# imported so that ``MODULE_STATE`` lists their tables and containers (each
# registers its own when it is imported)
import satassume.euf_adapter  # noqa: E402,F401
import satassume.lra_adapter  # noqa: E402,F401
import satassume.lra_bounds  # noqa: E402,F401
import satassume.relations  # noqa: E402,F401
import satassume.sympy_api  # noqa: E402,F401
import satassume.templates  # noqa: E402,F401
from satassume.memos import PROCESS as MEMOS, Table, module_locations  # noqa: E402

#: ``(module, attribute)`` of every module-level memo of the engine: the
#: process-wide memos registered with ``satassume.memos.PROCESS`` (tables
#: and adopted containers), which ``reset_module_state`` empties with one
#: ``MEMOS.clear()``.  A module-level memo that is not registered there is
#: unclassified in ``inventory``.
MODULE_STATE: Tuple[Tuple[str, str], ...] = tuple(module_locations())

#: module-level containers that are constants (built at import, never
#: written afterwards), so not state
MODULE_CONSTANTS: frozenset = frozenset({
    ("satassume.rules", "PREDICATES"), ("satassume.rules", "PRED_INDEX"),
    ("satassume.rules", "RULES"), ("satassume.rules", "RULE_CLAUSES"),
    ("satassume.rules", "RULE_INSTANTIATED"), ("satassume.rules", "RULE_INTERNAL"),
    ("satassume.rules", "RULE_FREE"),
    ("satassume.rules", "BASIS"), ("satassume.rules", "BASIS_INDEX"), ("satassume.rules", "BASIS_OF"),
    ("satassume.rules", "DEFINITIONS"), ("satassume.rules", "DEF_LITS"),
    ("satassume.rules", "_CNF_POS"), ("satassume.rules", "_CNF_NEG"),
    ("satassume.solver", "_BIT"), ("satassume.solver", "_NBIT"),
    ("satassume.relations", "RELATION_ATOMS"), ("satassume.relations", "_OPS"),
    ("satassume.lra", "_NEG"), ("satassume.lra", "_FLIP"),
    ("satassume.lra_adapter", "_PRED"), ("satassume.lra_adapter", "_REL"),
    ("satassume.lra_adapter", "_BAD"),
    ("satassume.euf_adapter", "_STRUCTURAL"),
    ("satassume.sympy_api", "CATEGORIES"), ("satassume.sympy_api", "RELATION_PREDICATES"),
    ("satassume.templates._common", "VOCAB"), ("satassume.templates._common", "SIGN_FLIP"),
    ("satassume.templates._common", "_SIGNED_INFINITE"),
    ("satassume.templates.atoms", "_ORACLE_PREDS"), ("satassume.templates.atoms", "_CONST_BASIS"),
    ("satassume.templates.core", "_ADD_CLOSED"), ("satassume.templates.core", "_ADD_SUBTRACT"),
    ("satassume.templates.core", "_STRICT"), ("satassume.templates.core", "_MUL_CLOSED"),
    ("satassume.templates.core", "_COEFF_BACK"), ("satassume.templates.core", "_POW_RULES"),
    ("satassume.templates.core", "_POW_E_RULES"), ("satassume.templates.core", "_NOTUNIT"),
    ("satassume.templates.core", "_POW_ONE_EQUIV"),
    # The Mul/Pow/exp tables and their guard and slot maps (#97, P6).  They
    # are tuples of Rows and MappingProxyType, so ``inventory`` (which only
    # looks at dict/list/set) does not see them; named here so that the
    # classification is explicit, as the P6 review asked.
    ("satassume.templates.core", "MUL_GUARDS"), ("satassume.templates.core", "POW_GUARDS"),
    ("satassume.templates.core", "IPI_GUARDS"), ("satassume.templates.core", "POW_SLOTS"),
    ("satassume.templates.core", "_POW_SLOT_NAMES"),
    ("satassume.templates.core", "MUL_TABLE"), ("satassume.templates.core", "POW_TABLE"),
    ("satassume.templates.core", "IPI_TABLE"),
})

#: intern tables: they grow with use and are never emptied, because live
#: objects (in the engine under test too) refer to their entries by index.
#: Not reset by ``reset_module_state``; that an answer does not depend on
#: their order of first use is checked only by the fresh-process reference
#: (``hashseed``, ``--confirm``)
MODULE_INTERNED: frozenset = frozenset({
    ("satassume.constfield", "_CONSTANTS"), ("satassume.constfield", "_BY_KEY"),
})

#: objects that are configuration (registrations), not history
MODULE_CONFIG: frozenset = frozenset({
    ("satassume.extensions", "extensions"),
    ("satassume.templates.registry", "registry"),
    ("satassume.epoch", "EPOCH"),                 # the registry epoch: bumped by every
                                                  # registration, never reset (#63)
    ("satassume.sympy_api", "_engine"),           # the default engine itself
    ("satassume.memos", "ADOPTED"),               # the adopted memos, registered by
                                                  # their modules at import
})


def _satassume_modules() -> List[Any]:
    return [m for name, m in list(sys.modules.items())
            if name == "satassume" or name.startswith("satassume.") and m is not None]


def import_all() -> None:
    """Import every ``satassume`` module, so that ``inventory`` does not
    depend on which modules earlier code happened to load (the LRA
    adapter imports ``constfield`` lazily, for instance)."""
    import pkgutil
    import satassume
    for info in pkgutil.walk_packages(satassume.__path__, "satassume."):
        try:
            importlib.import_module(info.name)
        except ImportError:        # an optional dependency (z3, ...) missing
            pass


def inventory(kinds=(dict, list, set)) -> List[Tuple[str, str, str]]:
    """Every module-level container of the loaded ``satassume`` modules, as
    ``(module, attribute, type name)``, and the mutable class attributes of
    their classes.  An object imported under another name is listed once,
    under a classified name if it has one.  The test suite compares this
    with ``MODULE_STATE``, ``MODULE_CONSTANTS`` and ``MODULE_CONFIG`` so
    that a cache added later is noticed."""
    known = set(MODULE_STATE) | set(MODULE_CONSTANTS) | set(MODULE_CONFIG) | set(MODULE_INTERNED)
    by_id: Dict[int, Tuple[str, str, str]] = {}
    for m in _satassume_modules():
        for attr, val in vars(m).items():
            if attr.startswith("__"):
                continue
            if type(val) in kinds or type(val) is Table:
                key = (m.__name__, attr, type(val).__name__)
                prev = by_id.get(id(val))
                if prev is None or (prev[:2] not in known and key[:2] in known):
                    by_id[id(val)] = key
            elif isinstance(val, type) and val.__module__ == m.__name__:
                for cattr, cval in vars(val).items():
                    if type(cval) in kinds and not cattr.startswith(("_field", "__")):
                        by_id[id(cval)] = (m.__name__, f"{val.__name__}.{cattr}", type(cval).__name__)
    return sorted(set(by_id.values()))


def reset_module_state(sympy_cache: bool = True) -> None:
    """Empty every process-wide memo of the engine (``satassume.memos.PROCESS``:
    the module-level memos of ``MODULE_STATE``, the template registry's
    memos, the extension registry's per-class memo) and,
    with ``sympy_cache``, SymPy's ``cacheit`` cache.  Registrations are
    kept: they are configuration."""
    MEMOS.clear()
    api = importlib.import_module("satassume.sympy_api")
    api._MATRIX_PREDICATES = None
    if sympy_cache:
        from sympy.core.cache import clear_cache
        clear_cache()
