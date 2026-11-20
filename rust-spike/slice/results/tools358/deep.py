"""deep.py LEVELS [plain|handlers|count]: Python's walker (WALK[0] None) on a formula LEVELS connectives deep, with
handler_count installed as in a suite run (handlers), with a counting EXCEPTION_HANDLED callback (count), or with no
monitoring (plain). Prints seconds, the outcome and how often the callback ran."""
import sys, time, os, tempfile
levels, mode = int(sys.argv[1]), sys.argv[2]
from sympy import And, Or, Q, symbols
import convert
from satassume import engine as E
x, y, z = symbols('x y z')
e = Q.positive(x)
for _ in range(levels // 2):
    e = Or(And(e, Q.positive(y), evaluate=False), Q.real(z), evaluate=False)
n = [0]
if mode == 'handlers':
    import handler_count
    handler_count.install(os.path.join(tempfile.mkdtemp(), 'h.jsonl'))
    real = handler_count._fired
    def fired(code, offset, exc):
        n[0] += 1
        return real(code, offset, exc)
    sys.monitoring.register_callback(handler_count.TOOL, sys.monitoring.events.EXCEPTION_HANDLED, fired)
elif mode == 'count':
    mon = sys.monitoring
    mon.use_tool_id(4, 'deep')
    def fired(code, offset, exc):
        n[0] += 1
    mon.register_callback(4, mon.events.EXCEPTION_HANDLED, fired)
    mon.set_events(4, mon.events.EXCEPTION_HANDLED)
eng = E.Engine()
convert.WALK[0] = None
t = time.time()
c = convert.convert(e, Q.positive(x), eng)
print(levels, mode, round(time.time() - t, 3), type(c).__name__, getattr(c, 'reason', None), 'callbacks', n[0], flush=True)
