"""The comparison of a family of rows (``templates/<family>.py``, #249) with
the legacy generators it replaces (``tests/_legacy_<family>_rules.py``).

For every node of the corpus (each head applied, unevaluated, to constants,
special values, multiples of ``pi`` and ``I*pi``, shifts by them, and
symbols) the compiled clauses of the head's template are computed with the
rows and with the legacy generator plus the family's ``ADDED`` rows, each
from empty caches.  The two must entail each other under the rule base:
the same facts follow, though the clauses differ (an implied row is not
written).  ``ADDED`` are the facts the rows give that the legacy rules did
not, each with its argument; :func:`check_added_are_new` checks that each
is new.
"""
from sympy import (
    Add, And, E, EulerGamma, Float, GoldenRatio, I, Mul, Rational, S, Symbol, oo, pi, sqrt,
)

from satassume.knowledge.rules import BASIS, RULE_CLAUSES
from satassume.knowledge.templates import _common, registry, wiring
from satassume.knowledge.templates._rows import rules
from satassume.knowledge.templates.registry import _split
from satassume.sat.solver import Solver


def arguments():
    x_, y_, n = Symbol('x'), Symbol('y'), Symbol('n', integer=True)
    r, p, im = Symbol('r', real=True), Symbol('p', positive=True), Symbol('i', imaginary=True)
    consts = [S.Zero, S.One, S.NegativeOne, Rational(2), Rational(1, 2), Rational(-3, 2),
              pi, E, I, -I, S.Infinity, S.NegativeInfinity, S.ComplexInfinity, S.NaN,
              Float(0.5), Float(2.0), GoldenRatio, EulerGamma, sqrt(2), 2 + I, oo*I]
    pis = [Mul(c, pi, evaluate=False) for c in (Rational(1, 2), Rational(3, 2), Rational(-1, 4),
                                                  Rational(7, 6), Rational(1, 3), 2, 3, -1)]
    pis += [pi*c*s for c in (1, 2, 3, Rational(1, 2), Rational(3, 2), Rational(1, 3))
            for s in (x_, n, r)]
    pis += [I*pi, I*pi*n, I*pi*n/2, I*x_, I*r]
    # r + I*pi*c*s (cosh)
    shifts = [x_ + I*pi, r + I*pi, r + 2*I*pi, r + I*pi*n, r + 2*I*pi*n, im + I*pi*n,
              x_ + y_ + I*pi, Add(y_, -y_, 2*I*pi*n, evaluate=False)]
    syms = [x_, n, r, p, im, x_ + 1, x_ - pi, Add(x_, -x_, evaluate=False), 1/x_, x_**2]
    return consts + pis + shifts + syms


def nodes(heads):
    return [h(a, evaluate=False) for h in heads for a in arguments()]


def both(gen, extra):
    def both(R, c):
        gen(R, c)
        extra(R, c)
    return both


def legacy_templates(legacy_gen, added):
    """``(legacy, legacy plus added)``: the templates of the legacy
    generators, without and with the ``added`` rows."""
    legacy = {h: wiring.template(h, g) for h, g in legacy_gen.items()}
    plus = {h: wiring.template(h, both(g, rules(h, added[h], __name__)) if h in added else g)
            for h, g in legacy_gen.items()}
    return legacy, plus


def rows_templates(heads, family):
    """The registered template of each head, attributed to the family."""
    name = f"{wiring.__name__}:{family}"
    out = {}
    for h in heads:
        ts = [t for t in registry.templates_for(h) if t.__module__ == name]
        assert len(ts) == 1, (h, ts)
        out[h] = ts[0]
    return out


def compiled(templates, e):
    cs, formulas = [], []
    _split(templates[type(e)](e), cs, formulas)
    return cs, sorted(map(str, formulas))


def run(templates, corpus):
    _common._CACHE.clear()
    try:
        return {e: compiled(templates, e) for e in corpus}
    finally:
        _common._CACHE.clear()


def _var(k, i):
    return k * len(BASIS) + i + 1


def _solver(c):
    """A solver holding the pattern's clauses and the rule base on each slot."""
    s = Solver()
    for k in range(c.pattern.nobjs):
        for cl in RULE_CLAUSES:
            s.add_clause([(1 if l > 0 else -1) * _var(k, abs(l) - 1) for l in cl])
    for lits, _, _ in c.pattern.clauses:
        s.add_clause([-_var(k, i) if neg else _var(k, i) for k, i, neg in lits])
    return s


def not_entailed(a, b):
    """The clauses of ``b`` that ``a`` (with the rule base) does not entail."""
    s = _solver(a)
    return [lits for lits, _, _ in b.pattern.clauses
            if s.solve([_var(k, i) if neg else -_var(k, i) for k, i, neg in lits])]


def differences(new, old):
    """Per node: clauses of ``new`` that ``old`` lacks, and the reverse."""
    out = {}
    for e in new:
        (cn, fn), (co, fo) = new[e], old[e]
        assert fn == fo, e
        assert [(tuple(map(str, c.objs)), c.pattern.node) for c in cn] == \
               [(tuple(map(str, c.objs)), c.pattern.node) for c in co], e
        gained = [l for a, b in zip(co, cn) for l in not_entailed(a, b)]
        lost = [l for a, b in zip(cn, co) for l in not_entailed(a, b)]
        if gained or lost:
            out[e] = (gained, lost)
    return out


def check_rows_entail_exactly(heads, family, legacy_gen, added):
    """The rows and the legacy generators plus ``added`` entail each other on
    every node of the corpus; returns the rows' compiled clauses."""
    _, plus = legacy_templates(legacy_gen, added)
    corpus = nodes(heads)
    new, old = run(rows_templates(heads, family), corpus), run(plus, corpus)
    diff = differences(new, old)
    assert not diff, list(diff.items())[:3]
    assert sum(1 for cs, _ in new.values() if cs) > len(corpus) // 2
    return new


def check_added_are_new(legacy_gen, added):
    """Every conjunct of every added row, alone on top of the legacy rules,
    gives a clause the legacy rules do not entail."""
    legacy, _ = legacy_templates(legacy_gen, added)
    for h, extra in added.items():
        e = h(Symbol('x'), evaluate=False)
        _common._CACHE.clear()
        [old], _ = compiled(legacy, e)
        for row in extra:
            prem, concl = row.args
            for c in (concl.args if isinstance(concl, And) else (concl,)):
                _common._CACHE.clear()
                plus = wiring.template(h, both(legacy_gen[h], rules(h, prem >> c, __name__)))
                [new], _ = compiled({h: plus}, e)
                assert not_entailed(old, new), (h, prem, c)
    _common._CACHE.clear()
