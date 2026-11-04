"""ids_core.py: an interning table and hash/== stand-ins at every satassume call site, chosen by frame.

install(mode):
  shadow  sites get the original result; the id result is computed too and every disagreement is logged.
  eqonly  == from satassume frames answered by ids; hash stays the real SymPy hash (so set order is unchanged).
  live    hash and == from satassume frames answered by ids; SymPy's own frames keep the real hash and ==.
  hashonly hash from satassume frames answered by ids; == stays the real SymPy == (the complement of eqonly).
install(mode, scope) says which frames count as sites:
  sa       satassume/ and generated dataclass code (<string>): what every mode above means by "satassume frames".
  repo     also tests/, tools/, harness/: a dict built by a test uses the same hash satassume reads it with.
  all      every frame, SymPy's and hypothesis's too: the ids applied consistently, so no dict can cross a frame boundary.
exempt (a set of "file.py:qualname") is scope sa with those code objects left on the real hash: see exempt.txt.
The file must stay outside satassume/, because a frame in this module counts as "not a site".

Table: by_addr maps the address of a pinned object to its id, with no SymPy call. by_obj is a dict keyed on the object
(real hash, real ==), asked only when an address is seen for the first time, so its partition is the dict partition.
"""
import os
import random
import sys
from collections import Counter

import satassume
from sympy import Basic
from sympy.core.sympify import SympifyError, _sympify

SA = os.path.dirname(os.path.realpath(satassume.__file__))
ROOT = os.path.dirname(SA)
REPO = tuple(os.path.join(ROOT, d) + os.sep for d in ("tests", "tools", "harness"))
_sites = {}


def in_sa(code):
    r = _sites.get(code)
    if r is None:
        fn = code.co_filename
        r = fn.startswith(SA) or fn == "<string>"
        if T.scope == "repo":
            r = r or fn.startswith(REPO)
        elif T.scope == "all":
            r = True
        if r and T.exempt and f"{os.path.basename(fn)}:{code.co_qualname}" in T.exempt:
            r = False
        _sites[code] = r
    return r


class T:
    mode = "off"
    scope = "sa"
    exempt = frozenset()
    hv = None      # IDS_RANDOM=SEED: id -> random hash instead of the id, as if interned in a random order
    rng = None
    busy = False   # inside the table: every wrapper gives the real answer (scope all would recurse otherwise)
    by_addr = {}
    by_obj = {}
    objs = []      # one pinned reference per address
    reps = []      # id -> first object seen
    hashes = []    # id -> real hash
    n = Counter()
    bad = {}       # (kind, site) -> [count, sample]
    origh = {}


def ID(o):
    i = T.by_addr.get(id(o))
    if i is None:
        T.n["first_sight"] += 1
        was, T.busy = T.busy, True
        try:
            i = T.by_obj.get(o)
            if i is None:
                i = T.by_obj[o] = len(T.reps)
                T.reps.append(o)
                T.hashes.append(hash(o))
                if T.hv is not None:
                    T.hv.append(T.rng.getrandbits(61) + 1)
        finally:
            T.busy = was
        T.by_addr[id(o)] = i
        T.objs.append(o)
    return i


def _log(kind, f, a, b, r_real, r_id):
    k = (kind, f"{os.path.basename(f.f_code.co_filename)}:{f.f_lineno}:{f.f_code.co_qualname}")
    e = T.bad.setdefault(k, [0, []])
    e[0] += 1
    if len(e[1]) < 5:
        e[1].append([type(a).__name__, repr(a)[:80], type(b).__name__, repr(b)[:80], repr(r_real), repr(r_id)])


def _idb(other):
    """id of the other operand, or None if it does not sympify."""
    if isinstance(other, Basic):
        return ID(other)
    T.n["eq_nonbasic"] += 1
    was, T.busy = T.busy, True
    try:
        other = _sympify(other)
    except SympifyError:
        return None
    finally:
        T.busy = was
    return ID(other)


def _wrap(cls):
    d = cls.__dict__
    if d.get("__hash__") is not None:
        oh = d["__hash__"]

        def __hash__(self, oh=oh):
            if not T.busy and T.mode != "eqonly" and in_sa(sys._getframe(1).f_code):
                T.n["hash"] += 1
                i = ID(self)
                if T.mode in ("live", "hashonly"):
                    return T.hv[i] if T.hv is not None else i
                r = oh(self)
                if r != T.hashes[i]:
                    _log("hash_changed", sys._getframe(1), self, self, r, T.hashes[i])
                return r
            return oh(self)
        cls.__hash__ = __hash__
    for name, want in (("__eq__", True), ("__ne__", False)):
        if name not in d:
            continue
        oe = d[name]

        def op(self, other, oe=oe, want=want, name=name):
            f = sys._getframe(1)
            if T.busy or T.mode == "hashonly" or not in_sa(f.f_code):
                return oe(self, other)
            T.n[name] += 1
            j = _idb(other)
            if j is None:
                T.n["eq_unsympifiable"] += 1
                return oe(self, other)
            r_id = (ID(self) == j) is want
            if T.mode != "shadow":
                return r_id
            r = oe(self, other)
            if r is NotImplemented:
                T.n["eq_notimpl"] += 1
                return r
            if bool(r) is not r_id:
                _log("nonbasic" if not isinstance(other, Basic) else name, f, self, other, r, r_id)
            if type(self) is not type(other) and bool(r) is want:
                T.n["eq_true_crosstype"] += 1
                _log("true_crosstype", f, self, other, r, r_id)
            return r
        setattr(cls, name, op)


def install(mode, scope="sa", exempt=()):
    T.mode, T.scope, T.exempt = mode, scope, frozenset(exempt)
    if os.environ.get("IDS_RANDOM"):
        T.rng, T.hv = random.Random(int(os.environ["IDS_RANDOM"])), []
    seen, todo = set(), [Basic]
    while todo:
        c = todo.pop()
        if c not in seen:
            seen.add(c)
            todo.extend(c.__subclasses__())
            _wrap(c)


def audit():
    """After a run: every pair in the table likely to be == across ids must not be ==. Numbers pairwise (capped), then
    groups by real hash and by str."""
    groups = {}
    for i, o in enumerate(T.reps):
        groups.setdefault(("h", T.hashes[i]), []).append(o)
        groups.setdefault(("s", str(o)), []).append(o)
    nums = [o for o in T.reps if getattr(o, "is_Number", False)][:3000]
    groups[("n", 0)] = nums
    res = Counter()
    samples = []
    m, T.mode = T.mode, "off"
    for key, g in groups.items():
        if len(g) < 2:
            continue
        res["groups_" + key[0]] += 1
        for x in range(len(g)):
            for y in range(x + 1, len(g)):
                res["pairs_" + key[0]] += 1
                if g[x] == g[y] or g[y] == g[x]:
                    res["eq_true_two_ids"] += 1
                    if len(samples) < 10:
                        samples.append([key[0], repr(g[x])[:60], repr(g[y])[:60]])
                if key[0] != "n" and len(samples) < 20 and type(g[x]) is not type(g[y]) and key[0] == "s":
                    samples.append(["same str, other type", repr(g[x])[:40], type(g[x]).__name__, type(g[y]).__name__])
    T.mode = m
    return dict(res), samples


def report():
    return dict(mode=T.mode, n=dict(T.n), ids=len(T.reps), addresses=len(T.objs),
                bad=[dict(kind=k[0], site=k[1], count=v[0], sample=v[1]) for k, v in
                     sorted(T.bad.items(), key=lambda kv: -kv[1][0])])
