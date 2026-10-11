"""Find the rows of the Add and Mul templates that the rest of the block
and the rule base already imply (issue #149, R1a).

A template block is a set of rules over the objects of a node (its
arguments and itself); the engine instantiates the rule base
(``rules.RULE_INSTANTIATED``) on every one of those objects.  A row is
*redundant* when, in every pattern the template builds (every arity and
every kind of constant argument), each clause the row gives is implied by
the clauses the other rows give plus the rule base on every slot.  Deleting
redundant rows keeps every pattern logically equivalent to what it was, so
no answer can change (the engine is complete over the clauses it emits, and
the demand split only delays clauses: escalation emits the rest).

Usage (z3 from the venv)::

    PYTHONPATH=.:SYMPY python tools/minimise.py            # greedy: rows that can go
    PYTHONPATH=.:SYMPY python tools/minimise.py --sizes    # clauses per pattern now

A row is named by its source: ``add:LINE`` for a ``rule(...)`` call of
``core._add_rules`` (one per line, all loop instances together, split by the
predicates it mentions) and ``mul:NAME`` for a ``MUL_TABLE`` row (split by
the ``$p`` instance).  The greedy pass tries the rows with the most
literals first and keeps a deletion only if every deleted row stays implied
in every pattern of :func:`shapes`; it reports the deletable rows, which are
then removed by hand from ``core.py`` (``tests/test_template_minimal.py``
re-proves each deletion).
"""
from __future__ import annotations

import ast
import inspect
import sys
import textwrap
import time
from collections import defaultdict

import z3
from sympy import Catalan, E, EulerGamma, Float, GoldenRatio, I, Rational, S, pi, oo, zoo, nan

from satassume.knowledge.rules import BASIS, NPRED, RULE_INSTANTIATED, expand_clause, unit_propagate
from satassume.knowledge.templates import _common, core
from satassume.knowledge.templates import table
from satassume.knowledge.templates.table import expand



def _loop_vars():
    """For each line of ``core._add_rules`` holding a ``rule(...)`` call, the
    loop variables of its enclosing ``for`` loops other than the argument
    index ``k``: they tell the row's instances apart."""
    src = inspect.getsource(core._add_rules)
    first = core._add_rules.__code__.co_firstlineno
    out = {}

    def walk(node, names):
        if isinstance(node, ast.For):
            names = names + [n.id for n in ast.walk(node.target) if isinstance(n, ast.Name) and n.id != 'k']
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'rule':
            out[first + node.lineno - 1] = tuple(names)
        for child in ast.iter_child_nodes(node):
            walk(child, names)
    walk(ast.parse(textwrap.dedent(src)), [])
    return out


LOOP_VARS = _loop_vars()

#: One constant of every kind the guards and ``const_value`` tell apart.
CONSTS = (S.Zero, S.One, S.NegativeOne, Rational(2), Rational(-2), Rational(3), Rational(4),
          Rational(1, 2), Rational(-1, 2), Rational(3, 2), Rational(1, 3), Rational(-2, 3),
          Float(1.5), Float(-2.0), pi, E, EulerGamma, GoldenRatio, Catalan, I, oo, -oo, zoo, nan)
#: A smaller set for patterns with two constants.
CONSTS2 = (S.One, S.NegativeOne, Rational(2), Rational(1, 2), Rational(-1, 2), Float(1.5),
           pi, E, I, oo, -oo, zoo)
MAX_N = 5
#: 'up' (default): a deleted clause must follow by unit propagation;
#: 'sem' (--semantic): by implication (z3).
MODE = 'up'


