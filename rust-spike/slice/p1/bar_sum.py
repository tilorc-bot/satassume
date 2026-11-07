"""bar_sum.py OUT BASE: the landing bar's numbers from bar.sh's output directory, against BASE's suite rows.
Prints numbers and lists only. It never says pass or fail: the worker reads and states each bar item."""
import collections, glob, json, os, re, sys

B, BASE = sys.argv[1], sys.argv[2]
PHASES = ['build', 'tests', 'suite', 'live', 'plants', 'seed1', 'suiteplants']


def cat(p, n=None):
    try:
        lines = open(p).read().splitlines()
    except OSError:
        return None
    return lines if n is None else lines[-n:]


def rows(d):
    out = {}
    for p in glob.glob(os.path.join(d, 'rows.*.jsonl')):
        for line in open(p):
            r = json.loads(line)
            out[r['id']] = r
    return out


def handlers(d):
    c = collections.Counter()
    for p in glob.glob(os.path.join(d, 'handlers.*.jsonl')):
        for line in open(p):
            h = json.loads(line)
            c[(h.get('where'), h.get('site'), h.get('type'), re.sub(r'0x[0-9a-f]+', '0x', str(h.get('text'))))] += 1
    return c


def caught(r):
    return sorted(json.dumps(x, sort_keys=True) for x in (r.get('caught') or []))


ran = {l.split()[0] for l in (cat(os.path.join(B, 'phases.txt')) or [])}
print('tested source:', (cat(os.path.join(B, 'source.txt')) or ['?'])[0])
print('rows:', B, '| base rows:', BASE)
print('build:', ' | '.join(cat(os.path.join(B, 'build.txt')) or ['not run']))
print('phases run:', ' '.join(p for p in PHASES if p in ran) or 'none', '| not run:', ' '.join(p for p in PHASES if p not in ran) or 'none')
print('config:', ' | '.join(cat(os.path.join(B, 'config.txt')) or []))

print('\n== tests (last lines)')
for f in ('tests.txt', 'direct.txt'):
    for l in cat(os.path.join(B, f), 3) or ['not run']:
        print(f'{f}: {l}')


def suite_numbers(d, base_rows, base_h, label):
    R = rows(d)
    if not R:
        print(f'{label}: no rows')
        return R
    print(f'{label}: exit {(cat(os.path.join(d, "exit.txt")) or ["?"])[0]}')
    print('  tree:', (cat(os.path.join(d, 'tree.txt')) or ['?'])[0])
    print('  outcomes:', dict(collections.Counter(r['outcome'] for r in R.values())), 'ids', len(R))
    new = sorted(set(R) - set(base_rows)); gone = sorted(set(base_rows) - set(R))
    changed = sorted(i for i in set(R) & set(base_rows) if R[i]['outcome'] != base_rows[i]['outcome'])
    print(f'  against base: new {len(new)}, gone {len(gone)}, changed outcome {len(changed)}')
    for i in new[:20]:
        print('    new', i, R[i]['outcome'])
    for i in gone[:20]:
        print('    gone', i, base_rows[i]['outcome'])
    for i in changed[:40]:
        print('    changed', i, base_rows[i]['outcome'], '->', R[i]['outcome'])
    h = handlers(d)
    fired_ids = {k[0] for k in h}
    passed = [i for i, r in R.items() if r['outcome'] == 'passed']
    pf = sorted(i for i in passed if i in fired_ids)
    print(f'  passed {len(passed)}: with no handler firing {len(passed) - len(pf)}, with a firing {len(pf)}')
    for i in pf:
        print('    passed with firing', i)
    print(f'  handler rows {sum(h.values())} in {len(fired_ids)} tests; multiset same as base: {h == base_h}')
    for k, v in sorted(h.items(), key=str):
        b = base_h.get(k, 0)
        print(f'    {v:5d} (base {b:5d})  {k[0]} | {k[1]} | {k[2]} | {k[3][:100]}')
    for k, v in sorted(base_h.items(), key=str):
        if k not in h:
            print(f'    {0:5d} (base {v:5d})  {k[0]} | {k[1]} | {k[2]} | {k[3][:100]}')
    cd = sorted(i for i in set(R) & set(base_rows) if caught(R[i]) != caught(base_rows[i]))
    print(f'  ids whose caught rows differ from base: {len(cd)}', cd[:10])
    log = os.path.join(d, 'pytest.log')
    if os.path.exists(log):
        print('  TermFault in pytest.log:', open(log, errors='replace').read().count('TermFault'))
    return R


print('\n== suite (bar 1 and 4)')
base_rows, base_h = rows(BASE), handlers(BASE)
print('base:', BASE, 'ids', len(base_rows), 'handler rows', sum(base_h.values()))
plain = suite_numbers(os.path.join(B, 'suite'), base_rows, base_h, 'suite')

print('\n== live (bar 2)')
L = os.path.join(B, 'live')
for l in cat(os.path.join(L, 'summary.txt')) or ['not run']:
    if l.startswith('==') or l.startswith('answers_sha') or l in ('MATCH', 'DIFFER') or l.startswith('{'):
        print(' ', l[:240])
hz = []
for p in sorted(glob.glob(os.path.join(L, '*.handlers'))):
    n = len(cat(p) or [])
    if n or not os.path.basename(p).startswith('plant-'):
        print('  handler file', os.path.basename(p), 'rows', n)
    else:
        hz.append(p)
print(f'  plant handler files with 0 rows: {len(hz)}')
for p in sorted(glob.glob(os.path.join(L, 'seedx-*.cmp'))):
    print('  ', os.path.basename(p), ' | '.join((cat(p, 2) or [])))

print('\n== plants (bar 3), each against this run\'s Python; fired = max(plant_fired, rel:plant_fired)')
print('| plant | wl | fired | verdict | first |')
for p in sorted(glob.glob(os.path.join(L, 'plant-*.cmp'))):
    m = re.match(r'plant-(dev|fuzz)-(.*)\.cmp$', os.path.basename(p))
    wl, pl = m.groups()
    try:
        d = json.load(open(p[:-4] + '.session.json'))
        f = max(d.get('plant_fired', 0), d.get('counts', {}).get('rel:plant_fired', 0))
    except (OSError, ValueError):
        f = '?'
    lines = cat(p) or []
    first = next((l for l in lines if l.startswith('first:')), '')[:120]
    print(f'| {pl} | {wl} | {f} | {lines[-1] if lines else "?"} | {first} |')

print('\n== suite plants, against this run\'s plain suite')
for d in sorted(glob.glob(os.path.join(B, 'suite-*/'))):
    print(os.path.basename(d.rstrip('/')))
    suite_numbers(d, plain, handlers(os.path.join(B, 'suite')), '  ' + os.path.basename(d.rstrip('/')))
    fired, errs, nfiles = 0, [], 0
    for f in glob.glob(os.path.join(d, 'counts.*.json')):
        nfiles += 1
        c = json.load(open(f))
        fired += c.get('rel:plant_fired', 0)
        if 'error' in c:
            errs.append(c['error'])
    print(f'  plant fired in the suite: {fired if nfiles else "not recorded (no counts files)"} ({nfiles} files){" errors: " + str(errs[:2]) if errs else ""}')
