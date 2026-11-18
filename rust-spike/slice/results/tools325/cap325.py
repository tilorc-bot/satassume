"""cap325.py WL OUT.jsonl [CAP] [--only i,j,...] (sa-port-325, issue 323): the None-certify scratch check. OFFLINE ONLY.

One pass of a workload (dev, or fuzz seed 424242, as tools322/nc322.py reads them) through the PURE-PYTHON package of the
worktree (no Rust backend installed, no package source changed). The driver wraps, in its own process only,
``Engine._ask``, ``Engine._complete_check``, ``Solver._solve``, ``Solver.entails`` and ``Solver.entails_all`` to copy the
model of every satisfiable solve of the query's DECIDING entailment (the last one on the session ``Engine._ask`` answers
in) and of the set's complete check. The answers' digest is printed so it can be compared with the Rust arm's.

Per query it then records, all by exact substitution into the ORIGINAL proposition and assumptions (exact325.py):
  model   for each polarity (proposition True / False): does a point read from one of the deciding entailment's models
          satisfy the assumptions and give the proposition that value? ok / fail / unk (uncheckable), with the reason.
          The point: a symbol's LRA value when its predicate block says finite and extended real, else the first
          representative (REPS) whose basis row equals the block ("faithful": every symbol's value has the block's row).
  check   the same for the point of the set's complete check (one point: which polarity it gives, if any).
  search  session-free: simple points from the assumptions and the proposition alone (POOL and the query's own constants),
          simplest first, at most CAP exact substitutions; the first point certifying each polarity, and how many
          substitutions that took. Run for EVERY query, so a definite answer contradicted by two certified witnesses
          would show.
A heuristic picks every candidate point; only the exact substitution decides.
"""
import hashlib, itertools, json, os, sys, time
from fractions import Fraction

args = [a for a in sys.argv[1:] if not a.startswith("--")]
wl, out = args[0], args[1]
CAP = int(args[2]) if len(args) > 2 else 2000
only = None
for a in sys.argv[1:]:
    if a.startswith("--only="):
        only = set(int(t) for t in a[7:].split(","))

from sympy import I, Integer, Rational, S, Symbol, oo, zoo, pi, sqrt, Q, And, Not
from satassume import sympy_api, engine as E
from satassume.sat.solver import Solver
from satassume.knowledge.rules import NPRED
import satassume
import exact325 as X

if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    from evalbench.common import workload
    pairs = workload(wl)

R = Rational
REPS = [Integer(n) for n in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 9, -9)] + \
       [R(1, 2), R(-1, 2), R(3, 2), R(-3, 2), R(1, 3), R(-1, 3), Integer(8), Integer(10), Integer(12), Integer(7),
        oo, -oo, zoo, I, -I, 2 * I, 1 + I, R(1, 2) + I, pi, -pi, pi / 2, -pi / 2] + list(X.NAMED)
REP_ROWS = [X.basis_row(*X.kind(v)) for v in REPS]
POOL = [Integer(0), Integer(1), Integer(-1), Integer(2), Integer(-2), R(1, 2), R(-1, 2), Integer(3), Integer(-3), R(3, 2),
        R(-3, 2), Integer(4), Integer(-4), Integer(5), Integer(-5), R(1, 3), R(-1, 3), Integer(10), Integer(-10)]
SPECIAL = [oo, -oo, I, -I, zoo, 1 + I, -1 + I, 1 - I, -1 - I, 2 * I, sqrt(2), pi]
STRUCT = [X.BIDX[n] for n in ("complex", "extended_negative", "extended_positive", "extended_real", "finite", "imaginary",
                              "zero")]

# ---------------------------------------------------------------- hooks (this process only)
STACK = []      # Engine._ask frames
TOP = []        # finished top-level frames of the current query
CHECKS = []     # (session, snapshot) of consistent complete checks of the current query
ENT = [None]    # the entailment being run: (frame, list)


