import pickle, sys, collections
from fractions import Fraction
from satassume.theories.lra import lra as L
from satassume.sympy_api import ask
C = collections.Counter()
f = L.LRATheory._register_atom
def g(self, lit, payload):
    f(self, lit, payload)
    a = self._atoms.get(lit)
    if a is not None:
        b = a[2]
        C["atom"] += 1
        C["int" if type(b) is Fraction and b.denominator == 1 else "frac" if type(b) is Fraction else "elem"] += 1
L.LRATheory._register_atom = g
fc = L.LRATheory.check
def h(self):
    C["check"] += 1; C["check-fields"] += self._fields; C["check-rows"] += bool(self._rows)
    C["check-diseq"] += bool(self._diseqs); C["check-ints"] += bool(self._int_lits)
    C["check-nonint-vals"] += any(type(q) is not Fraction or q.denominator != 1 for q in self._vq)
    return fc(self)
L.LRATheory.check = h
st = pickle.load(open(sys.argv[1], "rb"))
for p, a, r in st:
    try: ask(p, a)
    except ValueError: pass
print(dict(C))
