"""Shadow for component 0: under the real engine, on each top-level query, Rust's converted table is checked against
SymPy. Monkeypatch only, no satassume source changes. It decides nothing: no module counts as ported because of it.

Each row of Rust's table is read back and compared with what SymPy says now. Any difference is a mismatch and goes to
`bad` with the smallest text of its term; nothing is reclassified. A shadow error never reaches the query.

    term_shadow.install(); ...; term_shadow.report(path)
"""
import json
import struct
import sys
from collections import Counter

from sympy.core.basic import Basic, ordering_of_classes
from sympy.core.exprtools import decompose_power
from sympy.core.function import AppliedUndef
from sympy.core.numbers import Float, Rational
from sympy.core.sorting import default_sort_key
from sympy import S, Add, Mul, Expr, sympify

import sa_solver

from satassume import sympy_api
from satassume import relations as R
from satassume.sat import formula as F
from satassume.knowledge.extensions import Args
from satassume.knowledge.domain import constructed_noncommutative
from satassume.knowledge.templates import _may_be_nan
from satassume.theories.euf.euf_adapter import structural
from satassume.theories.lra import lra_adapter as L
from satassume import engine as E

import convert as C

COUNTS = Counter()          # checks and outcomes
KEPT = Counter()            # queries kept on Python, by reason
REFUSED = Counter()         # Rust's refusals in the checks, by reason
BAD = []                    # mismatches, first 200
SAMPLE = 40                 # pairs among the first SAMPLE terms of each query
CUR = [None]                # (Converted, TermTable) of the running top-level query
DEPTH = [0]
CHECK_ON = [True]
SITES = Counter()           # (op, caller file:line, outcome): which sites reach the algebra
EXAMPLES = {}               # refusal reason: first few (op, operands)
SAMPLE_DERIVED = 9          # a new derived term is compared against this many of the query's first terms


def bad(kind, *detail):
    COUNTS['mismatch'] += 1
    COUNTS['mismatch:' + kind] += 1
    if len(BAD) < 200:
        BAD.append((kind,) + tuple(str(d)[:200] for d in detail))


def same_value(rv, real, c, key):
    """Rust's value against SymPy's."""
    if isinstance(real, tuple):
        return (isinstance(rv, tuple) and len(rv) == len(real) and not (rv and rv[0] in ('T', 'Q', 'O') and _tagged(rv))
                and all(same_value(a, b, c, key) for a, b in zip(rv, real)))
    if isinstance(real, Basic):
        if key and isinstance(real, Rational):
            return isinstance(rv, tuple) and rv == ('Q', real.p, real.q)
        return isinstance(rv, tuple) and rv == ('T', c.ids.get(real))
    if real is None or real is True or real is False:
        return rv is real
    if isinstance(real, str):
        return type(rv) is str and rv == real
    try:
        i = int(real)
    except Exception:
        return isinstance(rv, tuple) and len(rv) == 2 and rv[0] == 'O'
    return type(rv) is int and rv == i and i == real


def _tagged(rv):
    return (rv[0] == 'T' and len(rv) == 2) or (rv[0] == 'Q' and len(rv) == 3) or (rv[0] == 'O' and len(rv) == 2)