def snap(solver):
    m = solver._model
    return (dict(m) if m is not None else None, solver.theory_models())


_ask0 = E.Engine._ask


def _ask(self, s, lits, proposition, contextual):
    fr = dict(s=s, ents=[], ctx=contextual)
    STACK.append(fr)
    try:
        r = _ask0(self, s, lits, proposition, contextual)
        fr["r"] = r
        return r
    finally:
        STACK.pop()
        if not STACK:
            TOP.append(fr)


E.Engine._ask = _ask
_decide0 = E.Engine._decide


def _decide(self, s, lit, lits=()):
    # a context-free query is answered by Engine.is_ through _decide: the same frame as _ask's
    fr = dict(s=s, ents=[], ctx=False, via="decide")
    STACK.append(fr)
    try:
        r = _decide0(self, s, lit, lits)
        fr["r"] = r
        return r
    finally:
        STACK.pop()
        if not STACK:
            TOP.append(fr)


E.Engine._decide = _decide
_cc0 = E.Engine._complete_check


def _cc(s, lits):
    v = _cc0(s, lits)
    try:
        CHECKS.append((s, snap(s.solver), str(v)))
    except Exception as ex:
        CHECKS.append((s, None, "snap raised " + type(ex).__name__))
    return v


E.Engine._complete_check = staticmethod(_cc)
_solve0 = Solver._solve


def _solve(self, lits, keep):
    r = _solve0(self, lits, keep)
    e = ENT[0]
    if e is not None and e[0] is self:
        e[1].append(snap(self) if r else None)
    return r


Solver._solve = _solve


def _wrap_ent(name):
    f0 = getattr(Solver, name)

    def f(self, *a, **k):
        fr = STACK[-1] if STACK else None
        mine = fr is not None and fr["s"].solver is self and ENT[0] is None
        if mine:
            rec = dict(kind=name, solves=[])
            ENT[0] = (self, rec["solves"])
        try:
            r = f0(self, *a, **k)
            if mine:
                rec["r"] = r
                fr["ents"].append(rec)
            return r
        finally:
            if mine:
                ENT[0] = None
    setattr(Solver, name, f)


_wrap_ent("entails")
_wrap_ent("entails_all")

# ---------------------------------------------------------------- points


def declared(sym):
    d = getattr(sym, "_assumptions_orig", None) or {}
    return {k: v for k, v in d.items() if not (k == "commutative" and v is True)}


def effective_assumptions(p, a, syms):
    """The assumptions with the symbols' own declared assumptions added as predicates (uncheckable if outside Q)."""
    extra = []
    for s in syms:
        for k, v in declared(s).items():
            pr = getattr(Q, k, None)
            if pr is None:
                extra.append(Symbol("declared_" + k))        # truth() reports it as uncheckable
            else:
                extra.append(pr(s) if v else Not(pr(s)))
    return And(a, *extra) if extra else a


def sym_value(v):
    if isinstance(v, Fraction):
        return Rational(v.numerator, v.denominator)
    if isinstance(v, int):
        return Integer(v)
    return None


