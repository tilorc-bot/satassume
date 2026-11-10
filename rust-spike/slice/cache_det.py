"""cache_det.py: does `_common._CACHE`'s key determine its value? (the `_CACHE` fix ruling, issue 323: "show that the cache
key fully determines the cached value, so whatever filled the cache first, every query gets the same result")

On every cache hit the pattern is built again from the hitting call's own arguments, outside the cache, and compared with
the cached one field by field. A hit whose own build differs is an entry that depends on which call came first.

- `_common.facts` and `_common.units`, in `_common` and in every template module holding the name (Python's functions,
  or Rust's `Common.facts`/`Common.units` once the backend is in): the same call is made again with the key taken out
  of the table, so it misses and builds; the cached pattern is then put back.
- knowledge_live's atom templates (common.rs `atom_pattern`): its `RECHECK` hook hands over the cached pattern and Rust's
  build from this call's reads.
Not covered: a template Rust calls natively (rows_tpl.rs, outer_tpl.rs, fn_tpl.rs reach `Common::facts` without the
Python name). For those the digest's `_CACHE` row (keys and values) against Python's is the evidence.

  pytest -p cache_det ...        totals into $SLICE_SUITE_OUT/cache_det.PID.json (after the backend's plugin, if any)
  CACHE_DET_OUT=FILE python -c 'import cache_det; cache_det.install(); ...'   for a script, on Python
  CACHE_DET_OUT=FILE CACHE_DET=1 python live.py ...                           live.py installs it after the backend
Totals: `hits` and `mismatch` by key family (`key[0]`), `order` (equal, another repr), and the first mismatches.
The probe makes every hit build again, so its runs are not for timing or for a digest (the put-back moves the key to the
table's end)."""
import atexit
import collections
import json
import os
import sys

FIELDS = ('rules', 'node', 'nobjs', 'clauses', 'used', 'child_preds', 'complete', 'wide')
STATE = dict(on=False, hits=collections.Counter(), mismatch=collections.Counter(), order=collections.Counter(), first=[])
NAMES = ('facts', 'units')


def family(key):
    return key[0] if type(key) is tuple and key and type(key[0]) is str else type(key).__name__


def compare(key, cached, fresh):
    """Count one hit; True when `fresh` (this call's own build) equals the cached pattern in every field."""
    f = family(key)
    STATE['hits'][f] += 1
    bad = [n for n in FIELDS if getattr(cached, n) != getattr(fresh, n) or type(getattr(cached, n)) is not type(getattr(fresh, n))]
    if bad:
        STATE['mismatch'][f] += 1
        if len(STATE['first']) < 20:
            STATE['first'].append(dict(test=os.environ.get('PYTEST_CURRENT_TEST', ''), key=repr(key)[:300], fields=bad,
                                       cached=repr(getattr(cached, bad[0]))[:300], fresh=repr(getattr(fresh, bad[0]))[:300]))
        return False
    if any(repr(getattr(cached, n)) != repr(getattr(fresh, n)) for n in FIELDS):
        STATE['order'][f] += 1
    return True


def _checked(f, cache):
    def checked(key, gen, *rest):
        before = cache.get(key)
        out = f(key, gen, *rest)
        if before is not None and out.pattern is before:
            del cache[key]
            try:
                fresh = f(key, gen, *rest).pattern
            finally:
                cache[key] = before
            compare(key, before, fresh)
        return out
    checked.__wrapped__ = f
    checked._cache_det = True
    return checked


def totals():
    return dict(hits=dict(STATE['hits']), mismatch=dict(STATE['mismatch']), order=dict(STATE['order']),
                first=STATE['first'])


def _write():
    path = os.environ.get('CACHE_DET_OUT')
    if path is None and os.environ.get('SLICE_SUITE_OUT'):
        path = os.path.join(os.environ['SLICE_SUITE_OUT'], f'cache_det.{os.getpid()}.json')
    if path:
        with open(path, 'w') as f:
            json.dump(totals(), f)


def install():
    """Wrap the names as they are now: call it after the backend's install. Returns the undo."""
    if STATE['on']:
        return lambda: None
    STATE['on'] = True
    from satassume.knowledge.templates import _common
    mods = [_common] + [m for n, m in list(sys.modules.items())
                        if n.startswith('satassume.knowledge.templates.') and m is not None and m is not _common]
    made, saved = {}, []
    for m in mods:
        for n in NAMES:
            f = m.__dict__.get(n)
            if f is None or getattr(f, '_cache_det', False) or not callable(f):
                continue
            # one wrapper per function: Rust's bound methods are one object in every module, Python's are `_common`'s
            w = made.get(id(f))
            if w is None:
                w = made[id(f)] = _checked(f, _common._CACHE)
            saved.append((m, n, f))
            setattr(m, n, w)
    kl = sys.modules.get('knowledge_live')
    if kl is not None:
        kl.RECHECK[0] = lambda kind, value, cached, fresh: compare((kind,), cached, fresh)
    atexit.register(_write)

    def undo():
        for m, n, f in saved:
            setattr(m, n, f)
        if kl is not None:
            kl.RECHECK[0] = None
        STATE['on'] = False
    return undo


def pytest_sessionstart(session):
    install()


def pytest_sessionfinish(session):
    _write()