def check_table(c, table):
    """Every row, read back from Rust, against SymPy."""
    objs, ids = c.objects, c.ids
    if len(table) != len(objs):
        bad('table-size', len(table), len(objs))
        return
    for i, t in enumerate(objs):
        COUNTS['terms'] += 1
        cls = type(t)
        name, kind, rank, flags, ckey, templates, struct_bit = table.class_row(i)
        if name != cls.__name__:
            bad('class-name', i, t, name)
        if ids[t] != i:
            bad('id', i, t)
        try:
            real_rank = ordering_of_classes.index(cls.__name__)
        except ValueError:
            real_rank = None
        if rank != real_rank:
            bad('rank', t, rank)
        if ckey != cls.class_key():
            bad('class-key', t, ckey)
        if (struct_bit and bool(t.args)) != structural(t):
            bad('structural', t, struct_bit)
        args, content, key, free, bits, level, closed, power = table.row(i)
        if args != [ids[a] for a in t.args]:
            bad('args', t, args)
        real_content = t._hashable_content()
        if not same_value(content, tuple(real_content), c, False):
            bad('content', t, content)
        if table.find(i) != i:
            bad('hash-cons', t, table.find(i))
        if not bits & C.F_READ:
            COUNTS['skeleton'] += 1
            continue
        try:
            real_key = default_sort_key(t)
        except Exception as e:
            COUNTS['key-raises:' + type(e).__name__] += 1
            if key is not None:
                bad('key-supplied-where-python-raises', t)
        else:
            if not same_value(key, real_key, c, True):
                bad('key', t, key)
        if sorted(free) != sorted(ids[x] for x in t.free_symbols):
            bad('free', t, free)
        want = C.F_READ
        number = getattr(t, 'is_number', False) is True
        for bit, v in ((C.F_NUMBER, number), (C.F_NAN, t.has(S.NaN)), (C.F_BAD, t.has(*L._BAD)), (C.F_FLOAT, t.has(Float)),
                       (C.F_UNDEF, t.atoms(AppliedUndef)), (C.F_MAYBE_NAN, _may_be_nan(t)),
                       (C.F_COMMUTATIVE, t.is_commutative is True)):
            if v:
                want |= bit
        if bits != want:
            bad('facts', t, bits, want)
        if level != constructed_noncommutative(t):
            bad('level', t, level)
        if closed is not None:
            finite, z = closed
            if finite is not t.is_finite:
                bad('is_finite', t, finite)
            try:
                real_z = complex(t)
            except Exception:
                real_z = None
            if real_z is None:
                if z is not None:
                    bad('complex', t, z)
            elif z is None or _bits(z[0]) != _bits(real_z.real) or _bits(z[1]) != _bits(real_z.imag):
                bad('complex', t, z, real_z)
        if power is not None:
            COUNTS['powers'] += 1
            base, e = decompose_power(t)
            b = ids.get(base)
            if power[0] != b or power[1] != e:
                bad('power', t, power, (base, e))
            if power[0] is None:
                COUNTS['power-base-not-input'] += 1


def _bits(x):
    return struct.pack('<d', x)


def check_order(c, table):
    """`Basic.compare` and the key order, Rust's against SymPy's, over pairs of the query's first terms."""
    objs = c.objects[:SAMPLE]
    for i, a in enumerate(objs):
        for j, b in enumerate(objs):
            if i == j:
                continue
            COUNTS['compare'] += 1
            try:
                real = a.compare(b)
            except Exception as e:
                real = type(e).__name__
            try:
                got = table.compare(i, j)
            except sa_solver.TermRefuse as e:
                REFUSED[f'compare: {e} / python: {real if isinstance(real, str) else "ordered"}'] += 1
                if not isinstance(real, str) and len(BAD) < 200:
                    BAD.append(('refused-compare', str(a)[:100], str(b)[:100]))
            else:
                if got != real:
                    bad('compare', a, b, got, real)
            if table.row(i)[2] is None or table.row(j)[2] is None:
                COUNTS['key-compare-no-key'] += 1
                continue
            try:
                ka, kb = default_sort_key(a), default_sort_key(b)
                real = -1 if ka < kb else 1 if kb < ka else 0
            except Exception as e:
                real = type(e).__name__
            COUNTS['key-compare'] += 1
            try:
                got = table.key_cmp(i, j)
            except sa_solver.TermRefuse as e:
                REFUSED[f'key: {e} / python: {real}'] += 1
            else:
                if got != real:
                    bad('key-compare', a, b, got, real)


