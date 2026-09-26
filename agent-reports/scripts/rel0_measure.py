"""Relevance plan (next-steps item 3), stage 0: how much of the refine
stream's time could "use only the assumptions connected to the query" save.

    PYTHONHASHSEED=0 PYTHONPATH=.:SYMPY python rel0_measure.py CMD STREAM [args]

Run from a satassume checkout; nothing in ``satassume/`` changes.

Commands:

``struct STREAM OUT.json``
    Structure only (no timings): per query, the assumption conjuncts split
    into components by shared keys (transitively), the query's component,
    and the sizes (nodes, solver variables, clauses) of a fresh session
    built for the whole set and for the component.  Session keys whole vs
    component.  Writes per-query rows (``OUT.json``) for ``logsplit``.

``logsplit LOG OUT.json``
    Joins a per-query log (``tools/refine_replay.py --log``) with the rows
    of ``struct``: time in queries ending None vs definite, time in queries
    whose component is strictly smaller.

``replay STREAM MODE``
    One cold pass of the stream in a fresh process, in stream order,
    through ``satassume.sympy_api.ask``; prints the wall time and the
    answers that differ from the recording.  MODE:
      ``base``   ask(p, a) as today;
      ``comp``   a model of the design without the consistency check: a
                 memo on (p, a) first, then ask(p, component) (so the
                 engine's answer memo and sessions are keyed by the
                 component); the split is memoized per assumption object
                 and its cost is inside the timing;
      ``check``  ``comp`` plus the design's consistency check: the first
                 time a whole set is used by a query whose component is
                 strictly smaller, a fresh session is built for the whole
                 set and its assumption literals propagated
                 (``Solver.implied``, what ``Session.query_literal`` checks
                 before answering); the check's time is also printed;
      ``fullcheck``  as ``check`` but the check is a complete SAT call
                 (``Solver.solve``) after the propagation;
      ``emptyonly``  as ``check``, but only a query whose component is
                 empty drops its assumptions (it goes context-free);
      ``nonempty``   as ``check``, but only a non-empty strictly smaller
                 component replaces the whole set.
    With ``REL0_DIFFS=path`` the stream indices whose answer differs from
    the recording are written there (JSON list).

``cold STREAM [LIMIT]``
    For every distinct (p, a) whose component is strictly smaller: ask in
    a fresh Engine with the whole set, and in another fresh Engine with the
    component; sums of both times (each a median of 3).

Keys of an expression: its free symbols plus the classes of its undefined
function applications (``f(1)`` and ``f(x)`` share ``f``; EUF congruence
can connect them).  Numbers are interpreted, so they connect nothing.  A
conjunct with no keys (``Q.positive(pi)``, ``Eq(f, g)`` over constants) is
in no component; a query with no keys has an empty component.
"""
from __future__ import annotations

import json
import pickle
import statistics
import sys
import time
from collections import Counter

from sympy import And
from sympy.core.function import AppliedUndef
from sympy.logic.boolalg import BooleanTrue

import satassume.sympy_api as api


# ---------------------------------------------------------------------------
# components

def conjuncts(a):
    if a is True or a is None or isinstance(a, BooleanTrue):
        return ()
    return tuple(a.args) if isinstance(a, And) else (a,)


_KEYS: dict = {}


def keys(e) -> frozenset:
    k = _KEYS.get(e)
    if k is None:
        k = frozenset(e.free_symbols) | frozenset(type(f) for f in e.atoms(AppliedUndef))
        _KEYS[e] = k
    return k


_SPLIT: dict = {}


def split(a):
    """Components of ``a``'s conjuncts: list of (keys, tuple of conjuncts);
    conjuncts without keys are dropped (they belong to no component)."""
    r = _SPLIT.get(a)
    if r is not None:
        return r
    comps = []          # [keys set, list of conjuncts]
    for c in conjuncts(a):
        k = set(keys(c))
        if not k:
            continue
        merged = [k, [c]]
        rest = []
        for comp in comps:
            if comp[0] & merged[0]:
                merged[0] |= comp[0]
                merged[1] = comp[1] + merged[1]
            else:
                rest.append(comp)
        rest.append(merged)
        comps = rest
    r = [(frozenset(k), tuple(cs)) for k, cs in comps]
    _SPLIT[a] = r
    return r


_COMP: dict = {}


def component(p, a):
    """``(formula, conjunct tuple, n_components)`` of the query's component
    (formula True if empty); the formula is ``a`` itself when the component
    is the whole set."""
    comps = split(a)
    pk = keys(p)
    mine = tuple(sorted((i for i, (k, _) in enumerate(comps) if k & pk)))
    key = (a, mine)
    hit = _COMP.get(key)
    if hit is not None:
        return hit if hit[0] is not None else (a, hit[1], hit[2])
    cs = tuple(c for i in mine for c in comps[i][1])
    if len(cs) == len(conjuncts(a)):
        f = None        # the whole set (the caller's own object)
    elif not cs:
        f = True
    else:
        f = And(*cs)
    hit = (f, cs, len(comps))
    _COMP[key] = hit
    return hit if f is not None else (a, cs, len(comps))


