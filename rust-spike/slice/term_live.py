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
import sys
import threading

import sa_solver
from sympy import Add, Mul
from sympy.core.basic import Basic
from sympy.core.numbers import Rational

from satassume import engine, relations, sympy_api
from satassume.knowledge.extensions import Args
from satassume.sat.formula import Not, P
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
    __slots__ = ('table', 'ids', 'objects', 'kept', 'counts', 'raised', 'derived', 'rev')

    def __init__(self, c):
        # Derived terms this query has met: {SymPy term: id} and {id: SymPy term}. Apart from `ids`, which other consumers
        # index `objects` by.
        self.derived, self.rev = {}, {}
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
        self.derived, self.rev = {}, {}
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


# ---- Slice B: term work through ids

#: Examples of what scaffolding refused, first few.
SCAFFOLD_BAD = []
#: `(site, Python's key, Rust's key)` for a sort site that disagreed, first few.
KEY_BAD = []
#: Test plants on Rust's answers: 'swap' reverses `eq_sides`, 'termwise-true' and 'termwise-false' fix `_termwise`, 'no-strip'
#: drops `_affine_strip` where it changed a side, 'key-reverse' flips a matched key, 'scaffold-form' fails the form check.
PLANT = [None]
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
        return i if type(q.objects[i]) is type(e) else None
    if not isinstance(e, Basic):
        COUNTS[f'term:unknown:{site}:{type(e).__name__}'] += 1
        return None
    i = q.derived.get(e)
    if i is not None:
        return i if type(q.rev[i]) is type(e) else None
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
                or any(x != y or type(x) is not type(y) for x, y in zip(o.args, kids))):
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


def _ids(q, site, *terms):
    if q is None or q.kept is not None:
        COUNTS['term:no-table:' + site] += 1
        return None
    ids = [term_id(q, e, site) for e in terms]
    if None in ids:
        COUNTS['term:py:' + site] += 1
        return None
    COUNTS['term:rust:' + site] += 1
    return ids


def _relation_atom(py):
    """`relation_atom`'s eq branch on ids. The other relations do no term work and stay as they are until slice C."""
    def run(name, lhs, rhs):
        if name != 'eq' and name != 'ne':
            return None
        q = current()
        ids = _ids(q, 'relation_atom', lhs, rhs)
        if ids is None:
            return None
        l, r = ids
        a, b = q.table.eq_sides(l, r)
        if PLANT[0] == 'swap':
            a, b = b, a
        if PLANT[0] == 'no-strip' and {a, b} != {l, r}:
            a, b = l, r
        # What Python would hold: the objects it was given, when they weren't stripped.
        x = lhs if a == l else rhs if a == r else scaffold(q, a, 'relation_atom')
        y = lhs if b == l else rhs if b == r else scaffold(q, b, 'relation_atom')
        atom = P("eq", Args((x, y)))
        if CHECK[0]:
            want = py('eq', lhs, rhs)
            _check('relation_atom', want == atom and all(type(u) is type(v) for u, v in zip(want.expr, atom.expr)),
                   lhs, rhs, want, atom)
        return atom
    run = _guarded('relation_atom', run)

    def relation_atom(name, lhs, rhs):
        atom = run(name, lhs, rhs)
        if atom is None:
            return py(name, lhs, rhs)
        return atom if name == 'eq' else Not(atom)
    relation_atom.__wrapped__ = py
    return relation_atom


def _termwise(py):
    """`_termwise` on ids. `d` was built by Python here (`glue_objects`, until slice C), and has to be what Rust builds."""
    def run(a, b, d):
        q = current()
        ids = _ids(q, '_termwise', a, b, d)
        if ids is None:
            return None
        i, j, k = ids
        if q.table.sub(i, j) != k:
            COUNTS['term:sub-differs'] += 1
            _refuse("termwise: Python's difference isn't Rust's")
        if PLANT[0] == 'termwise-true':
            return True
        if PLANT[0] == 'termwise-false':
            return False
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


def _eq_links(py):
    """`Relations._eq_links`, with its number tests and difference answered by Rust. The clauses are Python's, line for line,
    until slice C: they go through `session.var`, which holds SymPy objects, so a difference used here is scaffolding."""
    term = _guarded('_eq_links', lambda q, a, b: _ids(q, '_eq_links', a, b))
    numbers = _guarded('_eq_links', lambda q, i, j: q.table.is_number_term(i) or q.table.is_number_term(j))

    def diff(q, i, j, p, m):
        d = q.table.eq_diff(i, j)
        if PLANT[0] == 'termwise-false':
            return None
        o = None if d is None else scaffold(q, d, '_eq_links')
        if CHECK[0]:
            real = p - m
            want = None if relations._is_number(real) or not relations._termwise.__wrapped__(p, m, real) else real
            _check('_eq_links', want == o and type(want) is type(o), p, m, want, o)
        return o
    diff = _guarded('_eq_links', diff)

    def eq_links(self, var, atom):
        a, b = atom.expr
        q = current()
        ids = term(q, a, b)
        if ids is None:
            return py(self, var, atom)
        i, j = ids
        if numbers(q, i, j):
            return
        s = self.session
        g = -self._atom_selector(atom)

        def emit(clause):
            s.emit(clause + [g])
        s.ensure(a, {"positive_infinite", "negative_infinite"})
        s.ensure(b, {"positive_infinite", "negative_infinite"})
        for pred in ("positive_infinite", "negative_infinite"):
            emit([-s.var(pred, a), -s.var(pred, b), var])
        for u, v, p, m in ((i, j, a, b), (j, i, b, a)):
            d = diff(q, u, v, p, m)
            if d is None:
                continue
            s.ensure(d, {"zero", "nonzero"})
            emit([-s.var("zero", d), var])
            emit([-s.var("nonzero", d), -var])
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
    engine.DictCache.put = _journaled_put
    py_key, py_sort = relations._key, lra_adapter.default_sort_key
    if keys:
        relations._key = _key_consumer('relations._key', py_key)
        lra_adapter.default_sort_key = _key_consumer('lra_adapter', py_sort)
    py_atom, py_wise, py_links = relations.relation_atom, relations._termwise, relations.Relations._eq_links
    if terms:
        relations._key = _key_match('relations._key', py_key)
        lra_adapter.default_sort_key = _key_match('lra_adapter', py_sort)
        relations.relation_atom = sympy_api.relation_atom = _relation_atom(py_atom)
        relations._termwise = _termwise(py_wise)
        relations.Relations._eq_links = _eq_links(py_links)

    def undo():
        sympy_api._ask = py_ask
        engine.DictCache.put = _put
        relations._key, lra_adapter.default_sort_key = py_key, py_sort
        relations.relation_atom = sympy_api.relation_atom = py_atom
        relations._termwise = py_wise
        relations.Relations._eq_links = py_links
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
    CHECK[0] = bool(os.environ.get('SLICE_TERM_CHECK'))
    out = os.environ.get('SLICE_TERM_COUNTS')
    if out:
        import atexit
        atexit.register(lambda: dump(out))
    return install(keys=mode == 'keys', terms=mode == 'terms')
