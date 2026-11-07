"""hash_trace_sum.py ROWS.json [ROWS.json ...]: sums hash_trace.py's `site` key by (Rust callable, caller line) for
Basic.__hash__ and Integer.__hash__, one column per file. Reads summary only; prints the top N groups (default 40)."""
import collections, json, os, sys
N = int(os.environ.get("N", "40"))
level = os.environ.get("LEVEL", "site")   # rust | site | parent
cols = []
for p in sys.argv[1:]:
    d = json.load(open(p))
    c = collections.Counter()
    for k, v in d["site"].items():
        rust, site, parent, callee = k.split("|")
        if callee not in ("Basic.__hash__", "Integer.__hash__"):
            continue
        key = {"rust": rust, "site": f"{rust} <- {site}", "parent": f"{rust} <- {site} <- {parent}"}[level]
        c[(key, callee)] += v
    cols.append((os.path.basename(p), d["rust2py"].get("Basic.__hash__", 0), d["rust2py"].get("Integer.__hash__", 0), c))
keys = collections.Counter()
for *_, c in cols:
    for k, v in c.items():
        keys[k[0]] += v
print("\t".join(["group"] + [f"{n} B\t{n} I" for n, *_ in cols]))
for k, _ in keys.most_common(N):
    print("\t".join([k] + [f"{c[(k, 'Basic.__hash__')]}\t{c[(k, 'Integer.__hash__')]}" for *_, c in cols]))
print("\t".join(["TOTAL rust2py"] + [f"{b}\t{i}" for _, b, i, _ in cols]))
print("\t".join(["TOTAL site"] + [f"{sum(v for k, v in c.items() if k[1] == 'Basic.__hash__')}\t{sum(v for k, v in c.items() if k[1] == 'Integer.__hash__')}" for *_, c in cols]))
