"""Replay the ``ask`` query stream of the refine battery through satassume alone.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python tools/refine_replay.py stream.pkl [repeats]
        [--log PATH [--log-models]]

``stream.pkl`` is written by ``tools/refine_record.py``.  This is the
benchmark the performance commits of September 2026 quote (issue #7).
Prints the cold (first) pass wall time, which is the benchmark number, then every pass, and fails if any answer differs from the recording.

``--log PATH`` writes a per-query JSON-lines log of the cold pass (path
taken, outcome, session, every solve with its decisions and conflicts; see
``tools/query_log.py`` for the record format) and ``--log-models`` adds the
model of every satisfiable solve.  The log instruments the engine by
wrapping methods, so its pass is slower and is not the benchmark number;
without ``--log`` nothing is instrumented.
"""
import pickle, sys, time
argv = sys.argv[1:]
log_path = None
log_models = "--log-models" in argv
if log_models: argv.remove("--log-models")
if "--log" in argv:
    k = argv.index("--log"); log_path = argv[k + 1]; del argv[k:k + 2]
from satassume.sympy_api import ask
stream = pickle.load(open(argv[0], "rb"))
reps = int(argv[1]) if len(argv) > 1 else 1
times = []
if log_path is not None:
    import query_log
    dt, bad = query_log.run(stream, log_path, log_models)
    if bad:
        print(f"MISMATCH (logged pass): {len(bad)} of {len(stream)} answers differ; first:")
        for b in bad[:5]: print("  ", b)
        sys.exit(1)
    print(f"logged pass {dt:.2f}s, log written to {log_path}")
    reps -= 1
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
if times: print(f"{len(stream)} queries; {'first later' if log_path else 'cold'} pass {times[0]:.2f}s ({1000*times[0]/len(stream):.3f} ms/query); "
      f"all passes {' '.join(f'{t:.2f}' for t in times)}; answers match")
