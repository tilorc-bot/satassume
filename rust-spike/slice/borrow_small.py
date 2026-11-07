"""Smallest case: a theory hook that reads the solver during a call into the crate's Solver."""
import backend
from satassume.sat.solver import Solver as Py
class T:
    def __init__(self, s): self.s = s; self.seen = []
    def __getattr__(self, name):
        def hook(*a, **k):
            self.seen.append(self.s.nvars())
            return [] if name == "propagate" else None
        return hook
for name, make in (("python", Py), ("rust", backend.RustSolver)):
    s = make(); a = s.new_var(); t = T(s)
    try:
        s.attach_theory(t); s.add_clause([a]); r = s.solve([])
        print(name, "ok", r, "reads", len(t.seen))
    except Exception as e:
        print(name, type(e).__name__, e, "reads", len(t.seen))
