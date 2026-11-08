"""A workload for the zero twins (the test-only step before 5c7), as `live.py zero`. Dev, fuzz, loop and scope never
reach `relations.glue_atoms`' twin case (5c5: `glue-no-twins` fired 0 there), so `glue-of-plain` (5c6), which returns
`Session._glue_of`'s `atoms` without the twins, MATCHes on all four and only the suite catches it (gaps ruling).

Built from the code reached, not from any eval set: `Session._glue_of` / `_ensure_twins` (engine.py :1182-1230 on
1401d1f, session_glue.rs glue_of on Rust), `relations.zero_twins` / `glue_atoms` (the condition: a `zero(t)` gets its twin
`eq(t, 0)` only when `t` is under an application of the set or the query, scope.py :35-46, "chosen for its cost") and
`Engine._within_budget`'s `cross` twins (a `zero(t)` of one formula, `t` under an application of the other). Each term
`t` is asked in the `zero` and the `eq` spelling, with the application in the set, in the query, in both and in neither,
and the queries that make twins come both before and after the plain ones under the same set. It includes the pinned pair
(relations.py :171-181): under `integer(k) & integer(x) & negative(k) & positive(x)`, `Q.zero(k - x + 1)` is None where
`Q.eq(k - x + 1, 0)` is False on main.

`python zero_wl.py` answers every query on one engine in sequence (as live.py does, warm) and on a fresh engine alone, and
prints the counts and any query whose two answers differ.
"""
from sympy import Abs, Function, Q, Symbol, symbols

g = Function("g")
k, x, u, v = symbols("k x u v")
n = Symbol("n", integer=True)
y = Symbol("y", real=True)
SUM = k - x + 1
BASE = Q.integer(k) & Q.integer(x) & Q.negative(k) & Q.positive(x)

# (term, facts that bound it without a relation atom)
TERMS = [(SUM, BASE), (n, Q.nonnegative(n)), (y, Q.positive(y) | Q.zero(y)), (u - v, Q.real(u) & Q.real(v)),
         (2 * y + 1, Q.real(y))]


def _shapes(t, base):
    z, e = Q.zero(t), Q.eq(t, 0)
    app_f, app_c = Q.finite(g(t)), Q.composite(g(t, 1))
    sets = []
    for zz in (z, e):                    # the same set in both spellings
        sets += [base, base & zz, base & zz & app_f, base & zz & Q.composite(g(0, 1)), base & app_f,
                 base & ~zz & app_c, (zz | Q.positive(t)) & ~Q.finite(g(0))]
    props = [z, e, ~z, Q.nonzero(t), Q.zero(g(t)), Q.eq(g(t), g(0)), app_c, Q.positive(t) | Q.zero(g(t)),
             z | Q.zero(g(t)), e | Q.zero(g(t)), Q.zero(g(Abs(g(t)))), Q.composite(g(0, 1) + t)]
    out = []
    for s in dict.fromkeys(sets):
        out += [(p, s) for p in props]
        out += [(z, s), (e, s)]          # the pair again, after the twin-making queries under s
    return out


def queries():
    out = []
    for t, base in TERMS:
        out += _shapes(t, base)
    # the warm shapes of tests/test_zero_glue.py (WARM): a prefix, then the query, under one set
    out += [(q, Q.zero(n) & Q.composite(g(0, 1))) for q in (Q.eq(u, v), Q.lt(n, 1), Q.eq(n, 0), Q.composite(g(n, 1)))]
    out += [(q, Q.lt(n, 1) & Q.gt(n, -1) & Q.composite(g(0, 1))) for q in (Q.zero(n), Q.zero(g(n, 1)), Q.composite(g(n, 1)))]
    out += [(q, Q.zero(n) & Q.composite(g(0, 1)) & Q.positive(u - v))
            for q in (Q.composite(g(n, 1)), Q.zero(g(n, 1) - g(0, 1)), Q.positive(u - v + n))]
    # the pinned pair last, after everything above
    out += [(Q.zero(SUM), BASE), (Q.eq(SUM, 0), BASE), (~Q.zero(SUM), BASE), (Q.nonzero(SUM), BASE)]
    return out


def _outcome(p, a, e):
    from satassume.sympy_api import ask
    try:
        return ask(p, a, e)
    except Exception as ex:              # noqa: BLE001 (compared as an outcome)
        return type(ex).__name__


if __name__ == "__main__":
    import collections
    from satassume.engine import DictCache, Engine
    qs = queries()
    warm = Engine(cache=DictCache())
    c, bad = collections.Counter(), []
    for i, (p, a) in enumerate(qs):
        w, f = _outcome(p, a, warm), _outcome(p, a, Engine(cache=DictCache()))
        c[repr(f)] += 1
        if w != f:
            bad.append((i, p, a, w, f))
    print(len(qs), "queries;", dict(c))
    print("warm != fresh:", len(bad))
    for b in bad[:20]:
        print(*b, sep=" | ")
    pair = [_outcome(p, BASE, Engine(cache=DictCache())) for p in (Q.zero(SUM), Q.eq(SUM, 0))]
    print("pair (fresh): zero", pair[0], "eq", pair[1])
