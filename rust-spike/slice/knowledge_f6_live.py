"""Step 6f (issue 323): `knowledge/templates/{functions,special,rootof,nodes,physics,stats}.py` on Rust under
`knowledge_live.install()`, over the query's ids (term/tf6.rs).

`install(shadow, counts, fault_cls, mismatch)` swaps the six modules' names (they look them up as globals at call time; the
family modules take `shifted` by value, so it is swapped wherever it is bound) and returns the undo.

On Rust whenever the query isn't kept: the rule builders (`_pi_trig_rules`, `_cosh_shift_rules`, `_parts_of_round_rules`,
`_genocchi_half_rules`, `nodes._accum`, `special._multigamma_rules`' build), the unit facts (`_unit_interval_units` for a
Rational, `rootof._facts` over realroots.rs's `root_facts`, `stats._random_units`, `nodes._idx_facts`,
`physics._quantity_facts`), and the splits over the query's table (`_cosh_shift_split`, `shifted`, `special._doubled`).
A derived slot term (`r`, `x + c`, `2*x`) is rebuilt by SymPy from Rust's row (`term_live.scaffold`, counted under
`scaffold:rebuilt:f6`, refused on a form mismatch): the planner's scaffolding.

Stays on Python, counted in `COUNTS`: a kept query (`f6:kept`), no query on the stack (`f6:no-query`), an arg that isn't a
term with an id (`f6:derived`). Named SymPy-semantics callbacks (planner, 7 Nov), counted and loud through `fallback`:
`special._multigamma_value` (`f6:multigamma_value:python`: SymPy evaluates multigamma at a constant), and
`_unit_interval_units` for a Float (`f6:unit_interval:float`: Floats keep SymPy's precision semantics, the planner's default).
The template shells (`_unary`, `nary`, `_pi_trig`, `_exp_ipi`, `_cosh_shift`, `parts_of_round_templates`,
`multigamma_templates`, `accumbounds_templates`, the `*_units` registrations) stay Python: what's left in them is the arity
check, `const_key`/`facts`/`units` (6d's `_common`) and the rows' `gen` (6g). Conversion (planner's reclass ruling):
`rootof._coefficients`, and `randomsymbol_units`' reads of declared facts.
"""
import os
import sys

import sa_solver
from sympy import Add, Mul, Rational, S

from satassume.knowledge.domain import kept_product
from satassume.knowledge.templates import functions, nodes, physics, rootof, special, stats
from satassume.sat.formula import Not, P

import term_live

PLANT = [os.environ.get('SA_F6_PLANT') or None]
if not PLANT[0] and (os.environ.get('SLICE_SESSION_PLANT') or '').startswith('f6-'):
    PLANT[0] = os.environ['SLICE_SESSION_PLANT']   # the bar's channel (bar.sh's plants phase)

#: Plants, one per moved function: `f6-<name>` drops the last rule or fact Rust gave (or as noted in the wrapper).
PLANTS = ('f6-pi-trig', 'f6-cosh-rules', 'f6-parts-round', 'f6-genocchi', 'f6-accum', 'f6-multigamma', 'f6-unit-interval',
          'f6-rootof', 'f6-random', 'f6-idx', 'f6-quantity', 'f6-cosh-split', 'f6-shifted', 'f6-doubled')


def _hit(name):
    if PLANT[0] != name:
        return False
    kl = sys.modules.get('knowledge_live')
    if kl is not None:
        kl._fired()
    return True


def _drop(name, r):
    return r[:-1] if r and _hit(name) else r


def _pq(c):
    return int(c.p), int(c.q)


