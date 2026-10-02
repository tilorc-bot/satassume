"""Review of issue #97 P2 (branch ``issue-97/p2-fact-memo`` at c8519f3).

The fact cache is a memo of ``Engine.is_`` keyed on the node and the
registry epoch (``DictCache._epoch``).  The engine's settings
(``templates``, ``transfer``, ``uninterpreted``, ...) are part of what the
answer depends on but not of the key: a ``DictCache`` shared between two
engines with different settings, or given to an engine whose settings
change before its first query (``_settings_changed`` drops nothing while
``_epoch == -1``), serves the other configuration's answer, which is not
what a fresh engine with the same settings derives.  Both tests fail at
c8519f3 (the second engine answers True where a fresh one answers None).
"""
from satassume import Engine, DictCache, P


def _declaring(node):
    return [P('positive', 'x')] if node == 'x' else []


def _silent(node):
    return []


def test_shared_cache_is_not_served_across_different_templates():
    cache = DictCache()
    a = Engine(cache=cache, templates=_declaring)
    assert a.is_('x', 'positive') is True
    b = Engine(cache=cache, templates=_silent)
    fresh = Engine(templates=_silent)
    assert fresh.is_('x', 'positive') is None
    assert b.is_('x', 'positive') is None


def test_shared_cache_is_dropped_by_a_setting_change_before_the_first_query():
    cache = DictCache()
    a = Engine(cache=cache, templates=_declaring)
    assert a.is_('x', 'positive') is True
    b = Engine(cache=cache, templates=_declaring)
    b.templates = _silent                       # before b's first query
    assert Engine(templates=_silent).is_('x', 'positive') is None
    assert b.is_('x', 'positive') is None
