"""mutate.py's 10 mutants on the slice crate, each scored per check. Builds in a scratch copy; the tree isn't touched.
  mutate_slice.py WORKDIR [--sessions N] [--step1 N] [--jobs J] [--only I,J]
Checks: digest   answers only, step 1's corpus
        state    state compare, step 1's corpus
        fuzz-a   answers only, fuzz sessions (can this mutant change an answer the fuzzer sees?)
        fuzz     state compare, fuzz sessions
Prints a table and writes WORKDIR/mutants.json."""
import argparse
import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import sys

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
]
CHECKS = {"digest": ("step1", "answers"), "state": ("step1", "state"), "fuzz-a": ("fuzz", "answers"), "fuzz": ("fuzz", "state")}


def score(so, check, a):
    corpus, level = CHECKS[check]
    n = a.step1 if corpus == "step1" else a.sessions
    cmd = [sys.executable, os.path.join(HERE, "fuzz.py"), "--so", so, "--corpus", corpus, "--level", level, "--sessions", str(n), "--json"]
    x = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(x.stdout.strip().splitlines()[-1])
    except Exception:
        return dict(caught=True, what="crash", session="?", py="", rs=x.stderr[-400:], script_len=0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("work")
    p.add_argument("--sessions", type=int, default=2000)
    p.add_argument("--step1", type=int, default=300)
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--only")
    a = p.parse_args()
    crate = os.path.join(a.work, "crate")
    os.makedirs(a.work, exist_ok=True)
    if os.path.exists(crate):
        shutil.rmtree(os.path.join(crate, "src"))
    shutil.copytree(os.path.join(HERE, "solver_rs"), crate, dirs_exist_ok=True)
    only = set(map(int, a.only.split(","))) if a.only else set(range(len(M)))
    sos = {}
    for i, (f, name, x, y, _) in enumerate(M):
        if i not in only:
            continue
        path = os.path.join(crate, "src", f)
        src = open(path).read()
        if x not in src:
            sys.exit(f"NOMATCH {name}")
        open(path, "w").write(src.replace(x, y, 1))
        r = subprocess.run(["cargo", "build", "--release"], cwd=crate, capture_output=True, text=True,
                           env=dict(os.environ, PYO3_PYTHON=sys.executable))
        open(path, "w").write(src)
        if r.returncode:
            sys.exit(f"BUILD {name}\n{r.stderr[-800:]}")
        d = os.path.join(a.work, f"m{i}")
        os.makedirs(d, exist_ok=True)
        shutil.copy(os.path.join(crate, "target/release/libsa_solver.so"), os.path.join(d, "sa_solver.so"))
        sos[i] = d
    out = {}
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        futs = {ex.submit(score, sos[i], c, a): (i, c) for i in sos for c in CHECKS}
        for fu in cf.as_completed(futs):
            i, c = futs[fu]
            out.setdefault(i, {})[c] = fu.result()
    json.dump(out, open(os.path.join(a.work, "mutants.json"), "w"), indent=1)
    print("| # | mutant | missed by replays | digest | state | fuzz answers | fuzz state |")
    print("|---|---|---|---|---|---|---|")
    for i in sorted(out):
        cell = lambda c: (f"caught ({out[i][c]['what']}, {out[i][c].get('script_len')} calls)" if out[i][c]["caught"] else "no")
        print(f"| {i} | {M[i][1]} | {'yes' if M[i][4] else ''} | " + " | ".join(cell(c) for c in CHECKS) + " |")


main()
