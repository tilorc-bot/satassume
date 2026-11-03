"""The gates: run on every candidate (on orion; no timing here).

    python -m evalbench.gates CHECKOUT --out DIR [--baseline DIR] [--jobs 6] [--skip-tests]
    python -m evalbench.gates BASELINE_CHECKOUT --out baseline-answers/<sha> --record

1. Answers identical to the baseline's, position by position, on the full
   stream, the battery stream and the corpus (recorded order, one process
   each; a raise is an answer: "ValueError", "raise <Type>"), on the
   held-out fuzz, and on the fork-per-case battery slice (refine's output).
2. History independence (satassume issue 97): the unique stream replayed in
   a fixed shuffled order, and every unique stream query in a fresh process
   (``evalbench.forkq``), give the baseline's answers.
3. satassume's test suite: the candidate's own suite, and the BASELINE's
   tests run against the candidate's package, pass as on the baseline
   (same failures, by node id).

``--record`` stores the answers and test outcomes a candidate is compared
with.  Writes DIR/gates.json (and the answer files); prints a summary.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from evalbench.common import SYMPY, env_for, shim, workload
from evalbench.run import replay

INPROC = ["stream", "battery", "corpus", "stream-unique", "stream-shuffled", "ho-fuzz", "fork-battery"]
BASE_SHA = "9bafaa5"


def read(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def forkq(checkout, out, jobs):
    procs, parts = [], []
    for i in range(jobs):
        part = f"{out}.{i}"
        parts.append(part)
        procs.append(subprocess.Popen([sys.executable, "-m", "evalbench.forkq", "stream-unique",
                                       "--shard", f"{i}/{jobs}", "--out", part],
                                      env=env_for(checkout), cwd=shim(), stderr=subprocess.PIPE, text=True))
    for p in procs:
        _, err = p.communicate()
        if p.returncode:
            raise RuntimeError("forkq failed: " + err[-2000:])
    ans = {}
    for part in parts:
        with open(part) as f:
            for line in f:
                i, a = line.rstrip("\n").split("\t", 1)
                ans[int(i)] = json.loads(a)
        os.remove(part)
    res = [ans[i] for i in range(len(ans))]
    with open(out, "w") as f:
        for r in res:
            f.write(json.dumps(r) + "\n")
    return res


def pytest_outcomes(rootdir, jobs, junit):
    env = dict(os.environ, PYTHONPATH=SYMPY, PYTHONHASHSEED="0")
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-n", str(jobs),
           "--junitxml", junit, "tests"]
    p = subprocess.run(cmd, cwd=rootdir, env=env, capture_output=True, text=True)
    out = {}
    for tc in ET.parse(junit).getroot().iter("testcase"):
        nid = tc.get("classname", "") + "::" + tc.get("name", "")
        kind = "passed"
        for child in tc:
            if child.tag in ("failure", "error"):
                kind = "failed"
            elif child.tag == "skipped":
                kind = "xfail" if "xfail" in (child.get("type", "") + child.get("message", "")) else "skipped"
        out[nid] = kind
    tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-300:]
    return out, tail


def baseline_tests_on(checkout, base_checkout, tmp):
    """The baseline's tree (git archive of BASE_SHA) with the candidate's package."""
    d = os.path.join(tmp, "basetests")
    os.makedirs(d)
    a = subprocess.run(["git", "-C", base_checkout, "archive", BASE_SHA], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", d], input=a.stdout, check=True)
    shutil.rmtree(os.path.join(d, "satassume"))
    shutil.copytree(os.path.join(checkout, "satassume"), os.path.join(d, "satassume"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    return d


def compare(name, cand, base, pairs=None):
    diffs = []
    if len(cand) != len(base):
        return {"name": name, "ok": False, "error": f"length {len(cand)} vs {len(base)}", "diffs": []}
    for i, (c, b) in enumerate(zip(cand, base)):
        if c != b:
            d = {"i": i, "base": b, "cand": c}
            if pairs is not None:
                d["q"] = str(pairs[i][0]) + "  |  " + str(pairs[i][1])
            diffs.append(d)
    return {"name": name, "ok": not diffs, "n": len(cand), "n_diff": len(diffs), "diffs": diffs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("checkout")
    ap.add_argument("--out", required=True)
    ap.add_argument("--baseline", default=os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "baseline-answers", BASE_SHA))
    ap.add_argument("--base-checkout", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--skip-tests", action="store_true")
    args = ap.parse_args()
    co = os.path.abspath(args.checkout)
    args.out = os.path.abspath(args.out)
    args.baseline = os.path.abspath(args.baseline)
    os.makedirs(args.out, exist_ok=True)
    A = lambda w: os.path.join(args.out, f"answers-{w}.jsonl")  # noqa: E731
    B = lambda w: os.path.join(args.baseline, f"answers-{w}.jsonl")  # noqa: E731
    runs = {}
    for w in INPROC:
        runs[w] = replay(co, w, answers=A(w))
        print(w, json.dumps({k: runs[w].get(k) for k in ("n", "cases", "digest")}), flush=True)
    forkq(co, A("forkq"), args.jobs)
    print("forkq done", flush=True)
    res = {"checkout": co, "runs": runs, "checks": []}
    if not args.skip_tests:
        tmp = tempfile.mkdtemp(prefix="sa-eval-tests-")
        own, own_tail = pytest_outcomes(co, args.jobs, os.path.join(tmp, "own.xml"))
        res["tests_own"] = {"summary": own_tail, "outcomes": own}
        print("own tests:", own_tail, flush=True)
        if not args.record:
            d = baseline_tests_on(co, args.base_checkout, tmp)
            bt, bt_tail = pytest_outcomes(d, args.jobs, os.path.join(tmp, "base.xml"))
            res["tests_base_on_cand"] = {"summary": bt_tail, "outcomes": bt}
            print("baseline tests on candidate:", bt_tail, flush=True)
        shutil.rmtree(tmp, ignore_errors=True)
    if args.record:
        with open(os.path.join(args.out, "gates.json"), "w") as f:
            json.dump(res, f)
        return
    # 1. answers by position
    for w in ["stream", "battery", "corpus", "ho-fuzz", "fork-battery"]:
        pairs = None if w == "fork-battery" else workload(w)
        res["checks"].append(compare(w, read(A(w)), read(B(w)), pairs))
    # 2. history independence
    uq = workload("stream-unique")
    base_u = read(B("stream-unique"))
    res["checks"].append(compare("stream-unique", read(A("stream-unique")), base_u, uq))
    sh = workload("stream-shuffled")
    idx = {q: i for i, q in enumerate(uq)}
    base_sh = [base_u[idx[q]] for q in sh]
    res["checks"].append(compare("stream-shuffled", read(A("stream-shuffled")), base_sh, sh))
    res["checks"].append(compare("forkq (fresh process per query)", read(A("forkq")), read(B("forkq")), uq))
    # 3. tests
    with open(os.path.join(args.baseline, "gates.json")) as f:
        base = json.load(f)
    bo = base["tests_own"]["outcomes"]
    if not args.skip_tests:
        for key in ("tests_own", "tests_base_on_cand"):
            oc = res[key]["outcomes"]
            worse = sorted(n for n, k in oc.items() if k == "failed" and bo.get(n) != "failed")
            gone = sorted(n for n in bo if bo[n] == "passed" and n not in oc) if key == "tests_base_on_cand" else []
            res["checks"].append({"name": key, "ok": not worse and not gone, "summary": res[key]["summary"],
                                  "newly_failing": worse, "missing": gone})
    res["pass"] = all(c["ok"] for c in res["checks"])
    with open(os.path.join(args.out, "gates.json"), "w") as f:
        json.dump(res, f)
    for c in res["checks"]:
        extra = c.get("n_diff", len(c.get("newly_failing", [])))
        print(f"{'PASS' if c['ok'] else 'FAIL'}  {c['name']}  {extra if not c['ok'] else ''}")
    print("GATES", "PASS" if res["pass"] else "FAIL")


if __name__ == "__main__":
    main()
