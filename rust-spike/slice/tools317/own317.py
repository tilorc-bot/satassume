"""own317.py (sa-port-317) JSON [N]: own-cost tables from prof292.py's output: selfc (innermost sa_solver frame on
rust/glue/capi<-rust samples), Python self (innermost Python frame, leaf in the eval loop), rmod and pyfile inclusive."""
import json, sys
d = json.load(open(sys.argv[1])); n = int(sys.argv[2]) if len(sys.argv) > 2 else 15
N = d["N"]
print("cats", {k: f"{100*v/N:.2f}%" for k, v in sorted(d["cats"].items(), key=lambda kv: -kv[1])})
print("-- selfc"); 
for k, v in sorted(d["selfc"].items(), key=lambda kv: -kv[1])[:n]: print(f"{100*v/N:6.2f}% {v:6} D {100*d['dcat'].get(k,0)/N:5.2f}%  {k[:130]}")
print("-- py self")
for k, v in sorted(((k, v) for k, v in d["self"].items() if k.startswith("py:")), key=lambda kv: -kv[1])[:n]: print(f"{100*v/N:6.2f}% {v:6}  {k[:130]}")
print("-- c self")
for k, v in sorted(((k, v) for k, v in d["self"].items() if k.startswith("c:")), key=lambda kv: -kv[1])[:8]: print(f"{100*v/N:6.2f}% {v:6}  {k[:130]}")
for p in ("rmod:", "pyfile:"):
    print("--", p, "inclusive")
    for k, v in sorted(((k, v) for k, v in d["incl"].items() if k.startswith(p)), key=lambda kv: -kv[1])[:n + 5]: print(f"{100*v/N:6.2f}% {v:6}  {k[:130]}")
