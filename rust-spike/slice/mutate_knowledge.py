"""Planted bugs for component 6's atoms family, each built in a scratch copy, scored by three columns that run separately.

    mutate_knowledge.py WORK PLAIN_DIR [--only NAME,NAME] [--jobs J]

PLAIN_DIR holds dev-plain.tsv and fuzz-plain.tsv from the same tree. Each column reports `cmp` (a comparison saw it), `crash` (it
only died, which includes KnowledgeFault), or `no`:
  direct  knowledge_units_cmp over generated fact lists; sees only Rules::units, so row and table bugs can't show here.
  shadow  knowledge_fresh dev --mode shadow; a field mismatch, or an answer or digest off plain.
  off     knowledge_fresh dev and fuzz --mode atoms against plain, byte for byte: answers and session digests only, the real mode.
`off` is what a user's run would see; a bug only `shadow` catches changed a field and no answer. Each row records which build
loaded: a column from another build is void. The base row must read `no` in all three. WORK/results.jsonl as each ends.
"""
import argparse
import concurrent.futures as cf
import filecmp
import json
import os
import shutil
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
KN, PY, TAB, CONV, LIVE = ('solver_rs/src/term/knowledge.rs', 'solver_rs/src/term/py.rs', 'solver_rs/src/term/table.rs',
                           'convert.py', 'knowledge_live.py')
