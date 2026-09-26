"""Sample points that satisfy a case's assumptions: random draws, edge and branch-cut points.

Scalar family (:func:`check_points`, the differential's check): random draws
of :func:`.assumptions.draw` plus edge points: 0, 1, -1, I, -I and points on
the branch cuts of log, sqrt (any non-integer power), asin, acos, atan,
acoth, asech and acsch, used both as values of each symbol and, where such a
function's argument is linear in a single symbol, as that argument (the
symbol value that puts the argument on the cut).  A point is used only if it
satisfies the symbol's predicates and the relation, if any.

Extended family (:func:`ext_points`): the same, plus the infinities
``INF_VALUES`` for a symbol that has a predicate or occurs in a relation (a
relation makes it extended real, so only +-oo pass the relation there), and
the finite bounds of the relations.  A symbol with no fact at all is
sampled finite.

The order of the random calls is part of what the gates compare.
"""
from __future__ import annotations

import itertools

from sympy import I, Q, Rational, S, sympify

from . import assumptions as A


def _cut_points():
    half = Rational(1, 2)
    neg_real = [S.Zero, S.NegativeOne, S(-2), -half]
    return {
        "log": neg_real,
        "pow": neg_real,                 # sqrt and every non-integer power: principal log cut
        "asin": [S.One, S.NegativeOne, S(2), S(-2), 3 * half, -3 * half],
        "acos": [S.One, S.NegativeOne, S(2), S(-2), 3 * half, -3 * half],
        "atan": [I, -I, 2 * I, -2 * I],
        "acoth": [S.Zero, S.One, S.NegativeOne, half, -half],
        "asech": [S.Zero, S.One, S.NegativeOne, S(2), -half],
        "acsch": [S.Zero, I, -I, I / 2, -I / 2],
    }


def edge_values():
    """0, 1, -1, I, -I and every branch-cut point, as symbol values."""
    seen, out = set(), []
    for v in [S.Zero, S.One, S.NegativeOne, I, -I] + [p for ps in _cut_points().values() for p in ps]:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def cut_arguments(exprs):
    """(argument, cut points) for every branch-cut function occurring in ``exprs``."""
    from sympy import Pow, acos, acoth, acsch, asech, asin, atan, log
    cuts = _cut_points()
    kinds = [(log, "log"), (asin, "asin"), (acos, "acos"), (atan, "atan"),
             (acoth, "acoth"), (asech, "asech"), (acsch, "acsch")]
    out = []
    for expr in exprs:
        for sub in expr.atoms(log, asin, acos, atan, acoth, asech, acsch, Pow):
            if isinstance(sub, Pow):
                if sub.exp.is_integer is not True:
                    out.append((sub.base, cuts["pow"]))
                continue
            for cls, name in kinds:
                if isinstance(sub, cls):
                    out.append((sub.args[0], cuts[name]))
    return out


def _add_cut_preimages(exprs, cand):
    """Add to ``cand[s]`` the values of ``s`` that put a cut function's argument, linear in ``s`` alone, on its cut."""
    for arg, pts in cut_arguments(exprs):
        free = arg.free_symbols
        if len(free) != 1:
            continue
        (s,) = free
        if s not in cand:
            continue
        slope = arg.diff(s)
        if slope.free_symbols or slope == 0 or arg.subs(s, 0).free_symbols:
            continue              # only arguments linear in the one symbol
        for p in pts:
            v = (p - arg.subs(s, 0)) / slope
            if v not in cand[s]:
                cand[s].append(v)


def _satisfying(cand, combos, preds):
    """``cand`` with the values that fail a symbol's predicates (in ``preds``) removed."""
    def ok(s, v):
        try:
            return all(preds[p][1](v) for p in combos.get(s, ()))
        except (TypeError, ValueError):
            return False
    return {s: [v for v in vs if ok(s, v)] for s, vs in cand.items()}


