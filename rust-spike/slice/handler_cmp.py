"""What handler_count saw, Rust against Python, under the planner's two reporting rulings.
  suite RUST_DIR PY_DIR: passed on Rust split by firing, by test id with type and text. handlers.*.jsonl and rows.*.jsonl.
  live RUST_JSONL... -- PY_JSONL...: per query, firings on Rust that Python doesn't have, split by whether a session of
  that query moved. Each JSONL's `.handlers` is beside it; `JSONL.items` (a forced run) maps a row's place to its query.
Firings are compared as (site, type, text) with addresses scrubbed; a differing count of the same firing is shown as a
difference too, since a handler that fires more often on Rust is what this looks for."""
import collections
import glob
import json
import os
import re
import sys

ADDR = re.compile(r"0x[0-9a-fA-F]+")


def firing(r):
    return r["site"], r["type"], ADDR.sub("0xX", r["text"])


def read_handlers(paths, key=lambda w: w):
    out = collections.defaultdict(collections.Counter)
    for p in paths:
        with open(p) as f:
            for line in f:
                r = json.loads(line)
                out[key(r["where"])][firing(r)] += 1
    return out


def show(fs):
    return "; ".join(f"{n}x {s} {t}: {x[:120]}" for (s, t, x), n in fs.most_common())


def suite(rust, py):
    outcome = {}
    for p in glob.glob(f"{rust}/rows.*.jsonl"):
        with open(p) as f:
            for line in f:
                r = json.loads(line)
                outcome[r["id"]] = r["outcome"]
    a = read_handlers(glob.glob(f"{rust}/handlers.*.jsonl"))
    b = read_handlers(glob.glob(f"{py}/handlers.*.jsonl"))
    passed = [i for i, o in outcome.items() if o == "passed"]
    none, rust_only, same, py_only = [], [], [], []
    for i in passed:
        extra, lost = a[i] - b[i], b[i] - a[i]
        if extra:
            rust_only.append((i, extra))
        elif lost:
            py_only.append((i, lost))
        elif a[i]:
            same.append((i, a[i]))
        else:
            none.append(i)
    print(f"rows {len(outcome)}; passed on Rust {len(passed)}: no firing {len(none)}; firing on Rust not on Python "
          f"{len(rust_only)}; same firing on both {len(same)}; firing on Python not on Rust {len(py_only)}")
    for title, group in (("RUST ONLY", rust_only), ("PYTHON ONLY", py_only), ("BOTH", same)):
        for i, fs in sorted(group):
            print(f"{title} {i}: {show(fs)}")
    other = sorted(i for i in a if outcome.get(i) != "passed")
    print(f"not passed on Rust, with a firing: {len(other)}")
    for i in other:
        print(f"  {outcome.get(i, 'NO ROW')} {i}: {show(a[i] - b[i]) or '(same as Python)'}")


def rows(path):
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if "q" in r:
                yield r


def live(rust, py):
    b = read_handlers([p + ".handlers" for p in py])
    moved, totals = {}, collections.Counter()
    extra = collections.defaultdict(collections.Counter)
    for p in rust:
        items = None
        if os.path.exists(p + ".items"):
            with open(p + ".items") as f:
                items = json.load(f)
        to_q = (lambda w: items[w][0]) if items else (lambda w: w)
        a = read_handlers([p + ".handlers"])
        for r in rows(p):
            q = r["q"]
            m = any((s.get("group") or "").startswith("moved") for s in r.get("sessions", []))
            moved[(p, q)] = m
            totals["rows"] += 1
            totals["rows with a moved session"] += m
        for w, fs in a.items():
            totals["firings"] += sum(fs.values())
            diff = fs - b[to_q(w)]
            if diff:
                extra[moved.get((p, w), False)][(p, w)] = diff
    print(dict(totals))
    for m, label in ((True, "ROW WITH A MOVED SESSION, a failure under the ruling"), (False, "no moved session")):
        print(f"firing on Rust not on Python, {label}: {len(extra[m])}")
        for (p, w), fs in sorted(extra[m].items(), key=str)[:40]:
            print(f"  {os.path.basename(p)} {w}: {show(fs)}")


if __name__ == "__main__":
    if sys.argv[1] == "suite":
        suite(sys.argv[2], sys.argv[3])
    else:
        cut = sys.argv.index("--")
        live(sys.argv[2:cut], sys.argv[cut + 1:])
