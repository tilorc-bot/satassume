"""mutate.py's 10 mutants on the slice crate, each scored per check. Builds in a scratch copy; the tree isn't touched.
  mutate_slice.py WORKDIR [--sessions N] [--step1 N] [--seed S] [--jobs J] [--only I,J] [--timeout T] [--triage T] [--shrink T]
Checks: digest   answers only, step 1's corpus
        state    state compare, step 1's corpus
        fuzz-a   answers only, fuzz sessions (can this mutant change an answer the fuzzer sees?)
        fuzz     state compare, fuzz sessions
These are API answers, not the engine's dev and fuzz digests, which need step 3.

Each check ends in one outcome:
  caught   the two solvers differed
  no       the check ran to its end with no difference
  hang     out of time in one session that the unmutated build finishes: the mutant did it
  crash    the process died in one session that the unmutated build finishes: the mutant did it
  void     out of time or dead, and not shown to be the mutant's doing. It says why. Not a catch.
A row for the unmutated build ("base") runs the same checks with the same settings and has to come out "no".
Results go to WORKDIR as each check ends: results.jsonl, mutants.json, table.md; per-check output to WORKDIR/logs."""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
M = [
    ("solver.rs", "level sort: ascending then reversed (ties flip)", "raw.sort_by_key(|&l| std::cmp::Reverse(self.level[(l >> 1) as usize]));", "raw.sort_by_key(|&l| self.level[(l >> 1) as usize]); raw.reverse();", False),
    ("block.rs", "explain: last best wins, not first", "if k > bestk {", "if k >= bestk {", False),
    ("solver.rs", "_mention: pending blocks in reverse order", "for (b, new) in pend {", "for (b, new) in pend.into_iter().rev() {", True),
    ("solver.rs", "_learn: no var_inc decay", "self.var_inc /= VAR_DECAY;", "", False),
    ("solver.rs", "watch: blocker-style keep", "if c[0] == fl {\n                    c[0] = c[1];\n                    c[1] = fl;\n                }", "if c[0] == fl {\n                    c.swap(0, 1);\n                }\n                if c.len() > 2 && self.val[c[2] as usize] == T { c.swap(1, 2); self.watches[c[1] as usize].push(cr); continue; }", False),
    ("solver.rs", "ring: None counts as false in a clause", "if x != (if l & 1 == 1 { T } else { F }) {\n                    return true;", "if x == (if l & 1 == 1 { F } else { T }) {\n                    return true;", True),
    ("solver.rs", "_fill: no growth past the model's end", "if mv.len() < lo + n {\n            mv.resize(lo + n, U);\n        }\n        mv[lo..lo + n].copy_from_slice(&vals);", "let e = (lo + n).min(mv.len()); mv[lo..e].copy_from_slice(&vals[..e - lo]);", True),
    ("solver.rs", "_learn: bump after joining learnts", "self.bump_clause(c); // before it joins learnts: a rescale here misses it, as in Python\n            self.learnts.push(c);", "self.learnts.push(c);\n            self.bump_clause(c);", True),
    ("solver.rs", "_pick_branch: decisions not counted on -1", "self.n.decisions += 1;\n                nxt = self.pick_branch();", "nxt = self.pick_branch();\n                if nxt >= 0 { self.n.decisions += 1; }", False),
    ("solver.rs", "theory unit reason stored as learnt", "Reason::Clause(self.new_clause(vec![l], false))", "Reason::Clause(self.new_clause(vec![l], true))", True),
    # The boundary mutants, step 4. A batch: the crate has no batching layer, so these are the batches it has. Swapped callback order, a dropped result, a stale handle, and the rest of `lib.rs`'s callback layer. A list in place of the old text is several (old, new) sites.
    ("solver.rs", "batch flush: pending trail reaches theories newest first", "let l = self.trail[i];\n            i += 1;\n            let v = (l >> 1) as usize;\n            if self.tmap[v].is_empty() {", "let l = self.trail[self.trail.len() - 1 - (i - self.thead)];\n            i += 1;\n            let v = (l >> 1) as usize;\n            if self.tmap[v].is_empty() {", False),
    ("lib.rs", "batch: add_clauses in reverse", "run(|| Ok(self.s.add_clauses(&c)))", "{ let mut c = c; c.reverse(); run(|| Ok(self.s.add_clauses(&c))) }", False),
    ("lib.rs", "batch: add_internal clauses in reverse", "run(|| self.s.add_internal(&c, mentions.as_deref()))", "{ let mut c = c; c.reverse(); run(|| self.s.add_internal(&c, mentions.as_deref())) }", False),
    ("solver.rs", "callback order: check, last theory first", "for t in 0..self.theories.len() {\n            match self.theories[t].check() {", "for t in (0..self.theories.len()).rev() {\n            match self.theories[t].check() {", False),
    ("solver.rs", "callback order: push_level, last theory first", "for t in &mut self.theories {\n            t.push_level();", "for t in self.theories.iter_mut().rev() {\n            t.push_level();", False),
    ("solver.rs", "callback order: pop_level, last theory first", "for t in &mut self.theories {\n                    t.pop_level();", "for t in self.theories.iter_mut().rev() {\n                    t.pop_level();", False),
    ("solver.rs", "callback order: propagate, last theory first", "for pi in 0..self.tprops.len() {", "for pi in (0..self.tprops.len()).rev() {", False),
    ("solver.rs", "callback order: decide, last theory first", "for di in 0..self.tdecides.len() {", "for di in (0..self.tdecides.len()).rev() {", False),
    ("solver.rs", "callback order: a shared variable's theories, last first", "for k in 0..self.tmap[v].len() {\n                let t = self.tmap[v][k] as usize;\n                if let Some(c) = self.theories[t].assert_lit(x) {\n                    self.thead = i;", "for k in (0..self.tmap[v].len()).rev() {\n                let t = self.tmap[v][k] as usize;\n                if let Some(c) = self.theories[t].assert_lit(x) {\n                    self.thead = i;", False),
    ("lib.rs", "dropped: assert_lit's conflict", "ok(conflict_of(&r))\n    }\n\n    fn check", "let _ = ok(conflict_of(&r));\n        None\n    }\n\n    fn check", False),
    ("lib.rs", "dropped: check's conflict", "Some(c) => Check::Conflict(c),", "Some(_) => Check::Nothing,", False),
    ("lib.rs", "dropped: check's model", "None => Check::Model(PyObj(ok(r.get_item(1)).unbind())),", "None => Check::Nothing,", False),
    ("lib.rs", "dropped: propagate's first pair", "PyProps(ok(r.try_iter()))", "let mut it = ok(r.try_iter());\n        let _ = it.next();\n        PyProps(it)", False),
    ("lib.rs", "dropped: decide's answer", "Some(ok(int_of(&r)))", "let _ = ok(int_of(&r));\n            None", False),
    ("lib.rs", "dropped: register_atom never reaches the theory", "ok(self.obj.bind(p).call_method1(self.n_register.bind(p), (var, payload)));", "let _ = (p, var, payload);", False),
    ("lib.rs", "dropped: pop_level never reaches the theory", "ok(self.obj.bind(p).call_method0(self.n_pop.bind(p)));", "let _ = p;", False),
    ("lib.rs", "dropped: assert_lit's exception", "let r = ok(self.obj.bind(p).call_method1(self.n_assert.bind(p), (x,)));", "let r = match self.obj.bind(p).call_method1(self.n_assert.bind(p), (x,)) {\n            Ok(r) => r,\n            Err(_) => return None,\n        };", False),
    ("lib.rs", "conflict_of: any falsy first item, not `is False`", "!r.get_item(0)?.is(PyBool::new(r.py(), false))", "r.get_item(0)?.is_truthy()?", False),
    ("lib.rs", "hook_lits: a theory's clause reversed", "xs.try_iter()?.map(|x| Ok(int_of(&x?)?.clamp(-(i32::MAX as i64), i32::MAX as i64) as i32 as u32)).collect()", "let mut v = xs.try_iter()?.map(|x| Ok(int_of(&x?)?.clamp(-(i32::MAX as i64), i32::MAX as i64) as i32 as u32)).collect::<PyResult<Vec<u32>>>()?;\n    v.reverse();\n    Ok(v)", False),
    ("lib.rs", "stale handle: check goes to the process's latest theory at that place", [
        ("struct PyObj(Py<PyAny>);", "thread_local! { static SLOT: std::cell::RefCell<Vec<Py<PyAny>>> = const { std::cell::RefCell::new(Vec::new()) }; }\n\nstruct PyObj(Py<PyAny>);"),
        ("struct PyTheory {\n", "struct PyTheory {\n    slot: usize,\n"),
        ("Ok(PyTheory {\n", "Ok(PyTheory {\n            slot: 0,\n"),
        ("let t = PyTheory::new(theory)?;", "let mut t = PyTheory::new(theory)?;\n        t.slot = self.s.theories.len();\n        SLOT.with(|s| { let mut s = s.borrow_mut(); let o = theory.clone().unbind(); if s.len() <= t.slot { s.push(o); } else { s[t.slot] = o; } });"),
        ("let r = ok(self.obj.bind(p).call_method0(self.n_check.bind(p)));", "let target = SLOT.with(|s| s.borrow()[self.slot].clone_ref(p));\n        let r = ok(target.bind(p).call_method0(self.n_check.bind(p)));"),
    ], None, False),
    ("lib.rs", "stale handle: a variable keeps the process's first payload", "ok(self.obj.bind(p).call_method1(self.n_register.bind(p), (var, payload)));", "thread_local! { static SEEN: std::cell::RefCell<std::collections::HashMap<i32, Py<PyAny>>> = std::cell::RefCell::new(std::collections::HashMap::new()); }\n        let payload = SEEN.with(|s| s.borrow_mut().entry(var).or_insert(payload).clone_ref(p));\n        ok(self.obj.bind(p).call_method1(self.n_register.bind(p), (var, payload)));", False),
    ("lib.rs", "lifetime: __traverse__ misses the theory, so a cycle never frees", "visit.call(&t.obj)?;", "", False),
    ("lib.rs", "theory_models: reversed", "let items = ms.iter().map(|m| m.as_ref().map(|x| x.0.clone_ref(p)));", "let items = ms.iter().rev().map(|m| m.as_ref().map(|x| x.0.clone_ref(p)));", False),
    ("lib.rs", "run: a solver fault raises ValueError, not RuntimeError", "Ok(m) => Err(PyRuntimeError::new_err(m.0)),", "Ok(m) => Err(PyValueError::new_err(m.0)),", False),
    ("lib.rs", "model: an unassigned variable reads False", "F => Some(false),\n                _ => None,", "_ => Some(false),", False),
]
CHECKS = {"digest": ("step1", "answers"), "state": ("step1", "state"), "fuzz-a": ("fuzz", "answers"), "fuzz": ("fuzz", "state")}
LOCK = threading.Lock()
PROBE = """import sys
sys.path.insert(0, sys.argv[1])
import sa_solver
s = sa_solver.Solver()
n, h = 6, 5
v = lambda i, j: i * h + j + 1
for i in range(n):
    s.add_clause([v(i, j) for j in range(h)])
for j in range(h):
    for i in range(n):
        for k in range(i):
            s.add_clause([-v(i, j), -v(k, j)])
print(s.solve(), s._var_inc.hex(), sa_solver.__file__)
"""


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def fuzz_cmd(so, check, a):
    corpus, level = CHECKS[check]
    n = a.step1 if corpus == "step1" else a.sessions
    return [sys.executable, os.path.join(HERE, "fuzz.py"), "--so", so, "--corpus", corpus, "--level", level,
            "--sessions", str(n), "--seed", str(a.seed), "--json"]


