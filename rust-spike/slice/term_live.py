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

What Rust's table is used for depends on the mode. `keys` (slice A): `_key` and `lra_adapter`'s `default_sort_key` also ask
Rust for the input term's key, drop the value, and let a refusal go. Answers still come from Python's path.

`terms` (slice B, the default): `relation_atom`'s eq branch, `_termwise` and `_eq_links`'s difference are answered by Rust on
ids, so their answers now decide which atoms and clauses exist. The rest of the engine still holds SymPy objects until slice
C, so a derived term Rust returns is rebuilt in SymPy, as counted scaffolding (`scaffold:*`), checked against Rust's form,
refusing on any mismatch. That count must reach zero before any backend PR. A term with no id (one a template built, or from
an outer query's table) stays on Python for that one operation, counted as `term:py:<site>` and `term:unknown:<site>:<class>`.
At the two sort sites Python's key is still computed (the lra_adapter's until slice D, `_key` only on that fallback), so Rust's
key is asked for derived products too and must match it or refuse.

A fault, meaning Rust or conversion failing where it has no reason to, raises `TermFault`, also a BaseException, and isn't
caught at all.

What the rollback doesn't cover, by design. SymPy's own caches and `_assumptions`: a discarded run's reads go through SymPy
as Python's own run does, and neither is ours to empty. `Dummy._count`: a template that builds a Dummy (`limits.py:92`) has
advanced it, and setting it back could make a later Dummy equal to one SymPy's cache still holds.
"""
import collections
import os
import sys
import threading

import sa_solver
from sympy import Add, Mul, S
from sympy.core.basic import Basic
from sympy.core.numbers import Rational

from satassume import engine, relations, scope, sympy_api
from satassume.knowledge.extensions import Args
from satassume.knowledge.templates import _common
from satassume.sat.formula import And, Not, P
from satassume.state import memos
from satassume.theories.euf import euf_adapter
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
    __slots__ = ('table', 'ids', 'objects', 'kept', 'counts', 'raised', 'derived', 'rev', 'memo', 'ints', 'int_ids', 'classes')

    def __init__(self, c):
        # Derived terms this query has met: {SymPy term: id} and {id: SymPy term}. Apart from `ids`, which other consumers
        # index `objects` by. Plain Python int sides (`_int_id`): {id: int} and {int: id}, apart from `derived`, so `scaffold`
        # never gives one.
        self.derived, self.rev = {}, {}
        self.ints, self.int_ids = {}, {}
        # The per-query form of a cross-query memo (ruling on memos): `_under_apps`, `zero_twin`. Dies with the query.
        self.memo = {}
        # The query's own class table, {class: class id} by the classes' hash and `==` (convert._Walk.classes): `same_class`.
        self.classes = None
        if isinstance(c, convert.Kept):
            self.kept, self.table, self.ids, self.objects, self.counts, self.raised = c.reason, None, None, None, {}, ()
        else:
            self.kept = None
            self.classes = c.classes
            self.table = sa_solver.TermTable(c.tables)
            self.ids, self.objects, self.counts = c.ids, c.objects, c.counts
            self.raised = c.raised
            self.derived, self.rev = {}, {}


class _Refused(_Query):
    """The second run of a discarded query, and everything nested in it. A consumer sees `kept` and stays on Python."""
    __slots__ = ()

    def __init__(self):
        self.derived, self.rev = {}, {}
        self.ints, self.int_ids = {}, {}
        self.classes = None
        self.kept, self.table, self.ids, self.objects, self.counts, self.raised = 'refused', None, None, None, {}, ()


class _Seen:
    """formula.rs `SEEN`, the objects converted since the outermost entry began (`fm:twice`'s record): marked and rolled back
    with the rest (the gate for sa-port-269 (4)). A top query's discard happens outside any entry, where it is empty."""
    native, name = True, 'formula.SEEN'

    def items(self):
        return [(o, (first, tuple(more))) for o, first, more in sa_solver.formula_seen_rows()]

    def _nt_mark(self):
        return sa_solver.formula_seen_rows()

    def _nt_rollback(self, rows):
        sa_solver.formula_seen_restore(rows)
        return False


class _Kept:
    """formula.rs `KEPT`, plant 608's store. Read by the discard's check and not rolled back: its only writer is the plant
    (`Hand`'s drop under `fm-hand-kept`), so without the plant it is empty before and after."""
    native, name = True, 'formula.KEPT'

    def items(self):
        return [((k,), True) for k in sa_solver.formula_kept_rows()]


class _LraLive:
    """adapters.rs `LIVE`, what `lra_live.install` registered. Read by the discard's check and not rolled back: only
    `ad_lra_live` writes it, and no query calls that. (An adapter's own slot is keyed by its query object, which it holds;
    a refused run's query is never the current one again, so nothing reads what that run stored.)"""
    native, name = True, 'adapters.LIVE'

    def items(self):
        return [((i,), x) for i, x in enumerate(sa_solver.ad_lra_live_get() or ())]


#: Rust stores outside the memo registry that a discard marks, rolls back (those with `_nt_mark`) and checks (term_discard.py
#: reads every one). knowledge_live's `install_dispatch` adds Rust's dispatch memo and class cache.
NATIVE_EXTRA = [_Seen(), _Kept(), _LraLive()]

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
    flag, which are copied here. A `defaultdict(dict)` table (`lra_adapter._INTERPRETED`) grows inside its values once its key
    exists, so each value is a table too: an entry left there can hold a `_CONSTANTS` index this rollback frees."""

    def __init__(self, eng):
        self.tables = {}
        self.natives = {}
        self.engines = {}
        self.cache = []
        self.facts = {}
        self.cache_n = len(_common._CACHE)
        for _, _, t in memos.PROCESS.items():
            # The pattern cache is not rolled back (the `_CACHE` fix, issue 323, sa-port-248; ruling R3). When that was
            # ruled, Rust's memo of compiled nodes (dispatch.rs `Dispatch.memo`, which stands in for
            # `registry._clauses_cache`) and the native `_SPLIT` kept what the discarded run wrote and held the run's
            # patterns: the second run was served those nodes and never asked for their patterns again, so a `_CACHE` cut
            # back to the mark stayed short of the keys Python holds (f6: `cosh(y + 1*I*pi)`, refused for an LRA callback
            # on a derived term, left 1 key of Python's 6). Both are rolled back now (`_SPLIT` since 1a91a81, the dispatch
            # memo through `NATIVE_EXTRA`); `_CACHE` stays as ruled. Leaving its entries is safe because the key determines
            # the value (cache_det.py): the entry the discarded run left is the one any later run would build. Plant 666
            # `mark-wrong-pattern` breaks that at this site: one entry the run added gets another key's pattern.
            if t is _common._CACHE:
                continue
            self._note(t)
        for t in (constfield._CONSTANTS, constfield._BY_KEY):
            self._note(t)
        for t in NATIVE_EXTRA:
            self._note(t)
        self.add(eng)

    def _note(self, t):
        if getattr(t, 'native', False):
            # A Rust-native table's view (memos.rs `NativeTable`, engmemo.rs `EngineMemo`): Rust's map marks itself and takes
            # out what the run added (the planner's ruling on lra's cause, issue 323: a discarded run left its `_Split` in
            # `Engine.splits` and its verdict in `Engine._verdict`, and the rerun read them). A fact cache's view has its own
            # mark (`add`).
            if hasattr(t, '_nt_mark'):
                self.natives[id(t)] = (t, t._nt_mark())
            return
        self.tables[id(t)] = (t, len(t), getattr(t, 'stamp', _NO_STAMP), next(reversed(t), None) if len(t) else None)
        if isinstance(t, collections.defaultdict) and t.default_factory is dict:
            for inner in t.values():
                self._note(inner)

    def add(self, eng):
        if id(eng) in self.engines:
            return
        st = eng.stats     # Rust-owned since 5c10d (entry.rs `EngineStats`): snapshot and restore through its own methods
        mark = st._st_mark() if hasattr(st, '_st_mark') else (dict(st), eng.last_budget_limited)
        self.engines[id(eng)] = (eng, mark, set(eng._constructing))
        for c in (eng.cache, eng.custom_cache):     # a Rust-native fact cache (factcache.rs, step 5c10a) marks itself
            if id(c) not in self.facts and hasattr(c, '_fc_mark'):
                self.facts[id(c)] = (c, c._fc_mark())
        for _, _, t in eng.memos.items():
            self._note(t)

    def rollback(self):
        if PLANT[0] == 'mark-wrong-pattern':
            _wrong_pattern(self.cache_n)
        for facts, pred in reversed(self.cache):
            facts.pop(pred, None)
        for c, m in self.facts.values():
            if c._fc_rollback(m):
                COUNTS['rollback:cleared'] += 1
        # plant 611 'mark-skips-native': the native tables keep what the discarded run wrote; 'mark-skips-native:NAME' only
        # the table of that name (`splits`, `satassume.relations._SYMPY_ATOMS`, ...)
        skip = (PLANT[0] or '').partition('mark-skips-native')[1:] if (PLANT[0] or '').startswith('mark-skips-native') else None
        for t, m in self.natives.values():
            if skip is not None and skip[1] in ('', ':' + t.name):
                COUNTS['plant:mark-skips-native'] += 1
                continue
            COUNTS['rollback:native'] += 1
            if t._nt_rollback(m):
                COUNTS['rollback:cleared'] += 1
        leave = PLANT[0] == 'mark-leaves-entry'
        for t, n, stamp, last in self.tables.values():
            if leave and not isinstance(t, list) and t is not _common._CACHE and len(t) > n:
                # plant 667: the first table the run grew keeps the run's entries (term_discard.py must name it; its
                # `_CACHE` exemption must not cover any other container)
                leave = False
                COUNTS['plant:mark-leaves-entry'] += 1
                continue
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
        for eng, mark, constructing in self.engines.values():
            if hasattr(eng.stats, '_st_rollback'):
                eng.stats._st_rollback(mark)
            else:
                eng.stats.clear()
                eng.stats.update(mark[0])
                eng.last_budget_limited = mark[1]
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
        if i is None or not same_class(q, q.objects[i], e):
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


# ---- Slice B: term work through ids

#: Examples of what scaffolding refused, first few.
SCAFFOLD_BAD = []
#: `(site, Python's key, Rust's key)` for a sort site that disagreed, first few.
KEY_BAD = []
#: Test plants on Rust's answers: 'swap' reverses `eq_sides`, 'termwise-true' and 'termwise-false' fix `_termwise`, 'no-strip'
#: drops `_affine_strip` where it changed a side, 'key-reverse' flips a matched key, 'scaffold-form' fails the form check.
#: Slice C's: 'le-swap', 'no-ext', 'is-number-false', 'affine-false', 'linked-drop', 'under-empty', 'interned-reversed',
#: 'plan-drop', 'plan-pred', 'twin-one'. State step (iii)(a): plant 265 'int-as-number' (`_int_id`; counter 346 `term:int:*`).
#: The formula step: 666 'mark-wrong-pattern' (`_Mark.rollback` gives a `_CACHE` entry of the run another key's pattern), 667 'mark-leaves-entry' (`rollback` skips the
#: first other table the run grew), 611 'mark-skips-native' (`rollback` leaves the Rust-native tables as the run left them).
PLANT = [None]
#: A compiled pattern's fields (cache_det.py's FIELDS): plant 666 picks a pattern that differs from the one it replaces.
_PATTERN_FIELDS = ('rules', 'node', 'nobjs', 'clauses', 'used', 'child_preds', 'complete', 'wide')


def _wrong_pattern(n):
    """Plant 666 `mark-wrong-pattern` (`_Mark.rollback`): the first `_CACHE` entry the discarded run added (past the mark's
    `n` keys) takes the pattern of another key whose pattern differs in some field. `_CACHE` is kept after a discard because
    its key determines its value (ruling R3); after this the key no longer does, and cache_det.py (a hit's own build against
    the cached pattern) and the digest's `_CACHE` row (keys and values against Python's) must see it."""
    c = _common._CACHE
    keys = list(c)
    # first a pattern of the same shape (node slot and object count, which `_common.facts` checks and raises on), so the
    # wrong value goes through quietly; else any pattern that differs
    for shaped in (True, False):
        for k in keys[n:]:
            v = c[k]
            if v is None:
                continue
            for k2 in keys:
                w = c[k2]
                if k2 == k or w is None or not any(getattr(w, f, None) != getattr(v, f, None) for f in _PATTERN_FIELDS):
                    continue
                if shaped and (getattr(w, 'node', None) != getattr(v, 'node', None) or getattr(w, 'nobjs', None) != getattr(v, 'nobjs', None)):
                    continue
                c[k] = w
                COUNTS['plant:mark-wrong-pattern'] += 1
                COUNTS['plant:mark-wrong-pattern:shaped' if shaped else 'plant:mark-wrong-pattern:any'] += 1
                return


def same_class(q, a, b):
    """Whether `a` and `b` are of one class to query `q`. The same class object, or two class objects with one id in the
    query's own class table (`q.classes`, keyed by the classes' hash and `==` when the input was converted): two
    `Function('f')` are one class to SymPy and two objects, and which object a process-wide memo hands back follows history
    (`ad:cbm_noid`, results/cbm-noid-cause.md). The table is the query's, never the process's, and a class the query's input
    doesn't hold has no id, so it is one class only with itself. Every site that takes a row for a term asks here; Rust's
    sites ask `term::same_class`, the same rule."""
    ta, tb = type(a), type(b)
    if ta is tb:
        return True
    if sa_solver.class_is_plant():      # plant 661 (one plant for Rust's half and this one): the identity compare back
        return False
    c = q.classes
    try:
        i = c.get(ta) if c is not None else None
        same = i is not None and c.get(tb) == i
    except TypeError:                   # an unhashable class: no id
        same = False
    COUNTS['class:eq' if same else 'class:differs'] += 1
    return same
#: SLICE_TERM_CHECK: at each answer from Rust, also run Python's own function and compare, counted as `check:same:<site>` and
#: `check:differs:<site>`, with the first few in `CHECK_BAD`. It builds in SymPy, so it's for evidence, never for a number
#: that's quoted: the answer returned is Rust's either way.
CHECK = [False]
CHECK_BAD = []


def _check(site, same, *detail):
    COUNTS[('check:same:' if same else 'check:differs:') + site] += 1
    if not same and len(CHECK_BAD) < 50:
        CHECK_BAD.append((site,) + tuple(repr(x)[:200] for x in detail))


def _refuse(reason):
    raise sa_solver.TermRefuse(reason)


def term_id(q, e, site):
    """Rust's id of a SymPy term, or None if Rust has none. An `Add` or `Mul` that Python built of terms with ids gets one with
    its args as they are, so its form isn't in question. Any other class Python built has no row."""
    i = q.ids.get(e) if isinstance(e, Basic) else None
    if i is not None:
        # `==` can join classes (Float against Integer), so a row counts only for its own class.
        return i if same_class(q, q.objects[i], e) else None
    if not isinstance(e, Basic):
        if type(e) is int and site in _INT_SITES:
            return _int_id(q, e, site)
        COUNTS[f'term:unknown:{site}:{type(e).__name__}'] += 1
        return None
    i = q.derived.get(e)
    if i is not None:
        return i if same_class(q, q.rev[i], e) else None
    cls = type(e)
    if isinstance(e, Rational):
        i = q.table.number(e.p, e.q)
    elif (cls is Add or cls is Mul) and e.is_commutative is True:
        args = [term_id(q, a, site) for a in e.args]
        if None in args:
            return None
        i = q.table.raw_add(args) if cls is Add else q.table.raw_mul(args)
        COUNTS['term:learned'] += 1
    else:
        COUNTS[f'term:unknown:{site}:{cls.__name__}'] += 1
        return None
    if i >= q.table.n_input:
        q.derived[e] = i
        q.rev.setdefault(i, e)
    return i


