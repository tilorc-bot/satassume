"""Stage 0 of item 2 of the next-steps plan (irrational constants as bounded
LRA variables): census of unreadable relations on the refine stream and gate2.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy:tools \\
        python agent-reports/scripts/irr0_census.py stream  ~/.cache/satassume/stream.pkl  OUT.json [--verify S]
    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy:tools \\
        python agent-reports/scripts/irr0_census.py gate2   ~/.cache/satassume/gate2-frozen.jsonl OUT.json [--verify S]

For every query (in order, one engine, one answer memo, like the replay):

* ``base``: ``sympy_api.ask`` unchanged; the query is marked
  *uninterpreted* when the engine raised ``Uninterpreted`` for it (wrapping
  ``Engine.ask``/``Engine.is_``);
* static census: every relation of the proposition and (unless the
  proposition is about constants only, which ``sympy_api`` answers without
  the assumptions) of the assumptions is looked up with the adapters
  (``lra_adapter.interpret``, ``EUFAdapter.parse``); an atom neither reads
  is *unreadable* and classified

  - ``a``: every non-rational piece is a closed real finite number in a
    linear position (a summand, or a summand times a rational), e.g.
    ``x <= pi/2``, ``x - 2*pi``, ``x < 0.5``: readable under the plan;
  - ``b``: a closed non-rational number multiplies something with free
    symbols (``pi*x``, ``sqrt(2)*x``; ``b:float`` for ``0.5*x``, which
    would be linear if Floats were read as exact rationals): stays
    unreadable;
  - ``c``: anything else (``oo``/``nan``/``zoo``, a closed constant that is
    not known real or finite such as ``I``, ``f(1)``, non-scalar ...);

* ``plan`` oracle: the query with every type-``a`` unreadable relation
  rewritten as the plan would read it (each irreducible closed constant
  ``c``, after splitting sums and rational factors, becomes a fresh symbol
  ``_irr_k`` (the same constant, the same symbol), and the assumptions get
  ``Q.real(_irr_k) & (lo < _irr_k) & (_irr_k < hi)`` with 30-digit rational
  bounds from ``evalf``).  Relations EUF already reads (``Eq(x, pi)``) are
  left alone, so what the plan adds for equalities is not in the oracle.
  Unary facts of the constant (``Q.positive(pi)``) are not tied to the
  symbol, so the oracle can miss what those links would give.

``--verify S`` asks SymPy's own ``ask`` (S-second alarm) for every distinct
query the plan oracle changes (stream only; gate2 has SymPy's answer);
with ``--rest`` also for every distinct fully readable query the oracle
leaves None (does SymPy decide what the oracle does not?).
"""
import json, pickle, signal, sys, time
from collections import Counter, defaultdict
from fractions import Fraction

from sympy import Add, Mul, Rational, S, Symbol, Expr, Q, And, Float
from sympy.assumptions.assume import AppliedPredicate
from sympy.core.relational import Relational
from sympy.logic.boolalg import BooleanFunction

from satassume import Engine, sympy_api
from satassume import lra_adapter as L
from satassume.euf_adapter import EUFAdapter
from satassume.relations import Uninterpreted

# ---------------------------------------------------------------- base run
UNINT = [False]
for _name in ("ask", "is_"):
    _orig = getattr(Engine, _name)

    def _wrap(self, *a, _orig=_orig, **k):
        try:
            return _orig(self, *a, **k)
        except Uninterpreted:
            UNINT[0] = True
            raise
    setattr(Engine, _name, _wrap)


def run(eng, p, a):
    UNINT[0] = False
    try:
        r = sympy_api.ask(p, a, engine=eng)
    except ValueError:
        r = "error"
    except Exception as e:                     # noqa: BLE001 - recorded
        r = "crash:" + type(e).__name__
    return r, UNINT[0]


# ------------------------------------------------------------ relations
_REL_PREDS = {Q.lt, Q.le, Q.gt, Q.ge, Q.eq, Q.ne}


def rel_nodes(e, out):
    """Relation leaves of a SymPy Boolean (Relationals, ``Q.lt(a, b)``...,
    ``Q.is_true(rel)``)."""
    if e is True or e is False or e is S.true or e is S.false:
        return out
    if isinstance(e, Relational):
        out.append(e)
    elif isinstance(e, AppliedPredicate):
        if e.function in _REL_PREDS or (e.function == Q.is_true and e.arguments
                                        and isinstance(e.arguments[0], Relational)):
            out.append(e)
    elif isinstance(e, BooleanFunction):
        for x in e.args:
            rel_nodes(x, out)
    return out


