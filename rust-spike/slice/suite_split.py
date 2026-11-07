"""suite_split.py RUST PYTHON [--base-rust DIR --base-python DIR]: the planner's two numbers for a suite run with handler_count on.

Passed splits by id into passed with no firing and passed with a handler firing on RUST that doesn't fire on PYTHON for that test,
listing type and text. Compared as a multiset of (site, type, text), so a firing Python also has isn't counted against Rust. Nothing
is reclassified by hand. Also: outcomes against the base by id, the planted rows per worker (a worker with fewer than 4 proves nothing),
knowledge counts summed over workers, and firings on failed tests, kept apart.
"""
import argparse
import collections
import glob
import json
import os
import re


def rows(work):
    out = {}
    for f in glob.glob(os.path.join(work, "rows.*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            out[r["id"]] = r
    return out


def firings(work):
    by, plants = collections.defaultdict(collections.Counter), collections.Counter()
    workers = 0
    for f in glob.glob(os.path.join(work, "handlers.*.jsonl")):
        workers += 1
        for line in open(f):
            r = json.loads(line)
            if str(r["where"]).startswith("plant:"):
                plants[r["where"]] += 1
            else:
                # ids and addresses inside a message aren't part of what fired
                by[r["where"]][r["site"], r["type"], re.sub(r"0x[0-9a-f]+", "0x", r["text"])] += 1
    return by, plants, workers


def main():
    p = argparse.ArgumentParser()
    p.add_argument("rust")
    p.add_argument("python")
    p.add_argument("--base-rust")
    p.add_argument("--list", help="write the second group here in full")
    a = p.parse_args()
    rs, ps = rows(a.rust), rows(a.python)
    rf, rplants, rw = firings(a.rust)
    pf, pplants, pw = firings(a.python)
    for name, plants, w in (("rust", rplants, rw), ("python", pplants, pw)):
        print(f"{name}: {w} handler files, planted rows {dict(plants)}")
    outcomes = collections.Counter(r["outcome"] for r in rs.values())
    print("rust outcomes", dict(outcomes), "python outcomes", dict(collections.Counter(r["outcome"] for r in ps.values())))
    clean, second, failed_firing = [], {}, {}
    for i, r in sorted(rs.items()):
        extra = rf.get(i, collections.Counter()) - pf.get(i, collections.Counter())
        if r["outcome"] == "passed":
            if extra:
                second[i] = extra
            else:
                clean.append(i)
        elif extra:
            failed_firing[i] = extra
    print(f"passed {outcomes['passed']} = no firing beyond Python {len(clean)} + firing on Rust not on Python {len(second)}")
    print(f"tests with any firing: rust {len(rf)}, python {len(pf)}; firings outside any recorded test id:",
          sorted(set(rf) - set(rs))[:5])
    kinds = collections.Counter()
    for c in second.values():
        for (site, typ, text), n in c.items():
            kinds[site, typ, text[:100]] += n
    for k, n in kinds.most_common(25):
        print(" ", n, k)
    print("failed on Rust with an extra firing:", len(failed_firing))
    if a.list:
        with open(a.list, "w") as fh:
            for i, c in second.items():
                for k, n in c.items():
                    fh.write(json.dumps(dict(id=i, n=n, site=k[0], type=k[1], text=k[2])) + "\n")
    if a.base_rust:
        base = rows(a.base_rust)
        moved = [(i, base[i]["outcome"], rs[i]["outcome"]) for i in sorted(set(base) & set(rs)) if base[i]["outcome"] != rs[i]["outcome"]]
        print("against base by id:", len(moved), "moved; only in base", len(set(base) - set(rs)), "only here", len(set(rs) - set(base)))
        for m in moved[:40]:
            print(" ", m)
    counts = collections.Counter()
    for f in glob.glob(os.path.join(a.rust, "knowledge.*.json")):
        counts.update(json.load(open(f))["counts"])
    print("knowledge counts", dict(counts))


if __name__ == "__main__":
    main()
