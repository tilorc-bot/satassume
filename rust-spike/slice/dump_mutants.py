"""Planner's condition 3: drop or corrupt each field of the transfer's dump in turn, through the real engine.

  dump_mutants.py profile WL COUNTS OUT           which fields are non-empty at the move, three call indices per query
  dump_mutants.py run NAME WL ITEMS OUT           one mutant over ITEMS, a JSON list of [q, g]
  dump_mutants.py list                            mutant names
  dump_mutants.py score REF DIR                   caught, by what; "effective" is how many runs it really changed

A mutant is applied once, to the dump of the forced move. Test-only: goes with the transfer, no later than 1b.
"""
import json
import os
import signal
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import move_every_call as M  # noqa: E402

FIELDS = ("_key", "_var_of", "_slack_of", "_forms", "_lo", "_up", "_lo_r", "_up_r", "_vq", "_vd", "_rows", "_cols",
          "_atoms", "_ground", "_atoms_on", "_assigned", "_diseqs", "_ints", "_ints_on", "_int_lits", "_trail", "_lims",
          "_dirty", "_pending_ground", "_py_exhausted", "_py_branched", "_py_stats")
TIMEOUT = 30


def rev(x):
    """Reversed insertion order; False if that's no change."""
    if len(x) < 2:
        return None
    return dict(reversed(list(x.items()))) if isinstance(x, dict) else list(reversed(x))


def lose(x):
    if not x:
        return None
    if isinstance(x, dict):
        return dict(list(x.items())[:-1])
    if isinstance(x, set):
        return set(sorted(x)[:-1])
    return x[:-1]


def first(x, pred=lambda _: True):
    for i, v in enumerate(x):
        if pred(v):
            return i
    return None


def on_list(f, pred=lambda _: True):
    def g(x):
        i = first(x, pred)
        if i is None:
            return None
        y = list(x)
        y[i] = f(y[i])
        return y
    return g


def on_last_key(f):
    def g(x):
        if not x:
            return None
        y = dict(x)
        k = list(y)[-1]
        y[k] = f(y[k])
        return y
    return g


def nested(f):
    """f on the first inner list or dict that f changes."""
    def g(x):
        keys = list(x) if isinstance(x, dict) else range(len(x))
        for k in keys:
            r = f(x[k])
            if r is not None:
                y = dict(x) if isinstance(x, dict) else list(x)
                y[k] = r
                return y
        return None
    return g


def row_coeff(r):
    if not r:
        return None
    y = dict(r)
    k = next(iter(y))
    y[k] += 1
    return y


def identity(x):
    """Equal to `_ONE`/`_ZERO`, and not them."""
    from satassume.theories.lra.lra import _ONE, _ZERO

    def same(m, k):
        return m is _ONE and k is _ZERO
    if isinstance(x, dict):
        y = {a: (v, Fraction(1), Fraction(0)) if same(m, k) else (v, m, k) for a, (v, m, k) in x.items()}
        return y if any(same(*x[a][1:]) for a in x) else None
    y = [(v, Fraction(1), Fraction(0), lit) if same(m, k) else (v, m, k, lit) for v, m, k, lit in x]
    return y if any(same(m, k) for _, m, k, _l in x) else None


MUT = {}
for _f in FIELDS:
    MUT["drop:" + _f] = (_f, "drop")
for _f in ("_var_of", "_slack_of", "_forms", "_rows", "_atoms", "_ground", "_assigned", "_ints", "_ints_on", "_diseqs",
           "_int_lits", "_trail", "_lims", "_pending_ground"):
    MUT["order:" + _f] = (_f, rev)
MUT["order:_atoms_on_inner"] = ("_atoms_on", nested(rev))
MUT["order:_ints_on_inner"] = ("_ints_on", nested(rev))
MUT["order:_rows_inner"] = ("_rows", nested(rev))
for _f in ("_var_of", "_slack_of", "_forms", "_rows", "_atoms", "_ground", "_assigned", "_diseqs", "_ints", "_ints_on",
           "_int_lits", "_trail", "_lims", "_pending_ground", "_dirty"):
    MUT["lose:" + _f] = (_f, lose)
