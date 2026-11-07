"""Planted bugs for components D and 0, each built in a scratch copy and scored by the shadow on real queries.

    mutate_term.py WORK [--only NAME,NAME] [--jobs J] [--wl dev] [--limit N] [--synthetic]

`alg` and `order` are the algebra and key work; `boundary` is the crossing from conversion into Rust's table, both sides.
Caught: the shadow reports a mismatch, the table raises, or the process dies. `refused` means no mismatch but a refusal
the base doesn't have: safe, since the query stays on Python, and scored apart. `no`: nothing noticed. The base row must
read "no". Results as each ends: WORK/results.jsonl.
"""
import argparse
import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
ALG, TAB, RAT, CONV = 'solver_rs/src/term/algebra.rs', 'solver_rs/src/term/table.rs', 'solver_rs/src/term/rat.rs', 'convert.py'
M = [
    ('alg', 'neg-keeps-sign', ALG, 'let c = c.neg();', 'let c = c.clone();'),
    ('alg', 'free-not-deduped', ALG, 'free.dedup();', ''),
    ('alg', 'number-any-arg', ALG, 'number &= r.bits & fact::NUMBER != 0;', 'number |= r.bits & fact::NUMBER != 0;'),
    ('alg', 'float-not-inherited', ALG, 'let inherit = fact::NAN | fact::BAD | fact::FLOAT | fact::UNDEF;', 'let inherit = fact::NAN | fact::BAD | fact::UNDEF;'),
    ('alg', 'add-unsorted', ALG, 'self.sort_by_compare(&mut newseq)?;', ''),
    ('alg', 'mul-unsorted', ALG, 'self.sort_by_compare(&mut factors)?;', ''),
    ('alg', 'add-coeff-starts-1', ALG, 'let mut coeff = Rat::int(0);', 'let mut coeff = Rat::int(1);'),
    ('alg', 'mul-coeff-starts-2', ALG, 'let mut coeff = Rat::int(1);', 'let mut coeff = Rat::int(2);'),
    ('alg', 'keep-coeff-minus-one', ALG, 'if *a == Rat::int(-1) {', 'if *a == Rat::int(-2) {'),
    ('alg', 'no-merge-with-known', ALG, 'content: Arc<[V]>) -> TermId {\n        if let Some(t) = self.find(class, &content) {', 'content: Arc<[V]>) -> TermId {\n        if let Some(t) = None::<TermId> {'),
    ('order', 'key-arg-count', ALG, 'tuple(vec![int(n), tuple(ordered)])', 'tuple(vec![int(n + 1), tuple(ordered)])'),
    ('order', 'compare-length-flipped', TAB, 'let c = st.len().cmp(&ot.len());', 'let c = ot.len().cmp(&st.len());'),
    ('order', 'tuple-length-flipped', TAB, 'x.len().cmp(&y.len())', 'y.len().cmp(&x.len())'),
    ('order', 'rat-order-flipped', TAB, '(V::Rat(x), V::Rat(y)) => x.cmp(y),', '(V::Rat(x), V::Rat(y)) => y.cmp(x),'),
    ('order', 'rat-sign-not-normal', RAT, 'if d.is_negative() {', 'if false && d.is_negative() {'),
    ('boundary', 'rat-sign-on-read', TAB, 'V::Rat(Rat::new(p, q))', 'V::Rat(Rat::new(-p, q))'),
    ('boundary', 'rank-zero-lost', TAB, 'rank: (rank >= 0).then_some(rank as u32)', 'rank: (rank > 0).then_some(rank as u32)'),
    ('boundary', 'structural-flipped', TAB, 'structural: f[6] == V::Bool(true)', 'structural: f[6] == V::Bool(false)'),
    ('boundary', 'custom-content-flipped', TAB, 'custom_content: f[7] == V::Bool(true)', 'custom_content: f[7] == V::Bool(false)'),
    ('boundary', 'class-flag-bit', TAB, 'flags: int(&f[3])? as u32', 'flags: (int(&f[3])? as u32) ^ 1'),
    ('boundary', 'term-id-off-by-one', TAB, 'V::Term(TermId(self.next()? as u32))', 'V::Term(TermId((self.next()? as u32).saturating_sub(1)))'),
    ('boundary', 'closed-value-abs', TAB, 'Ok(f64::from_bits(int(v)? as u64))', 'Ok(f64::from_bits(int(v)? as u64).abs())'),
    ('boundary', 'conv-key-dropped', CONV, 'return default_sort_key(t)', 'return default_sort_key(t)[:3]'),
    ('boundary', 'conv-free-unordered', CONV, 'fid = sorted(self.term(x) for x in free)', 'fid = sorted((self.term(x) for x in free), reverse=True)'),
    ('boundary', 'conv-number-bit', CONV, "number = getattr(t, 'is_number', False) is True", "number = getattr(t, 'is_number', False) is not True"),
    ('boundary', 'conv-power-base', CONV, 'b = self.ids.get(base, -1)', 'b = -1'),
    ('boundary', 'read-memo-off', TAB, 'self.memo.lock().unwrap().insert((kind, t), v.clone());', 'if false { self.memo.lock().unwrap().insert((kind, t), v.clone()); }'),
    ('boundary', 'read-text-swapped', TAB, '(V::Text(x), V::Text(y)) => x.as_ref().cmp(y.as_ref())', '(V::Text(x), V::Text(y)) => y.as_ref().cmp(x.as_ref())'),
    ('boundary', 'conv-maybe-nan', CONV, 'if _may_be_nan(t):', 'if not _may_be_nan(t):'),
]
LOCK = threading.Lock()


