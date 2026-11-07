import glob, json, os, sys
R = sys.argv[1]
for p in sorted(glob.glob(R + '/*.py.json')):
    c = os.path.basename(p)[:-8]
    d = {}
    for m in ('py', 'off', 'on'):
        try:
            d[m] = json.load(open(f'{R}/{c}.{m}.json'))
        except Exception as e:
            d[m] = dict(log=[], err=open(f'{R}/{c}.{m}.err').read()[-200:])
    print(f'## {c}')
    for m in d:
        if 'err' in d[m]:
            print(' ', m, 'FAILED', d[m]['err'].replace('\n', ' ')[-180:])
    for i, r in enumerate(d['on']['log'] or d['py']['log']):
        if 'answer' not in r:
            print('  ', r)
            continue
        a = [d[m]['log'][i]['answer'] if i < len(d[m]['log']) else '?' for m in ('py', 'off', 'on')]
        k = r.get('cache', {})
        flag = '' if a[0] == a[1] == a[2] else '   <<< DIFFER'
        print(f"  {r['label']:12} py={a[0][:50]!r} off={a[1][:50]!r} on={a[2][:50]!r} epoch={r['epoch']} hit={k.get('hit')} miss={k.get('miss')} clear={k.get('epoch_clear')}{flag}")
    print('  on:', d['on'].get('term'), 'refusals', str(d['on'].get('refusals'))[:200])
    print('  off:', d['off'].get('term'), 'refusals', str(d['off'].get('refusals'))[:200])
