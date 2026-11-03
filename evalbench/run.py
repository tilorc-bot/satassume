"""Run evalbench.replay for a checkout in a fresh process; returns its JSON."""
import json
import os
import subprocess
import sys

from evalbench.common import env_for, shim


def replay(checkout, workload, *flags, python=sys.executable, answers=None):
    """One cold process replaying ``workload`` (``fork-battery``: the
    fork-per-case battery slice) against ``checkout``."""
    if workload == "fork-battery":
        cmd, sat = [python, "-m", "evalbench.cold_battery", *flags], True
        if answers:
            cmd += ["--out", os.path.abspath(answers)]
    else:
        cmd, sat = [python, "-m", "evalbench.replay", workload, *flags], False
        if answers:
            cmd += ["--answers", os.path.abspath(answers)]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env_for(checkout, sat), cwd=shim())
    if p.returncode:
        raise RuntimeError(f"{cmd} in {checkout} failed:\n{p.stderr[-3000:]}")
    res = json.loads(p.stdout.strip().splitlines()[-1])
    if "satassume" in res and not os.path.realpath(res["satassume"]).startswith(os.path.realpath(checkout)):
        raise RuntimeError(f"imported satassume from {res['satassume']}, not {checkout}")
    return res
