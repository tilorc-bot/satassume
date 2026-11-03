"""Judge one candidate: gates (orion), pinned A/B (pareto1), counters; writes
evalbench/results/<worker>-<sha>.md and prints the one-line verdict.

    python -m evalbench.judge WORKER CLONE SHA [--note "one line"] [--rounds 5] [--skip-ab]
"""
import argparse
import json
import os
import subprocess
import sys

from evalbench.common import HERE, ROOT
from evalbench.run import replay
from evalbench.summarize import load, table

WL = ["dev", "ho-stream", "ho-battery", "ho-fuzz", "corpus"]


def sh(*cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("worker")
    ap.add_argument("clone")
    ap.add_argument("sha")
    ap.add_argument("--note", default="")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--skip-ab", action="store_true")
    ap.add_argument("--skip-gates", action="store_true")
    args = ap.parse_args()
    co = sh(os.path.join(HERE, "fetch.sh"), args.clone, args.sha, args.worker)
    sha = os.path.basename(co).rsplit("-", 1)[1]
    tag = f"{args.worker}-{sha}"
    gdir = os.path.join(ROOT, "gate-results", tag)
    log = sh("git", "-C", co, "log", "--oneline", "9bafaa5..HEAD")
    stat = sh("git", "-C", co, "diff", "--stat", "9bafaa5", "HEAD", "--", "satassume")
    # gates
    if not args.skip_gates:
        p = subprocess.run([sys.executable, "-m", "evalbench.gates", co, "--out", gdir], text=True,
                           capture_output=True)
        print(p.stdout[-3000:], p.stderr[-3000:])
    with open(os.path.join(gdir, "gates.json")) as f:
        g = json.load(f)
    # counters (deterministic; orion)
    base_c = json.load(open(os.path.join(HERE, "baseline-counters-9bafaa5.json")))
    cand_c = {w: replay(co, w, "--counters", "--phases") for w in WL}
    # A/B
    ab_rows = None
    if not args.skip_ab:
        env = dict(os.environ, ROUNDS=str(args.rounds))
        sh(os.path.join(HERE, "pareto.sh"), "sync", f"{tag}={co}")
        subprocess.run([os.path.join(HERE, "pareto.sh"), "ab", f"ab-{tag}", "base", tag], env=env,
                       check=True, capture_output=True, text=True)
        ab_rows = table(load(os.path.join(ROOT, "bench-results", f"ab-{tag}", f"ab-{tag}.jsonl")))
    write(args, tag, co, log, stat, g, base_c, cand_c, ab_rows)


def write(args, tag, co, log, stat, g, base_c, cand_c, ab_rows):
    L = [f"# {tag}", "", f"Candidate: `{args.clone}` at `{tag.rsplit('-', 1)[1]}` ({args.note})", "",
         "Commits over 9bafaa5:", "```", log, "```", "", "```", stat, "```", ""]
    ok = g.get("pass")
    L += ["## Gates: " + ("PASS" if ok else "FAIL"), "", "| check | result | detail |", "|---|---|---|"]
    for c in g["checks"]:
        det = c.get("summary") or (f"{c.get('n_diff', 0)} of {c.get('n')} differ" if "n" in c else c.get("error", ""))
        L.append(f"| {c['name']} | {'pass' if c['ok'] else 'FAIL'} | {det} |")
    for c in g["checks"]:
        if not c["ok"]:
            L += ["", f"### {c['name']}: differences", ""]
            for d in c.get("diffs", [])[:200]:
                L.append(f"* #{d['i']}: `{d.get('q', '')}`: base `{d['base']}`, cand `{d['cand']}`")
            if len(c.get("diffs", [])) > 200:
                L.append(f"* ... {len(c['diffs']) - 200} more (gate-results/{tag}/gates.json)")
            for n in c.get("newly_failing", []) + c.get("missing", []):
                L.append(f"* {n}")
    L += ["", "## Time (pareto1, pinned, alternating cold processes; speedup = base/cand, paired by round)", ""]
    if ab_rows:
        L += ["| workload | metric | base median s | cand median s | speedup | per-round ratio cand/base |",
              "|---|---|---|---|---|---|"]
        for r in ab_rows:
            L.append(f"| {r['workload']} | {r['metric']} | {r['base_med']:.3f} | {r['cand_med']:.3f} | "
                     f"**{1 / r['ratio_med']:.3f}x** | {r['ratio_min']:.3f}..{r['ratio_max']:.3f} ({r['rounds']}) |")
        L += ["", "Noise floor (A/A, baseline vs itself, BASELINE.md): see there; treat |speedup - 1| below "
              "the A/A spread as no change."]
    else:
        L.append("(not run)")
    L += ["", "## Counters (deterministic; cand vs base, delta)", ""]
    keys = ["context_builds", "set_checks", "sessions", "queries", "escalations", "searches", "relevant",
            "consistency_checks", "cache_hits", "solver_conflicts", "solver_decisions", "solver_propagations",
            "solver_clauses", "solver_vars"]
    L += ["| counter | " + " | ".join(WL) + " |", "|---|" + "---|" * len(WL)]
    for k in keys:
        cells = []
        for w in WL:
            b = base_c[w]["counters"].get(k, 0)
            c = cand_c[w]["counters"].get(k, 0)
            cells.append(f"{c} ({c - b:+d})" if c != b else f"{c}")
        L.append(f"| {k} | " + " | ".join(cells) + " |")
    L += ["", "Phases on dev, instrumented (s, orion, indicative): " + ", ".join(
        f"{k} {cand_c['dev']['phases'].get(k, 0):.3f} (base {base_c['dev']['phases'].get(k, 0):.3f})"
        for k in sorted(base_c["dev"]["phases"]))]
    miss = cand_c["dev"].get("missing")
    if miss:
        L.append(f"Instrumentation could not find {miss}: those counters are not comparable.")
    L += ["", "The stream is satassume's home ground (its corpus was recorded from the same SymPy tests)."]
    path = os.path.join(HERE, "results", f"{tag}.md")
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    print(path)


if __name__ == "__main__":
    main()
