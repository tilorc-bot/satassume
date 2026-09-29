"""Stage 0 of the fact-lattice plan: what attaching a theory to every session
costs before the theory does any work, and what one theory propagation costs
against one rule-block implication.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/scripts/facts_theory_tax.py \\
        replay stream.pkl {plain|noop|noop-prop}
    ... facts_theory_tax.py micro

``replay``: one cold pass of the stream (answers checked), printing its wall
time.  ``noop`` attaches a theory that registers no atom and never answers
to every session's solver (``Session.__init__``), which is the least any
``FactTheory`` costs: with a theory attached the solver routes propagation
through ``_tpropagate``/``_theory_sync``, keeps no held assumption levels
(``Solver._assume``: held levels only without theories) and never caches a
propagation during which a theory propagated.  ``noop-prop`` adds a
``propagate`` method returning nothing (one extra call per sync).

``micro``: per-literal cost of an implication made by the rule block
(``register_block``, ``integer`` asserted on N fresh blocks, the block
implies 15 literals each) against the same implications made by a theory
through ``propagate`` with eager reasons (``Solver._theory_imply``), at a
decision level (under an assumption), where a theory reason becomes a
learnt clause.
"""
import pickle, sys, time

from satassume.engine import Session
from satassume.rules import NPRED, PRED_INDEX, RULE_INTERNAL, RULE_INSTANTIATED, unit_propagate
from satassume.solver import Solver


class NoopTheory:
    def register_atom(self, literal, payload):
        pass

    def assert_lit(self, literal):
        return None

    def check(self):
        return None

    def push_level(self):
        pass

    def pop_level(self):
        pass


class NoopPropTheory(NoopTheory):
    def propagate(self):
        return ()


def replay(path, mode):
    if mode != "plain":
        cls = NoopTheory if mode == "noop" else NoopPropTheory
        orig = Session.__init__

        def init(self, engine):
            orig(self, engine)
            self.solver.attach_theory(cls())
        Session.__init__ = init
    from satassume.sympy_api import ask
    stream = pickle.load(open(path, "rb"))
    t0 = time.perf_counter()
    bad = 0
    for p, a, r in stream:
        if ask(p, a) is not r:
            bad += 1
    dt = time.perf_counter() - t0
    print(f"{mode}: cold pass {dt:.3f}s, answers differing {bad}")


class ClosureTheory:
    """Propagates, for each asserted ``integer`` literal of a block, the
    block's rule consequences with the reason ``[lit, -integer]``."""

    def __init__(self, bases, cons):
        self.bases = bases
        self.cons = cons          # predicate offsets implied by integer
        self.pending = []
        self.reg = set()

    def register_atom(self, literal, payload):
        self.reg.add(literal)

    def assert_lit(self, literal):
        if literal > 0 and literal in self.bases:
            self.pending.append(literal)
        return None

    def propagate(self):
        out = []
        for v in self.pending:
            b = self.bases[v]
            for off, sign in self.cons:
                x = (b + off) * sign
                out.append((x, [x, -v]))
        self.pending = []
        return out

    def check(self):
        return None

    def push_level(self):
        pass

    def pop_level(self):
        self.pending = []


def micro(nblocks=2000, reps=5):
    integer = PRED_INDEX["integer"]
    implied = sorted(unit_propagate(RULE_INSTANTIATED, [integer + 1]))
    cons = [(abs(l) - 1, 1 if l > 0 else -1) for l in implied if abs(l) - 1 != integer]
    print(f"integer implies {len(cons)} literals by the rule block")
    best = {}
    for rep in range(reps):
        # rule block
        s = Solver()
        s.set_rule_block(RULE_INTERNAL, NPRED)
        sel = s.new_var()
        bases = []
        for k in range(nblocks):
            b = s.nvars() + 1
            s.ensure_vars(b + NPRED - 1)
            s.register_block(b)
            bases.append(b)
            s.add_clause([-sel, b + integer])
        t0 = time.perf_counter()
        tr = s.implied([sel])
        t_rule = time.perf_counter() - t0
        n_rule = len(tr)
        # theory
        s = Solver()
        sel = s.new_var()
        vb = {}
        for k in range(nblocks):
            b = s.nvars() + 1
            s.ensure_vars(b + NPRED - 1)
            vb[b + integer] = b
            s.add_clause([-sel, b + integer])
        th = ClosureTheory(vb, cons)
        s.attach_theory(th)
        for v in vb:
            s.register_atom(th, v, None)
        for v, b in vb.items():
            for off, sign in cons:
                s.register_atom(th, b + off, None)
        t0 = time.perf_counter()
        tr = s.implied([sel])
        t_th = time.perf_counter() - t0
        n_th = len(tr)
        for k, v in (("rule", t_rule), ("theory", t_th)):
            best[k] = min(best.get(k, 1e9), v)
        print(f"rep {rep}: rule block {t_rule * 1e3:.1f} ms for {n_rule} literals; "
              f"theory {t_th * 1e3:.1f} ms for {n_th} literals")
    n = nblocks * len(cons)
    print(f"best: rule block {best['rule'] / n * 1e6:.2f} us per implied literal, "
          f"theory {best['theory'] / n * 1e6:.2f} us per implied literal "
          f"(ratio {best['theory'] / best['rule']:.1f}x)")


if __name__ == "__main__":
    if sys.argv[1] == "replay":
        replay(sys.argv[2], sys.argv[3])
    else:
        micro()
