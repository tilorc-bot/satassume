"""Step 5b: the id-to-term link and C2a, each mode in its own process. What comes back and the clause stream of every session,
Python against Rust's methods. `link-none` is the direct test of the planner's ruling on the link: with every resolve None, so
that nothing depends on a row being there, the stream must not move. The `drop-*` plants show this comparison sees a lost clause.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _rust():
    import backend
    backend.install_euf()
    backend.install_transfer()
    import term_live
    term_live.from_env()
    import lra_live
    lra_live.from_env()
    import session_live
    session_live.from_env()
    return session_live


def _queries():
    from sympy import Float, Function, I, Integer, Q, S, Symbol, cos, oo, pi, sin, sqrt
    x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
    rx, ry = Symbol('rx', real=True), Symbol('ry', real=True)
    n = Symbol('n', integer=True)
    f, g = Function('f'), Function('g')
    half = Float('0.5')
    return {
        'sides-free': (Q.lt(x, y), True),
        'sides-number': (Q.lt(Integer(1), x), Q.gt(x, 2)),
        'sides-half': (Q.lt(S.Half, x), Q.gt(x, 1)),
        'sides-nan': (Q.lt(x, S.NaN), True),
        'sides-closed-pi': (Q.lt(pi, x), Q.gt(x, 4)),
        'sides-closed-sqrt': (Q.lt(sqrt(2), x), Q.gt(x, 2)),
        'sides-oo': (Q.lt(x, oo), Q.real(x)),
        'sides-minus-oo': (Q.lt(-oo, x), Q.real(x)),
        'sides-I': (Q.lt(I, x), True),
        'infinite-plain': (Q.lt(rx, ry), Q.positive_infinite(ry)),
        'infinite-sum': (Q.lt(x + y, z), Q.positive_infinite(x)),
        'infinite-neg': (Q.lt(x - y, z), Q.negative_infinite(x)),
        'infinite-pi-coeff': (Q.lt(pi * x, y), Q.positive(x)),
        'infinite-cancels': (Q.lt(x - x + y, z), Q.real(y)),
        'infinite-number-term': (Q.lt(x + sqrt(2), y), Q.lt(x, y)),
        'trichotomy': (Q.eq(x, y), Q.le(x, y) & Q.ge(x, y)),
        'trichotomy-real': (Q.eq(rx, ry), Q.le(rx, ry) & Q.ge(rx, ry)),
        'trichotomy-number': (Q.positive(x), Q.le(x, 2) & Q.ge(x, 2)),
        'mention': (Q.positive(sin(2)), Q.eq(sin(2), 1)),
        'mention-two': (Q.eq(f(sin(2)), f(cos(2))), Q.eq(sin(2), cos(2))),
        'mention-with-order': (Q.lt(x, sin(2)), Q.positive(sin(2)) & Q.gt(x, 1)),
        'mention-or': (Q.positive(sin(2)) | Q.lt(x, y), Q.positive(x)),
        'mention-eq': (Q.positive(f(sin(2))), Q.eq(x, sin(2)) & Q.positive(f(x))),
        'integer-link': (Q.integer(x + 1), Q.integer(x)),
        'integer-bound': (Q.lt(2 * n, 2) & Q.gt(2 * n, 0), True),
        # C2b. `_eq_infinity`: fresh dev never reaches it, so these and the fuzz are its evidence.
        'eq-oo-symbol': (Q.eq(x, oo), Q.positive_infinite(x)),
        'eq-oo-left': (Q.eq(oo, x), Q.positive_infinite(x)),
        'eq-minus-oo': (Q.eq(x, -oo), Q.negative_infinite(x)),
        'eq-oo-number': (Q.eq(f(x), oo), Q.eq(f(x), 2)),
        'eq-oo-pi': (Q.eq(pi, oo), True),
        'eq-minus-oo-sqrt': (Q.eq(sqrt(2), -oo), True),
        # `_guard` and `_bound`: a closed term in a guarded atom, twice, so the memo and `_bounded` both answer.
        'guard-twice': (Q.lt(x + pi, y) & Q.lt(x + pi, z), Q.gt(x, 1)),
        'bound-sqrt': (Q.lt(sqrt(2), x) & Q.lt(x, sqrt(3)), Q.gt(x, 5)),
        'link-unlinked-eq': (Q.eq(x + y, 0), Q.positive(x + y)),
        # C2c. Roles, transfer's candidates and congruence.
        'congruence': (Q.positive(f(y)), Q.eq(x, y) & Q.positive(f(x))),
        'congruence-two-args': (Q.positive(g(x, z)), Q.eq(x, y) & Q.positive(g(y, z))),
        'congruence-chain': (Q.positive(f(f(y))), Q.eq(x, y) & Q.positive(f(f(x)))),
        'congruence-rational': (Q.positive(f(x)), Q.eq(x, 2) & Q.positive(f(Integer(2)))),
        'congruence-two-rationals': (Q.positive(f(Integer(1))), Q.positive(f(Integer(2)))),
        'congruence-float': (Q.positive(f(half)), Q.eq(half, S.Half) & Q.positive(f(S.Half))),
        'congruence-no-merge': (Q.positive(f(x)), Q.positive(f(y))),
        'side-rational': (Q.positive(x), Q.eq(x, S.Half)),
        'side-zero-link': (Q.eq(x + y, 0), Q.positive(x)),
        'side-pi': (Q.positive(x), Q.eq(x, pi)),
        'share-iface': (Q.eq(f(x), f(y)), Q.le(x, y) & Q.ge(x, y)),
        'share-twins': (Q.eq(f(x + 1), f(y)), Q.eq(x + 1, y)),
        'share-two-way': (Q.lt(f(x), 1), Q.eq(x, y) & Q.lt(f(y), 0)),
    }


def _run():
    from satassume import engine
    from satassume.sympy_api import ask
    from sympy import Q
    Q_lt = Q.lt
    mod = _rust() if os.environ.get('MODE', 'rust') == 'rust' else None
    streams = [None]
    init = engine.Session.__init__

    def rec_init(self, *a, **k):
        init(self, *a, **k)
        add, stream = self.solver.add_clause, []
        streams[0].append(stream)

        def rec(c):
            stream.append(list(c))
            return add(c)
        self.solver.add_clause = rec
        reg = self.solver.register_atom

        def rec_atom(th, v, *rest):
            if 'Transfer' in type(th).__name__:
                stream.append(['atom', v, repr(rest)])
            return reg(th, v, *rest)
        self.solver.register_atom = rec_atom
    engine.Session.__init__ = rec_init
    # `selectors_of` reaches no clause: what it returned is compared on its own.
    from satassume import relations as _rel
    sels, py_sel = [], _rel.Relations.selectors_of

    def rec_sel(self, atoms):
        got = py_sel(self, atoms)
        sels.append(list(got))
        return got
    _rel.Relations.selectors_of = rec_sel
    out = {}
    for name, (p, a) in _queries().items():
        streams[0] = []
        sels.clear()
        try:
            got = repr(ask(p, a, engine=engine.Engine()))
        except BaseException as e:
            got = f'{type(e).__name__}: {e}'
        out[name] = dict(answer=got, streams=streams[0], selectors=list(sels))
    # `_order_infinite` returns on an unknown sign, past the `ensure` and `var` of the terms before it: those effects stay.
    from sympy import Symbol as Sy, pi as _pi
    from satassume import relations
    from satassume.theories.lra.constfield import Undecided
    real_sign, asked = relations.sign, [0]

    def undecided(c):
        asked[0] += 1
        raise Undecided(c)
    relations.sign = undecided
    streams[0] = []
    a_, b_, c_ = Sy('a_'), Sy('b_'), Sy('c_')
    try:
        got = repr(ask(Q_lt(a_ + _pi * b_, c_), True, engine=engine.Engine()))
    finally:
        relations.sign = real_sign
    out['infinite-undecided'] = dict(answer=got, streams=streams[0], asked=asked[0] > 0)
    # The reference keeps Python's `VarTable` under `Relations`, so these stay Python's and never reach Rust's.
    from satassume.ref import ref_outcome
    from sympy import Q, Symbol
    x, y = Symbol('x'), Symbol('y')
    before = mod.counts()['rel:order_sides'] if mod else 0
    out['ref'] = dict(answer=repr(ref_outcome(Q.lt(x, y), Q.gt(x, 1))), streams=[])
    out['ref-stayed-python'] = dict(answer=repr((mod.counts()['rel:order_sides'] if mod else 0) == before), streams=[])
    return dict(cases=out, counts=mod.counts() if mod else {})


def _direct():
    """`_guard`/`_bound` and `_eq_infinity`'s three paths called directly, `is_` forced where a real query can't choose the path.

    No query reaches `_bound`, on Python's own either, so this is its evidence. `_eq_infinity`'s plan and its trace test went with
    C2b; this replaces them. Each case records clauses, `ensure` and `is_`, in order, and what the method returned."""
    from sympy import Q, S, Symbol, oo, pi, sqrt
    from satassume.engine import Engine, Session
    from satassume.knowledge.extensions import Args
    from satassume.relations import Relations
    from satassume.sat.formula import P
    mod = _rust() if os.environ.get('MODE', 'rust') == 'rust' else None
    if mod:
        import term_live
    x = Symbol('x')

    def fresh(prop, answer=...):
        eng = Engine()
        log = []
        if answer is not ...:
            def is_(e, pred):
                log.append(['is_', str(e), pred])
                return answer
            eng.is_ = is_
        s = Session(eng)
        rel = Relations(s, eng._relation_specs)
        s.relations = rel
        add, ens = s.solver.add_clause, s.ensure

        def rec_add(c):
            log.append(['clause', list(c)])
            return add(c)

        def rec_ensure(e, preds=None):
            log.append(['ensure', str(e), None if preds is None else sorted(preds)])
            return ens(e, preds)
        s.solver.add_clause, s.ensure = rec_add, rec_ensure
        reg = s.solver.register_atom

        def rec_atom(th, v, *rest):
            if 'Transfer' in type(th).__name__:
                log.append(['atom', v, repr(rest)])
            return reg(th, v, *rest)
        s.solver.register_atom = rec_atom
        if mod:
            term_live.stack().append(term_live._convert(prop, True, eng))
        return s, rel, log

    def done():
        if mod:
            term_live.stack().pop()

    def lra(rel):
        ad = next(a for a in map(rel._adapter, rel.session.engine._relation_specs) if hasattr(a, 'register_bounds'))
        rel.session.solver.attach_theory(ad.theory)
        return ad

    class NoBounds:
        pass

    class NoneBounds:
        register_bounds = None

    out = {}
    for name, side, inf, answer, path in (
            ('symbolic', x, oo, ..., 'symbolic'), ('symbolic-left', x, -oo, ..., 'symbolic'),
            ('decided-false', S(2), oo, False, 'decided'), ('decided-true', oo, oo, True, 'decided'),
            ('decided-left', S(2), -oo, False, 'decided'), ('undecided', pi, -oo, None, 'undecided')):
        for flip in (False, True):
            s, rel, log = fresh(Q.eq(side, inf), answer)
            try:
                atom = P('eq', Args((inf, side) if flip else (side, inf)))
                var = s.table.var(atom)
                rel._eq_infinity(var, atom)
            finally:
                done()
            out[f'eq-{name}-{"flip" if flip else "plain"}'] = dict(log=log, path=path, var=var)
    # Neither side infinite: no clause, no read.
    s, rel, log = fresh(Q.eq(x, S(2)), True)
    try:
        atom = P('eq', Args((x, S(2))))
        rel._eq_infinity(s.table.var(atom), atom)
    finally:
        done()
    out['eq-no-infinity'] = dict(log=log, path='none')

    y = Symbol('y')
    for name, terms, answer in (('real-at-root', [pi], ...), ('forced-unknown', [pi], None), ('forced-false', [sqrt(2)], False),
                                ('forced-true', [sqrt(2)], True), ('symbol', [x], ...), ('mixed', [pi, x, sqrt(2), y], ...)):
        s, rel, log = fresh(Q.positive(sum(terms) + x), answer)
        try:
            ad = lra(rel)
            g = rel._guard(ad, terms)
            again = rel._guard(ad, terms)
            # A new term list: new memo entry, the constant already bounded.
            other = rel._guard(ad, list(terms) + [x])
        finally:
            done()
        out['guard-' + name] = dict(log=log, guard=list(g), same=g is again, other=list(other))
    for name, ad_of in (('no-attr', lambda rel: NoBounds()), ('none-attr', lambda rel: NoneBounds())):
        s, rel, log = fresh(Q.positive(pi))
        try:
            ad = ad_of(rel)
            got = rel._guard(ad, [pi])
        finally:
            done()
        out['guard-' + name] = dict(log=log, guard=list(got))
    # `_bound` called on its own; a term with symbols registers nothing.
    for name, term in (('pi', pi), ('sqrt', sqrt(2)), ('symbol', x)):
        s, rel, log = fresh(Q.positive(term))
        try:
            got = rel._bound(lra(rel), term)
        finally:
            done()
        out['bound-' + name] = dict(log=log, returned=repr(got))
    _direct_c2c(out, fresh, done)
    return dict(cases=out, counts=mod.counts() if mod else {})


def _rel_state(rel):
    """C2c's maps, in insertion order: they stay Python's objects on `rel`, so a difference in what's written shows here."""
    return dict(
        roles=[[str(a), [[k, list(g)] for k, g in v]] for a, v in rel._roles.items()],
        tv=[[str(u), list(v)] for u, v in rel._tv.items()],
        tsrc=[[str(u), k, [list(g) for g in v]] for (u, k), v in rel._tsrc.items()],
        cand=sorted(map(str, rel._xcand)), part=sorted(map(str, rel._xpart)), pairs=sorted(map(str, rel._xpairs)),
        counted=sorted(map(str, rel._xcounted)), heads=[[str(k[0]), k[1], [str(e) for e in v]] for k, v in rel._xheads.items()],
        pend=[[str(n), b] for n, b in rel._xpend], cursors=[rel._xslot, rel._xterm, rel._xtcur, rel._xhn, rel._xhseen, rel._xnsides],
        xfer=rel.xfer is not None, engaged=rel.session.xfer is rel, sel=getattr(rel, 'xfer_sel', None))