def _scaffold_bad(i, o, why):
    COUNTS['scaffold:mismatch'] += 1
    if len(SCAFFOLD_BAD) < 20:
        SCAFFOLD_BAD.append((why, repr(o)[:200]))
    _refuse('scaffold: ' + why)


def scaffold(q, i, site):
    """The SymPy object of id `i`. A derived term Python has never seen is rebuilt with SymPy's own constructors, as temporary
    construction on the slice branch: counted, and checked against Rust's form, refusing on a mismatch."""
    t = q.table
    if i < t.n_input:
        return q.objects[i]
    o = q.rev.get(i)
    if o is not None:
        return o
    row = t.row(i)
    args = row[0]
    name = t.class_row(i)[0]
    if not args:
        if not (isinstance(row[1], tuple) and len(row[1]) == 2):
            _scaffold_bad(i, row[1], 'a derived term with no args that is not a number')
        o = Rational(row[1][0], row[1][1])
        COUNTS['scaffold:rebuilt'] += 1
        COUNTS['scaffold:rebuilt:' + site] += 1
        if (o.p, o.q) != row[1] or type(o).__name__ != name:
            _scaffold_bad(i, o, 'number')
    else:
        f = {'Add': Add, 'Mul': Mul}.get(name)
        if f is None:
            _scaffold_bad(i, name, 'a derived class other than Add and Mul')
        kids = [scaffold(q, a, site) for a in args]
        o = f(*kids)
        COUNTS['scaffold:rebuilt'] += 1
        COUNTS['scaffold:rebuilt:' + site] += 1
        # Rust's form: the same class, and the same args in the same order, each of its own class.
        if (type(o).__name__ != name or len(o.args) != len(kids) or PLANT[0] == 'scaffold-form'
                or any(x != y or not same_class(q, x, y) for x, y in zip(o.args, kids))):
            _scaffold_bad(i, o, 'rebuilt form differs from Rust')
    k = q.ids.get(o)
    if k is None:
        k = q.derived.get(o)
    if k is not None and k != i:
        _scaffold_bad(i, o, 'rebuilt term has another id')
    q.derived[o] = i
    q.rev[i] = o
    return o


