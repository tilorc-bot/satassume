"""History independence: every query in a fresh process.

    python -m evalbench.forkq WORKLOAD --shard I/K --out PATH

The parent imports SymPy and satassume and loads the workload, nothing
else (no query runs in it); each query of the shard (indices = I mod K)
runs in a child forked from that state, so it sees exactly the state of a
fresh process.  Writes ``index<TAB>answer-json`` lines.
"""
import argparse
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workload")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    sys.setrecursionlimit(10000)
    i0, k = map(int, args.shard.split("/"))
    from evalbench.common import workload, ask_all
    from satassume import sympy_api
    pairs = workload(args.workload)
    with open(args.out, "w") as out:
        for i in range(i0, len(pairs), k):
            r, w = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(r)
                ans = ask_all(sympy_api.ask, [pairs[i]])[0]
                os.write(w, json.dumps(ans).encode())
                os._exit(0)
            os.close(w)
            data = b""
            while True:
                chunk = os.read(r, 1 << 16)
                if not chunk:
                    break
                data += chunk
            os.close(r)
            _, status = os.waitpid(pid, 0)
            ans = data.decode() if data else json.dumps(f"child died {status}")
            out.write(f"{i}\t{ans}\n")


if __name__ == "__main__":
    main()
