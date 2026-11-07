"""Step 6e (issue 323): `knowledge/templates/core.py` on Rust under `knowledge_live.install()`, over the query's ids.

`install(shadow)` swaps core's names in core, `wiring` and `functions` (they import them by value, and core calls itself), and
returns the undo. Ported so far: the Add family. The splits (`_half_split`, `_bound_split`, `_imag_split`, `_recip_templates`'
shape test) read the query's table; the rule builders (`_half_rules`, `_bound_rules`, `_recip_rules`, `_imag_rules`,
`_imag_number_rules`, `_not_unit_premises`) are Rust's whenever the query isn't kept. `facts`, `_CACHE` and the keys stay
Python (6d's `_common`): keys are built from the query's objects, or from p/q, which is conversion.

Stays on Python, counted in `COUNTS`: a kept query (`core:kept`), no query on the stack (`core:no-query`), an arg that isn't an
input term (`core:derived`). Scaffolding, by the planner's ruling: `kept_product`'s rest of a Mul is built by SymPy
(`core:kept_product`) and checked against Rust's `mul`; a mismatch refuses the query (`core:kept_product:mismatch`), and a
product Rust's algebra refuses is used unchecked (`core:kept_product:unchecked`). Not yet ported: the Mul and Pow families,
and `_imag_templates`' all-number branch (an `Add` of numbers, on Python, `core:imag_number:python`).
"""
import os

import sa_solver
from sympy import Rational, S

from satassume.knowledge.domain import kept_product
from satassume.knowledge.templates import core, functions, wiring

import term_live

RULES = ('_half_rules', '_bound_rules', '_recip_rules', '_imag_rules', '_imag_number_rules', '_not_unit_premises')
SPLITS = ('_half_split', '_bound_split', '_imag_split', '_recip_templates', '_imag_templates')
#: A planted bug for the comparisons (`--plant core-...` in knowledge_fresh / the bar): name -> what it breaks. Python side only;
#: the Rust plants are source mutants (mutate_knowledge.py).
PLANT = [os.environ.get('SA_CORE_PLANT') or None]


def _pq(c):
    return int(c.p), int(c.q)


def _rat(p, q):
    return Rational(p, q)


