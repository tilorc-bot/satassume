"""Shared pieces: paths, workloads, the answer encoding.

Every workload is a list of ``(proposition, assumptions)`` pairs replayed in
order through ``satassume.sympy_api.ask`` in ONE process (cold: the process
starts with nothing but imports).  Workload names:

* ``dev``            the quick dev set (``split.json``), recorded order, repeats kept
* ``dev-unique``     the dev set without repeated pairs
* ``stream``         the full stream (16,232 queries), recorded order
* ``stream-unique``  the stream's unique pairs (8,393), first-seen order
* ``corpus``         satassume's corpus (2,863), recorded order
* ``battery``        the battery stream (16,386), recorded order
* held-out (evaluator only): ``ho-stream`` (the stream's queries whose set is
  not a dev set), ``ho-battery`` (battery-stream queries whose pair is not in
  the stream and whose set is not a dev set: 1,101 queries),
  ``ho-fuzz`` (the fresh fuzz seed, ``fuzz.py``)
* gates only: ``stream-shuffled`` (unique stream, a fixed shuffle)
"""
import json
import os
import pickle
import random

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.environ.get("SA_EVAL_DATA", "/home/tilo/dev/rete-impl/data")
#: a copy of ~/maintenance/sympy-pin (ext/sympy, revision in ext/sympy.rev)
SYMPY = os.environ.get("SA_EVAL_SYMPY", os.path.join(ROOT, "ext", "sympy"))
SPLIT = os.path.join(HERE, "split.json")
SECRET = os.environ.get("SA_EVAL_SECRET", os.path.join(ROOT, "secret"))
SHUFFLE_SEED = 20261103


def _pkl(name):
    with open(os.path.join(DATA, name + ".pkl"), "rb") as f:
        return pickle.load(f)


def _unique(pairs):
    seen, out = set(), []
    for q in pairs:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def split():
    with open(SPLIT) as f:
        return json.load(f)


def workload(name):
    """The pairs of workload ``name`` (see the module docstring)."""
    if name in ("stream", "corpus", "battery"):
        rows = _pkl({"battery": "battery-stream"}.get(name, name))
        return [(p, a) for p, a, _ in rows]
    if name == "stream-unique":
        return _unique(workload("stream"))
    if name == "stream-shuffled":
        qs = workload("stream-unique")
        random.Random(SHUFFLE_SEED).shuffle(qs)
        return qs
    if name in ("dev", "dev-unique"):
        st = workload("stream")
        qs = [st[i] for i in split()["dev_indices"]]
        return _unique(qs) if name == "dev-unique" else qs
    if name == "ho-stream":
        devsets = _dev_sets()
        return [(p, a) for p, a in workload("stream") if a not in devsets]
    if name == "ho-battery":
        # the battery stream repeats 92% of the stream's pairs: only the
        # battery's own pairs (not in the stream, set not a dev set) count here
        devsets, seen = _dev_sets(), set(workload("stream"))
        return [(p, a) for p, a in workload("battery") if a not in devsets and (p, a) not in seen]
    if name == "ho-fuzz":
        from evalbench.fuzz import queries
        return queries(secret_seed())
    if name == "final-fuzz":
        # morning readout: a second secret seed made at readout time (never shown to workers)
        from evalbench.fuzz import queries
        return queries(secret_seed("final_fuzz_seed.txt"))
    raise KeyError(name)


def _dev_sets():
    st = _pkl("stream")
    return {st[i][1] for i in split()["dev_indices"]}


def secret_seed(fname="fuzz_seed.txt"):
    with open(os.path.join(SECRET, fname)) as f:
        return int(f.read().split()[0])


def enc(r):
    """An answer as JSON: True/False/None, or "ValueError"/"<Type>" for a raise."""
    return r


def ask_all(ask, pairs, clock=None, per_query=None):
    """Answers of ``pairs`` in order; with ``clock``, per-query seconds into ``per_query``."""
    out = []
    for p, a in pairs:
        if clock is not None:
            t = clock()
        try:
            r = ask(p, a)
            if r is not None and r is not True and r is not False:
                r = "non-bool " + repr(r)
        except ValueError:
            r = "ValueError"
        except Exception as e:  # noqa: BLE001 - recorded, compared, reported
            r = "raise " + type(e).__name__
        if clock is not None:
            per_query.append(clock() - t)
        out.append(r)
    return out


SATSIMP = os.environ.get("SA_EVAL_SATSIMP", os.path.join(ROOT, "ext", "satsimp"))


def shim():
    """A directory holding only ``evalbench`` (a symlink), so that the
    harness is importable without putting sa-eval's own satassume on the path."""
    d = os.environ.get("SA_EVAL_SHIM") or os.path.join(ROOT, ".shim")
    link = os.path.join(d, "evalbench")
    if not os.path.exists(link):
        os.makedirs(d, exist_ok=True)
        os.symlink(HERE, link)
    return d


def env_for(checkout, satsimp=False):
    """Environment for a child process that imports satassume from ``checkout``
    (and, with ``satsimp``, satsimp's checkout first: its ``tests`` package)."""
    env = dict(os.environ)
    head = [SATSIMP] if satsimp else []
    env["PYTHONPATH"] = os.pathsep.join([*head, os.path.abspath(checkout), SYMPY, shim()])
    env["PYTHONHASHSEED"] = "0"
    env.pop("PYTHONSTARTUP", None)
    return env
