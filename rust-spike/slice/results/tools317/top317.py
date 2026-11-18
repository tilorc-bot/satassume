"""top317.py (sa-port-317) JSON [N] [all]: top functions by inclusive share from prof292.py's output.
Default: project functions only: sa_solver Rust ("rs:", pyo3's own generic frames dropped) and Python frames ("py:");
"c:" frames (libpython, libc) are dropped. Entry wrappers that pyo3 generates for one function (the MakeDef
trampoline, __pyfunction_X, __pymethod_X__) carry the same samples as X's entry and are folded into one row, named by
the __pyfunction/__pymethod symbol, keeping the largest count. `all`: every rs:/c:/py: key, nothing folded.
Columns: inclusive share of in-loop samples, samples, self (leaf) share, selfc (innermost sa_solver frame of a
rust/glue/capi<-rust sample: own code plus the C API it calls directly)."""
import json, re, sys
d = json.load(open(sys.argv[1])); n = int(sys.argv[2]) if len(sys.argv) > 2 else 15; al = len(sys.argv) > 3
N = d["N"]; incl = d["incl"]; slf = d["self"]; sc = d["selfc"]
GEN = re.compile(r'^rs:(<?pyo3::|<\(pyo3::|<&|<\[|core::|alloc::|std::|<core::|<alloc::|<std::)')
def fold(k):
    m = re.search(r'fastcall_cfunction_with_keywords::<<(.*)::MakeDef>::_PYO3_DEF::Def>|(?:cfunction_with_keywords|noargs|fastcall_cfunction_with_keywords)::<<(.*)::MakeDef>', k)
    if m:
        p = (m.group(1) or m.group(2)).rsplit("::", 1)
        return "rs:" + (p[0] + "::" if len(p) > 1 else "") + "__pyfunction_" + p[-1]
    return k
rows = {}
for k, v in incl.items():
    if k.split(":")[0] not in ("rs", "c", "py"):
        continue
    if not al:
        if k.startswith("c:"):
            continue
        k2 = fold(k)
        if GEN.match(k2):
            continue
        k = k2
    if v > rows.get(k, (0,))[0]:
        rows[k] = (v, slf.get(k, 0), sc.get(k, 0))
print(f"N={N}")
for i, (k, (v, s, c)) in enumerate(sorted(rows.items(), key=lambda kv: -kv[1][0])[:n], 1):
    print(f"{i:3} {100*v/N:6.2f}% {v:6} self {100*s/N:5.2f}% selfc {100*c/N:5.2f}%  {k[:140]}")
