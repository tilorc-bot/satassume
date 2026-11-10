"""`_CACHE` after a query Rust refuses and Python reruns (the `_CACHE` fix, issue 323; test_cache_rollback.py).

    cache_rollback.py py|rust [PLANT]

One process, the installs in live.py's order, then the queries; prints one JSON line: the answers, `_CACHE`'s keys (repr, in
order), `_SPLIT`'s row count, and term_live's refusals. PLANT is a term_live plant (666 `mark-cuts-patterns`).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def queries():
    from sympy import Add, I, Mul, Pow, Q, Rational, S, Symbol, cosh, pi, E
    y = Symbol('y', real=True)
    return [
        # f6 1008: refused for an LRA callback on a derived term, after its five patterns were built
        Q.real(cosh(Add(y, Mul(S(1), I, pi, evaluate=False), evaluate=False), evaluate=False)),
        # wiring 4264
        Q.positive(Pow(E, Mul(Rational(1, 3), pi, I, evaluate=False), evaluate=False)),
    ]


def main():
    mode = sys.argv[1]
    plant = sys.argv[2] if len(sys.argv) > 2 else None
    if mode == 'rust':
        import p_install
        p_install.install()
    from satassume import sympy_api
    from satassume.knowledge.templates import _common
    from satassume.state import memos
    refused = None
    if mode == 'rust':
        import backend
        backend.install_euf()
        import term_live
        term_live.from_env()
        term_live.PLANT[0] = plant
        import lra_live
        lra_live.from_env()
        import session_live
        session_live.from_env()
        import knowledge_live
        knowledge_live.from_env()
        backend.install()
    answers = [sympy_api.ask(q) for q in queries()]
    if mode == 'rust':
        refused = {k: v for k, v in term_live.COUNTS.items() if k.startswith('refused')}
    split = [len(t) for name, _, t in memos.PROCESS.items() if name == 'satassume.engine._SPLIT']
    print(json.dumps(dict(answers=answers, keys=[repr(k) for k in _common._CACHE], split=split, refused=refused)))


if __name__ == '__main__':
    main()
