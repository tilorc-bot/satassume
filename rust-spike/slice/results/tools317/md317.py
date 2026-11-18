"""md317.py (sa-port-317): the results doc's tables from incl-WL-frames.json (prof292.py on 316's samples)."""
import json, re, subprocess, sys
sys.argv = sys.argv[:1]
GEN = re.compile(r'^rs:(<?pyo3::|<\(pyo3::|<\(&pyo3::|<&|<\[|core::|alloc|std::|<core::|<alloc|<std::)')
def fold(k):
    m = re.search(r'::<<(.*)::MakeDef>::_PYO3_DEF::Def>', k)
    if m and "PyClassImplCollector" not in k:
        p = m.group(1).rsplit("::", 1)
        return "rs:" + (p[0] + "::" if len(p) > 1 else "") + "__pyfunction_" + p[-1]
    return k
def nice(k):
    k = re.sub(r'^rs:', '', k); k = re.sub(r'__pyfunction_(\w+)', r'\1 (entry)', k)
    k = re.sub(r'<([\w:]+)>::__pymethod_(\w+?)__$', r'\1::\2 (entry)', k); k = re.sub(r'^<([\w:<>]+)>::', r'\1::', k)
    k = k.replace("_install.<locals>.", "").replace("<locals>.", "")
    return re.sub(r'^py:', '', k)[:78]
for wl in ("dev", "fuzz"):
    d = json.load(open(f"incl-{wl}-frames.json")); N = d["N"]; rows = {}
    for k, v in d["incl"].items():
        if k.split(":")[0] not in ("rs", "py"): continue
        k = fold(k)
        if GEN.match(k): continue
        if v > rows.get(k, (0,))[0]: rows[k] = (v, d["self"].get(k, 0) if k.startswith("py:") else d["selfc"].get(k, 0))
    top = sorted(rows.items(), key=lambda kv: -kv[1][0])
    print(f"\n**{wl}** ({N:,} in-loop samples, {len(d['runs'])} runs)\n\n| # | function | inclusive | own |\n|---|---|---|---|")
    for i, (k, (v, s)) in enumerate(top[:15], 1):
        print(f"| {i} | `{nice(k)}` | {100*v/N:.2f}% | {100*s/N:.2f}% |")
    print(f"\nRows 16-40 ({wl}): " + "; ".join(f"`{nice(k)}` {100*v/N:.1f}" for k, (v, s) in top[15:40]) + ".")
    own = sorted(d["selfc"].items(), key=lambda kv: -kv[1])[:10]
    print(f"\nOwn cost, top 10 Rust ({wl}): " + "; ".join(f"`{nice(k)}` {100*v/N:.2f}" for k, v in own) + ".")
    cl = sorted(((k, v) for k, v in d["self"].items() if k.startswith("c:")), key=lambda kv: -kv[1])[:6]
    print(f"C leaf, top 6 ({wl}): " + "; ".join(f"`{k[2:]}` {100*v/N:.2f}" for k, v in cl) + ".")
    print(f"Categories ({wl}): " + ", ".join(f"{k} {100*v/N:.1f}%" for k, v in sorted(d["cats"].items(), key=lambda kv: -kv[1])) + ".")
