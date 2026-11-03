"""One wide table from an evalbench.ab run: rows = workload x metric, one
column per arm (speedup over base, median of the paired per-round ratios,
with the min..max speedup over rounds), plus an answer check: every arm's
answer digest on every workload and round must equal base's.

    python -m evalbench.readout ab.jsonl --arm TREE=LABEL [--arm ...] [--base base]
"""
import argparse
import statistics
from collections import defaultdict

from evalbench.summarize import load, table


def digests(rows):
    d = defaultdict(set)                      # (workload, tree) -> {digest}
    for r in rows:
        if r.get("digest") is not None:
            d[(r["workload"], r["tree"])].add(r["digest"])
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--base", default="base")
    ap.add_argument("--arm", action="append", required=True, help="TREE=LABEL, in column order")
    args = ap.parse_args()
    arms = [a.split("=", 1) for a in args.arm]
    rows = load(args.path)
    t = {(r["workload"], r["metric"], r["tree"]): r for r in table(rows, args.base)}
    keys = list(dict.fromkeys((r["workload"], r["metric"]) for r in table(rows, args.base)))
    print("| workload | metric | base median s | " + " | ".join(lab for _, lab in arms) + " |")
    print("|---|---|---|" + "---|" * len(arms))
    for w, m in keys:
        base_med = next((t[(w, m, a)]["base_med"] for a, _ in arms if (w, m, a) in t), None)
        cells = []
        for a, _ in arms:
            r = t.get((w, m, a))
            cells.append("n/a" if r is None else
                         f"**{1 / r['ratio_med']:.2f}x** ({1 / r['ratio_max']:.2f}..{1 / r['ratio_min']:.2f})")
        print(f"| {w} | {m} | {base_med:.3f} | " + " | ".join(cells) + " |")
    print()
    d = digests(rows)
    n = {r["workload"]: r.get("n") for r in rows if r["tree"] == args.base}
    print("| workload | queries | base digest stable | " + " | ".join(lab for _, lab in arms) + " |")
    print("|---|---|---|" + "---|" * len(arms))
    for w in dict.fromkeys(r["workload"] for r in rows):
        b = d.get((w, args.base), set())
        cells = []
        for a, _ in arms:
            c = d.get((w, a), set())
            cells.append("n/a" if not c or not b else ("same" if c == b and len(b) == 1 else "**DIFFERS**"))
        print(f"| {w} | {n.get(w)} | {'yes' if len(b) == 1 else ('n/a' if not b else 'NO')} | " + " | ".join(cells) + " |")
    rounds = sorted({r["round"] for r in rows})
    print(f"\nrounds: {len(rounds)} (warm-up excluded); medians of paired ratios; range = min..max speedup over rounds.")


if __name__ == "__main__":
    main()
