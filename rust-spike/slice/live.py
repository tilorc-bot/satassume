"""live.py WL MODE OUT.jsonl: one pass of a real workload on one backend, recorded for `livecmp.py`.

WL: dev or fuzz. MODE: py (the pure Python solver) or rust (`backend.py`). The theories are the unchanged Python ones.

--check plain   answers only, solver untouched (rust: `backend.install()`, exactly what a user would run).
--check raw     answers and state.digest of each solver when its query ends, with no subclass and no hook wrappers:
                the end states must equal those of a traced run, which shows the tracing itself changes nothing.
--check end     also state.digest of each solver when its query ends, and each session's call stream.
--check entry   (default) also state.digest after every outermost solver call, into that stream.
--detail Q:FILE write every event of query Q to FILE, one JSON line each, with the whole dump after each solver call.

One line per query, flushed as it goes: answer, and per solver its stream hash, end-state hash and counts. The stream
holds, in order, every outermost solver call (name, arguments, result or exception, state hash) and every theory hook
(class, name, arguments, result). A call from inside a hook is counted as `reentry` with the caller's file:line, on
both backends, so the same run shows which adapters would reach it. The last line is the totals.

Nothing here changes satassume: the solver is subclassed and theory classes are wrapped from this file.
"""
import argparse
import functools
import gc
import hashlib
import json
import os
import random
import re
import sys
import types
import weakref

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ADDR = re.compile(r"0x[0-9a-f]+")
API = """new_var nvars ensure_vars add_clause add_clauses add_internal add_pattern set_rule_block register_block
mention_blocks mention propagate value root_trail implied release attach_theory theories register_atom theory_models
set_inert solve model conflict consistent entails entails_all stats""".split()
SEARCH = {"propagate", "solve", "implied", "consistent", "entails", "entails_all"}
COUNTERS = "props conflicts decisions learned restarts reductions ring_hits tdecisions late late_written".split()
HOOKS = ("register_atom", "assert_lit", "check", "propagate", "decide", "push_level", "pop_level")


def show(x):
    """A stable text for a value that crosses the boundary. Addresses are masked and counted: a repr with one in it
    compares nothing at that spot, so the totals say how often that happened."""
    k = x.__class__
    if x is None or k in (int, bool, str, float):
        return repr(x)
    if k in (list, tuple):
        return "[" + ",".join(map(show, x)) + "]"
    if k is dict:
        return "{" + ",".join(f"{show(a)}:{show(b)}" for a, b in x.items()) + "}"
    if k in T.theory_classes:
        return "<" + k.__name__ + ">"
    r = repr(x)
    if "0x" in r:
        T.addr += 1
        r = ADDR.sub("0xX", r)
    return r


class T:
    """Run state."""
    stack = []          # streams of the solver calls on the stack
    in_hook = 0
    solvers = []        # streams of this query's solvers
    theory_classes = set()
    addr = 0
    reentry = {}        # "backend-neutral" caller file:line -> count, per name
    detail = None       # open file for --detail
    check = "entry"
    dump = None
    digest = None
    hook_self = None
    outside = 0         # hook calls with no solver call on the stack
    created = 0
    dropped = 0
    hookcount = {}
    raises = {}


def _gone():
    T.dropped += 1


class Stream:
    __slots__ = ("h", "n", "solver", "entries", "hooks", "searches")

    def __init__(self, solver):
        self.h = hashlib.blake2b(digest_size=16)
        self.solver = solver
        self.entries = self.hooks = self.searches = 0

    def add(self, line):
        self.h.update(line.encode())
        self.h.update(b"\n")


def canon(d):
    """`state.digest` hashes in dict order, and the two dumps build their dicts in different code."""
    return dict(sorted(d.items()))


def is_iter(x):
    return isinstance(x, (types.GeneratorType, map, filter, zip)) or (hasattr(x, "__next__"))


def traced_class(base, dump):
    ns = {}
    for name in API:
        ns[name] = _entry(name, getattr(base, name))

    def start(self):
        st = Stream(self)
        self._live_stream = st
        T.solvers.append(st)
        T.created += 1
        weakref.finalize(self, _gone).atexit = False

    def __init__(self):
        base.__init__(self)
        start(self)
    if base.__init__ is not object.__init__:
        ns["__init__"] = __init__
    else:
        def __new__(cls):
            self = base.__new__(cls)
            start(self)
            return self
        ns["__new__"] = __new__
    return type("Traced" + base.__name__, (base,), ns)