def _guarded(site, f):
    """An ordinary exception from Rust or from this layer can't turn quiet in a handler on the engine's path."""
    def g(*a, **k):
        try:
            return f(*a, **k)
        except Exception as x:
            COUNTS['fault'] += 1
            raise TermFault(f'{site}: {type(x).__name__}: {x}') from x
    g.__wrapped__ = f
    return g


#: The sites whose Rust work reads a plain int side as Python does (state step (iii)(a)): `_is_number` False, skipped by
#: `_under_apps` and `_structural_subterms`, `extended_real` needed, no `_affine_strip`, Integer's sort key.
_INT_SITES = frozenset({'relation_atom', '_is_number', '_under_apps', '_structural_subterms', '_ext_atoms', 'key'})


def _int_id(q, e, site):
    """A plain Python `int` side, as user code passes `relation_atom('lt', s, 1)`: Rust's foreign leaf for it (`py_int`),
    never an `Integer` row, so Python's `_is_number(1)` False and the rest hold. The plant 'int-as-number' maps it to the
    `Integer` row instead, which is what this mustn't do."""
    COUNTS['term:int:' + site] += 1
    if PLANT[0] == 'int-as-number':
        return q.table.number(e, 1)
    i = q.int_ids.get(e)
    if i is None:
        i = q.int_ids[e] = q.table.py_int(e)
        q.ints[i] = e
    return i