def decode(s, sn, syms):
    """(point, info) from a snapshot of session ``s``. A model gives a symbol an LRA value (when a relation mentions it)
    and a block of 14 basis truth values; the blocks of the compound nodes (x + 1, n/2, ...) constrain the symbols too.
    Candidates per symbol: its LRA value when the block says finite and extended real, then every representative with the
    block's exact row, then (if none) those agreeing on STRUCT. The combination kept is the one under which the most
    blocks (symbols and compound nodes, as far as the node's value is of a decided kind) equal the model's.
    info: nodes = blocks compared, bad = blocks the point does not reproduce, und = compound nodes of undecided kind."""
    mdl, tms = sn
    lra = {}
    for tm in tms or ():
        if isinstance(tm, dict):
            for k, v in tm.items():
                if getattr(k, "is_Symbol", False):
                    lra[k] = v
    info = dict(lra=0, rep=0, relaxed=0, norep=0, missing=0, lra_nonq=0, nodes=0, bad=0, und=0, closed=0, opq=0, opq_bad=0)
    terms = []
    for tm in tms or ():
        if isinstance(tm, dict):
            for k, v in tm.items():
                if hasattr(k, "free_symbols") and not getattr(k, "is_Symbol", False):
                    terms.append((k, v))

    def block_of(node):
        b = s.base.get(node)
        if b is None or mdl is None:
            return None
        blk = tuple(mdl.get(b + i) for i in range(NPRED))
        return None if None in blk else blk
    cands, blocks, how = {}, {}, {}
    for x in syms:
        block = block_of(x)
        lv = lra.get(x)
        if lv is not None and sym_value(lv) is None:
            info["lra_nonq"] += 1
            lv = None
        lst = []
        if block is None:
            if lv is not None:
                lst = [sym_value(lv)]
            else:
                info["missing"] += 1
                continue
        else:
            blocks[x] = block
            if lv is not None and block[X.BIDX["finite"]] and block[X.BIDX["extended_real"]]:
                lst.append(sym_value(lv))
            ex = [v for v, row in zip(REPS, REP_ROWS) if X.same(row, block) and v not in lst]
            lst += ex
            if not ex:
                lst += [v for v, row in zip(REPS, REP_ROWS) if all(row[j] == block[j] for j in STRUCT) and v not in lst][:8]
            if not lst:
                info["norep"] += 1
                continue
        cands[x] = lst[:10]
        how[x] = (lra.get(x) is not None, block)
    have = list(cands)
    hs = set(have)
    nodes = []
    for node in s.base:
        if not getattr(node, "is_Symbol", False) and getattr(node, "free_symbols", None) and node.free_symbols <= hs:
            blk = block_of(node)
            if blk is not None:
                nodes.append((node, blk))
    best = None
    for n, combo in enumerate(itertools.product(*[cands[x] for x in have])):
        pt = dict(zip(have, combo))
        bad = und = 0
        for x in have:
            if x in blocks and not X.same(X.basis_row(*X.kind(pt[x])), blocks[x]):
                bad += 1
        for node, blk in nodes:
            k = X.term(node, pt)
            if k[0] is None:
                und += 1
            elif not X.same(X.basis_row(*k), blk):
                bad += 1
        if best is None or (bad, und) < best[0]:
            best = ((bad, und), pt)
            if bad == 0 and und == 0:
                break
        if n >= 400:
            break
    point = best[1] if best else {}
    if best:
        info["bad"], info["und"] = best[0]
    info["nodes"] = len(nodes) + len(blocks)
    # the LRA model's own values of terms that are not symbols: a closed term (pi) given a rational, an opaque compound
    # term (x*y) whose value is not what the point gives it
    for k, v in terms:
        if not k.free_symbols:
            info["closed"] += 1
            kk = X.kind(k)
            if kk[0] != "q" or sym_value(v) is None or kk[1] != Fraction(v):
                info["opq_bad"] += 1
        elif k.free_symbols <= set(point):
            info["opq"] += 1
            kk = X.term(k, point)
            if sym_value(v) is None or kk[0] != "q" or kk[1] != Fraction(v):
                info["opq_bad"] += 1
    for x in have:
        v = point[x]
        if how[x][0] and v.is_Rational and sym_value(lra[x]) == v:
            info["lra"] += 1
        elif x in blocks and X.same(X.basis_row(*X.kind(v)), blocks[x]):
            info["rep"] += 1
        else:
            info["relaxed"] += 1
    return point, info


