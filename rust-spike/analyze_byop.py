"""analyze_byop.py RAW: per-method wall times from a run-k.sh log with MODES="pybyop rsbyop". A clock pair per call, so rough."""
import json
import statistics as st
import sys

rows = [json.loads(line) for line in open(sys.argv[1]) if line.startswith("{")]
for r in rows:
    # Python's replay keeps the newest solver in a local, so most frees land on the next `new`: only the sum means anything
    n, d = r["by"].pop("new"), r["by"].pop("drop")
    r["by"]["new + drop"] = [n[0] + d[0], n[1]]
for wl in ("dev", "fuzz"):
    py = [r for r in rows if r["wl"] == wl and r["run"] == "pybyop" and r["round"] != "0"]
    rs = [r for r in rows if r["wl"] == wl and r["run"] == "rsbyop" and r["round"] != "0"]
    print(f"\n## {wl}: Python {st.median(r['T'] for r in py):.4f} s, Rust {st.median(r['T'] for r in rs):.4f} s, "
          f"Rust inside prop() {st.median(r['T_prop'] for r in rs):.4f} s "
          f"({st.median(r['T_prop'] / r['T'] for r in rs):.1%} of the Rust run)\n")
    print("| method | calls | Python s | Rust s | k | Python us/call | Rust us/call |\n|---|---:|---:|---:|---:|---:|---:|")
    for n in sorted(py[0]["by"], key=lambda n: -st.median(r["by"][n][0] for r in py)):
        a = st.median(r["by"][n][0] for r in py)
        b = st.median(r["by"][n][0] for r in rs)
        c = py[0]["by"][n][1]
        assert c == rs[0]["by"][n][1], n
        print(f"| {n} | {c} | {a:.4f} | {b:.4f} | {a / b:.1f} | {a / c * 1e6:.2f} | {b / c * 1e6:.3f} |")
