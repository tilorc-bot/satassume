"""Round 3, item B4: the cyclic garbage collector's share of the replay, and
which objects it spends its time on.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/scripts/gc_alloc.py stream.pkl MODE

One cold pass per process (answers checked). MODE:

``default``  the pass as it runs today, with ``gc.callbacks`` timing every
             collection per generation (count, objects collected, time)
``disable``  ``gc.disable()`` after the imports: the collector's share is
             ``default - disable`` (a bound for what allocation cuts could
             win, not a change to make: library code must not touch GC
             settings)
``freeze``   ``gc.collect(); gc.freeze()`` after the imports and the engine's
             warm-up: the import-time heap is moved to the permanent
             generation, so full collections stop re-scanning it
``heap``     tracked-object census by type (``gc.get_objects()``) after the
             imports and every 2,000 queries, and after the pass; the
             engine's own objects are split by owner (sessions alive,
             solver clause lists, fact cache, memos)
``scan``     at the start of every collection, the objects of the generations
             it scans (``gc.get_objects(g)`` for ``g <= generation``) by type;
             lists are split into int lists (clauses, trail pieces), lists
             of lists (watch lists) and other lists: what the collector
             spends its traversal on
``paths``    ``sys.getallocatedblocks()`` and the generation-0 counter
             around every query, summed by the query's path (memo, is_,
             propagation, escalation, search, cone; stage tracking from
             ``tools/query_log.py``): net blocks left behind and GC-tracked
             allocations per path
"""
import gc, pickle, sys, time
from collections import Counter

stream = pickle.load(open(sys.argv[1], "rb"))
mode = sys.argv[2]
import satassume.sympy_api as api
from satassume.engine import Engine, Session

pc = time.perf_counter
eng = api.default_engine()          # Engine() and the registry warm-up, outside the pass


def replay(hook=None):
    bad = 0
    t0 = pc()
    for i, (p, a, r) in enumerate(stream):
        if hook is not None:
            hook(i)
        try:
            got = api.ask(p, a)
        except ValueError:
            got = "err"
        if got is not r and got != "err":
            bad += 1
    return pc() - t0, bad


if mode in ("default", "disable", "freeze"):
    st = {g: [0, 0, 0.0] for g in range(3)}
    t_start = [0.0]

    def cb(phase, info):
        if phase == "start":
            t_start[0] = pc()
        else:
            s = st[info["generation"]]
            s[0] += 1; s[1] += info["collected"]; s[2] += pc() - t_start[0]
    if mode == "disable":
        gc.disable()
    if mode == "freeze":
        gc.collect(); gc.freeze()
        print(f"frozen objects {gc.get_freeze_count()}")
    gc.callbacks.append(cb)
    dt, bad = replay()
    gc.callbacks.remove(cb)
    tot = sum(s[2] for s in st.values())
    print(f"{mode}: pass {dt:.3f}s, mismatches {bad}; gc thresholds {gc.get_threshold()}")
    for g, (n, c, t) in st.items():
        print(f"  gen{g}: {n:5d} collections, {c:8d} collected, {1000 * t:7.1f} ms ({100 * t / dt:.2f}%)")
    print(f"  in collections {1000 * tot:.1f} ms ({100 * tot / dt:.2f}% of the pass)")

elif mode == "heap":
    def census(label):
        objs = gc.get_objects()
        c = Counter(type(o).__name__ for o in objs)
        print(f"-- {label}: {len(objs)} tracked objects; top types:",
              ", ".join(f"{k} {v}" for k, v in c.most_common(12)))

    def owners():
        sessions = [s for s, _ in eng._context_sessions.values()]
        ncl = sum(len(s.solver._clauses) + len(s.solver._learnts) for s in sessions)
        nw = sum(sum(len(w) for w in s.solver._watches) for s in sessions)
        nslots = sum(len(s.table.slots) for s in sessions)
        print(f"   sessions alive {len(sessions)}: clause lists {ncl}, watch entries {nw}, "
              f"table slots {nslots}; fact cache nodes {len(eng.cache.store)}, "
              f"answer memo {len(eng.answers)}, context-free fact dicts "
              f"{sum(1 for _ in eng.cache.store.values())}")
        from satassume.templates import registry
        from satassume import sympy_api
        print(f"   clauses_for memo {len(registry.default_registry._clauses_cache) if hasattr(registry, 'default_registry') else '?'}, "
              f"to_formula memo {len(sympy_api._FORMULAS)}")
    gc.collect()
    census("after imports")

    def hook(i):
        if i and i % 2000 == 0:
            census(f"before query {i}")
    dt, bad = replay(hook)
    census(f"after the pass ({dt:.2f}s, mismatches {bad})")
    owners()

elif mode == "scan":
    seen = {g: Counter() for g in range(3)}
    ncoll = Counter()

    def kind(o):
        t = type(o)
        if t is list:
            if not o:
                return "list (empty)"
            e = o[0]
            if type(e) is int:
                return "list of int"
            if type(e) is list:
                return "list of lists"
            return "list of " + type(e).__name__
        if t is tuple:
            return "tuple"
        return t.__name__

    def cb(phase, info):
        if phase != "start":
            return
        g = info["generation"]
        ncoll[g] += 1
        c = seen[g]
        for gg in range(g + 1):
            for o in gc.get_objects(gg):
                c[kind(o)] += 1
    gc.callbacks.append(cb)
    dt, bad = replay()
    gc.callbacks.remove(cb)
    print(f"scan: pass {dt:.2f}s (census inside the collections), mismatches {bad}")
    for g in range(3):
        tot = sum(seen[g].values())
        print(f"-- gen{g}: {ncoll[g]} collections, {tot} objects scanned ({tot / max(ncoll[g], 1):.0f} per collection); top kinds:")
        for k, v in seen[g].most_common(12):
            print(f"     {k:28s} {v:9d}  {100 * v / tot:5.1f}%")

elif mode == "paths":
    sys.path.insert(0, "tools")
    import query_log
    query_log.install(False)
    ctx = query_log.ctx
    net = Counter(); gc0 = Counter(); n = Counter(); ms = Counter()
    gc.disable()        # so the gen-0 counter is not reset by collections
    t_all = pc()
    for i, (p, a, r) in enumerate(stream):
        ctx.reset(i); ctx.via = "memo"
        b0 = sys.getallocatedblocks(); g0 = gc.get_count()[0]
        t0 = pc()
        try:
            api.ask(p, a)
        except ValueError:
            pass
        t1 = pc()
        g1 = gc.get_count()[0]; b1 = sys.getallocatedblocks()
        path = "memo" if ctx.via == "memo" else (">".join(ctx.path) or ctx.via)
        net[path] += b1 - b0; gc0[path] += g1 - g0; n[path] += 1; ms[path] += 1000 * (t1 - t0)
        if gc.get_count()[0] > 5_000_000:
            gc.collect(0)
    gc.enable()
    print(f"paths: pass {pc() - t_all:.2f}s (gc off, logging on)")
    print(f"{'path':52s} {'n':>6s} {'ms':>8s} {'net blocks':>11s} {'per q':>7s} {'gc-tracked net':>15s} {'per q':>7s}")
    for k in sorted(n, key=lambda k: -gc0[k]):
        print(f"{k:52s} {n[k]:6d} {ms[k]:8.1f} {net[k]:11d} {net[k] / n[k]:7.0f} {gc0[k]:15d} {gc0[k] / n[k]:7.0f}")
    print(f"{'total':52s} {sum(n.values()):6d} {sum(ms.values()):8.1f} {sum(net.values()):11d} {'':7s} {sum(gc0.values()):15d}")
