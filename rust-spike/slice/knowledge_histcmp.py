"""knowledge_histcmp.py DIR: read history runs from knowledge_fresh, `{wl}-{mode}-{run}.tsv`, run `s0`, `s1`, `s2` (hash seeds, recorded order), `shuf1`, `shuf2` (seed 0).

Row one: atoms against plain on the same query, seed and order, by answer, session count and digests; any difference gets its query.
Row two: each mode against its own `s0`, by answer and by digest. History may move Python; the check is that Rust moves on exactly the same queries, so both sets are named when they differ."""
import collections
import glob
import os
import sys


def read(path):
    rows, end = {}, False
    for line in open(path):
        if line.startswith('END'):
            end = True
            continue
        i, r, n, d = line.rstrip('\n').split('\t')
        rows[int(i)] = (r, n, d)
    return rows, end


def main(d):
    by = collections.defaultdict(dict)
    for f in sorted(glob.glob(os.path.join(d, '*.tsv'))):
        wl, mode, run = os.path.basename(f)[:-4].split('-')
        by[wl].setdefault(run, {})[mode] = read(f)
    for wl, runs in by.items():
        print(f'## {wl}')
        for run, ms in sorted(runs.items()):
            if set(ms) != {'plain', 'atoms'}:
                print(run, 'one mode only', sorted(ms))
                continue
            (p, pe), (a, ae) = ms['plain'], ms['atoms']
            common = sorted(set(p) & set(a))
            diff = [i for i in common if p[i] != a[i]]
            ans = [i for i in common if p[i][0] != a[i][0]]
            print(f'{run}: finished plain {pe} atoms {ae}; {len(common)} compared; atoms vs plain differ {len(diff)}, answers {len(ans)}', 'first', diff[:5])
        if 's0' not in runs or set(runs['s0']) != {'plain', 'atoms'}:
            continue
        for run, ms in sorted(runs.items()):
            if run == 's0' or set(ms) != {'plain', 'atoms'}:
                continue
            moved = {}
            for mode in ('plain', 'atoms'):
                base, cur = runs['s0'][mode][0], ms[mode][0]
                common = set(base) & set(cur)
                moved[mode] = ({i for i in common if base[i][0] != cur[i][0]}, {i for i in common if base[i] != cur[i]})
            pa, pd = moved['plain']
            aa, ad = moved['atoms']
            print(f'{run} vs s0: plain moved answers {len(pa)} state {len(pd)}; atoms moved answers {len(aa)} state {len(ad)}; '
                  f'only plain {sorted(pd - ad)[:5]} only atoms {sorted(ad - pd)[:5]}')


main(sys.argv[1])