def rebuild(v, objs):
    """The real formula from Rust's dump, with the real constructors and relation_atom."""
    tag = v[0]
    if tag == 'true':
        return F.TRUE
    if tag == 'false':
        return F.FALSE
    if tag == 'atom':
        args = [objs[a[1]] for a in v[2:]]
        return F.P(v[1], args[0] if len(args) == 1 else Args(args))
    if tag == 'rel':
        return R.relation_atom(v[1], objs[v[2][1]], objs[v[3][1]])
    if tag == 'opaque':
        return F.P(sympy_api.OPAQUE, objs[v[1][1]])
    kids = [rebuild(x, objs) for x in v[1:]]
    if tag == 'xor':
        f = kids[0]
        for a in kids[1:]:
            f = F.Not(F.Equivalent(f, a))
        return f
    return {'and': F.And, 'or': F.Or, 'not': F.Not, 'implies': F.Implies, 'equivalent': F.Equivalent, 'ite': F.ITE}[tag](*kids)


# ---- the algebra: Rust's derived terms against what SymPy builds

def _here(frame):
    return f"{frame.f_globals.get('__name__', '?')}:{frame.f_lineno}"


def operand_id(x, c, table):
    """Rust's id of an operand, or None if it's a term Rust was never told about."""
    if not isinstance(x, Basic):
        try:
            x = sympify(x)
        except Exception:
            return None
    i = c.ids.get(x)
    if i is None and isinstance(x, Rational):
        i = table.number(x.p, x.q)
        settle('number', x, i, c, table)
    return i


def same_term(real, i, c, table):
    """Class and args, recursively, arg order included."""
    name = table.class_row(i)[0]
    if name != type(real).__name__:
        return False
    args = table.row(i)[0]
    if len(args) != len(real.args):
        return False
    if not args:
        if isinstance(real, Rational):
            return table.row(i)[1] == (real.p, real.q)
        return c.ids.get(real) == i
    return all(same_term(a, k, c, table) for a, k in zip(real.args, args))


def show(i, c, table):
    args = table.row(i)[0]
    if not args:
        return str(table.row(i)[1]) if i >= table.n_input else str(c.objects[i])
    return f"{table.class_row(i)[0]}({', '.join(show(a, c, table) for a in args)})"


def settle(site, real, i, c, table):
    """Rust built `i` where SymPy built `real`: same form, and they must merge exactly as SymPy's hash and == do."""
    rev = c.__dict__.setdefault('rev', {})
    k = c.ids.get(real)
    if k is not None:
        COUNTS['alg:same-as-known'] += 1
        if i < table.n_input:
            COUNTS['alg:merged-with-input'] += 1
        if k != i:
            bad('merge', site, real, show(i, c, table))
        return
    if not same_term(real, i, c, table):
        bad('derived-form', site, real, show(i, c, table))
        return
    if i in rev or i < len(c.objects):
        bad('two-terms-one-id', site, real, show(i, c, table))
        return
    c.ids[real] = i
    rev[i] = real
    COUNTS['alg:derived-terms'] += 1
    check_derived(site, real, i, c, table)


def check_derived(site, real, i, c, table):
    """The new row's key, facts and order against SymPy's."""
    try:
        real_key = default_sort_key(real)
    except Exception as e:
        real_key = e
    COUNTS['alg:derived-keys'] += 1
    try:
        got = table.sort_key(i)
    except sa_solver.TermRefuse as e:
        COUNTS['alg:key-refused'] += 1
        REFUSED[f'derived key: {e}'] += 1
        _example(f'derived key: {e}', 'key', real)
    else:
        if isinstance(real_key, Exception) or not same_value(got, real_key, c, True):
            bad('derived-key', site, real, got, real_key)
    row = table.row(i)
    if sorted(row[3]) != sorted(c.ids[x] for x in real.free_symbols if x in c.ids) or any(x not in c.ids for x in real.free_symbols):
        bad('derived-free', site, real, row[3])
    number = getattr(real, 'is_number', False) is True
    if bool(row[4] & C.F_NUMBER) != number:
        bad('derived-number', site, real, row[4])
    for j, o in enumerate(c.objects[:SAMPLE_DERIVED]):
        COUNTS['alg:derived-compare'] += 1
        want = real.compare(o)
        try:
            have = table.compare(i, j)
        except sa_solver.TermRefuse as e:
            REFUSED[f'derived compare: {e}'] += 1
        else:
            if have != want:
                bad('derived-compare', real, o, have, want)


