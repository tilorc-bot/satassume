"""tab352.py OUT (sa-port-352): job352a.sh's rows as one table per workload: queries, calls of `witnesses`, certified;
arm diff's mismatches (each call run natively, then by witness.py), compiled and searched; arm native's counters: the
boundary lookups, the fallbacks to Python by reason and their share of the calls; whether the three arms' answer digests
are equal; cmp352.py's count of queries that differ (native against python)."""
import json, sys
out = sys.argv[1]
cmp_ = {l.split(" ", 1)[0]: json.loads(l.split(" ", 1)[1]) for l in open(out + "/cmp.txt")}
print("| workload | queries | calls | certified | diff: mismatches | compiled | searched | lookups | fallback miss/type/shape/off | share | digests equal | per query differ |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
tot = dict(calls=0, fb=0, mis=0, dif=0)
for wl, c in cmp_.items():
    n = wl.replace(":", "")
    d, na, py = (json.loads(open(f"{out}/{n}-{a}.json").read()) for a in ("diff", "native", "python"))
    k = na["counts"]
    fb = [k["wn:fallback:miss"], k["wn:fallback:type"], k["wn:fallback:shape"], k["wn:fallback:off"]]
    calls = d["N"]["calls"]
    assert d["N"]["fallback"] == sum(fb) and c["calls_results"][0][0] == calls, wl
    tot["calls"] += calls; tot["fb"] += sum(fb); tot["mis"] += d["mismatches"]; tot["dif"] += c["differ"]
    print(f"| {wl} | {d['n']} | {calls} | {c['certified'][0]} | {d['mismatches']} | {d['N']['compiled']} | {d['N']['searched']} | {k['wn:lookup']} | "
          f"{'/'.join(map(str, fb))} | {100 * sum(fb) / calls if calls else 0:.1f}% | {d['digest'] == na['digest'] == py['digest']} | {c['differ']} |")
print(f"\ntotals: calls {tot['calls']}, fallbacks {tot['fb']}, diff mismatches {tot['mis']}, queries that differ {tot['dif']}; "
      f".so {sorted({json.loads(open(f'{out}/{w.replace(':', '')}-native.json').read())['so'] for w in cmp_})}")
