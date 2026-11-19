import json, sys
def q(xs, f):
    xs = sorted(xs); return xs[min(len(xs)-1, int(f*len(xs)))] if xs else None
for f in sys.argv[1:]:
    d = json.load(open(f)); C = d["calls"]
    print("==", d['wl'], d['mode'], "digest", d['digest'], "s %.3f" % d['s'], "fires", d['fires'], "compiled", d['compiled'], "certified", d['certified'], "check_s %.3f" % d['check_s'], "work", d.get('work'), {k:v for k,v in (d['stats'] or {}).items() if k in ('queries','budget_limited','witness_certified')})
    for k, v in d["split"].items(): print("   ", k, v["n"], v["check_s"], v["engine_s"])
    ns = [c for c in C if c[11] is not None]
    print("   nosession asked", len(ns), "true", sum(1 for c in ns if c[12]), "s", round(sum(c[11] for c in ns)/1e6,4), "med us", q([c[11] for c in ns], .5), "max", max([c[11] for c in ns] or [0]))
    pl = [c for c in C if c[10] is not None]
    print("   pools", len(pl), "s", round(sum(c[10] for c in pl)/1e6,4), "| before pools s", round(sum(c[7] for c in C if c[7] is not None)/1e6,4), "| check total", round(sum(c[1] for c in C)/1e6,4))
    cert = [c for c in C if c[2]]; fall = [c for c in pl if not c[2]]
    for name, S in (("certified", cert), ("fall-through reaching pools", fall)):
        if not S: continue
        w = [c[9] for c in S]; z = [c[8] for c in S]
        print(f"   {name}: n {len(S)} work med {q(w,.5)} 90% {q(w,.9)} 99% {q(w,.99)} max {max(w)} | size med {q(z,.5)} 90% {q(z,.9)} max {max(z)} | s {sum(c[1] for c in S)/1e6:.4f}")
    if cert:
        w = sorted(c[9] for c in cert)
        print("   certified work top 12:", w[-12:])
