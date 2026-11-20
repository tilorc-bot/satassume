"""deep2.py LEVELS STOP: as deep.py's count mode, but the callback tallies (where handled, exception type) and the run
stops after STOP callbacks, printing the tally and how often convert.formula was entered."""
import sys, os, collections
levels, stop = int(sys.argv[1]), int(sys.argv[2])
from sympy import And, Or, Q, symbols
import convert
from satassume import engine as E
x, y, z = symbols('x y z')
e = Q.positive(x)
for _ in range(levels // 2):
    e = Or(And(e, Q.positive(y), evaluate=False), Q.real(z), evaluate=False)
tally = collections.Counter()
n = [0]
mon = sys.monitoring
mon.use_tool_id(4, 'deep')
def fired(code, offset, exc):
    n[0] += 1
    tally[(code.co_filename.rsplit('/', 2)[-1], code.co_qualname, type(exc).__name__)] += 1
    if n[0] >= stop:
        for k, v in tally.most_common(12):
            print(v, *k)
        print('formula entered', entered[0], flush=True)
        os._exit(0)
entered = [0]
def started(code, offset):
    if code is convert.formula.__code__:
        entered[0] += 1
    else:
        return mon.DISABLE
mon.register_callback(4, mon.events.EXCEPTION_HANDLED, fired)
mon.register_callback(4, mon.events.PY_START, started)
eng = E.Engine()
convert.WALK[0] = None
mon.set_events(4, mon.events.EXCEPTION_HANDLED | mon.events.PY_START)
c = convert.convert(e, Q.positive(x), eng)
print('ended', type(c).__name__, getattr(c, 'reason', None), 'callbacks', n[0], 'formula entered', entered[0])
for k, v in tally.most_common(12):
    print(v, *k)