def _example(reason, op, *operands):
    ex = EXAMPLES.setdefault(reason, [])
    if len(ex) < 5:
        ex.append((op,) + tuple(str(o)[:120] for o in operands))


def check_op(op, site, operands, real, ask_rust):
    """One operation a satassume frame asked SymPy for. `real` is a term, or a tuple of them for the coefficient splits."""
    cur = CUR[0]
    if cur is None or not CHECK_ON[0]:
        return
    c, table = cur
    COUNTS['alg:ops'] += 1
    COUNTS['alg:op:' + op] += 1
    ids = [operand_id(x, c, table) for x in operands]
    if any(i is None for i in ids):
        COUNTS['alg:unknown-operand'] += 1
        SITES[f'{op} {site} unknown-operand'] += 1
        unknown = next(x for x, i in zip(operands, ids) if i is None)
        _example(f'unknown operand at {op}', op, unknown, type(unknown).__name__)
        return
    try:
        got = ask_rust(table, *ids)
    except sa_solver.TermRefuse as e:
        COUNTS['alg:refused'] += 1
        REFUSED[f'{op}: {e}'] += 1
        SITES[f'{op} {site} refused'] += 1
        _example(f'{op}: {e}', op, *operands)
        c.__dict__.setdefault('refused_at', str(e))
        return
    SITES[f'{op} {site} checked'] += 1
    if isinstance(real, tuple):
        for r, g in zip(real, got):
            settle(op, r, g, c, table)
    else:
        settle(op, real, got, c, table)


def _div(t, a, b):
    r = t.row(b)[1]
    if not (isinstance(r, tuple) and len(r) == 2 and all(type(x) is int for x in r) and r[0] != 0):
        raise sa_solver.TermRefuse('div: a denominator that is not a nonzero rational')
    return t.mul([a, t.number(r[1], r[0])])


_OPS = {
    '__neg__': lambda t, a: t.neg(a),
    '__add__': lambda t, a, b: t.add([a, b]),
    '__radd__': lambda t, a, b: t.add([b, a]),
    '__sub__': lambda t, a, b: t.sub(a, b),
    '__rsub__': lambda t, a, b: t.sub(b, a),
    '__mul__': lambda t, a, b: t.mul([a, b]),
    '__rmul__': lambda t, a, b: t.mul([b, a]),
    '__truediv__': _div,
    'as_coeff_Add': lambda t, a: t.coeff_add(a),
    'as_coeff_Mul': lambda t, a: t.coeff_mul(a),
}


def _wrap_op(cls, name, f, static):
    rust = _OPS[name]
    nargs = 1 if name in ('__neg__', 'as_coeff_Add', 'as_coeff_Mul') else 2

    def wrapper(self, *a, **k):
        real = f() if static else f(self, *a, **k)
        fr = sys._getframe(1)
        if CUR[0] is not None and fr.f_globals.get('__name__', '').startswith('satassume'):
            if real is NotImplemented:
                return real
            operands = (self,) + a[:nargs - 1]
            try:
                check_op(name, _here(fr), operands, real, rust)
            except Exception as e:
                bad('check-raised', name, type(e).__name__, e)
        return real
    wrapper.__wrapped__ = f
    wrapper.__name__ = name
    setattr(cls, name, wrapper)


