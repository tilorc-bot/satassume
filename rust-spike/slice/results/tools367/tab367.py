"""tab367.py PROFDIR CNTDIR PATH [SHARE] (sa-port-367): the audit's tables for one path (PATH = default | rust-nat) from
PROFDIR/time/time.jsonl (pys367.sh's timed rows), PROFDIR/ana-WL-MODE.json (ana367.py) and CNTDIR/WL-PATH.json
(cnt367.py). Shares are of the sampler's in-loop samples of that path; seconds are share times the median timed pass.

(A) own and inclusive share per Python file, ranked by own summed over the four workloads; the files that together
    carry SHARE (default 80%) of the repository files' own time are marked *.
(B) per function of the marked files: own and inclusive share, calls, returns dropped at the call site, call sites.
(C) per stored field of the classes of the marked files, cnt367.py's counts: computes (non-trivial writes + in-place
    fills + self-updates), epochs (results computed: per object, clean to dirty), epochs read (a use that found the
    result unread), uses; the queries with a write and with a use; writers; readers ([mut] = fills in place, [aug] =
    self-update, ~ = not a LOAD_ATTR at that line: getattr() or a native reader). A field whose every write is
    trivial and that is never filled is `init only`: no result is computed into it on these workloads.
Classes: `read 0` (computed, never read: a removal candidate), `minority` (read on fewer than half of the computes: a
compute-on-first-read candidate), `read` (a port candidate), `-` (not computed on these workloads), `no value` (a
function without a returned value: its results are the fields it stores).
A reader in tests/, or in a slice module that is a check or an instrument (EXCL below), is marked [x] and not counted
as a read by the classes here only if cnt367.py saw it; the counted cells install none of them, so none appears."""
import collections, json, statistics, sys
prof, cnt, path = sys.argv[1:4]
share = float(sys.argv[4]) if len(sys.argv) > 4 else 0.80
mode = "py" if path == "default" else "rust"
WLS = ("dev", "fuzz", "budget", "wiring")
med = statistics.median
rows = [json.loads(l) for l in open(prof + "/time/time.jsonl")]
S = {}
print("## %s: wall time, 5 rounds pinned\n\n| workload | median s | min | max | iqr/median | digest | .so |\n|---|---|---|---|---|---|---|" % path)
for wl in WLS:
    g = [r for r in rows if r["wl"] == wl and r["arm"] == path]
    v = [r["s"] for r in g]
    q = statistics.quantiles(v, n=4)
    S[wl] = med(v)
    print("| %s | %.4f | %.4f | %.4f | %.1f%% | %s | %s |" % (wl, med(v), min(v), max(v), 100 * (q[2] - q[0]) / med(v),
          ",".join(sorted({r["digest"] for r in g})), ",".join(sorted({str(r.get("so")) for r in g}))))
A = {wl: json.load(open("%s/ana-%s-%s.json" % (prof, wl, mode))) for wl in WLS}
C = {wl: json.load(open("%s/%s-%s.json" % (cnt, wl, path))) for wl in WLS}
print("\nsampler: " + "; ".join("%s N %d, %d runs, digests %s, cats %s" % (wl, A[wl]["N"], len(A[wl]["runs"]), sorted({r[1] for r in A[wl]["runs"]}),
      ", ".join("%s %.1f" % (k, 100 * v / A[wl]["N"]) for k, v in sorted(A[wl]["cats"].items(), key=lambda x: -x[1])[:6])) for wl in WLS))
print("counts: " + "; ".join("%s digest %s .so %s env %s, plants failed %d, fields shown to fire %d (no live object %d)" % (
      wl, C[wl]["digest"], C[wl]["so"], C[wl]["env"], len(C[wl]["plant"]["failed"]), C[wl]["plant"]["fields_ok"],
      len(C[wl]["plant"]["fields_no_object"])) for wl in WLS))
