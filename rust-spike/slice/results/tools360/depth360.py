"""The differential's one DIFF under the suite's handler_count plugin (359's job: Q.commutative(Trace(M*N)), True;
Python's child read all, Rust's stopped at `complex 3`). Here: no pytest. Each walker's reads in the differential's
order up to `complex 3`, in a forked child with SECONDS of CPU, called D frames deeper, with and without a
sys.monitoring EXCEPTION_HANDLED tool (what handler_count registers). One row per (tool, walker, D): the read's value
and seconds, or KILLED. argv: DMAX [SECONDS]"""
import os, sys, time, signal, pickle, warnings
warnings.simplefilter('ignore')
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
from sympy import MatrixSymbol, Trace, Q
DMAX = int(sys.argv[1]); SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 10
M = MatrixSymbol('M', 2, 2); N = MatrixSymbol('N', 2, 2)
p = Q.commutative(Trace(M*N))
got = {}
real = convert.convert
which = [None]
def conv(pp, aa, eng):
    for name, w in (('py', None), ('rust', convert.rust_walk(convert.RUST_ITEMS))):
        was = convert.WALK[0]; convert.WALK[0] = w
        try: got[name] = real(pp, aa, eng)
        finally: convert.WALK[0] = was
    return real(pp, aa, eng)
convert.convert = conv
print('answer', sympy_api.ask(p, True), 'limit', sys.getrecursionlimit(), flush=True)
c = got['py']; n = len(c.objects)
print('terms', n, 'term 3', repr(c.objects[3]), type(c.objects[3]).__name__, flush=True)
fired = [0]
def cb(code, offset, exc): fired[0] += 1
def deep(d, fn):
    return fn() if d == 0 else deep(d - 1, fn)
def child(name, d, tool):
    rd, wr = os.pipe(); pid = os.fork()
    if pid == 0:
        try:
            os.close(rd)
            if tool:
                mon = sys.monitoring
                mon.use_tool_id(4, 'depth360'); mon.register_callback(4, mon.events.EXCEPTION_HANDLED, cb); mon.set_events(4, mon.events.EXCEPTION_HANDLED)
            ask = got[name].tables['reads']
            def run():
                out = None
                for kind in range(3):
                    for i in range(n):
                        if kind == 2 and i == 3:
                            signal.setitimer(signal.ITIMER_VIRTUAL, SECONDS)
                            t = time.process_time(); v = ask(kind, i); dt = time.process_time() - t
                            signal.setitimer(signal.ITIMER_VIRTUAL, 0)
                            return (repr(v), round(dt, 3), fired[0], list(got[name].raised)[-1:] )
                        ask(kind, i)
            signal.signal(signal.SIGVTALRM, signal.SIG_DFL)
            r = deep(d, run)
            with os.fdopen(wr, 'wb') as f: pickle.dump(r, f)
        finally:
            os._exit(0)
    os.close(wr)
    with os.fdopen(rd, 'rb') as f: data = f.read()
    os.waitpid(pid, 0)
    return pickle.loads(data) if data else 'KILLED'
for tool in (False, True):
    for d in range(DMAX + 1):
        print('tool' if tool else 'plain', 'D', d, '| py', child('py', d, tool), '| rust', child('rust', d, tool), flush=True)
