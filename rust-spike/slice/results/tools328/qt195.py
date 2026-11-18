"""qt195.py (sa-port-195: qt143.py with the rust-mode install order checked against 9529850's live.py --check plain/entry;
the only change: sa_solver is imported before backend, as live.py does. live.py's catch_count/handler_count/Solver.__init__
counters are instrumentation, not installs, and are left out as in qt143.)
qt143.py (sa-port-143: qt139.py plus KIND=pysample, pysampler.so with Python frames and per-query index; sa-port-86's qt86.py with the changes marked sa-port-139) WL MODE KIND [OUTBASE]: one cold pass, as rust-spike/slice/qtime.py does it, in recorded order, imports before the timer.

MODE: py (no install); rust (what `live.py --check plain` installs: p_install before satassume, then backend.install_euf,
term_live.from_env, lra_live.from_env and backend.install, so solver, EUF, transfer, P, LRA, term ids, slice D); rk (rust plus knowledge_live.install,
which neither live.py nor rust_plugin.py nor backend.py installs).

KIND: time (nothing added: per-query seconds and answers); sample (sampler.c, 0.5 ms, PCs to OUTBASE.bin and OUTBASE.maps,
flag set while term_live._convert runs); count (sys.monitoring: Python to Rust calls by name, Rust to Python callbacks by
name, Python function starts by file. The timer is meaningless there).

Prints one JSON line. Lives outside the repo: no satassume or crate source changes.
"""
import collections, ctypes, gc, hashlib, json, os, sys, time
wl, mode, kind = sys.argv[1:4]
outbase = sys.argv[4] if len(sys.argv) > 4 else None
S = os.environ["SLICE_DIR"]
so = term_live = lra_live = session_live = K = knowledge_live = None
if mode != "py":
    sys.path.insert(0, S)
    import p_install
    p_install.install()
from evalbench.common import workload
from satassume import sympy_api
if mode != "py":
    import sa_solver    # sa-port-195: before backend, as 9529850's live.py does
    import backend
    backend.install_euf()
    import term_live
    term_live.from_env()
    import lra_live     # sa-port-76: live.py --check plain has this since slice D
    lra_live.from_env()
    import session_live     # sa-port-86: live.py --check plain has this since step 5a. SLICE_SESSION=py keeps it off
    session_live.from_env()
    import knowledge_live   # sa-port-139: live.py --check plain has this since component 6. SLICE_KNOWLEDGE=py keeps it off
    knowledge_live.from_env()
    backend.install()
    so = hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest()[:16]
    if mode == "rk":
        import knowledge_live as K
        K.install()
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
pc = time.perf_counter
lib = None
plib = None
if kind == "pysample":     # sa-port-143
    plib = ctypes.PyDLL(os.environ["PYSAMPLER_SO"])
    plib.data.restype = ctypes.c_void_p
    plib.count.restype = ctypes.c_long
    plib.recsize.restype = ctypes.c_long
    plib.start.restype = ctypes.c_long
if kind == "sample":
    lib = ctypes.CDLL(os.environ["SAMPLER_SO"])
    lib.data.restype = ctypes.POINTER(ctypes.c_uint64)
    lib.count.restype = ctypes.c_long
    if term_live is not None:
        real_convert = term_live._convert

        def flagged(*a):
            lib.setflag(1)
            try:
                return real_convert(*a)
            finally:
                lib.setflag(0)
        term_live._convert = flagged
cnt = None
if kind == "count":
    cnt = dict(py2rust=collections.Counter(), rust2py=collections.Counter(), pyfile=collections.Counter())
    M = sys.monitoring
    TOOL = 3
    M.use_tool_id(TOOL, "qt76")
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
        """The crate's name for this callable, or None. Slots and getters are not calls and never reach here."""
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

    stack = []
    depth = [0]

    def on_call(code, off, f, arg0):
        if type(f).__name__ == "function":
            return
        n = rust_name(f)
        if n:
            cnt["py2rust"][n] += 1
            stack.append((f, depth[0]))

    def on_c_end(code, off, f, arg0):
        if stack and stack[-1][0] is f:
            stack.pop()

    def on_start(code, off):
        if stack and stack[-1][1] == depth[0]:
            cnt["rust2py"][code.co_qualname] += 1
        depth[0] += 1
        fn = code.co_filename
        i = fn.rfind("/satassume/")
        if i >= 0:
            cnt["pyfile"][fn[i + 11:]] += 1
        elif "/sympy/" in fn:
            cnt["pyfile"]["<sympy>"] += 1
        elif "/slice/" in fn:
            cnt["pyfile"]["<slice glue> " + os.path.basename(fn)] += 1

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
# sa-port-76: two kinds for the per-module table, each in rounds of its own. cprof: cProfile, calls and own time per function.
# fsamp: a Python-level SIGALRM at 1 ms that records the file of the leaf Python frame, and the nearest frame on the stack in
# satassume or the glue. Native time lands on the Python frame the call returns to, so it's charged to the caller.
prof = None
fs = None
if kind == "cprof":
    import cProfile
    prof = cProfile.Profile()