own = lambda a, k: a["byte"].get(k, 0) + a["c"].get(k, 0)
pct = lambda wl, n: 100.0 * n / A[wl]["N"]
files = sorted({k for a in A.values() for k in list(a["byte"]) + list(a["c"]) + list(a["incl"])}, key=lambda k: -sum(pct(wl, own(A[wl], k)) for wl in WLS))
repo = [k for k in files if k.startswith(("sa/", "slice/"))]
tot = sum(pct(wl, own(A[wl], k)) for k in repo for wl in WLS)
print("\n## (A) %s: own / inclusive share per file (%% of in-loop samples); * = in the %d%% set\n" % (path, 100 * share))
print("| file | " + " | ".join(w + " own / incl" for w in WLS) + " | own summed | cumulative of repository files | SymPy and stdlib under it, summed |\n|---|" + "---|" * (len(WLS) + 3))
for k in ("sympy", "stdlib"):
    print("| (%s: not a file to port) | %s | %.2f | | |" % (k, " | ".join("%.2f / %.1f" % (pct(wl, own(A[wl], k)), pct(wl, A[wl]["incl"].get(k, 0))) for wl in WLS),
          sum(pct(wl, own(A[wl], k)) for wl in WLS)))
cum = 0.0
marked = []
for k in repo:
    s = sum(pct(wl, own(A[wl], k)) for wl in WLS)
    if s < 0.05:
        break
    star = cum < share * tot
    cum += s
    if star:
        marked.append(k)
    und = sum(pct(wl, sum(A[wl]["under"].get(k, {}).values())) for wl in WLS)
    print("| %s%s | %s | %.2f | %.1f%% | %.2f |" % ("* " if star else "", k, " | ".join("%.2f / %.1f" % (pct(wl, own(A[wl], k)), pct(wl, A[wl]["incl"].get(k, 0))) for wl in WLS), s, 100 * cum / tot, und))
print("\nrepository files' own time summed over the four workloads: %.2f points; per workload: %s" % (tot, ", ".join(
      "%s %.2f%% = %.4f s" % (wl, sum(pct(wl, own(A[wl], k)) for k in repo), S[wl] * sum(own(A[wl], k) for k in repo) / A[wl]["N"]) for wl in WLS)))
print("marked: " + " ".join(marked))


def fcls(d):
    if d is None or not d["calls"]:
        return "-"
    if not d["returns"] or d["generator"]:
        return "no value" if not d["returns"] else "read"
    r = d["calls"] - d["discarded"]
    return "read 0" if r == 0 else ("minority" if 2 * r < d["calls"] else "read")


def dcls(d):
    if d is None or not d["writes"] + d["reads"]:
        return "-"
    if not d["epochs"]:
        return "init only"
    return "read 0" if d["epochs_read"] == 0 else ("minority" if 2 * d["epochs_read"] < d["epochs"] else "read")


worst = lambda cs: next((c for c in ("read 0", "minority", "read", "no value", "init only") if c in cs), "-")


def fworst(ds):
    """A field's class over the four workloads: by the summed epochs, so one workload's zero does not decide it."""
    e = sum(d["epochs"] for d in ds.values() if d)
    r = sum(d["epochs_read"] for d in ds.values() if d)
    if not e:
        return "init only" if any(d and d["writes"] + d["reads"] for d in ds.values()) else "-"
    return "read 0" if r == 0 else ("minority" if 2 * r < e else "read")
