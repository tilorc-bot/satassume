"""plant322.py (sa-port-322): shows each token of the count build fires on a planted case (FALSE ZEROS rule). Each case is a
list of queries and the tokens that must appear; a missing token is a FAIL row. Run as nc322.py is (same environment)."""
import os, sys
sys.argv = [sys.argv[0], "plant", "-"]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nc322
from nc322 import L, sa_solver, sympy_api, session_live
from sympy import Q, Symbol, symbols, Rational, pi, sqrt, Function
from satassume.sympy_api import Engine, default_engine
x, y = symbols("x y")
n = Symbol("n", integer=True)
A, B = symbols("A B", commutative=False)
f = Function("f")
fails = 0


def case(name, want, fn):
    global fails
    sa_solver.nc322_take()
    try:
        r = fn()
    except Exception as e:
        r = "raise " + type(e).__name__ + " " + str(e)[:60]
    ev = sa_solver.nc322_take()
    toks = ev.split(";")
    heads = set()
    for t in toks:
        heads.add(t); heads.add(t.split(":")[0]); heads.add(t[:2]); heads.add(t[:1])
    miss = [w for w in want if w not in heads]
    fails += bool(miss)
    print(("FAIL" if miss else "PASS"), name, "want", want, "missing", miss, "r", r, "ev", ev[:260])


def ask(p, a=True, **k):
    return sympy_api.ask(p, a, **k)


def with_bb(v, fn):
    old = L.BRANCH_BUDGET
    L.BRANCH_BUDGET = v
    try:
        return fn()
    finally:
        L.BRANCH_BUDGET = old


def with_plant(name, fn):
    old = session_live.PLANT[0]
    session_live.plant(name) if hasattr(session_live, "plant") else session_live.PLANT.__setitem__(0, name)
    try:
        return fn()
    finally:
        session_live.plant(old) if hasattr(session_live, "plant") else session_live.PLANT.__setitem__(0, old)


def small_budget():
    e = Engine()
    e.discovery_budget = 1
    return ask(Q.positive(x + y), Q.positive(x) & Q.positive(y), engine=e)


case("independent None, contextual", ["Q<", "Q>N", "V<", "V>c", "S<", "s", "e<", "e>N", "T00"], lambda: ask(Q.positive(x), Q.real(x)))
case("True under a set", ["Q>T"], lambda: ask(Q.real(x), Q.positive(x)))
case("False under a set", ["Q>F"], lambda: ask(Q.negative(x), Q.positive(x)))
case("context-free atom: is_ and _decide", ["I<", "I>N", "D<", "D>N"], lambda: ask(Q.positive(x + y)))
case("fact-cache hit", ["H"], lambda: (ask(Q.real(x + 1), Q.real(x)), ask(Q.positive(x + 1), Q.real(x) & Q.real(y)))[-1])
case("inconsistent set", ["V>i", "Q>X"], lambda: ask(Q.real(x), Q.positive(x) & Q.negative(x)))
case("consistent() after propagation", ["c<", "w"], lambda: ask(Q.real(x), Q.positive(x) & Q.real(y)))
case("discovery budget 1", ["B"], small_budget)
case("non-commutative", ["N"], lambda: ask(Q.positive(A * B), Q.real(x)))
case("BRANCH_BUDGET 1 (test_lra_exhaustion's set)", ["xb", "V>u"],
     lambda: with_bb(1, lambda: ask(Q.positive(n), Q.ge(n, 0) & Q.le(n, 1) & Q.ne(n, 0) & Q.ne(n, 1), engine=Engine())))
case("BRANCH_BUDGET 0, query flags", ["xb", "T01"],
     lambda: with_bb(0, lambda: ask(Q.gt(n, 3), Q.gt(n, Rational(1, 3)) & Q.lt(n, 7), engine=Engine())))
case("derived predicate (entails_all)", ["a<"], lambda: ask(Q.nonzero(x) | Q.zero(y), Q.real(x) & Q.real(y)))
case("ring hit", ["s:1:1:1:1", "s:1:1:1:2"], lambda: ask(Q.positive(x), Q.real(x) & Q.real(y)))
case("planted check raise (run with SLICE_SESSION_PLANT=ctx-check-raise): the catch and fallback", ["C", "F"], lambda: ask(Q.positive(x), Q.real(x), engine=Engine()))
case("LRA gives up (test_lra_constant_coefficients.py:398's set)", ["g"], lambda: ask(Q.real(x), Q.eq(x, (1 + sqrt(2)) ** 2) & Q.eq(x, 3 + 2 * sqrt(2)) & Q.positive(f(3 + 2 * sqrt(2))), engine=Engine()))
for off in (pi, sqrt(2), pi / 7):
    case("certificate bound skip, offset %s" % off, ["xs"], lambda: ask(Q.gt(y, 2), Q.integer(x + off) & Q.gt(x, 1) & Q.gt(y, x + 1), engine=Engine()))
case("engine-level non-commutative", ["N"], lambda: Engine().ask(sympy_api._formula(Q.positive(x), False), sympy_api._formula(Q.real(A * B + x), False)))
case("is_many (reached through Engine.ask above)", [], lambda: None)


def _atom(prop):
    fm = sympy_api._formula(prop, False)
    return fm.expr, fm.pred


def constructing():   # sa-port-323: the re-entrant None of Engine.is_ (engine.py:2020, entry.rs:614)
    e = Engine()
    node, pred = _atom(Q.positive(x + y))
    e._constructing.add(node)
    try:
        return e.is_(node, pred)
    finally:
        e._constructing.discard(node)


def is_noncomm():     # sa-port-323: Engine.is_ on a non-commutative node (engine.py:2018, entry.rs:610)
    node, pred = _atom(Q.positive(A * B))
    return Engine().is_(node, pred)


case("_constructing None", ["K"], constructing)
case("is_ on a non-commutative node", ["N"], is_noncomm)
# sa-port-323: sympy_api routes every non-commutative query away before the engine ("matrix"), so the engine's own
# refusals are reached only by a caller of the engine (as rust-spike/slice/test_noncomm_native.py does).
from satassume import P
case("Engine.ask about a non-commutative symbol", ["Q<", "N", "Q>N"], lambda: Engine().ask(P("commutative", A)))
case("Engine.is_ on a non-commutative node", ["I<", "N"], lambda: Engine().is_(A * B, "positive"))
# the certificate-bound skip needs a value larger than the certificate's bound Y at a split: tried with large offsets
for k in (3, 30, 300, 3000):
    case("certificate bound skip, 10**%d + 1/2 <= n <= 10**%d + pi" % (k, k), ["xs"],
         lambda: ask(Q.even(n), Q.ge(n, 10 ** k + Rational(1, 2)) & Q.le(n, 10 ** k + pi), engine=Engine()))
print("FAILS", fails)
