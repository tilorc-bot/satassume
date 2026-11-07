"""Slice B's counts, joined over `SLICE_TERM_COUNTS` files or the suite's `term.PID.json`: term_ids_counts.py FILE..."""
import collections
import json
import sys

tot = collections.Counter()
lists = collections.defaultdict(list)
for p in sys.argv[1:]:
    d = json.load(open(p))
    tot.update(d['counts'])
    for k, v in d.items():
        if k != 'counts':
            lists[k].extend(v)
for k in sorted(tot):
    print(f'{k}\t{tot[k]}')
for k, v in lists.items():
    print(f'-- {k}: {len(v)} kept')
    for x in v[:12]:
        print('  ', str(x)[:260])
