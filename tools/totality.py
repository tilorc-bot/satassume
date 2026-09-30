"""Totality checker for satassume's compiled template blocks (issue #53).

A node's *block* is the union of its compiled patterns
(``satassume.templates._common.Pattern``): clauses in slot space, with
literals ``(k, pidx, neg)`` over the slots of the node's templates (direct
arguments, the node, derived nodes).  The block is *total* if for every
assignment of the non-node slots that is consistent with the rule base
(one of the 48 rule-base models per slot) the node's clauses together with
the node's own rule base are satisfiable.  Totality makes the block a
conservative extension of its children's atoms: a model of everything
below extends to the node, so nodes another query left in a session cannot
change an answer, and a downward rule cannot put a fact at root that the
children's own blocks do not entail.  A non-total block is either unsound
(``commutative(x*A) -> commutative(A)`` against ``0*A == 0``, issue #47)
or a template gap (no rule saying a transcendental times a nonzero
algebraic is transcendental).

With ``--depth 1`` (the gate's setting, ``tests/test_totality.py``) the
children's own blocks one level down constrain the assignment, so slots
built from the same subterms (``3*x`` in ``exp(3*I*pi*x)``) or holding the
same object are related, and a number in a slot carries its closed facts
(``pi`` is transcendental).  ``--depth 0`` treats the slots as independent
and over-reports (derived-slot artefacts).

The check is one SAT call per block (satassume's own solver):

    exists child models  such that  for every node model m,
        some clause that m violates has all its child literals false.

The SAT model is the counterexample (the child assignment).

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python tools/totality.py --depth 1 \
        [--corpus queries.jsonl] [--stream stream.pkl] [--json OUT]

Without ``--corpus``/``--stream`` only the synthetic list of ``load_exprs``
is checked (about 2 s); with both, every subexpression of the corpus and
the refine stream (about 380 blocks, about 6 s).

Only compiled patterns are checked.  The plain formulas some templates
emit alongside them (the unit facts of a constant-argument node such as
``asin(7)`` or ``(-1)**I``: facts about the node alone, computed from the
constant) are not: they have no children, so totality would only mean
they are satisfiable, which the compiler's constant resolution already
guarantees.  Their count is reported as "formula-only".  A template that
cannot be compiled for an expression raises: the gate must not pass
because a block was skipped.
"""
from __future__ import annotations

import argparse
import itertools
import json
import pickle
import sys
import time

from satassume.rules import NPRED, PREDICATES, PRED_INDEX, RULE_CLAUSES, RULE_FREE
from satassume.solver import Solver


def rule_models():
    """Every assignment of the 33 predicates consistent with the rule base
    (as frozensets of true predicate indices); 48 with ``polar`` (free)."""
    s = Solver()
    for _ in range(NPRED):
        s.new_var()
    for c in RULE_CLAUSES:
        s.add_clause(list(c))
    out = []
    while s.solve():
        m = s.model()
        true = frozenset(i for i in range(NPRED) if m[i + 1])
        out.append(true)
        s.add_clause([-(i + 1) if m[i + 1] else (i + 1) for i in range(NPRED)])
    return out


def _describe(true):
    return " ".join(sorted(PREDICATES[i] for i in true))


_NUMBER_ENGINE = None


def number_units(k, o):
    """Unit clauses (slot ``k``) for the context-free facts of a number."""
    global _NUMBER_ENGINE
    from sympy import Basic
    if not (isinstance(o, Basic) and o.is_Atom and o.is_number):
        return ()
    if _NUMBER_ENGINE is None:
        from satassume import Engine
        _NUMBER_ENGINE = Engine()
    out = []
    for pred in PREDICATES:
        v = _NUMBER_ENGINE.is_(o, pred)
        if v is not None:
            out.append(((k, PRED_INDEX[pred], not v),))
    return out


