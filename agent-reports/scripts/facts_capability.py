"""Stage 0 of the fact-lattice plan: capability census on the refine stream.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy:agent-reports/scripts \\
        python agent-reports/scripts/facts_capability.py stream.pkl out.json [--verify SECONDS]

Answers every query of the stream (in order, one answer memo per mode like
``sympy_api.ask``) under four *oracles* that approximate what the design
would add, and compares with the recording:

* ``base``: ``sympy_api._ask`` unchanged (must equal the recording);
* ``transfer``: predicate transfer across equalities (layer 2.2), encoded
  as explicit clauses, the plan's own fuzz oracle: for every equality atom
  ``eq(a, b)`` in the proposition or the assumptions, the assumptions get
  ``eq(a, b) -> (P(a) <-> P(b))`` for each of the 33 predicates.  No
  congruence closure over subterms (``f(x)``, ``f(y)``): EUF already
  merges those classes, but the oracle only transfers across equality
  atoms that occur, so it is a lower bound on layer 2.2 in that respect;
* ``free``: a relation no theory interprets stays a free Boolean instead
  of making the query None (the ``relations.py`` change of stage 2);
* ``both``: the two together.

Every answer that is definite under an oracle and None in the recording
is a *more-definite* answer; one that is the opposite definite value is a
contradiction (an oracle bug or an engine bug).  With ``--verify S`` each
distinct more-definite query is also asked of SymPy's own ``ask`` (with an
S-second alarm) and compared.
"""
import json, pickle, signal, sys, time
from collections import Counter

from satassume import sympy_api
from satassume.engine import Engine, InconsistentAssumptions
from satassume.formula import And, Equivalent, Implies, Not, Or, P, TRUE, FALSE, atoms_of
from satassume.relations import Relations, Uninterpreted
from satassume.rules import PREDICATES
from satassume.sympy_api import Unsupported, to_formula

_orig_process = Relations.process
FREE = [False]


def process(self, user_atoms=()):
    if not FREE[0]:
        return _orig_process(self, user_atoms)
    # the loop of Relations.process without the final Uninterpreted check
    s = self.session
    user = [a for a in user_atoms if a.pred in ("eq", "lt")]
    for a in user:
        for side in a.expr:
            self._link_later(side)
    while True:
        s._flush()
        s._discover()
        if self.queue:
            atom = self.queue.pop()
            self.status[atom] = self._interpret(atom)
            self.active = True
            continue
        if self.active and self.top:
            top, self.top = self.top, {}
            for e in top:
                self._link_later(e)
        if self._pending_links:
            self._link(self._pending_links.pop())
            continue
        if self._share():
            continue
        break


Relations.process = process


def eq_atoms(f):
    return [a for a in atoms_of(f) if a.pred == "eq"] if f is not None else []


def transfer(f_atoms):
    out = []
    for a in f_atoms:
        x, y = a.expr
        out.append(Implies(a, And(*[Equivalent(P(p, x), P(p, y)) for p in PREDICATES])))
    return out


def answer(eng, p, a, mode):
    """Like ``sympy_api._ask`` with the oracle of ``mode``; 'error' for
    inconsistent assumptions."""
    try:
        prop = to_formula(p, True)
        assum = None if a is True else to_formula(a, True)
    except Unsupported:
        return None, "unsupported"
    if prop is TRUE:
        return True, "trivial"
    if prop is FALSE:
        return False, "trivial"
    if assum is TRUE:
        assum = None
    if assum is FALSE:
        return "error", "trivial"
    extra = []
    if mode in ("transfer", "both"):
        extra = transfer(list(dict.fromkeys(eq_atoms(prop) + eq_atoms(assum))))
    if extra:
        assum = And(*([assum] if assum is not None else []), *extra)
    FREE[0] = mode in ("free", "both")
    try:
        if assum is None and isinstance(prop, P):
            return eng.is_(prop.expr, prop.pred), "is_"
        return eng.ask(prop, assum), "ask"
    except InconsistentAssumptions:
        return "error", "ask"
    except Uninterpreted:
        return None, "uninterpreted"
    finally:
        FREE[0] = False


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
    except Exception as e:           # noqa: BLE001 - recorded, not hidden
        return f"exception {type(e).__name__}"
    finally:
        signal.alarm(0)


