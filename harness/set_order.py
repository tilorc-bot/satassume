"""Seeded order for every set a satassume module iterates (issue #325).

The answer of a query must not depend on the order sets iterate in
(docs/spec.md).  ``PYTHONHASHSEED`` barely tests that: it does not move sets
of ints, such as ``LRATheory._dirty``.  This module does, without touching
satassume: an import hook recompiles ``satassume.*`` with every place that
reads an iterable in order (``for``, comprehensions, ``list(x)``, ``*x``,
``x.pop()``, see ``_Rewrite``) routed through :func:`_order`.  ``_order``
leaves everything but a real set alone, so it also finds sets no syntactic
search can see, and it counts them per source line.

The order is a function of the seed and the set's contents.  Python allows
that (an unchanged set keeps its order, and two equal sets may agree), so a
query's order does not depend on earlier queries and one query reproduces
alone, under one ``PYTHONHASHSEED`` and with no ``Dummy`` in the set (SymPy
gives a ``Dummy`` a hash that differs from run to run).  Ties in ``hash`` keep
the table's order (-1 and -2 have one hash).

Sets inside SymPy are out of reach; vary ``PYTHONHASHSEED`` for those.  A
loop reads a snapshot, so it hides a set changed during its own iteration.

    PYTHONHASHSEED=0 python -m harness.set_order run OUT.json --seed 1 \\
        --stream 0:200:5 [--branch-budget 2] [--discovery-budget 50] \\
        [--only FILE:LINE,FILE:LINE] [--plant-bug]
    python -m harness.set_order compare BASE.json OTHER.json ...
    python -m harness.set_order nightly --seeds 0-1 --queries 200 --out DIR

``run`` without ``--seed`` installs the hook with the order untouched.
``--pairs MODULE:FUNCTION[:ARG...]`` replaces ``--stream`` by a function
returning ``(proposition, assumptions)`` pairs; :func:`strips` is one built to
sit near ``BRANCH_BUDGET``.  ``--plant-bug`` adds the bug :func:`_plant`
describes, the control of ``nightly``, which is what the nightly campaign runs
(harness/campaign.sh).
"""
import argparse
import ast
import builtins
import concurrent.futures
import hashlib
import importlib
import importlib.machinery
import json
import os
import random
import subprocess
import sys

#: callables that read an argument in iteration order, by last name
READERS = frozenset("""
    list tuple iter enumerate zip map filter sorted min max sum any all
    join extend fromkeys chain from_iterable product combinations permutations
    reduce Counter deque OrderedDict dict
""".split())

SEED = None     # None: leave the order alone
ONLY = None     # None: every site
#: site -> [iterations of a set, of a set with two or more elements, largest size]
CENSUS = {}
#: how many times a seed really changed an order
REORDERED = 0


def _order(x, site):
    if not isinstance(x, (set, frozenset)):
        return x
    n = len(x)
    c = CENSUS.setdefault(site, [0, 0, 0])
    c[0] += 1
    c[1] += n > 1
    c[2] = max(c[2], n)
    if SEED is None or n < 2 or (ONLY is not None and site not in ONLY):
        return x
    global REORDERED
    salt = hash((SEED, frozenset(x)))
    out = sorted(x, key=lambda e: hash((salt, e)))
    REORDERED += out != list(x)
    return out


def _pop(x, site):
    if not isinstance(x, set) or not x:
        return x.pop()
    o = _order(x, site)
    if o is x:
        return x.pop()
    e = o[0]
    x.remove(e)
    return e


