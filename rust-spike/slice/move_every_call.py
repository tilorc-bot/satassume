"""Planner's condition 2, a test-only use of the transfer: move an LRA session to Python before every call index.

  move_every_call.py count WL OUT                  every query, unforced; OUT.counts has (q, hook calls on a live core)
  move_every_call.py run WL COUNTS OUT [--shard I/N] [--stride K] one child per (q, G): moved before live-core call G
  move_every_call.py cmp REF OUT...                 against Python's rows from `live.py WL py` on this same tree

G counts hook calls on any live core in that query, so it covers every session of the query, and a move fires once.
Each child is a fresh engine: `live.py --fork`, forked after import. Goes away with the transfer, no later than 1b.
"""
import json
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
HOOKS = ("register_atom", "assert_lit", "check", "propagate", "push_level", "pop_level")


class S:
    g = -1
    n = 0
    fired = False


class Item:
    def __init__(self, q, g, p):
        self.q, self.g, self.p = q, g, p


def forced_class(base):
    def hook(name):
        f = getattr(base, name)

        def w(self, *a):
            if self.__dict__.get("_core") is not None:
                if S.n == S.g and not S.fired:
                    S.fired = True
                    self._move("forced")
                S.n += 1
            return f(self, *a)
        w.__name__ = name
        return w
    return type("LRATheory", (base,), {n: hook(n) for n in HOOKS})


def drive(wl, out, items, on_end=None):
    """Runs `items` as (q, g) through live.py's main, each row numbered by its place in `items`."""
    import live
    import lra_backend
    from satassume import sympy_api
    lra_backend.LRATheory = forced_class(lra_backend.LRATheory)
    pairs = live.load(wl)
    live.load = lambda _: [(Item(q, g, pairs[q][0]), pairs[q][1]) for q, g in items]
    real = sympy_api.ask

    def ask(item, a):
        S.g, S.n, S.fired = item.g, 0, False
        try:
            return real(item.p, a)
        finally:
            if on_end:
                on_end(item, S.n)
    sympy_api.ask = ask
    sys.argv = ["live.py", wl, "rust", out, "--check", "entry", "--fork"]
    live.main()


def count(wl, out):
    import live
    n = len(live.load(wl))
    with open(out + ".counts", "w") as f:
        def end(item, c):
            f.write(json.dumps([item.q, c]) + "\n")
            f.flush()
        drive(wl, out, [(q, -1) for q in range(n)], end)


def run(wl, counts, out, shard, stride):
    i, n = shard
    items = []
    for q, c in sorted(json.loads(x) for x in open(counts)):
        items += [(q, g) for g in range(0, c, stride)]
    items = items[i::n]
    json.dump(items, open(out + ".items", "w"))
    drive(wl, out, items)


def cmp(ref, outs):
    py = {}
    for x in open(ref):
        r = json.loads(x)
        if "q" in r:
            py[r["q"]] = r
    tot = dict(runs=0, moved=0, moved_level_gt0=0, not_fired=0, missing=0, ans=0, msg=0, sessions=0, end=0, stream=0,
               lra=0, queries=set(), raised=0)
    first = []
    levels = {}
    for out in outs:
        items = json.load(open(out + ".items"))
        rows = {}
        for x in open(out):
            r = json.loads(x)
            if "q" in r:
                rows[r["q"]] = r
        for k, (q, g) in enumerate(items):
            r, p = rows.get(k), py[q]
            if r is None:
                tot["missing"] += 1
                first.append((q, g, "row missing"))
                continue
            tot["runs"] += 1
            tot["queries"].add(q)
            forced = [s for s in r["sessions"] if (s["group"] or "").startswith("moved:forced")]
            if forced:
                tot["moved"] += 1
                lev = int(forced[0]["group"].split(":")[3])
                levels[lev] = levels.get(lev, 0) + 1
                tot["moved_level_gt0"] += lev > 0
            else:
                tot["not_fired"] += 1
            bad = []
            if r["ans"] != p["ans"]:
                tot["ans"] += 1
                bad.append(f"ans {p['ans']} {r['ans']}")
            if r["msg"] != p["msg"]:
                tot["msg"] += 1
                tot["raised"] += r["ans"] == "raise" or str(r["ans"]).startswith("raise")
                bad.append(f"msg {r['msg'][:120]}")
            if len(r["sessions"]) != len(p["sessions"]):
                tot["sessions"] += 1
                bad.append("session count")
            for a, b in zip(p["sessions"], r["sessions"]):
                for f, key in (("end", "end"), ("stream", "stream"), ("lra", "lra")):
                    if a[key] != b[key]:
                        tot[f] += 1
                        bad.append(f)
            if bad:
                first.append((q, g, sorted(set(bad))))
    tot["queries"] = len(tot["queries"])
    print(json.dumps(tot))
    print("levels at move:", dict(sorted(levels.items())))
    print("differences:", len(first))
    for x in first[:12]:
        print(" ", x)
    print("MATCH" if not first else "DIFFER")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "count":
        count(a[1], a[2])
    elif a[0] == "run":
        shard, stride = (0, 1), 1
        if "--shard" in a:
            shard = tuple(int(x) for x in a[a.index("--shard") + 1].split("/"))
        if "--stride" in a:
            stride = int(a[a.index("--stride") + 1])
        run(a[1], a[2], a[3], shard, stride)
    else:
        cmp(a[1], a[2:])
