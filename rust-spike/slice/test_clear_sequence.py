"""Item 4h: the clear() test. sa-port-256's 1/One sequence (h2.py cases int:condio and int:engio: a custom fact holding
int 1, then one holding One, a new Engine per ask) with `memos.PROCESS.clear()` and SymPy's `clear_cache()` before every
ask after the first, in both orders, on Python and Rust: the same answers and the same state after it (the moved process
memos by content and order, as the digest reads them, and `_common._CACHE`'s keys). The planner's bar item (10 Nov ~19:35):
"The 1/One sequence after PROCESS.clear() must give the same answers on Python and Rust."

    python test_clear_sequence.py py|rust SHAPE ORDER     one process; prints one JSON line
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def main(mode, shape, order):
    sys.path.insert(0, HERE)
    if mode == 'rust':
        import two_order
        two_order.install('rust')
    from sympy import Q, S, Symbol
    from sympy.assumptions import Predicate
    from sympy.core.cache import clear_cache
    from satassume import sympy_api
    from satassume.engine import Engine
    from satassume.knowledge.extensions import Args
    from satassume.knowledge.templates import _common
    from satassume.sat.formula import P, And, Implies
    from satassume.state import memos
    import moved_digest as md
    ext = sympy_api.extensions
    s = Symbol('s')
    hb = Predicate('hbig')
    cur = [None]
    if shape == 'cond':     # hbig(s) & positive(<the handler's 1>) -> positive(s): the answer needs the facts of the node 1
        ext.register('hbig', Symbol)(lambda a: Implies(And(P('hbig', a), P('positive', cur[0])), P('positive', a)))
    one = {'1': 1, '2': S.One}      # query 1: the fact holds int 1; query 2: One
    out = []
    for n, i in enumerate(order):
        if n:
            memos.PROCESS.clear()
            clear_cache()
        cur[0] = one[i]
        try:
            if shape == 'eng':      # the Engine-level API: P atoms with a plain int as expr
                out.append(repr(Engine().ask(P('positive', cur[0]), P('real', s))))
            else:
                out.append(repr(sympy_api.ask(Q.positive(s), hb(s), Engine())))
        except Exception as e:
            out.append('EXC %s: %s' % (type(e).__name__, str(e)[:80]))
    state = {}
    for name, _, c in memos.PROCESS.items():
        if name.rsplit('.', 1)[-1] in md.PROC and len(c):
            rows = [(md.show(a), md.show(b)) for a, b in list(c.items())] if not name.endswith('_SPLIT') else \
                [(md.show(r[0]), md.show(r[1]), md.show(r[2])) for _, r in list(c.items())]
            state[name] = [md._h(sorted(rows)), md._h(rows), len(rows)]
    state['_CACHE'] = [repr(k) for k in _common._CACHE]
    print(json.dumps(dict(answers=out, state=state)))


def run(mode, shape, order):
    env = dict(os.environ)
    for k in ('SLICE_TERM_PLANT', 'SLICE_SESSION_PLANT', 'SLICE_KNOWLEDGE_PLANT', 'SLICE_PLANT'):
        env.pop(k, None)
    out = subprocess.run([sys.executable, os.path.abspath(__file__), mode, shape, order], env=env, cwd=HERE,
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


@pytest.mark.parametrize('shape', ['cond', 'eng'])
@pytest.mark.parametrize('order', ['12', '21'])
def test_the_one_sequence_after_clear_is_pythons(shape, order):
    py, rust = run('py', shape, order), run('rust', shape, order)
    assert len(py['answers']) == 2 and not any(a.startswith('EXC') for a in py['answers']), py
    assert rust['answers'] == py['answers']
    assert rust['state'] == py['state']


def test_each_query_answers_alike_in_either_order_after_clear():
    """With the memos cleared between asks, a query's answer doesn't depend on which came first. (That int 1 answers None
    where One answers True is the #96 bug of the Python reference, held in fix/cache-key-type and out of the slice by R2;
    both backends give it.)"""
    for shape in ('cond', 'eng'):
        a, b = run('py', shape, '12')['answers'], run('py', shape, '21')['answers']
        assert a == b[::-1], (shape, a, b)


if __name__ == '__main__':
    main(*sys.argv[1:4])