def _ids(q, site, *terms):
    if q is None or q.kept is not None:
        COUNTS['term:no-table:' + site] += 1
        if q is None:   # Step scope: outside any query, as against inside a kept one.
            COUNTS['term:no-query:' + site] += 1
        return None
    ids = [term_id(q, e, site) for e in terms]
    if None in ids:
        COUNTS['term:py:' + site] += 1
        return None
    COUNTS['term:rust:' + site] += 1
    return ids


def _relation_atom(py):
    """`relation_atom` on ids. Rust says which side goes where, by position, so Python keeps the objects it was given and only
    a stripped side is rebuilt. A formula over P atoms stays Python's until component 5."""
    def eq(q, name, lhs, rhs, l, r):
        a, b = q.table.eq_sides(l, r)
        if PLANT[0] == 'swap':
            a, b = b, a
        if PLANT[0] == 'no-strip' and {a, b} != {l, r}:
            a, b = l, r
        # What Python would hold: the objects it was given, when they weren't stripped.
        x = lhs if a == l else rhs if a == r else scaffold(q, a, 'relation_atom')
        y = lhs if b == l else rhs if b == r else scaffold(q, b, 'relation_atom')
        atom = P("eq", Args((x, y)))
        return atom if name == 'eq' else Not(atom)

    def order(q, name, lhs, rhs, l, r):
        plan = q.table.order_relation(name, l, r)
        if plan is None:
            return False
        first, second, negated, ext = plan
        if PLANT[0] == 'le-swap' and negated:
            first, second = second, first
        if PLANT[0] == 'no-ext':
            ext = []
        sides = (lhs, rhs)
        f = P("lt", Args((sides[first], sides[second])))
        if not negated:
            return f
        f = Not(f)
        return And(*[P("extended_real", sides[p]) for p in ext], f) if ext else f

    def run(name, lhs, rhs):
        if name not in _RELATIONS:
            return None
        q = current()
        ids = _ids(q, 'relation_atom', lhs, rhs)
        if ids is None:
            return None
        f = eq if name in ('eq', 'ne') else order
        COUNTS['relation_atom:' + name] += 1
        got = f(q, name, lhs, rhs, *ids)
        if CHECK[0]:
            want = py(name, lhs, rhs)
            _check('relation_atom', want == got and _same_sides(want, got), name, lhs, rhs, want, got)
        return (got,)
    run = _guarded('relation_atom', run)

    def relation_atom(name, lhs, rhs):
        got = run(name, lhs, rhs)
        return py(name, lhs, rhs) if got is None else got[0]
    relation_atom.__wrapped__ = py
    return relation_atom


