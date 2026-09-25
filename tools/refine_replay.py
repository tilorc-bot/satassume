"""Replay the ``ask`` query stream of the refine battery through satassume alone.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python tools/refine_replay.py stream.pkl [repeats]

``stream.pkl`` is written by ``tools/refine_record.py``.  This is the
benchmark the performance commits of September 2026 quote (issue #7).
Prints the cold (first) pass wall time, which is the benchmark number, then every pass, and fails if any answer differs from the recording.
"""
import pickle, sys, time
from satassume.sympy_api import ask
stream = pickle.load(open(sys.argv[1], "rb"))
reps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
times = []
for _ in range(reps):
    bad = []
    t0 = time.perf_counter()
    for i, (p, a, r) in enumerate(stream):
        got = ask(p, a)
        if got is not r: bad.append((i, p, a, r, got))
    dt = time.perf_counter() - t0
    times.append(dt)
    if bad:
        print(f"MISMATCH: {len(bad)} of {len(stream)} answers differ; first:")
        for b in bad[:5]: print("  ", b)
        sys.exit(1)
print(f"{len(stream)} queries; cold pass {times[0]:.2f}s ({1000*times[0]/len(stream):.3f} ms/query); "
      f"all passes {' '.join(f'{t:.2f}' for t in times)}; answers match")
