"""Differential fuzz: one long-lived Solver with real LRA + EUF theories
(and shared interface atoms) against fresh solvers replaying the history.

Written by the reviewer of the fact-lattice stage 1 (2026-09-25) for the
held-levels-with-theories change: unlike ``test_solver_incremental``'s
theory mode (``ForbidTheory``, which has no history), LRA and EUF
propagate from state that pops can discard, which is what held levels and
the registration of atoms interact with.  ``MISSES`` collects the steps
where the live solver's ``implied`` is weaker than a fresh solver's (not
a wrong answer, but a lost implication).  Driven by
``tests/test_solver_real_theories.py``; by hand::

    python tests/real_theory_fuzz.py SEED0 N [lra|euf|both]
"""
import random
import sys
from fractions import Fraction

from satassume.solver import Solver
from satassume.lra import LRATheory, constraint
from satassume.euf import EUFTheory, EqAtom
from theory_harness import Recorder
from theory_harness import check_protocol

LVARS = ["x", "y", "z"]
ECONST = ["x", "y", "z", "a", "b"]


MISSES = []
ANS = []


class Mismatch(Exception):
    pass


def build_terms(th, specs, ids):
    ids = dict(ids)
    for name, spec in specs:
        if spec[0] == "c":
            ids[name] = th.term(spec[1])
        elif spec[0] == "v":
            ids[name] = th.value(spec[1])
        else:
            ids[name] = th.term(spec[1], [ids[a] for a in spec[2]])
    return ids


class World:
    def __init__(self, mode, record=False):
        self.s = Solver()
        self.lra = self.euf = None
        self.terms = {}
        self.mode = mode
        if mode in ("lra", "both"):
            self.lra = LRATheory()
            if record:
                self.lra = Recorder(self.lra, self.s)
            self.s.attach_theory(self.lra)
        if mode in ("euf", "both"):
            self.euf = EUFTheory()
            if record:
                self.euf = Recorder(self.euf, self.s)
            self.s.attach_theory(self.euf)

    def euf_inner(self):
        e = self.euf
        return getattr(e, "inner", e)

    def apply(self, ev):
        s = self.s
        k = ev[0]
        if k == "nv":
            s.ensure_vars(ev[1])
        elif k == "term":
            _, name, spec = ev
            self.terms.update(build_terms(self.euf_inner(), [(name, spec)], self.terms))
        elif k == "lra":
            _, v, payload = ev
            return s.register_atom(self.lra, v, payload)
        elif k == "euf":
            _, v, l, r, pos = ev
            return s.register_atom(self.euf, v, EqAtom(self.terms[l], self.terms[r], pos))
        elif k == "clause":
            return s.add_clause(ev[1])
        elif k == "clauses":
            return s.add_clauses(ev[1])


def fresh(mode, hist):
    w = World(mode)
    for ev in hist:
        w.apply(ev)
    return w.s