def derived_constraints(comp, depth=1):
    """Clauses (in the parent's slot space, possibly with extra slots) that
    the derived nodes' own template blocks impose: slot ``k > node`` holds
    ``objs[k]``, whose own patterns relate it to its arguments.  With
    ``depth`` >= 1 the direct arguments' own blocks are included too (one
    level down per unit of depth), so that arguments and derived nodes
    built from the same subterms are related through them."""
    from satassume.templates import registry
    pat = comp.pattern
    objs = list(comp.objs)
    slot_of = {id(o): k for k, o in enumerate(objs)}
    extra = []
    # a number in a slot (an argument, or the constant of a derived node)
    # carries its closed, context-free facts as units: the engine's
    # constants route asserts them whenever the node is visited, so a
    # child assignment that contradicts them is not realizable
    stack = [(k, 0) for k in pat.used if k > pat.node]
    if depth >= 1:
        stack += [(k, 1) for k in pat.used if k < pat.node]
    seen = set()
    while stack:
        k, d = stack.pop()
        if k in seen:
            continue
        seen.add(k)
        o = objs[k]
        compiled, _ = registry.clauses_for(o)
        for c in compiled:
            m = {}
            for j, oj in enumerate(c.objs):
                if id(oj) in slot_of:
                    m[j] = slot_of[id(oj)]
                else:
                    # find by equality (objects may be rebuilt)
                    for kk, ok in enumerate(objs):
                        if ok == oj:
                            m[j] = kk
                            break
                    else:
                        objs.append(oj)
                        m[j] = slot_of[id(oj)] = len(objs) - 1
                        if j > c.pattern.node:
                            stack.append((m[j], d))          # a derived node of this block
                        elif d < depth:
                            stack.append((m[j], d + 1))      # an argument, one level down
            for lits, _, _ in c.pattern.clauses:
                extra.append(tuple((m[kk], i, neg) for kk, i, neg in lits))
    # (after the walk: the derived blocks' own constants are slots too)
    for k, o in enumerate(objs):
        if k != pat.node:
            extra.extend(number_units(k, o))
    return extra


def check_pattern(pat, models, extra=(), alias=None):
    """Return None if total, else (child_assignment, fired_clauses).
    ``extra``: clauses over non-node slots that constrain the children
    (the derived nodes' own blocks); ``alias``: slot -> representative
    slot for slots holding the same object (``r**r``)."""
    if alias:
        def canon(k):
            return alias.get(k, k)
        pat_clauses = [(tuple((canon(k), i, neg) for k, i, neg in lits), a, b) for lits, a, b in pat.clauses]
        extra = [tuple((canon(k), i, neg) for k, i, neg in c) for c in extra]
    else:
        pat_clauses = pat.clauses
    slots = sorted({k for lits, _, _ in pat_clauses for k, _, _ in lits if k != pat.node}
                   | {k for c in extra for k, _, _ in c})
    if not slots:
        # a unit pattern: total iff satisfiable on its own
        s = Solver()
        for _ in range(NPRED):
            s.new_var()
        for c in RULE_CLAUSES:
            s.add_clause(list(c))
        for lits, _, _ in pat.clauses:
            s.add_clause([-(i + 1) if neg else i + 1 for k, i, neg in lits])
        return None if s.solve() else ({}, list(pat.clauses))
    s = Solver()
    base = {}
    for k in slots:
        base[k] = s.nvars()
        for _ in range(NPRED):
            s.new_var()
        for c in RULE_CLAUSES:
            s.add_clause([(base[k] + abs(l)) * (1 if l > 0 else -1) for l in c])

    def child_lit(k, i, neg):
        v = base[k] + i + 1
        return -v if neg else v

    for c in extra:
        s.add_clause([child_lit(k, i, neg) for k, i, neg in c])
    fire = []
    for lits, _, _ in pat_clauses:
        f = s.new_var()
        fire.append(f)
        child = [(k, i, neg) for k, i, neg in lits if k != pat.node]
        # f <-> AND(child literals false)
        for k, i, neg in child:
            s.add_clause([-f, -child_lit(k, i, neg)])
        s.add_clause([f] + [child_lit(k, i, neg) for k, i, neg in child])
    # for every node model m: some clause violated by m fires
    for m in models:
        viol = []
        for (lits, _, _), f in zip(pat_clauses, fire):
            node_lits = [(i, neg) for k, i, neg in lits if k == pat.node]
            if all((i not in m) if not neg else (i in m) for i, neg in node_lits):
                viol.append(f)
        if not viol:
            return None          # this node model satisfies everything: total
        s.add_clause(viol)
    if not s.solve():
        return None
    mdl = s.model()
    assign = {k: frozenset(i for i in range(NPRED) if mdl[base[k] + i + 1]) for k in slots}
    fired = [c for c, f in zip(pat_clauses, fire) if mdl[f]]
    return assign, fired