def _direct_c2c(out, fresh, done):
    """Each method C2c moved, called directly on forged state where a real query can't choose the path. `want` is written by hand
    where a method answers, so both sides agreeing on a wrong path doesn't pass."""
    from sympy import Float, Function, Q, Rational, S, Symbol, nan
    from satassume.knowledge.extensions import Args
    from satassume.relations import _EN, _IE, _IL, _MC, _SD
    from satassume.sat.formula import P
    x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
    f, h = Function('f'), Function('h')
    e = x + y
    half, half_f = Rational(1, 2), Float('0.5')

    def case(name, body, prop=Q.positive(x), want=..., answer=...):
        s, rel, log = fresh(prop, answer)
        try:
            try:
                got = body(s, rel)
            except Exception as err:
                got = 'raised ' + type(err).__name__
        finally:
            done()
        out[name] = dict(log=log, returned=repr(got), state=_rel_state(rel))
        if want is not ...:
            out[name]['want'] = repr(want)

    def atom(pred, a, b):
        return P(pred, Args((a, b)))

    def guard(rel):
        return [-rel._fresh()]

    # `_add_role`: no info yet, a repeat by `==`, another guard, another kind, and with info there.
    eq = atom('eq', x, y)

    def role_only(s, rel):
        return rel._add_role(eq, guard(rel), 'user')

    def role_repeat(s, rel):
        v = rel._fresh()
        s.table.var(eq)
        rel._info[eq] = ([], [], [x, y])
        rel._add_role(eq, [-v], 'user')
        rel._add_role(eq, [-v], 'user')

    def role_others(s, rel):
        s.table.var(eq)
        rel._info[eq] = ([], [], [x, y])
        a, b = guard(rel), guard(rel)
        rel._add_role(eq, a, 'user')
        rel._add_role(eq, b, 'user')
        rel._add_role(eq, a, 'tri')

    def role_then_interpret(s, rel):
        v = s.table.var(eq)
        rel._add_role(eq, guard(rel), 'user')
        rel._interpret(v, eq)

    def interpret_then_role(s, rel):
        v = s.table.var(eq)
        rel._interpret(v, eq)
        rel._add_role(eq, guard(rel), 'user')

    for name, body in (('only', role_only), ('repeat', role_repeat), ('others', role_others),
                       ('then-interpret', role_then_interpret), ('after-interpret', interpret_then_role)):
        case('role-' + name, body, Q.eq(x, y))

    # `_apply_role`: each kind by each atom shape, with and without twins and terms.
    shapes = (('eq', atom('eq', x, y), None), ('lt', atom('lt', x, y), None), ('rational', atom('eq', x, half), None),
              ('zero-left', atom('eq', S.Zero, e), e), ('zero-right', atom('eq', e, S.Zero), e), ('number-left', atom('eq', S(2), e), e))
    for kind in ('user', 'link', 'tri', 'iface'):
        for shape, a, link_of in shapes:
            for twins in (False, True):
                for terms in (False, True):
                    def apply_role(s, rel, a=a, kind=kind, link_of=link_of, twins=twins, terms=terms):
                        s.table.var(a)
                        tw = [(rel._fresh(), guard(rel)), (rel._fresh(), [])] if twins else []
                        info = (tw, [x, z] if terms else [], [y, z] if terms else [])
                        if link_of is not None:
                            rel._link_of[a] = link_of
                        return rel._apply_role(a, info, kind, guard(rel))
                    case(f'apply-{kind}-{shape}-{"twins" if twins else "plain"}-{"terms" if terms else "bare"}', apply_role, Q.eq(x, y))

    def twins_no_var(s, rel):
        return rel._apply_role(eq, ([(rel._fresh(), [])], [], []), 'user', guard(rel))

    def link_not_linked(s, rel):
        s.table.var(eq)
        return rel._apply_role(eq, ([], [], [x]), 'link', guard(rel))
    case('apply-twins-no-var', twins_no_var, Q.eq(x, y), want='raised KeyError')
    case('apply-link-of-missing', link_not_linked, Q.eq(x, y), want='raised KeyError')

    # `_tsource`.
    def ts_new(s, rel):
        return rel._tsource(x, _SD, guard(rel))

    def ts_same(s, rel):
        g = guard(rel)
        rel._tvar(x, _SD)
        rel._tsource(x, _SD, g)
        rel._tsource(x, _SD, g)

    def ts_equal(s, rel):
        g = guard(rel)
        rel._tvar(x, _SD)
        rel._tsource(x, _SD, g)
        rel._tsource(x, _SD, list(g))

    def ts_mc_set(s, rel):
        rel._tvar(x, _MC)
        rel._tsource(x, _SD, guard(rel))
        rel._tsource(x, _EN, guard(rel))

    def ts_mc_past(s, rel):
        rel._tvar(x, _MC)
        rel._tsource(x, _IE, guard(rel))
        rel._tsource(x, _IL, guard(rel))

    def ts_unset(s, rel):
        rel._tvar(x, _IE)
        rel._tsource(x, _SD, guard(rel))
    for name, body in (('new', ts_new), ('same-guard', ts_same), ('equal-guard', ts_equal), ('mc-set', ts_mc_set),
                       ('mc-past', ts_mc_past), ('other-unset', ts_unset)):
        case('tsource-' + name, body)

    # `_tvar`: each kind, with sources and twice; MC before and after SD and EN, with sources and without.
    for k in (_SD, _EN, _MC, _IE, _IL):
        def tvar_bare(s, rel, k=k):
            return [rel._tvar(x, k), rel._tvar(x, k)]

        def tvar_sources(s, rel, k=k):
            rel._tsource(x, k, guard(rel))
            rel._tsource(x, k, guard(rel))
            return rel._tvar(x, k)
        case(f'tvar-{k}-bare', tvar_bare)
        case(f'tvar-{k}-sources', tvar_sources)

    def mc_before(s, rel):
        return [rel._tvar(x, _MC), rel._tvar(x, _SD), rel._tvar(x, _EN)]

    def mc_after(s, rel):
        return [rel._tvar(x, _SD), rel._tvar(x, _EN), rel._tvar(x, _MC)]

    def mc_between(s, rel):
        return [rel._tvar(x, _SD), rel._tvar(x, _MC), rel._tvar(x, _EN)]

    def mc_sources(s, rel):
        rel._tsource(x, _SD, guard(rel))
        rel._tsource(x, _EN, guard(rel))
        return rel._tvar(x, _MC)

    def mc_one_source(s, rel):
        rel._tsource(x, _EN, guard(rel))
        return rel._tvar(x, _MC)
    for name, body in (('before', mc_before), ('after', mc_after), ('between', mc_between), ('sources', mc_sources),
                       ('one-source', mc_one_source)):
        case('tvar-mc-' + name, body)

    # `_share_guard`.
    def share_guard(s, rel):
        rel._tsource(x, _IL, guard(rel))
        rel._tsource(x, _IE, guard(rel))
        a = rel._share_guard(x)
        return [a, rel._share_guard(x), rel._share_guard(y), type(a).__name__]
    case('share-guard', share_guard)

    # `_congruent`, each exit.
    class Ad:
        def __init__(self, known):
            self.known = known

        def term_of(self, e):
            return 1 if self.known else None

    fx, fy, fz = f(x), f(y), f(z)

    def congruent(node, others, sides=(), cands=(), known=True, num=False):
        def body(s, rel):
            rel._xadapter = Ad(known)
            if others is not None:
                rel._xheads[(node.func, len(node.args))] = list(others)
            rel._xside.update({a: 2 for a in sides})
            rel._xcand.update(cands)
            if num:
                rel.num_sel[node] = 1
            return rel._congruent(node)
        return body
    for name, want, *a in (
            ('no-head', False, fx, None),
            ('one-term', False, fx, [fx], [x, y]),
            ('not-read', False, fx, [fx, fy], [x, y], (), False),
            ('not-read-number', True, fx, [fx, fy], [x, y], (), False, True),
            ('merge-sides', True, fx, [fx, fy], [x, y]),
            ('merge-cands', True, fx, [fx, fy], (), [x, y]),
            ('merge-one-each', True, fx, [fx, fy], [x], [y]),
            ('one-side-missing', False, fx, [fx, fy], [x]),
            ('other-side-missing', False, fx, [fx, fy], [y]),
            ('later-other', True, fx, [fx, fz, fy], [x, y]),
            ('only-itself', False, fx, [fx, f(x)], [x, y]),
            ('two-rationals', False, f(half), [f(half), f(S(2))], [half, S(2)]),
            ('rational-and-float', True, f(half), [f(half), f(half_f)], [half, half_f]),
            ('two-args-same', True, h(x, z), [h(x, z), h(y, z)], [x, y]),
            ('two-args-broken', False, h(x, z), [h(x, z), h(y, x)], [x, y]),
            ('two-args-rationals', False, h(x, half), [h(x, half), h(y, S(2))], [x, y, half, S(2)])):
        case('congruent-' + name, congruent(*a), want=want)

    # `_congruence_pairs`: a pair done, one to look at again, two rationals, and no second emit.
    def pairs(group_of, first=(), then=()):
        def body(s, rel):
            for g in group_of:
                rel._xheads[(g[0].func, len(g[0].args))] = list(g)
            rel._xside.update({a: 2 for a in first})
            rel._congruence_pairs()
            one = len(rel._xpairs)
            rel._xcand.update(then)
            rel._congruence_pairs()
            rel._congruence_pairs()
            return [one, len(rel._xpairs)]
        return body
    for name, want, *a in (
            ('merge', [1, 1], [[fx, fy]], [x, y]),
            ('not-yet', [0, 1], [[fx, fy]], [x], [y]),
            ('never', [0, 0], [[fx, fy]], [x]),
            ('rationals', [1, 1], [[f(half), f(S(2))]], [half, S(2)]),
            ('three', [3, 3], [[fx, fy, fz]], [x, y, z]),
            ('two-groups', [2, 2], [[fx, fy], [h(x, z), h(y, z)]], [x, y]),
            ('one-term', [0, 0], [[fx]], [x]),
            ('same-args', [0, 0], [[fx, f(x)]], [x]),
            ('two-args', [1, 1], [[h(x, y), h(y, x)]], [x, y])):
        case('pairs-' + name, pairs(*a), want=want)

    # `_engage_transfer`.
    def engage_off(s, rel):
        s.engine.transfer = False
        return rel._engage_transfer()

    def engage_no_adapter(s, rel):
        rel.specs = [sp for sp in rel.specs if sp.guarded]
        return rel._engage_transfer()

    def engage_on(s, rel):
        s.engine.transfer = True
        return rel._engage_transfer()
    case('engage-off', engage_off)
    case('engage-no-adapter', engage_no_adapter)
    case('engage-on', engage_on)

    # `_transfer_terms`, `sync_transfer`, `_xswitch` over a real engaged session, the theory's calls recorded.
    def engaged(s, rel, log):
        s.engine.transfer = True
        rel._engage_transfer()
        th = rel.xfer
        if th is None:
            raise AssertionError('not engaged')
        fixed, switch = th.set_fixed, th.switch

        def rec_fixed(t, facts):
            log.append(['fixed', t, repr(facts)])
            return fixed(t, facts)

        def rec_switch(t, a, b):
            got = switch(t, a, b)
            log.append(['switch', t, a, b, list(got)])
            return got
        th.set_fixed, th.switch = rec_fixed, rec_switch
        return rel._xadapter

    def side(rel, e, lv):
        rel._xside[e] = lv
        rel._xsides_n += 1

    def scenario(name, steps, want=...):
        s, rel, log = fresh(Q.eq(x, y))
        try:
            ad = engaged(s, rel, log)
            got = []
            for step in steps:
                got.append(step(s, rel, ad))
            res = got
        except Exception as err:
            res = 'raised ' + type(err).__name__ + ': ' + str(err)[:200]
        finally:
            done()
        out[name] = dict(log=log, returned=repr(res), state=_rel_state(rel))
        if want is not ...:
            out[name]['want'] = repr(want)

    def tt(s, rel, ad):
        return rel._transfer_terms()

    def sync(s, rel, ad):
        return rel.sync_transfer()

    def terms(*es):
        def step(s, rel, ad):
            for e_ in es:
                ad.term(e_)
        return step

    def sides(lv, *es):
        def step(s, rel, ad):
            for e_ in es:
                side(rel, e_, lv)
        return step

    def extra(*es):
        def step(s, rel, ad):
            rel._xextra.extend(es)
        return step

    def visit(*es):
        def step(s, rel, ad):
            for e_ in es:
                s.ensure(e_)
        return step

    scenario('terms-nothing', [tt, tt], want=[False, False])
    scenario('terms-side-symbol', [sides(2, x), tt, tt], want=[None, True, False])
    scenario('terms-side-rational-no-term', [sides(2, half), tt], want=[None, False])
    scenario('terms-side-rational-term', [terms(half), sides(2, half), tt])
    scenario('terms-side-visited', [visit(x), sides(2, x), tt])
    scenario('terms-one-head', [terms(fx), tt])
    scenario('terms-two-heads', [terms(fx, fy), tt, tt])
    scenario('terms-grown-later', [terms(fx), tt, terms(fy), tt, terms(fz), tt])
    scenario('terms-extra', [terms(fx), extra(fy), tt, tt])
    scenario('terms-not-structural', [terms(x, y, z), tt])
    scenario('terms-counted-once', [terms(fx), extra(fx, fx), tt])
    scenario('sync-nothing', [sync, sync])
    scenario('sync-side', [visit(x), sides(2, x), sync, sync])
    scenario('sync-side-link-then-full', [visit(x), sides(1, x), sync, sides(2, x), sync])
    scenario('sync-link-only', [visit(x), sides(1, x), sync, sync])
    scenario('sync-rational', [terms(half), sides(2, half), tt, visit(half), sync])
    scenario('sync-integer', [visit(S(2)), sides(2, S(2)), sync])
    scenario('sync-rational-part', [visit(S(2)), sides(1, S(2)), sync, sides(2, S(2)), sync])
    scenario('sync-nan', [visit(f(nan)), sides(2, f(nan)), sync])
    scenario('sync-congruent', [terms(fx, fy), sides(2, x, y), tt, sync, sync])
    scenario('sync-congruent-later', [terms(fx, fy), tt, sync, sides(2, x, y), sync])
    scenario('sync-congruent-chain', [terms(fx, fy, f(fx), f(fy)), sides(2, x, y), tt, sync, sync])
    scenario('sync-not-congruent', [terms(fx, fz), sides(2, x), tt, sync])
    scenario('sync-pi', [visit(S.Pi), sides(2, S.Pi), sync])


