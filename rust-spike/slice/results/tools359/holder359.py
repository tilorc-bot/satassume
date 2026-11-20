import gc, os, sys, weakref
S = os.environ["SLICE_DIR"]; sys.path.insert(0, S)
import p_install; p_install.install()
from satassume import sympy_api
import sa_solver, backend
backend.install_euf()
import term_live; term_live.from_env()
import lra_live; lra_live.from_env()
import session_live; session_live.from_env()
import knowledge_live; knowledge_live.from_env()
backend.install()
import convert, live
pairs = live.load("cls")
seen = []; real = convert.convert
def convert_(*a, **k):
    r = real(*a, **k); seen.append(r); return r
if len(sys.argv) > 1: convert.convert = convert_
made = []
if len(sys.argv) <= 1:      # no wrapper of convert: find the walkers by type afterwards
    pass
last = None
for i, (p, a) in enumerate(pairs[:40]):
    try: sympy_api.ask(p, a)
    except Exception as e: pass
    for r in seen:
        if not isinstance(r, convert.Kept):
            last = weakref.ref(r.tables['reads'].__self__)
    r = None
    del seen[:]
gc.collect()
import collections
c = collections.Counter(type(o).__name__ for o in gc.get_objects())
print({k: v for k, v in c.items() if any(n in k for n in ('Walk', 'TermTable', '_Query', 'Converted', 'Relations', 'Session', 'Hand', '_Refused', 'Dispatch'))})
def show(tn, depth=3):
    objs = [x for x in gc.get_objects() if type(x).__name__ == tn]
    ignore = {id(objs)}
    fr = objs[:1]
    for d in range(depth):
        nx = []
        for x in fr:
            rs = gc.get_referrers(x); ignore.add(id(rs))
            for y in rs:
                if id(y) in ignore or type(y).__name__ in ('frame',) or y is globals(): continue
                ignore.add(id(y))
                extra = ''
                if isinstance(y, dict):
                    ow = gc.get_referrers(y); ignore.add(id(ow))
                    extra = ' key ' + str([k for k, v in y.items() if v is x][:2]) + ' owners ' + str([type(z).__name__ + ':' + str(getattr(z, '__name__', ''))[:40] for z in ow if type(z).__name__ != 'frame'][:3])
                print(tn, '  ' * d, type(y).__module__ + '.' + type(y).__name__, repr(y)[:80], extra)
                if not isinstance(y, (type, type(sys))): nx.append(y)
        fr = nx[:3]
for tn in ('_Query', 'TermTable', 'Converted'):
    show(tn)
