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
    Ask(from_srepr("AppliedBinaryRelation(Q.eq, Symbol('u'), Symbol('y', real=True))"), from_srepr("And(AppliedPredicate(Q.zero, Symbol('u')), AppliedPredicate(Q.positive, Add(Integer(1), Function('f')(Integer(0)))))")),
    Ask(from_srepr("AppliedPredicate(Q.positive, Add(Integer(1), Function('f')(Symbol('u'))))"), from_srepr("And(AppliedPredicate(Q.zero, Symbol('u')), AppliedPredicate(Q.positive, Add(Integer(1), Function('f')(Integer(0)))))")),
]
rows, eng = execute(items, config, ref_level=ReferenceLevel.NONE, ref_for_last=True)
last = rows[-1]
print('engine after prefix:', last.warm, '  fresh engine:', last.ref)
assert last.warm == 'True' and last.ref == 'None', (last.warm, last.ref)
