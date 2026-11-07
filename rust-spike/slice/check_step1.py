"""Step 1's check: hand-written CNFs and propositional API calls give the same results on the Rust and Python solvers.

Each script runs on both. After every call the two must agree on the result or exception (type and message), and on
model, conflict, root_trail, nvars and stats, so a change in search shows up even when the answer doesn't.
Also: theory hooks with a stub theory, an exception from a hook, and session-end drop.
`python check_step1.py [random scripts, default 3000]`. This is a smoke check; step 2 builds the state compare.
"""
import gc
import itertools
import random
import sys

import backend
from satassume.sat.solver import Solver as PySolver

RS = backend.RustSolver
BLOCK = ((1, 2), (0, 3), (1, 4, 6), (2, 5))     # internal literals relative to 0, over 4 variables
BIG_BLOCK = ((0, 2, 4, 6, 8, 10, 12, 14, 16, 18),)   # over 128 models: the wide path of `closure`
counts = {"scripts": 0, "calls": 0, "compared": 0}


def snap(s):
    return s.model(), s.conflict(), s.root_trail(), s.nvars(), s.stats()


def call(s, name, args):
    try:
        return ("ok", getattr(s, name)(*args))
    except Exception as e:
        return ("raise", type(e).__name__, str(e))


def run(script, label):
    a, b = PySolver(), RS()
    counts["scripts"] += 1
    for i, (name, args) in enumerate(script):
        ra, rb = call(a, name, args), call(b, name, args)
        counts["calls"] += 1
        sa, sb = snap(a), snap(b)
        counts["compared"] += 1
        if ra != rb or sa != sb:
            print(f"MISMATCH {label} call {i} {name}{args}\n  py   {ra} {sa}\n  rust {rb} {sb}")
            sys.exit(1)
        counts["raises"] = counts.get("raises", 0) + (ra[0] == "raise")
    st = a.stats()
    for k in ("conflicts", "decisions", "restarts", "rule_blocks", "witness_hits"):
        counts[k] = counts.get(k, 0) + st[k]


def php(p, h):
    v = lambda i, j: i * h + j + 1
    cl = [[v(i, j) for j in range(h)] for i in range(p)]
    cl += [[-v(i, j), -v(k, j)] for j in range(h) for i, k in itertools.combinations(range(p), 2)]
    return cl


def cnf(clauses, *more):
    return [("add_clause", (c,)) for c in clauses] + [("solve", ())] + list(more)


