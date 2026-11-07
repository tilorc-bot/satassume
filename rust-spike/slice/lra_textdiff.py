"""lra_textdiff.py WL Q...: for each query, run Python and Rust and print the first field of the LRA state text that differs
(state.py's SLICE_LRA_TEXT). Reads no results; a small tool for finding what a `lra_diff` in livecmp means."""
import ast, os, subprocess, sys, tempfile
wl, qs = sys.argv[1], sys.argv[2:]
for q in qs:
    t = {}
    for m in ("py", "rust"):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "t")
            subprocess.run([sys.executable, "live.py", wl, m, os.path.join(d, "o"), "--check", "end", "--only", q],
                           env=dict(os.environ, SLICE_LRA_TEXT=f), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            t[m] = open(f).read().splitlines() if os.path.exists(f) else []
    print(f"q{q}: {len(t['py'])} py texts, {len(t['rust'])} rust texts")
    for i, (a, b) in enumerate(zip(t["py"], t["rust"])):
        if a == b:
            continue
        keys = [p for p in ("key var_of slack_of forms lo up lo_r up_r vq vd rows cols atoms ground atoms_on assigned diseqs "
                            "ints ints_on int_lits int_memo trail lims dirty pending fields gave_up eager exhausted branched "
                            "stats").split()]
        def cut(s):
            out = {}
            for j, k in enumerate(keys):
                x = s.find(f"'{k}': ")
                y = s.find(f"'{keys[j + 1]}': ", x) if j + 1 < len(keys) else len(s)
                out[k] = s[x:y]
            return out
        ca, cb = cut(a), cut(b)
        for k in keys:
            if ca[k] != cb[k]:
                x, y = ca[k], cb[k]
                n = next((n for n, (p, r) in enumerate(zip(x, y)) if p != r), min(len(x), len(y)))
                print(f"  text {i} field {k} at {n}\n   py   {x[max(0, n - 60):n + 200]}\n   rust {y[max(0, n - 60):n + 200]}")
        break
