"""suite_report.py RUST PYTHON [--kept KEPT]: the planner's three numbers from run_suite.sh's rows.

A failure on Rust is "needs internals" only if the text of the failure itself names one of:
  - NotImplementedError from the crate's provenance stubs ("the Rust solver has no provenance")
  - AttributeError on the Rust solver class, for an attribute that real `Solver` has and the crate doesn't
Anything else is a gate failure, including the borrow RuntimeError. A test the planner would class under "subclassing
Solver" still has to fail with one of those two: subclassing works on the crate's class, so it isn't a reason by itself.

A file outside HANDOFF_FILES with a "needs internals" failure is flagged, not accepted: that list is the check that a
real bug can't hide as a missing attribute. RUST and PYTHON are WORK directories; KEPT is the Python re-run of the kept
tests, whose rows have to pass. Prints markdown; writes classes.json to RUST.
"""
import argparse
import collections
import glob
import json
import os
import re

HANDOFF_FILES = {"test_lra_integers", "test_solver_incremental", "test_solver", "theory_harness", "test_transfer"}
ATTR = re.compile(r"AttributeError: (?:type object )?'?(\w+)'? (?:object )?has no attribute '(\w+)'")
BORROW = "Already mutably borrowed", "Already borrowed"
SOLVER_TYPES = {"Solver", "_CountingSolver", "BlockSolver", "MentionSolver"}


def rows(work):
    out = {}
    for f in glob.glob(os.path.join(work, "rows.*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            out[r["id"]] = r
    return out


def file_of(nodeid):
    return os.path.basename(nodeid.split("::")[0]).removesuffix(".py")


def classify(r, py_attrs):
    """(class, detail) of a failed row."""
    f = r["failure"] or {}
    text = (f.get("crash") or "") + "\n" + (f.get("text") or "")
    if "the Rust solver has no provenance" in text:
        return "internals", "provenance"
    if any(b in text for b in BORROW):
        return "reentry", (f.get("where") or "?")
    m = ATTR.search(text)
    if m and m.group(1) in SOLVER_TYPES:
        name = m.group(2)
        if name in py_attrs:
            return "internals", name
        return "gate", f"AttributeError on {name}, which Python's Solver doesn't have either"
    return "gate", (f.get("crash") or "")[:200]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("rust")
    p.add_argument("python")
    p.add_argument("--kept")
    a = p.parse_args()
    from satassume.sat.solver import Solver as PySolver
    py_attrs = set(dir(PySolver)) | set(vars(PySolver()))
    rs, ps = rows(a.rust), rows(a.python)
    groups = collections.defaultdict(list)
    for i, r in sorted(rs.items()):
        groups[r["outcome"]].append(i)
    classes = dict(internals=[], reentry=[], gate=[])
    for i in groups["failed"] + groups["collect-error"]:
        c, d = classify(rs[i], py_attrs)
        classes[c].append((i, d, ps.get(i, {}).get("outcome", "absent")))
    json.dump(classes, open(os.path.join(a.rust, "classes.json"), "w"), indent=1)

    passed = groups["passed"]
    touching = [i for i in passed if rs[i]["rust_made"]]
    print(f"Rust run: {len(rs)} tests; Python run: {len(ps)} tests.\n")
    print("| | tests |\n|---|---:|")
    print(f"| Ran on Rust and passed | {len(passed)} |")
    print(f"| of those, made a Rust solver inside the test | {len(touching)} |")
    print(f"| of those, none made inside the test (no solver, or a fixture shared across tests) | {len(passed) - len(touching)} |")
    print(f"| Kept on Python, needs internals | {len(classes['internals'])} |")
    print(f"| Failed on Rust: re-entry | {len(classes['reentry'])} |")
    print(f"| Failed on Rust: other | {len(classes['gate'])} |")
    for k in ("skipped", "xfailed", "xpassed"):
        print(f"| Rust {k} | {len(groups[k])} |")
    print()

    py_counts = collections.Counter(r["outcome"] for r in ps.values())
    print("Python baseline:", dict(py_counts), "\n")
    print("Tests whose outcome differs between the backends, other than a Rust failure counted above:")
    for i in sorted(set(rs) & set(ps)):
        if rs[i]["outcome"] != ps[i]["outcome"] and rs[i]["outcome"] not in ("failed", "collect-error"):
            print(f"- `{i}`: Python {ps[i]['outcome']}, Rust {rs[i]['outcome']}")
    print("Only in one run:", sorted(set(rs) ^ set(ps))[:20], "\n")

    print("### Needs internals, by file and reason")
    by = collections.Counter((file_of(i), d) for i, d, _ in classes["internals"])
    for (f, d), n in sorted(by.items()):
        flag = "" if f in HANDOFF_FILES else "  **NOT in the handoff's list**"
        print(f"- `{f}`: `{d}`: {n}{flag}")
    print(f"\nHandoff files with none: {sorted(HANDOFF_FILES - {f for f, _ in by})}\n")

    print("### Re-entry, by where it raised")
    for w, n in collections.Counter(d for _, d, _ in classes["reentry"]).most_common():
        print(f"- `{w}`: {n}")
    print("\n### Other failures")
    for i, d, po in classes["gate"]:
        print(f"- `{i}` (Python: {po}): {d}")

    print("\n### Passed after writing a private attribute the crate doesn't have (the write did nothing)")
    w = collections.defaultdict(list)
    for i in passed:
        for n in rs[i]["private_writes"]:
            w[n].append(i)
    for n, ids in sorted(w.items()):
        print(f"- `{n}`: {len(ids)}, e.g. `{ids[0]}`")
    if a.kept:
        ks = rows(a.kept)
        want = {i for i, _, _ in classes["internals"]}
        res = collections.Counter(ks[i]["outcome"] if i in ks else "absent" for i in want)
        print(f"\n### Kept tests re-run on Python: {dict(res)}")
        for i in sorted(want):
            if i not in ks or ks[i]["outcome"] not in ("passed", "skipped", "xfailed"):
                print(f"- `{i}`: {ks.get(i, {}).get('outcome', 'absent')}")


if __name__ == "__main__":
    main()
