"""`lra_adapter.py`'s term work from Rust (component 4, slice D, issue 323), installed from outside satassume.

On a query with a table, `interpret`, `order_sides`, `integer_form` and `closed_sign` answer from `term/lra_read.rs`, which
also holds `_from_sympy`. `relation` stays here: it reads predicate heads, so it's conversion. A kept query, a refused run's
second go, and a direct `Engine` call have no table to read and run Python's functions, counted.

A term with no row stays on Python for that one call, counted. An `Add` or `Mul` Python built of terms with rows gets a row with
its args as they are. A derived term coming back from Rust is rebuilt in SymPy as scaffolding, counted, and checked against
Rust's form, so a mismatch refuses.

`_INTERPRETED`: a call with ids doesn't read it. Each table holds its own memo, so results don't outlive the query. Calls with
no table keep Python's own path, memo included.

The registry stays Python's for now. Rust asks for `PI`, `E`, `radical` and `_generic` live, so there's one registry with its
history, and each ask is counted by `sa_solver.lra_counts()`.
"""
import os
import sys

import sa_solver

from sympy.core.add import Add
from sympy.core.basic import Basic
from sympy.core.mul import Mul
from sympy.core.numbers import Rational

from satassume.theories.lra import constfield, lra, lra_adapter

import term_live

COUNTS = term_live.COUNTS
#: SLICE_LRA_CHECK: also run Python's function and compare. It builds in SymPy, so it's for evidence, never for a quoted number.
CHECK = [False]
CHECK_BAD = []
SCAFFOLD_BAD = []
PLANTS = {'coeff': 1, 'sort': 2, 'pi': 3, 'eq': 4}


def _refuse(reason):
    raise sa_solver.TermRefuse(reason)


def _term_id(q, e, site):
    i = q.ids.get(e) if isinstance(e, Basic) else None
    if i is not None:
        # `==` can join classes (Float against Integer), so a row counts only for its own class.
        return i if type(q.objects[i]) is type(e) else None
    if not isinstance(e, Basic):
        COUNTS[f'lra:unknown:{site}:{type(e).__name__}'] += 1
        return None
    i = q.derived.get(e)
    if i is not None:
        return i if type(q.rev[i]) is type(e) else None
    cls = type(e)
    if isinstance(e, Rational):
        i = q.table.number(e.p, e.q)
    elif (cls is Add or cls is Mul) and e.is_commutative is True:
        args = [_term_id(q, a, site) for a in e.args]
        if None in args:
            return None
        i = q.table.raw_add(args) if cls is Add else q.table.raw_mul(args)
        COUNTS['lra:learned'] += 1
    else:
        COUNTS[f'lra:unknown:{site}:{cls.__name__}'] += 1
        return None
    if i >= q.table.n_input:
        q.derived[e] = i
        q.rev.setdefault(i, e)
    return i


def _bad(o, why):
    COUNTS['scaffold:mismatch'] += 1
    if len(SCAFFOLD_BAD) < 20:
        SCAFFOLD_BAD.append((why, repr(o)[:200]))
    _refuse('scaffold: ' + why)


def _scaffold(q, i, site):
    """The SymPy object of id `i`. Scaffolding: temporary, counted, and checked against Rust's form."""
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
            _bad(row[1], 'a derived term with no args that is not a number')
        o = Rational(row[1][0], row[1][1])
        if (o.p, o.q) != row[1] or type(o).__name__ != name:
            _bad(o, 'number')
    else:
        f = {'Add': Add, 'Mul': Mul}.get(name)
        if f is None:
            _bad(name, 'a derived class other than Add and Mul')
        kids = [_scaffold(q, a, site) for a in args]
        o = f(*kids)
        # Rust's form: the same class, and the same args in the same order, each of its own class.
        if (type(o).__name__ != name or len(o.args) != len(kids)
                or any(x != y or type(x) is not type(y) for x, y in zip(o.args, kids))):
            _bad(o, 'rebuilt form differs from Rust')
    COUNTS['scaffold:rebuilt'] += 1
    COUNTS['scaffold:rebuilt:' + site] += 1
    k = q.ids.get(o)
    if k is None:
        k = q.derived.get(o)
    if k is not None and k != i:
        _bad(o, 'rebuilt term has another id')
    q.derived[o] = i
    q.rev[i] = o
    return o


def _query():
    """The current query, if it has a table to read."""
    q = term_live.current()
    return None if q is None or q.kept is not None else q


def _rust(site, f, *a):
    """An ordinary exception here can't turn quiet in a handler on the engine's path."""
    try:
        return f(*a)
    except Exception as x:
        COUNTS['fault'] += 1
        raise term_live.TermFault(f'lra {site}: {type(x).__name__}: {x}') from x