def smaller(a, f) -> bool:
    return f is not a and bool(conjuncts(a))


# ---------------------------------------------------------------------------
# struct

def session_size(f):
    """(nodes, vars, clauses) of a fresh session with ``f`` assumed; None if
    no session (True) or it raised."""
    if f is True:
        return (0, 0, 0)
    eng = api.default_engine()
    try:
        g = api._formula(f, bool(eng.relation_specs))
    except api.Unsupported:
        return None
    try:
        s = eng._fresh_session()
        s.assume_formula(g)
        s.solver.propagate()
    except Exception as ex:  # Uninterpreted, inconsistent
        return type(ex).__name__
    sv = s.solver
    return (len(s.base), sv._nvars, len(sv._clauses))


def cmd_struct(stream, out):
    rows = []
    sizes = {}
    whole_keys, comp_keys = set(), set()
    ncomp_hist = Counter()
    for i, (p, a, r) in enumerate(stream):
        if api._is_constant_proposition(p):
            rows.append({"i": i, "kind": "constant"})
            continue
        n = len(conjuncts(a))
        if n == 0:
            rows.append({"i": i, "kind": "noassum"})
            continue
        f, cs, ncomp = component(p, a)
        sm = smaller(a, f)
        for x in (a, f):
            if x not in sizes:
                sizes[x] = session_size(x)
        whole_keys.add(a)
        comp_keys.add(f)
        ncomp_hist[ncomp] += 1
        rows.append({"i": i, "kind": "assum", "n": n, "ncomp": ncomp, "nc": len(cs),
                     "smaller": sm, "empty": f is True,
                     "whole": sizes[a], "comp": sizes[f]})
    json.dump(rows, open(out, "w"))
    ar = [x for x in rows if x["kind"] == "assum"]
    sm = [x for x in ar if x["smaller"]]
    print(f"queries {len(rows)}; constant {sum(x['kind']=='constant' for x in rows)}; "
          f"no assumptions {sum(x['kind']=='noassum' for x in rows)}; with assumptions {len(ar)}")
    print(f"components per set (by query): {dict(sorted(ncomp_hist.items()))}")
    print(f"component strictly smaller: {len(sm)} ({100*len(sm)/len(ar):.1f}%), "
          f"of which empty: {sum(x['empty'] for x in sm)}")
    print(f"distinct session keys: whole {len(whole_keys)}, component {len(comp_keys)} "
          f"(of them True: {int(True in comp_keys)})")
    dist_sm = {stream[x['i']][1] for x in sm}
    print(f"distinct whole sets used by a strictly-smaller query: {len(dist_sm)}")
    bad = Counter(type(x["whole"]).__name__ for x in ar if not isinstance(x["whole"], (list, tuple)))
    print(f"whole-set sessions not built (by query): {dict(bad)}")
    for lab, sel in (("all queries with assumptions", ar), ("strictly smaller", sm)):
        ok = [x for x in sel if isinstance(x["whole"], (list, tuple)) and isinstance(x["comp"], (list, tuple))]
        if not ok:
            continue
        print(f"{lab} ({len(ok)} with both sizes):")
        for j, nm in enumerate(("nodes", "vars", "clauses")):
            w = sum(x["whole"][j] for x in ok)
            c = sum(x["comp"][j] for x in ok)
            print(f"  {nm:8s} whole mean {w/len(ok):7.1f} median {statistics.median(x['whole'][j] for x in ok):6.0f}"
                  f" | comp mean {c/len(ok):7.1f} median {statistics.median(x['comp'][j] for x in ok):6.0f}"
                  f" | comp/whole {c/w if w else 0:.3f}")
    # distinct whole sets: sizes (for the consistency-check estimate)
    ws = [sizes[a] for a in whole_keys if isinstance(sizes[a], tuple)]
    print(f"distinct whole sets {len(whole_keys)}; built {len(ws)}; nodes mean "
          f"{sum(s[0] for s in ws)/len(ws):.1f}, clauses mean {sum(s[2] for s in ws)/len(ws):.1f}")


# ---------------------------------------------------------------------------
# logsplit

