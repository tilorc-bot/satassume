"""build_mutants.py WORK I,J,...: the unmutated build and each mutant, one at a time, with mutate_slice's own build code.
A site that doesn't match, or a build that fails, is recorded and the rest still build. Then mutate_live.py --resume scores them."""
import json, os, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv, args = [sys.argv[0], "/nonexistent"], sys.argv[1:]
from mutate_slice import HERE, M, build, mutated_build, sha
work = os.path.abspath(args[0]); only = [int(x) for x in args[1].split(",")]
crate = os.path.join(work, "crate")
os.makedirs(os.path.join(work, "logs"), exist_ok=True)
shutil.copytree(os.path.join(HERE, "solver_rs"), crate, dirs_exist_ok=True, ignore=shutil.ignore_patterns("target"))
log = open(os.path.join(work, "builds.jsonl"), "a")
def rec(**k):
    log.write(json.dumps(k) + "\n"); log.flush()
t = time.time(); d = build(crate, os.path.join(work, "base")); rec(k="base", sha=sha(d + "/sa_solver.so")[:16], s=round(time.time() - t))
for i in only:
    t = time.time()
    try:
        d = mutated_build(crate, work, i)
        rec(k=i, sha=sha(d + "/sa_solver.so")[:16], s=round(time.time() - t), name=M[i][1])
    except SystemExit as e:
        rec(k=i, failed=str(e)[:600], name=M[i][1])
print("built", len(only), "total", len(M))