def shapes():
    """``(kind, n, consts)`` for the Add and Mul patterns checked: every
    arity up to ``MAX_N`` with no constant, one constant in the first slot
    (and in the last, for n == 2), and two constants for n <= 3."""
    out = []
    for kind in ('add', 'mul'):
        for n in range(1, MAX_N + 1):
            out.append((kind, n, {}))
            for c in CONSTS:
                out.append((kind, n, {0: c}))
                if n == 2:
                    out.append((kind, n, {1: c}))
            if 2 <= n <= 3:
                for c in CONSTS2:
                    for d in CONSTS2:
                        out.append((kind, n, {0: c, 1: d}))
            if kind == 'mul' and 3 <= n <= 4:
                # the I*pi*c*s blocks (_mul_factor_sets)
                cs = {n - 3: I, n - 2: pi} if n == 3 else {0: Rational(1, 2), 1: I, 2: pi}
                out.append((kind, n, cs))
    return out


def tagged_rules(kind, n, consts):
    """``[(tag, premises, conclusion)]`` of one pattern, before resolution."""
    out = []
    if kind == 'mul':
        cur = [None]
        orig_specs = table._row_specs

        def row_specs(row, slots, p):
            cur[0] = p
            return orig_specs(row, slots, p)
        table._row_specs = row_specs
        try:
            for row, prem, concl in expand(core._table('MUL_TABLE'), core.MUL_GUARDS,
                                           {'n': n, 'consts': consts}, {'N': n, '*': range(n)}):
                out.append((('mul:' + row.name, cur[0] or ''), list(prem), list(concl)))
        finally:
            table._row_specs = orig_specs
        return out
    orig = _common.Rules.rule

    def rule(self, premises, conclusion):
        f = sys._getframe(1)
        if f.f_code.co_name == 'equiv':
            f = f.f_back
        orig(self, premises, conclusion)
        ps, cs = self.rules[-1]
        loop = ','.join(str(f.f_locals[v]) for v in LOOP_VARS.get(f.f_lineno, ()))
        out.append((('add:%d' % f.f_lineno, loop), ps, cs))
    _common.Rules.rule = rule
    try:
        core._add_rules(n, consts)
    finally:
        _common.Rules.rule = orig
    return out


def basis_clauses(rules, consts):
    """The rules resolved against ``consts``, as clauses over the basis:
    ``(slot, basis index, positive)`` literals."""
    out = []
    for ps, cs in _common.resolve([(p, c) for p, c in rules], consts):
        out += expand_clause([(k, p, not pos) for k, p, pos in ps] + [(k, p, pos) for k, p, pos in cs])
    return out


class Checker:
    """Implication over the rule base on ``nobjs`` objects (z3)."""

    def __init__(self, nobjs):
        self.v = [[z3.Bool(f"o{k}_{BASIS[i]}") for i in range(NPRED)] for k in range(nobjs)]
        self.block = [z3.Or([self.v[k][abs(l) - 1] if l > 0 else z3.Not(self.v[k][abs(l) - 1])
                             for l in cl]) for k in range(nobjs) for cl in RULE_INSTANTIATED]

    def lit(self, k, i, pos):
        return self.v[k][i] if pos else z3.Not(self.v[k][i])

    def unimplied(self, premises, goals):
        """The clauses of ``goals`` that ``premises`` and the rule base do
        not imply."""
        s = z3.Solver()
        s.add(self.block)
        s.add([z3.Or([self.lit(*l) for l in cl]) for cl in premises])
        return [cl for cl in goals if s.check([self.lit(k, i, not pos) for k, i, pos in cl]) != z3.unsat]


_CHECKERS: dict = {}


def checker(nobjs):
    c = _CHECKERS.get(nobjs)
    if c is None:
        c = _CHECKERS[nobjs] = Checker(nobjs)
    return c


def deletion_holds(shape, tagged, removed):
    """Whether every clause of the rows ``removed`` is implied, in the
    pattern ``shape``, by the other rows and the rule base."""
    kind, n, consts = shape
    gone = [(p, c) for t, p, c in tagged if t in removed]
    if not gone:
        return True
    try:
        goals = basis_clauses(gone, consts)
        kept = basis_clauses([(p, c) for t, p, c in tagged if t not in removed], consts)
    except ValueError:      # a constant contradicts a rule: not a real pattern
        return True
    if MODE == 'up':
        return all(up_implied(kept, cl, n + 1) for cl in goals)
    return not checker(n + 1).unimplied(kept, goals)


