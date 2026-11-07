"""knowledge_quiet.py {fire|rust WL [--limit N]} under the atoms family: can a raise reach the two quiet handlers unseen?

fire: sa-port-25's quiet_fire.py, unchanged, with `knowledge_live.install()` and handler_count installed in this process.
rust: finds, in workload WL, the first query where Rust's `symbol_units` or `constant_units` ("atom_units"), `units` or conversion runs inside either `try`
  (engine.py:1906's, sympy_api.py:1107's), then plants a ValueError at that call on that query. Each must escape as
  KnowledgeFault with the counter at 0: that's the claim that a Rust failure can't turn into a quiet answer. A combination no
  query reached prints "not reached", which is not a pass. Then the same three raises from a forced nest: the check itself
  calls `_ask` or the template inside the try, which no workload is claimed to do; printed as `forced`, kept apart from `reached`.
`plant_check(H)` is the firing check other runs call in their own process, so their zero is about a counter shown to work.
"""
import json
import os
import runpy
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _plants(E, A):
    return [("engine.py:1906 s.assumption_lits", E.Session, "assumption_lits"),
            ("engine.py:1906 _complete_check", E.Engine, "_complete_check"),
            ("sympy_api.py:1107 _formula", A, "_formula"),
            ("sympy_api.py:1107 eng.verdict", E.Engine, "verdict")]


def plant_check(H):
    """One planted ValueError at each call in the two tries; `H` records them as `plant:<site>`. Returns {site: rows seen}."""
    from sympy import Q, Symbol
    from satassume import engine as E, sympy_api as A
    x, y = Symbol("x", real=True), Symbol("y", real=True)
    out = {}
    was = H.where
    for name, owner, attr in _plants(E, A):
        real = getattr(owner, attr)
        fired = [0]

        def plant(*args, **kw):
            fired[0] += 1
            if fired[0] == 1:
                raise ValueError("planted " + name)
            return real(*args, **kw)
        H.where = "plant:" + name
        setattr(owner, attr, plant)
        try:
            A._consistent(Q.positive(x) & Q.negative(y), E.Engine())
        finally:
            setattr(owner, attr, real)
        out[name] = dict(reached=fired[0] > 0)
    H.where = was
    return out


def fire():
    import knowledge_live as K
    K.install()
    sys.argv = ["quiet_fire.py", "port2", os.path.join(HERE, "handler_count.py")]
    runpy.run_path(os.path.join(HERE, "quiet_fire.py"), run_name="__main__")
    print("knowledge counts", dict(K.COUNTS))


