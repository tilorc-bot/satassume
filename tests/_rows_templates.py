"""Helpers of the tests of the families of rows (#249): the registered
template of each function's rows, and what it gives for a node."""
from satassume.knowledge.templates import _common, registry, wiring
from satassume.knowledge.templates.registry import _split


def rows_templates(heads, family):
    """The template of each head's rows, registered for the head and
    attributed to the family (before any of ``wiring.AFTER_ROWS``)."""
    name = f"{wiring.__name__}:{family}"
    out = {}
    for h in heads:
        registry.templates_for(h)
        ts = [t for t in registry._by_class[h] if t.__module__ == name]
        assert len(ts) == 1 + sum(h in c for c, _ in wiring.AFTER_ROWS), (h, ts)
        out[h] = ts[0]
    return out


def compiled(templates, e):
    """``(patterns, formulas)`` the template of ``type(e)`` gives for the node
    ``e``, from empty pattern caches."""
    cs, formulas = [], []
    _common._CACHE.clear()
    try:
        _split(templates[type(e)](e), cs, formulas)
    finally:
        _common._CACHE.clear()
    return cs, sorted(map(str, formulas))
