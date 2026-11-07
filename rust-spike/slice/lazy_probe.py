"""Which reads in conversion can evaluate (issue 323, planner's ruling on lazy reads).

Each (term, read) pair runs in its own fork, so no cache or refined root interval carries from one read to the next, and
under its own alarm. An evaluation is counted, not timed: complex(), evalf, and CRootOf's own numeric refinement.
    python lazy_probe.py OUT.tsv [--degree 10] [--limit 60] [--jobs 3]
"""
import argparse
import multiprocessing as mp
import signal
import sys
import time

from sympy import (Abs, Add, CRootOf, Derivative, Eq, FiniteSet, Function, Limit, Lt, Max, Mod, Mul, Piecewise, Pow, Q,
                   Rational, S, Subs, Symbol, Tuple, conjugate, exp, floor, log, pi, re, sign, sin, sqrt, zeta)
from sympy.core.evalf import EvalfMixin
from sympy.core import evalf as evalf_mod
from sympy.core.expr import Expr
from sympy.core.exprtools import decompose_power
from sympy.core.function import AppliedUndef
from sympy.core.numbers import Float
from sympy.core.sorting import default_sort_key
from sympy.polys.rootoftools import ComplexRootOf

from satassume import sympy_api as A
from satassume.knowledge.domain import constructed_noncommutative
from satassume.knowledge.templates import _may_be_nan
from satassume.theories.lra.lra_adapter import _BAD


class Plain(Expr):
    """No handler of its own: `.is_commutative` falls through to SymPy's prerequisite facts."""


def terms(d):
    """name -> builder, so a fork builds only its own term and no other term's refinement reaches its count."""
    x, y = Symbol('x'), Symbol('y')
    f = Function('f')
    r = lambda: CRootOf(x**d - x + 1, 3)
    q = Rational(3, 2)
    return {
        'r': r, 'y+r': lambda: y + r(), 'y*r': lambda: y*r(), '2*r': lambda: 2*r(), 'y+2*r': lambda: y + 2*r(),
        'r+1': lambda: r() + 1, 'r*pi': lambda: r()*pi, 'r+sqrt2': lambda: r() + sqrt(2),
        '2*r*sqrt2': lambda: 2*r()*sqrt(2), 'r**2': lambda: r()**2, 'sqrt(r)': lambda: sqrt(r()), '1/r': lambda: 1/r(),
        'r**r': lambda: r()**r(), 'y**r': lambda: y**r(), 'r**y': lambda: r()**y, 'y**(r/3)': lambda: y**(r()/3),
        'exp(r)': lambda: exp(r()), 'sin(r)': lambda: sin(r()), 'log(r)': lambda: log(r()), 'Abs(r)': lambda: Abs(r()),
        'exp(y+r)': lambda: exp(y + r()), 'exp(y*r)': lambda: exp(y*r()), 'sin(y+r)': lambda: sin(y + r()),
        '(y+r)**2': lambda: (y + r())**2, '(y+r)**(1/3)': lambda: (y + r())**Rational(1, 3),
        'y*(y+r)': lambda: y*(y + r()), 'y**2+r*y': lambda: y**2 + r()*y,
        'Add(r,r,noeval)': lambda: Add(r(), r(), evaluate=False), 'Mul(r,r,noeval)': lambda: Mul(r(), r(), evaluate=False),
        'Pow(r,2,noeval)': lambda: Pow(r(), 2, evaluate=False), 'Mul(0,r,noeval)': lambda: Mul(0, r(), evaluate=False),
        'y+zeta(3)': lambda: y + zeta(3), 'y+exp(exp(5))': lambda: y + exp(exp(5)), 'y+sqrt2': lambda: y + sqrt(2),
        # Forms where decompose_power builds a Pow, which can reach Pow._eval_power and its evalf.
        'Pow(y**r,3/2)': lambda: Pow(y**r(), q, evaluate=False), 'Pow(y*r,3/2)': lambda: Pow(y*r(), q, evaluate=False),
        'Pow(y+r,3/2)': lambda: Pow(y + r(), q, evaluate=False), 'Pow(exp(y+r),3/2)': lambda: Pow(exp(y + r()), q, evaluate=False),
        'Pow(y,r*3/2)': lambda: Pow(y, r()*q, evaluate=False), 'exp(y*r*3/2)': lambda: exp(y*r()*q),
        'Pow(y**(1+r),3/2)': lambda: Pow(y**(1 + r()), q, evaluate=False), 'Pow(sin(y)**r,3/2)': lambda: Pow(sin(y)**r(), q, evaluate=False),
        # Classes whose handlers may answer None, so a fact read falls through to the prerequisites.
        'Plain(r)': lambda: Plain(r()), 'Plain(y+r)': lambda: Plain(y + r()), 'f(r)': lambda: f(r()), 'f(y+r)': lambda: f(y + r()),
        'Piecewise': lambda: Piecewise((r(), y > 0), (1, True)), 'Subs': lambda: Subs(y + r(), y, 1),
        'Derivative': lambda: Derivative(f(y)*r(), y), 'Limit': lambda: Limit(y + r(), y, 0), 'Max(y,r)': lambda: Max(y, r()),
        'floor(y+r)': lambda: floor(y + r()), 're(y+r)': lambda: re(y + r()), 'conjugate(y+r)': lambda: conjugate(y + r()),
        'Mod(y,r)': lambda: Mod(y, r()), 'sign(y+r)': lambda: sign(y + r()), 'Eq(y+r,1)': lambda: Eq(y + r(), 1),
        'Lt(r,y)': lambda: Lt(r(), y), 'FiniteSet(y+r)': lambda: FiniteSet(y + r()), 'Tuple(y,r)': lambda: Tuple(y, r()),
    }


