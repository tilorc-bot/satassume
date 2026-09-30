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
config = EngineConfig(**{'name': 'budget', 'discovery_budget': 5, 'session_limit': 2000, 'keep_sessions': 16, 'cone_search': True, 'cone_threshold': 3, 'transfer': True, 'uninterpreted': 'none', 'relevance': True, 'relations': 'default', 'cache_size': 200000, 'custom_cache_size': 200000, 'answers_size': 100000, 'splits_size': 20000})
items = [
    Ask(from_srepr("Or(AppliedBinaryRelation(Q.lt, Integer(1), Pow(Integer(2), Rational(1, 2))), AppliedBinaryRelation(Q.ne, E, Add(Symbol('w', nonzero=True), Mul(Pow(Mul(I, Symbol('w', nonzero=True)), Rational(1, 3)), Pow(Abs(Symbol('j', integer=True, even=True)), Rational(2, 3))))))"), from_srepr('True')),
    Ask(from_srepr("AppliedPredicate(Q.noninteger, Mul(Pow(Mul(I, Symbol('w', nonzero=True)), Rational(1, 3)), Pow(Abs(Symbol('j', integer=True, even=True)), Rational(2, 3))))"), from_srepr('true')),
]
rows, eng = execute(items, config, ref_level=ReferenceLevel.NONE, ref_for_last=True)
last = rows[-1]
print('engine after prefix:', last.warm, '  fresh engine:', last.ref)
assert last.warm == 'False' and last.ref == 'None', (last.warm, last.ref)
