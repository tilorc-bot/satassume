"""tab364.py DIR (sa-port-364): the computed-against-read table from cnt364.py's rows (gocnt364.sh's DIR/WL-CELL.json).
Per workload and cell: queries, and for each result of domain.py the count computed, the count read, and the number of
queries with at least one of each. Then the callers over the pass. Markdown on stdout."""
import json, sys
d = sys.argv[1]
WLS, CELLS = ("dev", "fuzz", "budget", "wiring"), ("py", "rust-py", "rust-nat")


def tot(rows, pred):
    n = q = 0
    for r in rows:
        s = sum(v for k, v in r.items() if pred(k))
        n += s
        q += 1 if s else 0
    return n, q


RES = [
    ("level: computed (outer calls of constructed_noncommutative)", lambda k: k == "constructed_noncommutative|outer"),
    ("level: of them not 0", lambda k: k == "constructed_noncommutative|nonzero"),
    ("level: read through engine._construction_level", lambda k: k.startswith("level_read|")),
    ("TermTable.row calls (the one exposer of the table's level column; term_live.scaffold reads row[0] and row[1] only)", lambda k: k.startswith("row_call|")),
    ("nc: read (calls of _noncommutative)", lambda k: k in ("_noncommutative|outer", "_noncommutative|inner")),
    ("nc: computed (calls with no memo row: the walk)", lambda k: k.startswith("nc_walk|")),
    ("nc: of the reads True", lambda k: k == "_noncommutative|nonzero"),
    ("nfalse: calls of noncommutative_false", lambda k: k.startswith("noncommutative_false|")),
    ("kept: calls of kept_product", lambda k: k.startswith("kept_product|")),
    ("fixed: calls of _fixed_noncommutative", lambda k: k.startswith("_fixed_noncommutative|")),
]
data = {}
for wl in WLS:
    for c in CELLS:
        try:
            data[wl, c] = json.load(open("%s/%s-%s.json" % (d, wl, c)))
        except OSError:
            pass
print("| workload | cell | queries | answers' digest | " + " | ".join(n for n, _ in RES) + " |")
print("|---|---|---|---|" + "---|" * len(RES))
for wl in WLS:
    for c in CELLS:
        j = data.get((wl, c))
        if j is None:
            continue
        cells = ["%d (%d q)" % tot(j["rows"], p) for _, p in RES]
        print("| %s | %s | %d | %s | %s |" % (wl, c, j["n"], j["digest"], " | ".join(cells)))
print()
for wl in WLS:
    for c in CELLS:
        j = data.get((wl, c))
        if j is None:
            continue
        print("%s %s callers: %s" % (wl, c, "; ".join("%s %d" % kv for kv in j["callers"].items())))
        print("%s %s values: %s" % (wl, c, "; ".join("%s: %d" % kv for kv in j["values"].items())))
        print("%s %s row callers: %s; selfcheck (the read counters on a planted read, after the pass): %s" % (
            wl, c, sorted({k for r in j["rows"] for k in r if k.startswith("row_call|")}), {k: v for k, v in j["selfcheck"].items() if k != "row"}))
        print("%s %s term_shadow loaded: %s; so %s; convert=%s" % (wl, c, j["term_shadow"], j["so"], j["convert"]))
