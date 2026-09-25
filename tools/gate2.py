"""Second gate: SymPy's own assumption-test queries, replayed against frozen answers.

    python tools/gate2.py CHECKOUT [--frozen PATH] [--sympy PATH] [--python PATH] [--show K]
    python tools/gate2.py CHECKOUT --freeze RECORDED.jsonl [--frozen OUT]

The queries are the ``sympy.ask`` / ``_ask_recursive`` calls SymPy's
assumption tests make, recorded with ``tools/record_queries.py`` (see
``agent-reports/2026-09-25-perf2-0.2-second-gate.md`` for how).  Every
new-system record is replayed in recording order through
``satassume.sympy_api.ask`` with one fresh ``Engine``, in a fresh process
whose ``PYTHONPATH`` is ``CHECKOUT`` and the SymPy pin, so any satassume
checkout can be gated with this script (records are rebuilt with this
directory's ``compare.rebuild``).

``--freeze`` writes the frozen file: one JSON line per replayable record
with the query (``prop``, ``assum`` as ``srepr``), SymPy's recorded answer
(``sympy``), the scope group of ``tools/compare.py`` (``in-scope`` or
``out:<category>``) and CHECKOUT's answer (``answer``: true / false / null
/ ``"error:ValueError"``).  Records that cannot be rebuilt are left out.

Without ``--freeze`` it replays the frozen file against CHECKOUT and exits
1 if any answer differs from the frozen one (in any group; the in-scope
count is printed separately), 0 otherwise.

Defaults: ``--frozen`` is ``$SATASSUME_GATE2`` or
``~/.cache/satassume/gate2-frozen.jsonl``; ``--sympy`` is
``$SATASSUME_SYMPY`` or ``/home/tilo/sympy``; ``--python`` is the running
interpreter.  On the Pi::

    /work/.mamba/envs/sympy/bin/python tools/gate2.py /work/src/perf-work \\
        --frozen /work/src/bench/gate2-frozen.jsonl --sympy /work/src/sympy-pin
"""
import argparse, collections, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

REPLAY = r'''
import json, sys, time
sys.path.append(sys.argv[2])                  # this tools/ dir, for compare.rebuild
from compare import rebuild
from satassume import Engine
from satassume.sympy_api import ask, out_of_scope
eng = Engine()
out = []
t_ask = 0.0
t0 = time.perf_counter()
for line in open(sys.argv[1]):
    rec = json.loads(line)
    if rec["kind"] not in ("ask", "rec"):
        continue
    try:
        prop = rebuild(rec["prop"]); assum = rebuild(rec["assum"])
        cat = out_of_scope(prop, assum)
    except Exception:
        out.append({"group": None, "answer": "unreplayable"})
        continue
    t = time.perf_counter()
    try:
        got = ask(prop, assum, engine=eng)
    except ValueError:
        got = "error:ValueError"
    except Exception as e:
        got = "crash:" + type(e).__name__
    t_ask += time.perf_counter() - t
    out.append({"group": "in-scope" if cat is None else "out:" + cat, "answer": got})
print(json.dumps({"results": out, "seconds": time.perf_counter() - t0, "ask_seconds": t_ask}))
'''


def replay(checkout, path, args):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = os.path.abspath(checkout) + os.pathsep + args.sympy
    p = subprocess.run([args.python, "-c", REPLAY, path, HERE], cwd=checkout, env=env,
                       capture_output=True, text=True, timeout=args.timeout)
    if p.returncode != 0:
        sys.stderr.write(p.stdout[-3000:] + p.stderr[-3000:])
        raise SystemExit(f"replay crashed in {checkout}")
    return json.loads(p.stdout.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("checkout")
    ap.add_argument("--freeze", metavar="RECORDED", help="write the frozen file from this recording")
    ap.add_argument("--frozen", default=os.environ.get("SATASSUME_GATE2",
                    os.path.expanduser("~/.cache/satassume/gate2-frozen.jsonl")))
    ap.add_argument("--sympy", default=os.environ.get("SATASSUME_SYMPY", "/home/tilo/sympy"))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--timeout", type=float, default=240.0)
    ap.add_argument("--show", type=int, default=10, help="print up to K changed answers")
    args = ap.parse_args()
    if not os.path.isdir(os.path.join(args.checkout, "satassume")):
        raise SystemExit(f"{args.checkout}: no satassume package there")

    if args.freeze:
        recs = [r for r in map(json.loads, open(args.freeze)) if r["kind"] in ("ask", "rec")]
        res = replay(args.checkout, args.freeze, args)
        n = 0
        groups = collections.Counter()
        with open(args.frozen, "w") as f:
            for rec, r in zip(recs, res["results"]):
                if r["answer"] == "unreplayable":
                    continue
                n += 1
                groups[r["group"]] += 1
                f.write(json.dumps({"kind": rec["kind"], "prop": rec["prop"], "assum": rec["assum"],
                                    "sympy": rec["value"], "group": r["group"],
                                    "answer": r["answer"]}) + "\n")
        print(f"froze {n} of {len(recs)} records ({len(recs) - n} unreplayable) to {args.frozen}; "
              f"groups {dict(groups)}; replay {res['seconds']:.2f}s (ask {res['ask_seconds']:.2f}s)")
        return 0

    frozen = [json.loads(l) for l in open(args.frozen)]
    full = replay(args.checkout, args.frozen, args)
    res = full["results"]
    changed = collections.Counter()
    total = collections.Counter(r["group"] for r in frozen)
    shown = 0
    for i, (want, got) in enumerate(zip(frozen, res)):
        if got["answer"] != want["answer"]:
            changed[want["group"]] += 1
            if shown < args.show:
                shown += 1
                print(f"CHANGED #{i} [{want['group']}] {want['prop']} | {want['assum']}: "
                      f"frozen {want['answer']} now {got['answer']} (sympy {want['sympy']})")
    n_changed = sum(changed.values())
    print(f"gate2: {len(frozen)} records ({total['in-scope']} in scope); changed {n_changed} "
          f"({changed['in-scope']} in scope){' ' + str(dict(changed)) if n_changed else ''}; "
          + ("FAIL" if n_changed else "answers match")
          + f"; replay {full['seconds']:.2f}s (ask {full['ask_seconds']:.2f}s)")
    return 1 if n_changed else 0


if __name__ == "__main__":
    sys.exit(main())