def _share():
    """`tests/test_relations.py::test_equality_sharing_is_needed_and_works`'s query. It patches `Relations._trichotomy` to turn the
    clause off; `rel_interpret` calls Rust's directly, so under Rust that patch reaches nothing."""
    sys.path.insert(0, os.path.join(HERE, '..', '..', 'tests'))
    mod = _rust() if os.environ.get('MODE', 'rust') == 'rust' else None
    from sympy import Q
    from satassume.relations import Relations
    from test_relations import ask_with, dummy_specs, f, relation_engine, x, y
    prop, assum = Q.eq(f(x), f(y)), (x <= y) & (y <= x)
    patch = os.environ.get('PATCH')
    if patch == 'first':
        Relations._trichotomy = lambda self, var, atom: None
    on = ask_with(relation_engine(dummy_specs()), prop, assum)
    Relations._share = lambda self: False
    if patch == 'after':
        Relations._trichotomy = lambda self, var, atom: None
    off = ask_with(relation_engine(dummy_specs()), prop, assum)
    return dict(on=repr(on), off=repr(off), fired=mod.counts()['rel:plant_fired'] if mod else 0)


def _sharing():
    """The replacement for `tests/test_relations.py::test_equality_sharing_is_needed_and_works` (ruled 8 Nov, report 609714d). That
    test turns the clause off by patching `Relations._share` and `_trichotomy`, which Rust's calls go past; here only the way it is
    turned off changes: `skip-share` on Rust, the same patches on Python. Its two assertions stay (`on`, `off`, dummy specs). The
    real-specs case (OrderAdapter + EUFAdapter) is the one where sharing is the only route: with `_trichotomy` off the query is
    still True, and None once sharing is off too. BREAK=share removes sharing from the start (Rust: `drop-share-tri`, the pairs
    counted and no interface atom, with `_trichotomy` off; Python: `_share` patched), and `tri_off` must then move."""
    sys.path.insert(0, os.path.join(HERE, '..', '..', 'tests'))
    rust = os.environ.get('MODE', 'rust') == 'rust'
    mod = _rust() if rust else None
    from sympy import Q
    from satassume.relations import AdapterSpec, Relations
    from satassume.theories.euf.euf_adapter import EUFAdapter
    from test_relations import ask_with, dummy_specs, f, relation_engine, x, y
    from theory_harness import OrderAdapter
    plant = __import__('sa_solver').rel_plant if rust and os.environ.get('SLICE_REL') != 'py' else None
    share, tri = Relations._share, Relations._trichotomy
    brk = os.environ.get('BREAK') == 'share'

    def off(share_off, tri_off, plant_name):
        if plant:
            plant(plant_name)
        else:
            Relations._share = (lambda self: False) if share_off else share
            Relations._trichotomy = (lambda self, var, atom: None) if tri_off else tri

    def real():
        return [AdapterSpec('order', OrderAdapter, True), AdapterSpec('euf', EUFAdapter, False)]
    prop, assum = Q.eq(f(x), f(y)), (x <= y) & (y <= x)
    out = {}
    out['on'] = repr(ask_with(relation_engine(dummy_specs()), prop, assum))
    off(True, True, 'skip-share')
    out['off'] = repr(ask_with(relation_engine(dummy_specs()), prop, assum))
    off(brk, True, 'drop-share-tri' if brk else 'skip-trichotomy')
    out['tri_off'] = repr(ask_with(relation_engine(real()), prop, assum))
    off(True, True, 'skip-share')
    out['both_off'] = repr(ask_with(relation_engine(real()), prop, assum))
    off(False, False, None)
    out['fired'] = mod.counts()['rel:plant_fired'] if mod else 0
    return out


