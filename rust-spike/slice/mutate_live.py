"""mutate_live.py WORK REF: the 10 mutants of `mutate_slice.py` scored on the real engine: the plan's digest column.

REF holds Python's reference runs from `run_live.sh` (dev-py.jsonl, fuzz-py.jsonl). Builds in a scratch copy, then for
the unmutated build and each mutant:
  dev-ans, fuzz-ans       `live.py --check plain`: answers only, with `backend.install()`. This is the digest column.
  dev-state, fuzz-state   `live.py --check entry`: session state and call streams.
A cell is: caught (with the first query), no, or hang/crash when out of time or dead. Results are written as each check
ends: results.jsonl, table.md. The unmutated row must read "no" throughout.
"""
import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mutate_slice import M, build, sha  # noqa: E402

CHECKS = {"dev-ans": ("dev", "plain"), "fuzz-ans": ("fuzz", "plain"), "dev-state": ("dev", "entry"),
          "fuzz-state": ("fuzz", "entry")}
LOCK = threading.Lock()


def read(path):
    rows, total = {}, None
    for line in open(path):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if "total" in r:
            total = r["total"]
        else:
            rows[r["q"]] = r
    return rows, total


def compare(ref, got, state):
    """Every query that differs, by kind, and the first of each. Checked over the queries the mutant finished."""
    n = dict(answers=0, end=0, stream=0, count=0)
    first = {}
    for q in sorted(got):
        x, y = ref[q], got[q]
        if x["ans"] != y["ans"]:
            n["answers"] += 1
            first.setdefault("answers", (q, x["ans"], y["ans"]))
        if not state:
            continue
        sx, sy = x["sessions"], y["sessions"]
        if len(sx) != len(sy):
            n["count"] += 1
            first.setdefault("count", q)
        for u, v in zip(sx, sy):
            n["end"] += u["end"] != v["end"]
            n["stream"] += u["stream"] != v["stream"]
            if u["end"] != v["end"]:
                first.setdefault("end", q)
            if u["stream"] != v["stream"]:
                first.setdefault("stream", q)
    return n, first


def score(k, so, check, a):
    wl, level = CHECKS[check]
    out = os.path.join(a.work, "logs", f"m{k}-{check}.jsonl")
    cmd = [sys.executable, os.path.join(HERE, "live.py"), wl, "rust", out, "--check", level, "--so", so]
    with open(out + ".err", "w") as err:
        try:
            rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=err, timeout=a.timeout).returncode
        except subprocess.TimeoutExpired:
            rc = None
    got, total = read(out)
    ref, rtot = read(os.path.join(a.ref, f"{wl}-py.jsonl"))
    n, first = compare(ref, got, level != "plain")
    r = dict(rc=rc, done=len(got), of=len(ref), n=n, first=first)
    if total:
        if total["so_sha"] != sha(os.path.join(so, "sa_solver.so")):
            sys.exit(f"VOID: m{k} {check} loaded the wrong build")
        r["searches"] = total["searches"]
    if any(n.values()):
        r["outcome"] = "caught"
    elif total is None:
        r["outcome"] = "hang" if rc is None else "crash"
    else:
        r["outcome"] = "no"
    return r


def cell(r):
    if r is None:
        return "..."
    o = r["outcome"]
    if o == "no":
        return "no"
    if o != "caught":
        return f"{o}, {r['done']} of {r['of']} queries"
    n = r["n"]
    bits = []
    if n["answers"]:
        bits.append(f"{n['answers']} answers, first q{r['first']['answers'][0]}")
    if n["count"]:
        bits.append(f"{n['count']} session counts")
    if n["stream"]:
        bits.append(f"{n['stream']} streams, first q{r['first']['stream']}")
    if n["end"]:
        bits.append(f"{n['end']} end states")
    tail = "" if r["done"] == r["of"] else f" ({r['rc'] if r['rc'] is not None else 'out of time'} at {r['done']} of {r['of']})"
    return "caught: " + "; ".join(bits) + tail


def write(a, rows):
    with open(os.path.join(a.work, "table.md.tmp"), "w") as f:
        f.write("| # | mutant | missed by replays | dev answers | fuzz answers | dev state | fuzz state |\n|---|---|---|---|---|---|---|\n")
        for i in rows:
            name, missed = ("unmutated", "") if i == "base" else (M[i][1], "yes" if M[i][4] else "")
            f.write(f"| {i} | {name} | {missed} | " + " | ".join(cell(rows[i].get(c)) for c in CHECKS) + " |\n")
    os.replace(os.path.join(a.work, "table.md.tmp"), os.path.join(a.work, "table.md"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("work")
    p.add_argument("ref")
    p.add_argument("--jobs", type=int, default=5)
    p.add_argument("--timeout", type=float, default=1800)
    p.add_argument("--only")
    p.add_argument("--checks", default=",".join(CHECKS))
    a = p.parse_args()
    a.work, a.ref = os.path.abspath(a.work), os.path.abspath(a.ref)
    import shutil
    crate = os.path.join(a.work, "crate")
    os.makedirs(os.path.join(a.work, "logs"), exist_ok=True)
    if os.path.exists(crate):
        shutil.rmtree(os.path.join(crate, "src"))
    shutil.copytree(os.path.join(HERE, "solver_rs"), crate, dirs_exist_ok=True, ignore=shutil.ignore_patterns("target"))
    only = set(map(int, a.only.split(","))) if a.only else set(range(len(M)))
    sos = {"base": build(crate, os.path.join(a.work, "base"))}
    for i, (f, name, x, y, _) in enumerate(M):
        if i not in only:
            continue
        path = os.path.join(crate, "src", f)
        src = open(path).read()
        if src.count(x) != 1:
            sys.exit(f"NOMATCH {name}: {src.count(x)} matches")
        open(path, "w").write(src.replace(x, y))
        try:
            sos[i] = build(crate, os.path.join(a.work, f"m{i}"))
        finally:
            open(path, "w").write(src)
    shas = {k: sha(os.path.join(d, "sa_solver.so")) for k, d in sos.items()}
    if len(set(shas.values())) != len(shas):
        sys.exit(f"VOID: two builds are the same file: {shas}")
    rows = {k: {} for k in sos}
    write(a, rows)
    checks = a.checks.split(",")

    def job(k, c):
        r = score(k, sos[k], c, a)
        with LOCK:
            rows[k][c] = r
            with open(os.path.join(a.work, "results.jsonl"), "a") as f:
                f.write(json.dumps(dict(mutant=k, check=c, **r)) + "\n")
            write(a, rows)
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for fu in cf.as_completed([ex.submit(job, k, c) for k in sos for c in checks]):
            fu.result()
    print(open(os.path.join(a.work, "table.md")).read())


if __name__ == "__main__":
    main()