HAND = {
    "empty": [("solve", ()), ("model", ())],
    "unit": cnf([[1]]),
    "contradiction": cnf([[1], [-1]]),
    "empty clause": cnf([[]]),
    "tautology and duplicates": cnf([[1, -1], [2, 2, 3], [3, 2, 2]]),
    "chain": cnf([[1], [-1, 2], [-2, 3], [-3, 4]]),
    "php 3 2": cnf(php(3, 2)),
    "php 4 3": cnf(php(4, 3)),
    "php 6 5, restarts": cnf(php(6, 5)),
    "php 3 3 sat": cnf(php(3, 3)),
    "zero literal": [("add_clause", ([1, 0],)), ("solve", ([0],)), ("entails", (0, [])), ("implied", ([0],))],
    "assumptions and core": cnf([[1, 2], [-1, 3], [-2, 3], [-3, 4]],
                                ("solve", ([-4],)), ("solve", ([-4, 1],)), ("solve", ([4],)), ("solve", ([-1, -2],))),
    "incremental": [("add_clause", ([1, 2],)), ("solve", ()), ("add_clause", ([-1],)), ("solve", ()),
                    ("add_clause", ([-2],)), ("solve", ()), ("add_clause", ([3],)), ("solve", ())],
    "new vars after a model": [("add_clause", ([1],)), ("solve", ()), ("ensure_vars", (5,)), ("solve", ()),
                               ("new_var", ()), ("solve", ([6],)), ("solve", ([-6],))],
    "entails": cnf([[1, 2], [-1, 3], [-2, 3]], ("entails", (3, [])), ("entails", (1, [])), ("entails", (-3, [])),
                   ("entails", (1, [-2])), ("entails", (3, [-3])), ("entails", (9, [])), ("consistent", ([1, -3],)),
                   ("consistent", ([1, 2],)), ("entails_all", ([3], [])), ("entails_all", ([1, 3], [-2])),
                   ("entails_all", ([1, 2], [])), ("entails_all", ([], [-3]))),
    "held levels": [("add_clause", ([-1, 2],)), ("add_clause", ([-2, 3],)), ("add_clause", ([-4, 5],)),
                    ("implied", ([1],)), ("implied", ([1, 4],)), ("implied", ([1, 4], 1)), ("add_clause", ([-3, 6],)),
                    ("implied", ([1, 4],)), ("release", (1,)), ("add_clause", ([-5, 7],)), ("implied", ([1, 4],)),
                    ("release", (0,)), ("implied", ([-3, 1],)), ("propagate", ()), ("value", (3,)), ("value", (-1,)),
                    ("value", (99,)), ("value", (0,)), ("entails", (6, [1, 4], 1)), ("solve", ([1, 4],))],
    "inert": [("add_clause", ([1, 2],)), ("set_inert", (2,)), ("solve", ()), ("solve", ([-1],)), ("solve", ([2],)),
              ("consistent", ([-2],))],
    "add_clauses": [("add_clauses", ([[1, 2], [-2, 3], [4]],)), ("solve", ()), ("add_clauses", ([[-4, 5], [-5]],)),
                    ("propagate", ()), ("solve", ()), ("add_clauses", ([[6, 7], [-6, 7], [6, -7], [-6, -7]],)),
                    ("solve", ())],
    "add_internal": [("ensure_vars", (6,)), ("add_internal", ([[2, 4], [3, 6], [8]],)), ("solve", ()),
                     ("add_internal", ([[9, 10]], [(4, 3), (5, 3)])), ("solve", ())],
    "add_pattern": [("add_pattern", ([[0, 2], [1, 3]], 3, 2)), ("solve", ([-3],)), ("add_clause", ([-4],)),
                    ("add_pattern", ([[0, 2], [1, 3]], 3, 2)), ("solve", ())],
    "rule block": [("set_rule_block", (BLOCK, 4)), ("set_rule_block", (BLOCK, 4)), ("register_block", (1,)),
                   ("register_block", (5, 3)), ("solve", ()), ("solve", ([1],)), ("entails", (2, [1])),
                   ("implied", ([6],)), ("mention", ([3],)), ("implied", ([1],)), ("mention_blocks", ([(5, 0xff)],)),
                   ("implied", ([1, 6],)), ("add_clause", ([-2, 5],)), ("solve", ([1, -5],)), ("set_inert", (2,)),
                   ("register_block", (3,)), ("register_block", (0,)), ("register_block", (9, 1 << 40)),
                   ("set_rule_block", (((0, 2),), 2)), ("add_clause", ([9],)), ("solve", ()), ("root_trail", ())],
    "rule block before set": [("register_block", (1,))],
    "rule block bad": [("set_rule_block", (((0,),), 2)), ("set_rule_block", (((0, 2),), 1)),
                       ("set_rule_block", (((0, 2),), 65)), ("set_rule_block", ((), None))],
    "wide block": [("set_rule_block", (BIG_BLOCK, 10)), ("register_block", (1, 3)), ("solve", ([-1],)),
                   ("implied", ([-1, -2],)), ("mention", ([3, 4],)), ("solve", ([-1, -2, -3, -4],))],
    "stats keys": [("add_clause", ([1, 2],)), ("stats", ())],
}


def random_script(rng):
    n = rng.randint(3, 30)
    lit = lambda: rng.choice((1, -1)) * rng.randint(1, n)
    lits = lambda lo, hi: [lit() for _ in range(rng.randint(lo, hi))]
    held = lambda: rng.choice((None, None, 0, 1, 2))
    script = []
    block = rng.random() < .5
    if block:
        script.append(("set_rule_block", (BLOCK, 4)))
    density = rng.uniform(1.5, 5.5)
    for c in range(int(n * density)):
        script.append(("add_clause", (lits(1 if rng.random() < .1 else 2, 4),)))
        if rng.random() > .25:
            continue
        k = rng.randrange(13)
        if k == 0:
            script.append(("solve", (lits(0, 3),)))
        elif k == 1:
            script.append(("implied", (lits(0, 3), held())))
        elif k == 2:
            script.append(("entails", (lit(), lits(0, 3), held())))
        elif k == 3:
            script.append(("consistent", (lits(0, 3), held())))
        elif k == 4:
            script.append(("entails_all", (lits(1, 3), lits(0, 2), held())))
        elif k == 5:
            script.append(("release", (rng.randint(0, 2),)))
        elif k == 6:
            script.append(("mention", (lits(1, 2),)))
        elif k == 7:
            script.append(("propagate", ()))
        elif k == 8:
            script.append(("set_inert", (rng.randint(1, n),)))
        elif k == 9 and block:
            script.append(("register_block", (rng.randint(1, n), rng.choice((0, 3, 12, 0xff)))))
        elif k == 10:
            script.append(("value", (lit(),)))
        elif k == 11:
            script.append(("ensure_vars", (n + rng.randint(0, 3),)))
        elif k == 12:
            script.append(("add_clauses", ([lits(2, 3), lits(1, 2)],)))
    script.append(("solve", ()))
    script.append(("solve", (lits(1, 3),)))
    return script


