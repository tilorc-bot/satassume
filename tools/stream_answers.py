"""Replay a recorded query stream through one engine and save the answers.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python \\
        tools/stream_answers.py STREAM OUT.json MODE

MODE ``default`` (``Engine()``) or ``free`` (``Engine(uninterpreted="free")``).
Replays every query of ``stream.pkl`` in order through ``sympy_api.ask`` on
one engine (as ``tools/ab.py`` does) and writes one answer per query
(true / false / null / "error") plus the wall time.  Compare two runs with
``tools/stream_answers_compare.py``.  ``tools/gate2_stream.py`` turns
gate2's frozen queries into a stream file.
"""
import json, pickle, sys, time

from satassume.engine import Engine
from satassume.sympy_api import ask


def main():
    stream = pickle.load(open(sys.argv[1], "rb"))
    out_path, mode = sys.argv[2], sys.argv[3]
    eng = Engine(**{"default": {}, "free": {"uninterpreted": "free"}}[mode])
    outs = []
    t0 = time.perf_counter()
    for p, a, _rec in stream:
        try:
            outs.append(ask(p, a, engine=eng))
        except ValueError:
            outs.append("error")
    dt = time.perf_counter() - t0
    print(f"{mode}: {len(outs)} queries in {dt:.1f}s")
    json.dump({"mode": mode, "seconds": dt, "answers": outs}, open(out_path, "w"))


if __name__ == "__main__":
    main()
