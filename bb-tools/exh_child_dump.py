def s(x):
    return str(x)


def dump(t):
    form_of = {v: f for f, v in t._slack_of.items()}
    bounds = []
    for v in range(len(t._lo)):
        lo, up = t._lo[v], t._up[v]
        if lo is None and up is None:
            continue
        f = form_of.get(v)
        bounds.append({"v": v, "key": None if t._key[v] is None else s(t._key[v]),
                       "form": None if f is None else [[a, s(c)] for a, c in f],
                       "lo": None if lo is None else [s(lo[0]), s(lo[1])],
                       "up": None if up is None else [s(up[0]), s(up[1])]})
    ints = [[v, s(m), s(k), lit, None if form_of.get(v) is None else
             [[a, s(c)] for a, c in form_of[v]]] for v, m, k, lit in t._int_lits]
    dis = [[v, s(c), None if form_of.get(v) is None else
            [[a, s(c2)] for a, c2 in form_of[v]]] for v, c, lit in t._diseqs]
    return bounds, ints, dis


