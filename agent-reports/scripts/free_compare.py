"""Free-Boolean re-measurement, step 2: compare default and free answers.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python \\
        agent-reports/scripts/free_compare.py STREAM DEFAULT.json FREE.json OUT.json [--verify S]

Classifies every stream query (default answer -> free answer): same, more
definite (None -> True/False), new error (-> ValueError), lost error, less
definite, flipped.  With ``--verify S`` every distinct changed query is
asked of SymPy's ``ask`` (S-second alarm).  Also a static census of the
relation atoms no theory reads (``unreadable``), by kind, over the
distinct queries and weighted by stream occurrences.
"""
import json, pickle, signal, sys
from collections import Counter

from sympy import Float, I, S, Mul, Add, Pow, Symbol
from sympy.core.relational import Relational

from satassume import lra_adapter
from satassume.euf_adapter import EUFAdapter
from satassume.formula import atoms_of
from satassume.relations import RELATION_ATOMS, sympy_atom
from satassume.sympy_api import Unsupported, to_formula

INF = (S.NaN, S.Infinity, S.NegativeInfinity, S.ComplexInfinity)


def sympy_answer(p, a, secs):
    from sympy import ask as sask

    def alarm(*_):
        raise TimeoutError
    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(secs)
    try:
        return sask(p, a)
    except TimeoutError:
        return "timeout"
    except ValueError:
        return "error"
    except Exception as e:           # noqa: BLE001 - recorded, not hidden
        return f"exception {type(e).__name__}"
    finally:
        signal.alarm(0)


def classify(d, f):
    if d == f:
        return "same"
    if d is None and f in (True, False):
        return "more definite"
    if f == "error":
        return "new error"
    if d == "error":
        return "lost error"
    if f is None:
        return "less definite"
    return "flipped"


def readable(atom):
    sat = sympy_atom(atom)
    if lra_adapter.interpret(sat) is not None:
        return True
    return atom.pred == "eq" and EUFAdapter.parse(sat) is not None


def why(atom):
    """Kind of an unreadable relation atom (first matching reason)."""
    a, b = atom.expr
    e = a - b if all(getattr(x, "is_Matrix", False) is False for x in (a, b)) else None
    sides = (a, b)
    if any(getattr(x, "is_Matrix", False) or getattr(x, "is_MatrixExpr", False) for x in sides):
        return "matrix"
    if any(x.has(*INF) for x in sides):
        return "oo/zoo/nan"
    if any(x.has(Float) for x in sides):
        return "Float"
    for x in (a, b):
        for t in Add.make_args(x):
            if t.free_symbols and t.is_Mul:
                c = [f for f in t.args if not f.free_symbols and not f.is_Rational]
                if c:
                    if any(f.has(I) for f in c):
                        return "I*x (imaginary coefficient)"
                    return "c*x (irrational coefficient: pi*x, sqrt(2)*x)"
            if not t.free_symbols and not t.is_Rational:
                if t.has(I) or t.is_extended_real is not True:
                    return "non-real constant (I, ...)"
                return "constant without bounds"
    return "other"


def unreadable(p, a):
    """Unreadable relation atoms of the query: (in proposition, in assumptions)."""
    out = []
    for e in (p, a):
        if e is True:
            out.append([])
            continue
        try:
            f = to_formula(e, True)
        except Unsupported:
            out.append([])
            continue
        out.append([x for x in atoms_of(f) if getattr(x, "pred", None) in RELATION_ATOMS
                    and not readable(x)])
    return out


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    stream = pickle.load(open(args[0], "rb"))
    d = json.load(open(args[1]))
    f = json.load(open(args[2]))
    verify = int(sys.argv[sys.argv.index("--verify") + 1]) if "--verify" in sys.argv else None
    C = Counter()
    rows = {}
    print(f"default {d['seconds']:.2f}s, free {f['seconds']:.2f}s")
    for i, ((p, a, _), x, y) in enumerate(zip(stream, d["answers"], f["answers"])):
        k = classify(x, y)
        C[k] += 1
        if k != "same":
            r = rows.setdefault((p, a), {"i": i, "n": 0, "p": str(p), "a": str(a),
                                         "default": x, "free": y, "kind": k, "_q": (p, a)})
            r["n"] += 1
    print("stream:", dict(C), "distinct changed:", len(rows))
    print("distinct by kind:", dict(Counter(r["kind"] for r in rows.values())))
    # unreadable census
    U = Counter(); Uw = Counter(); Q = Counter(); Qw = Counter()
    seen = {}
    atoms = {}
    AF = Counter()
    for (p, a, _), x, y in zip(stream, d["answers"], f["answers"]):
        key = (p, a)
        if key not in seen:
            up, ua = unreadable(p, a)
            seen[key] = (up, ua)
            new = True
        else:
            up, ua = seen[key]
            new = False
        if not (up or ua):
            continue
        where = "P+A" if up and ua else "P" if up else "A"
        AF[(str(x), str(y))] += 1
        Qw[where] += 1
        kinds = {why(x) for x in up + ua}
        for x in up + ua:
            atoms.setdefault(why(x), {}).setdefault(str(sympy_atom(x)), 0)
            atoms[why(x)][str(sympy_atom(x))] += 1
        for kd in kinds:
            Uw[kd] += 1
        if new:
            Q[where] += 1
            for kd in kinds:
                U[kd] += 1
    print("their answers (default, free):", dict(AF))
    census = {"answers_default_free": {f"{k[0]}->{k[1]}": v for k, v in AF.items()},"queries_with_unreadable": {"distinct": dict(Q), "stream": dict(Qw)},
              "by_kind_distinct": dict(U), "by_kind_stream": dict(Uw),
              "atoms": atoms}
    print("queries with an unreadable relation (distinct):", dict(Q), "(stream):", dict(Qw))
    for kd, c in U.most_common():
        print(f"  {c:5d} distinct {Uw[kd]:6d} stream  {kd}; {len(atoms[kd])} atoms, e.g.",
              "; ".join(sorted(atoms[kd], key=lambda t: -atoms[kd][t])[:4]))
    # changed rows: the unreadable atoms and SymPy's answer
    for r in rows.values():
        up, ua = seen[r["_q"]]
        r["unreadable"] = [str(sympy_atom(x)) for x in up + ua]
        r["unreadable_kinds"] = sorted({why(x) for x in up + ua})
    if verify:
        V = Counter()
        for r in rows.values():
            p, a = r["_q"]
            r["sympy"] = s = sympy_answer(p, a, verify)
            V[(r["kind"], "agree" if s == r["free"] else f"sympy {s}")] += 1
        for k, c in sorted(V.items(), key=str):
            print(f"  {c:4d}  {k}")
    for r in rows.values():
        del r["_q"]
    json.dump({"summary": dict(C), "census": census,
               "rows": sorted(rows.values(), key=lambda r: r["i"])},
              open(args[3], "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