def _join():
    """A query's input term and the same text under another `Function('f')`, each visited first in turn."""
    from sympy import Function, Q, Symbol
    from sympy.core.cache import clear_cache
    import sa_solver
    from satassume.engine import Engine, Session
    mod = _rust()
    import term_live
    x = Symbol('x')
    held = Function('f')(x)
    clear_cache()
    other = Function('f')(x)
    assert held == other and type(held) is not type(other)
    out = {}
    for order, first in (('held-first', held), ('other-first', other)):
        eng = Engine()
        s = Session(eng)
        q = term_live._convert(Q.positive(held), True, eng)
        assert q.kept is None and q.ids.get(held) is not None
        term_live.stack().append(q)
        try:
            core = s.table.core
            before = mod.counts()
            none_yet = sa_solver.rel_link_probe(core, held)
            n_before = len(s.table)
            after_no_node = mod.counts()
            s.var('positive', first)
            s.var('negative', other if first is held else held)
            joins = mod.counts()['join']
            ids = [sa_solver.rel_link_probe(core, o) for o in (held, other, held, held, other)]
            end = mod.counts()
            out[order] = dict(
                none_yet=none_yet == q.ids[held], ids=ids, want=q.ids[held], no_new_node=n_before == 0,
                no_node=after_no_node['link:no_node'] - before['link:no_node'],
                join_quiet=end['join'] == joins, hit=end['link:hit'] - before['link:hit'],
                second=end['link:second'] - before['link:second'], none=end['link:none'] - before['link:none'])
        finally:
            term_live.stack().pop()
    # Numbering: a resolve before the first var leaves the same numbers as none.
    numbers = []
    for probe in (False, True):
        eng = Engine()
        s = Session(eng)
        q = term_live._convert(Q.positive(held), True, eng)
        term_live.stack().append(q)
        try:
            if probe:
                sa_solver.rel_link_probe(s.table.core, held)
            numbers.append((s.var('positive', x), s.var('positive', held), s.var('real', other)))
        finally:
            term_live.stack().pop()
    out['numbers'] = numbers
    # Outside any query, and in a kept one.
    s = Session(Engine())
    before = mod.counts()['link:no_table']
    out['no_table'] = [sa_solver.rel_link_probe(s.table.core, held), mod.counts()['link:no_table'] - before]
    return out


