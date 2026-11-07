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
ap.add_argument("--only", default="basis,pyset,sharing,wanted,wanted_edge,p,theory")
a = ap.parse_args()
if a.so:
    sys.path.insert(0, a.so)
import sa_solver  # noqa: E402
from satassume.knowledge.rules import BASIS_INDEX, NPRED  # noqa: E402
from satassume.knowledge.extensions import Args  # noqa: E402
from satassume.sat.formula import And, Implies, Not, Or, P  # noqa: E402
from satassume.sat.theory import EqualitySharing as PySharing  # noqa: E402
from satassume.theories.euf.euf import EqAtom, EUFTheory  # noqa: E402
from satassume.theories.transfer import TransferTheory as PyT, transfer_wanted as py_wanted  # noqa: E402
import transfer_shadow as X  # noqa: E402

# Before any read: a theory built without the offline data must refuse, not guess polar's index.
try:
    sa_solver.TransferTheory(EUFTheory())
    UNREAD = "built"
except RuntimeError:
    UNREAD = "refused"
import sympy  # noqa: E402
import satassume  # noqa: E402

sa_solver.read_offline(os.path.join(HERE, "offline_data.json"),
                       os.path.dirname(os.path.dirname(os.path.abspath(satassume.__file__))), sympy.__version__)

if a.so and os.path.dirname(os.path.abspath(sa_solver.__file__)) != os.path.abspath(a.so):
    sys.exit(f"--so {a.so}: loaded {sa_solver.__file__}")
R = random.Random(a.seed)
fails = {}
ran = {}
known = []


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


def part_basis():
    """Polar's index as read from component D's file, against Python's `BASIS_INDEX`."""
    got = sa_solver._polar_index()
    print(f"basis: polar {got}, Python {BASIS_INDEX['polar']}, unread theory {UNREAD}")
    if got != BASIS_INDEX["polar"] or UNREAD != "refused":
        raise SystemExit("basis: differs")


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


def obs(fn, text=True):
    """What a call does, down to the exception's text. `text=False` for a constructor's argument errors, whose name differs."""
    try:
        return ("ok", fn())
    except BaseException as e:
        return ("raise", type(e).__name__, str(e) if text else "")


class Raises:
    def __hash__(self):
        return 7

    def __eq__(self, o):
        raise ZeroDivisionError("from __eq__")

    def __repr__(self):
        return "Raises"


class Fmt:
    def __init__(self, out):
        self.out = out

    def __format__(self, spec):
        return self.out


class StrSub(str):
    def __format__(self, spec):
        return "formatted"


class InstFmt:
    """`__format__` on the instance: an f-string looks on the type, so this one must not be called."""

    def __init__(self):
        self.__format__ = lambda spec: "instance"

    def __repr__(self):
        return "InstFmt"


class BadBool:
    def __hash__(self):
        return 3

    def __eq__(self, o):
        return self

    def __bool__(self):
        raise ZeroDivisionError("from __bool__")


class Cycle:
    pass


def shape(x):
    """A value comparable across the two `P` classes: the class by name, the rest by repr."""
    return (type(x).__name__, repr(x))


# The differences that stay, by exact row, each named in formula_py.rs and in the report. Printed on every run and don't fail
# it, so anything else does. Smallest cases: `is_dataclass(P)`, `P("a", 1).__dict__`, a `pickle.loads` of bytes written by
# Python's class, and a subclass with a `pred` property (Python refuses to build it, Rust builds it and ignores the property).
KNOWN = {"is_dataclass", "instance dict", "subclass overriding a field",
         *(f"pickle {i} written by Python's" for i in range(6))}