def _wrap_new(cls, name):
    f = cls.__dict__['__new__']
    f = f.__func__ if isinstance(f, staticmethod) else f
    raw = {'Add': lambda t, *x: t.raw_add(list(x)), 'Mul': lambda t, *x: t.raw_mul(list(x))}[name]
    ev = {'Add': lambda t, *x: t.add(list(x)), 'Mul': lambda t, *x: t.mul(list(x))}[name]

    def new(klass, *args, **k):
        real = f(klass, *args, **k)
        fr = sys._getframe(1)
        if CUR[0] is not None and klass is cls and fr.f_globals.get('__name__', '').startswith('satassume'):
            evaluate = k.get('evaluate')
            try:
                check_op(f'{name}.__new__' + ('' if evaluate is None else f'(evaluate={evaluate})'), _here(fr), args, real,
                         raw if evaluate is False else ev)
            except Exception as e:
                bad('check-raised', name, type(e).__name__, e)
        return real
    cls.__new__ = staticmethod(new)


def install_algebra():
    seen, stack = set(), [Expr]
    while stack:
        k = stack.pop()
        if k in seen:
            continue
        seen.add(k)
        stack.extend(k.__subclasses__())
    for k in sorted(seen, key=lambda k: (k.__module__, k.__qualname__)):
        for name in _OPS:
            f = k.__dict__.get(name)
            if f is None:
                continue
            if isinstance(f, staticmethod):
                _wrap_op(k, name, f.__func__, True)
            elif callable(f):
                _wrap_op(k, name, f, False)
    _wrap_new(Add, 'Add')
    _wrap_new(Mul, 'Mul')

    real_node = E.Session.node

    def node(self, n, demanded=None):
        cur = CUR[0]
        if cur is not None and CHECK_ON[0] and n not in self.base:
            c, table = cur
            if isinstance(n, Basic):
                COUNTS['node:new'] += 1
                i = c.ids.get(n)
                if i is None:
                    COUNTS['node:unknown'] += 1
                    fr = sys._getframe(1)
                    SITES[f'node {_here(fr)} unknown'] += 1
                    _example('node unknown', 'node', n, type(n).__name__)
                elif i >= table.n_input:
                    COUNTS['node:derived'] += 1
        return real_node(self, n, demanded)
    E.Session.node = node

    real_struct = E.Engine._struct
    real_cone = E.Engine._cone_info

    def cone_id(o, c):
        if isinstance(o, Basic):
            i = c.ids.get(o)
            return None if i is None else ('T', i)
        pred, arg = getattr(o, 'pred', None), getattr(o, 'arg', None)
        parts = arg if isinstance(arg, Args) else (arg,)
        ids = []
        for a in parts:
            i = c.ids.get(a) if isinstance(a, Basic) else None
            if i is None:
                return None
            ids.append(i)
        return ('P', str(pred), tuple(ids))

    def struct_(self, o):
        r = real_struct(self, o)
        cur = CUR[0]
        if cur is not None and CHECK_ON[0]:
            c, _ = cur
            COUNTS['struct:calls'] += 1
            ci = cone_id(o, c)
            if ci is None:
                COUNTS['struct:unknown-object'] += 1
                _example('struct unknown object', 'struct', o, type(o).__name__)
            else:
                w = c.__dict__.setdefault('weights', {})
                if w.setdefault(ci, r[1]) != r[1]:
                    bad('struct-weight', o, w[ci], r[1])
        return r
    E.Engine._struct = struct_

    def cone(self, d):
        r = real_cone(self, d)
        cur = CUR[0]
        if cur is not None and CHECK_ON[0]:
            c, _ = cur
            cn, w, _rel = r
            COUNTS['cone:calls'] += 1
            if cn is None:
                COUNTS['cone:over-budget'] += 1
            else:
                cids = [cone_id(o, c) for o in cn]
                unknown = sum(x is None for x in cids)
                COUNTS['cone:objects'] += len(cids)
                COUNTS['cone:unknown-objects'] += unknown
                COUNTS['cone:weight'] += w
                if not unknown:
                    COUNTS['cone:fully-known'] += 1
                    if len(set(cids)) != len(cn):
                        bad('cone-merge', d, len(set(cids)), len(cn))
                    total = sum(real_struct(self, o)[1] for o in cn)
                    if total != w:
                        bad('cone-weight', d, total, w)
        return r
    E.Engine._cone_info = cone


