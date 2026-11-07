"""Conversion on the real engine path (component 4, slice A, issue 323): the per-query table, the Kept route and a refusal
that reaches the top of the run. Installed from outside satassume. Pure Python stays the default.

`install()` wraps `sympy_api._ask`, which runs exactly on an answer-memo miss:

1. It converts the query and holds the table for the query's length, on a per-thread stack. `current()` is what every
   consumer reads. `knowledge_live` is one, and later slices of 4 are the rest. Nothing outlives the query.
2. A query conversion keeps runs on Python, counted as `kept:<reason>`.
3. `sa_solver.TermRefuse` is a BaseException, so no `except Exception` on the way can turn it into a quiet answer. That is
   seven handlers on the engine's path, not the two section 9 names: `engine.py:1906`, `sympy_api.py:1107`,
   `relations.py:1989`, `:2011`, `:2018`, `lra.py:461` (on Rust's solver `lra.rs:935`, which lets a BaseException up) and
   `lra_bounds.py:249`. Only the outermost `_ask` catches it. It
   discards the run, rolls back what the run wrote in Python (`_Mark`) and answers on Python, counted as `refused` and by
   reason. Everything nested in that second run stays on Python too: it can't refuse again.

What Rust's table is used for here: nothing that decides an answer. With `keys=True`, `_key` and `lra_adapter`'s
`default_sort_key` also ask Rust for the input term's key, drop the value, and let a refusal go. So a refusal here is a
real one, at the site that will use the key in slice B, and answers still come from Python's path.

A fault, meaning Rust or conversion failing where it has no reason to, raises `TermFault`, also a BaseException, and isn't
caught at all.

What the rollback doesn't cover, by design. SymPy's own caches and `_assumptions`: a discarded run's reads go through SymPy
as Python's own run does, and neither is ours to empty. `Dummy._count`: a template that builds a Dummy (`limits.py:92`) has
advanced it, and setting it back could make a later Dummy equal to one SymPy's cache still holds.
"""
import collections
import sys
import threading

import sa_solver

from satassume import engine, relations, sympy_api
from satassume.state import memos
from satassume.theories.lra import constfield, lra_adapter

import convert

#: Every `_ask` wrapper's counts. `knowledge_live.COUNTS` is this object.
COUNTS = collections.Counter()
#: (kind, id, exception type) of the first few reads that raised, across queries.
RAISED = []
MAX_RAISED = 50
#: (reason, repr of the proposition) of the first few refusals.
REFUSALS = []
MAX_REFUSALS = 200
#: term_discard.py's state check: called with the engine as the outermost run starts, past the mark, and with no arguments
#: between the rollback and the second run.
BEFORE_RUN = [None]
AFTER_ROLLBACK = [None]
#: Set by term_discard.py's plant: skip the rollback, to show the comparison catches a run that leaves something.
PLANT_NO_ROLLBACK = [False]


class TermFault(BaseException):
    """Rust failed where it has no reason to. Not an `Exception`, so no quiet handler reads it as "unknown"."""


class _Query:
    """One `_ask`'s table. `kept` is a reason, or None when the table is there."""
    __slots__ = ('table', 'ids', 'objects', 'kept', 'counts', 'raised')

    def __init__(self, c):
        if isinstance(c, convert.Kept):
            self.kept, self.table, self.ids, self.objects, self.counts, self.raised = c.reason, None, None, None, {}, ()
        else:
            self.kept = None
            self.table = sa_solver.TermTable(c.tables)
            self.ids, self.objects, self.counts = c.ids, c.objects, c.counts
            self.raised = c.raised


class _Refused(_Query):
    """The second run of a discarded query, and everything nested in it. A consumer sees `kept` and stays on Python."""
    __slots__ = ()

    def __init__(self):
        self.kept, self.table, self.ids, self.objects, self.counts, self.raised = 'refused', None, None, None, {}, ()


_local = threading.local()


def stack():
    try:
        return _local.stack
    except AttributeError:
        _local.stack = []
        return _local.stack


def current():
    """The innermost query's `_Query`, or None outside any."""
    s = stack()
    return s[-1] if s else None


def _journal():
    return getattr(_local, 'journal', None)


_NO_STAMP = object()


class _Mark:
    """What the run wrote, undone by size. A memo only grows during a run unless it's emptied, and a dict keeps insertion
    order, so the entries past the mark are the run's. One `len` and one last key a table per query. A table emptied during
    the run (restamped, or cleared when full) can regrow past the mark, and then what sits below the mark is the run's too:
    its last key shows that, its stamp shows a restamp, and the table is emptied, which is safe for a memo. What growth
    doesn't show: `DictCache.put` adding a predicate to a node already in the store, which `_put` journals, and a counter or
    flag, which are copied here."""

    def __init__(self, eng):
        self.tables = {}
        self.engines = {}
        self.cache = []
        for _, _, t in memos.PROCESS.items():
            self._note(t)
        for t in (constfield._CONSTANTS, constfield._BY_KEY):
            self._note(t)
        self.add(eng)

    def _note(self, t):
        self.tables[id(t)] = (t, len(t), getattr(t, 'stamp', _NO_STAMP), next(reversed(t), None) if len(t) else None)

    def add(self, eng):
        if id(eng) in self.engines:
            return
        self.engines[id(eng)] = (eng, dict(eng.stats), eng.last_budget_limited, set(eng._constructing))
        for _, _, t in eng.memos.items():
            self._note(t)

    def rollback(self):
        for facts, pred in reversed(self.cache):
            facts.pop(pred, None)
        for t, n, stamp, last in self.tables.values():
            if isinstance(t, list):
                if len(t) < n:
                    COUNTS['rollback:cleared'] += 1
                del t[n:]
                continue
            moved = stamp is not _NO_STAMP and t.stamp != stamp
            while len(t) > n:
                t.popitem()
            if moved or len(t) < n or (n and next(reversed(t)) is not last):
                if n:
                    COUNTS['rollback:cleared'] += 1
                dict.clear(t) if isinstance(t, dict) else t.clear()
            if moved:
                COUNTS['rollback:restamped'] += 1
                t.stamp = stamp
        for eng, st, budget, constructing in self.engines.values():
            eng.stats.clear()
            eng.stats.update(st)
            eng.last_budget_limited = budget
            eng._constructing.clear()
            eng._constructing.update(constructing)


