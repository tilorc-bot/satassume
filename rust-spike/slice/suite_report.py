"""suite_report.py RUST PYTHON: the planner's three numbers from run_suite.sh's rows.

A failure on Rust is "needs internals" only if the text of the failure itself names one of:
  - NotImplementedError from the crate's provenance stubs ("the Rust solver has no provenance")
  - AttributeError on the Rust solver class, for an attribute that real `Solver` has and the crate doesn't
  - a subclass's override of a private method that Rust never calls: only the node ids in SUBCLASS, each read by hand,
    and only if the failing line reads its counter
Anything else is a gate failure, including the borrow RuntimeError. Subclassing works on the crate's class, so it isn't a
reason by itself.

A "needs internals" failure raised in a file outside HANDOFF_FILES is flagged, not accepted: that list is the check that
a real bug can't hide as a missing attribute. The file is the one that raised, not the test's own: a test in test_euf
that fails inside theory_harness is theory_harness's. RUST and PYTHON are WORK directories. Prints markdown; writes
classes.json to RUST. A gate failure that fails the same way on Python is counted apart.
"""
import argparse
import collections
import glob
import json
import os
import re

HANDOFF_FILES = {"test_lra_integers", "test_solver_incremental", "test_solver", "theory_harness", "test_transfer"}
ATTR = re.compile(r"AttributeError: (?:type object )?[<']*(?:class ')?([\w.]+)'?>? (?:object )?has no attribute '(\w+)'")
FRAME = re.compile(r"^((?:tests|harness)/[\w./]+\.py):(\d+): in ", re.M)
SUBCLASS = {
    # _CountingSolver overrides _rb_reason to count; the crate calls its own, so the count stays 0.
    "tests/test_solver.py::test_rule_block_conflict_analysis_reads_propagator_reasons",
    "tests/test_solver.py::test_rule_block_final_conflict_reads_propagator_reasons",
    "tests/test_solver.py::test_rule_block_random_search_like_clauses",
}
BORROW = "Already mutably borrowed", "Already borrowed"
SOLVER_TYPES = {"Solver", "rust_plugin.Solver", "_CountingSolver", "BlockSolver", "MentionSolver"}


def rows(work):
    out = {}
    for f in glob.glob(os.path.join(work, "rows.*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            out[r["id"]] = r
    return out


def file_of(nodeid):
    return os.path.basename(nodeid.split("::")[0]).removesuffix(".py")


def raised_at(r):
    f = r["failure"]
    frames = FRAME.findall(f.get("text") or "")
    if frames:
        return f"{frames[-1][0]}:{frames[-1][1]}"
    return (f.get("where") or "?").replace(os.getcwd() + "/", "")


def raised_in(r):
    return os.path.basename(raised_at(r).split(":")[0]).removesuffix(".py")


def same_failure(a, b):
    """The last line of the failure, with addresses out."""
    last = lambda r: re.sub(r"0x[0-9a-f]+", "0x", (r["failure"]["crash"] or "").strip().splitlines()[-1])[:200]
    return last(a) == last(b)


def classify(r, py_attrs):
    """(class, detail) of a failed row."""
    f = r["failure"] or {}
    text = (f.get("crash") or "") + "\n" + (f.get("text") or "")
    if r["id"] in SUBCLASS and "assert" in (f.get("crash") or "") and ("n_rb_reasons" in text or "assert read > 0" in text):
        return "internals", "subclass override of _rb_reason"
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
    p.add_argument("--list", help="write every needs-internals and re-entry test here by name, with the line that raised")
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
    if a.list:
        with open(a.list, "w") as f:
            for c in ("internals", "reentry"):
                f.write(f"## {c}\n\n| test | raised at | reason | on Python |\n|---|---|---|---|\n")
                for i, d, po in classes[c]:
                    f.write(f"| `{i}` | `{raised_at(rs[i])}` | {d if c == 'internals' else 'borrow RuntimeError'} | {po} |\n")
                f.write("\n")
    both = [x for x in classes["gate"] if x[2] == "failed" and same_failure(rs[x[0]], ps[x[0]])]
    only = [x for x in classes["gate"] if x not in both]
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
    print(f"| Failed on Rust: other, failing the same way on pure Python | {len(both)} |")
    print(f"| Failed on Rust: other, passing on Python | {len(only)} |")
    print(f"| Python solvers made in the Rust run | {sum(r['py_made'] for r in rs.values())} |")
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
    by = collections.Counter((raised_in(rs[i]), d) for i, d, _ in classes["internals"])
    for (f, d), n in sorted(by.items()):
        flag = "" if f in HANDOFF_FILES else "  **NOT in the handoff's list**"
        print(f"- `{f}`: `{d}`: {n}{flag}")
    print(f"\nHandoff files with none: {sorted(HANDOFF_FILES - {f for f, _ in by})}\n")

    bad = [i for i, _, po in classes["internals"] if po != "passed"]
    print(f"Kept tests not passing on Python in the baseline run: {bad}\n")

    print("### Re-entry, by the last test frame before the raise")
    for w, n in collections.Counter(raised_at(rs[i]) for i, _, _ in classes["reentry"]).most_common():
        print(f"- `{w}`: {n}")
    print("\n### Other failures, passing on Python")
    for i, d, po in only:
        print(f"- `{i}` (Python: {po}): {d}")
    print("\n### Other failures, failing the same way on Python")
    for i, _, _ in both:
        print(f"- `{i}`")

    print("\n### Passed after writing a private attribute the crate doesn't have (the write did nothing)")
    w = collections.defaultdict(list)
    for i in passed:
        for n in rs[i]["private_writes"]:
            w[n].append(i)
    for n, ids in sorted(w.items()):
        print(f"- `{n}`: {len(ids)}, e.g. `{ids[0]}`")


if __name__ == "__main__":
    main()