def _call(what, **env):
    e = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE] + os.environ.get('PYTHONPATH', '').split(os.pathsep)), **env)
    r = subprocess.run([sys.executable, __file__, what], env=e, capture_output=True, text=True, cwd=HERE)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.splitlines()[-1])


@pytest.fixture(scope='module')
def py():
    return _call('run', MODE='py')


@pytest.fixture(scope='module')
def rust():
    return _call('run')


@pytest.fixture(scope='module')
def py_direct():
    return _call('direct', MODE='py')


@pytest.fixture(scope='module')
def rust_direct():
    return _call('direct')


def _differ(a, b):
    return sorted(k for k in a['cases'] if a['cases'][k] != b['cases'][k])


def test_methods_match_python(py, rust):
    assert _differ(py, rust) == []


def test_same_core_python_methods_match(py):
    assert _differ(py, _call('run', SLICE_REL='py')) == []


def test_undecided_return_was_reached(rust):
    assert rust['cases']['infinite-undecided']['asked'] is True


def test_direct_matches_python(py_direct, rust_direct):
    assert _differ(py_direct, rust_direct) == []


def test_direct_reaches_bound_and_every_infinity_path(py_direct, rust_direct):
    """So the MATCH above covers what it's for, on Python's side and Rust's."""
    for run in (py_direct, rust_direct):
        cases = run['cases']
        for name, case in cases.items():
            kinds = {step[0] for step in case['log']}
            if case.get('path') == 'symbolic':
                assert 'is_' not in kinds and 'ensure' in kinds and 'clause' in kinds, name
            elif case.get('path') == 'decided':
                assert 'is_' in kinds and 'ensure' not in kinds and [s for s in case['log'] if s[0] == 'clause'] == [
                    ['clause', [case['var'] if 'true' in name else -case['var']]]], name
            elif case.get('path') == 'undecided':
                assert 'is_' in kinds and 'ensure' in kinds and 'clause' in kinds, name
            elif case.get('path') == 'none':
                assert case['log'] == [], name
        # `_bound`'s root facts, once per constant, the memo's list kept.
        for name in ('guard-real-at-root', 'guard-forced-unknown', 'guard-forced-true', 'bound-pi', 'bound-sqrt'):
            facts = [s for s in cases[name]['log'] if s[0] == 'clause']
            assert len(facts) >= 2 and all(len(s[1]) == 1 for s in facts[:2]), name
        # Three `_guard` calls, one `_bound`: two root facts, and the rest is `ensure(x, real)`'s, none of them a unit.
        assert sum(s[0] == 'clause' and len(s[1]) == 1 for s in cases['guard-real-at-root']['log']) == 2
        assert cases['guard-real-at-root']['guard'] == [] and cases['guard-real-at-root']['same'] is True
        assert cases['guard-forced-unknown']['guard'] != []
        assert cases['bound-symbol']['log'] == [] and cases['guard-no-attr']['log'] == cases['guard-none-attr']['log']
    assert rust_direct['counts']['rel:bound'] > 0 and rust_direct['counts']['rel:eq_infinity'] > 0