def part_p():
    """`sa_solver.P` against Python's `P`, on everything visible. One row per behaviour; both classes get the same objects."""
    import copy
    import gc
    import pickle
    import weakref
    Y = sa_solver.P
    nan = float("nan")
    values = [1, 1.0, True, 0, -1, 2 ** 64, 1.5, nan, float("nan"), "a", "eq", "", b"a", None, (), (1, 2), (1, (2, 3)),
              frozenset({1}), "\ud800", [1], {}, {1}, Args((1, 2)), Args((2, 1)), Raises(), BadBool(), Fmt("f"), Fmt(5), StrSub("s"),
              InstFmt(), object()]
    preds = ["a", "lt", "eq", StrSub("a"), 1, None, [1]]
    n = 0

    def row(name, f):
        nonlocal n
        n += 1
        x, y = obs(lambda: f(P)), obs(lambda: f(Y))
        if x != y:
            (known.append if name in KNOWN else lambda c: fail("p", c))((name, x, y))

    # construction: the error's class is compared; the text names __init__ on one and __new__ on the other
    for name, f in [("no args", lambda C: C()), ("one", lambda C: C("a")), ("three", lambda C: C("a", 1, 2)),
                    ("bad kw", lambda C: C("a", 1, z=2)), ("kw", lambda C: shape(C(expr=1, pred="a")))]:
        n += 1
        x, y = obs(lambda: f(P), False), obs(lambda: f(Y), False)
        if x != y:
            fail("p", ("construct " + name, x, y))

    for pr in preds:
        for v in values:
            tag = f"{pr!r}/{type(v).__name__}"
            row("hash " + tag, lambda C: hash(C(pr, v)))
            row("repr " + tag, lambda C: repr(C(pr, v)))
            row("str " + tag, lambda C: str(C(pr, v)))
            row("fields " + tag, lambda C: (C(pr, v).pred is pr, C(pr, v).expr is v))
            row("self eq " + tag, lambda C: (lambda q: (q == q, q != q))(C(pr, v)))
            row("copy eq " + tag, lambda C: (C(pr, v) == C(pr, v), C(pr, v) != C(pr, v)))
            row("copy " + tag, lambda C: (lambda q: (type(copy.copy(q)) is C, copy.copy(q).expr is v))(C(pr, v)))

    # `==` across every pair, both ways: 1 and 1.0, NaN by identity, a raising __eq__, a __bool__ that raises
    for v in values:
        for w in values:
            tag = f"{type(v).__name__}/{type(w).__name__}"
            row("eq " + tag, lambda C: (C("a", v) == C("a", w), C("a", v) != C("a", w)))
            row("set " + tag, lambda C: len({C("a", v), C("a", w)}))
    row("eq pred", lambda C: C("a", 1) == C("b", 1))
    for other in [1, "a", None, ("a", 1), Raises()]:
        row("eq other", lambda C: (C("a", 1) == other, other == C("a", 1), C("a", 1) != other))

    # the class check, and what it reads: `other.__class__`, then `other.pred`, on a non-instance that says it's a P
    class Liar:
        pred, expr = "a", 1

        def __init__(self, C):
            self.C = C

        @property
        def __class__(self):
            return self.C

    row("eq liar", lambda C: (C("a", 1) == Liar(C), Liar(C) == C("a", 1), C("a", 2) == Liar(C)))

    PS, YS = type("Sub", (P,), {}), type("Sub", (Y,), {})

    def sub(f):
        nonlocal n
        n += 1
        x, y = obs(lambda: f(P, PS)), obs(lambda: f(Y, YS))
        if x != y:
            (known.append if "subclass " + f.__doc__ in KNOWN else lambda c: fail("p", c))(("subclass " + f.__doc__, x, y))

    def s1(C, S):
        "eq"
        return (S("a", 1) == C("a", 1), C("a", 1) == S("a", 1), S("a", 1) == S("a", 1), hash(S("a", 1)) == hash(C("a", 1)))

    def s2(C, S):
        "repr, type, fields"
        s = S("a", 1)
        return (repr(s), type(s).__name__, s.pred, s.expr, isinstance(s, C))

    def s3(C, S):
        "assign a field"
        S("a", 1).pred = 2

    def s4(C, S):
        "assign a non-field"
        s = S("a", 1)
        s.other = 2
        return s.other

    def s5(C, S):
        "delete a field"
        del S("a", 1).expr

    def s6(C, S):
        "copy"
        s = copy.copy(S("a", 1))
        return (type(s).__name__, s.pred, s.expr)

    def s7(C, S):
        "delete a non-field"
        s = S("a", 1)
        s.other = 2
        del s.other
        return hasattr(s, "other")

    def s8(C, S):
        "delete an absent non-field"
        del S("a", 1).other

    over = {"pred": property(lambda self: "over")}
    PO, YO = type("Over", (P,), over), type("Over", (Y,), over)

    def s9(C, S):
        "overriding a field"
        O = PO if C is P else YO
        return (repr(O("a", 1)), O("a", 1) == O("b", 1), hash(O("a", 1)) == hash(O("b", 1)))

    for f in (s1, s2, s3, s4, s5, s6, s7, s8, s9):
        sub(f)

    # ordering isn't defined
    for op in ("__lt__", "__le__", "__gt__", "__ge__"):
        row(op, lambda C: getattr(C("a", 1), op)(C("a", 1)) is NotImplemented)
    row("lt", lambda C: C("a", 1) < C("a", 2))

    # frozen: both assign and delete, a field and not a field, with the exception's text
    def assign(C, name):
        setattr(C("a", 1), name, 2)

    def delete(C, name):
        delattr(C("a", 1), name)

    for name in ("pred", "expr", "other", "__class__"):
        row("assign " + name, lambda C: assign(C, name))
        row("delete " + name, lambda C: delete(C, name))
    row("frozen is an AttributeError", lambda C: issubclass(obs_type(lambda: assign(C, "pred")), AttributeError))

    # operators, both sides, against atoms, formulas and things that aren't
    q = {P: P("b", 2), Y: Y("b", 2)}
    forms = [Not, lambda r: And(r, r), lambda r: Or(r, r), lambda r: Implies(r, r)]
    row("invert", lambda C: shape(~C("a", 1)))
    row("invert twice", lambda C: shape(~~C("a", 1)))
    for name, op in [("and", lambda x, y: x & y), ("or", lambda x, y: x | y), ("rshift", lambda x, y: x >> y),
                     ("xor", lambda x, y: x ^ y), ("add", lambda x, y: x + y)]:
        row(name + " atom", lambda C: shape(op(C("a", 1), q[C])))
        row(name + " int", lambda C: shape(op(C("a", 1), 1)))
        row(name + " rev int", lambda C: shape(op(1, C("a", 1))))
        for g in forms:
            row(name + " formula", lambda C: shape(op(C("a", 1), g(q[C]))))
            row(name + " rev formula", lambda C: shape(op(g(q[C]), C("a", 1))))

    # match, pickle, deepcopy
    def match(C):
        match C("a", 1):
            case C(pred, expr):
                return (pred, expr)
        return None

    row("match", match)
    row("match_args", lambda C: C.__match_args__)
    row("name", lambda C: (C.__name__, C.__qualname__, C.__module__, C.__doc__))
    row("weakref", lambda C: (lambda q: weakref.ref(q)() is q)(C("a", 1)))
    row("deepcopy", lambda C: (lambda q: (type(q) is C, q.pred, q.expr))(copy.deepcopy(C("a", (1, 2)))))
    row("is_dataclass", lambda C: __import__("dataclasses").is_dataclass(C))
    row("instance dict", lambda C: C("a", 1).__dict__)

    # pickle needs the class at its module's name, so the swap is made here for the Rust column. Every protocol, then a
    # pickle written by Python's class read back by Rust's, which is what an old file would hold.
    import satassume.sat.formula as SF
    for proto in range(pickle.HIGHEST_PROTOCOL + 1):
        def rt(C):
            SF.P = C
            try:
                q = pickle.loads(pickle.dumps(C("a", (1, 2)), proto))
                return (type(q) is C, q.pred, q.expr, q == C("a", (1, 2)))
            finally:
                SF.P = P
        row(f"pickle {proto}", rt)
        blob = pickle.dumps(P("a", (1, 2)), proto)

        def old(C):
            SF.P = C
            try:
                q = pickle.loads(blob)
                return (type(q) is C, q.pred, q.expr, q == C("a", (1, 2)))
            finally:
                SF.P = P
        row(f"pickle {proto} written by Python's", old)

    # a cycle through an atom: is it collected? Only a difference in memory, never in an answer
    def cycle(C):
        c = Cycle()
        c.p = C("a", c)
        r = weakref.ref(c)
        del c
        gc.collect()
        return r() is None

    row("cycle collected", cycle)
    ran["p"] = n


