"""The compare tool's state dump, on the Python solver: the same field -> string dict as the Rust solver's `dump()`
(`solver.rs`, at the end). Reads only: it never calls `_model`, which would complete a stored model and hide the very
paths it is there to look at. `diff` names the first field that differs. Used by `fuzz.py`; step 3 hashes `digest`.
"""
import hashlib
import struct

from satassume.sat.solver import Clause, _is_learnt


def _bits(x):
    return "%x" % struct.unpack("<Q", struct.pack("<d", x))[0]


def _join(xs):
    return " ".join(map(str, xs))


def _tri(x):
    return 2 if x is None else int(x)


def _hexes(xs):
    return " ".join("%x" % m for m in xs)


def _clause(c):
    act = c.act if c.__class__ is Clause else 0.0
    return f"{_join(c)}|{_bits(act)}|{int(_is_learnt(c))}"


def _reason(r):
    if r is None:
        return "-"
    if r.__class__ is int:
        return f"b{r >> 32:x}:{r & 0xFFFFFFFF:x}"
    return _clause(r)


def _model(m):
    return "N" if m is None else _join(map(_tri, m))


def _models(ms):
    return "N" if ms is None else " ; ".join(repr(m) for m in ms)


def dump_py(s):
    ths = s._theories
    index = lambda t: next(i for i, x in enumerate(ths) if x is t)
    ring = []
    for mv, ncl, rlen, nb, nt, na, _ in s._ring:
        ring.append(f"{_model(mv)}|{ncl} {rlen} {nb} {nt} {na}|{int(mv is s._mvals)} {int(mv is s._witness)}")
    w = "".join(f"{l}:{';'.join(_join(c) for c in ws)}\n" for l, ws in enumerate(s._watches) if ws)
    tmap = "".join(f"{v}:{_join(index(t) for t in s._tmap[v])} " for v in sorted(s._tmap))
    ac = s._acache
    if ac is None:
        acache = "N"
    else:
        (k, st, kl), t = ac
        acache = f"{_join(k)}|{st}|{kl}|{'N' if t is None else _join(t)}"
    d = {
        "trail": _join(s._trail),
        "trail_lim": _join(s._trail_lim),
        "qhead": str(s._qhead),
        "val": _join(map(_tri, s._val)),
        "level": _join(s._level),
        "reason": "\n".join(map(_reason, s._reason)),
        "clauses": ";".join(map(_clause, s._clauses)),
        "learnts": ";".join(map(_clause, s._learnts)),
        "watches": w,
        "act": _join(map(_bits, s._act)),
        "var_inc": _bits(s._var_inc),
        "cla_inc": _bits(s._cla_inc),
        "max_learnts": _bits(s._max_learnts),
        "polarity": _join(s._polarity),
        "heap": _join(s._heap),
        "hpos": _join(s._hpos),
        "seen": _join(s._seen),
        "ok": str(int(s._ok)),
        "nvars": str(s._nvars),
        "assumptions": _join(s._assumptions),
        "mvals": _model(s._mvals),
        "mdict": "N" if s._mdict is None else _join(map(_tri, s._mdict.values())),
        "witness": _model(s._witness),
        "mvals_is_witness": str(int(s._mvals is not None and s._mvals is s._witness)),
        "ring": ";".join(ring),
        "stamp": str(s._stamp),
        "acache": acache,
        "held": "N" if s._held is None else _join(s._held),
        "conflict": _join(s._conflict),
        "counters": _join((s._n_props, s._n_conflicts, s._n_decisions, s._n_learned, s._n_restarts, s._n_reductions,
                           s._n_ring_hits, s._n_tdecisions, s._n_late, s._n_late_written)),
        "scan": str(s._scan),
        "tmap": tmap,
        "thead": str(s._thead),
        "tprops": _join(index(m.__self__) for m in s._tprops),
        "tdecides": _join(index(m.__self__) for m in s._tdecides),
        "tpending": str(int(s._tpending)),
        "n_registered": str(s._n_registered),
        "rb_base": _join(s._rb_base),
        "rb_mask": _hexes(s._rb_mask),
        "rb_ment": _hexes(s._rb_ment),
        "rb_saved": _join(s._rb_saved),
        "rb_cl": _hexes(s._rb_cl),
        "rb_undo": _hexes(s._rb_undo),
        "rb_ulim": _join(s._rb_ulim),
        "uid": str(s._uid),
        "ment": _join(s._ment),
        "lazy": _join(s._lazy),
        "rb_n": str(s._rb_n),
        "rb_blocks": str(s._rb_blocks),
        "rb_nclauses": str(s._rb_nclauses),
        "rb_bases": _join(s._rb_bases),
        "rb_set": str(int(s._rb_clauses is not None)),
        "tmodels": _models(s._tmodels),
        "ring_tm": " // ".join(_models(r[6]) for r in s._ring),
    }
    return d


def diff(a, b):
    """The first field that differs, in dump order, with the spot it starts: (field, offset, a's text, b's text)."""
    for k in a:
        x, y = a[k], b.get(k)
        if x != y:
            y = "<missing>" if y is None else y
            i = next((i for i, (p, q) in enumerate(zip(x, y)) if p != q), min(len(x), len(y)))
            lo = max(0, i - 40)
            return k, i, x[lo:i + 80], y[lo:i + 80]
    extra = set(b) - set(a)
    return ("<extra fields>", 0, "", str(sorted(extra))) if extra else None


def digest(d):
    h = hashlib.blake2b(digest_size=16)
    for k in d:
        h.update(k.encode())
        h.update(d[k].encode())
    return h.hexdigest()