class Stub:
    """A scripted theory: says no to one set of literals, implies one literal, wants one variable decided."""

    def __init__(self, log):
        self.log, self.true, self.levels, self.atoms = log, set(), [], {}

    def register_atom(self, v, payload):
        self.atoms[v] = payload
        self.log.append(("reg", v, payload))

    def assert_lit(self, x):
        self.log.append(("assert", x))
        self.true.add(x)
        self.levels and self.levels[-1].append(x)
        if {1, 2} <= self.true:
            return (False, [-1, -2])

    def propagate(self):
        self.log.append(("prop",))
        if 3 in self.true and 4 not in self.true:
            yield (4, [-3, 4])

    def decide(self):
        self.log.append(("decide",))
        return None

    def check(self):
        self.log.append(("check",))
        if {4, 5} <= self.true:
            return (False, [-4, -5])
        return (True, sorted(self.true))

    def push_level(self):
        self.log.append(("push",))
        self.levels.append([])

    def pop_level(self):
        self.log.append(("pop",))
        self.true.difference_update(self.levels.pop())


def hooks():
    def go(cls):
        log, s = [], cls()
        t = Stub(log)
        s.attach_theory(t)
        out = [s.theories() == [t], call(s, "attach_theory", (t,))[1:]]
        for v in (1, 2, 3, 4, 5):
            out.append(s.register_atom(t, v, f"atom{v}"))
        out.append(call(s, "register_atom", (t, 1, "again")))
        out.append(call(s, "register_atom", (Stub([]), 1, "x")))
        for a in ([], [1], [1, 2], [3], [3, 5], [-4], [3, -4]):
            out.append((a, s.solve(a), s.model(), s.conflict(), s.theory_models()))
        out.append(s.solve([1]))                  # a model from the ring: theory models come back too
        out.append(s.theory_models())
        s.add_clause([1, 2, 3])
        out.append((s.solve(), s.stats()))
        return out, log
    a, b = go(PySolver), go(RS)
    assert a == b, f"hooks differ\n py {a}\n rs {b}"
    counts["hook calls"] = len(a[1])


def hook_raises():
    class Boom(Stub):
        def assert_lit(self, x):
            raise KeyError("boom")

    class Bad(Stub):
        def assert_lit(self, x):
            return (False, [x])    # true, so not a valid conflict

    def go(cls, th):
        s = cls()
        t = th([])
        s.attach_theory(t)
        s.register_atom(t, 1, None)
        r = [call(s, "solve", ([1],))]
        return r
    for th in (Boom, Bad):
        a, b = go(PySolver, th), go(RS, th)
        assert a == b, (a, b)
        assert a[0][0] == "raise"
    counts["hook raises"] = 2


def drop():
    class Adapter(Stub):
        pass

    before = (backend.created, backend.dropped)
    n = 200
    for _ in range(n):
        s = backend.make()
        t = Adapter([])
        s.attach_theory(t)
        s.register_atom(t, 1, [t])
        s.solve()
        t.solver = s                 # the cycle a session has: solver -> theory -> solver
        s.add_clause([1])
        del s, t
    gc.collect()
    made, gone = backend.created - before[0], backend.dropped - before[1]
    assert (made, gone) == (n, n), (made, gone)
    counts["sessions created"], counts["sessions dropped"] = made, gone


def main():
    nrand = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    for label, script in HAND.items():
        run(script, label)
    counts["hand scripts"] = counts["scripts"]
    rng = random.Random(20261107)
    for i in range(nrand):
        run(random_script(rng), f"random {i}")
    hooks()
    hook_raises()
    drop()
    print("same results:", counts)


if __name__ == "__main__":
    main()
