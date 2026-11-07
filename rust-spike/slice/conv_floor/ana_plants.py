"""One line per plant: state rows that differ from Python's, whether answers moved, hits, refusals, faults. Usage: ana_plants.py OUTDIR REFDIR WORKLOAD"""
import collections, glob, json, os, sys
R, REF, WL = sys.argv[1:4]
py = open(f'{REF}/{WL}-py.txt').read().splitlines()
print('field class stored hits rows answers state refused converted handler_fired crash')
for p in sorted(glob.glob(f'{R}/{WL}-*.plant')):
    d = json.load(open(p)); pre = p[:-6]
    got = open(pre + '.txt').read().splitlines() if os.path.exists(pre + '.txt') else []
    rows = sum(a != b for a, b in zip(py, got)) + abs(len(py) - len(got))
    ans = sum(a.split('\t')[1] != b.split('\t')[1] for a, b in zip(py, got))
    st = sum(a.split('\t')[1] == b.split('\t')[1] and a != b for a, b in zip(py, got))
    ref = conv = '?'
    if os.path.exists(pre + '.json'):
        j = json.load(open(pre + '.json')); ref = len(j['refusals']); conv = j['term'].get('converted')
    h = 0
    if os.path.exists(pre + '.handlers'):
        h = sum(1 for _ in open(pre + '.handlers'))
    print(d['field'], d['target'], d['stored'], d['plant_hits'], rows, ans, st, ref, conv, h, d['crash'][:90] or '-')
