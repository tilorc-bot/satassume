"""pcsum344.py DIR (sa-port-344, issue 323): the per-call rows of tools343/pc343.py (DIR/pc-SHA-WL-MODE-PASS.json,
3 passes on a quiet lease) read per SHA, workload and mode. A call's time is its median over the passes.
Prints: the calls and seconds of the check; certified against fall-through (n, sum, median, 90%, max); per exit of
Engine.ask after a fall-through (py mode; rust mode wraps the check only); the 10 calls with the most time in the
check, by query index, with points tried (pc344.py rows: calls of _holds), the exit and the first 70 characters of the query; and the calls whose
exit is over-budget, by query index."""
import glob, json, os, re, statistics as st, sys
D = sys.argv[1]
rows = {}
for f in sorted(glob.glob(os.path.join(D, "pc-*.json"))):
    sha, wl, mode, k = re.match(r"pc-([0-9a-f]+)-(\w+)-(\w+)-(\d+)\.json", os.path.basename(f)).groups()
    rows.setdefault((wl, mode, sha), []).append(json.load(open(f)))
def q(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else 0.0
def line(name, xs):
    return "%s n %d sum %.4f s median %.1f us 90%% %.1f us max %.1f us" % (name, len(xs), sum(xs) / 1e6, st.median(xs) if xs else 0, q(xs, .9), max(xs) if xs else 0)
for key in sorted(rows):
    P = rows[key]; wl, mode, sha = key
    assert len({(d["digest"], d["fires"], d["compiled"], d["certified"], len(d["calls"])) for d in P}) == 1, key
    d = P[0]; n = len(d["calls"])
    assert all([c[0] for c in p["calls"]] == [c[0] for c in d["calls"]] and [c[2:5] for c in p["calls"]] == [c[2:5] for c in d["calls"]] for p in P), key
    chk = [st.median(p["calls"][i][1] for p in P) for i in range(n)]
    eng = [st.median(p["calls"][i][5] for p in P) if d["calls"][i][5] is not None else None for i in range(n)]
    print("%s %s %s: passes %d queries %d calls %d compiled %d certified %d digest %s so %s; check_s by pass %s; pass s (wrapped, not S1) %s" % (
        wl, mode, sha, len(P), d["n"], d["fires"], d["compiled"], d["certified"], d["digest"], (d["so"] or "-")[:16],
        ["%.4f" % p["check_s"] for p in P], ["%.3f" % p["s"] for p in P]))
    print("  " + line("certified", [chk[i] for i in range(n) if d["calls"][i][2]]))
    print("  " + line("fall-through", [chk[i] for i in range(n) if not d["calls"][i][2]]))
    exits = sorted({c[4] for c in d["calls"] if c[4]})
    for e in exits:
        ix = [i for i in range(n) if d["calls"][i][4] == e]
        es = [eng[i] for i in ix if eng[i] is not None]
        print("  exit " + line(e, [chk[i] for i in ix]) + "; Engine.ask after it sum %.4f s median %.1f us" % (sum(es) / 1e6, st.median(es) if es else 0))
    text = {t["q"]: (t["prop"] + " | " + t["assume"]) for p in P for t in p["top"]}
    if len(d["calls"][0]) > 6:   # pc344.py rows: calls of _holds and microseconds before _pools
        pts = [d["calls"][i][6] for i in range(n)]
        cmp_ = [st.median(p["calls"][i][7] for p in P) if d["calls"][i][7] is not None else None for i in range(n)]
        reach = [i for i in range(n) if cmp_[i] is not None]
        print("  compile (before _pools): calls that reach _pools %d, sum %.4f s of the check's %.4f s in them; calls that stop in the compile %d, sum %.4f s" % (
            len(reach), sum(cmp_[i] for i in reach) / 1e6, sum(chk[i] for i in reach) / 1e6, n - len(reach), sum(chk[i] for i in range(n) if cmp_[i] is None) / 1e6))
        for name, ix in (("certified", [i for i in range(n) if d["calls"][i][2]]), ("fall-through", [i for i in range(n) if not d["calls"][i][2]])):
            hp = [pts[i] for i in ix]
            print("  points decided (_holds), %s: sum %d median %s 90%% %s max %s; calls at 32 or more: %d" % (name, sum(hp), st.median(hp) if hp else 0, q(hp, .9), max(hp) if hp else 0, sum(1 for h in hp if h >= 32)))
    top = sorted(range(n), key=lambda i: -chk[i])[:10]
    print("  top 10 [query index, check us, tried, exit, engine us]: " + "; ".join(
        "[%d, %.1f, %s, %s, %s]" % (d["calls"][i][0], chk[i], d["calls"][i][6] if len(d["calls"][i]) > 6 else d["calls"][i][3], d["calls"][i][4], "%.1f" % eng[i] if eng[i] is not None else "-") for i in top))
    print("  top 10 sum %.4f s of %.4f s" % (sum(chk[i] for i in top) / 1e6, sum(chk) / 1e6))
    for i in top[:3]:
        print("    q%d %s" % (d["calls"][i][0], text.get(d["calls"][i][0], "?")[:70]))
    ob = [i for i in range(n) if d["calls"][i][4] == "over-budget"]
    if ob:
        print("  over-budget by query index [q, check us, tried, engine us]: " + "; ".join("[%d, %.1f, %s, %.1f]" % (d["calls"][i][0], chk[i], ("%d points, compile %.1f us" % (d["calls"][i][6], cmp_[i])) if len(d["calls"][i]) > 6 else d["calls"][i][3], eng[i]) for i in ob))