def _edge_points(syms, cand, cap, fill):
    """The full product of the edge candidates when it has at most ``cap`` points, else each
    candidate with the other symbols filled by ``fill(symbol)`` (which may return None)."""
    total = 1
    for s in syms:
        total *= max(1, len(cand[s]))
    if syms and total <= cap:
        return [{s: (v if v is not None else fill(s)) for s, v in zip(syms, combo)}
                for combo in itertools.product(*[cand[s] or [None] for s in syms])]
    return [{t: (v if t == s else fill(t)) for t in syms} for s in syms for v in cand[s]]


def edge_candidates(exprs, syms, combos):
    """Per symbol: edge values and cut pre-images that satisfy its predicates."""
    cand = {s: list(edge_values()) for s in syms}
    _add_cut_preimages(exprs, cand)
    return _satisfying(cand, combos, A.PREDS)


def _complete(pt):
    return all(v is not None for v in pt.values())


def check_points(exprs, combos, rel, rng, random_points=12, cap=160):
    """Sample points satisfying the assumptions: random draws plus edge points."""
    syms = sorted(set().union(*(e.free_symbols for e in exprs)), key=str)
    points = []

    def rand_value(s):
        return A.draw(combos.get(s, ()), rng)

    for _ in range(random_points * 4):
        if len(points) >= random_points:
            break
        pt = {s: rand_value(s) for s in syms}
        if not _complete(pt):
            break
        points.append(pt)
    cand = edge_candidates(exprs, syms, combos)
    points += [pt for pt in _edge_points(syms, cand, cap, rand_value) if _complete(pt)]
    if rel is not None:
        points = [p for p in points if A.rel_holds(rel, p) is True]
    return points


# --- extended family

def _draw_point(syms, combos, rels, rng, inf_ok, p_inf=0.3):
    pt = {s: A.draw_ext(combos.get(s, ()), rng, inf_ok[s], p_inf) for s in syms}
    if any(v is None for v in pt.values()):
        return None
    for r in rels:                     # make an equation hold now and then
        if r.function == Q.eq and rng.random() < 0.7:
            a, b = (sympify(t) for t in r.arguments)
            if a in pt:
                v = b.xreplace(pt)
                if v.is_number and all(A.EXT_PREDS[p][1](v) for p in combos.get(a, ())):
                    pt[a] = v
    return pt


def ext_satisfiable(combos, rels, rng, tries=80):
    """Whether a random point satisfies ``combos`` and ``rels`` (a cheap filter, not a proof)."""
    syms = sorted(combos, key=str)
    inf_ok = {s: bool(combos[s]) or s in A.rel_syms(rels) for s in syms}
    for t in range(tries):
        pt = _draw_point(syms, combos, rels, rng, inf_ok, p_inf=0.5)
        if pt is None:
            return False
        if A.holds_all(rels, pt):
            return True
    return False


def ext_points(exprs, combos, rels, rng, random_points=12, cap=200):
    """Points satisfying ``combos`` and ``rels``: random draws, edge values, infinities and relation bounds."""
    syms = sorted(set().union(*(e.free_symbols for e in exprs)), key=str)
    relsyms = A.rel_syms(rels)
    inf_ok = {s: bool(combos.get(s)) or s in relsyms for s in syms}
    points = []
    for _ in range(random_points * 8):
        if len(points) >= random_points:
            break
        pt = _draw_point(syms, combos, rels, rng, inf_ok)
        if pt is None:
            break
        if A.holds_all(rels, pt):
            points.append(pt)
    cand = {s: list(edge_values()) + ([v for v in A.INF_VALUES] if inf_ok[s] else []) for s in syms}
    _add_cut_preimages(exprs, cand)
    for r in rels:                     # the finite bounds themselves
        for side in r.arguments:
            side = sympify(side)
            if side.is_number and not A.is_inf(side):
                for s in A.rel_syms((r,)):
                    if s in cand and side not in cand[s]:
                        cand[s].append(side)
    cand = _satisfying(cand, combos, A.EXT_PREDS)
    edge = _edge_points(syms, cand, cap, lambda s: A.draw_ext(combos.get(s, ()), rng, inf_ok[s]))
    points += [p for p in edge if _complete(p) and A.holds_all(rels, p)]
    return points