def _outcome(f, *a):
    try:
        return f(*a)
    except Exception as e:
        return type(e).__name__


def check_formula(c, table, proposition, assumptions, eng):
    """Runs relation_atom, which builds terms: the keys it asks for here are the shadow's, since CUR isn't set yet."""
    rel = bool(eng.relation_specs)
    fp, fa = table.formula()
    COUNTS['formula'] += 1
    if _outcome(rebuild, fp, c.objects) != _outcome(sympy_api.to_formula, proposition, rel):
        bad('formula', proposition)
    if fa is not None and _outcome(rebuild, fa, c.objects) != _outcome(sympy_api.to_formula, assumptions, rel, True):
        bad('formula-assumptions', assumptions)


def top_level(proposition, assumptions, eng):
    """One query: convert, build Rust's table, check it. Anything it raises is counted and goes no further."""
    COUNTS['queries'] += 1
    try:
        c = C.convert(proposition, assumptions, eng)
    except Exception as e:
        COUNTS['convert-raised'] += 1
        bad('convert-raised', type(e).__name__, e, proposition, assumptions)
        return None
    if isinstance(c, C.Kept):
        KEPT[c.reason] += 1
        return None
    COUNTS['converted'] += 1
    for k, v in c.counts.items():
        COUNTS['convert:' + k] += v
    try:
        table = sa_solver.TermTable(c.tables)
    except Exception as e:
        bad('table-raised', type(e).__name__, e, proposition)
        return None
    if CHECK_ON[0]:
        try:
            check_table(c, table)
            check_order(c, table)
            check_formula(c, table, proposition, assumptions, eng)
        except Exception as e:
            bad('check-raised', type(e).__name__, e, proposition)
    return c, table


def install():
    real_ask = sympy_api._ask

    def _ask(proposition, assumptions, eng):
        DEPTH[0] += 1
        try:
            if DEPTH[0] == 1:
                CUR[0] = top_level(proposition, assumptions, eng)
            return real_ask(proposition, assumptions, eng)
        finally:
            DEPTH[0] -= 1
            if DEPTH[0] == 0:
                CUR[0] = None

    sympy_api._ask = _ask

    # Keys the query itself asks for, as Rust would have to answer them: ruling 6's "used".
    def counted(site, real):
        def key(e, *a, **k):
            r = real(e, *a, **k)
            cur = CUR[0]
            if cur is not None:
                COUNTS['keys-used'] += 1
                COUNTS['keys-used:' + site] += 1
                c, table = cur
                i = c.ids.get(e)
                if i is None:
                    COUNTS['keys-used-unknown'] += 1
                    _example('key of an unknown term', site, e)
                else:
                    if i >= table.n_input:
                        COUNTS['keys-used-derived'] += 1
                    if CHECK_ON[0]:
                        try:
                            got = table.sort_key(i)
                        except sa_solver.TermRefuse as x:
                            REFUSED[f'key used: {x}'] += 1
                            _example(f'key used: {x}', site, e)
                        else:
                            if not same_value(got, r, c, True):
                                bad('key-used', e, site)
            return r
        return key

    R._key = counted('relations._key', R._key)
    L.default_sort_key = counted('lra_adapter', L.default_sort_key)


def report(path):
    with open(path, 'w') as f:
        json.dump(dict(counts=COUNTS, kept=KEPT, refused=REFUSED, bad=BAD, sites=SITES, examples=EXAMPLES), f, indent=0, sort_keys=True)