_RELATIONS = frozenset(('eq', 'ne', 'lt', 'gt', 'le', 'ge'))


def _same_sides(want, got):
    """The same classes in the sides of the atoms of two equal formulas, since `==` can join classes."""
    def atoms(f):
        if isinstance(f, P):
            yield f
        else:
            for x in getattr(f, 'args', ()) or ():
                yield from atoms(x)
    return all(type(u) is type(v) for x, y in zip(atoms(want), atoms(got)) if isinstance(x.expr, tuple) and isinstance(y.expr, tuple)
               for u, v in zip(x.expr, y.expr))


def _obj(q, i, site):
    if i < q.table.n_input:
        return q.objects[i]
    e = q.ints.get(i)
    return scaffold(q, i, site) if e is None else e


def _ext_atoms(py):
    """`_ext_atoms` on ids: Rust's test on each side, the sides Python's objects."""
    run = _guarded('_ext_atoms', lambda q, sides: _ids(q, '_ext_atoms', *sides))

    def ext_atoms(*sides):
        q = current()
        ids = run(q, sides)
        if ids is None:
            return py(*sides)
        got = [P("extended_real", e) for e, i in zip(sides, ids) if q.table.needs_ext(i)]
        if PLANT[0] == 'no-ext':
            got = []
        if CHECK[0]:
            want = py(*sides)
            _check('_ext_atoms', want == got, sides, want, got)
        return got
    ext_atoms.__wrapped__ = py
    return ext_atoms


def _is_number(py):
    """`_is_number` on ids, which is the term work of `zero_args` and `scope.linked_terms` and every other caller."""
    def run(e):
        q = current()
        ids = _ids(q, '_is_number', e)
        if ids is None:
            return None
        got = q.table.is_number_term(ids[0])
        if PLANT[0] == 'is-number-false':
            got = False
        if CHECK[0]:
            want = py(e)
            _check('_is_number', want == got, e, want, got)
        return got
    run = _guarded('_is_number', run)

    def is_number(e):
        if not isinstance(e, Basic) and type(e) is not int:
            return py(e)
        got = run(e)
        return py(e) if got is None else got
    is_number.__wrapped__ = py
    return is_number


def _affine_pair(py):
    """`scope.affine_pair` on ids: the atoms stay Python's, their sign-atom arguments go to Rust in order."""
    def run(atoms):
        q = current()
        signs = [a.expr for a in atoms if a.pred in scope.SIGN_PREDS]
        ids = _ids(q, 'affine_pair', *signs)
        if ids is None:
            return None
        got = q.table.affine_pair(ids)
        if got:
            COUNTS['affine_pair:True'] += 1
        if PLANT[0] == 'affine-false':
            got = False
        if CHECK[0]:
            want = py(atoms)
            _check('affine_pair', want == got, signs, want, got)
        return got
    run = _guarded('affine_pair', run)

    def affine_pair(atoms):
        atoms = list(atoms)
        got = run(atoms)
        return py(atoms) if got is None else got
    affine_pair.__wrapped__ = py
    return affine_pair


def _linked_terms(py):
    """`scope.linked_terms` is Python's over `_is_number`'s ids. This only counts it, and holds the plant."""
    def linked_terms(atoms):
        got = py(atoms)
        COUNTS['linked_terms'] += 1
        if got:
            COUNTS['linked_terms:nonempty'] += 1
        if PLANT[0] == 'linked-drop' and got:
            return frozenset(sorted(got, key=str)[1:])
        return got
    linked_terms.__wrapped__ = py
    return linked_terms


def _under_apps(py):
    """`_under_apps` on ids, memoized per query and not across queries. Its consumers only test membership."""
    def run(e):
        q = current()
        sides = e if isinstance(e, tuple) else (e,)
        if not all(isinstance(x, Basic) or type(x) is int for x in sides):
            return None
        ids = _ids(q, '_under_apps', *sides)
        if ids is None:
            return None
        key = ('under', tuple(ids))
        got = q.memo.get(key)
        if got is None:
            found = q.table.under_apps(ids)
            if found is None:
                COUNTS['term:py:_under_apps:own-atoms'] += 1
                return None
            got = q.memo[key] = frozenset(_obj(q, i, '_under_apps') for i in found)
            if got:
                COUNTS['under_apps:nonempty'] += 1
        if PLANT[0] == 'under-empty':
            got = frozenset()
        if CHECK[0]:
            want = py(e)
            _check('_under_apps', want == got, e, want, got)
        return got
    run = _guarded('_under_apps', run)

    def under_apps(e):
        got = run(e)
        return py(e) if got is None else got
    under_apps.__wrapped__ = py
    return under_apps


