"""cv_seen (sa-port-359): at session end, write this worker's walker counters (sa_solver.walk_counts(), 740-746), which
walker `convert` had and the .so loaded, so a 'SLICE_CONVERT=rust' suite or iv row is shown to have run walk.rs's entry
(and a row without it, not to have)."""
import json, os, sys
def pytest_sessionfinish(session, exitstatus):
    c = sys.modules.get('convert'); so = sys.modules.get('sa_solver')
    out = os.environ.get('SLICE_SUITE_OUT')
    if out:
        w = None if c is None else c.WALK[0]
        with open(os.path.join(out, f'cv.{os.getpid()}.json'), 'w') as h:
            json.dump(dict(counts=so.walk_counts() if so is not None and hasattr(so, 'walk_counts') else None,
                           walk='no-convert' if c is None else ('py' if w is None else ','.join(w.ITEMS)),
                           env=os.environ.get('SLICE_CONVERT'), so=getattr(so, '__file__', None)), h)
