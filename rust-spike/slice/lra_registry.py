"""The registry item, on slice D's bar: Python with history and Rust have to agree. One process, no reset between queries, an
engine kept across them, so `_CONSTANTS`, `_INTERPRETED` and SymPy's cache carry over. Each sequence registers constants in its own
order. `reset_module_state` doesn't clear `_CONSTANTS`, so a constant's index is fixed by its first registration in the process: a
reversed order needs its own process (the ORDER argument) or constants not yet seen (`FRESH`). Writes answers and the registry after
each query, so two runs compare by `cmp`. The two ORDERs have to differ from each other, or this says nothing about order.

    lra_registry.py py|rust OUT 01|10
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
mode, out, order = sys.argv[1:4]
if mode == 'rust':
    import backend
    backend.install()
    import lra_backend
    lra_backend.install()
    import term_live
    term_live.from_env()
    import lra_live
    lra_live.from_env()

from sympy import E, EulerGamma, Q, Symbol, cos, exp, log, pi, sin, sqrt  # noqa: E402
from harness.state import reset_module_state  # noqa: E402
from satassume import engine as En, sympy_api as A  # noqa: E402
from satassume.theories.lra import constfield as CF  # noqa: E402

x, y = Symbol('x', real=True), Symbol('y', real=True)
A0, B0 = log(2), log(3)


def block(a, b):
    """Every form that registers `a` or `b`, or reads a registered one back: as a coefficient, a constant, an order between them."""
    return [(Q.lt(a * x, 1), Q.eq(x, 0)), (Q.lt(b * x, 1), Q.eq(x, 0)), (Q.gt(a * x + b * y, a), Q.gt(x, 1) & Q.gt(y, 1)),
            (Q.lt(a, b), True), (Q.positive(a - b), True), (Q.lt(a * b * x, a + b), Q.eq(x, 0)), (Q.eq(a * x, b * x), Q.ne(x, 0)),
            (Q.lt(a * x, b), Q.lt(x, 0)), (Q.integer(a * x + 1), Q.integer(x))]


PAIRS = ((log(2), log(3)), (sin(1), cos(2)), (sqrt(2), sqrt(3)), (pi, E), (EulerGamma, log(5)), (exp(3), sqrt(5)), (log(7), sqrt(7)))


# In one process: ascending, then reversed, each on constants nothing has registered yet.
FRESH = ((log(11), log(13)), (log(19), log(17)), (sqrt(11), sqrt(13)), (sqrt(19), sqrt(17)))


def registry():
    return [(c.index, str(c.key)[:80], c.name, c.transcendental) for c in CF._CONSTANTS]


def run(fh, name, seq, engine):
    for i, (p, a) in enumerate(seq):
        if engine is None:
            A.set_default_engine(En.Engine())
        try:
            r = repr(A.ask(p, a))
        except Exception as e:
            r = f'{type(e).__name__}: {e}'
        g = hashlib.blake2b(repr(registry()).encode(), digest_size=8).hexdigest()
        fh.write(f'{name}\t{i}\t{r}\t{len(CF._CONSTANTS)}\t{g}\n')


with open(out, 'w') as fh:
    # Each scenario starts clean, then keeps its history.
    for keep in (True, False):                  # one engine throughout, or a new engine per query with the memos left alone
        first, second = int(order[0]), int(order[1])
        reset_module_state(sympy_cache=False)
        eng = En.Engine()
        A.set_default_engine(eng)
        for k, pair in enumerate(PAIRS):
            seq = block(pair[first], pair[second]) + block(pair[second], pair[first])
            run(fh, f'keep={keep}:pair={k}', seq, eng if keep else None)
        for k, (a, b) in enumerate(FRESH):
            run(fh, f'keep={keep}:fresh={k}', block(a, b) + block(b, a), eng if keep else None)
        fh.write('registry\t' + repr(registry()) + '\n')
    # The same query twice and a re-register after other work: a memo's hit must read as its first read did.
    reset_module_state(sympy_cache=False)
    A.set_default_engine(En.Engine())
    seq = block(log(2), sin(1)) * 2 + block(sin(1), log(2)) + block(log(2), sin(1))
    run(fh, 'repeat', seq, None)
    fh.write('registry\t' + repr(registry()) + '\n')
if mode == 'rust':
    print(lra_live.counts())
    print({k: v for k, v in term_live.COUNTS.items() if k.startswith(('refused', 'fault', 'kept'))})
