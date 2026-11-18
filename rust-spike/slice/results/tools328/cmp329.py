"""cmp329.py JOB_DIR (sa-port-329, issue 323): the slice suite by test id, per backend: on (SLICE_WITNESS=1) and off
(=0) on the witness tree, base on the base tree. Outcomes per arm; every id whose outcome differs between two arms, with
the failure's first line; the recorded state per test (rust_plugin's rows: rust_made, py_made, session, lra,
private_writes, caught) on against off, as counts of ids per field that differs; quiet catches (`caught`) and
handler_count's rows per arm."""
import glob, json, sys
from collections import Counter
job = sys.argv[1]


def load(arm, be):
    rows = {}
    for f in glob.glob(f"{job}/suite-{arm}-{be}/rows.*.jsonl"):
        for l in open(f):
            r = json.loads(l)
            rows[r["id"]] = r
    hs = sum(1 for f in glob.glob(f"{job}/suite-{arm}-{be}/handlers.*.jsonl") for l in open(f) if l.strip())
    return rows, hs


for be in ("rust", "python"):
    arms = {a: load(a, be) for a in ("on", "off", "base")}
    for a, (rows, hs) in arms.items():
        print(f"{be} {a}: {len(rows)} ids {dict(Counter(r['outcome'] for r in rows.values()))}; quiet catches recorded "
              f"{sum(len(r.get('caught') or []) for r in rows.values())} in {sum(1 for r in rows.values() if r.get('caught'))} ids; "
              f"handler rows {hs}; exit: {open(f'{job}/suite-{a}-{be}/exit.txt').read().strip()[:90]}")
    for a, b in (("on", "off"), ("off", "base"), ("on", "base")):
        ra, rb = arms[a][0], arms[b][0]
        only = sorted(set(ra) ^ set(rb))
        diff = sorted(i for i in set(ra) & set(rb) if ra[i]["outcome"] != rb[i]["outcome"])
        print(f"  {be} {a} against {b}: ids in one only {len(only)} ({Counter(i.split('::')[0] for i in only).most_common(3)}); outcome differs: {len(diff)}")
        for i in diff:
            f = (ra[i]["failure"] or rb[i]["failure"] or "")
            print(f"    {i}: {a} {ra[i]['outcome']}, {b} {rb[i]['outcome']}: {str(f).strip().splitlines()[-1][:200] if f else ''}")
    ra, rb = arms["on"][0], arms["off"][0]
    fields = Counter()
    by_file = Counter()
    for i in set(ra) & set(rb):
        for k in ("rust_made", "py_made", "session", "lra", "private_writes", "caught"):
            if ra[i].get(k) != rb[i].get(k):
                fields[k] += 1
                by_file[i.split("::")[0]] += 1
    print(f"  {be} on against off, ids whose recorded state differs, by field: {dict(fields)}; files most affected: {by_file.most_common(6)}")
