"""Round 3, item B3: the cost of the SymPy-facing layer (``sympy_api.ask``)
around the engine, as a share of the cold pass.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/scripts/api_overhead.py \
        stream.pkl MODE

MODE (one per process, each on a cold engine):

``plain``   the cold pass unwrapped (the denominator), then a second pass
            (every query a memo hit) and a third pass over only the queries
            that were memo hits in the cold pass: per-hit cost.  Then a
            micro-benchmark of the parts of a hit (key tuple, isinstance
            checks, ``_registry_state``, ``memo.get``) over the hit keys.
``wrap``    the cold pass with timers around ``sympy_api.ask`` (memo hits vs
            misses), ``sympy_api._formula`` (the to_formula memo, i.e. key
            building for an engine query) and the engine entry points
            ``Engine.ask/is_/_is_custom`` at depth 1.  API overhead of a miss
            = its ``ask`` time - its engine time; the timers' own cost is
            estimated with empty wrappers (``wrapnull``) and subtracted.
``wrapnull``  the same wrappers, timers that record nothing (the wrapping cost)
``profile``   cProfile of the cold pass; prints the sympy_api rows.
"""
import pickle, sys, time

stream = pickle.load(open(sys.argv[1], "rb"))
mode = sys.argv[2]
import satassume.sympy_api as api
from satassume.engine import Engine

pc = time.perf_counter


def cold(stream):
    t0 = pc()
    for p, a, r in stream:
        try:
            got = api.ask(p, a)
        except ValueError:
            got = "err"
        if got is not r and got != "err":
            raise SystemExit("mismatch")
    return pc() - t0


if mode == "plain":
    eng = api.default_engine()
    hits_before = eng.stats["cache_hits"]
    # which queries hit the memo in the cold pass: record keys seen, the
    # memo is never cleared on the stream (checked below)
    seen = set(); hit_idx = []
    for i, (p, a, r) in enumerate(stream):
        k = (p, a)
        if k in seen:
            hit_idx.append(i)
        seen.add(k)
    T = cold(stream)
    memo_hits = eng.stats["cache_hits"]
    print(f"cold pass {T:.3f}s; stats cache_hits {memo_hits} (memo + is_ cache); "
          f"repeat keys in the stream {len(hit_idx)}")
    T2 = cold(stream)
    print(f"second pass (all memo hits) {T2:.3f}s = {1e6 * T2 / len(stream):.2f} us/query")
    sub = [stream[i] for i in hit_idx]
    T3 = min(cold(sub) for _ in range(3))
    print(f"pass over the {len(sub)} cold-pass hits only: {1000 * T3:.1f} ms = "
          f"{1e6 * T3 / len(sub):.2f} us/hit = {100 * T3 / T:.2f}% of the cold pass")
    # parts of a hit
    memo = eng.answers
    Basic = api._Basic
    keys = [(p, a) for p, a, r in sub]
    n = len(keys)

    def bench(f, reps=5):
        best = 1e9
        for _ in range(reps):
            t0 = pc(); f(); best = min(best, pc() - t0)
        return best
    t_loop = bench(lambda: [None for p, a in keys])
    t_inst = bench(lambda: [isinstance(p, Basic) and (a is True or isinstance(a, Basic)) for p, a in keys])
    t_tuple = bench(lambda: [(p, a) for p, a in keys])
    t_state = bench(lambda: [api._registry_state(eng) for p, a in keys])
    t_cmp = bench(lambda: [memo.state != api._registry_state(eng) for p, a in keys])
    t_get = bench(lambda: [memo.get((p, a), None) for p, a in keys])
    t_hashp = bench(lambda: [hash(p) for p, a in keys])
    t_hasha = bench(lambda: [hash(a) for p, a in keys])
    print("parts over the hits (loop overhead subtracted), ms total / % of cold pass:")
    for name, t in (("isinstance checks", t_inst), ("key tuple", t_tuple),
                    ("_registry_state()", t_state), ("state compare incl. build", t_cmp),
                    ("memo.get((p, a))", t_get), ("hash(p)", t_hashp), ("hash(a)", t_hasha)):
        t -= t_loop
        print(f"  {name:28s} {1000 * t:7.2f} ms  {100 * t / T:5.2f}%")
    # the API layer of a miss, without the engine: the same memo work as a
    # hit plus put, and the two _formula lookups (warm memo: the cold pass
    # translated each distinct Boolean once; to_formula itself is timed
    # separately under the profiler)
    hs = set(hit_idx)
    miss = [(p, a) for i, (p, a, r) in enumerate(stream) if i not in hs]
    rel = bool(eng.relation_specs)
    fm = api._formula

    def fl():
        for p, a in miss:
            try:
                fm(p, rel)
                if a is not True:
                    fm(a, rel)
            except api.Unsupported:
                pass
    t_fl = bench(fl) - bench(lambda: [None for p, a in miss])
    scratch = type(memo)()
    t_memo = bench(lambda: [(memo.state != api._registry_state(eng), memo.get((p, a), None),
                             scratch.put((p, a), None)) for p, a in miss])
    print(f"misses ({len(miss)}): _formula lookups {1000 * t_fl:.2f} ms ({100 * t_fl / T:.2f}%), "
          f"state + get + put {1000 * t_memo:.2f} ms ({100 * t_memo / T:.2f}%)")

