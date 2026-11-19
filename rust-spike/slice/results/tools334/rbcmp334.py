"""rbcmp334.py BASE HEAD: rb334.sh's rows of two trees, per walker cell over the 20 workloads. Prints, per cell: rows
on each side, rows with bit 32, workloads whose masked digest differs (in order, and order-free), workloads where
HEAD's raw digest differs from its masked one, and which walker class wrote the rows."""
import json, sys
WLS = "lra f6 wiring scope dev fuzz ground port loop zero cert budget core opaque rootof value twin transfer760 transfer2340 cls".split()
b, h = sys.argv[1], sys.argv[2]
for c in ('cpy', 'crust'):
    B = {w: json.load(open(f'{b}/{c}/{w}.json')) for w in WLS}; D = {w: json.load(open(f'{h}/{c}/{w}.json')) for w in WLS}
    rows = lambda X: {k: sum(d.get(k, 0) for d in X.values()) for k in ('rows:_Walk', 'rows:_RustWalk', 'bit32', 'shape_bad', 'exit')}
    print(c, 'base', rows(B), 'so', sorted({d['so'] for d in B.values()}), '| head', rows(D), 'so', sorted({d['so'] for d in D.values()}))
    print('   bit 32 rows by workload, base:', {w: d['bit32'] for w, d in B.items() if d.get('bit32')}, 'head:', {w: d['bit32'] for w, d in D.items() if d.get('bit32')})
    print('   masked digest differs (in order):', [w for w in WLS if B[w]['masked'] != D[w]['masked']],
          '(order-free):', [w for w in WLS if B[w]['masked_sum'] != D[w]['masked_sum']])
    print('   raw digest equal base/head on:', sum(B[w]['raw'] == D[w]['raw'] for w in WLS), 'of 20; differs on:', [w for w in WLS if B[w]['raw'] != D[w]['raw']])
    print('   head raw != head masked on:', [w for w in WLS if D[w]['raw'] != D[w]['masked']])
print('cpy rows == crust rows, masked, per tree:', [all(json.load(open(f'{t}/cpy/{w}.json'))['masked'] == json.load(open(f'{t}/crust/{w}.json'))['masked'] for w in WLS) for t in (b, h)])
