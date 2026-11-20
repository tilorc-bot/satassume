"""diff368.py REF.ans A.ans [B.ans ...] (sa-port-368): the query indices whose answer differs from REF, per file."""
import json, sys
ref = json.load(open(sys.argv[1]))
for f in sys.argv[2:]:
    a = json.load(open(f))
    d = [(i, ref[i], a[i]) for i in range(len(ref)) if ref[i] != a[i]]
    print(f, "n", len(a), "moved", len(d), "first", d[:6], "..." if len(d) > 6 else "")
