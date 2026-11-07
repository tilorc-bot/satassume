"""split78.py WL MODE [--fine]: one cold pass with exclusive timers. Prints one JSON line. Not for speed: see the overhead row.

MODE rust: what `live.py --check plain` installs. MODE term-py: the same with SLICE_TERM=py, so the Python functions at the sites
term_live replaces are timed under the same wrappers. Lives outside the repo logic; touches no source.

Timers are exclusive: a stack, so a timed region inside another is charged only to itself.
Coarse regions: the pieces of convert, TermTable(), each read by kind, each consumer term_live and lra_live install, `_ask`'s
own work, the journal. --fine adds a timed copy of term_row, one perf_counter pair per fact, per term.
"""
import gc, hashlib, json, os, sys, time
wl, mode = sys.argv[1:3]
fine = '--fine' in sys.argv
S = os.environ["SLICE_DIR"]
sys.path.insert(0, S)
if mode == 'term-py':
    os.environ['SLICE_TERM'] = 'py'
import p_install
p_install.install()
from evalbench.common import workload
from satassume import sympy_api, engine, relations, scope
from satassume.theories.euf import euf_adapter
from satassume.theories.lra import lra_adapter
import backend, sa_solver
backend.install_euf()
import term_live, convert, lra_live
term_live.from_env()
lra_live.from_env()
backend.install()
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
pc = time.perf_counter
T, N = {}, {}
st = [[None, 0.0]]      # (name, child time)


def wrap(name, f):
    if getattr(f, '__split78__', False):
        return f

    def g(*a, **k):
        fr = [name, 0.0]
        st.append(fr)
        t = pc()
        try:
            return f(*a, **k)
        finally:
            d = pc() - t
            st.pop()
            T[name] = T.get(name, 0.0) + d - fr[1]
            N[name] = N.get(name, 0) + 1
            st[-1][1] += d
    g.__split78__ = True
    g.__wrapped__ = f
    return g


def patch(obj, attr, name):
    if hasattr(obj, attr):
        setattr(obj, attr, wrap(name, getattr(obj, attr)))


# Sites: each name is patched once per module holding it, sharing one timer, so a call from any of them lands on the same row.
def site(name, *holders):
    if not holders:
        return
    f0 = getattr(holders[0], name, None)
    if f0 is None:
        return
    w = wrap('site:' + name, f0)
    for h in holders:
        if getattr(h, name, None) is f0:
            setattr(h, name, w)


R, En, Sc, Eu, L = relations, engine, scope, euf_adapter, lra_adapter
site('relation_atom', R, sympy_api)
site('_termwise', R)
site('glue_objects', R, En)
site('_ext_atoms', R)
site('_is_number', R, En, Sc)
site('affine_pair', Sc, En)
site('linked_terms', Sc)
site('_under_apps', R)
site('zero_twin', R, En)
site('structural', Eu)
site('_structural_subterms', R)
site('_key', R)
site('default_sort_key', L)
for n in ('interpret', 'order_sides', 'integer_form', 'closed_sign', '_memoized'):
    site(n, L)
