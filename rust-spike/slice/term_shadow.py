"""Shadow for component 0: under the real engine, on each top-level query, Rust's converted table is checked against
SymPy. Monkeypatch only, no satassume source changes. It decides nothing: no module counts as ported because of it.

Each row of Rust's table is read back and compared with what SymPy says now. Any difference is a mismatch and goes to
`bad` with the smallest text of its term; nothing is reclassified. A shadow error never reaches the query.

    term_shadow.install(); ...; term_shadow.report(path)
"""
import json
import struct
from collections import Counter

from sympy.core.basic import Basic, ordering_of_classes
from sympy.core.exprtools import decompose_power
from sympy.core.function import AppliedUndef
from sympy.core.numbers import Float, Rational
from sympy.core.sorting import default_sort_key
from sympy import S

import sa_solver

from satassume import sympy_api
from satassume import relations as R
from satassume.sat import formula as F
from satassume.knowledge.extensions import Args
from satassume.knowledge.domain import constructed_noncommutative
from satassume.knowledge.templates import _may_be_nan
from satassume.theories.euf.euf_adapter import structural
from satassume.theories.lra import lra_adapter as L

import convert as C

COUNTS = Counter()          # checks and outcomes
KEPT = Counter()            # queries kept on Python, by reason
REFUSED = Counter()         # Rust's refusals in the checks, by reason
BAD = []                    # mismatches, first 200
SAMPLE = 40                 # pairs among the first SAMPLE terms of each query
CUR = [None]                # (Converted, TermTable) of the running top-level query
DEPTH = [0]
CHECK_ON = [True]


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
                       (C.F_UNDEF, t.atoms(AppliedUndef)), (C.F_MAYBE_NAN, _may_be_nan(t))):
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
                    COUNTS['keys-used-derived'] += 1
                elif CHECK_ON[0] and not same_value(table.row(i)[2], r, c, True):
                    bad('key-used', e, site)
            return r
        return key

    R._key = counted('relations._key', R._key)
    L.default_sort_key = counted('lra_adapter', L.default_sort_key)


def report(path):
    with open(path, 'w') as f:
        json.dump(dict(counts=COUNTS, kept=KEPT, refused=REFUSED, bad=BAD), f, indent=0, sort_keys=True)
