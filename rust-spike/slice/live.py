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
#: A workload row `(f, CALL)` is asked as `f()` (twin_wl.py: rows with their own engines).
CALL = "<call>"


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
    if wl == "port":        # not from the eval sets: aimed at the lines port_mutants.py changes
        from port_queries import queries
        return queries()
    if wl == "fuzz":
        from evalbench.fuzz import queries
        return queries(424242)
    if wl.startswith("transfer2:"):    # transfer_workload.py's second generator
        import transfer_workload
        _, seed, n = wl.split(":")
        return transfer_workload.queries2(int(seed), int(n))
    if wl.startswith("transfer:"):    # transfer_workload.py, by seed and count
        import transfer_workload
        seed, n = wl.split(":")[1:]
        return transfer_workload.queries(int(seed), int(n))
    if wl == "lra":
        import lra_wl
        return lra_wl.queries()
    if wl == "loop":    # loop_wl.py: vocabulary functions registered, for `_compile`'s demand path (5c2)
        import loop_wl
        return loop_wl.queries()
    if wl == "scope":   # scope_wl.py: custom predicates registered, for `extension_atoms` (step scope)
        import scope_wl
        return scope_wl.queries()
    if wl == "twin":    # twin_wl.py: two equal Function classes in one query, where plant class-is fires (issue 323)
        import twin_wl
        return twin_wl.queries()
    if wl == "zero":    # zero_wl.py: zero twins under an application, for `_glue_of`'s twin branch (before 5c7)
        import zero_wl
        return zero_wl.queries()
    if wl == "cls":     # cls_wl.py: two equal class objects in one query, for `same_class` (the ad:cbm_noid fix)
        import cls_wl
        return cls_wl.queries()
    if wl == "cert":    # cert_wl.py: pi bounds near the certificate's Y, for lra_cert's pi_laurent (adapters C2)
        import cert_wl
        return cert_wl.queries()
    if wl == "budget":  # budget_wl.py: queries over and near the discovery budget, for `_union` and `_within_budget` (5c7)
        import budget_wl
        return budget_wl.queries()
    if wl in ("f6", "value", "rootof", "core", "opaque", "wiring"):    # hidden-gap workloads (6, 6e, 6f, 6g(a), 6g(b)), whole engine
        import importlib
        return importlib.import_module(f"knowledge_{wl}_wl").queries()
    return workload(wl)


