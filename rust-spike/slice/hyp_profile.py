"""`-p hyp_profile --hypothesis-profile=bar`: the bar's hypothesis profile (planner [137e](b), issue 323).

Registers the profile `bar`: derandomize=True and database=None, nothing else, so every test keeps the max_examples,
deadline and health checks it sets itself. Under it each hypothesis test draws its examples from a seed derived from the
test function, the same in every run, so a suite row (and a suite plant's row) reproduces between bars.

Registering selects nothing. Only `--hypothesis-profile=bar` loads the profile, and only p1/bar.sh's suite invocations
pass it: a plain `pytest`, run_suite.sh and CI are unchanged. Hypothesis loads the profile in its pytest_configure, before
any test module is imported, so settings objects built at import (`FUZZ = settings(...)`) inherit it too.

In a suite run with SLICE_SUITE_OUT set, each process (each xdist worker) writes hyp.PID.json there at the end: the
profile in force with its derandomize and database, so a row directory says which exploration its run used.
"""
import json
import os

from hypothesis import settings

settings.register_profile('bar', derandomize=True, database=None)


def pytest_sessionfinish(session, exitstatus):
    d = os.environ.get('SLICE_SUITE_OUT')
    if not d:
        return
    s = settings()
    with open(os.path.join(d, f'hyp.{os.getpid()}.json'), 'w') as f:
        json.dump({'profile': settings.get_current_profile_name(), 'derandomize': s.derandomize,
                   'database': repr(s.database)}, f, sort_keys=True)
