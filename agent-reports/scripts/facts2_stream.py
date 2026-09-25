"""Stage 2 of the fact-lattice plan: the stream under predicate transfer.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python \\
        agent-reports/scripts/facts2_stream.py STREAM OUT.json MODE [--verify SECONDS]

MODE: ``transfer`` (``Engine()``, the branch default), ``free``
(``Engine(uninterpreted="free")``), ``off`` (``Engine(transfer=False)``,
control: must equal the recording).  Replays every query of the stream in
order through ``sympy_api.ask`` on one engine (as ``tools/ab.py`` does) and
classifies each answer against the recording: same, more definite (None ->
True/False), new error (ValueError where the recording answers), lost error,
less definite, contradiction.  With ``--verify S`` every distinct changed
query is also asked of SymPy's ``ask`` (S-second alarm).
"""
import json, pickle, signal, sys, time
from collections import Counter

from satassume.engine import Engine
from satassume.sympy_api import ask


def sympy_answer(p, a, secs):
    from sympy import ask as sask

    def alarm(*_):
        raise TimeoutError
    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(secs)
    try:
        return sask(p, a)
    except TimeoutError:
        return "timeout"
    except ValueError:
        return "error"
    except Exception as e:           # noqa: BLE001 - recorded, not hidden
        return f"exception {type(e).__name__}"
    finally:
        signal.alarm(0)


def classify(got, rec):
    if got is rec or got == rec:
        return "same"
    if rec is None and got in (True, False):
        return "more definite"
    if got == "error":
        return "new error"
    if rec == "error":
        return "lost error"
    if got is None:
        return "less definite"
    return "contradiction"


def main():
    stream = pickle.load(open(sys.argv[1], "rb"))
    out_path, mode = sys.argv[2], sys.argv[3]
    verify = int(sys.argv[sys.argv.index("--verify") + 1]) if "--verify" in sys.argv else None
    kw = {"transfer": {}, "free": {"uninterpreted": "free"}, "off": {"transfer": False}}[mode]
    eng = Engine(**kw)
    t0 = time.perf_counter()
    C = Counter()
    rows = {}
    for i, (p, a, rec) in enumerate(stream):
        try:
            got = ask(p, a, engine=eng)
        except ValueError:
            got = "error"
        rec = "error" if isinstance(rec, str) and rec.startswith("error") else rec
        k = classify(got, rec)
        C[k] += 1
        if k != "same":
            key = (str(p), str(a))
            r = rows.get(key)
            if r is None:
                r = rows[key] = {"i": i, "n": 0, "p": str(p), "a": str(a), "rec": rec,
                                 "got": got, "kind": k, "_q": (p, a)}
            r["n"] += 1
    dt = time.perf_counter() - t0
    print(f"{mode}: {dict(C)} in {dt:.1f}s; distinct changed {len(rows)}")
    if verify:
        V = Counter()
        for r in rows.values():
            p, a = r["_q"]
            t = time.perf_counter()
            r["sympy"] = sympy_answer(p, a, verify)
            r["sympy_s"] = round(time.perf_counter() - t, 2)
            s = r["sympy"]
            V[(r["kind"], "agree" if s == r["got"] else f"sympy {s}")] += 1
        for k, c in sorted(V.items(), key=str):
            print(f"  {c:4d}  {k}")
    for r in rows.values():
        del r["_q"]
    json.dump({"mode": mode, "summary": dict(C), "seconds": dt,
               "rows": sorted(rows.values(), key=lambda r: r["i"])},
              open(out_path, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