if kind == "fsamp":
    import signal
    fs = collections.Counter()

    def fs_where(fn):
        i = fn.rfind("/satassume/")
        if i >= 0:
            return fn[i + 11:]
        i = fn.rfind("/slice/")
        if i >= 0:
            return "slice/" + fn[i + 7:]
        return "<sympy>" if "/sympy/" in fn else "<other>"

    def fs_handler(sig, fr):
        leaf = fs_where(fr.f_code.co_filename)
        owner = leaf
        while owner in ("<sympy>", "<other>") and fr.f_back is not None:
            fr = fr.f_back
            owner = fs_where(fr.f_code.co_filename)
        fs[leaf + "|" + owner] += 1
    signal.signal(signal.SIGALRM, fs_handler)
per = [0.0] * len(pairs)
ans = [None] * len(pairs)
ask = sympy_api.ask
gc.collect()
gc.freeze()
if lib is not None:
    lib.start(500)
if plib is not None:     # sa-port-143
    _code_ok = plib.start(int(os.environ.get("PYSAMPLE_US", "1000")), int(os.environ.get("PYSAMPLE_WHAT", "3"))) == id(sys._getframe().f_code)
    _setq = plib.setq
if fs is not None:
    signal.setitimer(signal.ITIMER_REAL, 0.001, 0.001)
if prof is not None:
    prof.enable()
t0 = pc()
for i, (p, a) in enumerate(pairs):
    if plib is not None:
        _setq(i)
    t = pc()
    try:
        r = ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
    per[i] = pc() - t
    ans[i] = r
total = pc() - t0
if prof is not None:
    prof.disable()
if fs is not None:
    signal.setitimer(signal.ITIMER_REAL, 0, 0)
if lib is not None:
    lib.stop()
if plib is not None:     # sa-port-143
    plib.stop()
    plib.setq(-1)
if cnt is not None:
    sys.monitoring.set_events(TOOL, 0)
d = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]
row = dict(wl=wl, mode=mode, kind=kind, digest=d, s=total, so=so, n=len(pairs))
# sa-port-86: read after the timer. The crate's counters are compiled in, so timed rows carry them at no added cost. `installed`
# says what the switches left in place, on this tree, in this process.
from satassume import engine as _E
row["installed"] = dict(VarTable=_E.VarTable.__module__ + "." + _E.VarTable.__name__, compile_formula=_E.compile_formula.__module__,
                        formula_literal=_E.formula_literal.__module__, Session_var=_E.Session.var.__module__,
                        Session_table=type(_E.Session.__dict__.get("table")).__name__)
if session_live is not None:
    row["session"] = session_live.counts()
if knowledge_live is not None:
    row["knowledge_installed"] = knowledge_live.installed()     # sa-port-139
if term_live is not None:
    row["term"] = term_live.counts()
    row["refusals"] = len(term_live.REFUSALS)
    import convert as _cv   # sa-port-313: which walker this process ran with (read after the timer and the sampler stopped)
    row["slice_convert_env"] = os.environ.get("SLICE_CONVERT")
    _f = getattr(term_live, "FRAMES", None)     # sa-port-314: which per-query frames ran (read after the timer)
    row["term_frames"] = "no-switch" if _f is None else ("py" if _f[0] is None else type(_f[0]).__name__)
    row["term_frames_env"] = os.environ.get("SLICE_TERM_FRAMES")
    row["walk"] = repr(_cv.WALK[0])
if lra_live is not None:
    row["lra"] = lra_live.counts()
if prof is not None:
    prof.create_stats()
    with open(outbase + ".json", "w") as fh:
        json.dump([[*k, v[0], v[1], v[2], v[3]] for k, v in prof.stats.items()], fh)
    row["rust_classes"] = sorted(c.__name__ for c in vars(sa_solver).values() if isinstance(c, type)) if mode != "py" else []
if fs is not None:
    row["fsamp"] = dict(fs)
if kind in ("time", "pysample"):     # sa-port-143: pysample rows keep per and ans too
    row.update(per=per, ans=ans)
if plib is not None:     # sa-port-143: records, maps and every reachable code object (id -> file, qualname, firstlineno)
    n = plib.count()
    row["samples"] = n
    row["code_ok"] = _code_ok
    plib.nfaults.restype = ctypes.c_long
    row["walk_faults"] = plib.nfaults()
    row["recsize"] = plib.recsize()
    with open(outbase + ".bin", "wb") as fh:
        fh.write(ctypes.string_at(plib.data(), n * plib.recsize()))
    with open("/proc/self/maps") as a, open(outbase + ".maps", "w") as b:
        b.write(a.read())
    import types
    codes = {}
    def _add(co):
        if id(co) in codes:
            return
        codes[id(co)] = (co.co_filename, co.co_qualname, co.co_firstlineno)
        for c in co.co_consts:
            if isinstance(c, types.CodeType):
                _add(c)
    gc.unfreeze()
    _add(sys._getframe().f_code)
    for o in gc.get_objects():
        if isinstance(o, types.FunctionType):
            _add(o.__code__)
        elif isinstance(o, types.CodeType):
            _add(o)
        elif isinstance(o, (types.GeneratorType, types.CoroutineType)):
            _add(o.gi_code if hasattr(o, "gi_code") else o.cr_code)
    with open(outbase + ".codes.json", "w") as fh:
        json.dump({str(k): v for k, v in codes.items()}, fh)
if lib is not None:
    n = lib.count()
    row["samples"] = n
    with open(outbase + ".bin", "wb") as fh:
        fh.write(ctypes.string_at(lib.data(), n * 8))
    with open("/proc/self/maps") as a, open(outbase + ".maps", "w") as b:
        b.write(a.read())
if cnt is not None:
    row.update({k: dict(v.most_common()) for k, v in cnt.items()})
print(json.dumps(row))
