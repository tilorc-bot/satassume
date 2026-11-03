"""Judge one candidate: gates (orion), pinned A/B (pareto1), counters; writes
evalbench/results/<worker>-<sha>.md and prints the one-line verdict.

    python -m evalbench.judge WORKER CLONE SHA [--note "one line"] [--rounds 5] [--skip-ab]
        [--skip-gates] [--build "CMD"] [--remote-build "CMD"] [--ab-extra NAME] [--check-modules m1,m2]

--build: shell command run in the snapshot worktree on orion before the gates
(e.g. a Cython build_ext --inplace).  --remote-build: shell command run in the
synced tree on pareto1 (shared lease) before the A/B.  --check-modules: print
where these modules load from on both machines (an .so built for the other
arch is silently ignored).  --ab-extra: an already-synced tree (pareto1
~/sa-eval-bench/src/NAME) timed in the same A/B invocation.
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
    ap.add_argument("--build")
    ap.add_argument("--remote-build")
    ap.add_argument("--ab-extra", action="append", default=[])
    ap.add_argument("--check-modules", default="")
    ap.add_argument("--approved-test", action="append", default=[],
                    help="test node id whose failure forward-chain-3b approved as the design change")
    ap.add_argument("--reuse-ab", action="store_true", help="summarize the existing bench-results/ab-TAG run")
    args = ap.parse_args()
    co = sh(os.path.join(HERE, "fetch.sh"), os.path.abspath(args.clone), args.sha, args.worker)
    sha = os.path.basename(co).rsplit("-", 1)[1]
    tag = f"{args.worker}-{sha}"
    gdir = os.path.join(ROOT, "gate-results", tag)
    log = sh("git", "-C", co, "log", "--oneline", "9bafaa5..HEAD")
    stat = sh("git", "-C", co, "diff", "--stat", "9bafaa5", "HEAD", "--", "satassume")
    loaded = {}
    if args.build:
        subprocess.run(["sh", "-c", args.build], cwd=co, check=True, capture_output=True, text=True)
    if args.check_modules:
        loaded["orion"] = where(co, args.check_modules)
        print("orion loads:", loaded["orion"], flush=True)
    # gates
    if not args.skip_gates:
        p = subprocess.run([sys.executable, "-m", "evalbench.gates", co, "--out", gdir], text=True,
                           capture_output=True)
        print(p.stdout[-3000:], p.stderr[-3000:])
    with open(os.path.join(gdir, "gates.json")) as f:
        g = json.load(f)
    for c in g["checks"]:
        if c["name"].startswith("tests_") and args.approved_test:
            c["approved"] = [n for n in c.get("newly_failing", []) if n in args.approved_test]
            c["newly_failing"] = [n for n in c.get("newly_failing", []) if n not in args.approved_test]
            c["ok"] = not c["newly_failing"] and not c.get("missing")
    g["pass"] = all(c["ok"] for c in g["checks"])
    # counters (deterministic; orion)
    base_c = json.load(open(os.path.join(HERE, "baseline-counters-9bafaa5.json")))
    cand_c = {}
    for w in WL:
        try:
            cand_c[w] = replay(co, w, "--counters", "--phases")
        except RuntimeError as e:   # e.g. instrumentation cannot patch compiled modules
            cand_c[w] = {"counters": {}, "phases": {}, "error": str(e)[-500:]}
    # A/B
    ab_rows = None
    if args.reuse_ab:
        ab_rows = table(load(os.path.join(ROOT, "bench-results", f"ab-{tag}", f"ab-{tag}.jsonl")))
    elif not args.skip_ab:
        env = dict(os.environ, ROUNDS=str(args.rounds))
        sh(os.path.join(HERE, "pareto.sh"), "sync", f"{tag}={co}")
        if args.remote_build:
            tree = f"sa-eval-bench/src/{tag}"
            subprocess.run(["rsync", "-a", *[os.path.join(co, f) for f in ("setup.py", "pyproject.toml", "README.md")
                                              if os.path.exists(os.path.join(co, f))], f"pareto1:{tree}/"], check=True)
            sh("machine", "run", "pareto1", "-r", f"sa-eval build {tag}", "--", f"cd {tree} && {args.remote_build}")
        if args.check_modules:
            code = f"import importlib; print([importlib.import_module(m).__file__ for m in {args.check_modules.split(',')!r}])"
            loaded["pareto1"] = sh("ssh", "pareto1", f"cd sa-eval-bench && docker run --rm -v $HOME/sa-eval-bench:/work:ro "
                                   f"-e PYTHONPATH=/work/src/{tag}:/work/sympy sa-eval-bench:1 python -c \"{code}\"")
            print("pareto1 loads:", loaded["pareto1"], flush=True)
        subprocess.run([os.path.join(HERE, "pareto.sh"), "ab", f"ab-{tag}", "base", tag, *args.ab_extra], env=env,
                       check=True, capture_output=True, text=True)
        ab_rows = table(load(os.path.join(ROOT, "bench-results", f"ab-{tag}", f"ab-{tag}.jsonl")))
    v = verdict(g, [r for r in ab_rows or [] if r["tree"] == tag] or None)
    write(args, tag, co, log, stat, g, base_c, cand_c, ab_rows, v, loaded)
    print("VERDICT", v)


def where(co, mods):
    from evalbench.common import env_for, shim
    code = f"import importlib; print([importlib.import_module(m).__file__ for m in {mods.split(',')!r}])"
    return subprocess.run([sys.executable, "-c", code], env=env_for(co), cwd=shim(), check=True,
                          capture_output=True, text=True).stdout.strip()


def speed(ab_rows, w, m):
    for r in ab_rows or []:
        if r["workload"] == w and r["metric"] == m:
            return r
    return None


def verdict(g, ab_rows):
    """One line.  Faster on a workload = median speedup >= 1.02x and every
    round's ratio < 1 (the A/A noise floor, BASELINE.md)."""
    if not g.get("pass"):
        bad = [f"{c['name']} ({c.get('n_diff', len(c.get('newly_failing', [])))})" for c in g["checks"] if not c["ok"]]
        return "FAIL (gates: " + ", ".join(bad) + ")"
    if not ab_rows:
        return "gates PASS (no timing)"
    parts, faster, slower = [], 0, 0
    for w, m, lab in [("dev", "seconds", "dev"), ("dev", "none_s", "dev None"), ("ho-stream", "seconds", "held-out stream"),
                      ("ho-stream", "none_s", "held-out None"), ("ho-battery", "seconds", "ho-battery"),
                      ("ho-fuzz", "seconds", "fuzz"), ("corpus", "seconds", "corpus"), ("fork-battery", "ask_s", "fork ask")]:
        r = speed(ab_rows, w, m)
        if r is None:
            continue
        sp = 1 / r["ratio_med"]
        sig = "*" if (sp >= 1.02 and r["ratio_max"] < 1) or (sp <= 1 / 1.02 and r["ratio_min"] > 1) else ""
        faster += sp >= 1.02 and r["ratio_max"] < 1
        slower += sp <= 1 / 1.02 and r["ratio_min"] > 1
        parts.append(f"{lab} {sp:.2f}x{sig}")
    head = "PASS, faster" if faster and not slower else "PASS, mixed" if faster else \
        "PASS, slower" if slower else "PASS, no measurable change"
    return head + " (" + ", ".join(parts) + "; * = beyond A/A noise)"


