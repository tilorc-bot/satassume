"""pid_hand.py: hand checks on the P-id copy (PYTHONPATH must point at it). Each step in a fresh subprocess where order matters."""
import subprocess, sys, json, weakref
from fractions import Fraction
SNIP = {
"True first S.true": "from sympy import S,Integer; from satassume.sat.formula import P; P('a',S.true).__hash__(); P('a',Integer(1)).__hash__(); print(P('a',True)==P('a',Integer(1)), P('a',True)==P('a',S.true))",
"True first Integer(1)": "from sympy import S,Integer; from satassume.sat.formula import P; P('a',Integer(1)).__hash__(); P('a',S.true).__hash__(); print(P('a',True)==P('a',Integer(1)), P('a',True)==P('a',S.true))",
"1.0 first Integer(1)": "from sympy import Float,Integer; from satassume.sat.formula import P; P('a',Integer(1)).__hash__(); P('a',Float(1.0)).__hash__(); print(P('a',1.0)==P('a',Integer(1)), P('a',1.0)==P('a',Float(1.0)))",
"1.0 first Float(1.0)": "from sympy import Float,Integer; from satassume.sat.formula import P; P('a',Float(1.0)).__hash__(); P('a',Integer(1)).__hash__(); print(P('a',1.0)==P('a',Integer(1)), P('a',1.0)==P('a',Float(1.0)))",
"clear then new value": "from sympy import Symbol; from satassume.sat import formula as f; x,y=Symbol('x'),Symbol('y'); p=f.P('a',x); hash(p); f._P_IDS.clear(); q=f.P('a',y); print('p==q after clear, x!=y:', p==q, hash(p)==hash(q))",
"clear then same value": "from sympy import Symbol; from satassume.sat import formula as f; x,y=Symbol('x'),Symbol('y'); p=f.P('a',x); hash(p); f._P_IDS.clear(); hash(f.P('c',y)); q=f.P('a',x); print('p==q after clear, same value:', p==q)",
"1 and 1.0, Integer(1) and Float(1.0) seen": "from sympy import Float,Integer; from satassume.sat.formula import P; P('a',Integer(1)).__hash__(); P('a',Float(1.0)).__hash__(); print('P(a,1)==P(a,1.0):', P('a',1)==P('a',1.0))",
"1 and 1.0, nothing else seen": "from satassume.sat.formula import P; print('P(a,1)==P(a,1.0):', P('a',1)==P('a',1.0))",
}
for k, s in SNIP.items():
    r = subprocess.run([sys.executable, "-c", s], capture_output=True, text=True)
    print(f"{k}: {r.stdout.strip() or r.stderr.strip()[-200:]}")
# the real relation, no table
def cmp(a, b):
    try:
        return "T" if a == b else "."
    except Exception:
        return "X"
from sympy import S, Integer, Float, Rational, Symbol, Dummy
vals = {"True": True, "1": 1, "1.0": 1.0, "Fraction(1)": Fraction(1), "S.true": S.true, "Integer(1)": Integer(1), "Float(1.0)": Float(1.0), "Rational(1,1)": Rational(1, 1)}
print("hash", {k: hash(v) for k, v in vals.items()})
print("== table (row == col)")
ks = list(vals)
for a in ks:
    print(f"{a:14}", " ".join(cmp(vals[a], vals[b]) for b in ks))
vh = {"0.5": 0.5, "Fraction(1,2)": Fraction(1, 2), "Rational(1,2)": Rational(1, 2), "Float(0.5)": Float(0.5)}
print("hash", {k: hash(v) for k, v in vh.items()})
ks = list(vh)
for a in ks:
    print(f"{a:14}", " ".join(cmp(vh[a], vh[b]) for b in ks))
for n, o in (("Symbol", Symbol("x")), ("Integer", Integer(5)), ("Add", Symbol("x") + 1), ("Dummy", Dummy()), ("S.true", S.true)):
    try:
        weakref.ref(o); print("weakref ok", n)
    except TypeError as e:
        print("weakref no", n, e)