def install(shadow, counts, fault_cls, mismatch):
    mods = {'functions': functions, 'special': special, 'nodes': nodes, 'physics': physics, 'rootof': rootof,
            'stats': stats}
    names = {
        'functions': ('_pi_trig_rules', '_cosh_shift_rules', '_parts_of_round_rules', '_genocchi_half_rules',
                      '_unit_interval_units', '_cosh_shift_split', 'shifted'),
        'special': ('_doubled', '_multigamma_rules', '_multigamma_value'),
        'nodes': ('_accum', '_idx_facts'),
        'physics': ('_quantity_facts',),
        'rootof': ('_facts',),
        'stats': ('_random_units',),
    }
    py = {n: getattr(mods[m], n) for m, ns in names.items() for n in ns}

    def kept():
        q = term_live.current()
        if q is not None and q.kept is not None:
            counts['f6:kept'] += 1
            return True
        return False

    def query():
        q = term_live.current()
        if q is None:
            counts['f6:no-query'] += 1
            return None
        if q.kept is not None:
            counts['f6:kept'] += 1
            return None
        return q

    def id_of(q, x, name):
        i = term_live.term_id(q, x, 'f6')
        if i is None:
            counts['f6:derived'] += 1
            counts['f6:derived:' + name] += 1
        return i

    def obj(q, i):
        return term_live.scaffold(q, i, 'f6')

    def call(name, f, *a):
        try:
            return f(*a)
        except sa_solver.TermRefuse:
            counts['f6:refuse'] += 1
            raise
        except Exception as e:
            counts['fault'] += 1
            raise fault_cls(f'f6.{name}: {e}') from e

    def fallback(key, f, *a):
        """A named SymPy-semantics callback: counted under `key`, loud on any exception (KnowledgeFault is a BaseException)."""
        counts[key] += 1
        try:
            return f(*a)
        except Exception as e:
            counts['fault'] += 1
            raise fault_cls(f'{key}: {type(e).__name__}: {e}') from e

    def check(name, args, ours, theirs_f):
        if shadow:
            counts['shadow:f6'] += 1
            mismatch('f6:' + name, args, 'result', ours, theirs_f())
        return ours

    def rest(q, t):
        """A split's `s`: an id, or factor ids that SymPy's `kept_product` builds, checked against Rust's `mul`."""
        if isinstance(t, int):
            return obj(q, t)
        counts['f6:kept_product'] += 1
        ours = kept_product(tuple(obj(q, i) for i in t))
        try:
            theirs = sa_solver.core_kept_product(q.table, t)
        except sa_solver.TermRefuse:
            counts['f6:kept_product:unchecked'] += 1
            return ours
        same = (ours is None) == (theirs is None)
        if same and ours is not None:
            i = q.ids.get(ours)
            same = i is None or type(q.objects[i]) is not type(ours) or i == theirs
        if not same:
            counts['f6:kept_product:mismatch'] += 1
            raise sa_solver.TermRefuse('f6: kept_product differs from Rust mul')
        return ours

    # ---- Rule builders that append to `R`.

    def appending(name, plant, rs, conv):
        f = py[name]

        def g(R, *a):
            if kept():
                return f(R, *a)
            counts['f6:' + name] += 1
            r = _drop(plant, call(name, rs, *conv(*a)))
            if shadow:
                ref = functions.Rules()
                f(ref, *a)
                check(name, a, r, lambda: ref.rules)
            R.rules.extend(r)
        return g

    # ---- Builders and unit facts with no arguments from the query.

    def pure(name, plant, rs, conv=lambda *a: a):
        f = py[name]

        def g(*a):
            if kept():
                return f(*a)
            counts['f6:' + name] += 1
            r = _drop(plant, call(name, rs, *conv(*a)))
            return check(name, a, r, lambda: f(*a))
        return g

    def multigamma_rules(p):
        if kept():
            return py['_multigamma_rules'](p)

        def build():
            counts['f6:_multigamma_rules'] += 1
            r = _drop('f6-multigamma', call('_multigamma_rules', sa_solver.f6_multigamma_rules, int(p)))
            return check('_multigamma_rules', p, r, py['_multigamma_rules'](p))
        return build

    def unit_interval_units(kind, c, expr):
        if kept():
            return py['_unit_interval_units'](kind, c, expr)
        if c.is_Float:
            return fallback('f6:unit_interval:float', py['_unit_interval_units'], kind, c, expr)
        if not c.is_Rational:
            return []
        counts['f6:_unit_interval_units'] += 1
        r = call('_unit_interval_units', sa_solver.f6_unit_interval_units, kind == 'acos', *_pq(c))
        if r and _hit('f6-unit-interval'):
            r = r[:-1] + [(r[-1][0], not r[-1][1])]
        out = [P(p, expr) if v else Not(P(p, expr)) for p, v in r]
        return check('_unit_interval_units', (kind, c), out, lambda: py['_unit_interval_units'](kind, c, expr))

    def rootof_facts(coeffs, index):
        if kept():
            return py['_facts'](coeffs, index)
        counts['f6:_facts'] += 1
        if coeffs is not None:
            counts['realroots:root_facts'] += 1     # realroots.rs's root_facts, called from tf6.rs
        r = _drop('f6-rootof', call('_facts', sa_solver.f6_rootof_facts, None if coeffs is None else list(coeffs),
                                    int(index)))
        return check('_facts', (coeffs, index), r, lambda: py['_facts'](coeffs, index))

    def multigamma_value(expr, x, p):
        return fallback('f6:multigamma_value:python', py['_multigamma_value'], expr, x, p)

    # ---- Splits over the query's table.

    def cosh_shift_split(arg):
        q = query()
        i = q and id_of(q, arg, '_cosh_shift_split')
        if i is None or q is None:
            return py['_cosh_shift_split'](arg)
        counts['f6:_cosh_shift_split'] += 1
        r = call('_cosh_shift_split', sa_solver.f6_cosh_shift_split, q.table, i)
        if r is not None:
            ri, c, s_ = r
            c = Rational(*c)
            if _hit('f6-cosh-split'):
                c = c + 1
            if s_ is not None:
                s_ = rest(q, s_)
                if s_ is None:      # Python's `ipi_split` skips this term: its whole loop decides
                    counts['f6:_cosh_shift_split:rest-none'] += 1
                    return py['_cosh_shift_split'](arg)
            r = (obj(q, ri), c, s_)
        return check('_cosh_shift_split', arg, r, lambda: py['_cosh_shift_split'](arg))

    def shifted(x, c):
        q = query()
        c = S(c)
        i = q and id_of(q, x, 'shifted')
        if i is None or q is None or not c.is_Rational:
            if q is not None and not c.is_Rational:
                counts['f6:shifted:not-rational'] += 1
            return py['shifted'](x, c)
        counts['f6:shifted'] += 1
        if _hit('f6-shifted'):
            c = c + 1
        k = call('shifted', sa_solver.f6_shifted, q.table, i, *_pq(c))
        return check('shifted', (x, c), obj(q, k), lambda: py['shifted'](x, c))

    def doubled(x):
        q = query()
        i = q and id_of(q, x, '_doubled')
        if i is None or q is None:
            return py['_doubled'](x)
        counts['f6:_doubled'] += 1
        k = i if _hit('f6-doubled') else call('_doubled', sa_solver.f6_doubled, q.table, i)
        return check('_doubled', x, obj(q, k), lambda: py['_doubled'](x))

    swap = {
        'functions': {
            '_pi_trig_rules': appending('_pi_trig_rules', 'f6-pi-trig', sa_solver.f6_pi_trig_rules,
                                        lambda cos_, c, has_s: (bool(cos_), *_pq(c), bool(has_s))),
            '_cosh_shift_rules': appending('_cosh_shift_rules', 'f6-cosh-rules', sa_solver.f6_cosh_shift_rules,
                                           lambda c, has_s: (*_pq(c), bool(has_s))),
            '_genocchi_half_rules': appending('_genocchi_half_rules', 'f6-genocchi', sa_solver.f6_genocchi_half_rules,
                                              lambda h: (h,)),
            '_parts_of_round_rules': pure('_parts_of_round_rules', 'f6-parts-round', sa_solver.f6_parts_of_round_rules),
            '_unit_interval_units': unit_interval_units,
            '_cosh_shift_split': cosh_shift_split,
            'shifted': shifted,
        },
        'special': {
            '_doubled': doubled,
            '_multigamma_rules': multigamma_rules,
            '_multigamma_value': multigamma_value,
        },
        'nodes': {
            '_accum': pure('_accum', 'f6-accum', sa_solver.f6_accum_rules),
            '_idx_facts': pure('_idx_facts', 'f6-idx', lambda: sa_solver.f6_const_units('idx')),
        },
        'physics': {'_quantity_facts': pure('_quantity_facts', 'f6-quantity',
                                            lambda: sa_solver.f6_const_units('quantity'))},
        'rootof': {'_facts': rootof_facts},
        'stats': {'_random_units': pure('_random_units', 'f6-random', sa_solver.f6_randomsymbol_units,
                                        lambda pos, integer, real: (pos, integer, bool(real)))},
    }
    saved = []
    for m, fs in swap.items():
        for n, f in fs.items():
            f.__wrapped__ = py[n]
            f.__name__ = f.__qualname__ = n
            saved.append((mods[m], n, getattr(mods[m], n)))
            setattr(mods[m], n, f)
    # `shifted` is bound by value in special and the family modules (`from .functions import shifted`).
    for name, m in list(sys.modules.items()):
        if (name.startswith('satassume.knowledge.') and m is not functions
                and getattr(m, 'shifted', None) is py['shifted']):
            saved.append((m, 'shifted', py['shifted']))
            m.shifted = shifted

    def undo():
        for m, n, f in saved:
            setattr(m, n, f)
    return undo
