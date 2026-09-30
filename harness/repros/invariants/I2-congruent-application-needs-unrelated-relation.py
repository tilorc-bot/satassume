# Replays an invariant violation of satassume.sympy_api.ask (harness/INVARIANTS.md).
# Run from anywhere inside a satassume checkout:  PYTHONHASHSEED=0 python this_file.py
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(_d, 'harness', '__init__.py')):
    if os.path.dirname(_d) == _d:
        _d = os.getcwd()
        break
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from harness.invariants import replay
sev, base, other = replay(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'I2-congruent-application-needs-unrelated-relation.json'))
print('invariant I2: base', base, '  variant', other, '  severity', sev)
assert sev is not None, (base, other)
