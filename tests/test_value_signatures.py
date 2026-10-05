"""Value signatures of compiled template patterns (``templates._common._SIG``).

A pattern compiled for some constant values is reused for other values when
the new values give the same outcome to every table guard the compilation
evaluated and fall in the same fact class (``const_class``).  A wrong
signature silently gives wrong clauses, so this file compiles every node
both ways and compares the clauses:

* *exact*: ``SIGNATURES = False`` and empty caches before each node, so
  every pattern is compiled for its own values;
* *signature*: the signature table is kept warm across all nodes, and only
  the exact-key cache is emptied before each node, so a node whose
  signature was seen takes the shared pattern.

The nodes: every constant of the recorded corpus (``CORPUS_CONSTANTS``) and
a fuzz of random rationals, integers (primes, composites, units, signs,
large values) and special constants, placed in every argument position of
Add, Mul and Pow nodes (two and three arguments, numeric and symbolic
partners) and of the unary function templates.  Also: ``const_facts``
agrees with SymPy for every constant (the fact-class claim), and the
signature path is actually taken (hits are counted).

    PYTHONHASHSEED=0 python -m pytest -q tests/test_value_signatures.py
"""
import random

import pytest

sympy = pytest.importorskip("sympy")

from sympy import (  # noqa: E402
    Add, E, Float, GoldenRatio, I, Integer, Mul, Pow, Rational, S, Symbol,
    TribonacciConstant, exp, log, nan, oo, pi, sin, zoo,
)

from satassume.rules import PREDICATES  # noqa: E402
from satassume.templates import _common, registry  # noqa: E402

#: the distinct numeric atoms of the recorded corpus (queries.jsonl)
CORPUS_CONSTANTS = [
    -1, Rational(-1, 2), Rational(-1, 4), Rational(-1, 8), -11, -2, Rational(-2, 5), -22, -3,
    Rational(-3, 4), -4, -5, Rational(-5, 3), Rational(-5, 4), -6, -7, Rational(-7, 2), -8, -9,
    Rational(-9, 2), -oo, 0, Float('0.866025403784439'), 1, Float('1.0'), Float('1.4'),
    Float('1.73205080756888'), Rational(1, 2), Rational(1, 25), Rational(1, 3), Rational(1, 4),
    Rational(1, 7), Rational(1, 8), 10, 11, 12, 12345678901234567890, 15, 17, Rational(17, 2),
    Rational(17, 62), 18, 2, Float('2.0'), Float('2.47'), Rational(2, 3), Rational(2, 5), 22, 25,
    3, Float('3.0'), Float('3.14159265358979'), Rational(3, 2), Rational(3, 4), 4, Float('4.0'),
    5, Rational(5, 2), Rational(5, 3), Rational(5, 4), 6, 7, Float('7.2123'), 8, E, GoldenRatio,
    I, TribonacciConstant, nan, oo, pi, zoo,
]

SPECIAL = [S.Zero, S.One, S.NegativeOne, S.Half, -S.Half, I, -I, pi, E, oo, -oo, zoo, nan,
           GoldenRatio, Float('0.0'), Float('-1.0'), Float('0.5'), Float('-2.5'), Float('1e30')]


def fuzz_constants(seed=0, n=150):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        k = rnd.randrange(6)
        if k == 0:
            out.append(Integer(rnd.randint(-40, 40)))
        elif k == 1:
            out.append(Integer(rnd.choice([-1, 1]) * rnd.randint(10**6, 10**20)))
        elif k == 2:
            out.append(Rational(rnd.randint(-30, 30), rnd.randint(1, 12)))
        elif k == 3:
            out.append(Rational(rnd.randint(-10**9, 10**9), rnd.randint(1, 10**6)))
        elif k == 4:
            out.append(Integer(rnd.choice([2, 3, 5, 7, 11, 13, 101, 7919, 2**31 - 1, 2**61 - 1,
                                           4, 9, 15, 49, 2**32, 561, 7917])) * rnd.choice([1, -1]))
        else:
            out.append(rnd.choice(SPECIAL))
    return [S(c) for c in out]


def _nodes(consts):
    x, y = Symbol('x'), Symbol('y')
    p = Symbol('p', positive=True)
    k = Symbol('k', integer=True)
    out = []
    for c in consts:
        c = S(c)
        for t in (x, p, k, x * y):
            out += [Add(c, t, evaluate=False), Mul(c, t, evaluate=False),
                    Pow(c, t, evaluate=False), Pow(t, c, evaluate=False),
                    Add(c, t, y, evaluate=False), Mul(c, t, y, evaluate=False),
                    Mul(c, I, pi, t, evaluate=False), Mul(c, I, pi, evaluate=False),
                    exp(Mul(c, I, pi, t, evaluate=False), evaluate=False)]
        out += [Mul(c, I, evaluate=False), Add(c, I, evaluate=False),
                Pow(c, S.Half, evaluate=False), Pow(c, -1, evaluate=False),
                Pow(c, 2, evaluate=False), Pow(2, c, evaluate=False), Pow(E, c, evaluate=False),
                Pow(I, c, evaluate=False), Pow(-1, c, evaluate=False),
                sin(c, evaluate=False), log(c, evaluate=False), exp(c, evaluate=False)]
    return out


