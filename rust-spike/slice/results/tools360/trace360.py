"""The differential's one DIFF (359's job, suite input Q.commutative(Trace(M*N)), True): each walker's reads, one by
one, in a child with a timeout. argv: py|rust [handler]"""
import os, sys, time, faulthandler
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
import convert
from sympy import MatrixSymbol, Trace, Q, S as SS
M = MatrixSymbol('M', 2, 2); N = MatrixSymbol('N', 2, 2)
p, a = Q.commutative(Trace(M*N)), SS.true
which = sys.argv[1]
got = []
real = convert.convert
def conv(pp, aa, eng):
    w = None if which == 'py' else convert.rust_walk(convert.RUST_ITEMS)
    was = convert.WALK[0]; convert.WALK[0] = w
    try: r = real(pp, aa, eng)
    finally: convert.WALK[0] = was
    got.append(r); return r
convert.convert = conv
print('answer', sympy_api.ask(p, a), flush=True)
c = got[0]
print(type(c).__name__, 'objects', [repr(o)[:40] for o in c.objects], flush=True)
ask = c.tables['reads']; n = len(c.objects)
faulthandler.dump_traceback_later(20, exit=True)
for kind in range(len(convert.READS)):
    for i in range(n):
        t = time.time()
        v = ask(kind, i)
        dt = time.time() - t
        if dt > 0.5 or (kind, i) == (2, 3): print(convert.READS[kind], i, repr(v)[:60], round(dt, 2), flush=True)
print('end', dict(c.counts), list(c.raised), flush=True)
