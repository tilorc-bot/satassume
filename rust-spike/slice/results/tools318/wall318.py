# wall318.py BAR: phase and row wall times from phases.txt and commands.txt, and the kept-reasons equality.
import sys, re, os, datetime as dt
B = sys.argv[1]
def t(s): return dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ')
def f(d):
    s = int(d.total_seconds()); return f"{s//3600} h {s%3600//60:02d} m {s%60:02d} s" if s >= 3600 else f"{s//60} m {s%60:02d} s"
cmds = []
for line in open(os.path.join(B, 'commands.txt')):
    m = re.match(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) (.*)', line)
    if m: cmds.append((t(m.group(1)), m.group(2)))
start = cmds[0][0]; print('first command', start, 'last', cmds[-1][0])
prev = start
ph = {}
for line in open(os.path.join(B, 'phases.txt')):
    n, ts = line.split()[:2]; ph[n] = (prev, t(ts)); print(f"phase {n}: {f(t(ts) - prev)} (ends {ts})"); prev = t(ts)
print('total', f(prev - start))
# suite rows: the rm -rf command of each suite dir starts it; the next rm -rf (or the phase end) ends it
rows = [(ts, re.search(r'bar/(suite[^;\s]*);', c).group(1)) for ts, c in cmds if c.startswith('rm -rf') and re.search(r'bar/suite[^;\s]*;', c)]
ends = [r[0] for r in rows[1:]]
out = {}
for i, (ts, n) in enumerate(rows):
    if n == 'suite': e = ph['suite'][1]
    elif i + 1 < len(rows): e = rows[i + 1][0]
    else: e = ph['suiteplants'][1]
    out[n] = e - ts
for n, d in sorted(out.items(), key=lambda x: x[1]): print(f"  {n}: {f(d)}")
grp = lambda p: sum((d for n, d in out.items() if p(n)), dt.timedelta())
print('frames:rust + six tl-*:', f(grp(lambda n: n == 'suite-frames:rust' or n.startswith('suite-term:tl-'))))
print('five convert:*:', f(grp(lambda n: n.startswith('suite-convert:'))))
# extra workloads: the first command naming extra/WL-py.jsonl starts a workload
ex = []
for ts, c in cmds:
    m = re.search(r'extra/([^ /]+?)-py\.jsonl --check', c)
    if m and c.lstrip().startswith('('): ex.append((ts, m.group(1)))
for i, (ts, n) in enumerate(ex):
    e = ex[i + 1][0] if i + 1 < len(ex) else ph['extra'][1]
    ex[i] = (e - ts, n)
print('extra workloads, longest:', '; '.join(f"{n} {f(d)}" for d, n in sorted(ex, reverse=True)[:4]), '| count', len(ex))
bad = 0; nk = 0; sec = False
for line in open(os.path.join(B, 'sum.txt')):
    if line.startswith('== kept reasons'): sec = True; continue
    if sec and ' vs ' in line:
        for part in line.strip().split('; '):
            nk += 1
            a, b = part.split(' vs ')
            a = a.split(' ', 1)[1] if ':' in a.split(' ')[0] and a.split(' ')[0].endswith(':') else a
            if not a.endswith(b): bad += 1; print('  kept differs:', part[:200])
print('kept-reason entries', nk, 'differing from base', bad)
