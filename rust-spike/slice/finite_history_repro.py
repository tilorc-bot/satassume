"""`finite` of one term, read twice, answers differently: the pure-SymPy repro (issue 323, the convert step's gate (a)).

The term is the rootof workload's: `m = x*r`, `x` a positive Symbol, `r = ComplexRootOf._new(Poly(z**5 + z + 1), 1)`.
`_new` keeps a poly `rootof` would factor, and rootoftools' `_reals_cache` is keyed by the factors `rootof` isolates, so
this poly is never a key of it. No satassume code runs here. `m.is_finite` is what `convert._Walk._read_finite` reads.
Each row is a forked child: the assumptions shuffle seeded, `m` built new, then `m.is_finite` asked three times, each
printed as its value or as the exception's type.

What it shows: an ask raises KeyError (`_reals_cache[self.poly]`, in `ComplexRootOf._eval_is_real` or
`_eval_is_imaginary`) or answers True, by the order `sympy.core.assumptions._ask` shuffles the prerequisite facts into
(`sympy.core.random._assumptions_rng`), and each ask that raises leaves facts settled in the `_assumptions` of `m` and
`r`, so a later ask of the same object can answer where an earlier one raised. The read's VALUE (None for a raise, which
Rust refuses on, or True) depends on the shuffle's state and on who asked before: SymPy's own state, not the walker's,
not `_Walk`'s memo and not the walk order. With `--rootof` (`r = rootof(z**5 + z + 1, 1, radicals=False)`, the object
`rootof` itself builds) no ask raises.

    python finite_history_repro.py [--rootof] [SEEDS=16]
"""
import os
import sys

from sympy import Poly, Symbol, rootof
from sympy.core import random as sympy_random
from sympy.polys.rootoftools import ComplexRootOf


def ask(m):
    try:
        return repr(m.is_finite)
    except Exception as e:
        return type(e).__name__


def row(seed, proper):
    sympy_random._assumptions_rng.seed(seed)
    z = Symbol('z')
    r = rootof(z**5 + z + 1, 1, radicals=False) if proper else ComplexRootOf._new(Poly(z**5 + z + 1, z), 1)
    m = Symbol('x', positive=True) * r
    return [ask(m), ask(m), ask(m)]


def rows(seeds, proper):
    out = []
    for seed in range(seeds):
        rd, wr = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.write(wr, ' '.join(row(seed, proper)).encode())
            os._exit(0)
        os.close(wr)
        out.append(os.read(rd, 1000).decode().split())
        os.close(rd)
        os.waitpid(pid, 0)
    return out


if __name__ == '__main__':
    proper = '--rootof' in sys.argv
    args = [a for a in sys.argv[1:] if a != '--rootof']
    got = rows(int(args[0]) if args else 16, proper)
    for seed, r in enumerate(got):
        print(seed, *r)
    print('seeds', len(got), 'first ask raised', sum(r[0] != 'True' for r in got), 'second ask differs from first',
          sum(r[1] != r[0] for r in got), 'third differs from second', sum(r[2] != r[1] for r in got))