_put = engine.DictCache.put


def _journaled_put(self, node, pred, value):
    j = _journal()
    if j is not None:
        facts = self.store.get(node)
        if facts is not None and pred not in facts:
            j.cache.append((facts, pred))
    return _put(self, node, pred, value)


def _note_query(q):
    # The reads this query really asked for, so `read_raised` here is never a forced read.
    for name, n in q.counts.items():
        if n and (name.startswith('read:') or name in ('read_raised', 'read_term_missing')):
            COUNTS[name] += n
    RAISED[len(RAISED):] = list(q.raised)[:max(0, MAX_RAISED - len(RAISED))]


def _convert(proposition, assumptions, eng):
    # This can sit inside a quiet handler when a query nests, so a failure here must not be an Exception.
    try:
        q = _Query(convert.convert(proposition, assumptions, eng))
    except Exception as e:
        COUNTS['fault'] += 1
        raise TermFault(f'conversion: {e}') from e
    if q.kept is not None:
        COUNTS['kept:' + q.kept] += 1
    else:
        COUNTS['converted'] += 1
    return q


def _key_consumer(site, real):
    """A real read of Rust's key at a site that will use it. The value is dropped, and a refusal goes on up."""
    def key(e, *a, **k):
        r = real(e, *a, **k)
        q = current()
        if q is None or q.kept is not None:
            return r
        i = q.ids.get(e)
        # `==` can join classes (Float against Integer), so a row counts only for its own class.
        if i is None or type(q.objects[i]) is not type(e):
            COUNTS['key:not-input:' + site] += 1
            return r
        COUNTS['key:asked:' + site] += 1
        try:
            q.table.sort_key(i)
        except Exception as x:
            COUNTS['fault'] += 1
            raise TermFault(f'key {site}: {type(x).__name__}: {x}') from x
        return r
    key.__wrapped__ = real
    return key


_undo = [None]
_installs = [0]


def installed():
    return _installs[0] > 0


def install(keys=False):
    """Returns a function that undoes this call. Calls nest: `knowledge_live` and a test can both ask for the wrapper, and
    the last undo removes it. `keys` isn't nesting's to change: the first caller's value stands."""
    _installs[0] += 1
    if _installs[0] == 1:
        _undo[0] = _install(keys)

    def undo():
        _installs[0] -= 1
        if _installs[0] == 0:
            _undo[0]()
            _undo[0] = None
    return undo


def _install(keys):
    py_ask = sympy_api._ask

    def _ask(proposition, assumptions, eng):
        s = stack()
        top = not s
        if top:
            mark = _local.journal = _Mark(eng)
            if BEFORE_RUN[0] is not None:
                BEFORE_RUN[0](eng)
        elif _journal() is not None:     # None in a second run: nothing there is rolled back
            _local.journal.add(eng)
        if not top and isinstance(s[-1], _Refused):
            q = s[-1]
            COUNTS['nested-in-refused'] += 1
        else:
            q = _convert(proposition, assumptions, eng)
        s.append(q)
        try:
            try:
                return py_ask(proposition, assumptions, eng)
            finally:
                s.pop()
                if not isinstance(q, _Refused):
                    _note_query(q)
                if top:
                    _local.journal = None
        except sa_solver.TermRefuse as e:
            if not top:
                raise
            refusal = e
        reason = str(refusal)
        COUNTS['refused'] += 1
        COUNTS['refused:' + reason] += 1
        if len(REFUSALS) < MAX_REFUSALS:
            REFUSALS.append((reason, repr(proposition)[:200]))
        if not PLANT_NO_ROLLBACK[0]:
            mark.rollback()
        if AFTER_ROLLBACK[0] is not None:
            AFTER_ROLLBACK[0]()
        s.append(_Refused())
        try:
            return py_ask(proposition, assumptions, eng)
        except sa_solver.TermRefuse as e:
            COUNTS['fault'] += 1
            raise TermFault(f'refused on the second run, which reads no table: {e}') from e
        finally:
            s.pop()

    sympy_api._ask = _ask
    engine.DictCache.put = _journaled_put
    py_key, py_sort = relations._key, lra_adapter.default_sort_key
    if keys:
        relations._key = _key_consumer('relations._key', py_key)
        lra_adapter.default_sort_key = _key_consumer('lra_adapter', py_sort)

    def undo():
        sympy_api._ask = py_ask
        engine.DictCache.put = _put
        relations._key, lra_adapter.default_sort_key = py_key, py_sort
    return undo


def counts():
    return dict(COUNTS)


def from_env(default='keys'):
    """SLICE_TERM: `keys` (the default), `table` (the table, and no consumer of it here), or `py` (not installed)."""
    import os
    mode = os.environ.get('SLICE_TERM', default)
    if mode == 'py':
        return None
    if mode not in ('keys', 'table'):
        print(f'SLICE_TERM={mode}: not a mode', file=sys.stderr)
        raise SystemExit(2)
    return install(keys=mode == 'keys')
