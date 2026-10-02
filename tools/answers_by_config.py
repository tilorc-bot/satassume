"""Answers of the corpus and the refine stream under several engine
configurations, for an answer comparison between two checkouts (#113).

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python \\
        tools/answers_by_config.py queries.jsonl stream.pkl OUT.json

Run it once from each checkout (fresh processes: see docs/agents.md,
"Gating" 7) and compare the two JSON files entry by entry.  The corpus
records (``ask``, ``rec`` and ``old``) are asked with a fresh engine per
query under every preset of ``harness.state.PRESETS``; the refine stream
is replayed in order through one engine per config for ``default``,
``tight``, ``lean``, ``budget``, ``notransfer`` and ``whole``.  An answer
is ``repr`` of the result, ``"error"`` for ``ValueError`` (inconsistent
assumptions) or ``"exc:<type>"``.
"""
import json
import pickle
import sys

from compare import rebuild
from sympy import Q

from harness.state import PRESETS
from satassume.sympy_api import ask


def run(p, a, eng):
    try:
        return repr(ask(p, a, engine=eng))
    except ValueError:
        return "error"
    except Exception as e:  # noqa: BLE001 (compared as an outcome)
        return "exc:" + type(e).__name__


def main():
    corpus, unreadable = [], 0
    with open(sys.argv[1]) as fh:
        for line in fh:
            r = json.loads(line)
            try:
                if r["kind"] in ("ask", "rec"):
                    corpus.append((rebuild(r["prop"], evaluated=True),
                                   rebuild(r["assum"], evaluated=True)))
                elif r["kind"] == "old":
                    corpus.append((getattr(Q, r["fact"])(rebuild(r["expr"], evaluated=True)), True))
            except Exception:  # noqa: BLE001 (counted, printed below)
                unreadable += 1
    out = {"corpus": {}, "stream": {}}
    for name, cfg in PRESETS.items():
        out["corpus"][name] = [run(p, a, cfg.make()) for p, a in corpus]
    with open(sys.argv[2], "rb") as fh:
        stream = pickle.load(fh)
    for name in ("default", "tight", "lean", "budget", "notransfer", "whole"):
        eng = PRESETS[name].make()
        out["stream"][name] = [run(p, a, eng) for p, a, _ in stream]
    with open(sys.argv[3], "w") as fh:
        json.dump(out, fh)
    print("corpus", len(corpus), "unreadable", unreadable, "stream", len(stream))


if __name__ == "__main__":
    main()
