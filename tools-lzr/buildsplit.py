import sys, time, collections
from satassume import relations as R, engine as E, sympy_api
from satassume.sat import solver as SV
from satassume.theories.euf import euf_adapter as EA
from satassume.theories.lra import lra_adapter as LA
from evalbench.common import workload, ask_all
T = collections.Counter(); depth = [0, 0]   # in build, in a leaf
def wrap(cls, name, key, top=False):
    f = getattr(cls, name)
    def w(*a, **k):
        if top:
            depth[0] += 1; t = time.perf_counter()
            try: return f(*a, **k)
            finally: T[key] += time.perf_counter() - t; depth[0] -= 1
        if not depth[0] or depth[1]: return f(*a, **k)
        depth[1] = 1; t = time.perf_counter()
        try: return f(*a, **k)
        finally: T[key] += time.perf_counter() - t; depth[1] = 0
    setattr(cls, name, w)
wrap(R.Relations, "build", "build", top=True)
wrap(SV.Solver, "add_clause", "solver.add_clause")
wrap(SV.Solver, "register_atom", "solver.register_atom")
wrap(SV.Solver, "ensure_vars", "solver.ensure_vars")
wrap(EA.EUFAdapter, "term", "euf.term (interning)")
wrap(E.Session, "ensure", "session.ensure (nodes)")
wrap(LA.LRAAdapter, "register_integer", "lra.register_integer")
wrap(LA.LRAAdapter, "register_bounds", "lra.register_bounds")
if sys.argv[1] == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(int(sys.argv[2]))
else:
    pairs = workload(sys.argv[1])
ask_all(sympy_api.ask, pairs)
b = T.pop("build"); reg = sum(T.values())
print("build %.3fs  registration %.3fs (%.0f%%)  rest (generation) %.3fs (%.0f%%)" % (b, reg, 100*reg/b, b-reg, 100*(b-reg)/b))
for k, v in T.most_common(): print("  %-26s %.3fs %4.0f%%" % (k, v, 100*v/b))
