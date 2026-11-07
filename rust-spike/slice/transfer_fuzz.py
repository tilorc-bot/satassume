"""transfer_fuzz.py [--seed N] [--rounds N] [--so DIR]: component 3 through its API, Rust against Python, with no engine.

Four parts. `pyset`: `PySetOrder` against real CPython sets, on what `decide` builds. `sharing`: `EqualitySharing`, down
to which of two equal objects comes back. `wanted`: `transfer_wanted`. `theory`: random hook sequences over one real
Python EUF per pair of theories, with the result and full state compared after every call; the sequences respect the
solver's contract (levels balance, a variable is asserted once per level lifetime, one value), and they cover guards,
switches, fixed facts and partial atoms far more densely than the engine does.

Exits nonzero on any difference and prints the smallest case found, shrunk by dropping operations.
"""
import argparse
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--rounds", type=int, default=2000)
ap.add_argument("--so")
ap.add_argument("--only", default="pyset,sharing,wanted,theory")
a = ap.parse_args()
if a.so:
    sys.path.insert(0, a.so)
import sa_solver  # noqa: E402
from satassume.knowledge.rules import BASIS_INDEX, NPRED  # noqa: E402
from satassume.sat.formula import P  # noqa: E402
from satassume.sat.theory import EqualitySharing as PySharing  # noqa: E402
from satassume.theories.euf.euf import EqAtom, EUFTheory  # noqa: E402
from satassume.theories.transfer import TransferTheory as PyT, transfer_wanted as py_wanted  # noqa: E402
import transfer_shadow as X  # noqa: E402

if a.so and os.path.dirname(os.path.abspath(sa_solver.__file__)) != os.path.abspath(a.so):
    sys.exit(f"--so {a.so}: loaded {sa_solver.__file__}")
R = random.Random(a.seed)
fails = {}
ran = {}


def fail(part, case):
    fails.setdefault(part, []).append(case)


def py_order(groups):
    acc = None
    for g in groups:
        s = set()
        for k in g:
            s.add(k)
        acc = s if acc is None else acc | s
    return [] if acc is None else list(acc)


def part_pyset():
    """Every `decide`-shaped set: built by add, unioned left to right. Preds are small; wide values too, for the probes."""
    for n in range(a.rounds * 5):
        top = R.choice([NPRED, NPRED, 8, 16, 40, 300, 70000])
        groups = [[R.randrange(top) for _ in range(R.randrange(1, R.choice([3, 8, 20])))]
                  for _ in range(R.randrange(1, 6))]
        if py_order(groups) != sa_solver._pyset_replay(groups):
            fail("pyset", groups)
    # all pairs and triples of predicates, both insertion orders
    import itertools
    for k in (1, 2, 3):
        for g in itertools.permutations(range(NPRED), k):
            if py_order([list(g)]) != sa_solver._pyset_replay([list(g)]):
                fail("pyset", [list(g)])
    ran["pyset"] = a.rounds * 5


class Eq:
    """Equal by value, different objects: which one comes back is visible."""

    def __init__(self, k, tag):
        self.k, self.tag = k, tag

    def __hash__(self):
        return hash(self.k)

    def __eq__(self, o):
        return isinstance(o, Eq) and self.k == o.k

    def __repr__(self):
        return f"{self.k}#{self.tag}"


def part_sharing():
    tag = 0
    for n in range(a.rounds):
        p, r = PySharing(), sa_solver.EqualitySharing()
        for _ in range(R.randrange(1, 7)):
            sets = []
            for _ in range(R.randrange(0, 4)):
                s = []
                for _ in range(R.randrange(0, 6)):
                    tag += 1
                    s.append(Eq(R.randrange(6), tag))
                sets.append(s)
            # a generator of generators, as `_share` passes
            a1 = p.update(iter(sets))
            a2 = r.update(iter(iter(s) for s in sets))
            key = lambda ps: [(id(x), id(y)) for x, y in ps]
            if key(a1) != key(a2) or list(map(id, p.shared)) != list(map(id, r.shared)):
                fail("sharing", (repr(sets), repr(a1), repr(a2)))
    ran["sharing"] = a.rounds


def part_wanted():
    terms = [("t", i) for i in range(5)]
    for n in range(a.rounds * 5):
        atoms = []
        for _ in range(R.randrange(0, 7)):
            pr = R.choice(["lt", "lt", "lt", "eq", "le", "zero"])
            e = (R.choice(terms), R.choice(terms)) if pr != "zero" else R.choice(terms)
            atoms.append(P(pr, e))
        if R.random() < .2:
            atoms = [x for x in atoms if x.pred != "eq"]
        if py_wanted(iter(atoms)) != sa_solver.transfer_wanted(iter(atoms)):
            fail("wanted", repr(atoms))
    ran["wanted"] = a.rounds * 5


