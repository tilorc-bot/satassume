"""rtf_column.py BUILDS OUT PYDIR --only I,J: each mutant through tests/real_theory_fuzz.py's seeds (`rtf_compare.py`).
PYDIR holds py-euf.txt and py-both.txt. Two scores per mode: the test's own check (Rust incremental against Rust fresh,
which is all the test sees) and the answers against Python's dump. `lost_levels` is a raise or mismatch naming the level check.
"""
import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.argv, args = [sys.argv[0], "/nonexistent"], sys.argv[1:]
from mutate_slice import M  # noqa: E402
p = argparse.ArgumentParser()
p.add_argument("builds")
p.add_argument("out")
p.add_argument("pydir")
p.add_argument("--only")
p.add_argument("--seeds", type=int, default=150)
p.add_argument("--jobs", type=int, default=6)
p.add_argument("--timeout", type=float, default=1200)
a = p.parse_args(args)
os.makedirs(a.out, exist_ok=True)
ids = ["base"] + [int(x) for x in a.only.split(",")]


def one(k, mode):
    so = os.path.join(a.builds, "base" if k == "base" else f"m{k}")
    txt = os.path.join(a.out, f"m{k}-{mode}.txt")
    env = dict(os.environ, SLICE_SO=so)
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "rtf_compare.py"), "rust", mode, str(a.seeds), txt], env=env,
                           capture_output=True, text=True, timeout=a.timeout)
    except subprocess.TimeoutExpired:
        return dict(mutant=k, mode=mode, outcome="hang")
    if r.returncode or not r.stdout.strip():
        return dict(mutant=k, mode=mode, outcome="crash", rc=r.returncode, err=r.stderr[-300:])
    j = json.loads(r.stdout.strip().splitlines()[-1])
    got = open(txt).read().splitlines()
    ref = open(os.path.join(a.pydir, f"py-{mode}.txt")).read().splitlines()
    return dict(mutant=k, mode=mode, outcome="ran", self_mismatch=j["n_mismatch"], raised=j["n_raised"],
                first_mismatch=j["mismatches"][:1], first_raised=j["raised"][:1], answers=len(got), of=len(ref),
                differ=sum(x != y for x, y in zip(got, ref)) + abs(len(got) - len(ref)), level_reads=j["level_reads"])


with cf.ThreadPoolExecutor(a.jobs) as ex, open(os.path.join(a.out, "results.jsonl"), "w") as f:
    for fu in cf.as_completed([ex.submit(one, k, m) for k in ids for m in ("euf", "both")]):
        f.write(json.dumps(fu.result()) + "\n")
        f.flush()
print("done", len(ids))
