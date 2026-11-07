"""join_summary.py WORK: what join_log.py wrote, by shape, by test and by worker. Prints a summary only."""
import collections
import glob
import json
import os
import sys

work = sys.argv[1]
rows = [json.loads(l) for p in glob.glob(os.path.join(work, 'joins.*.jsonl')) for l in open(p)]
print('joins', len(rows), 'tests', len({r['test'] for r in rows}), 'workers', len({r['worker'] for r in rows}))
shape = collections.Counter()
other = []
for r in rows:
    a, b = r['first'], r['second']
    s = (a['meta'], b['meta'], a['name'] == b['name'], a['kwargs'] == b['kwargs'], r['same_text'], r['hash_eq'])
    shape[s] += 1
    if a['meta'] != 'UndefinedFunction' or b['meta'] != 'UndefinedFunction' or not r['same_text']:
        other.append(r)
print('shape (meta first, meta second, same name, same kwargs, same text, same hash): count')
for s, n in shape.most_common():
    print(' ', s, n)
print('not f(x) over two UndefinedFunction classes:', len(other))
for r in other[:20]:
    print('  ', r['test'], r['first']['name'], r['first_text'], '|', r['second']['name'], r['second_text'])
print('distinct (session, node):', len({(r['worker'], r['session'], r['nid']) for r in rows}))
print('distinct text:', collections.Counter(r['first_text'] for r in rows).most_common(12))
print('per test:')
for t, n in collections.Counter(r['test'] for r in rows).most_common():
    print(f'  {n:6d} {t}')