def gen_ops(r, nterm):
    """A list of operations; `replay` skips what the current state makes illegal, so any sublist is a case too."""
    ops = []
    nv = 0
    top = r.choice([NPRED, 3, 2])
    preds = r.sample(range(NPRED), top)
    if r.random() < .6 and BASIS_INDEX["polar"] not in preds:
        preds[0] = BASIS_INDEX["polar"]
    for _ in range(r.randrange(10, 70)):
        c = r.random()
        if c < .28:
            nv += 1
            pl = (r.randrange(nterm), r.choice(preds))
            ops.append(("atom", 1000 + nv, pl + ((True,) if r.random() < .3 else ())))
        elif c < .36:
            ops.append(("switch", r.randrange(nterm), r.choice([0, 500 + r.randrange(12)]), r.choice([0, 600 + r.randrange(12)])))
        elif c < .42:
            ops.append(("fixed", r.randrange(nterm), [(r.choice(preds), r.random() < .5) for _ in range(r.randrange(0, 4))]))
        elif c < .54:
            ops.append(("merge", r.randrange(nterm), r.randrange(nterm)))
        elif c < .72:
            ops.append(("assert", r.choice([1, 2, 3]), r.random() < .6))
        elif c < .80:
            ops.append(("push",))
        elif c < .86:
            ops.append(("pop",))
        elif c < .92:
            ops.append(("prop",))
        elif c < .96:
            ops.append(("check",))
        else:
            ops.append(("decide",))
    return ops, nv


def replay(ops, nterm, guard, rng_seed):
    """Run `ops` on both theories; the first difference, or None."""
    r = random.Random(rng_seed)
    euf = EUFTheory()
    ts = [euf.term(("c", i)) for i in range(nterm)]
    py = PyT(euf)

    class RT(sa_solver.TransferTheory):
        def __init__(self, e):
            self._attach()
    rs = RT(euf)

    def merged(ra, rb):
        py._merged(ra, rb)
        rs._merged(ra, rb)
    euf.on_merge = merged
    sel = 900 if guard else None
    if guard:
        py.guard(sel)
        rs.guard(sel)
    assigned = {}     # var -> (value, level)
    trail = [[]]      # per level, what was asserted
    eqs = {}          # (a, b) -> euf atom var
    nextv = [2000]
    control, atoms = [], []

    def tell(name, *args):
        try:
            x = ("ok", getattr(py, name)(*args))
        except Exception as e:
            x = ("raise", type(e).__name__, str(e))
        try:
            y = ("ok", getattr(rs, name)(*args))
        except BaseException as e:
            y = ("raise", type(e).__name__, str(e))
        if x != y:
            return f"{name}{args}: py {x!r} rust {y!r}"
        dp, dr = X.dump_py(py), dict(rs._dump())
        f = X.first_diff(dp, dr)
        if f:
            return f"{name}{args}: state {f}: py {dp[f]!r} rust {dr[f]!r}"
        return None

    def assert_(v, val):
        assigned[v] = val
        trail[-1].append(v)
        return tell("assert_lit", v if val else -v)
    for op in ops:
        k = op[0]
        d = None
        if k == "atom":
            atoms.append(op[1])
            d = tell("register_atom", op[1], op[2])
        elif k == "switch":
            try:
                new = py.switch(op[1], op[2], op[3])
            except Exception as e:
                return f"py switch raised {e!r}"
            newr = rs.switch(op[1], op[2], op[3])
            if new != newr:
                return f"switch{op[1:]}: py {new} rust {newr}"
            control.extend(new)
            d = tell("__repr__")
        elif k == "fixed":
            if len(trail) == 1:
                d = tell("set_fixed", op[1], op[2])
        elif k == "merge" and op[1] != op[2]:
            pr = (min(op[1], op[2]), max(op[1], op[2]))
            if pr in eqs:
                continue
            v = nextv[0]
            nextv[0] += 1
            eqs[pr] = v
            euf.register_atom(v, EqAtom(ts[pr[0]], ts[pr[1]], True))
            if euf.assert_lit(v) is not None:
                return None
            euf.propagate()
            d = tell("__repr__")
        elif k == "assert":
            pool = {1: atoms, 2: control, 3: [sel] if sel else []}[op[1]]
            free = [v for v in pool if v not in assigned]
            if free:
                d = assert_(r.choice(free), op[2])
        elif k == "push":
            trail.append([])
            euf.push_level()
            d = tell("push_level")
        elif k == "pop" and len(trail) > 1:
            for v in trail.pop():
                assigned.pop(v, None)
            euf.pop_level()
            d = tell("pop_level")
        elif k == "prop":
            d = tell("propagate")
        elif k == "check":
            d = tell("check")
        elif k == "decide":
            d = tell("decide")
        if d:
            return d
    return tell("propagate") or tell("check") or tell("decide")


def part_theory():
    total = 0
    for n in range(a.rounds):
        seed = R.randrange(1 << 30)
        r = random.Random(seed)
        nterm = r.randrange(2, 9)
        guard = r.random() < .5
        ops, _ = gen_ops(r, nterm)
        d = replay(ops, nterm, guard, seed)
        total += len(ops)
        if d:
            i = 0
            while i < len(ops):
                t = ops[:i] + ops[i + 1:]
                if replay(t, nterm, guard, seed):
                    ops = t
                else:
                    i += 1
            fail("theory", dict(seed=seed, nterm=nterm, guard=guard, ops=ops, diff=replay(ops, nterm, guard, seed)))
    ran["theory"] = a.rounds
    ran["theory ops"] = total


for part in a.only.split(","):
    globals()["part_" + part]()
print("ran", ran)
for part, cs in fails.items():
    print(part, len(cs), "differences; smallest:", min(cs, key=lambda c: len(repr(c))))
sys.exit(1 if fails else 0)