def clause_str(lits, node):
    def name(k):
        return "N" if k == node else f"s{k}"
    return " | ".join(("~" if neg else "") + f"{PREDICATES[i]}({name(k)})" for k, i, neg in lits)


def collect_patterns(exprs):
    """``(blocks, formulas_only)``: the distinct node blocks of every
    subexpression of ``exprs`` as ``key -> (expr, compiled patterns)``, one
    representative per combination of compiled patterns, and the number of
    nodes that also emit plain formulas.  A template that raises on an
    expression propagates: nothing is skipped."""
    from satassume.templates import registry
    seen = {}
    formulas_only = 0
    walk = set()
    for e in exprs:
        walk |= _subexprs(e)
    for e in walk:
        compiled, formulas = registry.clauses_for(e)
        if formulas:
            formulas_only += 1
        if not compiled:
            continue
        # a node's block is the union of its compiled patterns: key by the
        # tuple of pattern identities (the same combination once)
        key = tuple(sorted(id(c.pattern) for c in compiled))
        if key not in seen:
            seen[key] = (e, list(compiled))
    return seen, formulas_only


class _Union:
    """The clauses of every compiled pattern of one node in one slot
    space (objects identified by equality; the node last)."""

    def __init__(self, e, compiled):
        self.objs = []
        self.index = {}
        self.clauses = []
        for comp in compiled:
            pat = comp.pattern
            m = {}
            for k in pat.used:
                m[k] = self._slot(comp.objs[k])
            for lits, _, _ in pat.clauses:
                self.clauses.append((tuple((m[k], i, neg) for k, i, neg in lits), None, None))
        self.node = self._slot(e)
        self.used = tuple(range(len(self.objs)))

    def _slot(self, o):
        for k, x in enumerate(self.objs):
            if x == o:
                return k
        self.objs.append(o)
        return len(self.objs) - 1


class _Comp:
    def __init__(self, objs, pattern):
        self.objs = objs
        self.pattern = pattern


def _subexprs(e):
    out = set()
    stack = [e]
    while stack:
        x = stack.pop()
        if x in out:
            continue
        out.add(x)
        stack.extend(getattr(x, "args", ()))
    return out


def _expressions_of(obj):
    """The scalar expressions of a Boolean (the arguments of its applied
    predicates and the sides of its relations) or the expression itself."""
    from sympy.assumptions.assume import AppliedPredicate
    from sympy.core.expr import Expr
    from sympy.core.relational import Relational
    if not hasattr(obj, "atoms"):
        return []
    if isinstance(obj, Expr):
        return [obj]
    out = []
    for ap in obj.atoms(AppliedPredicate):
        out.extend(a for a in ap.arguments if isinstance(a, Expr))
    for rel in obj.atoms(Relational):
        out.extend(a for a in rel.args if isinstance(a, Expr))
    return out