M = [
    ('rules', 'closure-sign-swap', KN, 'sw |= if free & EVEN != 0 { free << 1 } else { free >> 1 };', 'sw |= if free & EVEN != 0 { free >> 1 } else { free << 1 };'),
    ('rules', 'closure-conflict-ignored', KN, 'if free == 0 {\n                    return None;', 'if free == 0 {\n                    continue;'),
    ('rules', 'closure-start-conflict-ignored', KN, 'if a & sw != 0 {\n            return None;', 'if a & sw != 0 {\n            return Some(a);'),
    ('rules', 'expand-no-clause-dedupe', KN, 'if seen.contains(&key) {\n                continue;\n            }', ''),
    ('rules', 'expand-no-literal-dedupe', KN, 'if !c.contains(&b) {', 'if true {'),
    ('rules', 'expand-pos-neg-swap', KN, 'let table = if pos { &self.cnf_pos } else { &self.cnf_neg };', 'let table = if pos { &self.cnf_neg } else { &self.cnf_pos };'),
    ('rules', 'sorted-lits-reversed', KN, 'for i in 0..self.basis.len() {\n            if m & (1u64 << (2 * i)) != 0 {', 'for i in (0..self.basis.len()).rev() {\n            if m & (1u64 << (2 * i)) != 0 {'),
    ('rules', 'sorted-lits-sign', KN, 'out.push(signed(i, true));', 'out.push(signed(i, false));'),
    ('rules', 'complete-no-rule-free', KN, 'let mut decided = self.rule_free;', 'let mut decided = 0u64;'),
    ('rules', 'complete-always', KN, 'decided.count_ones() as usize == self.basis.len()', 'decided.count_ones() as usize != usize::MAX'),
    ('rules', 'complete-never', KN, 'decided.count_ones() as usize == self.basis.len()', 'decided.count_ones() as usize == usize::MAX'),
    ('rules', 'unsubsumed-not-stable', KN, 'distinct.sort_by_key(Vec::len);', 'distinct.reverse(); distinct.sort_by_key(Vec::len);'),
    ('rules', 'unsubsumed-keeps-subsumed', KN, 'if !out.iter().any(|d| d.iter().all(|l| c.contains(l))) {', 'if true {'),
    ('rules', 'unsubsumed-keeps-duplicates', KN, 'if !distinct.contains(&c) {', 'if true {'),
    ('rules', 'rest-no-false-filter', KN, '.filter(|&(i, p)| units & 1u64 << lit_bit(signed(i, !p)) == 0)', '.filter(|_| true)'),
    ('rules', 'rest-no-new-unit', KN, 'if cl.len() == 1 && closed.is_some() {', 'if false {'),
    ('rules', 'rest-unit-after-conflict', KN, 'if cl.len() == 1 && closed.is_some() {', 'if cl.len() == 1 {'),
    ('rules', 'rest-no-satisfied-drop', KN, 'if cl.iter().any(|&(i, p)| units & 1u64 << lit_bit(signed(i, p)) != 0) {\n                        continue;\n                    }', ''),
    ('boundary', 'in-vocab-keeps-commutative', PY, 'k.in_vocab(name) && name != "commutative"', 'k.in_vocab(name)'),
    ('boundary', 'in-vocab-drops-all', KN, 'self.vocab.iter().any(|v| v == pred)', 'false'),
    ('boundary', 'const-basis-offset', PY, 'k.const_basis.iter().zip(values)', 'k.const_basis.iter().skip(1).zip(values)'),
    ('boundary', 'atom-row-wrong-id', PY, '.symbol_facts(TermId(t))', '.symbol_facts(TermId(t + 1))'),
    ('boundary', 'used-always', PY, 'let used = p.clauses.iter().any(|c| !c.is_empty());', 'let used = true;'),
    ('boundary', 'used-the-old-bug', PY, 'let used = p.clauses.iter().any(|c| !c.is_empty());', 'let used = !p.clauses.is_empty();'),
    ('boundary', 'pattern-rule-sign', PY, '(0, k.basis[i].as_str(), pos)', '(0, k.basis[i].as_str(), !pos)'),
    ('boundary', 'pattern-internal-sign', PY, '(0, 2 * i + n as usize)', '(0, 2 * i + !n as usize)'),
    ('boundary', 'pattern-complete-dropped', PY, '(rules, clauses, used, p.complete)', '(rules, clauses, used, false)'),
    ('boundary', 'conv-const-reversed', CONV, 'tuple(const_value(t, p) for p in _CONST_BASIS)', 'tuple(const_value(t, p) for p in reversed(_CONST_BASIS))'),
    ('boundary', 'conv-no-constant-rows', CONV, 'return tuple(const_value(t, p) for p in _CONST_BASIS)', 'return ()'),
    ('boundary', 'conv-no-symbol-rows', CONV, 'return tuple(t.assumptions0.items())', 'return ()'),
    ('boundary', 'conv-symbol-facts-sorted', CONV, 'tuple(t.assumptions0.items())', 'tuple(sorted(t.assumptions0.items()))'),
    ('wiring', 'live-any-class-row', LIVE, 'if i is not None and type(q.objects[i]) is type(expr):', 'if i is not None:'),
    ('wiring', 'live-all-derived', LIVE, 'if i is not None and type(q.objects[i]) is type(expr):', 'if False:'),
    ('wiring', 'live-derived-keeps-commutative', LIVE, "if f in VOCAB and v is not None and f != 'commutative']", "if f in VOCAB and v is not None]"),
    ('wiring', 'live-stack-not-popped', LIVE, 'finally:\n            stack.pop()', 'finally:\n            pass'),
    ('wiring', 'live-fault-quiet', LIVE, 'class KnowledgeFault(BaseException):', 'class KnowledgeFault(Exception):'),
]
LOCK = threading.Lock()
W = os.path.expanduser('~/sa-rust-ids-work')
PYTHON = f'{W}/venv/bin/python'