def install(shadow, counts, fault_cls, mismatch):
    py = {n: getattr(core, n) for n in RULES + SPLITS + ('_coeff_term', '_imag_term')}

    def query():
        """The query's `_Query`, or None to stay on Python (counted)."""
        q = term_live.current()
        if q is None:
            counts['core:no-query'] += 1
            return None
        if q.kept is not None:
            counts['core:kept'] += 1
            return None
        return q

    def ids_of(q, xs):
        out = []
        for x in xs:
            i = q.ids.get(x)
            if i is None or type(q.objects[i]) is not type(x):
                counts['core:derived'] += 1
                return None
            out.append(i)
        return out

    def call(name, f, *a):
        try:
            return f(*a)
        except sa_solver.TermRefuse:
            counts['core:refuse'] += 1
            raise
        except Exception as e:
            counts['fault'] += 1
            raise fault_cls(f'core.{name}: {e}') from e

    def rest(q, t):
        """`_coeff_term`'s `t`: an id, or factor ids that SymPy's `kept_product` builds, checked against Rust's `mul`."""
        if isinstance(t, int):
            return q.objects[t]
        counts['core:kept_product'] += 1
        ours = kept_product(tuple(q.objects[i] for i in t))
        try:
            theirs = sa_solver.core_kept_product(q.table, t)
        except sa_solver.TermRefuse:
            counts['core:kept_product:unchecked'] += 1
            return ours
        same = (ours is None) == (theirs is None)
        if same and ours is not None:
            i = q.ids.get(ours)
            same = i is None or type(q.objects[i]) is not type(ours) or i == theirs
        if not same:
            counts['core:kept_product:mismatch'] += 1
            raise sa_solver.TermRefuse('core: kept_product differs from Rust mul')
        return ours

    def coeff(q, c):
        return S.One if c is None else q.objects[c]

    def check(name, args, ours, theirs_f):
        if shadow:
            counts['shadow:core'] += 1
            mismatch('core:' + name, args, 'result', ours, theirs_f())
        return ours

    def half_split(args):
        q = query()
        ids = q and ids_of(q, args)
        if not ids:
            return py['_half_split'](args)
        counts['core:half_split'] += 1
        r = call('_half_split', sa_solver.core_half_split, q.table, ids)
        if r is not None:
            a0, terms = r
            out = []
            for a, _c, t in terms:
                t = rest(q, t)
                if t is None:
                    out = None
                    break
                out.append((a if PLANT[0] != 'core-half-parity' else 1 - a, t))
            r = None if out is None else (a0, out)
        return check('_half_split', args, r, lambda: py['_half_split'](args))

    def bound_split(args):
        q = query()
        ids = q and ids_of(q, args)
        if not ids:
            return py['_bound_split'](args)
        counts['core:bound_split'] += 1
        r = call('_bound_split', sa_solver.core_bound_split, q.table, ids)
        if r is not None:
            c0, c, t = r
            if not isinstance(t, int):
                t = rest(q, t)
                if t is not None and t.is_number:       # a built rest's, on Python with it
                    t = None
            else:
                t = q.objects[t]
            r = None if t is None else (q.objects[c0], coeff(q, c), t)
        return check('_bound_split', args, r, lambda: py['_bound_split'](args))

    def recip_templates(expr, split):
        q = query()
        c0, c1, u = split
        ids = q and ids_of(q, (u,))
        if not ids:
            return py['_recip_templates'](expr, split)
        counts['core:recip_templates'] += 1
        v = call('_recip_templates', sa_solver.core_recip_base, q.table, ids[0])
        if shadow:
            theirs = None if not (u.is_Pow and u.args[1] is S.NegativeOne) or u.args[0].is_number else u.args[0]
            mismatch('core:_recip_templates', u, 'base', None if v is None else q.objects[v], theirs)
        if v is None:
            return None
        return core.facts(('add_recip', c0, c1), lambda: core._recip_rules(c0, c1), {}, (q.objects[v], expr), 1)

    def imag_split(args):
        q = query()
        ids = q and ids_of(q, args)
        if not ids:
            return py['_imag_split'](args)
        counts['core:imag_split'] += 1
        r = call('_imag_split', sa_solver.core_imag_split, q.table, ids)
        if r is not None:
            r = [(coeff(q, c), None if x is None else q.objects[x]) for c, x in r]
        return check('_imag_split', args, r, lambda: py['_imag_split'](args))

    def imag_templates(expr, terms):
        q = query()
        xs = [x for _, x in terms if x is not None]
        ids = q and ids_of(q, xs)
        if q is None or (xs and not ids):
            return py['_imag_templates'](expr, terms)
        nums = [call('_imag_templates', sa_solver.core_is_number, q.table, i) for i in ids or ()]
        if all(nums):
            counts['core:imag_number:python'] += 1          # builds an Add of numbers: on Python
            return py['_imag_templates'](expr, terms)
        counts['core:imag_templates'] += 1
        if len(xs) > core.MAX_ONEOUT:
            return None
        signs = tuple(1 if c.p > 0 else -1 for c, x in terms if x is not None)
        csign = frozenset(1 if c.p > 0 else -1 for c, x in terms if x is None)
        consts = {k: x for k, x in enumerate(xs) if x.is_Atom and nums[k]}
        key = ('add_imag', signs, csign, tuple(sorted((k, core.const_key(x)) for k, x in consts.items())))
        return core.facts(key, lambda: core._imag_rules(signs, csign), consts, tuple(xs) + (expr,), len(xs))

    def kept():
        q = term_live.current()
        if q is not None and q.kept is not None:
            counts['core:kept'] += 1
            return True
        return False

    def rules(name, rs, conv):
        f = py[name]

        def g(*a):
            if kept():
                return f(*a)
            counts['core:' + name] += 1
            r = call(name, rs, *conv(*a))
            if PLANT[0] == 'core-rules-drop-last' and len(r) > 1:
                r = r[:-1]
            return check(name, a, r, lambda: f(*a))
        g.__name__ = g.__qualname__ = name
        g.__module__ = core.__name__
        g.__wrapped__ = f
        return g

    def not_unit(c0, c1):
        if kept():
            return py['_not_unit_premises'](c0, c1)
        counts['core:_not_unit_premises'] += 1
        r = [core._INT_BOUNDS[i][0] for i in call('_not_unit_premises', sa_solver.core_not_unit_premises, *_pq(c0), *_pq(c1))]
        return check('_not_unit_premises', (c0, c1), r, lambda: py['_not_unit_premises'](c0, c1))

    swap = {
        '_half_rules': rules('_half_rules', sa_solver.core_half_rules, lambda a0, odd, m: (a0, [bool(x) for x in odd], m)),
        '_bound_rules': rules('_bound_rules', sa_solver.core_bound_rules, lambda c0, c1: (*_pq(c0), *_pq(c1))),
        '_recip_rules': rules('_recip_rules', sa_solver.core_recip_rules, lambda c0, c1: (*_pq(c0), *_pq(c1))),
        '_imag_rules': rules('_imag_rules', sa_solver.core_imag_rules, lambda signs, cs: (list(signs), 1 in cs, -1 in cs)),
        '_imag_number_rules': rules('_imag_number_rules', sa_solver.core_imag_number_rules, lambda: ()),
        '_not_unit_premises': not_unit,
        '_half_split': half_split, '_bound_split': bound_split, '_imag_split': imag_split,
        '_recip_templates': recip_templates, '_imag_templates': imag_templates,
    }
    for name, f in swap.items():
        if not hasattr(f, '__wrapped__'):
            f.__wrapped__ = py[name]
    mods = (core, wiring, functions)
    saved = [(m, n, m.__dict__[n]) for m in mods for n in swap if n in m.__dict__]
    for m, n, _ in saved:
        setattr(m, n, swap[n])

    def undo():
        for m, n, f in saved:
            setattr(m, n, f)
    return undo
