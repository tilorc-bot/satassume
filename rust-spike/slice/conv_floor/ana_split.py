"""ana_split.py split.jsonl: medians per arm, first round dropped. Fine `row:*` rows are a breakdown of conv:term_row-total, not added to it."""
import json, statistics as st, sys
rows = [json.loads(x) for x in open(sys.argv[1])]
rows = [r for r in rows if r['round'] > 0]
med = st.median
for wl in ('dev', 'fuzz'):
    W = [r for r in rows if r['wl'] == wl]
    arm = lambda a: [r for r in W if r['arm'] == a]
    print(f'== {wl}: rounds {len(arm("plain"))}; digests {sorted({r["digest"] for r in W})}; refusals {sorted({r.get("refusals", 0) for r in W})}')
    for a in ('plain', 'coarse', 'fine', 'plain-termpy', 'termpy-wrapped'):
        s = [r['s'] for r in arm(a)]
        print(f'  {a:16s} {med(s):7.3f} s ({min(s):.3f} to {max(s):.3f})')
    p, pt = med(r['s'] for r in arm('plain')), med(r['s'] for r in arm('plain-termpy'))
    print(f'  overhead coarse {med(r["s"] for r in arm("coarse"))/p:.3f}x, fine {med(r["s"] for r in arm("fine"))/p:.3f}x, termpy-wrapped {med(r["s"] for r in arm("termpy-wrapped"))/pt:.3f}x; rust-termpy {p-pt:.3f} s')
    for a in ('coarse', 'termpy-wrapped', 'fine'):
        keys = sorted({k for r in arm(a) for k in r['T']})
        m = {k: med(r['T'].get(k, 0.0) for r in arm(a)) for k in keys}
        n = {k: arm(a)[0]['N'].get(k, 0) for k in keys}
        tot = med(r['s'] for r in arm(a))
        print(f'  -- {a} (total {tot:.3f} s)')
        conv = [k for k in keys if k.startswith(('conv:', 'table:', 'live:_convert', 'read'))]
        if a == 'coarse':
            print(f'  conversion incl. table parse, excl. reads: {sum(m[k] for k in conv if k != "read"):.3f} s; term_live other: {sum(m[k] for k in keys if k.startswith("live:") and k not in conv):.3f} s; sites: {sum(m[k] for k in keys if k.startswith("site:")):.3f} s')
        for k in sorted(keys, key=lambda k: -m[k]):
            if a == 'fine' and not k.startswith(('row:', 'conv:term_row')):
                continue
            print(f'    {k:44s}{m[k]*1000:10.1f} ms {m[k]/tot*100:5.1f}% {n[k]:9d}')