def run(cmd, env, cwd, log, timeout=2400):
    with open(log, 'a') as f:
        return subprocess.run(cmd, env=env, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout).returncode


def score(name, kind, path, old, new, a):
    d = os.path.join(a.work, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    log = os.path.join(d, 'log.txt')
    for f in os.listdir(HERE):
        if f.endswith('.py') or f == 'offline_data.json':
            shutil.copy(os.path.join(HERE, f), d)
    shutil.copytree(os.path.join(HERE, 'solver_rs'), os.path.join(d, 'solver_rs'), ignore=shutil.ignore_patterns('target'))
    row = dict(name=name, kind=kind)
    if path:
        p = os.path.join(d, path)
        s = open(p).read()
        if s.count(old) != 1:
            row['outcome'] = f'plant failed: {s.count(old)} matches'
            return row
        open(p, 'w').write(s.replace(old, new))
    env = dict(os.environ)
    root = os.path.dirname(os.path.dirname(HERE))
    w = os.path.expanduser('~/sa-rust-ids-work')
    env['PYTHONPATH'] = f'{root}:{w}/sympy:{w}/shim:{d}'
    py = f'{w}/venv/bin/python'
    if path and path.startswith('solver_rs'):
        env['CARGO_TARGET_DIR'] = os.path.join(a.work, 'target-' + threading.current_thread().name)
        env['PYO3_PYTHON'] = py
        if run(['cargo', 'build', '--release'], env, os.path.join(d, 'solver_rs'), log):
            row['outcome'] = 'did not build'
            return row
        shutil.copy(os.path.join(env['CARGO_TARGET_DIR'], 'release', 'libsa_solver.so'), os.path.join(d, 'sa_solver.so'))
    else:
        shutil.copy(os.path.join(HERE, 'sa_solver.so'), d)
    out = os.path.join(d, 'shadow.json')
    cmd = [py, os.path.join(d, 'term_shadow_fresh.py'), a.wl, out]
    if a.limit:
        cmd += ['--limit', str(a.limit)]
    if a.synthetic:
        cmd += ['--synthetic']
    rc = run(cmd, env, d, log)
    if rc or not os.path.exists(out):
        row['outcome'] = f'caught: process exit {rc}'
        return row
    r = json.load(open(out))
    kinds = {}
    for b in r['bad']:
        kinds[b[0]] = kinds.get(b[0], 0) + 1
    row.update(bad=len(r['bad']), first=kinds, refused=r['refused'], kept=r['kept'])
    row['outcome'] = 'caught' if r['bad'] else 'pending'
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('work')
    ap.add_argument('--only')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--wl', default='dev')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--synthetic', action='store_true', help='also run the shadow\'s synthetic algebra loop, wider than the engine reaches')
    a = ap.parse_args()
    a.work = os.path.abspath(a.work)
    os.makedirs(a.work, exist_ok=True)
    only = set(a.only.split(',')) if a.only else None
    base = score('base', 'base', None, None, None, a)
    print('base', base['outcome'], base.get('bad'), flush=True)
    results = os.path.join(a.work, 'results.jsonl')

    def one(m):
        kind, name, path, old, new = m
        r = score(name, kind, path, old, new, a)
        if r['outcome'] == 'pending':
            r['outcome'] = 'refused' if r['refused'] != base['refused'] or r['kept'] != base['kept'] else 'no'
        with LOCK:
            with open(results, 'a') as f:
                f.write(json.dumps(r) + '\n')
            print(r['kind'], r['name'], r['outcome'], r.get('first'), flush=True)
        return r
    if base['outcome'] == 'pending' and not base['bad']:
        base['outcome'] = 'no'
    with open(results, 'a') as f:
        f.write(json.dumps(base) + '\n')
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        list(ex.map(one, [m for m in M if not only or m[1] in only]))


if __name__ == '__main__':
    sys.exit(main())
