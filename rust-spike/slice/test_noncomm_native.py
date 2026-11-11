"""`_noncommutative_atoms` native (B's item 2; group-d-cause.md C7's cb_noncomm): entry.rs `noncommutative_atoms` reads
each vocabulary atom's term from domain.py's `_NONCOMM` memo, and calls domain's `_noncommutative` only on a miss
(`nc:memo_miss`, `ent:cb_noncomm`). Engine.ask and Engine.verdict (context.rs) no longer call the Python helper.

The case: `Engine.ask` about a non-commutative symbol answers None (the engine stays out of matrices), the first time
(memo miss) and again (memo hit); a contextual ask with such an assumption is None too; Python's helper gets no call
from Rust (a counting wrapper on engine._noncommutative_atoms), and a commutative symbol's query is unchanged.
Plant 623 `nc-memo-true-false`: a memo row of True is read as False, so the second query is decided (`commutative` is true
by definition) or raises: not None, which the answer check catches (not the plant's counter)."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _main(plant):
    import test_discovery_core as D
    D._rust()
    import sa_solver
    from sympy import Symbol
    from satassume import P
    from satassume import engine as E
    if plant != 'none':
        sa_solver.formula_plant(plant)
    calls = [0]
    real = E._noncommutative_atoms

    def counted(*a):
        calls[0] += 1
        return real(*a)
    E._noncommutative_atoms = counted
    A, x = Symbol('A', commutative=False), Symbol('x')
    eng = E.Engine()
    c0 = dict(sa_solver.session_counts())
    def ask(*a):
        try:
            return repr(eng.ask(*a))
        except Exception as e:
            return type(e).__name__
    rows = [ask(P('commutative', A)), ask(P('commutative', A)), ask(P('real', x), P('positive', A)),
            ask(P('commutative', x))]
    c1 = dict(sa_solver.session_counts())
    print(json.dumps(dict(rows=rows, py_calls=calls[0], miss=c1['nc:memo_miss'] - c0['nc:memo_miss'])))


def _run(plant='none'):
    e = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]), PYTHONHASHSEED='0')
    e.pop('SLICE_SESSION_PLANT', None)
    r = subprocess.run([sys.executable, __file__, plant], capture_output=True, text=True, env=e, cwd=HERE)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


def test_noncommutative_terms_answer_none_with_no_python_helper_call():
    j = _run()
    assert j['rows'] == ['None', 'None', 'None', 'True'], j
    assert j['py_calls'] == 0, j
    assert j['miss'] >= 1, j


def test_a_memo_true_read_as_false_answers_wrongly():
    j = _run('nc-memo-true-false')
    assert j['rows'][0] == 'None' and j['rows'][1] != 'None', j


if __name__ == '__main__':
    _main(sys.argv[1])