def run_seed(seed, mode):
    rng = random.Random(seed)
    live = World(mode, record=True)
    hist = []
    nv = 0
    log = []
    global LOG
    LOG = log

    def ev(e):
        hist.append(e)
        r = live.apply(e)
        log.append(e)
        return r

    def newvar():
        nonlocal nv
        nv += 1
        ev(("nv", nv))
        return nv

    if live.euf is not None:
        for c in ECONST:
            ev(("term", c, ("c", c)))
        ev(("term", "0", ("v", 0)))
        ev(("term", "1", ("v", 1)))
        for c in ["x", "y", "a"]:
            ev(("term", "f" + c, ("f", "f", [c])))
    ecount = [0]

    def lra_atom():
        v = newvar()
        k = rng.randint(1, 2)
        vs = rng.sample(LVARS, k)
        terms = {t: rng.choice([-2, -1, 1, 1, 2]) for t in vs}
        if rng.random() < 0.05:
            payload = ((), Fraction(rng.choice([0, -1])), False, False)
        else:
            payload = constraint(terms, rng.choice(["<", "<=", ">", ">=", "=", "!="]),
                                 rng.randint(-2, 2))
        return v, ev(("lra", v, payload))

    def euf_atom():
        v = newvar()
        names = list(live.terms)
        l, r = rng.sample(names, 2)
        return v, ev(("euf", v, l, r, rng.random() < 0.8))

    def iface_atom():
        v = newvar()
        a, b = rng.sample(LVARS, 2)
        ev(("lra", v, constraint({a: 1, b: -1}, "=", 0)))
        return v, ev(("euf", v, a, b, True))

    def new_term():
        ecount[0] += 1
        name = "t%d" % ecount[0]
        names = list(live.terms)
        if rng.random() < 0.5:
            spec = ("f", "f", [rng.choice(names)])
        else:
            spec = ("f", "g", rng.sample(names, 2))
        ev(("term", name, spec))

    def atom():
        choices = []
        if live.lra is not None:
            choices += ["lra", "lra"]
        if live.euf is not None:
            choices += ["euf", "euf"]
        if mode == "both":
            choices += ["iface"]
        c = rng.choice(choices)
        return {"lra": lra_atom, "euf": euf_atom, "iface": iface_atom}[c]()

    for _ in range(rng.randint(3, 7)):
        atom()
    for _ in range(rng.randint(0, 3)):
        newvar()

    def rlit():
        v = rng.randint(1, nv)
        return v if rng.random() < 0.5 else -v

    pool = []

    def rassump():
        if pool and rng.random() < 0.6:
            A = list(rng.choice(pool))
            if rng.random() < 0.3:
                A.append(rlit())
            return A
        A = list({abs(x): x for x in (rlit() for _ in range(rng.randint(0, 3)))}.values())
        pool.append(A)
        if len(pool) > 4:
            pool.pop(0)
        return A

    s = live.s

    def check(cond, *what):
        if not cond:
            raise Mismatch((seed, what, log[-40:]))

    for step in range(rng.randint(20, 60)):
        r = rng.random()
        if r < 0.10:
            atom()
        elif r < 0.14 and live.euf is not None:
            new_term()
        elif r < 0.30:
            c = list({abs(x): x for x in (rlit() for _ in range(rng.randint(1 if rng.random() < 0.08 else 2, 3)))}.values())
            ev(("clause", c))
        elif r < 0.34:
            cs = [list({abs(x): x for x in (rlit() for _ in range(rng.randint(2, 3)))}.values())
                  for _ in range(rng.randint(1, 3))]
            cs = [c for c in cs if len(c) >= 2]
            ev(("clauses", cs))
            s.propagate()
        elif r < 0.55:
            A = rassump()
            log.append(("implied", A))
            got = s.implied(A)
            ANS.append((seed, step, "implied", None if got is None else sorted(got)))
            f = fresh(mode, hist)
            ref = f.implied(A)
            if got is None:
                check(not fresh(mode, hist).solve(A), "implied None but SAT", A)
            else:
                if ref is None:
                    check(False, "live implied not None, fresh None", A)
                if not set(ref) <= set(got):
                    MISSES.append((seed, step))
                for x in set(got) - set(ref):
                    check(not fresh(mode, hist).solve(A + [-x]), "implied unsound", A, x)
        elif r < 0.75:
            A = rassump()
            lit = rlit()
            log.append(("entails", lit, A))
            try:
                got = s.entails(lit, A)
            except ValueError:
                got = "inc"
            try:
                ref = fresh(mode, hist).entails(lit, A)
            except ValueError:
                ref = "inc"
            ANS.append((seed, step, "entails", got))
            check(got == ref, "entails", lit, A, got, ref)
        elif r < 0.92:
            A = rassump()
            log.append(("solve", A))
            got = s.solve(A)
            ref = fresh(mode, hist).solve(A)
            ANS.append((seed, step, "solve", got))
            check(got == ref, "solve", A, got, ref)
        else:
            log.append(("propagate",))
            s.propagate()
        for t in (live.lra, live.euf):
            if t is not None:
                t.mark(step)
                check(len(getattr(t, "inner", t)._lims) == len(s._trail_lim), "level mismatch")
    for t in (live.lra, live.euf):
        if t is not None:
            try:
                check_protocol(t)
            except AssertionError as e:
                check(False, "protocol", str(e))
    return True


if __name__ == "__main__":
    seed0, n = int(sys.argv[1]), int(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) > 3 else "both"
    bad = 0
    for seed in range(seed0, seed0 + n):
        try:
            run_seed(seed, mode)
        except Mismatch as e:
            bad += 1
            seed_, what, lg = e.args[0]
            print("MISMATCH seed", seed_, what)
            if bad <= 3:
                for x in lg[-25:]:
                    print("   ", x)
    print("done", mode, seed0, n, "mismatches", bad, "implied-misses", len(MISSES))
    if len(sys.argv) > 4:
        with open(sys.argv[4], "w") as f:
            for a in ANS:
                f.write(repr(a) + "\n")