def load_exprs(corpus=None, stream=None):
    from sympy import Symbol, symbols, I, pi, oo, E, Rational, Integer, Float  # noqa
    from sympy import sin, cos, tan, cot, exp, log, sqrt, Abs, acos, asin, atan, acot, sinh, cosh, tanh  # noqa
    from sympy import re, im, sign, conjugate, floor, ceiling, factorial, Function  # noqa
    exprs = []
    if corpus:
        # records of tools/compare.py: ``prop``/``assum`` (srepr of a
        # Boolean) or ``expr`` (an old-system record); records that do not
        # rebuild (a removed class) are skipped like compare.py skips them
        ns = {}
        exec("from sympy import *\nfrom sympy.assumptions import Q\nfrom sympy.core.symbol import Symbol", ns)
        with open(corpus) as fh:
            for line in fh:
                d = json.loads(line)
                for key in ("prop", "assum", "expr"):
                    v = d.get(key)
                    if not v or v in ("true", "True"):
                        continue
                    try:
                        obj = eval(v, ns)
                    except Exception:  # noqa: BLE001  (unreplayable record)
                        continue
                    exprs.extend(_expressions_of(obj))
    if stream:
        with open(stream, "rb") as fh:
            st = pickle.load(fh)
        for p, a, r in st:
            exprs.extend(_expressions_of(p))
            exprs.extend(_expressions_of(a))
    # synthetic: every registered function class on symbols with declared
    # facts, and the node shapes of every non-total family found so far
    # (the fast mode of tests/test_totality.py runs this list alone, so a
    # shape that once failed stays pinned here)
    from sympy import arg  # noqa
    x, y, z, w, a, b, k = symbols("x y z w a b k")
    A = Symbol("A", commutative=False)
    p = Symbol("p", positive=True)
    n = Symbol("n", integer=True)
    funcs = [exp, log, sin, cos, tan, cot, Abs, acos, asin, atan, acot, sinh, cosh, tanh, re, im,
             sign, conjugate, floor, ceiling, factorial, arg, Function("f")]
    syn = [x + y, x * y, x * A, A * x, x + A, x**y, x**2, x**-1, A**-1, 2 * x, -x, x - y, x * y * z,
           x + y + z, x**n, p**x, sqrt(x), x**Rational(1, 3), exp(I * pi * x), x * I, I * x + 1,
           2 * x + 1, x + 1, x - 1, x / 2, 3 * x, x**pi, pi**x, log(x, 2),
           (x + 1) ** 2, (x * y) ** 2, x**(2 * y), oo + x, x + oo, x * oo, 0**x, 1**x, (-1)**x,
           I**x, E**x, x**I, sqrt(2) * x, x + pi, Float(2.5) * x]
    syn += [f(x) for f in funcs]
    # a non-commutative argument: the Abs/re/im/sign family of issue #47
    syn += [f(A) for f in funcs]
    syn += [x * y * A, A**2, 2 * A, A + 1, A**x, x**A, x * A + 1, Abs(x * A), re(x * A), Abs(A)**2,
            A * p, A + p, n * A]
    # the families of c26e5e1 at depth 1 (MEASUREMENTS.md section 2 and 8.3):
    # transcendental products, the coefficient-free product of a rational
    # coefficient Mul, re/im of a rounding function, Abs of a sum
    syn += [log(x) / log(2), -re(n) * arg(x) / (2 * pi), im(w * y), exp(3 * I * pi * x),
            exp(2 * I * pi * x), exp(I * pi * x / 2), I * (w + I * x) * (y + I * z),
            2 * b * log(Abs(x)), 4 * b * log(Abs(x)), a * b * log(Abs(x)),
            exp(I * pi * floor(arg(x) / (2 * pi) + Rational(1, 2))),
            x + I * pi * (4 * n + 1) / 2, pi * k + pi * n / 2 + x, Abs(2 * x + 1),
            -log(x) * im(n) / (2 * pi) + Rational(1, 2), re(ceiling(y)), re(floor(y)), im(ceiling(y)),
            floor(x) + Rational(1, 2), ceiling(y) + Rational(1, 2), 3 * I + pi * I, pi * x, x / pi,
            2 * x * y, 3 * x * y * z, x * y / 2, Rational(3, 2) * x * y, -x * y,
            # a product derived from the argument of exp(I*pi*c*s) or E**(I*pi*c*s)
            exp(I * pi * n * x), exp(3 * I * pi * x * y), exp(I * pi * x * y / 2), E**(I * pi * x * y),
            E**(3 * I * pi * n * x / 2), exp(-I * pi * x * y * z),
            # half-integer sums of products
            x * y / 2 + Rational(1, 2), 2 * x * y + Rational(1, 2), x + 3 * y * z / 2, x * y * z / 2 + 1,
            Rational(1, 2) * x * y * z + w, x * y / 2 + n * z / 2]
    exprs.extend(syn)
    return exprs