class _Rewrite(ast.NodeTransformer):
    def __init__(self, label):
        self.label = label

    def _call(self, fn, node):
        site = ast.Constant(f"{self.label}:{node.lineno}")
        return ast.copy_location(
            ast.Call(ast.Name(fn, ast.Load()), [node, site], []), node)

    def visit_For(self, node):
        self.generic_visit(node)
        node.iter = self._call("__set_order__", node.iter)
        return node

    def visit_comprehension(self, node):
        self.generic_visit(node)
        node.iter = self._call("__set_order__", node.iter)
        return node

    def visit_Starred(self, node):
        self.generic_visit(node)
        if isinstance(node.ctx, ast.Load):
            node.value = self._call("__set_order__", node.value)
        return node

    def visit_YieldFrom(self, node):
        self.generic_visit(node)
        node.value = self._call("__set_order__", node.value)
        return node

    def visit_Assign(self, node):
        self.generic_visit(node)
        if any(isinstance(t, (ast.Tuple, ast.List)) for t in node.targets):
            node.value = self._call("__set_order__", node.value)
        return node

    def visit_AugAssign(self, node):        # list += a_set
        self.generic_visit(node)
        if isinstance(node.op, ast.Add):
            node.value = self._call("__set_order__", node.value)
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        if name == "pop" and isinstance(f, ast.Attribute) and not node.args and not node.keywords:
            return self._call("__set_pop__", f.value)
        if name in READERS and not (name in ("min", "max") and len(node.args) > 1):
            # fromkeys's value and reduce's function and initial value are not read in order
            first, last = {"fromkeys": (0, 1), "reduce": (1, 2)}.get(name, (0, len(node.args)))
            node.args = [a if isinstance(a, ast.Starred) or not first <= i < last
                         else self._call("__set_order__", a)
                         for i, a in enumerate(node.args)]
        return node


def rewrite(source, path, label):
    """The code object of ``source`` with its set iteration seeded."""
    tree = _Rewrite(label).visit(ast.parse(source, path))
    return compile(ast.fix_missing_locations(tree), path, "exec", dont_inherit=True)


class _Loader(importlib.machinery.SourceFileLoader):
    def get_code(self, fullname):       # no .pyc is read or written
        path = self.get_filename(fullname)
        label = path.rsplit(os.sep + "satassume" + os.sep, 1)[-1].replace(os.sep, "/")
        return rewrite(self.get_data(path), path, label)


class _Finder:
    @staticmethod
    def find_spec(name, path=None, target=None):
        if name != "satassume" and not name.startswith("satassume."):
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path, target)
        if spec is not None and isinstance(spec.loader, importlib.machinery.SourceFileLoader):
            spec.loader = _Loader(spec.loader.name, spec.loader.path)
        return spec


def install(seed=None, only=None):
    """Seed set order in every ``satassume`` module imported from now on."""
    global SEED, ONLY
    if "satassume" in sys.modules:
        raise RuntimeError("install() must run before satassume is imported")
    SEED, ONLY = seed, only
    builtins.__set_order__, builtins.__set_pop__ = _order, _pop
    sys.meta_path.insert(0, _Finder)


class _Trace:
    """Per query: which clauses reached the solvers, the LRA path (literals
    asserted, conflicts of branch and bound), and how many LRA theories ran
    out of branches.  A clean comparison means little if the shuffle moved no
    search or no budget ever ran out."""

    def __init__(self):
        from satassume.sat import solver
        from satassume.theories.lra import lra
        self.clauses, self.path, self.spent = hashlib.sha1(), hashlib.sha1(), set()
        add, branch, assert_lit = solver.Solver.add_clause, lra.LRATheory._branch, lra.LRATheory.assert_lit

        def add_clause(s, *a, **k):
            self.clauses.update(repr(a).encode())
            return add(s, *a, **k)

        def _assert_lit(t, literal):
            self.path.update(b"%d," % literal)
            return assert_lit(t, literal)

        def _branch(t, *a, **k):
            r = branch(t, *a, **k)
            self.path.update(repr(r).encode())
            if t.exhausted:
                self.spent.add(id(t))
            return r
        solver.Solver.add_clause = add_clause
        lra.LRATheory._branch, lra.LRATheory.assert_lit = _branch, _assert_lit

    def row(self, answer):
        r = (str(answer), self.clauses.hexdigest()[:12], len(self.spent), self.path.hexdigest()[:12])
        self.clauses, self.path, self.spent = hashlib.sha1(), hashlib.sha1(), set()
        return r


