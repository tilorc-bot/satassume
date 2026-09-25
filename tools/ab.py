"""Interleaved A/B of the refine-stream replay between two satassume checkouts.

    PYTHONHASHSEED=0 python tools/ab.py REF_DIR CAND_DIR [--rounds 2] [--stream PATH]
                                        [--sympy PATH] [--python PATH] [--label TEXT]

Runs the replay of ``stream.pkl`` (13,877 recorded ``ask`` calls, see
``tools/refine_replay.py``) in a fresh process per run, alternating
reference, candidate, reference, candidate, ... ``--rounds`` times, each a
cold pass.  The replay loop is embedded here so both sides run the *same*
loop whatever their own ``tools/refine_replay.py`` says.  Prints every run,
the best-of for each side and the relative change, and exits 1 if any run
of either side returns an answer that differs from the recording (the
recording is the oracle, so ref and cand agreeing with it means they agree
with each other).

Defaults: ``--stream`` is ``$SATASSUME_STREAM`` or
``~/.cache/satassume/stream.pkl``; ``--sympy`` is ``$SATASSUME_SYMPY`` or
``/home/tilo/sympy``; ``--python`` is the interpreter running this script.

On the Pi container::

    /work/.mamba/envs/sympy/bin/python tools/ab.py /work/src/perf-ref /work/src/perf-work \
        --stream /work/src/bench/stream.pkl --sympy /work/src/sympy-pin

Nothing else should run on the machine while this does; the two agents of
the September 2026 rounds each measure on their own machine for that reason.
"""
import argparse, json, os, subprocess, sys, time

REPLAY = r'''
import pickle, sys, time, json
stream = pickle.load(open(sys.argv[1], "rb"))
from satassume.sympy_api import ask
bad = 0; first = None
t0 = time.perf_counter()
for i, (p, a, r) in enumerate(stream):
    got = ask(p, a)
    if got is not r:
        bad += 1
        if first is None: first = (i, str(p), str(a), str(r), str(got))
dt = time.perf_counter() - t0
print(json.dumps({"n": len(stream), "seconds": dt, "bad": bad, "first_bad": first}))
'''


def run_once(checkout, args):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = os.path.abspath(checkout) + os.pathsep + args.sympy
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    p = subprocess.run([args.python, "-c", REPLAY, args.stream], cwd=checkout, env=env,
                       capture_output=True, text=True, timeout=args.timeout)
    if p.returncode != 0:
        sys.stderr.write(p.stdout + p.stderr)
        raise SystemExit(f"replay crashed in {checkout}")
    return json.loads(p.stdout.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("ref"); ap.add_argument("cand")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--stream", default=os.environ.get("SATASSUME_STREAM",
                    os.path.expanduser("~/.cache/satassume/stream.pkl")))
    ap.add_argument("--sympy", default=os.environ.get("SATASSUME_SYMPY", "/home/tilo/sympy"))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--timeout", type=float, default=240.0, help="per run, seconds")
    ap.add_argument("--label", default="", help="free text echoed in the summary line")
    ap.add_argument("--json", action="store_true", help="also print a JSON summary line")
    args = ap.parse_args()
    for d in (args.ref, args.cand):
        if not os.path.isdir(os.path.join(d, "satassume")):
            raise SystemExit(f"{d}: no satassume package there")
    if not os.path.exists(args.stream):
        raise SystemExit(f"stream not found: {args.stream}")

    times = {"ref": [], "cand": []}
    ok = True
    for r in range(args.rounds):
        for side, d in (("ref", args.ref), ("cand", args.cand)):
            res = run_once(d, args)
            times[side].append(res["seconds"])
            flag = ""
            if res["bad"]:
                ok = False
                flag = f"  MISMATCH {res['bad']} answers, first {res['first_bad']}"
            print(f"round {r+1} {side:4s} {res['seconds']:.3f}s ({1000*res['seconds']/res['n']:.3f} ms/query){flag}",
                  flush=True)
    best_ref, best_cand = min(times["ref"]), min(times["cand"])
    change = 100.0 * (best_cand - best_ref) / best_ref
    verdict = "answers match" if ok else "ANSWER MISMATCH"
    print(f"best-of-{args.rounds}: ref {best_ref:.3f}s  cand {best_cand:.3f}s  "
          f"change {change:+.1f}% ({'faster' if change < 0 else 'slower'}); {verdict}"
          + (f"  [{args.label}]" if args.label else ""))
    if args.json:
        print(json.dumps({"ref": times["ref"], "cand": times["cand"], "best_ref": best_ref,
                          "best_cand": best_cand, "change_pct": change, "match": ok,
                          "label": args.label}))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
