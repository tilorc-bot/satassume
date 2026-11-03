"""sa-bb-1's c2 prototype (patch_child.py, mode latds) as an installable hook."""
from fractions import Fraction
from proto import in_span


def install(L_mod):
    global L, ocheck
    L = L_mod
    ocheck = L.LRATheory._check
    return check


PSEUDO = 10 ** 9
C = {"exhausted": 0, "lat_conflicts": 0, "ds_branch_checks": 0, "checks": 0}


def lattice(t):
    """(gens, reasons, vec) for t's asserted literals, or None with constants."""
    form_of = {v: f for f, v in t._slack_of.items()}
    pins, reasons = {}, []
    for v in range(len(t._lo)):
        if t._key[v] is not None and t._lo[v] is not None and t._lo[v] == t._up[v]:
            pins[v] = t._lo[v][0]

    def vec(v, m, k):
        f = form_of.get(v, ((v, L._ONE),))
        o = {"1": k}
        for a, c in f:
            if a in pins:
                o["1"] += m * c * pins[a]
                reasons.extend((t._lo_r[a], t._up_r[a]))
            else:
                o[f"v{a}"] = o.get(f"v{a}", 0) + m * c
        return {a: c for a, c in o.items() if c}

    gens = [{"1": Fraction(1)}] + [vec(v, m, k) for v, m, k, l in t._int_lits if l > 0]
    return gens, reasons, vec




def check(self):
    C["checks"] += 1
    e0 = self.stats["exhausted"]
    if self._int_lits and not self._fields and True:
        gens, reasons, vec = lattice(self)
        pos = [-l for *_, l in self._int_lits if l > 0]
        for v, m, k, l in self._int_lits:
            if l < 0 and in_span(gens, vec(v, m, k)):
                C["lat_conflicts"] += 1
                self.stats["conflicts"] += 1
                return (False, L._dedupe([-l] + pos + [-r for r in reasons if r]))
        if True:
            extra = []
            for f, s in self._slack_of.items():
                if (self._lo[s] is not None or self._up[s] is not None
                        or any(w == s for w, *_ in self._diseqs)) \
                        and in_span(gens, vec(s, L._ONE, L._ZERO)):
                    extra.append((s, L._ONE, L._ZERO, PSEUDO))
            if extra:
                C["ds_branch_checks"] += 1
                n0 = len(extra)
                self._int_lits[:0] = extra
                try:
                    r = ocheck(self)
                finally:
                    del self._int_lits[:n0]
                if r is not None and r[0] is False and -PSEUDO in r[1]:
                    r = (False, L._dedupe([x for x in r[1] if x != -PSEUDO]
                                          + pos + [-q for q in reasons if q]))
                C["exhausted"] += self.stats["exhausted"] - e0
                return r
    r = ocheck(self)
    C["exhausted"] += self.stats["exhausted"] - e0
    return r


