"""Summarize evalbench.ab output: per workload, medians per tree and the
candidate/baseline ratio per round (paired: same round, adjacent runs).

    python -m evalbench.summarize ab.jsonl [--base base] [--md]

Ratio = candidate time / baseline time (< 1 is faster); speedup = 1/ratio.
Spread: min..max of the per-round ratios.  Metrics: ``seconds`` (replay
loop), ``none_s``/``def_s`` (its None / definite answers) for replays;
``ask_s`` (inside satassume's ask), ``ask_none_s``, ``refine_s`` for the
fork-per-case battery.
"""
import argparse
import json
import statistics
from collections import defaultdict

METRICS = {"fork-battery": ["ask_s", "ask_none_s", "refine_s"]}
DEFAULT_METRICS = ["seconds", "none_s", "def_s"]


def load(path):
    rows = [json.loads(line) for line in open(path)]
    return [r for r in rows if not r.get("warmup")]


def table(rows, base="base"):
    by = defaultdict(dict)                    # (workload, round) -> tree -> row
    for r in rows:
        by[(r["workload"], r["round"])][r["tree"]] = r
    trees = sorted({r["tree"] for r in rows}, key=lambda t: (t != base, t))
    workloads = list(dict.fromkeys(r["workload"] for r in rows))
    out = []
    for w in workloads:
        for m in METRICS.get(w, DEFAULT_METRICS):
            rounds = sorted(rd for (ww, rd) in by if ww == w)
            med = {t: statistics.median(by[(w, rd)][t][m] for rd in rounds if t in by[(w, rd)])
                   for t in trees}
            for t in trees[1:]:
                ratios = [by[(w, rd)][t][m] / by[(w, rd)][base][m] for rd in rounds
                          if t in by[(w, rd)] and base in by[(w, rd)] and by[(w, rd)][base][m] > 0]
                if not ratios:
                    continue
                out.append({"workload": w, "metric": m, "tree": t, "rounds": len(ratios),
                            "base_med": med[base], "cand_med": med[t],
                            "ratio_med": statistics.median(ratios), "ratio_min": min(ratios),
                            "ratio_max": max(ratios)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--base", default="base")
    args = ap.parse_args()
    rows = table(load(args.path), args.base)
    print("| workload | metric | tree | base median s | cand median s | speedup (median paired) | ratio range | rounds |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['workload']} | {r['metric']} | {r['tree']} | {r['base_med']:.3f} | {r['cand_med']:.3f} | "
              f"{1 / r['ratio_med']:.3f}x | {r['ratio_min']:.3f}..{r['ratio_max']:.3f} | {r['rounds']} |")


if __name__ == "__main__":
    main()
