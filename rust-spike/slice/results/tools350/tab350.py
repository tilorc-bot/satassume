"""tab350.py DIR... (sa-port-350): the profile of item 1 as a table, from prof350.sh's prof.jsonl. Medians over the
rounds. Shares are of `s` of the plain arm (the pass with only two clock reads per check): the phase arm's own timers
(N calls of perf_counter pairs) inflate its times, so its phases are scaled to the plain arm's check_s."""
import json, statistics, sys
rows = [json.loads(l) for d in sys.argv[1:] for l in open(d + "/prof.jsonl")]
med = statistics.median
key = lambda r: (r["wl"], r["mode"])
print("| workload, mode | off s | on s | on/off | fires | compiled | certified | check s | share | fall-through s | share "
      "| compile | search | evaluation | guards | moves (share of on s) | timer calls |")
print("|" + "---|" * 17)
for k in sorted({key(r) for r in rows}):
    g = lambda arm: [r for r in rows if key(r) == k and r["arm"] == arm]
    off, pl, ph = g("off"), g("plain"), g("phase")
    if not (off and pl and ph):
        continue
    s_off, s_on = med(r["s"] for r in off), med(r["s"] for r in pl)
    chk, fall = med(r["check_s"] for r in pl), med(r["check_fall_s"] for r in pl)
    pc = med(r["check_s"] for r in ph)
    part = {n: med(r[n + "_s"] for r in ph) / pc for n in ("compile", "search", "evaluation", "guards")}
    moves = chk * (1 - part["guards"]) / s_on
    n = ph[0]["N"]
    timers = sum(n[x] for x in ("patched", "known", "users", "pools", "roots", "probe_eval", "enum", "holds"))
    p = pl[0]
    print("| %s %s | %.4f | %.4f | %+.1f%% | %d | %d | %d | %.4f | %.1f%% | %.4f | %.1f%% | %.0f%% | %.0f%% | %.0f%% | %.0f%% | %.1f%% | %d |" % (
        k[0], k[1], s_off, s_on, 100 * (s_on / s_off - 1), p["fires"], ph[0]["compiled"], p["certified"], chk,
        100 * chk / s_on, fall, 100 * fall / s_on, 100 * part["compile"], 100 * part["search"],
        100 * part["evaluation"], 100 * part["guards"], 100 * moves, timers))
print()
for r in rows:
    if r["arm"] == "cprof":
        t = r["cprof_total"]
        print("cprof %s %s: witness.py own %.0f%%, fractions.py %.0f%%, builtins %.0f%%, engine.py %.1f%%, other %.1f%%; top: %s" % (
            r["wl"], r["mode"], *(100 * r["cprof_by_file"].get(f, 0) / t for f in ("witness.py", "fractions.py", "builtins", "engine.py")),
            100 * (t - sum(r["cprof_by_file"].get(f, 0) for f in ("witness.py", "fractions.py", "builtins", "engine.py"))) / t,
            ", ".join("%s %.0f%%" % (a.split(":", 1)[1], 100 * b / t) for a, b in list(r["cprof_top"].items())[:6])))
ds = {(r["wl"], r["digest"]) for r in rows}
print("digests:", sorted(ds), "so:", sorted({r["so"] for r in rows if r["so"]}))
print("spread of s, plain arm (iqr / median):", {"%s %s" % k: "%.1f%%" % (100 * (lambda v: (statistics.quantiles(v, n=4)[2] - statistics.quantiles(v, n=4)[0]) / med(v))([r["s"] for r in rows if key(r) == k and r["arm"] == "plain"])) for k in sorted({key(r) for r in rows})})
