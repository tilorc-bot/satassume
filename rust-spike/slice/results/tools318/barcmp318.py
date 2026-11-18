# barcmp318.py NEW_BAR OLD_BAR: compares two bars' sum.txt plant tables and suite rows by id. Read-only.
import sys, glob, json, os, re, collections
NEW, OLD = sys.argv[1], sys.argv[2]
def plants(b):
    rows = {}; sec = None
    for line in open(os.path.join(b, 'sum.txt')):
        if line.startswith('== '): sec = line
        if line.startswith('| ') and sec:
            c = [x.strip() for x in line.strip().strip('|').split('|')]
            if len(c) >= 4 and c[0] not in ('plant', '---'):
                rows[(sec.split('(')[0].strip(), c[0], c[1])] = (c[2], c[3])
    return rows
pn, po = plants(NEW), plants(OLD)
print('plant table rows new', len(pn), 'old', len(po), 'only new', sorted(set(pn) - set(po))[:5], 'only old', sorted(set(po) - set(pn))[:5])
d = [(k, po[k], pn[k]) for k in sorted(set(pn) & set(po)) if pn[k] != po[k]]
print('plant rows whose (fired, verdict) differ:', len(d))
for x in d[:40]: print('  ', x)
vd = [x for x in d if x[1][1] != x[2][1]]
print('plant rows whose verdict differs:', len(vd))
print('verdicts new:', collections.Counter(v[1] for v in pn.values()), 'old:', collections.Counter(v[1] for v in po.values()))
def ids(b):
    out = {}
    for dd in sorted(glob.glob(os.path.join(b, 'suite*'))):
        if not os.path.isdir(dd): continue
        r = {}
        for p in glob.glob(os.path.join(dd, 'rows.*.jsonl')):
            for line in open(p):
                j = json.loads(line); r[j['id']] = j.get('outcome')
        out[os.path.basename(dd)] = r
    return out
sn, so = ids(NEW), ids(OLD)
print('suite rows new', len(sn), 'old', len(so), 'only new', sorted(set(sn) - set(so)), 'only old', sorted(set(so) - set(sn)))
PH = 'tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence'
for k in sorted(set(sn) & set(so)):
    a, b = sn[k], so[k]
    diff = sorted(i for i in set(a) | set(b) if a.get(i) != b.get(i))
    cn = collections.Counter(a.values()); co = collections.Counter(b.values())
    vs_plain = sum(1 for i in a if a[i] != sn['suite'].get(i))
    print(f"{k}: ids {len(a)}/{len(b)} failed {cn['failed']}/{co['failed']} passed {cn['passed']}/{co['passed']} | ids differing from old row {len(diff)} | changed vs this bar's plain {vs_plain} | planted-history new {a.get(PH)} old {b.get(PH)}")
    for i in diff[:6]:
        if i != PH: print('     ', i, b.get(i), '->', a.get(i))
