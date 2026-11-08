"""Step 6g(a): direct checks of Rust's dispatch (term/dispatch.rs) against Python's `TemplateRegistry.clauses_for`.
Run from this directory: `python dispatch_direct.py [PLANT]`. Each check says whether it was reached; exit 1 on any
difference, so a plant (SLICE_SESSION_PLANT's dispatch-* names, passed as PLANT) shows as caught by a nonzero exit.

1. Same (compiled, formulas) as Python for a spread of nodes, including a subclass that redefines an `_eval_is_` fact
   (`_redefines`), equal-but-distinct undefined-function classes (the ordering_of_classes case: classes equal under `==`),
   and functions applied to nan (`_applied_to_nan`).
2. Epoch: a template registered after the first query reaches Rust (register, re-ask, match Python), via the engine.
3. A user-registered template sends the class to Python's path (`registry:python:user`).
"""
import os
import sys

# harness.state lives in the repo's tests/ (run from rust-spike/slice)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tests'))

if len(sys.argv) > 1:
    os.environ['SLICE_SESSION_PLANT'] = sys.argv[1]
os.environ.pop('SESSION_REPORT', None)

import term_live
term_live.from_env()
import knowledge_live
knowledge_live.from_env()

from sympy import (Abs, Function, Q, S, Symbol, cos, exp, gamma, log, oo, pi, sin, sqrt, zoo, nan, Rational,
                   Integer, besselj, Piecewise, floor)
from satassume import engine as E, sympy_api as A
from satassume.sat.formula import P, Not
from satassume.knowledge.templates import TemplateRegistry, registry
from harness.state import reset_module_state

D = knowledge_live.DISPATCH[0]
assert D is not None, 'dispatch not installed'
PY = TemplateRegistry.clauses_for.__get__(registry)
BAD = []


def key(r):
    compiled, formulas = r
    # By content: with no query on the stack atoms' patterns are built by Rust per call (6g(a)), not Python's cached object.
    return ([(_pat(c.pattern), tuple(c.objs)) for c in compiled], list(formulas))


def _pat(p):
    return (repr(p.rules), repr(p.clauses), p.used, p.complete, p.node, p.nobjs, repr(p.child_preds))


def same(e, what):
    ours, theirs = key(D.clauses_for(e)), key(PY(e))
    if ours != theirs:
        BAD.append((what, e))
        print('DIFF', what, e, ours, theirs)


x, y = Symbol('x'), Symbol('y', positive=True)


class mysin(sin):
    """A subclass redefining a fact sin has: `_redefines` keeps only sin's own-facts templates."""
    def _eval_is_zero(self):
        return None


from sympy.core.cache import clear_cache
f1 = Function('f')
clear_cache()
f2 = Function('f')
assert f1 == f2 and f1 is not f2
nodes = [x, y, S(2), Rational(1, 3), pi, S.Half, x + y, x * y, x ** 2, sqrt(x), exp(x), log(y), sin(x), cos(x + 1),
         Abs(x), gamma(x), besselj(1, x), floor(x), Piecewise((x, x > 0), (1, True)), mysin(x), f1(x), f2(x),
         Abs(nan), sin(oo - x), gamma(zoo), Abs(x + oo), sin(x + 1)]
opq = [Abs(nan), sin(oo - x), gamma(zoo), Abs(x + oo), Abs(x), sin(x + 1)]
from satassume.knowledge.templates import _applied_to_nan
for e in opq:
    if D.is_opaque(e) != _applied_to_nan(e):
        BAD.append(('opaque', e))
        print('DIFF opaque', e)
for e in nodes:
    same(e, 'node')
# twice: the memo's answer equals the first
for e in nodes:
    same(e, 'memo')


def fresh():
    reset_module_state(sympy_cache=False)
    A.set_default_engine(E.Engine())


G = Function('G')
q = Q.positive(G(x))
fresh()
before = A.ask(q)
registry.register(G)(lambda e: P('positive', e))
fresh()
after_rust = A.ask(q)
counts = D.counts()
user = counts.get('registry:python:user', 0)
# Python's answer after the registration, with the dispatch off
saved = registry.__dict__.pop('clauses_for')
fresh()
after_py = A.ask(q)
registry.clauses_for = saved
same(G(x), 'user')
print('epoch: before', before, 'after rust', after_rust, 'after python', after_py, 'user path', user)
if after_rust != after_py:
    BAD.append(('epoch', q))
if user == 0:
    BAD.append(('user path not taken', q))
print('counts', {k: v for k, v in sorted(D.counts().items()) if not k.startswith('registry:python:') or
                 k in ('registry:python:user', 'registry:python:_load', 'registry:python:wide_formulas')})
print('reached: nodes', len(nodes), 'opaque', len(opq), 'BAD', len(BAD))
sys.exit(1 if BAD else 0)
