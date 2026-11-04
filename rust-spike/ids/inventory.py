"""inventory.py WL OUT.json: dynamic inventory of hash and == on SymPy objects, by the satassume line that asks.

Monkeypatches only. Every __hash__ and __eq__ defined by a SymPy class is wrapped. A call counts when the Python
frame that caused it is in satassume/ (so SymPy's own internal hashing is not counted, which matches the "outermost
entry" of tools-rust/rc.py mon). Formula.__hash__ / __eq__ are wrapped too, so the line behind a P hash is visible.
The bytecode op at the asking line separates direct == (COMPARE_OP) from container lookups.
"""
import dis
import hashlib
import json
import os
import sys
from collections import Counter

wl, out_path = sys.argv[1], sys.argv[2]
from evalbench.common import ask_all, workload  # noqa: E402
from satassume import sympy_api  # noqa: E402
from satassume.engine import Engine  # noqa: E402
from satassume.sat import formula as fm  # noqa: E402
from sympy import Basic  # noqa: E402

if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)

HITS = Counter()
OPS = {}
depth = [0]
SA = os.path.dirname(os.path.realpath(sympy_api.__file__))


def opname(code, lasti):
    k = (code, lasti)
    r = OPS.get(k)
    if r is None:
        r = "?"
        for i in dis.get_instructions(code):
            if i.offset == lasti:
                r = i.opname
                if r == "COMPARE_OP" or r == "CONTAINS_OP" or r == "IS_OP":
                    r = f"{r}:{i.argrepr}"
                break
        OPS[k] = r
    return r


def note(kind, a, b):
    f = sys._getframe(2)
    code = f.f_code
    fn = code.co_filename
    if not fn.startswith(SA):
        if "site-packages" not in fn and "/sympy/" in fn:
            return
    HITS[(kind, fn, f.f_lineno, code.co_qualname, opname(code, f.f_lasti), a, b, depth[0] > 0)] += 1


def wrap(cls):
    d = cls.__dict__
    if d.get("__hash__") is not None:
        oh = d["__hash__"]

        def __hash__(self, oh=oh):
            note("hash", type(self).__name__, "")
            return oh(self)
        cls.__hash__ = __hash__
    if "__eq__" in d:
        oe = d["__eq__"]

        def __eq__(self, other, oe=oe):
            note("eq", type(self).__name__, type(other).__name__)
            return oe(self, other)
        cls.__eq__ = __eq__
    if "__ne__" in d:
        one = d["__ne__"]

        def __ne__(self, other, one=one):
            note("ne", type(self).__name__, type(other).__name__)
            return one(self, other)
        cls.__ne__ = __ne__


seen = set()
todo = [Basic]
while todo:
    c = todo.pop()
    if c in seen:
        continue
    seen.add(c)
    todo.extend(c.__subclasses__())
    wrap(c)
for c in (fm.Formula,):
    oh, oe = c.__hash__, c.__eq__

    def fh(self, oh=oh):
        note("Fhash", type(self).__name__, "")
        return oh(self)

    def fe(self, other, oe=oe):
        note("Feq", type(self).__name__, type(other).__name__)
        return oe(self, other)
    c.__hash__, c.__eq__ = fh, fe


def bound(name):
    o = getattr(Engine, name)

    def w(*a, **k):
        depth[0] += 1
        try:
            return o(*a, **k)
        finally:
            depth[0] -= 1
    setattr(Engine, name, w)


for n in ("ask", "is_", "is_many", "verdict"):
    bound(n)

ans = ask_all(sympy_api.ask, pairs)
digest = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]
root = os.path.dirname(SA)
rows = []
for (kind, fn, line, q, op, a, b, inside), n in HITS.items():
    rows.append(dict(kind=kind, file=fn.replace(root + "/", ""), line=line, fn=q, op=op, a=a, b=b, inside=inside, n=n))
rows.sort(key=lambda r: -r["n"])
json.dump(dict(wl=wl, digest=digest, rows=rows), open(out_path, "w"))
tot = Counter()
for r in rows:
    tot[(r["kind"], r["inside"])] += r["n"]
print(wl, digest, {f"{k[0]}{'_in' if k[1] else '_out'}": v for k, v in tot.items()})