def _zero_twin(py):
    """`zero_twin` under the per-query memo: `relation_atom`'s eq on ids."""
    def zero_twin(e):
        q = current()
        if q is None or q.kept is not None:
            return py(e)
        tw = q.memo.get(('twin', e))
        if tw is None:
            COUNTS['zero_twin'] += 1
            tw = q.memo[('twin', e)] = relations.relation_atom('eq', e, S.One if PLANT[0] == 'twin-one' else S.Zero)
        return tw
    zero_twin.__wrapped__ = py
    return zero_twin


def _structural(py):
    """`euf_adapter.structural`: conversion's class bit, and args. A term with no id is Python's."""
    def run(e):
        q = current()
        ids = _ids(q, 'structural', e)
        if ids is None:
            return None
        got = q.table.structural(ids[0])
        if CHECK[0]:
            want = py(e)
            _check('structural', want == got, e, want, got)
        return got
    run = _guarded('structural', run)

    def structural(e):
        got = run(e)
        return py(e) if got is None else got
    structural.__wrapped__ = py
    return structural


def _interned(py):
    """`EUFAdapter.interned` on ids, in its order. `_intern` stays Python's: its dicts outlive the query, until component 5."""
    def run(exprs):
        q = current()
        ids = _ids(q, 'interned', *exprs)
        if ids is None:
            return None
        return [_obj(q, i, 'interned') for i in q.table.interned(ids)]
    run = _guarded('interned', run)

    def interned(self, exprs):
        exprs = list(exprs)
        got = run(exprs)
        if got is None:
            return py(self, exprs)
        if PLANT[0] == 'interned-reversed':
            got.reverse()
        if CHECK[0]:
            want = py(self, exprs)
            _check('interned', want == got, exprs, want, got)
        return got
    interned.__wrapped__ = py
    return interned


def _structural_subterms(py):
    """`relations._structural_subterms` on ids, in its order."""
    def run(e):
        q = current()
        ids = _ids(q, '_structural_subterms', e)
        if ids is None:
            return None
        return [_obj(q, i, '_structural_subterms') for i in q.table.structural_subterms(ids[0])]
    run = _guarded('_structural_subterms', run)

    def subterms(e):
        got = run(e) if isinstance(e, Basic) or type(e) is int else None
        if got is None:
            return py(e)
        if CHECK[0]:
            want = py(e)
            _check('_structural_subterms', want == got, e, want, got)
        return got
    subterms.__wrapped__ = py
    return subterms


def _termwise(py):
    """`_termwise` on ids, for any caller left with a `d` Python built, which has to be what Rust builds. The glue, its only
    caller on the engine's path, now asks Rust directly: `_glue_objects`."""
    def run(a, b, d):
        q = current()
        ids = _ids(q, '_termwise', a, b, d)
        if ids is None:
            return None
        i, j, k = ids
        if q.table.sub(i, j) != k:
            COUNTS['term:sub-differs'] += 1
            _refuse("termwise: Python's difference isn't Rust's")
        got = q.table.termwise(i, j, k)
        if CHECK[0]:
            want = py(a, b, d)
            _check('_termwise', want == got, a, b, d, want, got)
        return got
    run = _guarded('_termwise', run)

    def termwise(a, b, d):
        got = run(a, b, d)
        return py(a, b, d) if got is None else got
    termwise.__wrapped__ = py
    return termwise


def _glue_objects(py):
    """`glue_objects`' eq branch on ids (slice C): Rust's difference and `_termwise`, and `d` joins the cone's objects only as
    a rebuilt object, since `_struct` reads SymPy terms until component 5. Which nodes join is what the budget weighs, so a
    wrong answer here moves weights and can move a verdict near the budget. What the adapters read stays theirs."""
    term = _guarded('glue_objects', lambda q, a, b: _ids(q, 'glue_objects', a, b))

    def diff(q, u, v, p, m):
        t = q.table
        d = t.sub(u, v)
        if t.is_number_term(d):
            return None
        COUNTS['glue:termwise'] += 1
        real_wise = t.termwise(u, v, d)
        COUNTS['glue:termwise:' + str(real_wise)] += 1
        wise = True if PLANT[0] == 'termwise-true' else False if PLANT[0] == 'termwise-false' else real_wise
        o = scaffold(q, d, 'glue_objects') if wise else None
        if CHECK[0]:
            real = p - m
            want = None if relations._is_number.__wrapped__(real) or not relations._termwise.__wrapped__(p, m, real) else real
            _check('glue_objects', want == o and type(want) is type(o), p, m, want, o)
        return o
    diff = _guarded('glue_objects', diff)
    numbers = _guarded('glue_objects', lambda q, i, j: q.table.is_number_term(i) or q.table.is_number_term(j))

    def glue_objects(atom, specs, memo):
        sides = tuple(atom.expr)
        if atom.pred != 'eq' or len(sides) != 2:
            return py(atom, specs, memo)
        q = current()
        ids = term(q, *sides)
        if ids is None:
            return py(atom, specs, memo)
        i, j = ids
        a, b = sides
        k = set()
        for e in sides:
            k.add(e)
            if not relations._is_number(e):
                k.update(relations.link_objects(e, specs, memo))
        if not numbers(q, i, j):
            for u, v, p, m in ((i, j, a, b), (j, i, b, a)):
                d = diff(q, u, v, p, m)
                if d is not None:
                    k.add(d)
        if specs:
            try:
                sat = relations.sympy_atom(atom)
                for ad in relations._guarded_adapters(specs, memo):
                    k.update(relations._terms_of(ad, sat, False))
            except Exception as x:   # noqa: BLE001 (sides the adapters cannot read): as `glue_objects`. A refusal and a fault pass
                COUNTS['caught:glue_objects:' + type(x).__name__] += 1
        k.discard(atom)
        return k
    glue_objects.__wrapped__ = py
    return glue_objects


