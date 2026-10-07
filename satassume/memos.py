"""Named, bounded memo tables and the objects that own them (issue #97).

A :class:`Memos` holds every memo of one owner under a name, and empties
them all with one :meth:`Memos.clear`.  There are two kinds of owner:

* :data:`PROCESS`, the memos shared by every engine of the process.  Only
  a pure function of its key and of the registry epoch
  (:mod:`satassume.epoch`) or the default registry's version may live
  here: sharing such a memo between engines, or keeping it across
  queries, can change how fast an answer comes but never the answer.  The
  tables that ``satassume`` modules create with :meth:`Memos.table` are
  registered here when the module is imported; memos owned by modules
  that keep a plain container (``engine._SPLIT``, ``solver._RULE_TABLES``,
  ...) are *adopted* by location (:data:`ADOPTED`), so :meth:`clear` and
  ``python -m harness inventory`` see them too.
* one per engine, ``Engine.memos`` (:func:`engine_memos`): the memos of
  that engine, which may depend on its settings (the answer and split
  memos, the structural cones, the verdict and ``Uninterpreted`` memos).
  Two engines never share one.

Each table declares what it is keyed on besides its own key (``key``):
``"pure"`` (nothing), ``"epoch"`` (the registry epoch),
``"extensions"`` (the default extension registry's version) or
``"settings"`` (the epoch and the owning engine's settings).  A table
keyed on a counter records the value it was filled under in
:attr:`Table.stamp`; the function using it compares and calls
:meth:`Table.restamp` (one attribute read and one comparison on the hit
path, like the ``[state]`` lists it replaces).

An adopted name that no longer resolves (an attribute renamed in its
module or on ``Engine``) raises from :meth:`Memos.items` and
:meth:`Memos.clear`, so ``harness inventory`` and the tests notice.
"""
from __future__ import annotations

import sys
import weakref
from typing import Any, Callable, Dict, Iterator, List, Tuple

#: what a table may be keyed on besides its key; only the first three may
#: live on :data:`PROCESS`
KEYS = ("pure", "epoch", "extensions", "settings")
PROCESS_KEYS = frozenset(KEYS[:3])


class Table(dict):
    """A bounded memo: a ``dict`` (lookups stay ``dict.get``) with a name,
    what it is keyed on, a size bound and the stamp it was filled under.
    ``clear()`` is ``dict.clear`` and keeps the stamp; :meth:`reset`
    forgets the stamp too."""

    __slots__ = ("name", "key", "size", "stamp")

    def __init__(self, name: str, key: str = "pure", size: int = 100_000):
        super().__init__()
        if key not in KEYS:
            raise ValueError(f"memo {name}: key {key!r} is not one of {KEYS}")
        self.name, self.key, self.size, self.stamp = name, key, int(size), None

    def put(self, k, v):
        """``self[k] = v``, emptying the table first when it is full
        (the ``sympy_api`` answer and split memos use it; the others keep
        their own size test next to the lookup)."""
        if len(self) >= self.size:
            dict.clear(self)
        self[k] = v
        return v

    def restamp(self, stamp) -> None:
        """Empty the table and record that it is filled under ``stamp``."""
        dict.clear(self)
        self.stamp = stamp

    def reset(self) -> None:
        """Empty the table and forget its stamp, so the next use restamps
        it (what :meth:`Memos.clear` does); ``clear()`` only empties it,
        and it refills under the same stamp."""
        dict.clear(self)
        self.stamp = None

    def __repr__(self) -> str:
        return f"<Table {self.name} key={self.key} {len(self)}/{self.size}>"



class Memos:
    """The memo tables of one owner, by name."""

    def __init__(self, owner: str):
        self.owner = owner
        self._tables: Dict[str, Table] = {}
        #: memos kept elsewhere: name -> (what it is keyed on, getter of
        #: the container or None when it does not exist yet)
        self._adopted: Dict[str, Tuple[str, Callable[[], Any]]] = {}

    def table(self, name: str, key: str = "pure", size: int = 100_000) -> Table:
        """A new table registered under ``name`` (a re-import of the
        defining module replaces the old one)."""
        if self is PROCESS and key not in PROCESS_KEYS:
            raise ValueError(f"memo {name}: a process-wide memo must be keyed on "
                             f"{sorted(PROCESS_KEYS)}, not {key!r}")
        t = Table(name, key, size)
        self._tables[name] = t
        return t

    def adopt(self, name: str, getter: Callable[[], Any], key: str = "pure") -> None:
        """Register a container this object does not own: ``getter()``
        returns it, None when its owner is not loaded, or raises when the
        name does not resolve; :meth:`clear` calls its ``clear()``."""
        if key not in KEYS or (self is PROCESS and key not in PROCESS_KEYS):
            raise ValueError(f"memo {name}: bad key {key!r}")
        self._adopted[name] = (key, getter)

    def items(self) -> Iterator[Tuple[str, str, Any]]:
        """``(name, key, container)`` of every memo, adopted ones whose
        owner is not loaded left out; an adopted name whose owner is
        loaded but which does not resolve raises ``AttributeError``."""
        for name, t in self._tables.items():
            yield name, t.key, t
        for name, (key, get) in self._adopted.items():
            c = get()
            if c is not None:
                yield name, key, c

    def names(self) -> List[str]:
        return list(self._tables) + list(self._adopted)

    def sizes(self) -> Dict[str, int]:
        return {name: len(c) for name, _, c in self.items()}

    def clear(self) -> None:
        """Empty every memo (and forget the stamps of the tables)."""
        for t in self._tables.values():
            t.reset()
        for _, (_, get) in self._adopted.items():
            c = get()
            if c is not None:
                c.clear()

    def __repr__(self) -> str:
        return f"<Memos {self.owner}: {len(self._tables)} tables, {len(self._adopted)} adopted>"


