"""Planted bugs for component 6's atoms family, each built in a scratch copy, scored by columns that run separately.

    mutate_knowledge.py WORK PLAIN_DIR [--only NAME,NAME] [--jobs J]

PLAIN_DIR holds dev-plain.tsv and fuzz-plain.tsv from the same tree. Each column reports `cmp` (a comparison saw it), `crash` (it
only died, which includes KnowledgeFault), or `no`:
  direct  knowledge_units_cmp over generated fact lists; sees only Rules::units, so row and table bugs can't show here.
  shadow  knowledge_fresh dev --mode shadow; a field mismatch, or an answer or digest off plain.
  off     knowledge_fresh dev, fuzz and value --mode atoms against plain, byte for byte: answers and session digests only, the real mode.
          `off_by_wl` scores each workload; `off` and `off_wl` are the first that caught it.
  unit    test_knowledge_common.py, test_knowledge_realroots.py and test_knowledge_core.py against Python's.
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
RW = 'solver_rs/src/rows.rs'
RR = 'solver_rs/src/realroots.rs'
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
    ('rules', 'unsubsumed-not-stable', KN, 'if !distinct.contains(&c) {\n            distinct.push(c);\n        }\n    }\n    distinct.sort_by_key(Vec::len);', 'if !distinct.contains(&c) {\n            distinct.push(c);\n        }\n    }\n    distinct.reverse(); distinct.sort_by_key(Vec::len);'),
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
    ('realroots', 'realroots-chain-no-negate', RR, 'out.push(r.iter().map(Rat::neg).collect());', 'out.push(r);'),
    ('realroots', 'realroots-imaginary-sign', RR, 'if k % 4 < 2 {', 'if k % 4 < 1 {'),
    ('realroots', 'realroots-sign-boundary', RR, 'let sign = if *index < BigInt::from(neg) {', 'let sign = if *index <= BigInt::from(neg) {'),
    ('realroots', 'realroots-bits-off-by-one', RR, '.unwrap_or(0) > MAX_BITS', '.unwrap_or(0) >= MAX_BITS'),
    ('realroots', 'realroots-squarefree-skipped', RR, '        || !squarefree(&p)\n', ''),
    ('common', 'common-unsubsumed-keeps-subsumed', KN, 'let hit = c.iter().any(|l| index.get(l).is_some_and(|ds| ds.iter().any(|&d| is_subset(&out[d], &c))));', 'let hit = false;'),
    ('common', 'common-resolve-keeps-subsumed', KN, 'if kept.iter().any(|k| is_subset(k, &key)) {', 'if false {'),
    ('common', 'common-contrapositive-sign', KN, '(*k, p.clone(), !*pos)', '(*k, p.clone(), *pos)'),
    ('common', 'common-wide-off-by-one', KN, 'if n > max_expand {', 'if n >= max_expand {'),
    ('common', 'common-clause-sort-reversed', KN, 'c.sort_unstable();\n        c.dedup();\n        if seen.insert(c.clone())', 'c.sort_unstable_by(|a, b| b.cmp(a));\n        c.dedup();\n        if seen.insert(c.clone())'),
    ('common', 'common-undecidable-premise-kept', KN, "R::Decided(false) | R::Undecidable => continue 'rule,", "R::Decided(false) => continue 'rule,\n                R::Undecidable => {}"),
    ('common', 'common-internal-sign', PY, '(k, 2 * i + n as usize)', '(k, 2 * i + !n as usize)'),
    ('wiring', 'live-any-class-row', LIVE, 'if i is not None and type(q.objects[i]) is type(value):', 'if i is not None:'),
    ('core', 'core-half-split-q3', 'solver_rs/src/term/tcore.rs', 'if c.d != BigInt::from(2) {', 'if c.d != BigInt::from(2) && c.d != BigInt::from(3) {'),
    ('core', 'core-half-parity', 'solver_rs/src/term/tcore.rs', 'let parity = |r: &Rat| -> u8 { if two.mul(r).n.mod_floor(&BigInt::from(2)).is_zero() { 0 } else { 1 } };', 'let parity = |r: &Rat| -> u8 { if two.mul(r).n.mod_floor(&BigInt::from(2)).is_zero() { 1 } else { 0 } };'),
    ('core', 'core-coeff-no-rest', 'solver_rs/src/term/tcore.rs', 'let t = if rest.len() == 1 { Rest::One(rest[0]) } else { Rest::Product(rest.to_vec()) };', 'let t = Rest::One(rest[0]);'),
    ('core', 'core-bound-zero-kept', 'solver_rs/src/term/tcore.rs', 'if self.rat(c).ok_or(Refuse("core: a Rational class without a value"))?.is_zero() {', 'if false {'),
    ('core', 'core-bound-number-kept', 'solver_rs/src/term/tcore.rs', '            if self.core_is_number(u)? {\n                return Ok(None);', '            if false && self.core_is_number(u)? {\n                return Ok(None);'),
    ('core', 'core-recip-any-exp', 'solver_rs/src/term/tcore.rs', 'if self.class_of(args[1]).kind != Kind::NegativeOne || self.core_is_number(args[0])? {', 'if self.core_is_number(args[0])? {'),
    ('core', 'core-imag-two-rest', 'solver_rs/src/term/tcore.rs', 'if rest.len() + 1 != args.len() || rest.len() > 1 {', 'if rest.len() + 1 != args.len() || rest.len() > 2 {'),
    ('core', 'core-imag-split-partial', 'solver_rs/src/term/tcore.rs', 'None => none = true,    // Python reads every term before it tests for None', 'None => {}'),
    ('core', 'core-half-rules-parity', 'solver_rs/src/term/tcore.rs', 'out.push((prem, vec![(m, "integer", num_odd == 0)]));', 'out.push((prem, vec![(m, "integer", num_odd == 1)]));'),
    ('core', 'core-half-rules-max', 'solver_rs/src/term/tcore.rs', 'if o.len() > MAX_HALF_ODD {', 'if o.len() >= MAX_HALF_ODD {'),
    ('core', 'core-bound-rules-sign', 'solver_rs/src/term/tcore.rs', 'let pos = c1.n.is_positive();\n    for (ps, lower, b) in INT_BOUNDS {', 'let pos = !c1.n.is_positive();\n    for (ps, lower, b) in INT_BOUNDS {'),
    ('core', 'core-recip-rules-noswap', 'solver_rs/src/term/tcore.rs', '        if c1.n.is_negative() {\n            std::mem::swap(&mut a, &mut b);', '        if false {\n            std::mem::swap(&mut a, &mut b);'),
    ('core', 'core-imag-rules-strict', 'solver_rs/src/term/tcore.rs', 'if k == j { strict[k] } else { weak[k] }', 'if k == j { weak[k] } else { weak[k] }'),
    ('core', 'core-imag-number-rules', 'solver_rs/src/term/tcore.rs', '(vec![(0, "real", true), (0, "zero", false)], vec![(1, "imaginary", true)]),', '(vec![(0, "real", true)], vec![(1, "imaginary", true)]),'),
    ('core', 'core-not-unit-two', 'solver_rs/src/term/tcore.rs', '*lower == pos && v >= two || *lower != pos && v <= minus_two', '*lower == pos && v >= Rat::int(1) || *lower != pos && v <= minus_two'),
    ('core', 'core-pi-split-second-i', 'solver_rs/src/term/tcore.rs', 'if kind == Kind::ImaginaryUnit && !seen_i {', 'if kind == Kind::ImaginaryUnit {'),
    ('core', 'core-pi-split-zero', 'solver_rs/src/term/tcore.rs', 'if c.is_zero() {\n            return Ok(None); // Mul(I, pi, 0, x)', 'if false {\n            return Ok(None); // Mul(I, pi, 0, x)'),
    ('core', 'core-mul-sets-ct-two', 'solver_rs/src/term/tcore.rs', 'if args.len() >= 3 {', 'if args.len() >= 2 {'),
    ('core', 'core-mul-sets-ipi-any', 'solver_rs/src/term/tcore.rs', 'Some((c, Some(Rest::One(s)))) if self.core_is_mul(s) =>', 'Some((c, Some(Rest::One(s)))) =>'),
    ('core', 'core-quotient-any-k', 'solver_rs/src/term/tcore.rs', 'if self.core_is_number(v)? || !self.core_negative_integer(k)? {', 'if self.core_is_number(v)? {'),
    ('core', 'core-quotient-rules', 'solver_rs/src/term/tcore.rs', 'vec![(vec![(0, "odd", true), (1, "even", true)], vec![(3, "integer", false)])]', 'vec![(vec![(0, "odd", true), (1, "integer", true)], vec![(3, "integer", false)])]'),
    ('core', 'core-unit-angle-neg', 'solver_rs/src/term/tcore.rs', 'Some(Rat::new(BigInt::from(-1), BigInt::from(2)))', 'Some(Rat::new(BigInt::from(1), BigInt::from(2)))'),
    ('core', 'core-exp-arg-any', 'solver_rs/src/term/tcore.rs', 'Some(u) } else { None }', 'Some(u) } else { Some(u) }'),
    ('core', 'core-irrational-den', 'solver_rs/src/term/tcore.rs', 'Ok(!(exact_root(&b.n, &e.d) && exact_root(&b.d, &e.d)))', 'Ok(!exact_root(&b.n, &e.d))'),
    ('core', 'core-pow-bound-any-exp', 'solver_rs/src/term/tcore.rs', 'if self.class_of(b).flags & flag::IS_ADD == 0 || self.core_is_number(e)? && !self.core_negative_integer(e)? {', 'if self.class_of(b).flags & flag::IS_ADD == 0 {'),
    ('core', 'core-pow-bound-no-finite', 'solver_rs/src/term/tcore.rs', 'p.extend([(1, "integer", true), (1, "negative", true), (2, "finite", true)]);', 'p.extend([(1, "integer", true), (1, "negative", true)]);'),
    ('core', 'core-unit-power-half', 'solver_rs/src/term/tcore.rs', '} else if phi.d == BigInt::from(2) {', '} else if phi.d == BigInt::from(3) {'),
    ('core', 'core-ipi-odd', 'solver_rs/src/term/tcore.rs', 'CWhen::Odd => int && !c.n.is_even(),', 'CWhen::Odd => int,'),
    ('core', 'core-ipi-back-odd', 'solver_rs/src/term/tcore.rs', '("ipi.s.int.odd.back_odd", &[(S, "integer", true), (N, "negative", true)], (S, "odd", true), true, Odd),', '("ipi.s.int.odd.back_odd", &[(S, "integer", true), (N, "negative", true)], (S, "even", true), true, Odd),'),
    ('core', 'core-ipi-other', 'solver_rs/src/term/tcore.rs', 'CWhen::Other => !int && c.d != BigInt::from(2),', 'CWhen::Other => !int,'),
    ('rows', 'rows-neg-dropped', RW, 'Ast::Neg(x) => eval(py, x, number)?.neg(),', 'Ast::Neg(x) => eval(py, x, number)?,'),
    ('rows', 'rows-sub-is-add', RW, 'Op::Sub => x.sub(&y).ok()?,', 'Op::Sub => x.add(&y).ok()?,'),
    ('rows', 'rows-div-is-mul', RW, 'Op::Div => x.div(&y).ok()?,', 'Op::Div => x.mul(&y).ok()?,'),
    ('rows', 'rows-abs-dropped', RW, '"Abs" => x.abs().ok()?,', '"Abs" => x,'),
    ('rows', 'rows-int-off-by-one', RW, 'Some(Num::Q(Rat::norm_big(BigInt::from(*i), BigInt::one())))', 'Some(Num::Q(Rat::norm_big(BigInt::from(*i + 1), BigInt::one())))'),
    ('rows', 'rows-exp-power-sign', RW, 'q.mul(base.pow(sympy_rational(py, &Rat::norm_big(BigInt::from(k), BigInt::one()))?, py.None())?).map(Some)', 'q.mul(base.pow(sympy_rational(py, &Rat::norm_big(BigInt::from(-k), BigInt::one()))?, py.None())?).map(Some)'),
    ('rows', 'rows-key-ignored', RW, 'if self.by_key.len() > 1 {', 'if self.by_key.len() > 99 {'),
    ('rows', 'rows-premise-sign', RW, 'Data::Bool(b) => PyBool::new(py, *b).to_owned().into_any(),', 'Data::Bool(b) => PyBool::new(py, !*b).to_owned().into_any(),'),
    ('rows', 'rows-plain-always', RW, 'if r.len() > 2 {\n                    plain = false;', 'if r.len() > 2 {'),
    ('wiring', 'live-all-derived', LIVE, 'if i is not None and type(q.objects[i]) is type(value):', 'if False:'),
    ('wiring', 'live-value-on-value', LIVE, 'return Compiled((obj,), pat)', 'return Compiled((value,), pat)'),
    ('wiring', 'live-value-negated', LIVE, "'value', False, value, obj)", "'value', False, -value, obj)"),
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
    row['off'], by_wl = 'no', {}
    # `rootof` is scored only when its plain rows are there, so older runs keep their columns.
    wls = ('dev', 'fuzz', 'value') + tuple(w for w in ('rootof', 'rows', 'core') if os.path.exists(os.path.join(a.plain, f'{w}-plain.tsv')))
    for wl in wls:
        rc, out = fresh(d, env, log, wl, 'atoms')
        if rc:
            by_wl[wl] = 'crash'
            if row['off'] == 'no':
                row['off'], row['off_wl'] = 'crash', wl
            continue
        by_wl[wl] = 'no'
        if not filecmp.cmp(out, os.path.join(a.plain, f'{wl}-plain.tsv'), False):
            ls = open(out).read().splitlines()
            ps = open(os.path.join(a.plain, f'{wl}-plain.tsv')).read().splitlines()
            lines = sum(x != y for x, y in zip(ls, ps)) + abs(len(ls) - len(ps))
            answers = sum(x.split('\t')[1:2] != y.split('\t')[1:2] for x, y in zip(ls, ps))
            by_wl[wl] = dict(lines=lines, answers=answers)
            if row['off'] == 'no':
                row.update(off='cmp', off_lines=lines, off_answers=answers, off_wl=wl)
    row['off_by_wl'] = by_wl
    # realroots, directly
    with open(os.path.join(d, 'realroots.txt'), 'w') as f:
        rc = subprocess.run([PYTHON, os.path.join(d, 'realroots_cmp.py'), '--random', '1500'], env=env, cwd=d, stdout=f, stderr=subprocess.STDOUT).returncode
    row['realroots'] = 'cmp' if rc == 1 else 'no' if rc == 0 else f'rc={rc}'
    # rows, directly
    with open(os.path.join(d, 'rows.txt'), 'w') as f:
        rc = subprocess.run([PYTHON, os.path.join(d, 'rows_cmp.py'), '2000'], env=env, cwd=d, stdout=f, stderr=subprocess.STDOUT).returncode
    row['rows_direct'] = 'cmp' if rc == 1 else 'no' if rc == 0 else f'rc={rc}'
    # unit
    with open(os.path.join(d, 'unit.txt'), 'w') as f:
        rc = subprocess.run([PYTHON, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', os.path.join(d, 'test_knowledge_common.py'), os.path.join(d, 'test_knowledge_realroots.py'), os.path.join(d, 'test_knowledge_core.py')], env=env, cwd=d, stdout=f, stderr=subprocess.STDOUT).returncode
    row['unit'] = 'cmp' if rc == 1 else 'no' if rc == 0 else f'rc={rc}'
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
