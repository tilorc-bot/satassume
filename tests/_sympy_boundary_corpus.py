"""Corpus of ``tests/test_sympy_boundary.py``: generic queries through
``satassume.sympy_api.ask(..., strict=True)`` under the runtime trap
(``tests/_sympy_trap.py``), one per template family and theory.  Run in a
subprocess of its own (the trap patches SymPy process-wide):

    python -I tests/_sympy_boundary_corpus.py ROOT

Prints one JSON object: the answers, the trap's events and how many calls
went through the strict check.  Every symbol is plain: the facts are Q facts.
"""
import json
import os
import sys

ROOT = os.path.abspath(sys.argv[1])
sys.path[:0] = [ROOT, os.path.join(ROOT, "tests")]

import _sympy_trap  # noqa: E402

_sympy_trap.install(os.path.join(ROOT, "satassume"))

from sympy import (Abs, E, Eq, I, Implies, Integer, Q, Rational, Symbol, cos,  # noqa: E402
                   exp, floor, im, log, pi, re, sin, sqrt)

from satassume import sympy_api  # noqa: E402

# the trap watches PKG: a satassume imported from elsewhere would record nothing
assert os.path.abspath(sympy_api.__file__).startswith(_sympy_trap.PKG), sympy_api.__file__

x, y, z = Symbol("x"), Symbol("y"), Symbol("z")

# (proposition, assumptions, expected: True, False, None or "ValueError")
CORPUS = [
    # signs and parity of sums
    (Q.positive(x + y), Q.positive(x) & Q.positive(y), True),
    (Q.even(x + y), Q.odd(x) & Q.odd(y), True),
    (Q.odd(x + 1), Q.even(x), True),
    (Q.nonnegative(x + y), Q.nonnegative(x) & Q.positive(y), True),
    # products
    (Q.negative(x*y), Q.positive(x) & Q.negative(y), True),
    (Q.even(x*y), Q.even(x) & Q.integer(y), True),
    (Q.zero(x*y), Q.nonzero(x) & Q.nonzero(y), False),
    (Q.real(2*x), Q.real(x), True),
    # powers
    (Q.positive(x**2), Q.real(x) & Q.nonzero(x), True),
    (Q.nonnegative(x**2), Q.real(x), True),
    (Q.real(sqrt(x)), Q.nonnegative(x), True),
    (Q.integer(x**y), Q.integer(x) & Q.positive(y) & Q.integer(y), True),
    (Q.positive(2**x), Q.real(x), True),
    # exp and log
    (Q.positive(exp(x)), Q.real(x), True),
    (Q.real(log(x)), Q.positive(x), True),
    (Q.positive(log(x)), Q.positive(x - 1), True),
    (Q.real(log(x)), Q.gt(x, 0) & Q.real(x), True),
    # trigonometric
    (Q.real(sin(x)), Q.real(x), True),
    (Q.real(cos(x)), Q.real(x), True),
    (Q.zero(sin(pi*x)), Q.integer(x), True),        # sin(pi*k*s) is 0 for integer k, s (#180 S7)
    # Abs, floor, re, im
    (Q.nonnegative(Abs(x)), Q.complex(x), True),
    (Q.zero(Abs(x)), Q.nonzero(x), False),
    (Q.integer(floor(x)), Q.real(x), True),
    (Q.negative(floor(x)), Q.negative(x), True),
    (Q.real(re(x)), Q.complex(x), True),
    (Q.zero(im(x)), Q.real(x), True),
    # relations (LRA, EUF)
    (Q.positive(x), Q.gt(x, 1) & Q.real(x), True),
    (Q.lt(x, z), Q.lt(x, y) & Q.lt(y, z), True),
    (Q.eq(x, y), Q.le(x, y) & Q.ge(x, y), True),
    (Q.gt(x + y, 0), Q.gt(x, 0) & Q.gt(y, 0), True),
    (Q.integer(x), Q.gt(x, 0) & Q.lt(x, 1), False),
    (x > 0, Q.positive(x), True),
    (Eq(x, y), Q.eq(y, x), True),
    # constants
    (Q.positive(pi), True, True),
    (Q.transcendental(E), True, True),
    (Q.imaginary(I), True, True),
    (Q.real(I*pi), True, False),
    (Q.rational(Rational(3, 4)), True, True),
    # primes
    (Q.prime(Integer(7)), True, True),
    (Q.composite(Integer(91)), True, True),
    (Q.prime(x*y), Q.prime(x) & Q.prime(y), False),
    # Booleans and an inconsistent set
    (Q.positive(x) | Q.zero(x), Q.nonnegative(x), True),
    (Implies(Q.real(x), Q.positive(x**2)), Q.nonzero(x), True),
    (Q.real(x), Q.positive(x) & Q.negative(x), "ValueError"),
]

strict = [0]
_check = sympy_api.check_strict


def _counting_check(*exprs):
    strict[0] += 1
    return _check(*exprs)


sympy_api.check_strict = _counting_check

answers = []
for prop, assumptions, expected in CORPUS:
    try:
        r = sympy_api.ask(prop, assumptions, strict=True)
    except _sympy_trap.TrapError as e:
        r = f"TrapError: {e}"
    except ValueError:
        r = "ValueError"
    answers.append({"query": f"{prop} | {assumptions}", "answer": r, "expected": expected})

# the trap is armed: a call made from a frame in the package directory
def _probe(code):
    fn = os.path.join(_sympy_trap.PKG, "_trap_probe.py")
    try:
        exec(compile(code, fn, "exec"), {"Symbol": Symbol, "x": x})
    except _sympy_trap.TrapError:
        return "TrapError"


n = len(_sympy_trap.EVENTS)
canary = {"forbidden": _probe("x.simplify()"),
          "symbol_assumption": _probe("Symbol('p', positive=True).is_real")}
canary["events"] = sorted(e["kind"] for e in _sympy_trap.EVENTS[n:])
del _sympy_trap.EVENTS[n:]
# a cached method that is not a constructor is checked itself, not allowed
# as cacheit's wrapper
canary["cached"] = _probe("(x**2 + x).as_leading_term(x)")
del _sympy_trap.EVENTS[n:]

# strict is on: a symbol declared with an assumption is rejected
try:
    sympy_api.ask(Q.real(Symbol("p", positive=True)), strict=True)
    rejected = False
except sympy_api.AssumptionSymbolError:
    rejected = True

print(json.dumps({"answers": answers, "events": _sympy_trap.EVENTS, "strict_checks": strict[0],
                  "queries": len(CORPUS), "rejected": rejected, "canary": canary}, default=str))