MUT["lose:_cols_inner"] = ("_cols", nested(lambda c: lose(c) if c else None))
MUT["lose:_atoms_on_inner"] = ("_atoms_on", nested(lambda c: lose(c) if c else None))
MUT["value:_lo"] = ("_lo", on_list(lambda _: None, lambda v: v is not None))
MUT["value:_up"] = ("_up", on_list(lambda _: None, lambda v: v is not None))
MUT["value:_lo_r"] = ("_lo_r", on_list(lambda v: v + 1, lambda v: v != 0))
MUT["value:_up_r"] = ("_up_r", on_list(lambda v: v + 1, lambda v: v != 0))
MUT["value:_vq"] = ("_vq", on_list(lambda v: v + 1))
MUT["value:_vd"] = ("_vd", on_list(lambda v: v + 1))
MUT["value:_rows"] = ("_rows", nested(row_coeff))
MUT["value:_atoms"] = ("_atoms", on_last_key(lambda a: (a[0], a[1], a[2] + 1)))
MUT["value:_ground"] = ("_ground", on_last_key(lambda v: not v))
MUT["value:_assigned"] = ("_assigned", on_last_key(lambda v: not v))
MUT["value:_ints"] = ("_ints", on_last_key(lambda a: (a[0], a[1] + 1, a[2])))
MUT["value:_int_lits"] = ("_int_lits", on_list(lambda a: (a[0], a[1], a[2] + 1, a[3])))
MUT["value:_diseqs"] = ("_diseqs", on_list(lambda a: (a[0], a[1] + 1, a[2])))
MUT["value:_trail"] = ("_trail", lambda x: x + x[-1:] if x else None)
MUT["value:_lims"] = ("_lims", on_list(lambda v: v + 1))
MUT["value:_dirty"] = ("_dirty", lambda x: x | {0} if 0 not in x else None)
MUT["value:_key"] = ("_key", on_list(lambda _: None, lambda v: v is not None))
MUT["value:_py_exhausted"] = ("_py_exhausted", lambda v: not v)
MUT["value:_py_branched"] = ("_py_branched", lambda v: not v)
MUT["value:_py_stats"] = ("_py_stats", lambda s: {**s, "pivots": s["pivots"] + 1})
MUT["identity:_ints"] = ("_ints", identity)
MUT["identity:_int_lits"] = ("_int_lits", identity)


def mutating_class(base, name, log):
    field, how = MUT[name] if name else (None, None)

    def _state(self):
        st = base._state(self)
        if M.S.fired and not M.S.mutated:
            M.S.mutated = True
            if name is None:
                log(sorted(k for k in FIELDS if st.get(k)))
            elif how == "drop":
                del st[field]
                log(True)
            else:
                r = how(st[field])
                if r is not None:
                    st[field] = r
                log(r is not None)
        return st
    return type("LRATheory", (base,), {"_state": _state})


def go(name, wl, items, out):
    import lra_backend
    M.S.mutated = False
    side = open(out + ".eff", "a")
    cur = {}

    def log(x):
        side.write(json.dumps([cur.get("q"), cur.get("g"), x]) + "\n")
        side.flush()
    lra_backend.LRATheory = mutating_class(lra_backend.LRATheory, name, log)
    json.dump(items, open(out + ".items", "w"))
    from satassume import sympy_api
    real = sympy_api.ask

    def timed(p, a):
        cur.update(q=M.S.q, g=M.S.g)
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("hang")))
        signal.alarm(TIMEOUT)
        try:
            return real(p, a)
        finally:
            signal.alarm(0)
    sympy_api.ask = timed
    M.drive(wl, out, [tuple(x) for x in items])


def score(ref, d):
    py = {}
    for x in open(ref):
        r = json.loads(x)
        if "q" in r:
            py[r["q"]] = r
    res = {}
    for name in MUT:
        out = os.path.join(d, name.replace(":", "_") + ".jsonl")
        if not os.path.exists(out + ".items"):
            continue
        items = json.load(open(out + ".items"))
        rows = {}
        for x in open(out):
            r = json.loads(x)
            if "q" in r:
                rows[r["q"]] = r
        eff = sum(1 for x in open(out + ".eff") if json.loads(x)[2]) if os.path.exists(out + ".eff") else 0
        kinds, firstq = {}, None
        for k, (q, g) in enumerate(items):
            r, p = rows.get(k), py[q]
            hit = []
            if r is None:
                hit = ["died"]
            else:
                if r["ans"] != p["ans"]:
                    hit.append("raise" if str(r["ans"]).startswith("raise") else "ans")
                if len(r["sessions"]) != len(p["sessions"]):
                    hit.append("sessions")
                for a, b in zip(p["sessions"], r["sessions"]):
                    hit += [f for f in ("end", "stream", "lra") if a[f] != b[f]]
            for h in set(hit):
                kinds[h] = kinds.get(h, 0) + 1
            if hit and firstq is None:
                firstq = (q, g, sorted(set(hit))[:4])
        res[name] = dict(runs=len(items), effective=eff, caught=bool(kinds), kinds=kinds, first=firstq)
    json.dump(res, open(os.path.join(d, "score.json"), "w"), indent=0)
    caught = [n for n, v in res.items() if v["caught"]]
    idle = [n for n, v in res.items() if not v["effective"] and not v["caught"]]
    missed = [n for n, v in res.items() if v["effective"] and not v["caught"]]
    only_raise = [n for n in caught if set(res[n]["kinds"]) <= {"raise", "died"}]
    print(f"mutants {len(res)} caught {len(caught)} missed {len(missed)} never effective {len(idle)}; caught only by a raise: {len(only_raise)}")
    print("MISSED:", missed)
    print("NEVER EFFECTIVE:", idle)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "list":
        print("\n".join(MUT))
    elif a[0] == "profile":
        items = []
        for q, c in sorted(json.loads(x) for x in open(a[2])):
            if c > 1:
                items += sorted({(q, c // 3), (q, 2 * c // 3), (q, c - 1)})
        go(None, a[1], items, a[3])
    elif a[0] == "run":
        go(a[1], a[2], json.load(open(a[3])), a[4])
    else:
        score(a[1], a[2])