def readable(node):
    if L.interpret(node) is not None:
        return True
    return EUFAdapter.parse(node) is not None


class NotA(Exception):
    def __init__(self, kind, why):
        self.kind, self.why = kind, why


def closed_real(c):
    """Reason string if the closed number ``c`` is not usable, else None."""
    if not c.is_number:
        return "closed non-number (f(1))"
    if c.is_extended_real is not True:
        return "not known real (I, ...)" if c.is_extended_real is False else "real unknown"
    if c.is_finite is not True:
        return "not known finite"
    return None


def plan_lin(e, consts):
    """Rewrite of ``e`` with every irreducible closed non-rational constant
    in a linear position replaced by its symbol (collected in ``consts``,
    constant -> count); raises NotA."""
    if not isinstance(e, Expr) or getattr(e, "is_Matrix", False) \
            or getattr(e, "is_MatrixExpr", False):
        raise NotA("c", "non-scalar")
    if not e.free_symbols:
        if e.is_Rational:
            return e
        if e.is_Add:
            return Add(*[plan_lin(a, consts) for a in e.args])
        if e.is_Mul:
            coeff, rest = e.as_coeff_Mul()
            if coeff.is_Rational and coeff != 1:
                return coeff * plan_lin(rest, consts)
        why = closed_real(e)
        if why:
            raise NotA("c", why)
        consts[e] = consts.get(e, 0) + 1
        return symbol(e)
    if e.is_Add:
        return Add(*[plan_lin(a, consts) for a in e.args])
    if e.is_Mul:
        coeff, rest, bad = S.One, [], []
        for f in e.args:
            if f.free_symbols:
                rest.append(f)
            elif f.is_Rational:
                coeff *= f
            else:
                bad.append(f)
        if bad:
            if any(isinstance(f, Float) for f in bad):
                raise NotA("b", "float*symbol")
            if any(f.is_extended_real is not True for f in bad):
                raise NotA("c", "non-real coefficient (I*x)")
            raise NotA("b", "constant*symbol")
        if coeff != 1:
            return coeff * plan_lin(Mul(*rest), consts)
        if len(rest) == 1:
            return plan_lin(rest[0], consts)
    return e                                    # opaque term


def classify(node):
    """``(kind, why, consts, rewritten)``."""
    r = L.relation(node)
    if r is None:
        return "c", "not a binary relation", {}, None
    name, lhs, rhs = r
    for side in (lhs, rhs):
        if not isinstance(side, Expr):
            return "c", "non-scalar", {}, None
        if side.has(*L._BAD):
            return "c", "oo/nan/zoo", {}, None
    consts = {}
    try:
        l2, r2 = plan_lin(lhs, consts), plan_lin(rhs, consts)
    except NotA as x:
        return x.kind, x.why, {}, None
    if not consts:
        return "c", "unexplained", {}, None
    op = {"lt": Q.lt, "le": Q.le, "gt": Q.gt, "ge": Q.ge, "eq": Q.eq, "ne": Q.ne}[name]
    return "a", "linear constant", consts, op(l2, r2)


# ------------------------------------------------------------ constants
SYMS: dict = {}
BOUNDS: dict = {}


def symbol(c):
    s = SYMS.get(c)
    if s is None:
        s = SYMS[c] = Symbol(f"_irr_{len(SYMS)}")
    return s


def bounds(c):
    """Rational ``(lo, hi)`` with ``lo < c < hi`` from a 30-digit strict
    evalf, widened by 1e-25 relative; None if evalf fails."""
    b = BOUNDS.get(c, False)
    if b is not False:
        return b
    t = time.perf_counter()
    try:
        v = c.evalf(30, strict=True)
        f = Fraction(str(v))
        w = max(abs(f), Fraction(1)) * Fraction(1, 10 ** 25)
        b = (Rational(f - w), Rational(f + w))
    except Exception:                          # noqa: BLE001 - reported
        b = None
    BOUNDS[c] = b
    EVALF_MS[c] = 1000 * (time.perf_counter() - t)
    return b


EVALF_MS: dict = {}


