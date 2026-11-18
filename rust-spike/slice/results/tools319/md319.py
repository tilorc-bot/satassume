"""md319.py (sa-port-319) FIX.json OLD.json [N]: (a)'s table from cap319.py's output: top N project Rust functions by the
capi<-rust samples they cause on FIX (46750d4), with OLD's share (5b1d96f) beside it and each function's kinds."""
import collections, json, sys
f, o = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])); n = int(sys.argv[3]) if len(sys.argv) > 3 else 15
N, M = f["N"], o["N"]
kinds = collections.defaultdict(collections.Counter)
for k, v in f["fk"].items():
    p, kd = k.split("\t"); kinds[p][kd] += v
tot = sum(f["fn"].values())
print(f"capi<-rust {tot} of {N} samples ({100*tot/N:.1f}%); 5b1d96f {sum(o['fn'].values())} of {M} ({100*sum(o['fn'].values())/M:.1f}%)\n")
print("| # | Rust function | 46750d4 | 5b1d96f | what it asks for (share of all samples) |\n|---|---|---|---|---|")
for i, (p, v) in enumerate(sorted(f["fn"].items(), key=lambda kv: -kv[1])[:n], 1):
    ks = "; ".join(f"{kd} {100*c/N:.2f}" for kd, c in kinds[p].most_common(4))
    print(f"| {i} | `{p[:70]}` | {100*v/N:.2f}% | {100*o['fn'].get(p,0)/M:.2f}% | {ks} |")
print("\nKinds, all functions: " + "; ".join(f"{k} {100*v/N:.2f} ({100*o['kind'].get(k,0)/M:.2f})" for k, v in sorted(f["kind"].items(), key=lambda kv: -kv[1])))