def fill(p, a, point, syms, cap=300):
    """Values for the symbols the model does not hold (the relevance split leaves part of the set out of the session):
    the first simple values that keep the assumptions true or undecided-but-not-false. Returns the number filled."""
    miss = [x for x in syms if x not in point]
    if not miss:
        return 0
    n = 0
    for combo in itertools.product(POOL + SPECIAL, repeat=len(miss)):
        n += 1
        pt = dict(point); pt.update(zip(miss, combo))
        if X.truth(a, pt) is True:
            point.update(zip(miss, combo))
            return len(miss)
        if n >= cap:
            break
    point.update((x, POOL[0]) for x in miss)
    return len(miss)


def query_constants(p, a):
    ks = set()
    for e in (p, a):
        for n in e.atoms(Rational):
            ks.add(n)
        for n in e.atoms(S.Pi.__class__):
            pass
    # the floor and ceiling of every closed real subterm (pi/2 -> 1, 2), by exact integer comparison of its evalf
    from sympy import preorder_traversal, floor, ceiling
    for e in (p, a):
        for n in preorder_traversal(e):
            if getattr(n, "is_number", False) and not n.is_Rational and getattr(n, "is_extended_real", None):
                try:
                    f = n.evalf(30)
                    ks.add(Integer(int(floor(f)))); ks.add(Integer(int(ceiling(f))))
                except Exception:
                    pass
    return ks


def pool_for(p, a):
    """(head, tail) of the common pool: the simplest values and the query's own constants; then the rest."""
    ks = sorted(query_constants(p, a), key=lambda v: (abs(v), v))
    extra = []
    for k in ks:
        extra += [k, k + 1, k - 1, k + R(1, 2), k - R(1, 2)]
    if p.has(pi) or (hasattr(a, "has") and a.has(pi)):
        extra += [pi / 2, -pi / 2, pi, -pi, 3 * pi / 2, -3 * pi / 2, 2 * pi, -2 * pi, pi / 4, -pi / 4]
    return POOL[:7], extra + SPECIAL[:10] + POOL[7:] + SPECIAL[10:]


def conjuncts(a):
    return list(a.args) if isinstance(a, And) else [a]


SMALL = [Integer(0), Integer(1), Integer(-1), Integer(2), R(1, 2), Integer(-2)]


def lin_roots(p, a, syms):
    """Per symbol, the exact roots of the query's atoms that are linear in it with a rational coefficient: for a relation
    lhs - rhs = 0, for a predicate of a compound term t, t = 0 and t = 1; the other symbols at a few small values. A root
    is kept when it is rational or a + b*pi (a kind the evaluator decides)."""
    from sympy.assumptions.assume import AppliedPredicate
    from sympy.core.relational import Relational
    exprs = []
    for e in (p, a):
        if not hasattr(e, "atoms"):
            continue
        try:
            for at in e.atoms(AppliedPredicate):
                g = at.arguments
                if len(g) == 2:
                    exprs.append(g[0] - g[1])
                elif len(g) == 1 and hasattr(g[0], "is_Symbol") and not g[0].is_Symbol:
                    exprs += [g[0], g[0] - 1]
            for at in e.atoms(Relational):
                exprs.append(at.lhs - at.rhs)
        except Exception:
            pass
    crit = {x: [] for x in syms}
    for d in exprs:
        try:
            fs = d.free_symbols
            for x in fs:
                if x not in crit:
                    continue
                c = d.diff(x)
                if c.free_symbols or not c.is_Rational or c == 0:
                    continue
                others = sorted(fs - {x}, key=str)
                for combo in itertools.islice(itertools.product(SMALL, repeat=len(others)), 12):
                    pt = dict(zip(others, combo)); pt[x] = Integer(0)
                    v = d.xreplace(pt)
                    if X.kind(v)[0] in ("q", "p"):
                        r = -v / c
                        if r not in crit[x]:
                            crit[x].append(r)
        except Exception:
            continue
    return crit


