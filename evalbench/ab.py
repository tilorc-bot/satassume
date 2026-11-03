"""Pinned A/B: baseline and candidate alternating, cold processes, inside
ONE bench-container invocation (one leased CPU for the whole comparison).

    python -m evalbench.ab --tree base=DIR --tree cand=DIR [--tree cand2=DIR] \
        --rounds 5 --warmup 1 --workloads dev,ho-stream,ho-battery,ho-fuzz,corpus,fork-battery \
        --out /results/ab.jsonl

Each round runs every (workload, tree) pair once in a fresh process; the
tree order alternates between rounds (and rotates for >2 trees).  Warm-up
rounds are recorded with ``"warmup": true`` and ignored by the summary.
One JSON line per run.
"""
import argparse
import json
import os
import time

from evalbench.run import replay

DEFAULT = "dev,ho-stream,ho-battery,ho-fuzz,corpus,fork-battery"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", action="append", required=True, help="NAME=DIR")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--workloads", default=DEFAULT)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    trees = [t.split("=", 1) for t in args.tree]
    with open(args.out, "a") as out:
        for rnd in range(args.warmup + args.rounds):
            k = rnd % len(trees)
            order = trees[k:] + trees[:k]
            if rnd % 2:
                order = order[::-1]
            for w in args.workloads.split(","):
                for name, d in order:
                    res = replay(d, w)
                    res.update({"round": rnd - args.warmup, "warmup": rnd < args.warmup, "tree": name,
                                "dir": d, "t_unix": round(time.time(), 1)})
                    out.write(json.dumps(res) + "\n")
                    out.flush()
                    print(json.dumps({k2: res.get(k2) for k2 in ("round", "workload", "tree", "seconds", "ask_s")}),
                          flush=True)


if __name__ == "__main__":
    main()