def cmd_logsplit(log, struct_json):
    rows = {x["i"]: x for x in json.load(open(struct_json))}
    log = [json.loads(line) for line in open(log)]
    tot = sum(r["ms"] for r in log)
    print(f"logged queries {len(log)}, {tot:.0f} ms")
    by = Counter()
    n = Counter()
    for r in log:
        o = r["outcome"]
        k = "None" if o is None else ("error" if o == "error" else "definite")
        by[k] += r["ms"]
        n[k] += 1
    for k in by:
        print(f"  outcome {k:9s} {n[k]:6d} queries {by[k]:8.0f} ms {100*by[k]/tot:5.1f}%")
    grp = Counter()
    gn = Counter()
    for r in log:
        x = rows[r["i"]]
        if x["kind"] != "assum":
            k = x["kind"]
        elif x["smaller"]:
            k = "smaller-empty" if x["empty"] else "smaller"
        else:
            k = "whole"
        k2 = k + (" /memo" if r["via"] == "memo" else "")
        grp[k2] += r["ms"]
        gn[k2] += 1
        o = r["outcome"]
        if k.startswith("smaller"):
            grp["smaller: outcome " + ("None" if o is None else "definite")] += r["ms"]
            gn["smaller: outcome " + ("None" if o is None else "definite")] += 1
            if r.get("session_new") in ("first", "evicted", "cone") or r.get("built"):
                grp["smaller: built a session"] += r["ms"]
                gn["smaller: built a session"] += 1
    for k in sorted(grp):
        print(f"  {k:28s} {gn[k]:6d} queries {grp[k]:8.0f} ms {100*grp[k]/tot:5.1f}%")


# ---------------------------------------------------------------------------
# replay

def cmd_replay(stream, mode):
    eng = api.default_engine()
    rel = bool(eng.relation_specs)
    ask = api.ask
    checked = {}
    memo = {}
    tcheck = [0.0]
    ncheck = [0]

    def check(a):
        t0 = time.perf_counter()
        ncheck[0] += 1
        try:
            g = api._formula(a, rel)
            s = eng._fresh_session()
            lits = s.assume_formula(g)
            ok = s.solver.propagate() and s.solver.implied(lits) is not None
            if ok and mode == "fullcheck":
                ok = s.solver.solve(lits)
        except api.Unsupported:
            ok = True
        except Exception as ex:
            ok = type(ex).__name__ != "InconsistentAssumptions"
        checked[a] = ok
        tcheck[0] += time.perf_counter() - t0
        return ok

    def ask_rel(p, a):
        key = (p, a)
        r = memo.get(key, memo)
        if r is not memo:
            return r
        if api._is_constant_proposition(p) or not conjuncts(a):
            r = ask(p, a)
        else:
            f = component(p, a)[0]
            if (mode == "emptyonly" and f is not True) or (mode == "nonempty" and f is True):
                f = a
            if f is not a and mode != "comp":
                ok = checked.get(a)
                if ok is None:
                    ok = check(a)
                if not ok:
                    raise ValueError("inconsistent assumptions")
            r = ask(p, f)
        memo[key] = r
        return r

    fn = ask if mode == "base" else ask_rel
    diff = Counter()
    diff_i = []
    t0 = time.perf_counter()
    for i, (p, a, r) in enumerate(stream):
        try:
            got = fn(p, a)
        except ValueError:
            got = "error"
        if got is not r:
            diff[(r, got)] += 1
            diff_i.append(i)
    dt = time.perf_counter() - t0
    import os
    if os.environ.get("REL0_DIFFS"):
        json.dump(diff_i, open(os.environ["REL0_DIFFS"], "w"))
    print(json.dumps({"mode": mode, "s": round(dt, 4), "check_s": round(tcheck[0], 4),
                      "checks": ncheck[0], "stats": eng.stats, "diff": {f"{k[0]}->{k[1]}": v for k, v in diff.items()}}))


# ---------------------------------------------------------------------------
# cold

def cmd_cold(stream, limit=None):
    from satassume.engine import Engine
    seen = set()
    pairs = []
    for p, a, r in stream:
        if api._is_constant_proposition(p) or not conjuncts(a) or (p, a) in seen:
            continue
        seen.add((p, a))
        f = component(p, a)[0]
        if f is not a:
            pairs.append((p, a, f))
    if limit:
        pairs = pairs[:limit]
    Engine()     # warm the template registry

    def one(p, x):
        best = []
        for _ in range(3):
            eng = Engine()
            t0 = time.perf_counter()
            try:
                api.ask(p, x, engine=eng)
            except ValueError:
                pass
            best.append(time.perf_counter() - t0)
        return statistics.median(best)
    tw = tc = 0.0
    for p, a, f in pairs:
        tw += one(p, a)
        tc += one(p, f)
    print(json.dumps({"pairs": len(pairs), "whole_s": round(tw, 4), "comp_s": round(tc, 4),
                      "saving": round(1 - tc / tw, 4) if tw else None}))


def main():
    cmd = sys.argv[1]
    if cmd == "logsplit":
        return cmd_logsplit(sys.argv[2], sys.argv[3])
    stream = pickle.load(open(sys.argv[2], "rb"))
    if cmd == "struct":
        cmd_struct(stream, sys.argv[3])
    elif cmd == "replay":
        cmd_replay(stream, sys.argv[3])
    elif cmd == "cold":
        cmd_cold(stream, int(sys.argv[3]) if len(sys.argv) > 3 else None)


if __name__ == "__main__":
    main()