def _var(k, i, pos):
    v = k * NPRED + i + 1
    return v if pos else -v


def _block(nobjs):
    return [tuple(_var(k, abs(l) - 1, l > 0) for l in cl)
            for k in range(nobjs) for cl in RULE_INSTANTIATED]


def up_implied(kept, cl, nobjs):
    """Whether the clauses ``kept`` and the rule base propagate every
    literal of ``cl`` once its other literals are false (unit propagation
    only, as ``rules.minimize_for_propagation``): wherever ``cl`` would
    propagate, the rest propagates the same literal, so deleting ``cl``
    changes neither the models nor what propagation derives."""
    clauses = tuple(_block(nobjs) + [tuple(_var(*l) for l in c) for c in kept])
    lits = [_var(*l) for l in cl]
    for l in lits:
        derived = unit_propagate(clauses, [-m for m in lits if m != l])
        if derived is not None and l not in derived:
            return False
    return True


def pattern_size(kind, n, consts, removed=frozenset()):
    tagged = tagged_rules(kind, n, consts)
    cl = _common.Pattern(_common.resolve([(p, c) for t, p, c in tagged if t not in removed], consts),
                         n, n + 1).clauses
    return len(cl), sum(len(c[0]) for c in cl)


def greedy(verbose=True):
    allshapes = shapes()
    tagged = {sh_key(s): tagged_rules(*s) for s in allshapes}
    weight = defaultdict(int)
    for kind in ('add', 'mul'):
        for t, p, c in tagged[(kind, 2, ())]:
            weight[t] += len(p) + len(c)
    tags = sorted({t for v in tagged.values() for t, _, _ in v}, key=lambda t: (-weight[t], t))
    removed = set()
    order = list(allshapes)
    for t in tags:
        trial = removed | {t}
        t0 = time.time()
        bad = None
        for i, s in enumerate(order):
            if not deletion_holds(s, tagged[sh_key(s)], trial):
                bad = s
                order.insert(0, order.pop(i))
                break
        if bad is None:
            removed = trial
        if verbose:
            print(f"{'DELETE' if bad is None else 'keep  '} {t[0]:28} {t[1]:60} "
                  f"w={weight[t]:3} ({time.time() - t0:.1f}s)"
                  + ('' if bad is None else f"  needed in {bad[0]} n={bad[1]} {fmt_consts(bad[2])}"),
                  flush=True)
    return removed


def sh_key(s):
    return (s[0], s[1], tuple((k, type(c), c) for k, c in sorted(s[2].items())))


def fmt_consts(consts):
    return '{' + ', '.join(f"{k}: {c}" for k, c in sorted(consts.items())) + '}'


def main(argv):
    if '--sizes' in argv:
        for kind in ('add', 'mul'):
            for n in range(2, MAX_N + 1):
                for consts in ({}, {0: S(2)}, {0: S.NegativeOne}, {0: Rational(1, 2)}):
                    print(kind, n, fmt_consts(consts), *pattern_size(kind, n, consts))
        return 0
    global MODE
    if '--semantic' in argv:
        MODE = 'sem'
    removed = greedy()
    print("\nDeletable rows:")
    for t in sorted(removed):
        print(" ", t[0], t[1])
    print("\nClauses/literals per pattern, now -> without them:")
    for kind in ('add', 'mul'):
        for n in range(2, MAX_N + 1):
            for consts in ({}, {0: S(2)}, {0: S.NegativeOne}, {0: Rational(1, 2)}, {0: I}, {0: oo}):
                print(" ", kind, n, fmt_consts(consts), '%d/%d -> %d/%d' % (
                    *pattern_size(kind, n, consts), *pattern_size(kind, n, consts, removed)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