def _entry(name, f):
    search = name in SEARCH

    @functools.wraps(f)
    def w(self, *a, **k):
        st = self._live_stream
        if T.stack and T.stack[-1] is st and not T.in_hook:
            return f(self, *a, **k)     # the Python solver calling its own API: not an entry
        if T.in_hook:
            fr = sys._getframe(1)
            key = f"{name} from {fr.f_code.co_filename.rsplit('satassume/', 1)[-1]}:{fr.f_lineno}"
            T.reentry[key] = T.reentry.get(key, 0) + 1
        a = tuple(list(x) if is_iter(x) else x for x in a)
        args = show(a) + (show(k) if k else "")
        T.stack.append(st)
        saved, T.in_hook = T.in_hook, 0
        try:
            r = f(self, *a, **k)
            out = show(r)
        except Exception as e:
            r = e
            out = f"raise {type(e).__name__}: {ADDR.sub('0xX', str(e))}"
            T.raises[name] = T.raises.get(name, 0) + 1
        finally:
            T.stack.pop()
            T.in_hook = saved
        st.entries += 1
        st.searches += search
        d = None
        if T.check == "entry" or T.detail:
            d = canon(T.dump(self))
        s = T.digest(d) if d is not None and T.check == "entry" else ""
        st.add(f"E {name} {args} {out} {s}")
        if T.detail:
            json.dump(dict(ev="entry", name=name, args=args[:2000], out=out[:2000], state=d), T.detail)
            T.detail.write("\n")
        if isinstance(r, Exception):
            raise r
        return r
    return w


def wrap_hooks(cls):
    """Class-level, once: the solver's own lookups then find the wrapper on both backends."""
    if cls in T.theory_classes:
        return
    T.theory_classes.add(cls)
    for name in HOOKS:
        f = getattr(cls, name, None)
        if f is not None:
            setattr(cls, name, _hook(cls.__name__, name, f))


def _hook(cname, name, f):
    tag = cname + "." + name

    def w(self, *a):
        # A theory calling its own hook (LRATheory._check's push_level) isn't a boundary crossing: Python's does and
        # Rust's core can't be seen to. The stream holds what the solver called.
        if T.hook_self is self:
            return f(self, *a)
        outer, T.hook_self = T.hook_self, self
        try:
            return _hook_call(self, f, a, cname, name, tag)
        finally:
            T.hook_self = outer
    return functools.wraps(f)(w)


def _hook_call(self, f, a, cname, name, tag):
    if True:
        st = T.stack[-1] if T.stack else None
        T.hookcount[tag] = T.hookcount.get(tag, 0) + 1
        args = show(a)
        T.in_hook += 1
        try:
            r = f(self, *a)
        finally:
            T.in_hook -= 1
        if st is None:
            T.outside += 1
            return r
        st.hooks += 1
        if is_iter(r):
            return _gen(st, cname, name, args, r)
        line = f"H {cname}.{name} {args} {show(r)}"
        st.add(line)
        if T.detail:
            T.detail.write(json.dumps(dict(ev="hook", line=line[:2000])) + "\n")
        return r


def _gen(st, cname, name, args, r):
    """A generator from a hook stays lazy: consuming it early could change what the theory sees between items."""
    st.add(f"H {cname}.{name} {args} gen")
    for x in r:
        st.add(f"Y {show(x)}")
        yield x


def install_hooks_on_attach(cls):
    orig = cls.attach_theory

    def attach_theory(self, theory):
        wrap_hooks(type(theory))
        return orig(self, theory)
    cls.attach_theory = attach_theory


TWICE = 1000000


