# Reproduces a history-dependent answer of satassume.sympy_api.ask.
# Run from anywhere inside a satassume checkout, or from its root (needs sympy):
#   PYTHONHASHSEED=0 python this_file.py
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(_d, 'harness', '__init__.py')):
    if os.path.dirname(_d) == _d:       # not inside a checkout: try the cwd
        _d = os.getcwd()
        break
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from harness.checker import Ask, Event, execute, ReferenceLevel
from harness.state import EngineConfig
from harness.sympy_io import from_srepr
config = EngineConfig(**{'name': 'default', 'discovery_budget': 400, 'session_limit': 2000, 'keep_sessions': 16, 'cone_search': True, 'cone_threshold': 3, 'transfer': True, 'uninterpreted': 'none', 'relevance': True, 'relations': 'default', 'cache_size': 200000, 'custom_cache_size': 200000, 'answers_size': 100000, 'splits_size': 20000})
items = [
    Ask(from_srepr("Implies(AppliedPredicate(Q.transcendental, Mul(Symbol('w', nonzero=True), Pow(Symbol('j', integer=True, even=True), Integer(2)))), AppliedPredicate(Q.transcendental, Rational(1, 2)))"), from_srepr("And(AppliedPredicate(Q.commutative, Symbol('j', integer=True, even=True)), AppliedPredicate(Q.noninteger, Mul(I, Symbol('w', nonzero=True), Pow(Symbol('j', integer=True, even=True), Integer(2)))), AppliedPredicate(Q.extended_negative, Mul(I, Pow(Symbol('w', nonzero=True), Integer(2)), Pow(Symbol('j', integer=True, even=True), Integer(4)), Add(Mul(Integer(-1), Pow(Symbol('w', nonzero=True), Integer(-2)), Pow(Symbol('j', integer=True, even=True), Integer(-4))), Mul(I, Symbol('w', nonzero=True), Pow(Symbol('j', integer=True, even=True), Integer(2)))))))")),
    Ask(from_srepr("Equivalent(AppliedPredicate(Q.extended_nonpositive, Symbol('j', integer=True, even=True)), AppliedPredicate(Q.finite, Symbol('p', positive=True)))"), from_srepr("And(AppliedPredicate(Q.commutative, Symbol('j', integer=True, even=True)), AppliedPredicate(Q.noninteger, Mul(I, Symbol('w', nonzero=True), Pow(Symbol('j', integer=True, even=True), Integer(2)))), AppliedPredicate(Q.extended_negative, Mul(I, Pow(Symbol('w', nonzero=True), Integer(2)), Pow(Symbol('j', integer=True, even=True), Integer(4)), Add(Mul(Integer(-1), Pow(Symbol('w', nonzero=True), Integer(-2)), Pow(Symbol('j', integer=True, even=True), Integer(-4))), Mul(I, Symbol('w', nonzero=True), Pow(Symbol('j', integer=True, even=True), Integer(2)))))))")),
]
rows, eng = execute(items, config, ref_level=ReferenceLevel.NONE, ref_for_last=True)
last = rows[-1]
print('engine after prefix:', last.warm, '  fresh engine:', last.ref)
assert last.warm == 'ValueError' and last.ref == 'True', (last.warm, last.ref)
