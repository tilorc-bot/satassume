"""wn_seen (sa-port-352): at session end, write this worker's native witness counters (witness_live.counts(), 706-713) and
whether the hook is in place, so a 'SLICE_WITNESS_RUST=1' suite or iv row is shown to have run witness.rs (and a row
without it, not to have)."""
import json, os, sys
def pytest_sessionfinish(session, exitstatus):
    wl = sys.modules.get('witness_live'); w = sys.modules.get('satassume.witness'); so = sys.modules.get('sa_solver')
    out = os.environ.get('SLICE_SUITE_OUT')
    if out:
        with open(os.path.join(out, f'wn.{os.getpid()}.json'), 'w') as h:
            json.dump(dict(counts=wl.counts() if wl and hasattr(so, 'witness_counts') else None, hook=bool(w and getattr(w, 'NATIVE', [None])[0]), enabled=bool(w and w.ENABLED[0]),
                           env=os.environ.get('SLICE_WITNESS_RUST'), so=getattr(so, '__file__', None)), h)
