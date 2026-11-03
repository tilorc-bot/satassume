import pickle, sys, collections
S = collections.Counter(); TOT = collections.Counter(); SOL = collections.Counter()
for f in sys.argv[1:]:
    s, t, so, _ = pickle.load(open(f, "rb"))
    S.update(s); TOT.update(t); SOL.update(so)
n = TOT["outside-solve"] + TOT["in-solve"]
def cat(k):
    ks = k.split(" < ")
    # bucket: what part of the theory interface the sample is in
    for x in ks:
        if x in ("lra._branch",): return "lra B&B (_branch)"
    for x in ks:
        if x == "lra._concrete" or x == "lra._model": return "lra check model (_concrete/_model)"
    for x in ks:
        if x == "lra._simplex": return "lra simplex"
    for x in ks:
        if x.startswith("lra.check") or x == "lra._check": return "lra check other"
    for x in ks:
        if x in ("lra.assert_lit", "lra._assert_kind", "lra._set_upper", "lra._set_lower", "lra._update", "lra._int_bounds", "lra._assert_integral"): return "lra assert (no simplex)"
    for x in ks:
        if x in ("lra.propagate", "lra._implied", "lra._int_verdict"): return "lra propagate"
    for x in ks:
        if x in ("lra.push_level", "lra.pop_level", "lra._undo_to"): return "lra push/pop"
    if ks[0].startswith("lra."): return "lra other:" + ks[0]
    if ks[0].startswith("tr."): return "transfer"
    return ks[0]
for cls in ("plain", "lra-idle", "lra-active", "lra-gaveup", "other", "outside"):
    tot = sum(v for (c, k), v in S.items() if c == cls)
    if not tot: continue
    print(f"== {cls}: {tot} samples ({100*tot/n:.1f}% of pass), solves {SOL.get(cls, '-')}")
    C = collections.Counter()
    for (c, k), v in S.items():
        if c == cls: C[cat(k)] += v
    for k, v in C.most_common(14):
        print(f"   {k:38s} {v:5d} {100*v/n:5.2f}% of pass")
