"""scan329.py WL... (cwd rust-spike/slice) (sa-port-329, issue 323): per workload, how many queries mention each derived predicate SymPy's
rule base states one way only (witness.ONE_WAY: hermitian, antihermitian, commutative), as an applied predicate anywhere
in the proposition or the assumptions, or as a key of a symbol's assumptions0 other than `commutative: True`. A workload
with no such query cannot tell the ONE_WAY reading from rules.DEFINITIONS: the check never asks for either there.
For plant 751 (skip-own): `declared`, the queries with a symbol whose assumptions0 holds more than `commutative: True`,
and `bounding`, those among them where a symbol's own assumptions exclude one of the check's fixed candidate values
(witness._HEAD, _TAIL) or are undecided: only there can skipping the own assumptions change the points."""
import sys
from sympy import Basic, Symbol
from sympy.assumptions.assume import AppliedPredicate
from satassume import witness
from satassume.witness import ONE_WAY
import live     # the slice's driver, for its loader of the 20 workloads (run from rust-spike/slice)
for wl in sys.argv[1:]:
    pairs = live.load(wl)
    n = {k: 0 for k in ONE_WAY}
    own = declared = bounding = 0
    for p, a in pairs:
        seen, o, dec, bnd = set(), False, False, False
        for e in (p, a):
            if not isinstance(e, Basic):
                continue
            for ap in e.atoms(AppliedPredicate):
                name = str(ap.function.name)
                if name in ONE_WAY:
                    seen.add(name)
            for s in e.atoms(Symbol):
                d = s.assumptions0
                if d.get("commutative") is not True or "hermitian" in d or "antihermitian" in d:
                    o = True
                if len(d) > 1:
                    dec = True
                    try:
                        f = witness._own(s)
                        bnd = bnd or not all(f(v) for v in witness._HEAD + witness._TAIL)
                    except witness._Undecided:
                        bnd = True
        for k in seen:
            n[k] += 1
        own += o
        declared += dec
        bounding += bnd
    print(wl, len(pairs), n, "own assumptions0 with one of them (beyond commutative: True):", own, "declared:", declared, "bounding:", bounding)
