"""Free-Boolean re-measurement: interleaved timing of default vs free.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/scripts/free_ab.py \\
        [STREAM] [--rounds N]

Like ``tools/ab.py`` but on one checkout: each run is a fresh process of
``free_stream.py`` (the stream replay through ``sympy_api.ask`` on one
engine), alternating ``default``, ``free``, ``default``, ... ``--rounds``
times (default 3).  Prints every run's replay time, the best-of per mode
and the relative change, and checks that each mode answers the same in
every round.
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
rounds = int(sys.argv[sys.argv.index("--rounds") + 1]) if "--rounds" in sys.argv else 3
if args and args[-1] == str(rounds):
    args = args[:-1]
stream = args[0] if args else os.path.expanduser("~/.cache/satassume/stream.pkl")
best, answers = {}, {}
with tempfile.TemporaryDirectory() as tmp:
    for r in range(rounds):
        for mode in ("default", "free"):
            out = os.path.join(tmp, f"{mode}.json")
            subprocess.run([sys.executable, os.path.join(HERE, "free_stream.py"), stream, out, mode],
                           check=True, capture_output=True, timeout=240)
            res = json.load(open(out))
            print(f"round {r + 1} {mode:7s} {res['seconds']:.3f}s", flush=True)
            best[mode] = min(best.get(mode, 1e9), res["seconds"])
            if answers.setdefault(mode, res["answers"]) != res["answers"]:
                print(f"  {mode}: answers differ from round 1")
d, f = best["default"], best["free"]
print(f"best default {d:.3f}s  free {f:.3f}s  change {100 * (f - d) / d:+.1f}%")