def crit_values(cs):
    """The roots, the midpoints of neighbours (so a narrow gap such as 3/2 < x < pi/2 gets a point) and a step outside."""
    keyed = sorted(((float(c), c) for c in cs[:12]), key=lambda t: t[0])
    outv = [c for _, c in keyed]
    for (f1, c1), (f2, c2) in zip(keyed, keyed[1:]):
        if f2 > f1:
            outv.append((c1 + c2) / 2)
    if keyed:
        lo, hi = keyed[0][1], keyed[-1][1]
        outv += [lo - 1, hi + 1, lo - R(1, 2), hi + R(1, 2)]
    return outv


def pools(p, a, syms):
    """One pool per symbol: head, the symbol's roots and midpoints, tail; without the values a one-symbol conjunct of
    the assumptions makes False."""
    head, tail = pool_for(p, a)
    crit = lin_roots(p, a, syms)
    per = {}
    for x in syms:
        seen, lst = set(), []
        for v in head + crit_values(crit[x]) + tail:
            if v not in seen:
                seen.add(v); lst.append(v)
        per[x] = lst
    for c in conjuncts(a):
        fs = getattr(c, "free_symbols", set())
        if len(fs) == 1:
            x = next(iter(fs))
            if x in per:
                per[x] = [v for v in per[x] if X.truth(c, {x: v}) is not False]
    return [per[x] for x in syms]


def by_index_sum(sizes):
    """All index tuples over the given sizes, smallest index sum first."""
    for tot in range(0, sum(m - 1 for m in sizes) + 1):
        for t in _compositions(sizes, 0, tot):
            yield t


def _compositions(sizes, k, tot):
    m = sizes[k]
    if k == len(sizes) - 1:
        if tot < m:
            yield (tot,)
        return
    for i in range(min(tot, m - 1) + 1):
        for rest in _compositions(sizes, k + 1, tot - i):
            yield (i,) + rest


def search(p, a, syms, cap):
    """Session-free: the first point certifying each value of p, the substitutions used when each was found, and a
    tally of the points tried: A true with p True / False / undecided, A undecided (with the first reason of each)."""
    res = {True: None, False: None}
    at = {True: None, False: None}
    tl = dict(n=0, sat=0, nT=0, nF=0, punk=0, aunk=0, pwhy=None, awhy=None)
    if not syms:
        return res, at, tl
    ps = pools(p, a, syms)
    if any(not q for q in ps):
        return res, at, tl
    for idx in by_index_sum([len(q) for q in ps]):
        pt = {x: q[i] for x, q, i in zip(syms, ps, idx)}
        tl["n"] += 1
        ta = X.truth(a, pt)
        if ta is True:
            tl["sat"] += 1
            tp = X.truth(p, pt)
            if tp is True or tp is False:
                tl["nT" if tp else "nF"] += 1
                if res[tp] is None:
                    res[tp] = pt; at[tp] = tl["n"]
                    if res[not tp] is not None:
                        break
            else:
                tl["punk"] += 1
                if tl["pwhy"] is None:
                    tl["pwhy"] = tp[:80]
        elif ta is not False:
            tl["aunk"] += 1
            if tl["awhy"] is None:
                tl["awhy"] = ta[:80]
        if tl["n"] >= cap:
            break
    return res, at, tl


def pstr(pt):
    return None if pt is None else ", ".join("%s=%s" % (k, v) for k, v in sorted(pt.items(), key=lambda kv: str(kv[0])))