@pytest.mark.parametrize('plant', ['drop-bound', 'drop-guard', 'drop-eq-infinity', 'drop-add-role', 'drop-apply-role', 'drop-candidacy',
                                   'drop-tsource', 'drop-tvar', 'drop-tvar-mc', 'drop-engage', 'drop-terms', 'drop-terms-side', 'drop-fixed',
                                   'drop-sync', 'drop-sync-polar', 'drop-xswitch', 'drop-congruence', 'congruent-never', 'share-guard-one'])
def test_direct_sees_its_plants(py_direct, plant):
    got = _call('direct', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py_direct, got) != []


def test_each_method_ran(rust):
    c = rust['counts']
    for k in ('closed_extended_real', 'order_sides', 'order_infinite', 'trichotomy', 'mention_number', 'link_integer',
              'fresh', 'interpret', 'guard', 'link', 'selectors_of', 'eq_infinity', 'add_role', 'apply_role', 'tsource', 'tvar',
              'share_guard', 'congruent', 'engage_transfer', 'transfer_terms', 'sync_transfer', 'xswitch', 'congruence_pairs'):
        assert c['rel:' + k] > 0, k
    # Not `bound`: no query here reaches it, on Python's own `_bound` either. `_direct` calls it.
    assert c['rel:var'] > 0 and c['link:resolved'] > 0 and c['link:hit'] > 0 and c['link:no_node'] > 0


