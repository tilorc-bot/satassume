"""Slice C, a direct comparison: random terms, the wrappers on ids against Python's own functions on the objects.

    relations_direct.py N SEED [--plant NAME] [--out FILE]

`_eq_links` runs on a recording session, so the trace compared is every ensure, var allocation, selector and emit, in order: that
is what var numbering rests on. `_eq_infinity`'s plan is gone (C2b): it runs in `relations_core.rs`, compared in
`test_relations_core.py`. Also
`relation_atom` for all six names, `_ext_atoms`, `_is_number`, `affine_pair`, `_under_apps`, `zero_twin`, `structural`, `interned`
and `_structural_subterms`. Fresh dev and fuzz make 0 nonempty `_under_apps`, so this is that function's evidence too. A refusal is counted by reason and is no evidence. `differs:*` is a finding. Exit 0 with none.
"""
import argparse
import collections
import random
import sys

from sympy import And, Q, Rational, S, oo, pi, sqrt, zoo
from satassume import relations as R, scope, sympy_api as A
from satassume.sat.formula import P
from satassume.theories.euf import euf_adapter as EA
from satassume.knowledge.extensions import Args

import convert
import sa_solver
import term_ids_direct_terms as T
import term_live as TL


#: Closed sides: Rationals answer False, a closed non-Rational answers None, the infinities answer True for their own.
NUMBERS = (S(2), S(-3), Rational(1, 2), S.Zero, pi, sqrt(2), pi + 1, 2*pi, oo, -oo, zoo)


class Rec:
    """A session that records. `is_` answers by a fixed rule, so all three of `_eq_infinity`'s paths run."""
    def __init__(self):
        self.log, self.vars, self.n, self.engine = [], {}, 100, self

    def is_(self, e, pred):
        self.log.append(('is_', e, pred))
        return {oo: pred == 'positive_infinite', -oo: pred == 'negative_infinite'}.get(e, False if e.is_Rational else None)

    def ensure(self, e, preds):
        self.log.append(('ensure', e, type(e).__name__, sorted(preds)))

    def var(self, pred, e):
        k = (pred, e)
        if k not in self.vars:
            self.n += 1
            self.vars[k] = self.n
            self.log.append(('var', pred, e, self.n))
        return self.vars[k]

    def emit(self, clause):
        self.log.append(('emit', list(clause)))


class Rel:
    def __init__(self, s):
        self.session = s

    def _atom_selector(self, atom):
        s = self.session
        s.n += 1
        s.log.append(('selector', s.n))
        return s.n


def trace(method, atom):
    s = Rec()
    method(Rel(s), 7, atom)
    return s.log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('n', type=int)
    ap.add_argument('seed', type=int)
    ap.add_argument('--plant')
    ap.add_argument('--out')
    a = ap.parse_args()
    r = random.Random(a.seed)
    undo = TL.install(terms=True)
    TL.PLANT[0] = a.plant
    c, bad = collections.Counter(), []

    def differs(what, *detail):
        c['differs:' + what] += 1
        if len(bad) < 12:
            bad.append((what,) + tuple(repr(x)[:160] for x in detail))

    def step(what, f):
        c['asked:' + what] += 1
        try:
            f()
        except sa_solver.TermRefuse as e:
            c[f'refused:{what}:{e}'] += 1
        else:
            c['answered:' + what] += 1

    def same(what, want, got, *case):
        if want != got or repr(want) != repr(got):
            differs(what, *case, want, got)

    for _ in range(a.n):
        p, q0 = T.term(r), T.term(r)
        k = r.random()
        if k < 0.3:
            q0 = r.choice((oo, -oo))
            if r.random() < 0.5:
                # A closed side, so `_eq_infinity`'s callback on `is_` runs: each of its three answers, by `Rec.is_`.
                p = r.choice(NUMBERS)
        third = T.term(r)
        conv = convert.convert(And(Q.positive(p), Q.positive(q0), Q.positive(third)), True, A.default_engine())
        if isinstance(conv, convert.Kept):
            c['kept:' + conv.reason] += 1
            continue
        q = TL._Query(conv)
        TL.stack().append(q)
        try:
            c['cases'] += 1
            for name in ('eq', 'ne', 'lt', 'gt', 'le', 'ge'):
                step('relation_atom:' + name, lambda: same('relation_atom:' + name, R.relation_atom.__wrapped__(name, p, q0),
                                                           R.relation_atom(name, p, q0), name, p, q0))
            step('_ext_atoms', lambda: same('_ext_atoms', R._ext_atoms.__wrapped__(p, q0), R._ext_atoms(p, q0), p, q0))
            for e in (p, q0, third):
                step('_is_number', lambda: same('_is_number', R._is_number.__wrapped__(e), R._is_number(e), e))
                step('structural', lambda: same('structural', EA.structural.__wrapped__(e), EA.structural(e), e))
                step('_under_apps', lambda: same('_under_apps', set(R._under_apps.__wrapped__(e)), set(R._under_apps(e)), e)
                     if R._under_apps.__wrapped__(e) == R._under_apps(e) else differs('_under_apps', e))
                step('zero_twin', lambda: same('zero_twin', R.zero_twin.__wrapped__(e), R.zero_twin(e), e))
                step('subterms', lambda: same('subterms', R._structural_subterms.__wrapped__(e), R._structural_subterms(e), e))
            step('interned', lambda: same('interned', EA.EUFAdapter.interned.__wrapped__(None, [p, q0, third]),
                                          EA.EUFAdapter.interned(None, [p, q0, third]), p, q0, third))
            atoms = [P('positive', e) for e in (p, q0, third)]
            step('affine_pair', lambda: same('affine_pair', scope.affine_pair.__wrapped__(atoms), scope.affine_pair(atoms), p, q0, third))
            atom = P('eq', Args((p, q0)))
            for name, m in (('_eq_links', R.Relations._eq_links),):
                step(name, lambda: same(name, trace(m.__wrapped__, atom), trace(m, atom), p, q0))
        except Exception as e:
            differs('raised', p, q0, type(e).__name__, e)
        finally:
            TL.stack().pop()
    undo()
    out = sys.stdout if a.out is None else open(a.out, 'w')
    for k in sorted(c):
        print(f'{c[k]}\t{k}', file=out)
    for k in sorted(TL.COUNTS):
        if k.startswith(('plan:', 'is_:', 'under_apps:', 'zero_twin', 'affine_pair:', 'term:py:')):
            print(f'{TL.COUNTS[k]}\t{k}', file=out)
    for b in bad:
        print(b, file=out)
    sys.exit(1 if any(k.startswith('differs:') for k in c) else 0)


main()