def rust(wl, limit):
    import sa_solver
    from harness.state import reset_module_state
    from satassume import engine as E, sympy_api as A
    from evalbench.common import workload
    import handler_count as H
    path = tempfile.mktemp(dir=os.environ.get("SCRATCH", "."))
    H.install(path)
    Real = sa_solver.Knowledge
    hook = [lambda kind: None]

    class Proxy:
        def __init__(self, data):
            self.k = Real(data)

        def const_basis(self):
            return self.k.const_basis()

        def symbol_units(self, table, i):
            hook[0]("atom_units")
            return self.k.symbol_units(table, i)

        def constant_units(self, table, i):
            hook[0]("atom_units")
            return self.k.constant_units(table, i)

        def units(self, facts):
            hook[0]("units")
            return self.k.units(facts)
    sa_solver.Knowledge = Proxy
    import convert
    py_convert = convert.convert

    def conv(p, a, eng):
        hook[0]("convert")
        return py_convert(p, a, eng)
    convert.convert = conv
    import knowledge_live as K
    import term_live as T
    K.install()
    check = E.Engine._build_context.__code__
    cons = A._consistent.__code__
    src = open(check.co_filename).read().splitlines()
    line = next(i + 1 for i in range(check.co_firstlineno, len(src)) if "self._complete_check(s, s.assumption_lits())" in src[i])

    def site():
        f = sys._getframe(2)
        while f:
            if f.f_code is check and f.f_lineno == line:
                return "engine.py:1906"
            if f.f_code is cons:
                return "sympy_api.py:1107"
            f = f.f_back
        return None

    first, totals = {}, {}
    if wl == "fuzz":
        from evalbench.fuzz import queries
        pairs = queries(424242)[:limit]
    else:
        pairs = workload(wl)[:limit]
    i = [0]

    def scan(kind):
        s = site()
        if s:
            totals[kind, s] = totals.get((kind, s), 0) + 1
            first.setdefault((kind, s), i[0])
    hook[0] = scan

    def fresh():
        reset_module_state(sympy_cache=False)
        A.set_default_engine(E.Engine())

    def ask(p, a):
        fresh()
        try:
            return "ok:%r" % (A.ask(p, a),)
        except Exception as e:
            return "raise:" + type(e).__name__
        except K.KnowledgeFault as e:
            return "KnowledgeFault: " + str(e)[:120]
        except T.TermFault as e:
            return "TermFault: " + str(e)[:120]

    for i[0], (p, a) in enumerate(pairs):
        ask(p, a)
    print("queries", len(pairs), "inside a try:", {f"{k}@{s}": n for (k, s), n in sorted(totals.items())})
    print("counts", dict(K.COUNTS))
    H._out.flush()
    print("unplanted handler rows in the scan", len(open(path).read().splitlines()))
    for kind in ("atom_units", "units", "convert"):
        for s in ("engine.py:1906", "sympy_api.py:1107"):
            if (kind, s) not in first:
                print(json.dumps(dict(kind=kind, site=s, result="not reached")))
                continue
            q = first[kind, s]
            fired = [0]

            def plant(k):
                if k == kind and site() == s:
                    fired[0] += 1
                    if fired[0] == 1:
                        raise ValueError("planted")
            open(path, "w").close()
            hook[0] = plant
            r = ask(*pairs[q])
            hook[0] = lambda kind: None
            H._out.flush()
            print(json.dumps(dict(kind=kind, site=s, query=q, fired=fired[0], result=r, counter_saw=len(open(path).read().splitlines()))))
    forced(A, E, K, H, path, hook, ask)


def forced(A, E, K, H, path, hook, ask):
    """A raise from conversion or a template, made to happen inside each `try` by a nested call the plant adds."""
    from sympy import Q, Symbol
    from satassume.knowledge.templates import registry
    x, y = Symbol("x", real=True), Symbol("y", real=True)
    query = (Q.positive(x), Q.positive(x) & Q.negative(y))
    template = next(t for t in registry._by_class[Symbol] if hasattr(t, "__wrapped__"))
    nested = dict(convert=lambda eng: A._ask(Q.positive(Symbol("n")), True, eng),
                  units=lambda eng: template(Symbol("n")),)    # not an input term of this query: the derived path
    for s, attr in (("engine.py:1906", "_complete_check"), ("sympy_api.py:1107", "verdict")):
        for kind, call in nested.items():
            real = getattr(E.Engine, attr)
            state = dict(entered=0, fired=0)

            def plant(self, *args, **kw):
                state["entered"] += 1
                if state["entered"] == 1:
                    def h(k):
                        if k == kind and not state["fired"]:
                            state["fired"] += 1
                            raise ValueError("planted")
                    hook[0] = h
                    try:
                        call(self)
                    finally:
                        hook[0] = lambda kind: None
                return real(self, *args, **kw)
            open(path, "w").close()
            setattr(E.Engine, attr, plant)
            try:
                r = ask(*query)
            finally:
                setattr(E.Engine, attr, real)
            H._out.flush()
            print(json.dumps(dict(forced=kind, site=s, **state, result=r, counter_saw=len(open(path).read().splitlines()))))


if __name__ == "__main__":
    if sys.argv[1] == "fire":
        fire()
    else:
        rust(sys.argv[2], int(sys.argv[4]) if len(sys.argv) > 3 else None)
