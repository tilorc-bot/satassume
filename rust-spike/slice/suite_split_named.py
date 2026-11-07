"""suite_split_named.py RUST PYTHON [--list FILE]: the planner's two numbers for a suite run with `-p handler_count`.

Passed splits into: no handler firing on Rust that doesn't fire on Python for that test, and at least one that does.
A firing is (site, type, text). Total passed stays as run; nothing here moves a test by hand. A firing outside NAMED is
a finding. Both runs must have the counter installed; a directory with no handlers file is refused, since that's not a
zero. A firing Python shares counts as not Rust's, and is counted on its own line so the two numbers can be checked.
"""
import argparse
import collections
import glob
import json
import os
import sys

NAMED = {"tests/test_invariants.py::test_ci_stream_reports_only_what_replays"}  # the ruling's one needs-internals case


def rows(work):
    out = {}
    for f in glob.glob(os.path.join(work, "rows.*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            out[r["id"]] = r
    return out


def firings(work):
    files = glob.glob(os.path.join(work, "handlers.*.jsonl"))
    if not files:
        sys.exit(f"{work}: no handlers file, so the counter wasn't installed; that isn't a zero")
    out = collections.defaultdict(collections.Counter)
    for f in files:
        for line in open(f):
            r = json.loads(line)
            out[r["where"]][(r["site"], r["type"], r["text"])] += 1
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("rust")
    p.add_argument("python")
    p.add_argument("--list", help="write every second-group test here, with its firings")
    a = p.parse_args()
    rr, pr = rows(a.rust), rows(a.python)
    rf, pf = firings(a.rust), firings(a.python)
    count = collections.Counter(r["outcome"] for r in rr.values())
    print("rust outcomes", dict(count), "python outcomes", dict(collections.Counter(r["outcome"] for r in pr.values())))
    passed = [i for i, r in rr.items() if r["outcome"] == "passed"]
    second, shared, counts_differ = {}, [], []
    for i in passed:
        only = {k: n for k, n in rf.get(i, {}).items() if k not in pf.get(i, {})}
        if only:
            second[i] = only
        elif rf.get(i):
            shared.append(i)
            if rf[i] != pf.get(i):
                counts_differ.append(i)
    print(f"passed {len(passed)}: no Rust-only firing {len(passed) - len(second)}, Rust-only firing {len(second)}")
    print(f"  of the first number, firing the same on Python: {len(shared)}, with different counts: {len(counts_differ)}")
    findings = sorted(set(second) - NAMED)
    print(f"  second group named by the ruling: {len(set(second) & NAMED)}; findings: {len(findings)}")
    missing = sorted(NAMED - set(second))
    if missing:
        print(f"  named but not in the second group: {missing}")
    by = collections.Counter(k for v in second.values() for k in v)
    for k, n in by.most_common(12):
        print(f"  {n} tests' distinct firing: {k[0]} {k[1]}: {k[2][:90]}")
    other = {i: v for i, v in rf.items() if i not in passed}
    print(f"firings on Rust in tests that didn't pass, or outside a test: {len(other)}")
    pyonly = [i for i in passed if pf.get(i) and not rf.get(i)]
    print(f"passed with a firing only on Python: {len(pyonly)}")
    if a.list:
        with open(a.list, "w") as o:
            for i in sorted(second):
                tag = "named" if i in NAMED else "FINDING"
                for k, n in second[i].items():
                    o.write(json.dumps(dict(id=i, tag=tag, n=n, site=k[0], type=k[1], text=k[2])) + "\n")
            for i in counts_differ:
                o.write(json.dumps(dict(id=i, tag="counts differ", rust=sum(rf[i].values()),
                                        python=sum(pf[i].values()))) + "\n")
            for i, v in other.items():
                o.write(json.dumps(dict(id=i, tag="not passed", firings=[list(k) + [n] for k, n in v.items()])) + "\n")


if __name__ == "__main__":
    main()
