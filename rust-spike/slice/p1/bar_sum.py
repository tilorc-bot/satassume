"""bar_sum.py OUT BASE: the landing bar's numbers from bar.sh's output directory, against BASE's suite rows.
Prints numbers and lists only. It never says pass or fail: the worker reads and states each bar item."""
import collections, glob, json, os, re, sys

B, BASE = sys.argv[1], sys.argv[2]
PHASES = ['build', 'tests', 'suite', 'live', 'plants', 'seed1', 'extra', 'suiteplants', 'fmrows']


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
X = os.path.join(B, 'extra')
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
print('\n== extra workloads (WLS; bar 2 and the gaps ruling)')
for l in cat(os.path.join(X, 'summary.txt')) or ['not run']:
    if l.startswith('==') or l.startswith('answers_sha') or l in ('MATCH', 'DIFFER') or l.startswith('{') or l == 'not run':
        print(' ', l[:240])
for p in sorted(glob.glob(os.path.join(X, '*-rust.handlers'))):
    print('  handler file', os.path.basename(p), 'rows', len(cat(p) or []))
for p in sorted(glob.glob(os.path.join(L, 'seedx-*.cmp'))):
    print('  ', os.path.basename(p), ' | '.join((cat(p, 2) or [])))

print('\n== plants (bar 3), each against this run\'s Python; fired = max(plant_fired, rel:plant_fired)')
print('| plant | wl | fired | verdict | first |')
for p in sorted(glob.glob(os.path.join(L, 'plant-*.cmp'))) + sorted(glob.glob(os.path.join(X, 'plant-*.cmp'))):
    m = re.match(r'plant-([^-]+)-(.*)\.cmp$', os.path.basename(p))
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


# Planner's kept-reasons ruling (8 Nov): the share of queries kept per reason on each workload, against base. A rise in a
# share is a finding even when answers MATCH. Counts are term_live's `kept:<reason>` and `refused[:<reason>]` rows, which the
# Rust live run writes to <wl>-rust.knowledge.json; the denominator is that run's query count (<wl>-rust.tot). The base is
# BASE's sibling live/ and extra/ (BASE is a .../suite directory), or KEPT_BASE if set.
def kept(d):
    out = {}
    for k in sorted(glob.glob(os.path.join(d, '*-rust.knowledge.json'))):
        wl = os.path.basename(k)[:-len('-rust.knowledge.json')]
        try:
            c = json.load(open(k))['counts']
            q = json.loads((cat(k.replace('.knowledge.json', '.tot')) or ['{}'])[0]).get('queries')
        except (OSError, ValueError, KeyError):
            continue
        out[wl] = (q, {r: n for r, n in c.items() if r.startswith('kept:') or r == 'refused' or r.startswith('refused:')})
    return out


print('\n== kept reasons: share of queries kept per reason, Rust run, against base')
kb = os.environ.get('KEPT_BASE') or os.path.dirname(BASE.rstrip('/'))
for sub in ('live', 'extra'):
    now, base = kept(os.path.join(B, sub)), kept(os.path.join(kb, sub))
    for wl, (q, c) in now.items():
        bq, bc = base.get(wl, (None, {}))
        reasons = sorted(set(c) | set(bc) | {'refused', 'kept:out-of-scope'})
        cells = []
        for r in reasons:
            s = f'{c.get(r, 0)}/{q} ({100 * c.get(r, 0) / q:.2f}%)' if q else f'{c.get(r, 0)}/?'
            b = f'{bc.get(r, 0)}/{bq} ({100 * bc.get(r, 0) / bq:.2f}%)' if bq else 'base not found'
            rise = ' RISE' if bq and q and c.get(r, 0) / q > bc.get(r, 0) / bq else ''
            cells.append(f'{r} {s} vs {b}{rise}')
        print(f'  {sub}/{wl}: ' + '; '.join(cells))
# fm_rows.py's exact rows: the plain run must end `exit 0`; a plant's run is caught when it ends `exit 1`
print('fm rows (fm_rows.py check; plain wants exit 0, a plant is caught on exit 1):')
for d in sorted(glob.glob(os.path.join(B, 'fmrows*'))) or [None]:
    ls = cat(os.path.join(d, 'check.txt')) if d else None
    print('  %s: %s' % (os.path.basename(d) if d else 'fmrows', ' | '.join(ls[-2:]) if ls else 'not run'))