def test_c2c_answers_are_the_ones_written_down(py_direct, rust_direct):
    """Python against Rust can't see both taking the wrong exit, so the methods that answer are held to a written answer."""
    for run in (py_direct, rust_direct):
        wanted = {k: c for k, c in run['cases'].items() if 'want' in c}
        assert len(wanted) >= 27
        for name, c in wanted.items():
            assert c['returned'] == c['want'], name


def test_c2c_direct_reaches_what_it_says(py_direct, rust_direct):
    for run in (py_direct, rust_direct):
        c = run['cases']
        kinds = lambda name: {s[0] for s in c[name]['log']}
        assert c['role-repeat']['state']['roles'][0][1] == [['user', c['role-repeat']['state']['roles'][0][1][0][1]]]
        assert c['tsource-equal-guard']['state']['tsrc'][0][2] == [c['tsource-equal-guard']['state']['tsrc'][0][2][0]] * 2
        assert len(c['tsource-same-guard']['state']['tsrc'][0][2]) == 1
        assert c['engage-off']['state']['xfer'] is False and c['engage-no-adapter']['state']['xfer'] is False
        assert c['engage-on']['state']['xfer'] is True and c['engage-on']['state']['engaged'] is True
        assert kinds('engage-on') == {'atom'} and 'enable' in c['engage-on']['log'][0][2]
        # A candidate takes all 14 predicates, a link-only side `polar`, a rational what its facts leave.
        assert sum(s[0] == 'atom' and s[2].endswith('False)') for s in c['sync-side']['log']) == 14
        assert sum(s[0] == 'atom' and s[2].endswith('False)') for s in c['sync-link-only']['log']) == 1
        assert 'switch' in kinds('sync-side') and 'switch' not in kinds('sync-integer') and 'atom' in kinds('sync-integer')
        assert 'fixed' in kinds('terms-side-rational-term') and 'fixed' not in kinds('terms-side-rational-no-term')
        assert c['sync-nan']['state']['pend'] == [] and c['sync-nan']['state']['cand'] == []
        assert 'ensure' in kinds('terms-two-heads') and 'ensure' not in kinds('terms-one-head')
        assert sorted(c['sync-congruent']['state']['cand']) == ['f(x)', 'f(y)', 'x', 'y']
        assert c['sync-not-congruent']['state']['cand'] == ['x']