def model_part(p, a, syms, fr):
    """The (a) record of a None query from its deciding entailment's models."""
    ents = fr["ents"]
    if not ents:
        return dict(ent=None)
    ent = ents[-1]
    sn = [x for x in ent["solves"] if x is not None]
    rec = dict(ent=ent["kind"], r=str(ent.get("r")), solves=len(ent["solves"]), sat=len(sn), nents=len(ents))
    per = []
    for x in sn:
        pt, info = decode(fr["s"], x, syms)
        info["filled"] = fill(p, a, pt, syms)
        ta, tp = X.truth(a, pt), X.truth(p, pt)
        per.append(dict(pt=pstr(pt), ta=ta, tp=tp, info=info, lra=str([t for t in (x[1] or ()) if isinstance(t, dict) and any(hasattr(k, "free_symbols") for k in t)])[:300]))
    rec["snaps"] = per
    for want in (True, False):
        best = None
        for d in per:
            ta, tp = d["ta"], d["tp"]
            if ta is True and tp is (not want):
                continue                # this model is the other polarity's witness
            if ta is True and tp is want:
                v = ("ok", "", d)
            elif ta is False:
                v = ("fail", "assumptions false at the model's point", d)
            elif tp is (not want):
                v = ("unk", "assumptions: " + str(ta), d)      # other polarity's model, itself uncheckable
                continue
            elif ta is not True:
                v = ("unk", "assumptions: " + str(ta), d)
            else:
                v = ("unk", "proposition: " + str(tp), d)
            rank = {"ok": 0, "unk": 1, "fail": 2}[v[0]]
            if best is None or rank < best[0]:
                best = (rank, v)
        if best is None:
            rec["T" if want else "F"] = dict(v="fail", why="no model of the entailment gives this value")
        else:
            v = best[1]
            rec["T" if want else "F"] = dict(v=v[0], why=v[1], pt=v[2]["pt"], info=v[2]["info"], lra=v[2]["lra"])
    return rec


def run():
    ans = []
    fh = open(out, "w")
    t00 = time.time()
    for i, (p, a) in enumerate(pairs):
        TOP.clear(); CHECKS.clear(); ENT[0] = None; del STACK[:]
        try:
            r = sympy_api.ask(p, a)
            if r is not None and r is not True and r is not False:
                r = "non-bool " + repr(r)
        except ValueError:
            r = "ValueError"
        except Exception as e:
            r = "raise " + type(e).__name__
        ans.append(r)
        if only is not None and i not in only:
            continue
        row = dict(i=i, ans=r)
        try:
            syms = sorted((p.free_symbols if hasattr(p, "free_symbols") else set()) |
                          (a.free_symbols if hasattr(a, "free_symbols") else set()), key=str)
            a_eff = effective_assumptions(p, a, syms) if a is not True else effective_assumptions(p, S.true, syms)
            row["nsym"] = len(syms)
            row["declared"] = sum(1 for s in syms if declared(s))
            row["arith"] = X.arith_only(p) and (a is True or X.arith_only(a))
            row["frames"] = len(TOP)
            if r is None and TOP:
                fr = TOP[-1]
                row["model"] = model_part(p, a_eff, syms, fr)
                cs = [c for c in CHECKS if c[0] is fr["s"] and c[1] is not None]
                if cs:
                    pt, info = decode(fr["s"], cs[-1][1], syms)
                    info["filled"] = fill(p, a_eff, pt, syms)
                    row["check"] = dict(pt=pstr(pt), ta=X.truth(a_eff, pt), tp=X.truth(p, pt), info=info, verdict=cs[-1][2])
            t0 = time.perf_counter()
            res, at, tl = search(p, a_eff, syms, CAP)
            row["search"] = dict(T=pstr(res[True]), F=pstr(res[False]), atT=at[True], atF=at[False],
                                 s=round(time.perf_counter() - t0, 5), **tl)
        except Exception as ex:
            import traceback
            row["error"] = type(ex).__name__ + ": " + str(ex)[:200] + " | " + traceback.format_exc()[-300:]
        if only is not None or r is None:
            row["q"] = str(p)[:300]; row["a"] = str(a)[:300]
        fh.write(json.dumps(row, default=str) + "\n")
    fh.close()
    head = dict(wl=wl, n=len(pairs), digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16], cap=CAP,
                package=os.path.dirname(satassume.__file__), wall=round(time.time() - t00, 1),
                hashseed=os.environ.get("PYTHONHASHSEED"))
    json.dump(head, open(out + ".head", "w"))
    print(json.dumps(head))


if __name__ == "__main__":
    run()