def obs_type(fn):
    try:
        fn()
    except BaseException as e:
        return type(e)
    return type(None)


def part_wanted_edge():
    """`transfer_wanted` on atoms that aren't pairs. Fixed cases, so the smallest case is itself; the first three are the ones
    the handoff names. Each is tried under `py_wanted` and Rust, with the exception's text."""
    a12, a21 = P("lt", (1, 2)), P("lt", (2, 1))
    nan = float("nan")
    cases = {
        "lt lt lt3": [a12, a21, P("lt", (1, 2, 3))],
        "lt3 lt lt": [P("lt", (1, 2, 3)), a12, a21],
        "lt3 alone": [P("lt", (1, 2, 3))],
        "lt1 alone": [P("lt", (1,))],
        "lt0 alone": [P("lt", ())],
        "list": [P("lt", [1, 2])],
        "two lists": [P("lt", [1, 2]), P("lt", [2, 1])],
        "int": [P("lt", 5)],
        "str pair": [P("lt", "ab"), P("lt", "ba")],
        "str three": [P("lt", "abc")],
        "unhashable side": [P("lt", ([], 1))],
        "frozenset": [P("lt", frozenset({1, 2}))],
        "same sides": [P("lt", (1, 1))],
        "1 and 1.0": [P("lt", (1, 2)), P("lt", (2.0, 1.0))],
        "nan identity": [P("lt", (nan, 1)), P("lt", (1, nan))],
        "nan apart": [P("lt", (float("nan"), 1)), P("lt", (1, float("nan")))],
        "raising eq": [P("lt", (Raises(), 1)), P("lt", (1, Raises()))],
        "eq before a bad lt": [P("lt", 5), P("eq", 5)],
        "not an atom": [5],
        "not iterable": 5,
    }
    # the order Python's `for x, y in lts` meets a malformed atom depends on hash order; try a spread of ints
    for i in range(40):
        cases[f"lt3 with {i}"] = [P("lt", (i, i + 1)), P("lt", (i + 1, i)), P("lt", (i, i + 1, i + 2))]
    for name, atoms in cases.items():
        x, y = obs(lambda: py_wanted(atoms)), obs(lambda: sa_solver.transfer_wanted(atoms))
        if x != y:
            fail("wanted_edge", (name, x, y))
    ran["wanted_edge"] = len(cases)


for part in a.only.split(","):
    globals()["part_" + part]()
print("ran", ran)
if known:
    print("named differences, not failures:", len(known), sorted(c[0] for c in known))
for part, cs in fails.items():
    print(part, len(cs), "differences; smallest:", min(cs, key=lambda c: len(repr(c))))
    if part in ("p", "wanted_edge"):
        # fixed rows, so every distinct kind of row is worth seeing; one example each
        seen = {}
        for c in cs:
            seen.setdefault((c[0].split(" ")[0] + c[0].split(" ")[-1][:3], c[1][0], c[2][0], c[1][1] if c[1][0] == "raise" else "", c[2][1] if c[2][0] == "raise" else ""), c)
        for c in seen.values():
            print("  ", repr(c)[:300])
sys.exit(1 if fails else 0)
