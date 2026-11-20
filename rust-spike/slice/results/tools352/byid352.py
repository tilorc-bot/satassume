"""byid352.py JOB_DIR (sa-port-352, issue 323): job352b.sh's rows read. The suite by test id (rust_plugin's rows: outcome
and the recorded state rust_made, py_made, session, lra, private_writes, caught) nat against wit, off against base and
nat against off; the native counters per cell from wn_seen (a cell that should run witness.rs shows compiles, the
others show none); the planted-history test's outcome per cell. Then iv: per run name the failing ids (-rf) and the
exit line, nat against wit, and the counters summed per switch."""
import glob, json, os, re, sys
from collections import Counter
job = sys.argv[1]
PH = "tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence"
KEYS = ("rust_made", "py_made", "session", "lra", "private_writes", "caught")


def wn(d):
    c, hook = Counter(), set()
    for f in glob.glob(d + "/wn.*.json"):
        r = json.load(open(f))
        c.update(r["counts"] or {})
        hook.add(r["hook"])
    return dict(c), sorted(hook)


def load(arm):
    rows = {}
    for f in glob.glob(f"{job}/suite-{arm}-rust/rows.*.jsonl"):
        for l in open(f):
            r = json.loads(l)
            rows[r["id"]] = r
    return rows


arms = {a: load(a) for a in ("nat", "wit", "off", "base")}
for a, rows in arms.items():
    d = f"{job}/suite-{a}-rust"
    print(f"suite {a}: {len(rows)} ids {dict(Counter(r['outcome'] for r in rows.values()))}; quiet catches "
          f"{sum(len(r.get('caught') or []) for r in rows.values())}; planted-history {rows.get(PH, {}).get('outcome')}; "
          f"exit {open(d + '/exit.txt').read().strip()[:80]}; wn {wn(d)}; tree {open(d + '/tree.txt').read().split()[0]}")
for a, b in (("nat", "wit"), ("off", "base"), ("nat", "off")):
    ra, rb = arms[a], arms[b]
    only = sorted(set(ra) ^ set(rb))
    diff = sorted(i for i in set(ra) & set(rb) if ra[i]["outcome"] != rb[i]["outcome"])
    state = Counter(k for i in set(ra) & set(rb) for k in KEYS if ra[i].get(k) != rb[i].get(k))
    print(f"  {a} against {b}: ids in one only {len(only)} {only[:4]}; outcome differs {len(diff)}; recorded state differs, ids by field {dict(state)}")
    for i in diff:
        f = ra[i].get("failure") or rb[i].get("failure") or ""
        print(f"    {i}: {a} {ra[i]['outcome']}, {b} {rb[i]['outcome']}: {str(f).strip().splitlines()[-1][:200] if f else ''}")
iv = job + "/iv"


def fails(d):
    log = open(d + "/pytest.log", errors="replace").read()
    return sorted(set(re.findall(r"^FAILED (\S+)", log, re.M))), open(d + "/exit.txt").read().strip()


names = sorted(os.path.basename(d)[:-4] for d in glob.glob(iv + "/*-wit"))
moved, seen, exits, cnt = 0, Counter(), Counter(), {"wit": Counter(), "nat": Counter()}
for n in names:
    (fo, eo), (fn, en) = fails(f"{iv}/{n}-wit"), fails(f"{iv}/{n}-nat")
    be = n.split("-")[1]
    for sw, f, e in (("wit", fo, eo), ("nat", fn, en)):
        exits[(be, sw, e.split()[0])] += 1
        cnt[sw].update({k: v for k, v in wn(f"{iv}/{n}-{sw}")[0].items()})
        for i in f:
            seen[(be, sw, i)] += 1
    if fo != fn or eo.split()[1:] != en.split()[1:] and re.sub(r"in [\d.]+s.*", "", eo) != re.sub(r"in [\d.]+s.*", "", en):
        moved += 1
        print(f"MOVED {n}: wit only {sorted(set(fo) - set(fn))}; nat only {sorted(set(fn) - set(fo))}; {eo} | {en}")
print(f"iv runs {len(names)} wit + {len(names)} nat; runs whose failing ids or pass/fail counts differ: {moved}")
print("iv exit codes (backend, switch, rc): runs", dict(sorted(exits.items())))
print("iv native counters summed, wit:", dict(cnt["wit"]), "nat:", dict(cnt["nat"]))
for (be, sw, i), c in sorted(seen.items()):
    print(f"  {be} {sw} {i}: fails in {c} runs")