def run_one(cmd, out, err, timeout):
    """Return code, or None if out of time."""
    with open(out, "w") as o, open(err, "w") as e:
        try:
            return subprocess.run(cmd, stdout=o, stderr=e, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            return None


def last_json(path):
    lines = open(path).read().strip().splitlines()
    try:
        return json.loads(lines[-1])
    except (IndexError, ValueError):
        return None


def triage(mid, so, base, check, a, label, kind):
    """A run that timed out or died: does this one session do it to the mutant, and not to the unmutated build?"""
    logs = os.path.join(a.work, "logs")
    cmd = lambda d: fuzz_cmd(d, check, a) + ["--label", label, "--no-shrink"]
    res = {}
    for name, d in (("mutant", so), ("base", base)):
        tag = os.path.join(logs, f"m{mid}-{check}-triage-{name}")
        res[name] = run_one(cmd(d), tag + ".out", tag + ".err", a.triage)
    bad = lambda rc: rc is None or rc < 0 or rc not in (0, 1)
    note = f"session {label}: mutant rc {res['mutant']}, unmutated rc {res['base']} (None: over {a.triage} s)"
    if bad(res["mutant"]) and not bad(res["base"]):
        return dict(outcome=kind, session=label, note=note)
    if bad(res["base"]):
        return dict(outcome="void", session=label, note=f"the unmutated build fails too; {note}")
    return dict(outcome="void", session=label, note=f"does not reproduce on this session alone; {note}")


def score(mid, so, base, check, a):
    logs = os.path.join(a.work, "logs")
    tag = os.path.join(logs, f"m{mid}-{check}")
    prog = tag + ".progress"
    if os.path.exists(prog):
        os.remove(prog)
    rc = run_one(fuzz_cmd(so, check, a) + ["--progress", prog, "--shrink-seconds", str(a.shrink)], tag + ".out", tag + ".err", a.timeout)
    j = last_json(tag + ".out")
    if j is not None:
        if j["so_sha"] != sha(os.path.join(so, "sa_solver.so")):
            sys.exit(f"VOID: m{mid} {check} loaded {j['so']}, not the build in {so}")
        if j["caught"]:
            # A run out of time here had already found the difference: only its shrinking was cut.
            return dict(outcome="caught", what=j["what"], session=j["session"], calls=j["script_len"],
                        shrunk=j["shrunk"], py=j["py"][:300], rs=j["rs"][:300])
        if rc == 0:
            return dict(outcome="no", seconds=j["seconds"], reach=j["reach"])
    label = open(prog).read() if os.path.exists(prog) else None
    kind = "hang" if rc is None else "crash"
    if label is None:
        return dict(outcome="void", note=f"{kind} before any session; rc {rc}; {tag}.err")
    if mid == "base":
        return dict(outcome="void", session=label, note=f"the unmutated build: {kind}, rc {rc}; {tag}.err")
    return triage(mid, so, base, check, a, label, kind)


def cell(r):
    if r is None:
        return "..."
    o = r["outcome"]
    if o == "caught":
        return f"caught: {r['what']}, session {r['session']}, {r['calls']} calls{'' if r['shrunk'] else ' (not fully shrunk)'}"
    if o == "no":
        return "no"
    return f"{o}: session {r.get('session', '?')}"


def write(a, rows, loadcheck):
    with open(os.path.join(a.work, "mutants.json.tmp"), "w") as f:
        json.dump(dict(loadcheck=loadcheck, rows={str(k): v for k, v in rows.items()}), f, indent=1)
    os.replace(os.path.join(a.work, "mutants.json.tmp"), os.path.join(a.work, "mutants.json"))
    with open(os.path.join(a.work, "table.md.tmp"), "w") as f:
        f.write("| # | mutant | missed by replays | digest | state | fuzz answers | fuzz state |\n|---|---|---|---|---|---|---|\n")
        for i in rows:
            name, missed = ("unmutated", "") if i == "base" else (M[i][1], "yes" if M[i][4] else "")
            f.write(f"| {i} | {name} | {missed} | " + " | ".join(cell(rows[i].get(c)) for c in CHECKS) + " |\n")
    os.replace(os.path.join(a.work, "table.md.tmp"), os.path.join(a.work, "table.md"))


def build(crate, d):
    r = subprocess.run(["cargo", "build", "--release"], cwd=crate, capture_output=True, text=True,
                       env=dict(os.environ, PYO3_PYTHON=sys.executable))
    if r.returncode:
        sys.exit(f"BUILD {d}\n{r.stderr[-800:]}")
    os.makedirs(d, exist_ok=True)
    shutil.copy(os.path.join(crate, "target/release/libsa_solver.so"), os.path.join(d, "sa_solver.so"))
    return d


def mutated_build(crate, work, i):
    """Build mutant i in `crate` and restore the source. Exits if a site doesn't match exactly once."""
    f, name, x, y, _ = M[i]
    path = os.path.join(crate, "src", f)
    src = open(path).read()
    out = src
    for old, new in x if isinstance(x, list) else [(x, y)]:
        if out.count(old) != 1:
            sys.exit(f"NOMATCH {name}: {out.count(old)} matches of {old[:60]!r}")
        out = out.replace(old, new)
    open(path, "w").write(out)
    try:
        return build(crate, os.path.join(work, f"m{i}"))
    finally:
        open(path, "w").write(src)


def probe(d):
    return subprocess.run([sys.executable, "-c", PROBE, d], capture_output=True, text=True, check=True).stdout.strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("work")
    p.add_argument("--sessions", type=int, default=2000)
    p.add_argument("--step1", type=int, default=300)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--only")
    p.add_argument("--timeout", type=float, default=600, help="seconds per check")
    p.add_argument("--triage", type=float, default=120, help="seconds per session when finding out what a hang was")
    p.add_argument("--shrink", type=float, default=60, help="seconds of shrinking per catch")
    a = p.parse_args()
    a.work = os.path.abspath(a.work)
    crate = os.path.join(a.work, "crate")
    os.makedirs(os.path.join(a.work, "logs"), exist_ok=True)
    if os.path.exists(crate):
        shutil.rmtree(os.path.join(crate, "src"))
    shutil.copytree(os.path.join(HERE, "solver_rs"), crate, dirs_exist_ok=True, ignore=shutil.ignore_patterns("target"))
    only = set(map(int, a.only.split(","))) if a.only else set(range(len(M)))
    base = build(crate, os.path.join(a.work, "base"))
    sos = {"base": base}
    for i in range(len(M)):
        if i in only:
            sos[i] = mutated_build(crate, a.work, i)
    # Load proof. Every build is different, each check verifies the file its process loaded, and one mutant visibly
    # behaves differently from the unmutated build on a fixed script.
    shas = {k: sha(os.path.join(d, "sa_solver.so")) for k, d in sos.items()}
    if len(set(shas.values())) != len(shas):
        sys.exit(f"VOID: two builds are the same file: {shas}")
    loadcheck = dict(sha={str(k): v[:16] for k, v in shas.items()}, base=probe(base))
    if 3 in sos:
        loadcheck["m3"] = probe(sos[3])
        if loadcheck["m3"].split()[1] == loadcheck["base"].split()[1]:
            sys.exit(f"VOID: mutant 3 has the unmutated var_inc: {loadcheck}")
    print("load check:", json.dumps(loadcheck), flush=True)
    rows = {k: {} for k in sos}
    write(a, rows, loadcheck)

    def job(k, c):
        r = score(k, sos[k], base, c, a)
        with LOCK:
            rows[k][c] = r
            with open(os.path.join(a.work, "results.jsonl"), "a") as f:
                f.write(json.dumps(dict(mutant=k, check=c, **{x: y for x, y in r.items() if x != "reach"})) + "\n")
            write(a, rows, loadcheck)
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for fu in cf.as_completed([ex.submit(job, k, c) for k in sos for c in CHECKS]):
            fu.result()
    print(open(os.path.join(a.work, "table.md")).read())


if __name__ == "__main__":
    main()
