"""The engine must not read facts SymPy's old assumptions cached on an
object, and must not write derived facts into SymPy objects.

Found through satrefine (``tests/refine_identities/needs/
test_checker_ask_poisons_plain_symbols.py`` on ``refine-identities``):

1. SymPy's old assumptions call ``0**n`` finite for a plain ``n``
   (``Pow._eval_is_algebraic`` returns True for a zero base, and algebraic
   implies finite), although ``0**-1`` is ``zoo``; the value is cached in
   ``(0**n)._assumptions``;
2. the engine's former default cache read that dict as facts that hold
   unconditionally, so ``Q.negative(n) & Q.nonnegative(x)`` was declared
   inconsistent (``0**n`` with negative ``n`` is infinite);
3. the root-level fact "``n`` is not negative" was written into
   ``n._assumptions``, which is the one ``StdFactKB`` shared by every symbol
   created with the same assumptions: afterwards
   ``Symbol('anything').is_negative`` was False.

The engine now keeps its own cache and reads SymPy objects only through
the templates (declared symbol assumptions, fixed-value constants); see
``satassume.engine.DictCache``.
"""
import subprocess
import sys
import textwrap

import pytest

sympy = pytest.importorskip("sympy")
from sympy import Symbol, Q, Integer, exp, log, sqrt, Abs

from satassume import Engine
from satassume.engine import DictCache
from satassume.sympy_api import ask, default_engine


def _definite(kb):
    return {k: v for k, v in kb.items() if v is not None}


@pytest.mark.xfail(reason="SymPy: (0**n).is_finite is True for a plain n "
                          "(upstream bug, not patched here)", strict=False)
def test_sympy_zero_power_is_not_finite_for_a_plain_exponent():
    assert (0**Symbol('n')).is_finite is not True


@pytest.mark.parametrize("make_engine", [default_engine, Engine],
                         ids=["default_engine", "Engine()"])
def test_cached_sympy_fact_does_not_make_assumptions_inconsistent(make_engine):
    eng = make_engine()
    n, x = Symbol('n'), Symbol('x')
    e = 0**n
    assert e.is_finite is True          # SymPy caches the wrong fact
    assert ask(Q.positive(e), Q.negative(n) & Q.nonnegative(x), eng) is False
    assert ask(Q.infinite(e), Q.negative(n), eng) is True
    assert ask(Q.finite(e), Q.negative(n), eng) is False
    # context-free, the engine does not take SymPy's cached answer
    assert ask(Q.finite(e), True, eng) is None
    assert eng.is_(e, 'finite') is None


def test_one_ask_does_not_change_other_symbols():
    n, x = Symbol('n'), Symbol('x')
    plain = _definite(Symbol('probe')._assumptions)
    (0**n).is_finite
    ask(Q.positive(0**n), Q.negative(n) & Q.nonnegative(x))
    assert Symbol('fresh').is_negative is None
    assert _definite(Symbol('probe')._assumptions) == plain
    assert _definite(n._assumptions) == plain


def test_engine_does_not_write_sympy_assumptions():
    """Neither context-free nor contextual queries touch ``_assumptions``."""
    y = Symbol('y')
    p = Symbol('p', positive=True)
    exprs = [exp(y), p + 1, p*y, y**2 + 1, Abs(y), log(p), sqrt(p)]
    before = [dict(e._assumptions) for e in exprs]
    eng = Engine()
    for e in exprs:
        for pred in ('positive', 'real', 'finite', 'zero', 'integer'):
            eng.is_(e, pred)
            ask(getattr(Q, pred)(e), Q.real(y), eng)
    assert [dict(e._assumptions) for e in exprs] == before
    assert eng.is_(p + 1, 'positive') is True


def test_declared_symbol_facts_still_used():
    """Only SymPy's *derived* cached facts are ignored; declared ones are
    read through the templates, whether or not SymPy has cached anything."""
    eng = Engine()
    k = Symbol('k', integer=True, negative=True)
    assert ask(Q.finite(0**k), True, eng) is False
    assert ask(Q.real(k), True, eng) is True
    assert eng.is_(k - 1, 'negative') is True
    assert ask(Q.positive(Integer(3)), True, eng) is True


def test_object_cache_name_is_the_engine_cache():
    from satassume import ObjectCache
    assert ObjectCache is DictCache
    assert type(Engine().cache) is DictCache


# -- many queries in one process ---------------------------------------------

_MANY = textwrap.dedent("""
    import itertools
    from sympy import (Symbol, Q, S, exp, log, sqrt, Abs, sin, cos, Pow,
                       Integer, Rational, I, pi)
    from satassume.sympy_api import ask
    from satassume.engine import DictCache

    x, y, n, m = Symbol('x'), Symbol('y'), Symbol('n'), Symbol('m')
    probe = {k: v for k, v in Symbol('probe')._assumptions.items() if v is not None}
    exprs = [0**n, 1**n, 0**(n - 1), x**n, (-1)**n, exp(n), log(x), sqrt(x),
             Abs(x), x*y, x + y, x**2 + 1, n*m, sin(x), x**y, 1/x, 1/(n + 1),
             Pow(0, -1, evaluate=False), 2**n, x - y, exp(I*pi*n)]
    for e in exprs:   # let SymPy cache whatever it believes
        for f in ('finite', 'real', 'positive', 'negative', 'zero',
                  'integer', 'algebraic', 'extended_real'):
            getattr(e, 'is_' + f)
    preds = [Q.positive, Q.negative, Q.zero, Q.nonzero, Q.finite, Q.infinite,
             Q.real, Q.integer, Q.even, Q.odd, Q.rational, Q.algebraic,
             Q.nonnegative, Q.nonpositive, Q.extended_real, Q.imaginary]
    atoms = [p(s) for p in preds for s in (x, n)]
    contexts = [a & b for a, b in itertools.combinations(atoms, 2)][::7]
    contexts += [Q.negative(n) & Q.nonnegative(x), Q.negative(n),
                 Q.negative(x) & Q.negative(n), Q.infinite(n), ~Q.finite(x)]
    answered = asked = 0
    for c in contexts:
        for e in exprs:
            for p in preds[:8]:
                asked += 1
                try:
                    r = ask(p(e), c)
                except ValueError:
                    r = 'inconsistent'
                answered += r is not None
                if r == 'inconsistent' and c in (Q.negative(n) & Q.nonnegative(x),
                                                 Q.negative(n)):
                    raise SystemExit(f"consistent assumptions {c} called inconsistent")
    for i in range(20):
        s = Symbol(f'fresh{i}')
        facts = {k: v for k, v in s._assumptions.items() if v is not None}
        assert facts == probe, (s, facts, probe)
        for f in ('negative', 'positive', 'zero', 'finite', 'real', 'integer'):
            assert getattr(s, 'is_' + f) is None, (s, f)
    for s in (x, y, n, m):
        facts = {k: v for k, v in s._assumptions.items() if v is not None}
        assert facts == probe, (s, facts)
    assert ask(Q.negative(n), Q.negative(n)) is True
    print(asked, answered)
""")


def test_many_asks_leave_fresh_symbols_untouched():
    out = subprocess.run([sys.executable, "-c", _MANY], capture_output=True,
                         text=True, timeout=900)
    assert out.returncode == 0, out.stderr[-3000:] + out.stdout[-2000:]
    asked, answered = map(int, out.stdout.split()[-2:])
    assert asked > 1000 and answered > 0