def run(cmd, env, cwd, log, timeout=2400):
    with open(log, 'a') as f:
        f.write(f'$ {cmd}\n')
        f.flush()
        try:
            return subprocess.run(cmd, env=env, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            return 'timeout'


def fresh(d, env, log, wl, mode):
    out = os.path.join(d, f'{wl}-{mode}.tsv')
    return run([PYTHON, os.path.join(d, 'knowledge_fresh.py'), wl, out, '--mode', mode], env, d, log), out


def score(name, kind, path, old, new, a):
    # lib.rs reaches lra.rs by a relative #[path], which from a copied crate lands beside the scratch dirs.
    lra = os.path.join(a.work, 'lra')
    with LOCK:
        if not os.path.lexists(lra):
            os.symlink(os.path.abspath(os.path.join(HERE, '..', 'lra')), lra)
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
    env['PYTHONPATH'] = f'{root}:{W}/sympy:{W}/shim:{d}'
    if path and path.startswith('solver_rs'):
        env['CARGO_TARGET_DIR'] = os.path.join(a.work, 'target-' + threading.current_thread().name)
        env['PYO3_PYTHON'] = PYTHON
        if run(['cargo', 'build', '--release'], env, os.path.join(d, 'solver_rs'), log):
            row['outcome'] = 'did not build'
            return row
        shutil.copy(os.path.join(env['CARGO_TARGET_DIR'], 'release', 'libsa_solver.so'), os.path.join(d, 'sa_solver.so'))
    else:
        shutil.copy(os.path.join(HERE, 'sa_solver.so'), d)
    so = subprocess.run([PYTHON, '-c', 'import sa_solver, convert; print(sa_solver.__file__, convert.__file__)'], env=env, cwd=d,
                        capture_output=True, text=True).stdout.split()
    row['loaded_here'] = bool(so) and all(os.path.dirname(x) == d for x in so)
    # direct
    txt = os.path.join(d, 'direct.txt')
    with open(txt, 'w') as f:
        rc = subprocess.run([PYTHON, os.path.join(d, 'knowledge_units_cmp.py'), '--random', '20000'], env=env, cwd=d, stdout=f, stderr=subprocess.STDOUT).returncode
    body = open(txt).read()
    row['direct'] = 'crash' if rc else 'cmp' if 'DIFFS' in body else 'no'
    # shadow
    rc, out = fresh(d, env, log, 'dev', 'shadow')
    if rc:
        row['shadow'] = 'crash'
    else:
        c = json.load(open(out + '.counts.json'))['counts']
        row['shadow_mismatch'] = c.get('shadow:mismatch', 0)
        row['shadow'] = 'cmp' if c.get('shadow:mismatch') or not filecmp.cmp(out, os.path.join(a.plain, 'dev-plain.tsv'), False) else 'no'
    # off
    row['off'] = 'no'
    for wl in ('dev', 'fuzz'):
        rc, out = fresh(d, env, log, wl, 'atoms')
        if rc:
            row['off'] = 'crash'
            break
        if not filecmp.cmp(out, os.path.join(a.plain, f'{wl}-plain.tsv'), False):
            ls = open(out).read().splitlines()
            ps = open(os.path.join(a.plain, f'{wl}-plain.tsv')).read().splitlines()
            row['off'] = 'cmp'
            row['off_lines'] = sum(x != y for x, y in zip(ls, ps)) + abs(len(ls) - len(ps))
            row['off_answers'] = sum(x.split('\t')[1:2] != y.split('\t')[1:2] for x, y in zip(ls, ps))
            row['off_wl'] = wl
            break
    row['outcome'] = 'scored'
    for f in os.listdir(d):
        if f.endswith('.tsv'):
            os.remove(os.path.join(d, f))
    shutil.rmtree(os.path.join(d, 'solver_rs'), ignore_errors=True)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('work')
    ap.add_argument('plain')
    ap.add_argument('--only')
    ap.add_argument('--jobs', type=int, default=3)
    a = ap.parse_args()
    a.work, a.plain = os.path.abspath(a.work), os.path.abspath(a.plain)
    os.makedirs(a.work, exist_ok=True)
    only = set(a.only.split(',')) if a.only else None
    results = os.path.join(a.work, 'results.jsonl')

    def one(m):
        kind, name, path, old, new = m
        r = score(name, kind, path, old, new, a)
        with LOCK:
            with open(results, 'a') as f:
                f.write(json.dumps(r) + '\n')
        return r
    if not only or 'base' in only:
        one(('base', 'base', None, None, None))
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        list(ex.map(one, [m for m in M if not only or m[1] in only]))
    with open(results + '.done', 'w') as f:
        f.write('done\n')


if __name__ == '__main__':
    sys.exit(main())