def test_rust_kinds_are_pythons():
    """`relations_core.rs` hardcodes `_SD` and the others."""
    assert _call('kinds') == dict(rust=[0, 1, 2, 3, 4], py=[0, 1, 2, 3, 4])


def test_link_none_moves_nothing(py):
    """The ruling: the link doesn't depend on any row being there."""
    got = _call('run', SLICE_SESSION_PLANT='link-none')
    assert got['counts']['rel:plant_fired'] > 0 and got['counts']['link:resolved'] == 0
    assert _differ(py, got) == []


@pytest.mark.parametrize('plant', ['drop-order-sides', 'drop-order-infinite', 'drop-trichotomy', 'drop-interpret', 'drop-guard',
                                   'drop-link', 'drop-selector', 'drop-eq-infinity', 'fresh-skew', 'drop-add-role', 'drop-apply-role',
                                   'drop-candidacy', 'drop-tsource', 'drop-tvar', 'drop-tvar-mc', 'drop-engage', 'drop-terms', 'drop-terms-side',
                                   'drop-fixed', 'drop-sync', 'drop-sync-polar', 'drop-xswitch', 'drop-congruence', 'congruent-never',
                                   'share-guard-one',
                                   # Step 5c4's bar plants, one in each moved method.
                                   'drop-init-engage', 'drop-enqueue', 'drop-note-top', 'drop-proc-eq-links', 'drop-link-later',
                                   'wants-never', 'drop-share'])
def test_dropped_clause_is_seen(py, plant):
    got = _call('run', SLICE_SESSION_PLANT=plant)
    assert got['counts']['rel:plant_fired'] > 0
    assert _differ(py, got) != []


def test_fresh_not_inert_fires():
    """The clause stream can't see `set_inert`, so this plant only shows it fires here. Its comparison is the fresh digests."""
    assert _call('run', SLICE_SESSION_PLANT='fresh-not-inert')['counts']['rel:plant_fired'] > 0


def test_a_patch_on_a_moved_method_reaches_nothing():
    """Why that suite test fails under Rust: the patch, and not the query. Turn the method off in Rust and it answers as Python's does with the patch in place from the start."""
    want = dict(on='True', off='None', fired=0)
    assert _call('share', MODE='py', PATCH='after') == want
    assert _call('share', SLICE_REL='py', PATCH='after') == want
    # Rust's calls go past the patch. If this starts answering None, the suite test passes again: drop its name from the report.
    assert _call('share', PATCH='after') == dict(on='True', off='True', fired=0)
    # With the method really off, from the start, Rust answers as Python does.
    assert _call('share', MODE='py', PATCH='first') == dict(on='None', off='None', fired=0)
    got = _call('share', SLICE_SESSION_PLANT='skip-trichotomy')
    assert got['fired'] > 0 and (got['on'], got['off']) == ('None', 'None')


def test_sharing_is_needed_and_works():
    """`test_equality_sharing_is_needed_and_works`, re-pointed: its two assertions with the clause off by `skip-share`, and the
    real-specs case where sharing is the only route. Same answers on Python, on Rust and on Rust's core with Python's methods."""
    want = dict(on='True', off='None', tri_off='True', both_off='None')
    assert {k: v for k, v in _call('sharing', MODE='py').items() if k != 'fired'} == want
    got = _call('sharing')
    assert got['fired'] > 0 and {k: v for k, v in got.items() if k != 'fired'} == want
    assert {k: v for k, v in _call('sharing', SLICE_REL='py').items() if k != 'fired'} == want


def test_sharing_case_fails_without_sharing():
    """With sharing removed from the start, the real-specs case moves: the test above fails on both backends."""
    assert _call('sharing', MODE='py', BREAK='share')['tri_off'] == 'None'
    got = _call('sharing', BREAK='share')
    assert got['fired'] > 0 and got['tri_off'] == 'None'


def test_link_crossings_add_up(rust):
    """Each kind of crossing the report quotes, against the calls that make it."""
    c = rust['counts']
    assert c['link:calls'] == c['link:cross_current'] > 0
    assert c['link:cross_hash'] == c['link:calls'] - c['link:no_table']
    assert c['link:cross_term_id'] == c['link:cross_hash'] - c['link:hit']


def test_join_second_object_resolves_on_its_own():
    got = _call('join')
    for order in ('held-first', 'other-first'):
        o = got[order]
        # The term's own object has its id, the other class none, in either order and past memo hits.
        assert o['ids'] == [o['want'], None, o['want'], o['want'], None], (order, o)
        assert o['none_yet'] and o['no_new_node'] and o['no_node'] == 1 and o['join_quiet'], (order, o)
        assert o['hit'] >= 2 and o['second'] == 2 and o['none'] == 2, (order, o)
    a, b = got['numbers']
    assert a == b


def test_link_outside_a_query_is_none():
    got = _call('join')
    assert got['no_table'] == [None, 1]


def _kinds():
    _rust()
    import sa_solver
    from satassume import relations as r
    return dict(rust=list(sa_solver.REL_KINDS), py=[r._SD, r._EN, r._MC, r._IE, r._IL])


if __name__ == '__main__':
    print(json.dumps({'run': _run, 'join': _join, 'direct': _direct, 'share': _share, 'sharing': _sharing, 'kinds': _kinds}[sys.argv[1]]()))
