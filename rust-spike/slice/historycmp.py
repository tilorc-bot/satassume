"""historycmp.py WORK: plan section 3's runs 1 to 4, from run_history.sh. Prints markdown.
Each row is Rust against Python on the same query, seed and order, by answer, end state and call stream. Then the same
backend against itself across orders, which says what history does to each backend: Rust must move exactly where
Python does, so the table names each query whose state moved on either one."""
import json
import os
import sys

TWICE = 1000000


def read(path):
    rows, total = {}, None
    if not os.path.exists(path):
        return rows, total
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


def sess(r, f):
    return [s[f] for s in r.get("sessions", [])]


def cmp_pair(a, b):
    n = dict(q=0, ans=0, msg=0, sessions=0, end=0, stream=0, count=0)
    first = {}
    for q in sorted(set(a) & set(b)):
        x, y = a[q], b[q]
        n["q"] += 1
        if x["ans"] != y["ans"]:
            n["ans"] += 1
            first.setdefault("ans", q)
        n["msg"] += x["msg"] != y["msg"]
        sx, sy = x.get("sessions", []), y.get("sessions", [])
        n["count"] += len(sx) != len(sy)
        for u, v in zip(sx, sy):
            n["sessions"] += 1
            if u["end"] != v["end"]:
                n["end"] += 1
                first.setdefault("end", q)
            if u["stream"] != v["stream"]:
                n["stream"] += 1
                first.setdefault("stream", q)
    return n, first


def moved(base, other):
    """Queries whose answer, or any state, differs from the base run."""
    ans, st = set(), set()
    for q in set(base) & set(other):
        if base[q]["ans"] != other[q]["ans"]:
            ans.add(q)
        if sess(base[q], "end") != sess(other[q], "end") or sess(base[q], "stream") != sess(other[q], "stream"):
            st.add(q)
    return ans, st


def main():
    w = sys.argv[1]
    runs = ["recorded", "shuffle1", "shuffle2", "fork", "twice", "seed1", "seed2"]
    data = {}
    print("### Rust against Python, same query, order and seed\n")
    print("| run | wl | queries Py/Rust | total rows | answers differ | msgs differ | sessions | end state differ | stream differ | session count differ | dropped/created |")
    print("|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|")
    bad = 0
    for run in runs:
        for wl in ("dev", "fuzz"):
            py, tp = read(f"{w}/{run}-{wl}-py.jsonl")
            rs, tr = read(f"{w}/{run}-{wl}-rust.jsonl")
            data[run, wl] = py, rs
            n, first = cmp_pair(py, rs)
            done = "yes" if tp and tr else "**no**"
            dc = f"{tr.get('backend_dropped')}/{tr.get('backend_created')}" if tr else "?"
            print(f"| {run} | {wl} | {len(py)}/{len(rs)} | {done} | {n['ans']} | {n['msg']} | {n['sessions']} | {n['end']} | {n['stream']} | {n['count']} | {dc} |")
            bad += bool(n["ans"] or n["msg"] or n["end"] or n["stream"] or n["count"] or len(py) != len(rs) or not tp or not tr)
            if first:
                print(f"| | first | {first} | | | | | | | | |")
    print(f"\nRuns that differ or didn't finish: {bad}\n")

    print("### Each backend against itself: what history moves\n")
    print("| run, against recorded | wl | Python: answers moved | Rust: answers moved | Python: state moved | Rust: state moved | same queries? |")
    print("|---|---|---:|---:|---:|---:|---|")
    for run in ("shuffle1", "shuffle2", "fork", "seed1", "seed2"):
        for wl in ("dev", "fuzz"):
            pb, rb = data["recorded", wl]
            po, ro = data[run, wl]
            pa, ps = moved(pb, po)
            ra, rs = moved(rb, ro)
            print(f"| {run} | {wl} | {len(pa)} | {len(ra)} | {len(ps)} | {len(rs)} | {'yes' if pa == ra and ps == rs else '**no**'} |")
            if pa | ra:
                print(f"| | | answers: {sorted(pa | ra)[:12]} | | | | |")
            if run.startswith("shuffle") and wl == "dev":
                print(f"| | | query 873 state moved: Python {873 in ps}, Rust {873 in rs} | | | | |")

    print("\n### Run 3: the same query twice in a row\n")
    print("| wl | queries | Python: repeat's answer differs | Rust: repeat's answer differs | same queries? | Python: repeat vs recorded answer | Rust: repeat vs recorded answer |")
    print("|---|---:|---:|---:|---|---:|---:|")
    for wl in ("dev", "fuzz"):
        py, rs = data["twice", wl]
        pb, rb = data["recorded", wl]

        def diff(x):
            return {q for q in x if q < TWICE and q + TWICE in x and x[q]["ans"] != x[q + TWICE]["ans"]}

        def vs(x, b):
            return {q for q in b if q + TWICE in x and x[q + TWICE]["ans"] != b[q]["ans"]}
        dp, dr = diff(py), diff(rs)
        print(f"| {wl} | {sum(q < TWICE for q in py)} | {len(dp)} | {len(dr)} | {'yes' if dp == dr else '**no**'} | {len(vs(py, pb))} | {len(vs(rs, rb))} |")
        if dp | dr:
            print(f"| | {sorted(dp | dr)[:12]} | | | | | |")

    print("\n### Answers across all orders, and answer digests\n")
    for wl in ("dev", "fuzz"):
        shas = {}
        for run in runs:
            for b in ("py", "rust"):
                _, t = read(f"{w}/{run}-{wl}-{b}.jsonl")
                if t and run != "twice":
                    shas.setdefault(t["answers_sha"], []).append(f"{run}-{b}")
        print(f"- {wl}: " + "; ".join(f"`{k}`: {len(v)} runs" for k, v in shas.items()))
    t = {}
    for run in runs:
        for wl in ("dev", "fuzz"):
            _, tr = read(f"{w}/{run}-{wl}-rust.jsonl")
            if tr:
                for k in ("reentry", "entry_raises"):
                    t[k] = t.get(k, 0) + (len(tr[k]) if hasattr(tr[k], "__len__") else tr[k])
                t["python_solvers_made"] = t.get("python_solvers_made", 0) + tr["python_solvers_made"]
    print(f"\nRust runs in total: {t}")


if __name__ == "__main__":
    main()