def bound_facts(consts):
    out = []
    for c in consts:
        b = bounds(c)
        s = symbol(c)
        out.append(Q.real(s))
        if b is not None:
            out += [Q.lt(b[0], s), Q.lt(s, b[1])]
    return out


# ------------------------------------------------------------ per query
ATOM_INFO: dict = {}


def atom_info(node):
    r = ATOM_INFO.get(node)
    if r is None:
        if readable(node):
            r = ("ok", None, {}, None)
        else:
            r = classify(node)
        ATOM_INFO[node] = r
    return r


def rewrite(e, sub):
    if not sub:
        return e
    if isinstance(e, (Relational, AppliedPredicate)):
        return sub.get(e, e)
    if isinstance(e, BooleanFunction):
        return e.func(*[rewrite(x, sub) for x in e.args])
    return e


def census(p, a):
    """``(kinds, atoms, plan_query)``: kinds of unreadable atoms, the
    unreadable atoms with info, and the rewritten query (None when the plan
    leaves it unchanged or unreadable)."""
    const_prop = isinstance(p, sympy_api._Basic) and sympy_api._is_constant_proposition(p)
    parts = [("p", p)] + ([] if const_prop or a is True else [("a", a)])
    bad = []
    for where, e in parts:
        for n in rel_nodes(e, []):
            info = atom_info(n)
            if info[0] != "ok":
                bad.append((where, n, info))
    kinds = {k for _, _, (k, *_r) in bad}
    plan = None
    if bad and kinds == {"a"}:
        sub = {n: info[3] for _, n, info in bad}
        consts = {}
        for _, _, info in bad:
            consts.update(info[2])
        p2 = rewrite(p, sub)
        base_a = True if const_prop else a
        a2 = rewrite(base_a, sub) if base_a is not True else True
        extra = bound_facts(sorted(consts, key=str))
        a2 = And(*([a2] if a2 is not True else []), *extra)
        plan = (p2, a2)
    return kinds, bad, plan


def sympy_answer(p, a, secs):
    from sympy import ask

    def alarm(*_):
        raise TimeoutError
    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(secs)
    try:
        return ask(p, a)
    except TimeoutError:
        return "timeout"
    except ValueError:
        return "error"
    except Exception as e:                     # noqa: BLE001
        return f"exception {type(e).__name__}"
    finally:
        signal.alarm(0)


def load(mode, path):
    if mode == "stream":
        return [(p, a, r, None) for p, a, r in pickle.load(open(path, "rb"))]
    from compare import rebuild
    out = []
    for line in open(path):
        rec = json.loads(line)
        out.append((rebuild(rec["prop"]), rebuild(rec["assum"]), rec["answer"], rec["sympy"]))
    return out


def qclass(kinds):
    if not kinds:
        return "readable"
    if kinds == {"a"}:
        return "all a"
    if "c" in kinds:
        return "has c"
    return "has b (no c)"


def main():
    mode, path, out_path = sys.argv[1:4]
    verify = int(sys.argv[sys.argv.index("--verify") + 1]) if "--verify" in sys.argv else None
    Qs = load(mode, path)
    eng, eng_plan = Engine(), Engine()
    memo, memo_plan = {}, {}
    rows = []
    for i, (p, a, rec, sym) in enumerate(Qs):
        key = (p, a)
        if key not in memo:
            base, unint = run(eng, p, a)
            kinds, bad, plan = census(p, a)
            memo[key] = (base, unint, kinds, bad, plan)
        base, unint, kinds, bad, plan = memo[key]
        planned = base
        if plan is not None:
            if plan not in memo_plan:
                memo_plan[plan] = run(eng_plan, *plan)
            planned = memo_plan[plan][0]
        rows.append(dict(i=i, key=key, rec=rec, sympy=sym, base=base, unint=unint,
                         kinds=kinds, bad=bad, plan=plan, planned=planned))
        if i % 2000 == 0:
            print(f"  {i}/{len(Qs)}", flush=True)
    report(mode, rows, verify, out_path)


def outcome(before, after):
    d = lambda x: x is True or x is False         # noqa: E731
    if after == before:
        return "same"
    if before is None and d(after):
        return "more definite"
    if after == "error":
        return "new error"
    if d(before) and after is None:
        return "less definite"
    return f"other {before}->{after}"


