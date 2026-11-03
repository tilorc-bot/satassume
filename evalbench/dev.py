"""The quick dev set, for workers: answers, time, counters, phases.

    ~/dev/sa-eval/.venv/bin/python ~/dev/sa-eval/evalbench/dev.py CHECKOUT \
        [--base BASE_CHECKOUT] [--rounds 3] [--workload dev] [--profile OUT.prof]

* answers: compared with the baseline's (9bafaa5) answers on the dev set,
  query by query (evalbench/dev-answers-9bafaa5.jsonl);
* time: ROUNDS cold processes (alternating with BASE if given), medians of
  the replay loop, split into None / definite answers.  Unpinned: on a
  shared machine expect a few % noise; the evaluator's numbers are pinned;
* counters (deterministic) and phase times: one instrumented process each
  (with BASE: both, and the delta).
``--workload dev-unique`` drops repeated queries (no answer-memo hits).
"""
import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shim"))
from evalbench.common import HERE, workload  # noqa: E402
from evalbench.run import replay  # noqa: E402

REF = os.path.join(HERE, "dev-answers-9bafaa5.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("checkout")
    ap.add_argument("--base")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--workload", default="dev")
    ap.add_argument("--profile")
    args = ap.parse_args()
    trees = [("cand", os.path.abspath(args.checkout))]
    if args.base:
        trees.append(("base", os.path.abspath(args.base)))
    tmp = os.path.join("/tmp", f"sa-eval-dev-{os.getpid()}.jsonl")
    # answers
    first = replay(trees[0][1], args.workload, answers=tmp)
    ans = [json.loads(line) for line in open(tmp)]
    os.remove(tmp)
    if args.workload == "dev":
        ref = [json.loads(line) for line in open(REF)]
        pairs = workload("dev")
        diff = [(i, ref[i], a) for i, a in enumerate(ans) if a != ref[i]]
        print(f"answers vs 9bafaa5 on dev: {len(ans) - len(diff)}/{len(ans)} identical")
        for i, b, a in diff[:30]:
            print(f"   #{i}: {pairs[i][0]}  |  {pairs[i][1]}:  base {b}  cand {a}")
        if len(diff) > 30:
            print(f"   ... {len(diff) - 30} more")
    # time
    runs = {name: [] for name, _ in trees}
    runs["cand"].append(first)
    for r in range(args.rounds):
        for name, d in (trees if r % 2 else trees[::-1]):
            if name == "cand" and r == 0:
                continue
            runs[name].append(replay(d, args.workload))
    print(f"time ({args.workload}, {first['n']} queries, medians of cold processes; unpinned):")
    med = {}
    for name, _ in trees:
        rs = runs[name]
        med[name] = {k: statistics.median(x[k] for x in rs) for k in ("seconds", "none_s", "def_s")}
        m = med[name]
        print(f"   {name}: total {m['seconds']:.3f} s   None {m['none_s']:.3f} s ({rs[0]['n_none']})   "
              f"definite {m['def_s']:.3f} s ({rs[0]['n_def']})   runs {len(rs)}")
    if args.base:
        print("   speedup base/cand: " + "   ".join(f"{k} {med['base'][k] / med['cand'][k]:.3f}x"
                                                   for k in ("seconds", "none_s", "def_s")))
    # counters and phases
    inst = {name: replay(d, args.workload, "--counters", "--phases") for name, d in trees}
    keys = sorted(set().union(*(set(v["counters"]) for v in inst.values())))
    print("counters" + (" (cand / base / delta)" if args.base else "") + ":")
    for k in keys:
        c = inst["cand"]["counters"].get(k, 0)
        if args.base:
            b = inst["base"]["counters"].get(k, 0)
            print(f"   {k:28s} {c:10d} {b:10d} {c - b:+10d}")
        else:
            print(f"   {k:28s} {c:10d}")
    print("phases, instrumented run (s)" + (" (cand / base)" if args.base else "") + ":")
    for k in sorted(set().union(*(set(v["phases"]) for v in inst.values()))):
        c = inst["cand"]["phases"].get(k, 0.0)
        line = f"   {k:12s} {c:8.3f}"
        if args.base:
            line += f" {inst['base']['phases'].get(k, 0.0):8.3f}"
        print(line)
    for name, v in inst.items():
        if v.get("missing"):
            print(f"   {name}: instrumentation could not find {v['missing']} (those counters/phases are not comparable)")
    if args.profile:
        replay(trees[0][1], args.workload, "--profile", os.path.abspath(args.profile))
        print(f"profile: {args.profile} (python -m pstats)")


if __name__ == "__main__":
    main()