elif mode in ("wrap", "wrapnull"):
    from collections import Counter
    acc = Counter(); cnt = Counter()
    real = mode == "wrap"
    state = {"depth": 0, "miss": False}
    orig_ask, orig__ask, orig_formula = api.ask, api._ask, api._formula

    def _ask(p, a, eng):
        state["miss"] = True
        return orig__ask(p, a, eng)
    api._ask = _ask

    def _formula(expr, rel):
        if not real:
            return orig_formula(expr, rel)
        t0 = pc()
        try:
            return orig_formula(expr, rel)
        finally:
            acc["_formula"] += pc() - t0; cnt["_formula"] += 1
    api._formula = _formula

    def entry(name, orig):
        def w(self, *a, **k):
            state["depth"] += 1
            if state["depth"] > 1 or not real:
                try:
                    return orig(self, *a, **k)
                finally:
                    state["depth"] -= 1
            t0 = pc()
            try:
                return orig(self, *a, **k)
            finally:
                acc["engine"] += pc() - t0; cnt["engine:" + name] += 1
                state["depth"] -= 1
        return w
    Engine.ask = entry("ask", Engine.ask)
    Engine.is_ = entry("is_", Engine.is_)
    Engine._is_custom = entry("is_custom", Engine._is_custom)

    t_all = pc()
    first = None
    for i, (p, a, r) in enumerate(stream):
        state["miss"] = False
        e0 = acc["engine"]
        t0 = pc()
        try:
            api.ask(p, a)
        except ValueError:
            pass
        dt = pc() - t0
        k = "miss" if state["miss"] else "hit"
        acc[k] += dt; cnt[k] += 1
        if i == 0:
            first = (dt, acc["engine"] - e0)
    T = pc() - t_all
    print(f"{mode}: pass {T:.3f}s")
    for k in ("hit", "miss", "engine", "_formula"):
        print(f"  {k:10s} {1000 * acc[k]:8.1f} ms  n={cnt[k]}")
    print("  engine calls:", {k: v for k, v in cnt.items() if k.startswith("engine:")})
    if real:
        print(f"  api part of misses (miss - engine) {1000 * (acc['miss'] - acc['engine']):.1f} ms, "
              f"of which _formula {1000 * acc['_formula']:.1f} ms; the first query (Engine() and "
              f"registry warm-up) {1000 * (first[0] - first[1]):.1f} ms of it")

elif mode == "profile":
    import cProfile, pstats, io
    pr = cProfile.Profile()
    pr.enable(); T = cold(stream); pr.disable()
    print(f"profiled pass {T:.3f}s")
    s = io.StringIO()
    st = pstats.Stats(pr, stream=s)
    st.sort_stats("cumulative").print_stats(r"sympy_api|registry_state|__hash__|_hashable|engine.py:.*\((ask|is_)\)")
    print(s.getvalue()[:6000])