def _plant_plan(plan):
    """The plan plants: a dropped clause and a swapped pred, each on the plan's last clause."""
    if PLANT[0] == 'plan-drop' and plan:
        return plan[:-1]
    if PLANT[0] == 'plan-pred' and plan:
        swap = {'zero': 'nonzero', 'nonzero': 'zero', 'positive_infinite': 'negative_infinite',
                'negative_infinite': 'positive_infinite'}
        ens, lits = plan[-1]
        return plan[:-1] + [(ens, [(n, swap.get(p, p), t) for n, p, t in lits])]
    return plan


def _run_plan(self, q, plan, var, g, given, site):
    """A plan from Rust, left to right on the session, so var numbering holds. `g` runs after each clause's literals. `s.var` holds SymPy objects until component 5: `given` are the objects the
    atom holds, and a derived id is rebuilt."""
    s = self.session

    def obj(i):
        return given[i] if i in given else _obj(q, i, site)
    for ens, lits in plan:
        if ens is not None:
            s.ensure(obj(ens[0]), set(ens[1]))
            continue
        clause = [(-var if n else var) if p is None else (-s.var(p, obj(t)) if n else s.var(p, obj(t))) for n, p, t in lits]
        clause.append(g())
        s.emit(clause)


def _eq_links(py):
    """`Relations._eq_links`: Rust returns the clauses as a plan over ids. A difference used here is scaffolding."""
    def plan_of(q, i, j, a, b):
        plan = q.table.eq_links_plan(i, j)
        if PLANT[0] == 'termwise-false':
            plan = [op for op in plan if (op[0] is None or op[0][0] in (i, j))
                    and (op[0] is not None or all(t in (i, j) or p is None for _, p, t in op[1]))]
        if CHECK[0]:
            got = [_obj(q, op[0][0], '_eq_links') for op in plan if op[0] is not None and 'zero' in op[0][1]]
            want = []
            if plan:
                for p, m in ((a, b), (b, a)):
                    real = p - m
                    if not (relations._is_number.__wrapped__(real) or not relations._termwise.__wrapped__(p, m, real)):
                        want.append(real)
            _check('_eq_links', want == got and all(type(x) is type(y) for x, y in zip(want, got)), a, b, want, got)
        return _plant_plan(plan)
    plan_of = _guarded('_eq_links', plan_of)
    term = _guarded('_eq_links', lambda q, a, b: _ids(q, '_eq_links', a, b))

    def eq_links(self, var, atom):
        a, b = atom.expr
        q = current()
        ids = term(q, a, b)
        if ids is None:
            return py(self, var, atom)
        i, j = ids
        plan = plan_of(q, i, j, a, b)
        if not plan:
            return
        g = -self._atom_selector(atom)
        COUNTS['plan:_eq_links'] += 1
        _run_plan(self, q, plan, var, lambda: g, {i: a, j: b}, '_eq_links')
    eq_links.__wrapped__ = py
    return eq_links


def _tagged(got):
    """`term_shadow._tagged`: a value of Rust's that is a term, a Rational or an opaque one, not a tuple of the key's."""
    return (got[0] == 'T' and len(got) == 2) or (got[0] == 'Q' and len(got) == 3) or (got[0] == 'O' and len(got) == 2)


def _same_key(got, real, q):
    """Rust's key against Python's, by `term_shadow.same_value`'s rule (`key=True`), with `term_id` for its id lookup, so a
    term inside a key can be derived."""
    if isinstance(real, tuple):
        return (isinstance(got, tuple) and len(got) == len(real) and not (got and got[0] in ('T', 'Q', 'O') and _tagged(got))
                and all(_same_key(a, b, q) for a, b in zip(got, real)))
    if isinstance(real, Rational):
        return isinstance(got, tuple) and got == ('Q', real.p, real.q)
    if isinstance(real, Basic):
        return isinstance(got, tuple) and got == ('T', term_id(q, real, 'key'))
    if real is None or real is True or real is False:
        return got is real
    if isinstance(real, str):
        return type(got) is str and got == real
    try:
        i = int(real)
    except Exception:
        return isinstance(got, tuple) and len(got) == 2 and got[0] == 'O'
    return type(got) is int and got == i and i == real


def _key_match(site, real):
    """A sort site whose key Python still computes: Rust's key for the same term, input or derived, must match or refuse."""
    def ask(e, r):
        q = current()
        if q is None or q.kept is not None:
            return
        i = term_id(q, e, 'key')
        if i is None:
            COUNTS['key:not-known:' + site] += 1
            return
        COUNTS['key:asked:' + site] += 1
        if i >= q.table.n_input:
            COUNTS['key:derived:' + site] += 1
        got = q.table.sort_key(i)
        if PLANT[0] == 'key-reverse':
            got = ('reversed', got)
        if not _same_key(got, r, q):
            COUNTS['key:mismatch:' + site] += 1
            if len(KEY_BAD) < 20:
                KEY_BAD.append((site, repr(e)[:200], repr(r)[:300], repr(got)[:300]))
            _refuse("key: differs from Python's")
    ask = _guarded(site, ask)

    def key(e, *a, **k):
        r = real(e, *a, **k)
        if not a and not k:
            ask(e, r)
        return r
    key.__wrapped__ = real
    return key