def _pairs(spec):
    mod, fn, *arg = spec.split(":")
    return getattr(importlib.import_module(mod), fn)(*(int(a) if a.isdigit() else a for a in arg))


def strips(seed, n=400):
    """Queries about integers in thin strips: bounded variables, with the
    query's negation leaving a band that holds rationals but maybe no
    integer.  So many are definite only through branch and bound, with a
    number of branches near the budget.  About 1 in 8 answers changes between
    budgets 4 and 1000."""
    from sympy import And, Q, Rational as R, symbols
    names = symbols("a b c d", integer=True)
    rng = random.Random(seed)

    def form(vs):
        while True:
            cs = [rng.randint(-9, 9) for _ in vs]
            if sum(c != 0 for c in cs) >= 2:
                return sum(c * v for c, v in zip(cs, vs))

    out = []
    for _ in range(n):
        vs = rng.sample(names, rng.choice([2, 3, 3, 4]))
        k = rng.choice([5, 10, 20, 50, 100])
        s = [f(v, b) for v in vs for f, b in ((Q.ge, -k), (Q.le, k))]
        band, query = form(vs), form(vs)
        t, u = rng.randint(-9, 9), rng.randint(-9, 9)
        s += [Q.ge(band, t + R(1, 3)), Q.le(band, t + rng.randint(1, 3) + R(2, 3)), Q.ge(query, u + R(1, 2))]
        if rng.random() < .4:
            s.append(Q.ne(rng.choice(vs), rng.randint(-3, 3)))
        out.append((Q.gt(query, u + rng.randint(1, 3) + R(1, 2)), And(*s)))
    return out


_PLANT = """
def plant(theory, budget):
    literals = {lit for *_, lit in theory._int_lits}
    for literal in literals:
        if literal != min(literals):
            budget[0] = 0
        break
"""


def _plant():
    """A bug of the kind this module looks for, so that ``nightly`` can show it
    is able to fail: whether branch and bound gets its budget depends on which
    element of a set iterates first.  That is the path of issue #325, where a
    definite answer becomes None.  It goes through :func:`rewrite` and uses no
    site of satassume, so no fix to one can remove it."""
    from satassume.theories.lra import lra
    env = {}
    exec(rewrite(_PLANT, "<plant>", "plant"), env)
    branch = lra.LRATheory._branch

    def _branch(t, budget):
        env["plant"](t, budget)
        return branch(t, budget)
    lra.LRATheory._branch = _branch


def run(args):
    install(args.seed, set(args.only.split(",")) if args.only else None)
    from satassume import sympy_api
    from satassume.theories.lra import lra
    if args.plant_bug:
        _plant()
    trace = _Trace()
    if args.branch_budget is not None:
        lra.BRANCH_BUDGET = args.branch_budget
    if args.pairs:
        eng = sympy_api.default_engine()
        if args.discovery_budget is not None:
            eng.discovery_budget = args.discovery_budget
        rows = []
        for p, a in _pairs(args.pairs):
            try:
                answer = sympy_api.ask(p, a, engine=eng)
            except Exception as e:
                answer = type(e).__name__
            rows.append(trace.row(answer))
    else:
        from harness.checker import ReferenceLevel, execute
        from harness.generators import random_stream
        from harness.state import EngineConfig
        seed, queries, sets, *profile = args.stream.split(":")
        opts = {"relations": True, "max_depth": 3, "profile": profile[0] if profile else "base"}
        cfg = EngineConfig()
        eng = cfg.make()
        if args.discovery_budget is not None:
            eng.discovery_budget = args.discovery_budget
        rows = []
        try:
            stream = random_stream(int(seed), int(queries), int(sets), **opts)
        except TypeError as e:      # before any query (issue #326)
            if "Invalid NaN comparison" not in str(e):
                raise
            with open(args.out, "w") as f:
                json.dump({"rows": [], "generator": repr(e)}, f)
            return 0
        execute(stream, cfg, ReferenceLevel.NONE,
                engine=eng, on_row=lambda r: rows.append(trace.row(r.warm)))
    with open(args.out, "w") as f:
        json.dump({"rows": rows, "census": CENSUS, "reordered": REORDERED}, f)
    unseen = (ONLY or set()) - CENSUS.keys()
    if unseen:
        raise SystemExit(f"--only sites that never iterated a set: {sorted(unseen)}")
    return 0


