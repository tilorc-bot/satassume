"""wk346.py DIR [BOUND...] (sa-port-346): from pc346.py's rows in DIR (py), per workload: calls of the check, certified, the
work (term evaluations charged) of the certified calls, and for each BOUND how many certified calls have more work
(lost), how many fall-through calls it stops, and the work it saves."""
import glob, json, sys
d0, bounds = sys.argv[1], [int(b) for b in sys.argv[2:]]
def q(xs, f):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(f * len(xs)))] if xs else None
tot = {b: [0, 0, 0, 0] for b in bounds}; allc = []
print("| workload | calls | certified | certified work: median, 90%, 99%, max | " + " | ".join(f"lost at {b}" for b in bounds) + " | fall-through work: all, " + ", ".join(f"at {b}" for b in bounds) + " |")
print("|---" * (5 + 2 * len(bounds) ) + "|")
for f in sorted(glob.glob(d0 + "/pc-*-py.json")):
    d = json.load(open(f)); C = d["calls"]
    cert = [c[9] for c in C if c[2]]; fall = [c[9] for c in C if not c[2] and c[9] is not None]
    allc += cert
    lost = [sum(1 for w in cert if w > b) for b in bounds]
    fw = [sum(min(w, b) for w in fall) for b in bounds]
    for b, l in zip(bounds, lost): tot[b][0] += l
    print(f"| {d['wl']} | {len(C)} | {len(cert)} | " + (f"{q(cert,.5)}, {q(cert,.9)}, {q(cert,.99)}, {max(cert)}" if cert else "") + " | " + " | ".join(map(str, lost)) + f" | {sum(fall)}, " + ", ".join(map(str, fw)) + " |")
print("all certified", len(allc), "lost", {b: tot[b][0] for b in bounds})