def _same_num(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is constfield.Element:
        return a._n == b._n and a._d == b._d
    return a == b


def _same(a, b):
    """Same value at the same position: terms by == and class, numbers by type and representation."""
    if isinstance(a, dict) or isinstance(b, dict):
        return (type(a) is type(b) and len(a) == len(b)
                and all(_same(x, y) for x, y in zip(a.items(), b.items())))
    if isinstance(a, (tuple, list)):
        return (isinstance(b, (tuple, list)) and type(a) is type(b) and len(a) == len(b)
                and all(_same(x, y) for x, y in zip(a, b)))
    if isinstance(a, Basic):
        return type(a) is type(b) and a == b
    return _same_num(a, b)


def _check(site, ours, theirs, arg):
    same = _same(ours, theirs())
    COUNTS[('lra:check:same:' if same else 'lra:check:differs:') + site] += 1
    if not same and len(CHECK_BAD) < 50:
        CHECK_BAD.append((site, repr(arg)[:200], repr(ours)[:300]))


def _objs(q, ids, site):
    return [_scaffold(q, i, site) for i in ids]


def _pairs(q, items, site):
    return tuple((_scaffold(q, i, site), c) for i, c in items)


def _ids(q, site, *terms):
    out = []
    for e in terms:
        i = _term_id(q, e, site)
        if i is None:
            return None
        out.append(i)
    return out


def _flag():
    return lra_adapter.GENERIC_CONSTANTS


def _install():
    py_interpret = lra_adapter.interpret
    py_order_sides = lra_adapter.order_sides
    py_integer_form = lra_adapter.integer_form
    py_closed_sign = lra_adapter.closed_sign
    py_memoized = lra_adapter._memoized

    def on_python(site, q, py_f, *a):
        COUNTS[f'lra:{site}:' + ('no-query' if term_live.current() is None else 'kept' if q is None else 'no-id')] += 1
        return py_f(*a)

    def interpret(atom):
        rel = lra_adapter.relation(atom)
        if rel is None:
            return None
        q = _query()
        i = None if q is None else _ids(q, 'interpret', rel[1], rel[2])
        if i is None:
            return on_python('interpret', q, py_interpret, atom)
        COUNTS['lra:interpret:rust'] += 1
        r = _rust('interpret', q.table.lra_interpret, rel[0], i[0], i[1], _flag(), q.objects)
        if r is None:
            out = None
        else:
            c, terms = r
            if c is not True and c is not False:
                items, rhs, strict, equality, positive = c
                c = (_pairs(q, items, 'interpret'), rhs, strict, equality), positive
            out = c, _objs(q, terms, 'interpret')
        if CHECK[0]:
            _check('interpret', out, lambda: py_interpret(atom), atom)
        return out

    def order_sides(atom):
        rel = lra_adapter.relation(atom)
        if rel is None or rel[0] != 'lt':
            return None
        q = _query()
        i = None if q is None else _ids(q, 'order_sides', rel[1], rel[2])
        if i is None:
            return on_python('order_sides', q, py_order_sides, atom)
        COUNTS['lra:order_sides:rust'] += 1
        r = _rust('order_sides', q.table.lra_order_sides, i[0], i[1], _flag(), q.objects)
        if r is None:
            out = None
        else:
            out = tuple((dict(_pairs(q, items, 'order_sides')), inf) for items, inf in r)
        if CHECK[0]:
            _check('order_sides', out, lambda: py_order_sides(atom), atom)
        return out

    def integer_form(e):
        q = _query()
        i = None if q is None else _ids(q, 'integer_form', e)
        if i is None:
            return on_python('integer_form', q, py_integer_form, e)
        COUNTS['lra:integer_form:rust'] += 1
        r = _rust('integer_form', q.table.lra_integer_form, i[0], _flag(), q.objects)
        if r is None:
            out = None
        else:
            items, c, keys = r
            out = lra.Integral(_pairs(q, items, 'integer_form'), c), _objs(q, keys, 'integer_form')
        if CHECK[0]:
            _check('integer_form', out, lambda: py_integer_form(e), e)
        return out

    def closed_sign(e):
        q = _query()
        i = None if q is None else _ids(q, 'closed_sign', e)
        if i is None:
            return on_python('closed_sign', q, py_closed_sign, e)
        COUNTS['lra:closed_sign:rust'] += 1
        out = _rust('closed_sign', q.table.lra_closed_sign, i[0], _flag(), q.objects)
        if CHECK[0]:
            _check('closed_sign', out, lambda: py_closed_sign(e), e)
        return out

    def memoized(key, read, arg):
        # A query with a table memoizes per table, inside these functions. Python's memo serves everything else.
        if _query() is None:
            return py_memoized(key, read, arg)
        return read(arg)

    saved = (lra_adapter.interpret, lra_adapter.order_sides, lra_adapter.integer_form, lra_adapter.closed_sign,
             lra_adapter._memoized)
    lra_adapter.interpret, lra_adapter.order_sides, lra_adapter.integer_form = interpret, order_sides, integer_form
    lra_adapter.closed_sign = closed_sign
    lra_adapter._memoized = memoized

    def undo():
        (lra_adapter.interpret, lra_adapter.order_sides, lra_adapter.integer_form, lra_adapter.closed_sign,
         lra_adapter._memoized) = saved
    return undo


_undo = [None]
_installs = [0]


def install(check=None, plant=None):
    """Returns a function that undoes this call. Calls nest, and it installs term_live's table too. `check` and `plant` default
    to SLICE_LRA_CHECK and SLICE_LRA_PLANT."""
    _installs[0] += 1
    undo_table = term_live.install() if not term_live.installed() else (lambda: None)
    if _installs[0] == 1:
        CHECK[0] = bool(os.environ.get('SLICE_LRA_CHECK')) if check is None else check
        p = os.environ.get('SLICE_LRA_PLANT') if plant is None else plant
        sa_solver.lra_plant(PLANTS[p] if p else 0)
        _undo[0] = _install()

    def undo():
        _installs[0] -= 1
        if _installs[0] == 0:
            _undo[0]()
            _undo[0] = None
            sa_solver.lra_plant(0)
            CHECK[0] = False
        undo_table()
    return undo


def from_env():
    """SLICE_LRA: `rust` (the default) or `py` (not installed)."""
    mode = os.environ.get('SLICE_LRA', 'rust')
    if mode == 'py':
        return None
    if mode != 'rust':
        print(f'SLICE_LRA={mode}: not a mode', file=sys.stderr)
        raise SystemExit(2)
    return install()


def counts():
    out = {k: v for k, v in COUNTS.items() if k.startswith(('lra:', 'scaffold:'))}
    out.update({'rust:' + k: v for k, v in sa_solver.lra_counts().items()})
    return out