def moved(base, other):
    """Indices whose answer differs, and how many clause sequences and LRA paths do."""
    a, b = base["rows"], other["rows"]
    if not a or len(a) != len(b):
        raise ValueError(f"{len(a)} queries against {len(b)}")
    return ([i for i, (x, y) in enumerate(zip(a, b)) if x[0] != y[0]],
            sum(x[1] != y[1] for x, y in zip(a, b)),
            sum(x[3] != y[3] for x, y in zip(a, b)))


def compare(args):
    with open(args.base) as f:
        base = json.load(f)
    bad = 0
    for path in args.others:
        with open(path) as f:
            other = json.load(f)
        m, clauses, paths = moved(base, other)
        bad += len(m)
        print(f"{path}: {len(other['rows'])} compared, {len(m)} answers moved {m[:20]}, "
              f"{clauses} clause sequences and {paths} LRA paths moved, "
              f"{sum(r[2] > 0 for r in other['rows'])} queries ran out of branches")
    return 1 if bad else 0


#: the budgets of a nightly comparison, as arguments of ``run``
BUDGETS = {"normal": [], "bb2": ["--branch-budget", "2"], "db5": ["--discovery-budget", "5"]}


def _plan(first, last, queries, profiles, plant):
    """``(base leg, other legs)`` per corpus and budget; a leg is ``(name, hash
    seed, arguments of run)``.  Shuffle and hash seeds move with the corpus."""
    extra = ["--plant-bug"] if plant else []
    for s in range(first, last + 1):
        corpora = {f"strips-{s}": ["--pairs", f"harness.set_order:strips:{s}:{queries}"]}
        corpora.update({f"{p}-{s}": ["--stream", f"{s}:{queries}:5:{p}"] for p in profiles})
        for corpus, what in corpora.items():
            for budget, limit in BUDGETS.items():
                name, args = f"{corpus}.{budget}", what + limit + extra
                h = (1, 2, 42)[s % 3]
                yield ((f"{name}.off", 0, args),
                       [(f"{name}.s{s + 1}", 0, ["--seed", str(s + 1), *args]),
                        (f"{name}.s{s + 2}", 0, ["--seed", str(s + 2), *args]),
                        (f"{name}.s{s + 1}.h{h}", h, ["--seed", str(s + 1), *args])])


def _leg(out, name, hashseed, args):
    """One leg in a fresh interpreter: what ``run`` wrote, or None if it crashed."""
    path = os.path.join(out, name + ".json")
    cmd = [sys.executable, "-m", "harness.set_order", "run", path, *args]
    r = subprocess.run(cmd, env=dict(os.environ, PYTHONHASHSEED=str(hashseed)),
                       capture_output=True, text=True)
    if r.returncode:
        print(f"{name}: exit {r.returncode}\n{r.stderr[-2000:]}", file=sys.stderr)
        return None
    with open(path) as f:
        return json.load(f)


