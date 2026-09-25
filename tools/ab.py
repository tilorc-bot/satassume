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

``--allow-more-definite`` (the acceptance rule of the fact-lattice plan):
an answer that is None in the recording and True/False now is *more
definite*; it is counted and listed (``--show K``, ``--more-definite-out
PATH`` writes all of them as JSON lines) but does not fail the run.  A
contradiction (the other definite value), a less definite answer (None
where the recording is definite) or a ValueError fails as before.  Since
the recording no longer pins those answers, two more checks apply: a query
more definite on ref must get the same answer from cand (cand may add
more definite answers, not drop or flip ref's), and each side's more
definite answers must be the same in every round.  ``--more-definite-out``
needs the flag and is truncated at start-up.  Without the flag every
difference fails (the default is unchanged).

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
bad = 0; first = None; diffs = []
t0 = time.perf_counter()
for i, (p, a, r) in enumerate(stream):
    try:
        got = ask(p, a)
    except ValueError:
        got = "error"
    if got is not r:
        bad += 1
        if first is None: first = (i, str(p), str(a), str(r), str(got))
        diffs.append((i, str(p), str(a), r, got))
dt = time.perf_counter() - t0
print(json.dumps({"n": len(stream), "seconds": dt, "bad": bad, "first_bad": first, "diffs": diffs}))
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


def classify(recorded, got) -> str:
    """``more`` (None -> True/False), ``less`` (True/False -> None),
    ``contradiction`` (True <-> False) or ``error`` (anything else)."""
    def definite(x):
        return x is True or x is False     # not ``in (True, False)``: 1 == True
    if recorded is None and definite(got):
        return "more"
    if definite(recorded) and got is None:
        return "less"
    if definite(recorded) and definite(got):
        return "contradiction"
    return "error"


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
    ap.add_argument("--allow-more-definite", action="store_true",
                    help="more definite answers (None -> True/False) are listed, not failures")
    ap.add_argument("--show", type=int, default=10, help="with --allow-more-definite: list up to K")
    ap.add_argument("--more-definite-out", help="with --allow-more-definite: write them all here")
    args = ap.parse_args()
    for d in (args.ref, args.cand):
        if not os.path.isdir(os.path.join(d, "satassume")):
            raise SystemExit(f"{d}: no satassume package there")
    if not os.path.exists(args.stream):
        raise SystemExit(f"stream not found: {args.stream}")

    if args.more_definite_out and not args.allow_more_definite:
        ap.error("--more-definite-out needs --allow-more-definite")
    if args.more_definite_out:                # truncated now, so a failed run leaves no stale file
        for path in (args.more_definite_out, args.more_definite_out + ".ref"):
            open(path, "w").close()

    times = {"ref": [], "cand": []}
    ok = True
    more = {}                               # (side, index) -> diff, first run of each side
    first_more = {}                         # side -> {index: answer} of its first run
    for r in range(args.rounds):
        for side, d in (("ref", args.ref), ("cand", args.cand)):
            res = run_once(d, args)
            times[side].append(res["seconds"])
            flag = ""
            if args.allow_more_definite:
                kinds = {}
                run_more = {}
                for diff in res["diffs"]:
                    k = classify(diff[3], diff[4])
                    kinds.setdefault(k, []).append(diff)
                    if k == "more":
                        more.setdefault((side, diff[0]), diff)
                        run_more[diff[0]] = diff[4]
                failing = [x for k, xs in kinds.items() if k != "more" for x in xs]
                flag = ("  " + ", ".join(f"{len(xs)} {k}" for k, xs in sorted(kinds.items()))) if kinds else ""
                if failing:
                    ok = False
                    flag += f"  MISMATCH, first {failing[0]}"
                # The more definite answers of a side must be the same in every round:
                # the recording no longer pins them, so a round that differs is not caught
                # by the comparison with the recording.
                if side not in first_more:
                    first_more[side] = run_more
                elif run_more != first_more[side]:
                    ok = False
                    changed = sorted(set(run_more.items()) ^ set(first_more[side].items()))
                    flag += f"  UNSTABLE more definite answers across rounds, first {changed[0]}"
            elif res["bad"]:
                ok = False
                flag = f"  MISMATCH {res['bad']} answers, first {res['first_bad']}"
            print(f"round {r+1} {side:4s} {res['seconds']:.3f}s ({1000*res['seconds']/res['n']:.3f} ms/query){flag}",
                  flush=True)
    best_ref, best_cand = min(times["ref"]), min(times["cand"])
    change = 100.0 * (best_cand - best_ref) / best_ref
    if args.allow_more_definite:
        # ref and cand agree with each other only where both agree with the recording;
        # every query more definite on ref must get the same answer from cand.
        ref_more, cand_more = first_more.get("ref", {}), first_more.get("cand", {})
        # A query more definite on ref only means cand answered it like the recording
        # (None; anything else already failed): cand is less definite than ref.
        clash = sorted(i for i in ref_more if cand_more.get(i) is not ref_more[i])
        if clash:
            ok = False
            i = clash[0]
            print(f"  REF AND CAND DIFFER on {len(clash)} of ref's more definite answers, "
                  f"first #{i}: ref {ref_more[i]}, cand {cand_more.get(i)}", flush=True)
    verdict = "answers match" if ok else "ANSWER MISMATCH"
    if args.allow_more_definite:
        for side in ("ref", "cand"):
            ds = sorted(v for (sd, _), v in more.items() if sd == side)
            if ds:
                verdict += f"; {side}: {len(ds)} more definite"
            for diff in ds[:args.show]:
                print(f"  more definite ({side}) #{diff[0]}: {diff[1]} | {diff[2]}: "
                      f"recorded {diff[3]}, now {diff[4]}")
            if args.more_definite_out:        # always written, so no stale file survives
                with open(args.more_definite_out if side == "cand" else args.more_definite_out + ".ref", "w") as f:
                    for diff in ds:
                        f.write(json.dumps({"i": diff[0], "prop": diff[1], "assum": diff[2],
                                            "recorded": diff[3], "now": diff[4]}) + "\n")
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