def _canonical(e):
    compiled, formulas = registry.clauses_for(e)
    blocks = []
    for c in compiled:
        clauses = tuple(sorted(tuple(sorted(lits)) for lits, _, _ in c.pattern.clauses))
        blocks.append((tuple(map(str, c.objs)), c.pattern.node, clauses, c.pattern.complete))
    return tuple(sorted(blocks)), tuple(sorted(map(str, formulas)))


def _one(e):
    _common._CACHE.clear()
    registry._clauses_cache.clear()
    try:
        return _canonical(e)
    except Exception as exc:  # noqa: BLE001  (compared like a result)
        return ("raises", type(exc).__name__)


def _clear_all():
    _common._CACHE.clear()
    _common._SIG.clear()
    registry._clauses_cache.clear()


def _compare(monkeypatch, nodes):
    _clear_all()
    hits = [0]
    orig = _common._signature_facts

    def counting(key, gen, consts, node):
        n = len(_common._CACHE)
        rec = []
        real = _common._Recorder

        class R(real):
            __slots__ = ()

            def __init__(self, v):
                super().__init__(v)
                rec.append(1)

        monkeypatch.setattr(_common, "_Recorder", R)
        pat = orig(key, gen, consts, node)
        monkeypatch.setattr(_common, "_Recorder", real)
        if not rec:
            hits[0] += 1
        return pat

    monkeypatch.setattr(_common, "_signature_facts", counting)
    sig = [_one(e) for e in nodes]
    monkeypatch.setattr(_common, "SIGNATURES", False)
    _clear_all()
    exact = []
    for e in nodes:
        _common._CFACTS.clear()
        _common._CLASS.clear()
        exact.append(_one(e))
    _clear_all()
    diff = [e for e, a, b in zip(nodes, sig, exact) if a != b]
    assert not diff, f"signature and exact patterns differ for {diff[:5]}"
    return hits[0]


def test_corpus_constants_both_ways(monkeypatch):
    nodes = _nodes(CORPUS_CONSTANTS)
    hits = _compare(monkeypatch, nodes)
    assert hits > 100, hits   # the signature path is taken


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_fuzz_constants_both_ways(monkeypatch, seed):
    consts = fuzz_constants(seed)
    random.Random(seed).shuffle(consts)
    hits = _compare(monkeypatch, _nodes(consts))
    assert hits > 100, hits


@pytest.mark.parametrize("seed", [0, 1])
def test_const_facts_agree_with_sympy(seed):
    """Every constant of a fact class has the class's facts (in any order
    of first use)."""
    consts = list(map(S, CORPUS_CONSTANTS)) + SPECIAL + fuzz_constants(seed, 400)
    consts += [Integer(n) for n in range(-60, 61)] + [Rational(p, q) for p in range(-9, 10)
                                                      for q in range(2, 7)]
    random.Random(seed).shuffle(consts)
    _common._CFACTS.clear()
    _common._CLASS.clear()
    try:
        for c in consts:
            fv = _common.const_facts(c)
            got = [fv[i] for i in range(len(PREDICATES))]
            want = [_common.const_value(c, p) for p in PREDICATES]
            assert got == want, (c, [(p, a, b) for p, a, b in zip(PREDICATES, got, want) if a != b])
    finally:
        _common._CFACTS.clear()
        _common._CLASS.clear()


def test_signature_reuses_pattern_across_values():
    """``3*x`` and ``5*x`` (odd primes) share the pattern; ``2*x`` (even)
    and ``-3*x`` (negative: other guard outcome) do not."""
    x = Symbol('x')
    _clear_all()
    try:
        pats = {}
        for c in (3, 5, 2, -3):
            _common._CACHE.clear()
            registry._clauses_cache.clear()
            compiled, _ = registry.clauses_for(Mul(c, x, evaluate=False))
            pats[c] = compiled[0].pattern
        assert pats[3] is pats[5]
        assert pats[2] is not pats[3]
        assert pats[-3] is not pats[3]
    finally:
        _clear_all()


def test_raw_read_is_not_shared(monkeypatch):
    """A generator that reads a constant outside a table guard is kept
    under its exact key only."""
    _clear_all()
    try:
        x = Symbol('x')
        calls = []

        def gen_for(consts):
            def gen():
                c = consts[0]           # a raw read
                calls.append(c)
                return [((), ((1, 'positive' if c > 2 else 'negative', True),))]
            return gen

        for c in (3, 5):
            consts = _common.consts_of((Integer(c), x))
            _common.facts(('test-raw', 2, _common.pattern_key('t', 2, consts)),
                          gen_for(consts), consts, (Integer(c), x), 1)
        assert len(calls) == 2
        assert not any(k[0] == 'test-raw' for k in _common._SIG)
    finally:
        _clear_all()