#: the process-wide memos: pure functions of their keys and the epoch
PROCESS = Memos("process")


def _path(obj, path: str):
    """Attribute ``path`` (dotted) of ``obj``; None when ``obj`` is None
    (the owning module is not imported, or the engine is gone).  A part
    that does not resolve raises ``AttributeError``: an adopted memo that
    is renamed must fail loudly, not drop out of :meth:`Memos.items`,
    :meth:`Memos.clear` and the inventory (#97 P4 review)."""
    if obj is None:
        return None
    for part in path.split("."):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            raise AttributeError(f"adopted memo {path!r}: {obj!r} has no "
                                 f"attribute {part!r}") from None
    return obj


def _module_attr(module: str, path: str) -> Callable[[], Any]:
    return lambda: _path(sys.modules.get(module), path)


#: ``(module, attribute path, key)`` of the process-wide memos that their
#: modules keep as plain containers (or on a registry object).  Each is a
#: pure function of its key (``_SPLIT`` and ``_RULE_TABLES`` keep the keyed
#: object alive and compare it by identity; ``_INTERPRETED`` is keyed on
#: ``GENERIC_CONSTANTS``; the template registry's memos follow its own
#: version counter).  ``templates._common._CACHE`` holds compiled patterns
#: by template key, and a later registration may reuse a key, so
#: ``TemplateRegistry.register`` empties it: keyed on the epoch.
ADOPTED: Tuple[Tuple[str, str, str], ...] = (
    ("satassume.engine", "_NEIGH", "pure"),
    ("satassume.engine", "_WANT", "pure"),
    ("satassume.engine", "_SPLIT", "pure"),
    ("satassume.solver", "_RULE_TABLES", "pure"),
    ("satassume.lra_bounds", "_BOUNDS", "pure"),
    ("satassume.lra_adapter", "_INTERPRETED", "pure"),
    ("satassume.lra_bounds", "_ENCLOSURES", "pure"),
    ("satassume.lra_bounds", "_IV", "pure"),
    ("satassume.euf_adapter", "_class_ok", "pure"),
    ("satassume.templates._common", "_CACHE", "epoch"),
    ("satassume.templates.registry", "registry._clauses_cache", "epoch"),
    ("satassume.templates.registry", "registry._mro_cache", "epoch"),
    ("satassume.extensions", "extensions._node_cache", "extensions"),
)

for _mod, _attr, _key in ADOPTED:
    PROCESS.adopt(f"{_mod}.{_attr}", _module_attr(_mod, _attr), _key)
del _mod, _attr, _key


def module_locations() -> List[Tuple[str, str]]:
    """``(module, attribute)`` of every process-wide memo that is a
    module-level name: the tables (named ``module.attribute``) and the
    adopted containers that are not attributes of a registry object."""
    out = [tuple(name.rpartition(".")[::2]) for name in PROCESS._tables]
    out += [(m, p) for m, p, _ in ADOPTED if "." not in p]
    return out


#: the per-engine memos: attributes of :class:`satassume.engine.Engine`
#: that hold what the engine computed (all keyed on the epoch and the
#: engine's settings, dropped by ``Engine._check_version`` and
#: ``Engine._settings_changed``).  The fact caches are the engine's own
#: unless a ``DictCache`` was passed to several engines on purpose.
ENGINE_MEMOS: Tuple[str, ...] = (
    "answers", "splits", "_kids", "_cones", "_qcones", "_glue_adapters",
    "_failed", "_verdict", "cache.store", "custom_cache.store",
)


def engine_memos(engine) -> Memos:
    """The :class:`Memos` of ``engine`` (``Engine.memos``): its memo
    attributes (:data:`ENGINE_MEMOS`), held through a weak reference so the
    object keeps no engine alive."""
    ref = weakref.ref(engine)
    m = Memos(f"engine@{id(engine):x}")

    def getter(attr):
        def get():
            return _path(ref(), attr)
        return get

    for attr in ENGINE_MEMOS:
        m.adopt(attr, getter(attr), "settings")
    return m
