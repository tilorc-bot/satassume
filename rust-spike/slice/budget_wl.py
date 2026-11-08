"""A workload for the discovery budget (step 5c7), as `live.py budget`. Dev, fuzz and zero never put a query over the budget
(sa-port-148's smoke: `bud:over_budget` 0 on all three), so `_union`'s over-budget returns and `_within_budget`'s False are
unreached there, and so is any query whose answer the budget decides.

Built from the code reached, not from any eval set: `Engine._struct`'s C-WIDEADD case (a sum of more than
`discovery_budget` = 400 non-constant terms weighs 401), `Engine._union` (engine.py :1759 on 44f4762; budget.rs `union` on
Rust): a sub-cone over the budget, the running weight passing the budget, and a cone that partly overlaps the union so far,
whose new objects are weighed one by one; `Engine._within_budget` (:1783; budget.rs `within_budget`): the proposition's or
the set's cone over the budget, and the sum `wp + wa` over the budget with only the set's objects outside the proposition's
cone counted. Plain symbols, no per-symbol facts (those made sessions slow: sa-port-148), so every session is small.

The answers the budget decides: under a set of k overlapping sums (`s`, `s + b_i`), the set weighs about |s| + 2k exactly,
but counting each overlapping cone whole (the `union-skip-overlap` plant) gives about k * |s|, past the budget, and the
query is answered None instead of True or False. The overlap and `wp + wa` queries use predicates whose sessions need
no LRA rows, so each session stays small under live.py's per-entry state digest. `python budget_wl.py` answers each query on a fresh engine and prints
the time, the answer and `last_budget_limited`.
"""
from sympy import Add, And, Q, symbols

B = symbols("b0:460")


def S(a, b):
    return Add(*B[a:b])


def _over():
    """Queries over the budget: a C-WIDEADD sum, and unions whose weight passes 400. The sums share `b0` with the rest of
    the query, so sympy_api's relevance split keeps them in the query the engine weighs."""
    w401, w420 = S(0, 401), S(0, 420)
    s2 = B[0] + S(210, 420)                                                   # overlaps S(0, 210) in b0 only
    out = [(Q.positive(w401), None), (~Q.positive(w401), None), (Q.positive(w401) & Q.positive(B[0]), None),
           (Q.positive(B[0]) | Q.negative(w420), None),
           (Q.positive(w401), Q.positive(B[0])), (Q.positive(B[0]), Q.positive(w420)),
           (Q.positive(B[0]), Q.positive(w420) & Q.negative(B[0])),        # a set over the budget never raises
           (Q.positive(S(0, 400)), None),                                   # 400 terms: built, weighs 401 by its walk
           # two or three sums that fit alone and not together: the running weight passes the budget
           (Q.positive(S(0, 210)) & Q.positive(S(210, 420)), None),
           (Q.positive(S(0, 150)) & Q.negative(S(150, 300)) & Q.positive(S(300, 450)), None),
           (Q.positive(S(0, 210)) & Q.positive(s2), None),
           (Q.positive(B[0]), Q.positive(S(0, 210)) & Q.positive(s2)),
           (Q.positive(S(0, 210)), Q.positive(s2)),
           (Q.positive(S(0, 210)), Q.positive(s2) & Q.positive(B[0]))]
    return out


def _overlap():
    """Overlapping sums: `s`, then `s + b_i`. Each later cone partly overlaps the union so far. The exact weight is about
    |s| + 2k; counting each overlapping cone whole (the `union-skip-overlap` plant) gives about k * (|s| + 2) > 400, so True
    and False become None. Predicates with no LRA rows (integer, real, finite): under live.py's `--check entry`, which digests
    the whole state after every outermost solver call, a sign query over 8 sums of 50 terms made 15,022 entries in one
    session and took about 14 min (sa-port-154: 2.2 s under `--check raw`, 5.0 s under `end`)."""
    out = []
    for k, n, pr in ((16, 25, Q.integer), (12, 33, Q.real), (16, 25, Q.finite)):
        s = S(0, n)
        sums = [s] + [s + B[n + i] for i in range(k - 1)]
        every = And(*[pr(t) for t in sums])
        out += [(pr(s), every), (~pr(s), every)]
        if pr is Q.integer:
            out += [(pr(sums[-1]), And(*[pr(t) for t in sums[:-1]])), (every, None), (every, every),
                    (pr(s) & pr(sums[1]), pr(B[n]) & pr(s))]
    return out


def _sum_over():
    """`_within_budget`'s last test: the proposition's and the set's cones fit alone, `wp + wa` doesn't, and only the set's
    objects outside the proposition's cone count: none, about 100 (fits), and 200 (doesn't: None, budget-limited)."""
    p = Q.integer(S(0, 200))
    return [(p, Q.integer(S(0, 200)) & Q.integer(B[0])), (~p, Q.integer(S(0, 200)) & Q.integer(B[0])),
            (p, Q.integer(S(100, 300))), (p, Q.integer(S(100, 399)))]


def queries():
    return [(p, True if a is None else a) for p, a in _over() + _overlap() + _sum_over()]


if __name__ == "__main__":
    import time
    from satassume import sympy_api
    from satassume.engine import Engine
    for i, (p, a) in enumerate(queries()):
        sympy_api.set_default_engine(Engine())
        t = time.time()
        try:
            r = sympy_api.ask(p, a)
        except Exception as e:
            r = type(e).__name__
        print(i, r, sympy_api.default_engine().last_budget_limited, round(time.time() - t, 2), flush=True)
