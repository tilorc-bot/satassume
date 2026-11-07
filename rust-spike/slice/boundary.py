"""boundary.py [--so DIR] [--seeds N] [--seed0 S] [--json]: sessions that overlap, on both solvers, compared.

The API fuzzer runs one session at a time and the workloads never start one from a hook, so neither can see a handle
that outlives or crosses a session. Each seed builds the same script on Python and on Rust, with two stub theories per
session (`fuzz.Stub`), and compares every hook call, its arguments (payloads included), and after each solve its result,
the conflict, the theory models and the state digest. Then it drops everything and checks the solvers and theories are
gone, each theory holding a reference to its solver so that only the GC can free them.

Kinds, by seed mod 5:
  between    a nested session runs to its end and drops between two solves of the outer one
  in-check   the same, from inside the outer theory's `check`
  in-assert  the same, from inside the outer theory's `assert_lit`
  alternate  two sessions stay alive and take turns
  after      the outer session drops, then a new one with the same variables and other payloads

Exit status 1 if the two differ. The last line of output is JSON: caught, what, session, reach, so, so_sha.
"""
import argparse
import gc
import hashlib
import json
import os
import random
import sys
import weakref

HERE = os.path.dirname(os.path.abspath(__file__))
KINDS = ("between", "in-check", "in-assert", "alternate", "after")
REACH = dict(nested_in_hook=0, solves=0, sessions=0, hook_calls=0)


def spec_of(r, atoms):
    spec = fuzz.theory_spec(r, atoms)
    spec.pop("raise_at", None)
    spec.pop("bad_at", None)
    spec["model"] = True
    return spec


class Run:
    """One seed on one solver class."""

    def __init__(self, cls, dump, seed):
        self.cls, self.dump, self.seed = cls, dump, seed
        self.log = []
        self.refs = []
        self.kind = KINDS[seed % len(KINDS)]
        self.trigger = None     # (name, hook, nth, function) run once, from inside a hook

    def theory(self, r, label, atoms):
        run = self

        class T(fuzz.StubBoth):
            def _hit(self, hook, *args):
                REACH["hook_calls"] += 1
                super()._hit(hook, *args)
                t = run.trigger
                if t and t[0] == self.name and t[1] == hook and self.calls[hook] >= t[2]:
                    run.trigger = None
                    REACH["nested_in_hook"] += 1
                    t[3]()
        return T(spec_of(r, atoms), self.log, label)

    def session(self, label, seed):
        """Its variables, clauses and atoms are a function of the seed; the label makes each payload its own."""
        r = random.Random(seed)
        s = self.cls()
        REACH["sessions"] += 1
        s.track_owners = False
        n = 14
        for _ in range(n):
            s.new_var()
        for _ in range(22):
            s.add_clause([r.choice((-1, 1)) * r.randint(1, n) for _ in range(3)])
        ts = []
        for name in ("a", "b"):
            atoms = r.sample(range(1, n + 1), 6)
            t = self.theory(r, f"{label}.{name}", atoms)
            t.solver = s    # a cycle only the GC can break
            s.attach_theory(t)
            for v in atoms:
                s.register_atom(t, v, f"{label}.{name}.{v}")
            ts.append(t)
        self.refs += [weakref.ref(s)] + [weakref.ref(t) for t in ts]
        return s, r, n

    def solve(self, label, s, r, n):
        a = [r.choice((-1, 1)) * v for v in r.sample(range(1, n + 1), r.randint(0, 3))]
        REACH["solves"] += 1
        try:
            res = s.solve(a)
        except Exception as e:      # the type only: a message is the wrapper's to word
            res = type(e).__name__
        self.log.append((label, "solve", a, res, list(s.conflict()), repr(s.theory_models()),
                         state.digest(self.dump(s))))

    def nested(self, label):
        s, r, n = self.session(label, self.seed + 1000)
        for _ in range(3):
            self.solve(label, s, r, n)

    def go(self):
        s, r, n = self.session("outer", self.seed)
        if self.kind == "between":
            self.solve("outer", s, r, n)
            self.nested("inner")
        elif self.kind == "in-check":
            self.trigger = ("outer.a", "check", 1, lambda: self.nested("inner"))
        elif self.kind == "in-assert":
            self.trigger = ("outer.b", "assert", 2, lambda: self.nested("inner"))
        elif self.kind == "alternate":
            s2, r2, n2 = self.session("other", self.seed + 1000)
            for _ in range(3):
                self.solve("outer", s, r, n)
                self.solve("other", s2, r2, n2)
            del s2
        elif self.kind == "after":
            self.solve("outer", s, r, n)
            del s
            gc.collect()
            s, r, n = self.session("later", self.seed)
            label = "later"
            for _ in range(3):
                self.solve(label, s, r, n)
        if self.kind != "after":
            for _ in range(3):
                self.solve("outer", s, r, n)
        del s
        gc.collect()
        self.log.append(("alive after drop", sum(x() is not None for x in self.refs)))
        return self.log


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i, x, y
    return min(len(a), len(b)), "end" if len(a) < len(b) else None, "end" if len(b) < len(a) else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--so")
    p.add_argument("--seeds", type=int, default=500)
    p.add_argument("--seed0", type=int, default=1)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    sys.path.insert(0, HERE)
    if a.so:
        sys.path.insert(0, a.so)
    import sa_solver
    if a.so and os.path.dirname(os.path.abspath(sa_solver.__file__)) != os.path.abspath(a.so):
        sys.exit(f"--so {a.so}: loaded {sa_solver.__file__} instead")
    global fuzz, state
    import fuzz
    import state
    res = dict(caught=False, what=None, session=None, kinds={}, so=sa_solver.__file__,
               so_sha=hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest())
    for seed in range(a.seed0, a.seed0 + a.seeds):
        py = Run(fuzz.pysolver.Solver, state.dump_py, seed).go()
        rs = Run(sa_solver.Solver, sa_solver.Solver.dump, seed).go()
        kind = KINDS[seed % len(KINDS)]
        res["kinds"][kind] = res["kinds"].get(kind, 0) + 1
        if py != rs:
            i, x, y = first_diff(py, rs)
            res.update(caught=True, what=kind, session=seed, event=i, py=repr(x)[:400], rs=repr(y)[:400])
            break
    res["reach"] = REACH
    print(json.dumps(res))
    sys.exit(1 if res["caught"] else 0)


if __name__ == "__main__":
    main()