def nightly(args, leg=_leg):
    """Every corpus and budget, against the same one with the shuffle off and
    hash seed 0.  Fails on a moved answer, and on anything that means the
    comparison showed nothing: a crashed leg, a seed that reordered no set,
    strips that no longer reach the budget, or a control that moved no answer.
    A stream is skipped only where every leg stopped on the known generator
    TypeError (issue #326); in some legs only, the legs did not ask the same
    queries, and that fails.  Clause and LRA path moves are only reported.  The
    property is about answers (docs/spec.md), and the search may move for
    reasons that are not bugs."""
    os.makedirs(args.out, exist_ok=True)
    first, last = map(int, args.seeds.split("-"))
    plan = list(_plan(first, last, args.queries, args.profiles.split(",") if args.profiles else [], args.plant_bug))
    strips = f"harness.set_order:strips:{first}:{args.queries}"
    control = (("control.off", 0, ["--pairs", strips, "--plant-bug"]),
               [(f"control.s{first + 1}", 0, ["--seed", str(first + 1), "--pairs", strips, "--plant-bug"])])
    groups = plan + [control]
    legs = [lg for base, others in groups for lg in (base, *others)]
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        done = dict(zip((lg[0] for lg in legs), pool.map(lambda lg: leg(args.out, *lg), legs)))

    bad = []
    totals = {"queries": 0, "answers": 0, "clauses": 0, "paths": 0}
    planted = 0
    skipped = set()
    for (base, _, _), others in groups:
        b = done[base]
        is_control = base.startswith("control.")
        if b is None:
            bad.append(f"{base} crashed")
            continue
        if "generator" in b:
            print(f"{base}: no queries, the generator crashed: {b['generator']}", file=sys.stderr)
            ran = [other for other, *_ in others if done[other] is None or "generator" not in done[other]]
            if ran:
                bad.append(f"{base}: {b['generator']}, but not in {ran}")
            else:
                skipped.add(base.split(".")[0])
            continue
        if ".normal.off" in base and base.startswith("strips-"):
            if not any(r[2] for r in b["rows"]) or not {"True", "None"} <= {r[0] for r in b["rows"]}:
                bad.append(f"{base}: strips no longer reach the budget")
        for other, *_ in others:
            o = done[other]
            if o is None or "generator" in o:
                bad.append(f"{other} {'crashed' if o is None else o['generator']}")
                continue
            m, clauses, paths = moved(b, o)
            if is_control:
                planted = len(m)
            else:
                totals["queries"] += len(o["rows"])
                totals["answers"] += len(m)
                totals["clauses"] += clauses
                totals["paths"] += paths
                if m:
                    bad.append(f"{other} moved answers of {base}: {m[:20]}")
                if not o["reordered"]:
                    bad.append(f"{other}: the seed reordered no set")
            print(json.dumps({"source": other, "control": is_control, "queries": len(o["rows"]),
                              "moved": m, "clause_moves": clauses, "lra_path_moves": paths,
                              "families": [] if is_control else ["set-order-answer"] * len(m)}))
    if not planted:
        bad.append("the planted bug moved no answer: this comparison cannot fail")
    for b in bad:
        print(b, file=sys.stderr)
    print(f"set order: {totals['queries']} queries compared, {totals['answers']} answers moved "
          f"(fails the job); {totals['clauses']} clause sequences and {totals['paths']} LRA paths moved "
          f"(reported only); the planted bug moved {planted}; {len(skipped)} stream{'' if len(skipped) == 1 else 's'} skipped for a generator crash; "
          f"{'FAILED' if bad else 'ok'}", file=sys.stderr)
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(prog="harness.set_order")
    sub = ap.add_subparsers(required=True)
    p = sub.add_parser("run")
    p.add_argument("out")
    p.add_argument("--seed", type=int)
    p.add_argument("--only")
    p.add_argument("--branch-budget", type=int)
    p.add_argument("--discovery-budget", type=int)
    p.add_argument("--plant-bug", action="store_true")
    what = p.add_mutually_exclusive_group(required=True)
    what.add_argument("--pairs")
    what.add_argument("--stream")
    p.set_defaults(fn=run)
    p = sub.add_parser("compare")
    p.add_argument("base")
    p.add_argument("others", nargs="+")
    p.set_defaults(fn=compare)
    p = sub.add_parser("nightly")
    p.add_argument("--seeds", required=True, help="first-last corpus seed")
    p.add_argument("--queries", type=int, default=200)
    p.add_argument("--profiles", default="base,related,declared,deep,links")
    p.add_argument("--out", required=True)
    p.add_argument("--jobs", type=int, default=os.cpu_count())
    p.add_argument("--plant-bug", action="store_true", help="in every leg, to see the job fail")
    p.set_defaults(fn=nightly)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
