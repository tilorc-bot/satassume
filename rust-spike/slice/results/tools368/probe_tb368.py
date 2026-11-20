# probe_tb368.py (B368_PRE; sa-port-368): where the names in P368_NAMES are defined on euf.EUFTheory's MRO, what cnt367
# installed in front of them, and the traceback of the first P368_N AttributeErrors that leave sympy_api.ask (re-raised unchanged).
import os, sys, traceback
from satassume import sympy_api
import satassume.theories.euf.euf as euf
C = euf.EUFTheory
print("euf.EUFTheory is", C.__module__ + "." + C.__qualname__, "mro", [k.__module__ + "." + k.__qualname__ for k in C.__mro__],
      "dictoffset", C.__dictoffset__, file=sys.stderr)
for n in os.environ.get("P368_NAMES", "rep members").split():
    print(" ", n, [(k.__qualname__, type(k.__dict__[n]).__name__) for k in C.__mro__ if n in k.__dict__], file=sys.stderr)
_ask, _left = sympy_api.ask, [int(os.environ.get("P368_N", "1"))]


def ask(p, a):
    try:
        return _ask(p, a)
    except AttributeError:
        if _left[0] > 0:
            _left[0] -= 1
            print("QUERY", G["Q"][0], "ask(%r, %r)" % (p, a), file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        raise


sympy_api.ask = ask
