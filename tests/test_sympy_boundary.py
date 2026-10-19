"""The SymPy boundary (docs/design.md, "The SymPy boundary"): strict mode
of ``sympy_api.ask``, the static check ``tools/check_sympy_boundary.py``
and the runtime trap over a generic corpus.

The trap patches SymPy process-wide, so the corpus runs in a subprocess
of its own (``tests/_sympy_boundary_corpus.py``, with ``tests/_sympy_trap.py``):
nothing leaks into this process or other tests, and it is xdist-safe (no
shared files; the result comes back on stdout).
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

sympy = pytest.importorskip("sympy")
from sympy import Dummy, Function, Integral, Q, Symbol, Wild, exp, sin

from satassume import DictCache, Engine
from satassume.sympy_api import AssumptionSymbolError, ask, check_strict

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def eng():
    return Engine(cache=DictCache())


# -- strict mode -----------------------------------------------------------

def test_strict_rejects_symbol_assumptions(eng):
    x = Symbol('x', positive=True)
    assert ask(Q.real(x), True, eng) is True        # default: the declaration is a fact
    with pytest.raises(AssumptionSymbolError) as e:
        ask(Q.real(x), True, eng, strict=True)
    assert isinstance(e.value, ValueError)
    assert e.value.symbols == (x,)
    assert "x (positive=True)" in str(e.value)


def test_strict_plain_symbols_with_q_facts(eng):
    x = Symbol('x')
    assert ask(Q.real(x), Q.positive(x), eng, strict=True) is True
    assert ask(Q.positive(x), Q.real(x), eng, strict=True) is None
    assert ask(Q.real(Symbol('c', commutative=True)), Q.real(x), eng, strict=True) is None
    check_strict(True, False, None, Q.real(x))


@pytest.mark.parametrize("s", [Dummy('d', integer=True), Wild('w', real=True),
                               Symbol('z', positive=False), Symbol('A', commutative=False)])
def test_strict_rejects_any_non_default_assumption(eng, s):
    with pytest.raises(AssumptionSymbolError) as e:
        ask(Q.real(s), True, eng, strict=True)
    assert e.value.symbols == (s,)


def test_strict_nested(eng):
    x, p, n = Symbol('x'), Symbol('p', positive=True), Dummy('n', integer=True)
    with pytest.raises(AssumptionSymbolError) as e:
        ask(Q.positive(exp(x + sin(p))), Q.real(x), eng, strict=True)
    assert e.value.symbols == (p,)
    with pytest.raises(AssumptionSymbolError) as e:
        ask(Q.real(x), Q.real(x) & (Q.positive(x) | Q.zero(sin(p) + n)), eng, strict=True)
    assert set(e.value.symbols) == {p, n}
    # a bound symbol counts too
    with pytest.raises(AssumptionSymbolError):
        ask(Q.real(Integral(n, (n, 0, x))), True, eng, strict=True)


def test_strict_undefined_function_assumptions(eng):
    x = Symbol('x')
    f, g = Function('f', real=True), Function('g')
    with pytest.raises(AssumptionSymbolError) as e:
        ask(Q.real(f(x)), True, eng, strict=True)
    assert e.value.symbols == (f,)
    assert ask(Q.real(g(x)), Q.real(g(x)), eng, strict=True) is True


def test_strict_is_checked_before_the_answer_memo(eng):
    p = Symbol('p', positive=True)
    assert ask(Q.real(p), Q.real(p), eng) is True
    hits = eng.stats["cache_hits"]
    assert ask(Q.real(p), Q.real(p), eng) is True
    assert eng.stats["cache_hits"] == hits + 1      # memoized
    with pytest.raises(AssumptionSymbolError):
        ask(Q.real(p), Q.real(p), eng, strict=True)


# -- static check ----------------------------------------------------------

def _checker():
    spec = importlib.util.spec_from_file_location(
        "check_sympy_boundary", ROOT / "tools" / "check_sympy_boundary.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_static_check_passes_on_the_package(capsys):
    assert _checker().main([]) == 0
    assert " 0 unmarked sites" in capsys.readouterr().out


def test_static_check_flags_a_snippet():
    snippet = (
        "def f(e, a, c, name):\n"
        "    e.simplify()\n"                                      # 2
        "    e.equals(a)\n"                                       # 3
        "    e._eval_refine(a)\n"                                 # 4
        "    v = e.is_positive\n"                                 # 5
        "    w = getattr(e, 'is_' + name)\n"                      # 6
        "    u = getattr(e, f'is_{name}')\n"                      # 7
        "    k = e.assumptions0\n"                                # 8
        "    ok = e.is_Add and e.is_number and e.is_commutative\n"
        "    ok = c.is_integer()\n"                               # a method: not SymPy's
        "    ok = getattr(e, 'is_Rational', False)\n"
        "    m = c.is_zero  # sympy-boundary: c a Rational\n"
        "    # sympy-boundary: c a Rational\n"
        "    m = c.is_zero\n"
        "    m = c.is_zero  # sympy-boundary:\n"                  # 15: no reason
        "    G = {'a': lambda x: (x.is_Rational\n"
        "                         and x.is_positive),  # sympy-boundary: x Rational\n"
        "         'b': lambda x: x.is_positive}\n"                # 18: its own item
    )
    lines = [line for line, _ in _checker().check_source(snippet)]
    assert lines == [2, 3, 4, 5, 6, 7, 8, 15, 18]


# -- runtime trap ----------------------------------------------------------

def test_runtime_trap_corpus():
    """Every query of the corpus through ``ask(..., strict=True)`` with
    SymPy's reasoning and simplification trapped: no call is reached from
    satassume but construction (``_sympy_trap.CONSTRUCTION``), and no fact
    of an assumption-carrying symbol is read (the corpus has none)."""
    out = subprocess.run([sys.executable, "-I", str(ROOT / "tests" / "_sympy_boundary_corpus.py"),
                          str(ROOT)], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-3000:]
    d = json.loads(out.stdout.splitlines()[-1])
    # the trap is armed: a probe from the package directory raises and records
    assert d["canary"] == {"forbidden": "TrapError", "symbol_assumption": None,
                           "events": ["forbidden", "symbol_assumption"]}
    assert d["rejected"] and d["strict_checks"] >= d["queries"] >= 40
    bad = [e for e in d["events"] if not e["allowed"]]
    assert not bad, bad
    wrong = [a for a in d["answers"] if a["answer"] != a["expected"]]
    assert not wrong, wrong
