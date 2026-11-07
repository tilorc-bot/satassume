"""probe_build.py WORK: build `solver_rs` with a counter line at each path the workloads never ran, in a scratch copy.
Restarts, reduce_db, and the conditions of mutants 2, 5, 6, 7, 9. Each hit appends "NAME THEORIES TEST" to $PROBE_FILE;
rust_plugin.py keeps $PROBE_TEST current. The answers aren't touched. The build is WORK/sa_solver.so; run_suite.sh takes
it with SLICE_SO=WORK and PROBE_FILE set."""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HIT = """
pub fn probe_hit(name: &str, theories: usize) {
    use std::io::Write;
    if let Ok(path) = std::env::var("PROBE_FILE") {
        let test = std::env::var("PROBE_TEST").unwrap_or_default();
        let mut f = std::fs::OpenOptions::new().create(true).append(true).open(path).unwrap();
        writeln!(f, "{name} {theories} {test}").unwrap();
    }
}
"""
SITES = [
    ("for (b, new) in pend {", 'if pend.len() >= 2 { probe_hit("m2-two-pending", self.theories.len()); }\n        for (b, new) in pend {'),
    ("if x != (if l & 1 == 1 { T } else { F }) {\n                    return true;", 'if x == U { probe_hit("m5-ring-none", self.theories.len()); }\n                if x != (if l & 1 == 1 { T } else { F }) {\n                    return true;'),
    ("if mv.len() < lo + n {", 'if mv.len() < lo + n { probe_hit("m6-fill-growth", self.theories.len()); }\n        if mv.len() < lo + n {'),
    ("self.bump_clause(c); // before it joins learnts: a rescale here misses it, as in Python", 'let ci = self.cla_inc;\n            self.bump_clause(c);\n            if self.cla_inc != ci { probe_hit("m7-rescale-in-learn", self.theories.len()); }'),
    ("Reason::Clause(self.new_clause(vec![l], false))", '{ probe_hit("m9-unit-reason-above-root", self.theories.len()); Reason::Clause(self.new_clause(vec![l], false)) }'),
    ("fn reduce_db(&mut self) {", 'fn reduce_db(&mut self) {\n        probe_hit("reduce_db", self.theories.len());'),
    ("self.n.restarts += restarts - 1;", 'if restarts > 1 { probe_hit("restart", self.theories.len()); }\n        self.n.restarts += restarts - 1;'),
]


def main():
    work = os.path.abspath(sys.argv[1])
    crate = os.path.join(work, "crate")
    shutil.copytree(os.path.join(HERE, "solver_rs"), crate, dirs_exist_ok=True, ignore=shutil.ignore_patterns("target"))
    path = os.path.join(crate, "src", "solver.rs")
    src = open(os.path.join(HERE, "solver_rs", "src", "solver.rs")).read()
    for old, new in SITES:
        if src.count(old) != 1:
            sys.exit(f"NOMATCH {src.count(old)}: {old[:60]!r}")
        src = src.replace(old, new)
    open(path, "w").write(src + HIT)
    subprocess.run(["cargo", "build", "--release"], cwd=crate, check=True, capture_output=True,
                   env=dict(os.environ, PYO3_PYTHON=sys.executable))
    shutil.copy(os.path.join(crate, "target/release/libsa_solver.so"), os.path.join(work, "sa_solver.so"))
    print(os.path.join(work, "sa_solver.so"))


if __name__ == "__main__":
    main()