READS = {
    'args': lambda t: t.args,
    'hash': hash,
    'hashable_content': lambda t: tuple(t._hashable_content()),
    'free_symbols': lambda t: t.free_symbols,
    'is_number': lambda t: getattr(t, 'is_number', False),
    'has_nan': lambda t: t.has(S.NaN),
    'has_bad': lambda t: t.has(*_BAD),
    'has_float': lambda t: t.has(Float),
    'atoms_undef': lambda t: t.atoms(AppliedUndef),
    '_may_be_nan': _may_be_nan,
    'is_commutative': lambda t: t.is_commutative,
    'constructed_noncommutative': constructed_noncommutative,
    'as_base_exp': lambda t: t.as_base_exp() if isinstance(t, Expr) else None,
    'decompose_power': decompose_power,
    'is_finite': lambda t: t.is_finite,
    'complex': complex,
    'default_sort_key': default_sort_key,
    'formula_gt': lambda t: A.relation_parts(Q.gt(t, 1)),
    'is_scalar': A._is_scalar,
}
HEAVY = {'complex', 'default_sort_key', 'is_finite'}


class Over(BaseException):
    pass


def _alarm(*_):
    raise Over()


def _count(owner, name, counts, key):
    f = getattr(owner, name)

    def wrapped(*a, **k):
        counts[key] += 1
        return f(*a, **k)
    setattr(owner, name, wrapped)


def one(job):
    term, read, d, limit = job
    try:
        t = terms(d)[term]()
    except Exception as e:
        return (term, read, '0', 0, 0, 0, 'no build ' + type(e).__name__)
    counts = dict(complex=0, evalf=0, root=0)
    _count(Expr, '__complex__', counts, 'complex')
    _count(EvalfMixin, 'evalf', counts, 'evalf')
    EvalfMixin.n = EvalfMixin.evalf
    _count(evalf_mod, 'evalf', counts, 'evalf')
    _count(ComplexRootOf, '_eval_evalf', counts, 'root')
    _count(ComplexRootOf, 'eval_rational', counts, 'root')
    _count(ComplexRootOf, '_refine_complexes', counts, 'root')
    signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, limit)
    s = time.perf_counter()
    # Never str() a result: printing an Add goes through as_ordered_terms, which calls complex(). That made the first
    # run of this script report evaluations in as_base_exp. Only a plain value's text is kept.
    try:
        v = READS[read](t)
        out = str(v) if v is None or isinstance(v, (bool, int)) else type(v).__name__
    except Over:
        out = 'OVER'
    except Exception as e:
        out = 'raises ' + type(e).__name__
    el = time.perf_counter() - s
    signal.setitimer(signal.ITIMER_REAL, 0)
    return (term, read, f'{el:.4f}', counts['complex'], counts['evalf'], counts['root'], out.replace('\t', ' '))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('out')
    p.add_argument('--degree', type=int, default=10)
    p.add_argument('--limit', type=float, default=60)
    p.add_argument('--jobs', type=int, default=3)
    p.add_argument('--after', default=None, help='only the terms listed after this one')
    a = p.parse_args()
    # Cheap reads first, so a stall in the heavy ones leaves the table's useful half written.
    names = list(terms(a.degree))
    if a.after:
        names = names[names.index(a.after) + 1:]
    jobs = [(t, r, a.degree, a.limit) for r in sorted(READS, key=lambda r: r in HEAVY) for t in names]
    ctx = mp.get_context('fork')
    with ctx.Pool(a.jobs, maxtasksperchild=1) as pool, open(a.out, 'w') as f:
        f.write('term\tread\tsec\tcomplex\tevalf\troot\tresult\n')
        for row in pool.imap_unordered(one, jobs):
            f.write('\t'.join(map(str, row)) + '\n')
            f.flush()
        f.write('# done\n')


if __name__ == '__main__':
    main()