def _discarded_runs(moved):
    """A refused term_live run is rolled back and run again (term_live.py `_ask`), and the answer comes from the rerun alone.
    What this recorder kept of the discarded run (its solvers' streams, the digest's sessions and relations) leaves the record
    with it, so a query's row holds the sessions its answer came from, as Python's does: before the rollback reached the
    Rust-native tables (issue 323, lra's cause) the rerun did less than Python and the two counts happened to be equal.
    Counted in the totals, `discarded_runs` and `discarded_solvers`; what a discarded run leaves in the state is
    term_discard.py's check, not this record's. Chained after any hook already there."""
    import term_live
    n = dict(runs=0, solvers=0, digest_sessions=0)
    at = [None]
    before, after = term_live.BEFORE_RUN[0], term_live.AFTER_ROLLBACK[0]

    def start(eng):
        at[0] = (len(T.solvers), moved.run_mark() if moved else None)
        if before is not None:
            before(eng)

    def rolled_back():
        if after is not None:
            after()
        if at[0] is None:
            return
        k, m = at[0]
        at[0] = None
        n['runs'] += 1
        n['solvers'] += len(T.solvers) - k
        del T.solvers[k:]
        if moved:
            n['digest_sessions'] += moved.run_discard(m)
    term_live.BEFORE_RUN[0], term_live.AFTER_ROLLBACK[0] = start, rolled_back
    return n


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

    if args.mode == "rust" and os.environ.get("SLICE_TRANSFER") != "py":    # before the first import of satassume
        if args.so:
            sys.path.insert(0, args.so)
        import p_install
        p_install.install()

    from satassume import engine, ref, sympy_api
    from satassume.sat import solver as SV
    import catch_count
    import state
    catch_count.install()
    # The whole of both `try`s, by code object. SLICE_PLANT_HANDLER=NAME (below, after the installs) plants a raise so a run
    # can show this install fires.
    import handler_count
    open(args.out + ".handlers", "w").close()      # append mode below, for forked children: a rerun starts empty
    handler_count.install(args.out + ".handlers")
    lra_groups = {}
    T.digest = state.digest
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
    if backend and args.check != "plain":    # plain's install() does this too
        backend.install_transfer()
    if backend:     # Component 4 slice A: rust mode only, so Python's column stays the control. SLICE_TERM=py keeps it off.
        import term_live
        term_live.from_env()
        import lra_live     # Slice D. SLICE_LRA_TERM=py keeps it off.
        lra_live.from_env()
        import session_live     # Component 5, step 5a. SLICE_SESSION=py keeps it off.
        session_live.from_env()
        import knowledge_live   # Component 6's ported parts (port-wire.md). SLICE_KNOWLEDGE=py keeps them off.
        knowledge_live.from_env()
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

    if os.environ.get("CACHE_DET"):     # cache_det.py: every `_CACHE` hit built again and compared; after the installs
        import cache_det
        cache_det.install()

    # After every install above, on both modes: a workload may build the default engine while it loads (scope_wl's
    # install() does), and an engine built before knowledge_live.from_env() and backend.install() keeps Python's
    # bindings, such as with_closed_units(registry.clauses_for) (engine.py:1330-1341), for the whole run (issue 323).
    # SLICE_PLANT_HANDLER, after the installs (issue 323, planner ~14:55 9 Nov, Q2): planted before them, backend.install()
    # replaced the patched rows with context.rs's, so no plant fired on Rust and its handler zeros were void. Patched after,
    # context.rs calls the patch by name (`ctx:cb_patched`) and relevance.rs calls `Engine.verdict` by name (`rv:cb_verdict`):
    # the raise reaches Rust's own handlers (context.rs build_context, relevance.rs `_consistent`) and their handler rows.
    # SLICE_SESSION_PLANT=ctx-check-raise raises inside context.rs's complete check itself.
    plant = {"assumption_lits": (engine.Session, "assumption_lits"), "complete_check": (engine.Engine, "_complete_check"),
             "formula": (sympy_api, "_formula"), "verdict": (engine.Engine, "verdict")}.get(os.environ.get("SLICE_PLANT_HANDLER"))
    if plant:
        real = getattr(*plant)

        def _planted(*a, **k):      # `ask` calls `_formula` before `_consistent` does: raising there never reaches the handler
            if plant[1] == "_formula" and sys._getframe(1).f_code.co_name != "_consistent":
                return real(*a, **k)
            raise ValueError("planted")
        setattr(*plant, _planted)
    # The moved containers' digest (moved_digest.py; issue 323), after the installs, on both modes: SLICE_MOVED=0 keeps it off.
    moved = None
    if args.check != "plain":
        import moved_digest
        moved = moved_digest.install(bool(backend))
    pairs = load(args.wl)

    discarded = _discarded_runs(moved) if backend else None
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
                r = p() if type(a) is str and a == CALL else sympy_api.ask(p, a)
                if r is not None and r is not True and r is not False:
                    r = "non-bool " + repr(r)
            except ValueError as e:
                r, msg = "ValueError", str(e)
            except Exception as e:
                r, msg = "raise " + type(e).__name__, str(e)
            answers[key] = r
            rec = dict(q=key, ans=r, msg=ADDR.sub("0xX", msg))
            # step 5c10d: the default engine's read-only stats view and last_budget_limited after each query
            # (Rust-owned on Rust), compared by livecmp.py (stats_diff)
            eng = sympy_api.default_engine()
            rec["eng"] = [list(eng.stats.items()), eng.last_budget_limited]
            caught = catch_count.take()
            if caught:
                rec["caught"] = caught
            if moved:
                rec["moved"] = moved.session_rows()
                mq = moved.query_rows()
                if mq:
                    rec["moved_q"] = mq
                if pos % moved_digest.every() == moved_digest.every() - 1 or pos == len(order) - 1:
                    rec["moved_eng"] = moved.engine_rows(eng)
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
                   python_solvers_made=py_made[0], traced_made=T.created, traced_dropped=T.dropped, discarded=discarded,
                   reentry=T.reentry, addr_masked=T.addr, hook_outside_solver=T.outside, hook_counts=T.hookcount,
                   entry_raises=T.raises, reach=reach, answers=hist,
                   theory_classes=sorted(c.__name__ for c in T.theory_classes),
                   lra_groups=lra_groups,
                   hashseed=os.environ.get("PYTHONHASHSEED"))
        if moved:
            tot["moved"] = moved.tot
        if backend:
            tot["backend_created"], tot["backend_dropped"] = backend.created, backend.dropped
            tot["so_sha"] = so_sha
        out.write(json.dumps(dict(total=tot)) + "\n")
    print(json.dumps(tot))


if __name__ == "__main__":
    main()
