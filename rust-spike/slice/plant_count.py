"""`-p plant_count` in a suite run with SLICE_SUITE_OUT set: each process (each xdist worker) writes counts.PID.json there at
the end, the crate's session counters (`rel:plant_fired` among them), so a suite plant run says whether the plant fired at
all. A plant that fired 0 makes that run's "no change" void. bar_sum.py sums the files."""
import json
import os


def pytest_sessionfinish(session, exitstatus):
    d = os.environ.get('SLICE_SUITE_OUT')
    if not d:
        return
    try:
        import sa_solver
        c = dict(sa_solver.session_counts())
    except Exception as e:  # report it, don't hide it: the summary shows `error`
        c = {'error': repr(e)}
    with open(os.path.join(d, f'counts.{os.getpid()}.json'), 'w') as f:
        json.dump(c, f, sort_keys=True)