def write(args, tag, co, log, stat, g, base_c, cand_c, ab_rows, v, loaded=None):
    L = [f"# {tag}", "", f"**Verdict: {v}**", "", f"Candidate: `{args.clone}` at `{tag.rsplit('-', 1)[1]}` ({args.note})", "",
         "Commits over 9bafaa5:", "```", log, "```", "", "```", stat, "```", ""]
    if args.build or args.remote_build:
        L += [f"Build on orion: `{args.build}`", "", f"Build on pareto1: `{args.remote_build}`", ""]
    for m, f in (loaded or {}).items():
        L.append(f"Modules load on {m} from: `{f}`  ")
    if loaded:
        L.append("")
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
    for c in g["checks"]:
        if c.get("approved"):
            L += ["", f"{c['name']}: expected design change, failure approved by forward-chain-3b (not a gate "
                  "failure): " + ", ".join(f"`{n}`" for n in c["approved"])]
    for c in g["checks"]:
        if c.get("flaky"):
            L += ["", f"{c['name']}: failed under xdist on loaded orion but passed on a serial rerun "
                  "(wall-clock-limit tests; not counted): " + ", ".join(f"`{n}`" for n in c["flaky"])]
    L += ["", "## Time (pareto1, pinned, alternating cold processes; speedup = base/cand, paired by round)", ""]
    if ab_rows:
        L += ["| workload | metric | tree | base median s | cand median s | speedup | per-round ratio cand/base |",
              "|---|---|---|---|---|---|---|"]
        for r in ab_rows:
            L.append(f"| {r['workload']} | {r['metric']} | {r['tree']} | {r['base_med']:.3f} | {r['cand_med']:.3f} | "
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
    errs = {w: c["error"] for w, c in cand_c.items() if c.get("error")}
    if errs:
        L.append(f"Counter runs failed on {sorted(errs)} (shown as 0): {next(iter(errs.values()))[-300:]}")
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