def load(wl):
    from evalbench.common import workload
    if wl == "ground":      # not from the eval sets: atoms that cancel, for `_ground` and `_pending_ground`
        from ground_queries import queries
        return queries()
    if wl == "fuzz":
        from evalbench.fuzz import queries
        return queries(424242)
    return workload(wl)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wl")
    ap.add_argument("mode", choices=["py", "rust"])
    ap.add_argument("out")
    ap.add_argument("--check", default="entry", choices=["plain", "raw", "end", "entry"])
    ap.add_argument("--detail")
    ap.add_argument("--shuffle", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", help="comma-separated query numbers")
    ap.add_argument("--so", help="load sa_solver from this directory (a mutant)")
    ap.add_argument("--handlers", help="count the quiet Exception handlers here: handler_count.py")
    ap.add_argument("--fork", action="store_true", help="each query in its own child, forked after import")
    ap.add_argument("--twice", action="store_true", help=f"each query twice in a row; the repeat is numbered q + {TWICE}")
    args = ap.parse_args()
    T.check = args.check

    from satassume import engine, ref, sympy_api
    from satassume.sat import solver as SV
    import catch_count
    import state
    catch_count.install()
    # The whole of both `try`s, by code object. SLICE_PLANT_HANDLER=NAME plants a raise so a run can show this install fires.
    import handler_count
    handler_count.install(args.out + ".handlers")
    plant = {"assumption_lits": (engine.Session, "assumption_lits"), "complete_check": (engine.Engine, "_complete_check"),
             "formula": (sympy_api, "_formula"), "verdict": (engine.Engine, "verdict")}.get(os.environ.get("SLICE_PLANT_HANDLER"))
    if plant:
        real = getattr(*plant)

        def _planted(*a, **k):      # `ask` calls `_formula` before `_consistent` does: raising there never reaches the handler
            if plant[1] == "_formula" and sys._getframe(1).f_code.co_name != "_consistent":
                return real(*a, **k)
            raise ValueError("planted")
        setattr(*plant, _planted)
    lra_groups = {}
    T.digest = state.digest
    pairs = load(args.wl)
    if args.handlers:
        import handler_count
        handler_count.install(args.handlers)
    py_made = [0]
    oinit = SV.Solver.__init__

    def counted(self, *a, **k):
        py_made[0] += 1
        return oinit(self, *a, **k)
    SV.Solver.__init__ = counted

    backend = None
    so_sha = None
    if args.mode == "rust":
        if args.so:
            sys.path.insert(0, args.so)
        import sa_solver    # before backend, whose own path entry holds the unmutated build
        if args.so and os.path.dirname(os.path.abspath(sa_solver.__file__)) != os.path.abspath(args.so):
            sys.exit(f"--so {args.so}: loaded {sa_solver.__file__} instead")
        so_sha = hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest()
        import backend
        backend.install_euf()
    if args.check == "plain":
        if backend:
            backend.install()
    elif args.check == "raw":
        if backend and os.environ.get("SLICE_LRA", "rust") == "rust":
            import lra_backend
            lra_backend.install()
        if backend:
            make, T.dump = backend.make, state.with_euf(backend.RustSolver.dump, backend.RustSolver.theories)
        else:
            make, T.dump = SV.Solver, state.with_euf(state.dump_py, SV.Solver.theories)

        def factory():
            s = make()
            T.created += 1
            T.solvers.append(Stream(s))
            return s
        engine.Solver = ref.Solver = factory
    else:
        if args.mode == "rust":
            if os.environ.get("SLICE_LRA", "rust") == "rust":
                import lra_backend
                lra_backend.install()
            base, T.dump = backend.RustSolver, state.with_euf(backend.RustSolver.dump, backend.RustSolver.theories)
        else:
            base, T.dump = SV.Solver, state.with_euf(state.dump_py, SV.Solver.theories)
        install_hooks_on_attach(base)
        cls = traced_class(base, T.dump)
        engine.Solver = ref.Solver = cls

    q_detail, f_detail = None, None
    if args.detail:
        q_detail, f_detail = args.detail.split(":", 1)
        q_detail = int(q_detail)

    order = list(range(len(pairs)))
    if args.shuffle:
        random.Random(args.shuffle).shuffle(order)
    if args.limit:
        order = order[:args.limit]
    if args.only:
        order = [int(x) for x in args.only.split(",")]

    if args.twice:
        order = [i for i in order for _ in (0, 1)]
    answers = {}
    reach, hist = {}, {}
    tot = dict(queries=len(order), solvers=0, queries_with_solver=0, queries_with_search=0, entries=0, hooks=0,
               searches=0)
    with open(args.out, "w") as out:
        for pos, i in enumerate(order):
            if args.handlers:
                handler_count.where = i
            p, a = pairs[i]
            key = i + TWICE if args.twice and pos % 2 else i
            if args.fork:
                out.flush()
                child = os.fork()
                if child:
                    status = os.waitpid(child, 0)[1]
                    if status:      # its row is missing: say how it died, since a signal leaves no traceback
                        print(f"child of query {key} died, wait status {status}", file=sys.stderr, flush=True)
                    continue
            T.solvers = []
            handler_count.where = key
            if i == q_detail:
                T.detail = open(f_detail, "w")
            msg = ""
            try:
                r = sympy_api.ask(p, a)
                if r is not None and r is not True and r is not False:
                    r = "non-bool " + repr(r)
            except ValueError as e:
                r, msg = "ValueError", str(e)
            except Exception as e:
                r, msg = "raise " + type(e).__name__, str(e)
            answers[key] = r
            rec = dict(q=key, ans=r, msg=ADDR.sub("0xX", msg))
            caught = catch_count.take()
            if caught:
                rec["caught"] = caught
            if args.check != "plain":
                sess = []
                for st in T.solvers:
                    dd = T.dump(st.solver)
                    e = T.digest(canon(dd))
                    for name, x in zip(COUNTERS, dd["counters"].split()):
                        reach[name] = reach.get(name, 0) + int(x)
                    reach["sessions_with_theory"] = reach.get("sessions_with_theory", 0) + bool(dd["tmap"])
                    reach["sessions_with_tmodel"] = reach.get("sessions_with_tmodel", 0) + (dd["tmodels"] != "N")
                    reach["learnts_at_end_max"] = max(reach.get("learnts_at_end_max", 0), dd["learnts"].count(";") + bool(dd["learnts"]))
                    if T.detail:
                        json.dump(dict(ev="end", state=canon(T.dump(st.solver))), T.detail)
                        T.detail.write("\n")
                    lra_d, group = state.lra_of(st.solver)
                    if group:
                        lra_groups[group] = lra_groups.get(group, 0) + 1
                    sess.append(dict(end=e, stream=st.h.hexdigest(), entries=st.entries, hooks=st.hooks,
                                     searches=st.searches, lra=lra_d, group=group, branching=state.lra_branching(st.solver)))
                    tot["entries"] += st.entries
                    tot["hooks"] += st.hooks
                    tot["searches"] += st.searches
                rec["sessions"] = sess
                tot["solvers"] += len(sess)
                tot["queries_with_solver"] += bool(sess)
                tot["queries_with_search"] += any(s["searches"] for s in sess)
            hist[str(r)] = hist.get(str(r), 0) + 1
            if args.fork:
                # The totals live in the parent, so a child's would read 0 on either backend: they go in the row.
                rec["child"] = dict(py_made=py_made[0], made=T.created, dropped=T.dropped, reentry=T.reentry,
                                    outside=T.outside, raises=T.raises, addr=T.addr)
            out.write(json.dumps(rec) + "\n")
            out.flush()
            if args.fork:
                os._exit(0)     # a child that died first leaves its row out, and livecmp counts the queries
            if T.detail:
                T.detail.close()
                T.detail = None
            T.solvers = []
        st = None
        gc.collect()
        if args.fork:   # the counts are in the children's rows: the parent takes back what it can
            out.flush()
            rows = [json.loads(x) for x in open(args.out)]
            answers = {x["q"]: x["ans"] for x in rows}
            for x in rows:
                hist[str(x["ans"])] = hist.get(str(x["ans"]), 0) + 1
                tot["solvers"] += len(x.get("sessions", []))
                c = x["child"]
                py_made[0] += c["py_made"]
                T.created += c["made"]
                T.dropped += c["dropped"]
                T.addr += c["addr"]
                T.outside += c["outside"]
                for mine, theirs in ((T.reentry, c["reentry"]), (T.raises, c["raises"])):
                    for k, v in theirs.items():
                        mine[k] = mine.get(k, 0) + v
        tot.update(wl=args.wl, mode=args.mode, check=args.check, shuffle=args.shuffle,
                   answers_sha=hashlib.sha256(json.dumps([answers[i] for i in sorted(answers)]).encode())
                   .hexdigest()[:16],
                   python_solvers_made=py_made[0], traced_made=T.created, traced_dropped=T.dropped,
                   reentry=T.reentry, addr_masked=T.addr, hook_outside_solver=T.outside, hook_counts=T.hookcount,
                   entry_raises=T.raises, reach=reach, answers=hist,
                   theory_classes=sorted(c.__name__ for c in T.theory_classes),
                   lra_groups=lra_groups,
                   hashseed=os.environ.get("PYTHONHASHSEED"))
        if backend:
            tot["backend_created"], tot["backend_dropped"] = backend.created, backend.dropped
            tot["so_sha"] = so_sha
        out.write(json.dumps(dict(total=tot)) + "\n")
    print(json.dumps(tot))


if __name__ == "__main__":
    main()