_undo = [None]
_installs = [0]


def installed():
    return _installs[0] > 0


def install(keys=False, terms=False):
    """Returns a function that undoes this call. Calls nest: `knowledge_live` and a test can both ask for the wrapper, and
    the last undo removes it. `keys` and `terms` aren't nesting's to change: the first caller's values stand."""
    _installs[0] += 1
    if _installs[0] == 1:
        _undo[0] = _install(keys, terms)

    def undo():
        _installs[0] -= 1
        if _installs[0] == 0:
            _undo[0]()
            _undo[0] = None
    return undo


def _install(keys, terms):
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
    # Step 5c10a: a Rust-native fact cache rolls back by its own mark (`_Mark.add`); `_journaled_put` stays for SLICE_FACTCACHE=py.
    import session_live
    if not session_live.factcache_native():
        engine.DictCache.put = _journaled_put
    py_key, py_sort = relations._key, lra_adapter.default_sort_key
    if keys:
        relations._key = _key_consumer('relations._key', py_key)
        lra_adapter.default_sort_key = _key_consumer('lra_adapter', py_sort)
    # relations.relation_atom dispatches through RELATION_ATOM_IMPL at call time (planner, 9 Nov, Q1), so a name imported before
    # this install reaches the wrapper too; the module attribute is still replaced, for `__wrapped__`.
    py_disp, py_atom = relations.relation_atom, relations._relation_atom_py
    py_wise, py_links = relations._termwise, relations.Relations._eq_links
    py_glue = relations.glue_objects
    py_ext, py_num, py_affine = relations._ext_atoms, relations._is_number, scope.affine_pair
    py_linked, py_under, py_twin = scope.linked_terms, relations._under_apps, relations.zero_twin
    py_struct, py_interned, py_subterms = euf_adapter.structural, euf_adapter.EUFAdapter.interned, relations._structural_subterms
    if terms:
        relations._key = _key_match('relations._key', py_key)
        lra_adapter.default_sort_key = _key_match('lra_adapter', py_sort)
        relations.relation_atom = sympy_api.relation_atom = _relation_atom(py_atom)
        if os.environ.get('SLICE_SESSION_PLANT') != 'inst-slot-skip':   # plant 421: the slot left empty
            relations.RELATION_ATOM_IMPL[0] = relations.relation_atom
        relations._termwise = _termwise(py_wise)
        relations.Relations._eq_links = _eq_links(py_links)
        relations.glue_objects = engine.glue_objects = _glue_objects(py_glue)
        relations._ext_atoms = _ext_atoms(py_ext)
        relations._is_number = engine._is_number = scope._is_number = _is_number(py_num)
        scope.affine_pair = engine._affine_pair = _affine_pair(py_affine)
        scope.linked_terms = _linked_terms(py_linked)
        relations._under_apps = _under_apps(py_under)
        relations.zero_twin = engine.zero_twin = _zero_twin(py_twin)
        euf_adapter.structural = _structural(py_struct)
        euf_adapter.EUFAdapter.interned = _interned(py_interned)
        relations._structural_subterms = _structural_subterms(py_subterms)

    def undo():
        sympy_api._ask = py_ask
        engine.DictCache.put = _put
        relations._key, lra_adapter.default_sort_key = py_key, py_sort
        relations.relation_atom = sympy_api.relation_atom = py_disp
        relations.RELATION_ATOM_IMPL[0] = None
        relations._termwise = py_wise
        relations.Relations._eq_links = py_links
        relations.glue_objects = engine.glue_objects = py_glue
        relations._ext_atoms = py_ext
        relations._is_number = engine._is_number = scope._is_number = py_num
        scope.affine_pair = engine._affine_pair = py_affine
        scope.linked_terms = py_linked
        relations._under_apps = py_under
        relations.zero_twin = engine.zero_twin = py_twin
        euf_adapter.structural = py_struct
        euf_adapter.EUFAdapter.interned = py_interned
        relations._structural_subterms = py_subterms
    return undo


def counts():
    return dict(COUNTS)


def report():
    return {'counts': counts(), 'refusals': REFUSALS, 'scaffold_bad': SCAFFOLD_BAD, 'key_bad': KEY_BAD, 'check_bad': CHECK_BAD}


def dump(path):
    import json
    with open(path, 'w') as f:
        json.dump(report(), f)


def from_env(default='terms'):
    """SLICE_TERM: `terms` (the default), `keys`, `table` (the table, and no consumer of it here), or `py` (not installed).
    SLICE_TERM_PLANT names one of `PLANT`'s test plants."""
    import os
    mode = os.environ.get('SLICE_TERM', default)
    if mode == 'py':
        return None
    if mode not in ('terms', 'keys', 'table'):
        print(f'SLICE_TERM={mode}: not a mode', file=sys.stderr)
        raise SystemExit(2)
    PLANT[0] = os.environ.get('SLICE_TERM_PLANT') or None
    if not PLANT[0] and os.environ.get('SLICE_SESSION_PLANT') == 'int-as-number':
        PLANT[0] = 'int-as-number'      # plant 265, the bar's channel (bar.sh's plants phase)
    CHECK[0] = bool(os.environ.get('SLICE_TERM_CHECK'))
    out = os.environ.get('SLICE_TERM_COUNTS')
    if out:
        import atexit
        atexit.register(lambda: dump(out))
    return install(keys=mode == 'keys', terms=mode == 'terms')