patch(R.Relations, '_eq_links', 'site:_eq_links')
patch(R.Relations, '_eq_infinity', 'site:_eq_infinity')
patch(Eu.EUFAdapter, 'interned', 'site:interned')
if term_live.installed():
    term_live.convert = convert
    patch(convert, 'convert', 'conv:other')
    patch(convert, 'formula', 'conv:formula')
    patch(convert, 'default_engine_settings', 'conv:settings')
    W = convert._Walk
    patch(W, 'walk', 'conv:walk')
    patch(W, 'power_rows', 'conv:power_rows')
    patch(W, 'read', 'read')
    real_klass = W.klass

    def klass(self, cls, _k=wrap('conv:klass-miss', real_klass)):
        c = self.classes.get(cls)
        return c if c is not None else _k(self, cls)
    W.klass = klass
    W.enc_top = None
    if fine:
        from sympy import S as SS
        from sympy.core.function import AppliedUndef
        from sympy.core.numbers import Float
        from sympy.core.basic import Basic
        from satassume.knowledge.domain import constructed_noncommutative as cnc
        from satassume.knowledge.templates import _may_be_nan
        from satassume.theories.lra.lra_adapter import _BAD
        C = convert

        def add(n, d):
            T[n] = T.get(n, 0.0) + d
            N[n] = N.get(n, 0) + 1

        def term_row(self, t, out):
            # The same statements as convert._Walk.term_row at d29e94b, a pair of clocks around each.
            fr = ['conv:row-frame', 0.0]
            st.append(fr)
            t0 = pc()
            a = pc()
            out += (C.T_TUPLE, 6, C.T_INT, self.classes[type(t)], C.T_TUPLE, len(t.args))
            ids = self.ids
            for x in t.args:
                out += (C.T_TERM, ids[x])
            b = pc(); add('row:args', b - a); a = pc()
            if type(t)._hashable_content is Basic._hashable_content:
                out.append(C.T_NONE)
            else:
                self.enc(tuple(t._hashable_content()), out)
            b = pc(); add('row:content', b - a)
            if isinstance(t, C._SKELETON):
                out += (C.T_NONE, C.T_INT, 0, C.T_INT, 0)
            else:
                if t is SS.NaN:
                    self.term(SS.NegativeInfinity)
                a = pc()
                free = t.free_symbols
                b = pc(); add('row:free_symbols', b - a); a = pc()
                fid = sorted(self.term(x) for x in free)
                out += (C.T_TUPLE, len(fid))
                for i in fid:
                    out += (C.T_TERM, i)
                b = pc(); add('row:free-enc', b - a); a = pc()
                number = getattr(t, 'is_number', False) is True
                b = pc(); add('row:is_number', b - a); a = pc()
                bits = C.F_READ
                if number:
                    bits |= C.F_NUMBER
                if t.has(SS.NaN):
                    bits |= C.F_NAN
                b = pc(); add('row:has-nan', b - a); a = pc()
                if t.has(*_BAD):
                    bits |= C.F_BAD
                b = pc(); add('row:has-bad', b - a); a = pc()
                if t.has(Float):
                    bits |= C.F_FLOAT
                b = pc(); add('row:has-float', b - a); a = pc()
                if t.atoms(AppliedUndef):
                    bits |= C.F_UNDEF
                b = pc(); add('row:atoms-undef', b - a); a = pc()
                if _may_be_nan(t):
                    bits |= C.F_MAYBE_NAN
                b = pc(); add('row:may_be_nan', b - a); a = pc()
                nc = cnc(t)
                out += (C.T_INT, bits, C.T_INT, nc)
                b = pc(); add('row:noncomm', b - a)
            d = pc() - t0
            st.pop()
            st[-1][1] += d
            T['conv:term_row-total'] = T.get('conv:term_row-total', 0.0) + d - fr[1]
            N['conv:term_row-total'] = N.get('conv:term_row-total', 0) + 1
        W.term_row = term_row
    else:
        patch(W, 'term_row', 'conv:term_row-total')
    # TermTable() is the Rust parse of the tokens.
    real_tt = sa_solver.TermTable
    real_conv = term_live._convert
    term_live._convert = wrap('live:_convert-own', real_conv)
    patch(term_live, '_note_query', 'live:_note_query')
    patch(term_live._Mark, '__init__', 'live:mark')
    patch(term_live._Mark, 'add', 'live:mark')
    engine.DictCache.put = wrap('live:journaled_put', engine.DictCache.put)

    class TT:
        def __new__(cls, tables, _w=wrap('table:TermTable()', real_tt)):
            return _w(tables)
    term_live.sa_solver = type('M', (), {k: getattr(sa_solver, k) for k in dir(sa_solver) if not k.startswith('__')} | {'TermTable': TT})
real_ask = sympy_api._ask
sympy_api._ask = wrap('ask:outer(incl. engine, solver, theories)', real_ask)
ask = sympy_api.ask
per = 0.0
ans = [None] * len(pairs)
gc.collect()
gc.freeze()
t0 = pc()
for i, (p, a) in enumerate(pairs):
    try:
        r = ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
    ans[i] = r
total = pc() - t0
d = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]
row = dict(wl=wl, mode=mode, fine=fine, digest=d, s=total, n=len(pairs), T=T, N=N, term=term_live.counts(),
           refusals=len(term_live.REFUSALS))
print(json.dumps(row))
