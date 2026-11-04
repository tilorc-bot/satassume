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
alone.  Ties in ``hash`` keep the table's order (-1 and -2 have one hash).

Sets inside SymPy are out of reach; vary ``PYTHONHASHSEED`` for those.

    PYTHONHASHSEED=0 python -m harness.set_order run OUT.json --seed 1 \\
        --stream 0:200:5 [--branch-budget 2] [--discovery-budget 50] \\
        [--only engine.py:1713,theories/lra/lra.py:614]
    python -m harness.set_order compare BASE.json OTHER.json ...

``run`` without ``--seed`` installs the hook with the order untouched.
``--pairs MODULE:FUNCTION[:ARG...]`` replaces ``--stream`` by a function
returning ``(proposition, assumptions)`` pairs; :func:`strips` is one built to
sit near ``BRANCH_BUDGET``.
"""
import argparse
import ast
import builtins
import hashlib
import importlib
import importlib.machinery
import json
import os
import random
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
    salt = hash((SEED, frozenset(x)))
    return sorted(x, key=lambda e: hash((salt, e)))


def _pop(x, site):
    if not isinstance(x, set) or not x:
        return x.pop()
    e = next(iter(_order(x, site)))
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
        if name in READERS:
            node.args = [a if isinstance(a, ast.Starred) else self._call("__set_order__", a)
                         for a in node.args]
        return node


def rewrite(source, path, label):
    """The code object of ``source`` with its set iteration seeded."""
    tree = _Rewrite(label).visit(ast.parse(source, path))
    return compile(ast.fix_missing_locations(tree), path, "exec", dont_inherit=True)


class _Loader(importlib.machinery.SourceFileLoader):
    def get_code(self, fullname):       # no .pyc is read or written
        path = self.get_filename(fullname)
        label = path.split(os.sep + "satassume" + os.sep)[-1].replace(os.sep, "/")
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


def run(args):
    install(args.seed, set(args.only.split(",")) if args.only else None)
    from satassume import sympy_api
    from satassume.theories.lra import lra
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
        execute(random_stream(int(seed), int(queries), int(sets), **opts), cfg, ReferenceLevel.NONE,
                engine=eng, on_row=lambda r: rows.append(trace.row(r.warm)))
    with open(args.out, "w") as f:
        json.dump({"rows": rows, "census": CENSUS}, f)
    return 0


def moved(base, other):
    """Indices whose answer differs, and how many clause sequences and LRA paths do."""
    a, b = base["rows"], other["rows"]
    if len(a) != len(b):
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


def main():
    ap = argparse.ArgumentParser(prog="harness.set_order")
    sub = ap.add_subparsers(required=True)
    p = sub.add_parser("run")
    p.add_argument("out")
    p.add_argument("--seed", type=int)
    p.add_argument("--only")
    p.add_argument("--branch-budget", type=int)
    p.add_argument("--discovery-budget", type=int)
    what = p.add_mutually_exclusive_group(required=True)
    what.add_argument("--pairs")
    what.add_argument("--stream")
    p.set_defaults(fn=run)
    p = sub.add_parser("compare")
    p.add_argument("base")
    p.add_argument("others", nargs="+")
    p.set_defaults(fn=compare)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
