"""Step 6e (issue 323): `knowledge/templates/core.py` on Rust under `knowledge_live.install()`, over the query's ids.

`install(shadow)` swaps core's names in core, `wiring` and `functions` (they import them by value, and core calls itself), and
returns the undo. Ported so far: the Add family. The splits (`_half_split`, `_bound_split`, `_imag_split`, `_recip_templates`'
shape test) read the query's table; the rule builders (`_half_rules`, `_bound_rules`, `_recip_rules`, `_imag_rules`,
`_imag_number_rules`, `_not_unit_premises`) are Rust's whenever the query isn't kept. `facts`, `_CACHE` and the keys stay
Python (6d's `_common`): keys are built from the query's objects, or from p/q, which is conversion.

Stays on Python, counted in `COUNTS`: a kept query (`core:kept`), no query on the stack (`core:no-query`), an arg that isn't an
input term (`core:derived`). Scaffolding, by the planner's ruling: `kept_product`'s rest of a Mul is built by SymPy
(`core:kept_product`) and checked against Rust's `mul`; a mismatch refuses the query (`core:kept_product:mismatch`), and a
product Rust's algebra refuses is used unchecked (`core:kept_product:unchecked`). Named SymPy-semantics callbacks (planner,
7 Nov), counted and loud through `fallback`: `_imag_templates`' all-number branch (`core:imag_number:python`) and
`_unit_power_units` for a non-Rational exponent (`core:unit_power:python`).
"""
import os
import types
import sys

import sa_solver
from sympy import Add, Mul, Rational, S

from satassume.knowledge.domain import kept_product
from satassume.sat.formula import Not, P
from satassume.knowledge.templates import _rows_runtime, core, functions, wiring

import term_live

RULES = ('_half_rules', '_bound_rules', '_recip_rules', '_imag_rules', '_imag_number_rules', '_not_unit_premises')
#: 6g(c5): the Addition template builders rows_tpl.rs computes directly (`RowsTpl::add_tpl`).
ADD_TPL = ('_half_templates', '_bound_templates', '_recip_templates', '_imag_templates')
SPLITS = ('_half_split', '_bound_split', '_imag_split', '_recip_templates', '_imag_templates')
#: The Mul and Pow families. `ipi_split`/`pi_split` stay Python's one-line calls of `_pi_split`, which is swapped in core, so
#: `functions._pi_trig`'s default `split_=pi_split` and the closures built before install reach Rust too.
MULPOW = ('_mul_factor_sets', '_quotient_rules', '_quotient_templates', '_unit_angle', '_pi_split', 'ipi_rules',
          'irrational_root', '_unit_power_units', '_exp_arg', '_pow_bound_templates')
#: A planted bug for the comparisons (`--plant core-...` in knowledge_fresh / the bar): name -> what it breaks. Python side only;
#: the Rust plants are source mutants (mutate_knowledge.py).
PLANT = [os.environ.get('SA_CORE_PLANT') or None]
#: 6g(c): with `install(shadow=True)`, `shadow_split(name, args, ours)`: Python's split for a result rows_tpl.rs's direct path
#: computed (the shell never runs there), compared field by field as the shell's `check` does. knowledge_common_live hands it
#: to Rust's Common (py_fns '_shadow_split'). None when the shadow is off.
SHADOW_SPLIT = [None]
if not PLANT[0] and (os.environ.get('SLICE_SESSION_PLANT') or '').startswith('core-'):
    PLANT[0] = os.environ['SLICE_SESSION_PLANT']   # the bar's channel (bar.sh's plants phase)


def _hit(name):
    """True when plant `name` is on; counts the firing where the bar's `fired` reads it (knowledge_live._fired)."""
    if PLANT[0] != name:
        return False
    kl = sys.modules.get('knowledge_live')
    if kl is not None:
        kl._fired()
    return True


def _pq(c):
    return int(c.p), int(c.q)


def _rat(p, q):
    return Rational(p, q)