def report(mode, rows, verify, out_path):
    out = {"mode": mode, "queries": len(rows)}
    print(f"== {mode}: {len(rows)} queries")
    base_bad = sum(r["base"] != r["rec"] for r in rows)
    print(f"base answers differing from the recording/frozen: {base_bad}")
    out["base_differs"] = base_bad
    out["base_vs_rec"] = dict(Counter(outcome(r["rec"], r["base"]) for r in rows))
    print(f"  base against the recording: {out['base_vs_rec']}")
    odd = [r for r in rows if r["bad"] and not r["unint"]]
    out["base_vs_rec_examples"] = [f"{r['rec']}->{r['base']} | {r['key'][0]} | {r['key'][1]}"[:220]
                                   for r in rows if r["base"] != r["rec"]][:12]
    out["static_not_dynamic"] = dict((str(k), v) for k, v in Counter(
        (str(r["base"]), qclass(r["kinds"]), sympy_api._is_constant_proposition(r["key"][0])
         if isinstance(r["key"][0], sympy_api._Basic) else None) for r in odd).most_common())
    out["static_not_dynamic_examples"] = [f"{r['key'][0]} | {r['key'][1]}"[:200] for r in odd[:6]]
    print(f"  unreadable atom but no Uninterpreted (base, class, constant prop): {out['static_not_dynamic']}")
    # 1. uninterpreted queries and sessions
    un = [r for r in rows if r["unint"]]
    sess = lambda rs: len({r["key"][1] for r in rs})      # noqa: E731
    print(f"Uninterpreted: {len(un)} queries ({len({r['key'] for r in un})} distinct), "
          f"{sess(un)} distinct assumption sets")
    static_bad = [r for r in rows if r["bad"]]
    print(f"static: {len(static_bad)} queries with an unreadable atom; "
          f"dynamic/static agreement {dict(Counter((r['unint'], bool(r['bad'])) for r in rows))}")
    out["uninterpreted"] = {"queries": len(un), "distinct": len({r['key'] for r in un}),
                            "sessions": sess(un)}
    out["dyn_static"] = {str(k): v for k, v in Counter((r['unint'], bool(r['bad'])) for r in rows).items()}
    QC = Counter(); QCd = defaultdict(set); QCs = defaultdict(set); QCnone = Counter()
    for r in un:
        c = qclass(r["kinds"])
        QC[c] += 1; QCd[c].add(r["key"]); QCs[c].add(r["key"][1])
        QCnone[c] += r["base"] is None
    print("uninterpreted queries by class (queries / distinct / sessions / base None):")
    out["by_class"] = {}
    for c, n in QC.most_common():
        print(f"  {c:14s} {n:6d} {len(QCd[c]):6d} {len(QCs[c]):6d} {QCnone[c]:6d}")
        out["by_class"][c] = [n, len(QCd[c]), len(QCs[c]), QCnone[c]]
    # per atom (distinct, over atoms of uninterpreted queries) and per occurrence
    A = Counter(); Aw = Counter(); Aq = Counter(); seen = set()
    for r in un:
        for where, n, info in r["bad"]:
            Aq[(info[0], info[1])] += 1
            if n not in seen:
                seen.add(n); A[info[0]] += 1; Aw[(info[0], info[1], where)] += 1
    print(f"distinct unreadable atoms: {dict(A)}")
    for k, v in Aw.most_common():
        print(f"  {v:5d}  {k}")
    out["atoms"] = dict(A)
    out["atoms_why"] = {str(k): v for k, v in Aw.items()}
    ex = defaultdict(list)
    for n in seen:
        info = ATOM_INFO[n]
        if len(ex[(info[0], info[1])]) < 6:
            ex[(info[0], info[1])].append(str(n))
    out["atom_examples"] = {str(k): v for k, v in ex.items()}
    # EUF-only equalities with linear constants (plan would give them to LRA too)
    eqs = set()
    for r in rows:
        p, a = r["key"]
        for e in (p, a):
            for n in rel_nodes(e, []):
                rel = L.relation(n)
                if rel and rel[0] in ("eq", "ne") and L.interpret(n) is None \
                        and EUFAdapter.parse(n) is not None and classify(n)[0] == "a":
                    eqs.add(n)
    out["euf_only_linear_const_eq"] = len(eqs)
    out["euf_only_examples"] = [str(n) for n in list(eqs)[:8]]
    print(f"equalities read by EUF only that are linear with constants: {len(eqs)} distinct")
    # 2. plan oracle
    O = Counter(); changed = {}
    for r in rows:
        o = outcome(r["base"], r["planned"])
        O[o] += 1
        if o != "same":
            changed.setdefault(r["key"], {"i": r["i"], "n": 0, "o": o, "base": r["base"],
                                          "planned": r["planned"], "rec": r["rec"], "sympy": r["sympy"],
                                          "bad": [str(n) for _, n, _ in r["bad"]]})
            changed[r["key"]]["n"] += 1
    fr = [r for r in un if qclass(r["kinds"]) == "all a"]
    print(f"plan oracle over all queries: {dict(O)}; fully readable under plan: {len(fr)} queries, "
          f"{sum(r['base'] is None for r in fr)} of them None today")
    out["plan"] = dict(O)
    out["plan_distinct"] = dict(Counter(v["o"] for v in changed.values()))
    out["plan_sessions"] = {o: len({k[1] for k, v in changed.items() if v["o"] == o})
                            for o in out["plan_distinct"]}
    print(f"  distinct: {out['plan_distinct']}; sessions: {out['plan_sessions']}")
    # errors: distinct assumption sets
    errs = defaultdict(int)
    for k, v in changed.items():
        if v["o"] == "new error":
            errs[str(k[1])] += v["n"]
    out["new_error_sets"] = errs
    for s, n in errs.items():
        print(f"  new error x{n}: {s[:160]}")
    # verification
    V = Counter()
    for (p, a), v in changed.items():
        if mode == "gate2":
            s = v["sympy"]
        elif verify:
            s = sympy_answer(p, a, verify)
        else:
            continue
        v["sympy"] = s
        V[(v["o"], "agree" if s == v["planned"] else f"sympy {s}")] += 1
    if V:
        print("verification against SymPy's ask (distinct changed queries):")
        for k, c in sorted(V.items(), key=str):
            print(f"  {c:4d}  {k}")
    out["verify"] = {str(k): c for k, c in V.items()}
    # what the oracle leaves None among the fully readable: does SymPy decide?
    if verify and "--rest" in sys.argv:
        R = Counter(); Rq = Counter(); rest_ex = []
        done = {}
        for r in fr:
            if r["planned"] is not None:
                continue
            k = r["key"]
            if k not in done:
                done[k] = sympy_answer(*k, verify)
                if done[k] in (True, False) and len(rest_ex) < 15:
                    rest_ex.append(f"{done[k]} | {k[0]} | {k[1]}"[:220])
                R[str(done[k])] += 1
            Rq[str(done[k])] += 1
        out["rest_sympy_distinct"] = dict(R); out["rest_sympy_queries"] = dict(Rq)
        out["rest_examples"] = rest_ex
        print(f"fully readable, still None under the oracle; SymPy says (distinct): {dict(R)}; (queries): {dict(Rq)}")
    out["changed"] = [dict(p=str(k[0]), a=str(k[1]), **{x: (y if isinstance(y, (bool, int, type(None), list)) else str(y))
                                                         for x, y in v.items()}) for k, v in changed.items()]
    # 3. constants
    C = Counter(); Cq = Counter(); Cs = defaultdict(set)
    for r in un:
        cs = set()
        for _, n, info in r["bad"]:
            cs.update(info[2])
        for c in cs:
            Cq[c] += 1; Cs[c].add(r["key"][1])
    for n in seen:
        for c in ATOM_INFO[n][2]:
            C[c] += 1
    print(f"distinct constants (type a atoms): {len(Cq)}")
    out["constants"] = []
    for c, nq in Cq.most_common():
        b = bounds(c)
        row = dict(c=str(c), atoms=C[c], queries=nq, sessions=len(Cs[c]),
                   real=c.is_extended_real, finite=c.is_finite, float=isinstance(c, Float),
                   bound=None if b is None else [str(b[0].evalf(12)), str(b[1].evalf(12))],
                   evalf_ms=round(EVALF_MS.get(c, 0), 2))
        out["constants"].append(row)
    for row in out["constants"][:25]:
        print(f"  {row['c']:22s} atoms {row['atoms']:4d} queries {row['queries']:5d} sessions {row['sessions']:3d} "
              f"real {row['real']} bound {'ok' if row['bound'] else 'FAIL'}")
    json.dump(out, open(out_path, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