classtime = collections.defaultdict(lambda: collections.Counter())
print("\n## (B) %s: functions of the marked files (own%% / incl%% / SymPy+stdlib under it%% ; calls / dropped returns)\n" % path)
for k in marked:
    fn = collections.defaultdict(dict)
    for wl in WLS:
        for key, d in C[wl]["funcs"].items():
            f, q, line = key.rsplit(":", 2)
            if f == k:
                fn[q, line][wl] = d
    samp = {}
    for wl in WLS:
        for key, n in A[wl]["ownf"].items():
            if key.startswith(k + ":"):
                samp.setdefault(key[len(k) + 1:], {})[wl] = n
    lines = collections.defaultdict(list)
    for (q, line) in fn:
        lines[q].append(line)
    print("### %s\n\n| function:line | class | %s | %s | call sites (dev, else the first workload with calls) |\n|---|---|%s" % (
          k, " | ".join(w + " own/incl/under" for w in WLS), " | ".join(w + " calls/dropped" for w in WLS), "---|" * (2 * len(WLS) + 1)))
    order = sorted(set(q for q, _ in fn) | set(samp), key=lambda q: -sum(pct(wl, A[wl]["ownf"].get(k + ":" + q, 0)) for wl in WLS))
    for q in order:
        ls = sorted(lines.get(q, ["?"]), key=lambda x: int(x) if x != "?" else 0)
        for line in ls:
            ds = fn.get((q, line), {})
            cl = worst({fcls(ds.get(wl)) for wl in WLS})
            share1 = 1.0 / len(ls)
            cells = " | ".join("%.2f/%.2f/%.2f" % (pct(wl, A[wl]["ownf"].get(k + ":" + q, 0)), pct(wl, A[wl]["inclf"].get(k + ":" + q, 0)),
                               pct(wl, A[wl]["underf"].get(k + ":" + q, 0))) for wl in WLS)
            cc = " | ".join("%d/%d" % (ds[wl]["calls"], ds[wl]["discarded"]) if wl in ds else "0" for wl in WLS)
            first = next((ds[wl] for wl in WLS if wl in ds), None)
            st = "; ".join("%s x%d" % (s.split(" ")[0], n) for s, n in (first["sites"][:3] if first else []))
            print("| %s:%s%s | %s | %s | %s | %s |" % (q, line, " (%d defs share the samples)" % len(ls) if len(ls) > 1 else "", cl, cells, cc, st))
            for wl in WLS:
                classtime[cl][wl] += share1 * S[wl] * A[wl]["ownf"].get(k + ":" + q, 0) / A[wl]["N"]
    print()
print("## (C) %s: stored fields of the marked files' classes (computes / epochs / epochs read / uses ; queries with a write / with a use)\n" % path)
flag = []
for k in marked:
    names = sorted({key for wl in WLS for key in C[wl]["fields"] if key.startswith(k + ":")})
    if not names:
        continue
    print("### %s\n\n| class.field | class | %s | writers | readers (top 4) |\n|---|---|%s" % (k, " | ".join(w + " c/e/er/u ; wq/rq" for w in WLS), "---|" * (len(WLS) + 2)))
    for key in names:
        ds = {wl: C[wl]["fields"].get(key) for wl in WLS}
        cl = fworst(ds)
        cells = " | ".join("%d/%d/%d/%d ; %d/%d" % (d["writes"] - d["trivial"] + d["mut"] + d["aug"], d["epochs"], d["epochs_read"], d["use"], d["wq"], d["rq"]) if d else "0" for d in ds.values())
        first = next((d for d in ds.values() if d and d["writes"]), None) or next((d for d in ds.values() if d), None)
        wr = "; ".join("%s x%d" % (s.split(" ")[0], n) for s, n in (first.get("writers", [])[:3] if first else []))
        rd = "; ".join("%s%s x%d" % (s.split(" ")[0], "~" * ("(via)" in s) + "".join(t for t in (" [mut]", " [aug]") if t in s), n) for s, n in (first["readers"][:4] if first else []))
        print("| %s | %s | %s | %s | %s |" % (key[len(k) + 1:], cl, cells, wr, rd))
        if cl in ("read 0", "minority"):
            flag.append((k, key[len(k) + 1:], cl))
    print()
print("## (D) %s: own time of the marked files' functions by class of the returned value, seconds per pass\n" % path)
print("| class | " + " | ".join(WLS) + " |\n|---|" + "---|" * len(WLS))
for cl in ("read 0", "minority", "read", "no value", "-"):
    print("| %s | %s |" % (cl, " | ".join("%.4f (%.2f%%)" % (classtime[cl][wl], 100 * classtime[cl][wl] / S[wl]) for wl in WLS)))
print("\nfields classed read 0 or minority (%d): %s" % (len(flag), "; ".join("%s %s [%s]" % f for f in flag)))
