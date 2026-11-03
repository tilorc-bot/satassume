"""Make the dev / held-out split of the stream (run once, before any
candidate existed; the result is evalbench/split.json).

Unit: the assumption set (a stream query's second element).  Every set is
either a dev set or a held-out set; the dev workload is the stream
restricted to the dev sets, in recorded order, repeats kept, each set
capped at its first CAP queries (one set has 1,313).  Sets are drawn
stratified by their size (queries in the stream): within each stratum, in
a seeded random order, until the stratum's dev queries reach FRACTION of
its capped queries.  The seed is the first of 0, 1, ... whose dev set has
TARGET +- 5% queries and a recorded-None share within 1.5 points of the
stream's.
"""
import collections
import json
import os
import pickle
import random

from evalbench.common import DATA, SPLIT

CAP = 200
TARGET = 2000
STRATA = [(1, 4), (5, 19), (20, 79), (80, 299), (300, 10 ** 9)]


def draw(stream, seed):
    occ = collections.defaultdict(list)
    for i, (p, a, r) in enumerate(stream):
        occ[a].append(i)
    capped_total = sum(min(len(v), CAP) for v in occ.values())
    frac = TARGET / capped_total
    rng = random.Random(seed)
    chosen = []
    for lo, hi in STRATA:
        sets = [a for a in occ if lo <= len(occ[a]) <= hi]
        sets.sort(key=lambda a: occ[a][0])          # deterministic before shuffling
        rng.shuffle(sets)
        want = frac * sum(min(len(occ[a]), CAP) for a in sets)
        got = 0
        for a in sets:
            n = min(len(occ[a]), CAP)
            if got + n / 2 > want:
                break
            chosen.append(a)
            got += n
    idx = sorted(i for a in chosen for i in occ[a][:CAP])
    return chosen, idx


def main():
    stream = pickle.load(open(os.path.join(DATA, "stream.pkl"), "rb"))
    none_share = sum(r is None for *_, r in stream) / len(stream)
    for seed in range(1000):
        chosen, idx = draw(stream, seed)
        ns = sum(stream[i][2] is None for i in idx) / len(idx)
        if abs(len(idx) - TARGET) <= TARGET * 0.05 and abs(ns - none_share) <= 0.015:
            break
    sizes = collections.Counter(a for *_, a, _ in [(None, *q[1:]) for q in stream])
    out = {"seed": seed, "cap": CAP, "strata": STRATA, "n_sets_stream": len(sizes),
           "dev_sets": len(chosen), "dev_queries": len(idx),
           "dev_unique": len({(stream[i][0], stream[i][1]) for i in idx}),
           "dev_recorded_none_share": round(ns, 4), "stream_recorded_none_share": round(none_share, 4),
           "dev_set_sizes": sorted((sizes[a] for a in chosen), reverse=True),
           "dev_indices": idx}
    with open(SPLIT, "w") as f:
        json.dump(out, f)
    print(json.dumps({k: v for k, v in out.items() if k != "dev_indices"}))


if __name__ == "__main__":
    main()