def kind(p, a):
    """Short description of the relations in the query."""
    from sympy.core.relational import Relational
    from sympy.assumptions.assume import AppliedPredicate
    from sympy import preorder_traversal
    def rels(e):
        out = set()
        if e is True:
            return out
        for x in preorder_traversal(e):
            if isinstance(x, Relational):
                out.add({"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[x.rel_op])
            elif isinstance(x, AppliedPredicate) and str(x.function.name) in ("eq", "ne", "lt", "le", "gt", "ge"):
                out.add(str(x.function.name))
        return out
    ra, rp = rels(a), rels(p)
    return ("A:" + ",".join(sorted(ra)) if ra else "") + (" P:" + ",".join(sorted(rp)) if rp else "")


def main():
    stream = pickle.load(open(sys.argv[1], "rb"))
    out_path = sys.argv[2]
    verify = None
    if "--verify" in sys.argv:
        verify = int(sys.argv[sys.argv.index("--verify") + 1])
    modes = ["base", "transfer", "free", "both"]
    res = {}
    for mode in modes:
        eng = Engine()
        memo = {}
        t0 = time.perf_counter()
        outs = []
        for i, (p, a, rec) in enumerate(stream):
            key = (p, a)
            if key not in memo:
                memo[key] = answer(eng, p, a, mode)
            outs.append(memo[key][0])
        res[mode] = outs
        print(f"{mode}: {time.perf_counter() - t0:.1f}s", flush=True)
    rec = [r for _, _, r in stream]
    summary = {}
    newly = {}
    for mode in modes:
        C = Counter()
        for i, (o, r) in enumerate(zip(res[mode], rec)):
            if o == r:
                C["same"] += 1
            elif r is None and o in (True, False):
                C["more definite"] += 1
                newly.setdefault(i, {})[mode] = o
            elif o == "error":
                C["error (inconsistent)"] += 1
                newly.setdefault(i, {})[mode] = o
            elif o is None:
                C["less definite"] += 1
            else:
                C["contradiction"] += 1
                newly.setdefault(i, {})[mode] = o
        summary[mode] = dict(C)
        print(mode, dict(C))
    # distinct queries that change under some oracle
    distinct = {}
    for i, d in newly.items():
        p, a, r = stream[i]
        k = (p, a)
        e = distinct.setdefault(k, {"i": i, "n": 0, "rec": r, "modes": d, "kind": kind(p, a)})
        e["n"] += 1
    by_kind = Counter()
    for k, e in distinct.items():
        by_kind[(e["kind"], tuple(sorted(e["modes"])))] += 1
    print(f"distinct changed queries: {len(distinct)}")
    for (kd, ms), c in by_kind.most_common():
        print(f"  {c:4d}  {kd:24s} {','.join(ms)}")
    rows = []
    for (p, a), e in distinct.items():
        row = {"i": e["i"], "n": e["n"], "p": str(p), "a": str(a), "kind": e["kind"],
               "modes": {m: v for m, v in e["modes"].items()}}
        if verify:
            t = time.perf_counter()
            row["sympy"] = sympy_answer(p, a, verify)
            row["sympy_s"] = round(time.perf_counter() - t, 2)
        rows.append(row)
    if verify:
        V = Counter()
        for row in rows:
            for m, v in row["modes"].items():
                s = row["sympy"]
                V[(m, "agree" if s == v else "sympy None" if s is None else f"sympy {s}")] += 1
        print("verification against sympy.ask (per distinct query and mode):")
        for k, c in sorted(V.items()):
            print(f"  {c:4d}  {k}")
    json.dump({"summary": summary, "rows": rows}, open(out_path, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
