"""Replay a query stream in one answer mode of ``ask`` (issue #317), and
check a mode's answers against the full ones.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python tools/ask_modes.py run STREAM OUT.json MODE
    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python tools/ask_modes.py check FULL.json OTHER.json

MODE: ``full`` (the defaults), ``true_only``, ``unchecked``
(``check_consistency=False``) or ``unchecked_true_only``.  ``run`` replays
every query of the stream (``stream.pkl`` or a ``gate2_stream.py`` file) in
order on one ``Engine()``, as ``tools/stream_answers.py`` does, and writes
the answers (true / false / null / "error") and the wall time.

``check`` compares a mode's answers with the full ones, query by query:

* where the full answer is an error, a checked mode must raise too and an
  unchecked one may answer anything (vacuous);
* elsewhere a ``true_only`` mode answers True exactly where the full
  answer is True and None otherwise, and an unchecked mode the full
  answer or None (a lost answer); never another definite answer, never an
  error.

It prints the counts per kind and exits 1 on a violation.
"""
import json
import pickle
import sys
import time

MODES = {
    "full": {},
    "true_only": {"true_only": True},
    "unchecked": {"check_consistency": False},
    "unchecked_true_only": {"check_consistency": False, "true_only": True},
}


def run(stream_path, out_path, mode):
    from satassume.engine import Engine
    from satassume.sympy_api import ask
    kw = MODES[mode]
    stream = pickle.load(open(stream_path, "rb"))
    eng = Engine()
    outs = []
    t0 = time.perf_counter()
    for p, a, _rec in stream:
        try:
            outs.append(ask(p, a, engine=eng, **kw))
        except ValueError:
            outs.append("error")
    dt = time.perf_counter() - t0
    json.dump({"mode": mode, "seconds": dt, "answers": outs}, open(out_path, "w"))
    print(f"{mode}: {len(outs)} queries, {dt:.3f} s")


def check(full_path, other_path):
    full = json.load(open(full_path))
    other = json.load(open(other_path))
    mode = other["mode"]
    true_only = MODES[mode].get("true_only", False)
    checked = MODES[mode].get("check_consistency", True)
    counts, bad = {}, []
    for i, (f, g) in enumerate(zip(full["answers"], other["answers"])):
        if f == "error":
            kind = "error kept" if g == "error" else f"error -> {g}"
            ok = g == "error" or not checked
        else:
            expect = None if true_only and f is not True else f
            if g == expect:
                kind = "same" if g == f else "False -> None"
            elif g is None and not checked:
                kind = f"lost {f}"
            else:
                kind, ok = f"VIOLATION {f} -> {g}", False
            ok = not kind.startswith("VIOLATION")
        counts[kind] = counts.get(kind, 0) + 1
        if not ok:
            bad.append(i)
    print(f"{mode} against {full['mode']}: {len(full['answers'])} queries")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
    if bad:
        print(f"  violations at {bad[:20]}")
        sys.exit(1)


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    {"run": run, "check": check}[cmd](*args)
