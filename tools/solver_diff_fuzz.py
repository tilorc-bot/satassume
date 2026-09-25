"""Differential fuzz of an incremental solver against fresh reference solvers.

    python tools/solver_diff_fuzz.py NEW/satassume/solver.py REF/satassume/solver.py SEED0 N

Runs N random seeds.  Each seed drives one long-lived ``Solver`` of NEW through
a random mix of ``add_clause``/``add_clauses``/``add_internal``/``add_pattern``,
``implied``, ``entails``, ``solve``, ``propagate``, ``root_trail`` and
``value``, and checks every answer against fresh REF solvers built from the
same clauses (the oracle), so state held between calls (cached propagation,
held assumption levels) cannot change an answer.  Written for the solver
commits of September 2026; NEW and REF may be the same file.
"""
import importlib.util, random, sys
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
New = load(sys.argv[1], "newsolver").Solver
Old = load(sys.argv[2], "oldsolver").Solver
seed0 = int(sys.argv[3]); n = int(sys.argv[4])
def rclause(rng, nv, k):
    vs = rng.sample(range(1, nv + 1), min(k, nv))
    return [v if rng.random() < 0.5 else -v for v in vs]
def fresh(cls, nv):
    o = Old(); o.ensure_vars(nv)
    for c in cls: o.add_clause(c)
    o.propagate()
    return o
def entailed(cls, nv, A, x):
    return not fresh(cls, nv).solve(list(A) + [-x])
def sat(cls, nv, A):
    return fresh(cls, nv).solve(list(A))
def check(cond, *msg):
    if not cond:
        print("FAIL", *msg); [print(x) for x in log]; sys.exit(1)
stats = {}
for seed in range(seed0, seed0 + n):
    rng = random.Random(seed)
    nv = rng.randint(3, 20)
    a = New(); a.ensure_vars(nv)
    cls = []
    A = None
    log = []
    after_prop = True
    for step in range(rng.randint(5, 80)):
        op = rng.random()
        if op < 0.30:
            c = rclause(rng, nv, rng.choice([1, 2, 2, 3, 3, 4]))
            log.append(("add_clause", c)); cls.append(c)
            r = a.add_clause(c)
            check(r or not sat(cls, nv, []), seed, step, "add_clause False but SAT")
            after_prop = len(c) != 1 and after_prop
        elif op < 0.40:
            cs = [rclause(rng, nv, rng.choice([1, 2, 3])) for _ in range(rng.randint(1, 4))]
            log.append(("add_clauses", cs)); cls.extend(cs)
            r = a.add_clauses(cs)
            check(r or not sat(cls, nv, []), seed, step, "add_clauses False but SAT")
            after_prop = False
        elif op < 0.48:
            ext = [rclause(rng, nv, rng.choice([1, 2, 3])) for _ in range(rng.randint(1, 4))]
            cs = [[2 * abs(x) + (x < 0) for x in c] for c in ext]
            log.append(("add_internal", ext)); cls.extend(ext)
            r = a.add_internal(cs)
            check(r or not sat(cls, nv, []), seed, step, "add_internal False but SAT")
            after_prop = False
        elif op < 0.53:
            k = 3
            base = nv + 1; nv += k
            p = []
            for _ in range(3):
                u, w = rng.sample(range(k), 2)
                p.append((2 * u + rng.randint(0, 1), 2 * w + rng.randint(0, 1)))
            p = tuple(p)
            log.append(("add_pattern", p, base, k))
            a.ensure_vars(nv)
            for c in p: cls.append([(-(l >> 1) if l & 1 else l >> 1) + (base if l & 1 == 0 else -base) for l in c])
            r = a.add_pattern(p, base, k)
            c = [rng.randint(base, nv), -rng.randint(1, base - 1)]
            log.append(("add_clause", c)); cls.append(c)
            r = a.add_clause(c) and r
            check(r or not sat(cls, nv, []), seed, step, "add_pattern False but SAT")
        elif op < 0.72:
            if A is None or rng.random() < 0.3:
                A = rclause(rng, nv, rng.choice([1, 1, 1, 2, 3]))
            log.append(("implied", A))
            got = a.implied(A)
            ref = fresh(cls, nv).implied(A)
            if got is None:
                check(not sat(cls, nv, A), seed, step, "implied None but consistent")
            else:
                check(ref is not None, seed, step, "implied misses UP conflict", ref)
                check(set(ref) <= set(got), seed, step, "implied misses", set(ref) - set(got))
                extra = set(got) - set(ref)
                for x in extra:
                    check(entailed(cls, nv, A, x), seed, step, "implied unsound", x)
                stats["extra"] = stats.get("extra", 0) + (1 if extra else 0)
        elif op < 0.85:
            if A is None: A = rclause(rng, nv, 1)
            lit = rng.choice([1, -1]) * rng.randint(1, nv)
            log.append(("entails", lit, A))
            try: got = a.entails(lit, A)
            except ValueError: got = "err"
            try: ref = fresh(cls, nv).entails(lit, A)
            except ValueError: ref = "err"
            check(got == ref, seed, step, "entails", got, ref)
        elif op < 0.90:
            if A is None: A = rclause(rng, nv, 1)
            AA = A + rclause(rng, nv, 1) if rng.random() < 0.5 else A
            log.append(("solve", AA))
            got = a.solve(AA)
            check(got == sat(cls, nv, AA), seed, step, "solve")
            if got:
                m = a.model()
                check(all(m[abs(x)] == (x > 0) for x in AA), seed, step, "model/assumptions")
                check(all(any(m[abs(x)] == (x > 0) for x in c) for c in cls), seed, step, "model/clauses")
        elif op < 0.95:
            log.append(("propagate",))
            r = a.propagate()
            check(r or not sat(cls, nv, []), seed, step, "propagate False but SAT")
            after_prop = True
        else:
            log.append(("root",))
            rt = a.root_trail()
            check(len(set(rt)) == len(rt), seed, step, "dup root")
            for x in rt:
                check(entailed(cls, nv, [], x), seed, step, "root unsound", x)
        if a._ok:
            # value(): sound; complete w.r.t. root propagation after propagate()
            ref = fresh(cls, nv) if after_prop else None
            for v in range(1, nv + 1):
                x = a.value(v)
                if x is not None:
                    check(entailed(cls, nv, [], v if x else -v), seed, step, "value unsound", v)
                if ref is not None and ref._ok and ref.value(v) is not None:
                    check(x == ref.value(v), seed, step, "value incomplete", v, x, ref.value(v))
print("ok", n, "seeds", stats)
