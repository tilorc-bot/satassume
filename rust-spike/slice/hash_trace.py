"""hash_trace.py WL [MODE]: sa-port-94's per-site hash count. sa-port-86's qt86.py, kind `count`, rust arm, with one change:
each Rust-to-Python callback is also keyed by the Rust callable on top of the stack and the Python line that called it.

Same install sequence as qt86.py (what `live.py --check plain` installs), so its `rust2py` totals are qt86's numbers.
Added keys:
  site:   "rust callable|caller file:line qualname|caller's caller file qualname|callee" -> count, for callees named *__hash__
  byrust: "rust callable|callee" -> count, for every callback
A count, not a timing: the timer is meaningless under sys.monitoring. No satassume or crate source changes.
MODE: rust (default) or py (no install; site/byrust stay empty).
"""
import collections, gc, hashlib, json, os, sys, time
wl = sys.argv[1]
mode = sys.argv[2] if len(sys.argv) > 2 else "rust"
S = os.environ["SLICE_DIR"]
so = term_live = lra_live = session_live = None
if mode != "py":
    sys.path.insert(0, S)
    import p_install
    p_install.install()
from evalbench.common import workload
from satassume import sympy_api
if mode != "py":
    import backend, sa_solver
    backend.install_euf()
    import term_live
    term_live.from_env()
    import lra_live
    lra_live.from_env()
    import session_live
    session_live.from_env()
    backend.install()
    so = hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest()[:16]
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)

cnt = dict(py2rust=collections.Counter(), rust2py=collections.Counter(), site=collections.Counter(), byrust=collections.Counter())
M = sys.monitoring
TOOL = 3
M.use_tool_id(TOOL, "hash_trace")
E = M.events
classes = {v for v in vars(sa_solver).values() if isinstance(v, type)} if mode != "py" else set()
funcs = {id(v) for v in vars(sa_solver).values() if callable(v) and not isinstance(v, type)} if mode != "py" else set()
tmemo = {}


def rust_type(t):
    r = tmemo.get(t)
    if r is None:
        r = tmemo[t] = next((c.__name__ for c in t.__mro__ if c in classes), "")
    return r


def rust_name(f):
    if isinstance(f, type):
        r = rust_type(f)
        return r + ".__new__" if r else None
    oc = getattr(f, "__objclass__", None)
    if oc is not None:
        r = rust_type(oc)
        return f"{r}.{f.__name__}" if r else None
    if id(f) in funcs:
        return f.__name__
    s = getattr(f, "__self__", None)
    if s is not None:
        r = rust_type(type(s))
        return f"{r}.{getattr(f, '__name__', '?')}" if r else None
    return None


def short(fn):
    for mark, pre in (("/satassume/", ""), ("/slice/", "slice/"), ("/sympy/", "sympy/")):
        i = fn.rfind(mark)
        if i >= 0:
            return pre + fn[i + len(mark):]
    return os.path.basename(fn)


lmemo = {}


def line_of(code, off):
    k = (code, off)
    r = lmemo.get(k)
    if r is None:
        r = 0
        for a, b, ln in code.co_lines():
            if a <= off < b:
                r = ln or 0
                break
        r = lmemo[k] = r
    return r


stack = []
depth = [0]


def on_call(code, off, f, arg0):
    if type(f).__name__ == "function":
        return
    n = rust_name(f)
    if n:
        cnt["py2rust"][n] += 1
        fr = sys._getframe(1)
        up = fr.f_back
        site = f"{short(code.co_filename)}:{line_of(code, off)} {code.co_qualname}"
        parent = f"{short(up.f_code.co_filename)} {up.f_code.co_qualname}" if up is not None else "-"
        stack.append((f, depth[0], n, site, parent))


def on_c_end(code, off, f, arg0):
    if stack and stack[-1][0] is f:
        stack.pop()


def on_start(code, off):
    if stack and stack[-1][1] == depth[0]:
        q = code.co_qualname
        cnt["rust2py"][q] += 1
        top = stack[-1]
        cnt["byrust"][f"{top[2]}|{q}"] += 1
        if q.endswith("__hash__"):
            cnt["site"][f"{top[2]}|{top[3]}|{top[4]}|{q}"] += 1
    depth[0] += 1


def on_end(code, off, arg):
    depth[0] -= 1


def on_resume(code, off):
    depth[0] += 1


R = M.register_callback
R(TOOL, E.CALL, on_call)
R(TOOL, E.C_RETURN, on_c_end)
R(TOOL, E.C_RAISE, on_c_end)
R(TOOL, E.PY_START, on_start)
R(TOOL, E.PY_RESUME, on_resume)
R(TOOL, E.PY_RETURN, on_end)
R(TOOL, E.PY_YIELD, on_end)
R(TOOL, E.PY_UNWIND, on_end)
ev = E.CALL | E.PY_START | E.PY_RESUME | E.PY_RETURN | E.PY_YIELD | E.PY_UNWIND
M.set_events(TOOL, ev)
M.set_events(TOOL, ev | E.C_RETURN | E.C_RAISE)

ans = [None] * len(pairs)
ask = sympy_api.ask
gc.collect()
gc.freeze()
t0 = time.perf_counter()
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
total = time.perf_counter() - t0
M.set_events(TOOL, 0)
d = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]
import satassume
row = dict(wl=wl, mode=mode, kind="hash_trace", digest=d, s=total, so=so, n=len(pairs), satassume=satassume.__file__,
           sa_solver=sa_solver.__file__ if mode != "py" else None)
if session_live is not None:
    row["session"] = session_live.counts()
if term_live is not None:
    row["term"] = term_live.counts()
if lra_live is not None:
    row["lra"] = lra_live.counts()
row.update({k: dict(v.most_common()) for k, v in cnt.items()})
print(json.dumps(row))
