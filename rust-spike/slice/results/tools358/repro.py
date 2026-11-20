"""repro.py WIDTH LIMIT: no satassume, no SymPy. f recurses through a generator expression WIDTH wide, as convert.formula
does; an EXCEPTION_HANDLED callback is registered. Counts callbacks and calls of f until RecursionError comes out."""
import sys, time
width, limit = int(sys.argv[1]), int(sys.argv[2])
sys.setrecursionlimit(limit)
calls, fired, failed = [0], [0], [0]
def cb(code, offset, exc):
    fired[0] += 1
mon = sys.monitoring
if len(sys.argv) > 3:
    mon.use_tool_id(4, 'repro'); mon.register_callback(4, mon.events.EXCEPTION_HANDLED, cb); mon.set_events(4, mon.events.EXCEPTION_HANDLED)
def f(n):
    calls[0] += 1
    return tuple(f(n + 1) for _ in range(width))
t = time.time()
try:
    f(0)
except RecursionError:
    pass
print(f'width {width} limit {limit} monitored {len(sys.argv) > 3}: calls of f {calls[0]}, callbacks {fired[0]}, {time.time() - t:.3f} s')
