import sys, json, collections
from satassume import relations as R
from satassume.sat import solver as SV
C = collections.Counter()
_i0 = R.Relations._interpret
def _interpret(self, atom):
    C["interp_link" if (atom in self._link_lt or atom in self._link_eq) else "interp_other"] += 1
    return _i0(self, atom)
R.Relations._interpret = _interpret
_l0 = R.Relations._link
def _link(self, e):
    C["links"] += 1
    return _l0(self, e)
R.Relations._link = _link
_ra0 = SV.Solver.register_atom
def register_atom(self, th, v, *a, **k):
    C["xfer_atoms" if type(th).__name__ == "TransferTheory" else "theory_atoms"] += 1
    return _ra0(self, th, v, *a, **k)
SV.Solver.register_atom = register_atom
_init0 = R.Relations.__init__
def __init__(self, *a, **k):
    C["relation_sessions"] += 1
    _init0(self, *a, **k)
R.Relations.__init__ = __init__
from evalbench.common import ask_all, workload
from satassume import sympy_api
if sys.argv[1] == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(sys.argv[1])
ask_all(sympy_api.ask, pairs)
print(sys.argv[1], dict(C))