def install(shadow, counts, fault_cls, mismatch):
    py = {n: getattr(core, n) for n in RULES + SPLITS + MULPOW + ('_coeff_term', '_imag_term')}
    # The shadow's reference for the composites: Python's code over Python's own helpers, not the swapped ones.
    pure = dict(core.__dict__)
    for n, f in list(pure.items()):
        if isinstance(f, types.FunctionType) and f.__globals__ is core.__dict__:
            pure[n] = types.FunctionType(f.__code__, pure, n, f.__defaults__, f.__closure__)

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

    def ids_of(q, xs, name=None):
        out = []
        for x in xs:
            i = q.ids.get(x)
            if i is not None and type(q.objects[i]) is not type(x):
                i = None
            if i is None and isinstance(x, (Add, Mul)):
                i = term_live.term_id(q, x, 'core')        # a derived Add or Mul of terms with ids: a row as it is
                if i is not None:
                    counts['core:derived:id'] += 1
            if i is None:
                counts['core:derived'] += 1
                if name:
                    counts['core:derived:' + name] += 1
                return None
            out.append(i)
        return out

    def obj(q, i):
        return term_live.scaffold(q, i, 'core')

    def call(name, f, *a):
        try:
            return f(*a)
        except sa_solver.TermRefuse:
            counts['core:refuse'] += 1
            raise
        except Exception as e:
            counts['fault'] += 1
            raise fault_cls(f'core.{name}: {e}') from e

    def fallback(key, f, *a):
        """A named SymPy-semantics callback (planner, 7 Nov, the same class as R9 `enclose`): counted under `key`, and loud on
        any exception (KnowledgeFault is a BaseException), so it can't come back from a quiet handler as "unknown"."""
        counts[key] += 1
        try:
            return f(*a)
        except Exception as e:
            counts['fault'] += 1
            raise fault_cls(f'{key}: {type(e).__name__}: {e}') from e

    def rest(q, t):
        """`_coeff_term`'s `t`: an id, or factor ids that SymPy's `kept_product` builds, checked against Rust's `mul`."""
        if isinstance(t, int):
            return obj(q, t)
        counts['core:kept_product'] += 1
        ours = kept_product(tuple(obj(q, i) for i in t))
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
        return S.One if c is None else obj(q, c)

    def check(name, args, ours, theirs_f):
        if shadow:
            counts['shadow:core'] += 1
            mismatch('core:' + name, args, 'result', ours, theirs_f())
        return ours

    def half_split(args):
        q = query()
        ids = q and ids_of(q, args, '_half_split')
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
                out.append((1 - a if _hit('core-half-parity') else a, t))
            r = None if out is None else (a0, out)
        return check('_half_split', args, r, lambda: py['_half_split'](args))

    def bound_split(args):
        q = query()
        ids = q and ids_of(q, args, '_bound_split')
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
                t = obj(q, t)
            r = None if t is None else (obj(q, c0), coeff(q, c), t)
        return check('_bound_split', args, r, lambda: py['_bound_split'](args))

    def recip_templates(expr, split):
        q = query()
        c0, c1, u = split
        ids = q and ids_of(q, (u,), '_recip_templates')
        if not ids:
            return py['_recip_templates'](expr, split)
        counts['core:recip_templates'] += 1
        v = call('_recip_templates', sa_solver.core_recip_base, q.table, ids[0])
        if shadow:
            theirs = None if not (u.is_Pow and u.args[1] is S.NegativeOne) or u.args[0].is_number else u.args[0]
            mismatch('core:_recip_templates', u, 'base', None if v is None else obj(q, v), theirs)
        if v is None:
            return None
        return core.facts(('add_recip', c0, c1), lambda: core._recip_rules(c0, c1), {}, (obj(q, v), expr), 1)

    def imag_split(args):
        q = query()
        ids = q and ids_of(q, args, '_imag_split')
        if not ids:
            return py['_imag_split'](args)
        counts['core:imag_split'] += 1
        r = call('_imag_split', sa_solver.core_imag_split, q.table, ids)
        if r is not None:
            r = [(coeff(q, c), None if x is None else obj(q, x)) for c, x in r]
        return check('_imag_split', args, r, lambda: py['_imag_split'](args))

    def imag_templates(expr, terms):
        q = query()
        xs = [x for _, x in terms if x is not None]
        ids = q and ids_of(q, xs, '_imag_templates')
        if q is None or (xs and not ids):
            return py['_imag_templates'](expr, terms)
        nums = [call('_imag_templates', sa_solver.core_is_number, q.table, i) for i in ids or ()]
        if all(nums):
            # Builds an Add of numbers with SymPy's arithmetic. Later question: can Rust's constfield do it exactly?
            return fallback('core:imag_number:python', py['_imag_templates'], expr, terms)
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
            if len(r) > 1 and _hit('core-rules-drop-last'):
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


    # ---- The Mul family.

    def pi_split_(arg, imag):
        q = query()
        ids = q and ids_of(q, (arg,), '_pi_split')
        if not ids:
            return py['_pi_split'](arg, imag)
        counts['core:_pi_split'] += 1
        r = call('_pi_split', sa_solver.core_pi_split, q.table, ids[0], imag)
        if r is not None:
            c, s_ = r
            c = _rat(*c)
            if _hit('core-pi-coeff'):
                c = c + 1
            if s_ is not None:
                s_ = rest(q, s_)
            r = None if (s_ is None and r[1] is not None) else (c, s_)
        return check('_pi_split', (arg, imag), r, lambda: py['_pi_split'](arg, imag))

    def mul_factor_sets(expr):
        q = query()
        ids = q and ids_of(q, (expr,), '_mul_factor_sets')
        if not ids:
            return py['_mul_factor_sets'](expr)
        counts['core:_mul_factor_sets'] += 1
        ct, ipi = call('_mul_factor_sets', sa_solver.core_mul_factor_sets, q.table, ids[0])
        out = [expr.args]
        if ct is not None:
            c, fs = ct
            t = rest(q, fs)
            if t is not None:
                out.append((obj(q, c), t))
        if ipi is not None:
            c, s_ = ipi
            c = _rat(*c)
            s_ = rest(q, s_)
            if s_ is not None and s_.is_Mul and not _hit('core-mul-drop-ipi'):
                out.append(((c,) if c != 1 else ()) + (S.ImaginaryUnit, S.Pi, s_))
        return check('_mul_factor_sets', expr, out, lambda: pure['_mul_factor_sets'](expr))

    def quotient_templates(expr):
        q = query()
        ids = q and ids_of(q, (expr,), '_quotient_templates')
        if not ids:
            return py['_quotient_templates'](expr)
        counts['core:_quotient_templates'] += 1
        r = call('_quotient_templates', sa_solver.core_quotient_shape, q.table, ids[0])
        if shadow:
            theirs = _quotient_shape_py(expr)
            mismatch('core:_quotient_templates', expr, 'shape', None if r is None else tuple(obj(q, i) for i in r), theirs)
        if r is None:
            return None
        a, v, t = (obj(q, i) for i in r)
        consts = {0: a} if a.is_Atom and call('_quotient_templates', sa_solver.core_is_number, q.table, r[0]) else {}
        return core.facts(('mul_quot', core.const_key(a) if consts else None), core._quotient_rules, consts,
                          (a, v, t, expr), 3)

    # ---- The Pow family.

    def unit_angle(b):
        q = query()
        ids = q and ids_of(q, (b,), '_unit_angle')
        if not ids:
            return py['_unit_angle'](b)
        counts['core:_unit_angle'] += 1
        r = call('_unit_angle', sa_solver.core_unit_angle, q.table, ids[0])
        r = None if r is None else _rat(*r)
        return check('_unit_angle', b, r, lambda: py['_unit_angle'](b))

    def exp_arg(b):
        q = query()
        ids = q and ids_of(q, (b,), '_exp_arg')
        if not ids:
            return py['_exp_arg'](b)
        counts['core:_exp_arg'] += 1
        r = call('_exp_arg', sa_solver.core_exp_arg, q.table, ids[0])
        r = None if r is None else obj(q, r)
        return check('_exp_arg', b, r, lambda: py['_exp_arg'](b))

    def ipi_rules(rule, c, iS, N):
        if kept():
            return py['ipi_rules'](rule, c, iS, N)
        counts['core:ipi_rules'] += 1
        r = call('ipi_rules', sa_solver.core_ipi_rules, *_pq(c), iS, N)
        if len(r) > 1 and _hit('core-rules-drop-last'):
            r = r[:-1]
        if shadow:
            theirs = []
            py['ipi_rules'](lambda p, k: theirs.append((p, k)), c, iS, N)
            check('ipi_rules', (c, iS, N), r, lambda: theirs)
        for prem, concl in r:
            rule(prem, concl)

    def irrational_root(b, e):
        if b is None or e is None:
            return py['irrational_root'](b, e)
        q = query()
        ids = q and ids_of(q, (b, e), 'irrational_root')
        if not ids:
            return py['irrational_root'](b, e)
        counts['core:irrational_root'] += 1
        r = call('irrational_root', sa_solver.core_irrational_root, q.table, *ids)
        return check('irrational_root', (b, e), r, lambda: py['irrational_root'](b, e))

    def unit_power_units(angle, e, expr):
        q = query()
        ids = q and ids_of(q, (e,), '_unit_power_units')
        r = ids and call('_unit_power_units', sa_solver.core_unit_power_units, q.table, *_pq(angle), ids[0])
        if r is None or not ids:
            # SymPy's as_real_imag of a non-Rational exponent. Later question: can Rust's constfield do it exactly?
            return fallback('core:unit_power:python', py['_unit_power_units'], angle, e, expr)
        counts['core:_unit_power_units'] += 1
        out = [P(p, expr) if v else Not(P(p, expr)) for p, v in r]
        return check('_unit_power_units', (angle, e, expr), out, lambda: py['_unit_power_units'](angle, e, expr))

    def pow_bound_templates(expr):
        q = query()
        ids = q and ids_of(q, (expr,), '_pow_bound_templates')
        if not ids:
            return py['_pow_bound_templates'](expr)
        counts['core:_pow_bound_templates'] += 1
        shape = call('_pow_bound_templates', sa_solver.core_pow_bound_shape, q.table, ids[0])
        r = None
        if shape is not None:
            b, e = (obj(q, i) for i in shape)
            split = core._bound_split(b.args)
            if split is not None:
                c0, c1, u = split
                idx = call('_pow_bound_templates', sa_solver.core_not_unit_premises, *_pq(c0), *_pq(c1))
                if idx:
                    r = (b, e, c0, c1, u, idx)
        if shadow:
            ours = None if r is None else r[2:5] + ([core._INT_BOUNDS[i][0] for i in r[5]],)
            mismatch('core:_pow_bound_templates', expr, 'split', ours, _pow_bound_py(expr))
        if r is None:
            return None
        b, e, c0, c1, u, idx = r
        consts = {1: e} if call('_pow_bound_templates', sa_solver.core_is_number, q.table, shape[1]) else {}
        return core.facts(('pow_bound', c0, c1, core.const_key(e) if consts else None),
                          lambda: sa_solver.core_pow_bound_rules(idx), consts, (u, e, b, expr), 3)

    def _quotient_shape_py(expr):
        if len(expr.args) != 2:
            return None
        a, t = expr.args
        if not t.is_Pow:
            a, t = t, a
        if not t.is_Pow or t.args[0].is_number or not (t.args[1].is_Integer and t.args[1].p < 0):
            return None
        return a, t.args[0], t

    def _pow_bound_py(expr):
        b, e = expr.args
        if not b.is_Add or (e.is_number and not (e.is_Integer and e.p < 0)):
            return None
        split = py['_bound_split'](b.args)
        if split is None:
            return None
        prems = py['_not_unit_premises'](*split[:2])
        return (*split, prems) if prems else None

    swap = {
        '_half_rules': rules('_half_rules', sa_solver.core_half_rules, lambda a0, odd, m: (a0, [bool(x) for x in odd], m)),
        '_bound_rules': rules('_bound_rules', sa_solver.core_bound_rules, lambda c0, c1: (*_pq(c0), *_pq(c1))),
        '_recip_rules': rules('_recip_rules', sa_solver.core_recip_rules, lambda c0, c1: (*_pq(c0), *_pq(c1))),
        '_imag_rules': rules('_imag_rules', sa_solver.core_imag_rules, lambda signs, cs: (list(signs), 1 in cs, -1 in cs)),
        '_imag_number_rules': rules('_imag_number_rules', sa_solver.core_imag_number_rules, lambda: ()),
        '_not_unit_premises': not_unit,
        '_half_split': half_split, '_bound_split': bound_split, '_imag_split': imag_split,
        '_recip_templates': recip_templates, '_imag_templates': imag_templates,
        '_mul_factor_sets': mul_factor_sets, '_quotient_templates': quotient_templates,
        '_quotient_rules': rules('_quotient_rules', sa_solver.core_quotient_rules, lambda: ()),
        '_unit_angle': unit_angle, '_pi_split': pi_split_, 'ipi_rules': ipi_rules, 'irrational_root': irrational_root,
        '_unit_power_units': unit_power_units, '_exp_arg': exp_arg, '_pow_bound_templates': pow_bound_templates,
    }
    def _add_tpl_py(name, expr, split):
        # 6g(c5): Python's template builder with `facts` captured: (key, consts, objs, node, gen()), Python's rules
        # (the originals, not the Rust swap), or None when it builds no template.
        got = []
        names = ('facts',) + RULES
        saved = {n: core.__dict__[n] for n in names}
        saved_tpl = core.__dict__[name]             # _half_templates/_bound_templates: core's own (not swapped)

        def capture(key, gen, consts, objs, node):
            got.append((key, dict(consts), tuple(objs), node, gen()))
            return got[-1]
        try:
            core.facts = capture
            for n in RULES:
                setattr(core, n, py[n])
            r = py.get(name, saved_tpl)(expr, split)
        finally:
            for n, f in saved.items():
                setattr(core, n, f)
        return None if r is None else got[-1]

    def shadow_split(name, args, ours):
        counts['shadow:core'] += 1
        counts['shadow:direct:' + name] += 1
        if ours is not None and ours != []:
            counts['shadow:direct:' + name + ':split'] += 1
        # `_quotient_templates`: Rust shows its shape `(a, v, v**k)` or None, as the shell's shadow compares (facts' result
        # is a template object; the facts after the shape are Common::facts, shared with Python's path).
        # 6g(c3): `_pow_bound_templates` shows `(c0, c1, u, bound indices)`, compared as the shell's shadow does; `ipi_split` is
        # Python's `_pi_split(arg, True)`; `ipi_rules` collects Python's rows through its `rule`; the two-constant and
        # three-argument shells get their args as a tuple.
        if name == '_quotient_templates':
            theirs = _quotient_shape_py(args)
        elif name == '_pow_bound_templates':
            ours = None if ours is None else tuple(ours[:3]) + ([core._INT_BOUNDS[i][0] for i in ours[3]],)
            theirs = _pow_bound_py(args)
        elif name == 'ipi_split':
            theirs = py['_pi_split'](args, True)
        elif name == 'ipi_rules':
            theirs = []
            py['ipi_rules'](lambda p, k: theirs.append((p, k)), *args)
        elif name == 'constant_value':
            theirs = _rows_runtime.constant_value(*args)
        elif name in ADD_TPL:
            theirs = _add_tpl_py(name, *args)
        elif name in ('irrational_root', '_unit_power_units'):
            theirs = py[name](*args)
        else:
            theirs = py[name](args)
        mismatch('core:' + name, args, 'result', ours, theirs)
    if shadow:
        SHADOW_SPLIT[0] = shadow_split
    for name, f in swap.items():
        if not hasattr(f, '__wrapped__'):
            f.__wrapped__ = py[name]
    mods = (core, wiring, functions)
    saved = [(m, n, m.__dict__[n]) for m in mods for n in swap if n in m.__dict__]
    for m, n, _ in saved:
        setattr(m, n, swap[n])

    def undo():
        SHADOW_SPLIT[0] = None
        for m, n, f in saved:
            setattr(m, n, f)
    return undo