def check_block(e, compiled, models, depth=1, independent=False):
    """Check the block of node ``e`` (the union of its compiled patterns):
    None if total, else ``(union, assignment, fired)`` with the child
    assignment (slot -> true predicate indices) and the fired clauses."""
    pat = _Union(e, compiled)
    comp = _Comp(tuple(pat.objs), pat)
    extra = () if independent else derived_constraints(comp, depth)
    r = check_pattern(pat, models, extra)
    if r is None:
        return None
    assign, fired = r
    return pat, assign, fired


def run(exprs, depth=1, independent=False, models=None):
    """Check every distinct node block of the subexpressions of ``exprs``:
    ``(failures, checked, formulas_only)`` with ``failures`` a list of
    ``(expr, union, assignment, fired)``.  The gate (tests/test_totality.py)
    and ``main`` both run this."""
    if models is None:
        models = rule_models()
    pats, formulas_only = collect_patterns(exprs)
    failures = []
    for key, (e, compiled) in pats.items():
        r = check_block(e, compiled, models, depth, independent)
        if r is not None:
            pat, assign, fired = r
            failures.append((e, pat, assign, fired))
    return failures, len(pats), formulas_only


def describe(e, pat, assign, fired):
    """One failure as a JSON-friendly dict (used by ``--json`` and the test)."""
    return {"expr": repr(e), "type": type(e).__name__, "node": pat.node, "slots": list(pat.used),
            "assignment": {str(k): sorted(PREDICATES[i] for i in t) for k, t in assign.items()},
            "fired": [clause_str(l, pat.node) for l, _, _ in fired]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus")
    ap.add_argument("--stream")
    ap.add_argument("--json")
    ap.add_argument("--depth", type=int, default=1,
                    help="include the arguments' own blocks this many levels down (the gate: 1)")
    ap.add_argument("--independent", action="store_true",
                    help="treat derived slots as independent of the arguments (the naive check)")
    args = ap.parse_args()
    t0 = time.time()
    models = rule_models()
    print(f"rule-base models: {len(models)}")
    exprs = load_exprs(args.corpus, args.stream)
    failures, total, formulas_only = run(exprs, args.depth, args.independent, models)
    print(f"expressions: {len(exprs)}; distinct node blocks (pattern combinations): {total}; "
          f"nodes with formula-only templates (plain formulas not checked): {formulas_only}")
    failures = [(pat, e, assign, fired) for e, pat, assign, fired in failures]
    print(f"checked {total} blocks in {time.time() - t0:.1f}s; non-total: {len(failures)}")
    out = []
    for pat, e, assign, fired in failures:
        print(f"\n=== block of {e!r} (type {type(e).__name__}, {len(pat.clauses)} clauses, slots {pat.used}, node slot {pat.node})")
        for k, true in sorted(assign.items()):
            what = pat.objs[k] if k < len(pat.objs) else "(grandchild)"
            print(f"  slot {k} = {what}: {_describe(true)}")
        print("  fired clauses (all child literals false; no node model satisfies them together):")
        for lits, _, _ in fired[:40]:
            print("    " + clause_str(lits, pat.node))
        out.append(describe(e, pat, assign, fired))
    fam = {}
    for pat, e, assign, fired in failures:
        key = tuple(sorted(set(clause_str(l, pat.node) for l, _, _ in fired)))
        fam.setdefault(key, []).append(repr(e))
    print(f"\nfailure families (by the set of fired clauses): {len(fam)}")
    for key, es in sorted(fam.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(es)} patterns, e.g. {es[0]}:")
        for c in key[:8]:
            print(f"      {c}")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
