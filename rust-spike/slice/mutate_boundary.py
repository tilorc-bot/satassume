"""mutate_boundary.py BUILDS WORK [--only I,J] [--jobs J] [--seeds N] [--suite FILE...]: two more checks for the builds
`mutate_slice.py` made in BUILDS (base and mK/sa_solver.so).
  nested  boundary.py: overlapping sessions, compared with Python.
  suite   the test files given, on that build, against the same files on base: caught if a test that passes on base
          fails on the mutant. `rust_plugin.py` makes the solver; each mutant runs one worker.
Results as each ends: WORK/results.jsonl, WORK/table.md. The base row must read "no"."""
import argparse
import concurrent.futures as cf
import glob
import json
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mutate_slice import M, sha  # noqa: E402

LOCK = threading.Lock()
ROOT = os.path.dirname(os.path.dirname(HERE))


def nested(k, so, a):
    log = os.path.join(a.work, f"m{k}-nested.out")
    with open(log, "w") as o, open(log + ".err", "w") as e:
        try:
            rc = subprocess.run([sys.executable, os.path.join(HERE, "boundary.py"), "--so", so, "--seeds", str(a.seeds)],
                                stdout=o, stderr=e, timeout=a.timeout).returncode
        except subprocess.TimeoutExpired:
            return dict(outcome="hang")
    lines = open(log).read().strip().splitlines()
    j = json.loads(lines[-1]) if lines and lines[-1].startswith("{") else None
    if j is None:
        return dict(outcome="crash", rc=rc)
    if j["so_sha"] != sha(os.path.join(so, "sa_solver.so")):
        sys.exit(f"VOID: m{k} loaded {j['so']}")
    if j["caught"]:
        return dict(outcome="caught", what=j["what"], session=j["session"], event=j["event"])
    return dict(outcome="no", reach=j["reach"])


def rows_of(d):
    out = {}
    for f in glob.glob(os.path.join(d, "rows.*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            out[r["id"]] = r
    return out


def suite(k, so, a, base_rows):
    d = os.path.join(a.work, f"m{k}-suite")
    os.makedirs(d, exist_ok=True)
    for f in glob.glob(os.path.join(d, "rows.*.jsonl")):
        os.remove(f)
    env = dict(os.environ, SLICE_SUITE_OUT=d, SLICE_SUITE_BACKEND="rust", SLICE_SO=so, HYPOTHESIS_STORAGE_DIRECTORY=os.path.join(d, "hyp"),
               PYTHONPATH=os.environ["PYTHONPATH"] + ":" + HERE)
    cmd = [sys.executable, "-m", "pytest", "-p", "rust_plugin", "-q", "--tb=line", "-p", "no:cacheprovider", *a.suite]
    with open(os.path.join(d, "pytest.log"), "w") as o:
        try:
            rc = subprocess.run(cmd, stdout=o, stderr=subprocess.STDOUT, cwd=ROOT, env=env, timeout=a.suite_timeout).returncode
        except subprocess.TimeoutExpired:
            rc = None
    rs = rows_of(d)
    if base_rows is None:
        ok = sum(r["outcome"] == "passed" for r in rs.values())
        return dict(outcome="no" if rc in (0, 1) else "void", passed=ok, tests=len(rs), rc=rc), rs
    broke = sorted(i for i, r in base_rows.items() if r["outcome"] == "passed" and rs.get(i, {}).get("outcome", "absent") not in ("passed", "absent"))
    out = dict(rc=rc, tests=len(rs), broke=len(broke), first=broke[:3])
    out["outcome"] = "caught" if broke else ("no" if rc is not None and len(rs) >= len(base_rows) else ("hang" if rc is None else "crash"))
    return out, rs


def cell(r):
    if r is None:
        return "..."
    if r["outcome"] == "caught":
        if "broke" in r:
            return f"caught: {r['broke']} tests, e.g. `{r['first'][0].split('::')[-1][:40]}`"
        return f"caught: {r['what']}, seed {r['session']}"
    return r["outcome"]


def write(a, rows):
    with open(os.path.join(a.work, "table.md.tmp"), "w") as f:
        f.write("| # | mutant | nested | suite |\n|---|---|---|---|\n")
        for k in rows:
            name = "unmutated" if k == "base" else M[k][1]
            f.write(f"| {k} | {name} | {cell(rows[k].get('nested'))} | {cell(rows[k].get('suite'))} |\n")
    os.replace(os.path.join(a.work, "table.md.tmp"), os.path.join(a.work, "table.md"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("builds")
    p.add_argument("work")
    p.add_argument("--only")
    p.add_argument("--jobs", type=int, default=3)
    p.add_argument("--seeds", type=int, default=500)
    p.add_argument("--timeout", type=float, default=600)
    p.add_argument("--suite-timeout", type=float, default=900)
    p.add_argument("--suite", nargs="*", default=[])
    a = p.parse_args()
    a.work, a.builds = os.path.abspath(a.work), os.path.abspath(a.builds)
    os.makedirs(a.work, exist_ok=True)
    ids = sorted(map(int, a.only.split(","))) if a.only else [i for i in range(len(M)) if os.path.isdir(f"{a.builds}/m{i}")]
    sos = {"base": os.path.join(a.builds, "base"), **{i: os.path.join(a.builds, f"m{i}") for i in ids}}
    rows = {k: {} for k in sos}
    base_rows = None
    if a.suite:
        rows["base"]["suite"], base_rows = suite("base", sos["base"], a, None)
        base_rows = {i: r for i, r in base_rows.items() if r["outcome"] == "passed"}
    write(a, rows)

    def job(k, c):
        r = nested(k, sos[k], a) if c == "nested" else suite(k, sos[k], a, base_rows)[0]
        with LOCK:
            rows[k][c] = r
            with open(os.path.join(a.work, "results.jsonl"), "a") as f:
                f.write(json.dumps(dict(mutant=k, check=c, **r)) + "\n")
            write(a, rows)
    work = [(k, "nested") for k in sos]
    if a.suite:
        work += [(k, "suite") for k in ids]
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for fu in cf.as_completed([ex.submit(job, k, c) for k, c in work]):
            fu.result()
    print(open(os.path.join(a.work, "table.md")).read())


if __name__ == "__main__":
    main()
