"""fzcmp342.py DIR SHA... (sa-port-342): fz342.py's rows with SLICE_WITNESS=1 against =0, per SHA, kind, seed, mode and
hash seed: rows that differ in the answer, the exception type or its message. Per SHA and kind: runs, queries, rows that
differ, exceptions by type (off / on), the check's calls and certified pairs with the switch on (and with it off: 0)."""
import collections, glob, json, os, sys
d, shas = sys.argv[1], sys.argv[2:]
bad = 0
for sha in shas:
    tot = collections.defaultdict(lambda: collections.Counter())
    exc = collections.defaultdict(lambda: [collections.Counter(), collections.Counter()])
    for f0 in sorted(glob.glob(f"{d}/{sha}-*-0.json")):
        f1 = f0[:-6] + "1.json"
        key = os.path.basename(f0)[len(sha) + 1:-7]
        try:
            a, b = json.loads(open(f0).read()), json.loads(open(f1).read())
        except Exception as e:
            print(sha, key, "MISSING OR UNREADABLE", type(e).__name__)
            bad += 1
            continue
        k = (a["kind"], a["mode"])
        t = tot[k]
        assert a["witness"] is False and b["witness"] is True, (f0, a["witness"], b["witness"])
        diff = [(i, x, y) for i, (x, y) in enumerate(zip(a["rows"], b["rows"])) if x != y]
        if len(a["rows"]) != len(b["rows"]) or not a["rows"]:
            diff.append(("length", len(a["rows"]), len(b["rows"])))
        t["runs"] += 1
        t["rows"] += len(a["rows"])
        t["asks"] += sum(r[0] != "event" for r in a["rows"])
        t["differ"] += len(diff)
        t["runs that differ"] += bool(diff)
        t["calls off"] += a["fires"]
        t["calls on"] += b["fires"]
        t["certified on"] += b["certified"]
        for j, x in enumerate((a, b)):
            for r in x["rows"]:
                if r[0] == "raise":
                    exc[k][j][r[1]] += 1
        if diff:
            bad += 1
            print(sha, key, "DIFFER", len(diff), "first:", json.dumps(diff[:3])[:600])
    for k in sorted(tot):
        print(sha, k[0], k[1], dict(tot[k]), "exceptions off", dict(exc[k][0]), "on", dict(exc[k][1]))
print("FZ", "rows equal on every run" if not bad else f"{bad} runs differ or are missing")
