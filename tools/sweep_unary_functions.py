"""Sweep of SymPy's one-argument functions for ``knowledge/domain.py``'s
``SWEPT_UNARY`` (#239).

    python tools/sweep_unary_functions.py [--check]

Imports ``sympy`` and the modules of ``MODULES`` and walks every
``Function`` subclass that keeps ``Function``'s generic
``_eval_is_commutative`` (not an undefined function, not a class in a
``.tests.`` module or outside ``sympy``).  Each class is
applied, evaluated and unevaluated, to one argument of each non-commutative
term at level 2 (``A``, ``-A``, ``A + 1``, ``A*B``, ``exp(A)``, ...).  The
term is then rebuilt by ``doit()``, ``doit(deep=False)``, ``func(*args)``,
``rewrite(exp)`` and ``expand()``.  A class is listed only if it builds
such a term, and no rebuild is commutative (a number, ``zoo``) and none of
the first three raises or times out.  Prints the sorted list as
``module.qualname`` lines; with ``--check``, compares it with
``SWEPT_UNARY`` and exits 1 if a listed class is now flagged.
"""
import importlib
import signal
import sys

from sympy import Symbol, adjoint, exp, sin
from sympy.core.function import AppliedUndef, Function

from satassume.knowledge.domain import SWEPT_UNARY, constructed_noncommutative

#: modules ``import sympy`` does not load that define functions of
#: non-commutative terms (``Dagger(A)``, ``log1p(A)``)
MODULES = ['sympy.codegen.cfunctions', 'sympy.codegen.numpy_nodes', 'sympy.codegen.scipy_nodes',
           'sympy.physics.quantum', 'sympy.physics.secondquant', 'sympy.physics.wigner',
           'sympy.stats', 'sympy.tensor.functions']
for _m in MODULES:
    try:
        importlib.import_module(_m)
    except ImportError:         # not in this SymPy version
        pass

A, B = Symbol('A', commutative=False), Symbol('B', commutative=False)
ARGS = [A, -A, A + 1, A*B, 2*A, exp(A), A + B, adjoint(A), sin(A), A*B*A, A**2, 1/A]


class _Timeout(Exception):
    pass


def _alarm(*_):
    raise _Timeout()


def _classes():
    todo, seen = [Function], {}
    while todo:
        for c in todo.pop().__subclasses__():
            todo.append(c)
            name = f"{c.__module__}.{c.__qualname__}"
            if (issubclass(c, AppliedUndef) or not name.startswith('sympy.')
                    or '.tests.' in name
                    or getattr(c, '_eval_is_commutative', None) is not Function._eval_is_commutative):
                continue
            seen[name] = c
    return seen


def _flagged(c, args):
    """Whether a level-2 term ``c(a)`` may be rebuilt into a commutative
    term; None if ``c`` builds no such term."""
    built = False
    for a in args:
        for kw in ({}, {'evaluate': False}):
            signal.alarm(5)
            try:
                try:
                    t = c(a, **kw)
                except Exception:
                    continue
                if type(t) is not c or len(t.args) != 1:
                    continue
                built = True
                rebuilds = (t.doit, lambda: t.doit(deep=False), lambda: t.func(*t.args),
                            lambda: t.rewrite(exp), t.expand)
                for k, rebuild in enumerate(rebuilds):
                    try:
                        r = rebuild()
                    except _Timeout:
                        raise
                    except Exception:
                        if k < 3:
                            return True
                        continue
                    if r.is_commutative is not False:
                        return True
            except _Timeout:
                return True
            finally:
                signal.alarm(0)
    return False if built else None


def main():
    signal.signal(signal.SIGALRM, _alarm)
    args = [a for a in ARGS if constructed_noncommutative(a) == 2]
    ok, bad = [], []
    for name, c in sorted(_classes().items()):
        f = _flagged(c, args)
        if f is False:
            ok.append(name)
        elif f:
            bad.append(name)
    for name in ok:
        print(name)
    if '--check' in sys.argv:
        now_bad = sorted(SWEPT_UNARY & set(bad))
        print(f"# {len(ok)} pass, {len(bad)} flagged; listed but flagged: {now_bad}",
              file=sys.stderr)
        return 1 if now_bad else 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
