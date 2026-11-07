"""The compare tool's state dump, on the Python solver: the same field -> string dict as the Rust solver's `dump()`
(`solver.rs`, at the end). Reads only: it never calls `_model`, which would complete a stored model and hide the very
paths it is there to look at. `diff` names the first field that differs. Used by `fuzz.py`; step 3 hashes `digest`.
"""
import hashlib
import re
import struct
import sys

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


_shown = {}


def show_head(o):
    """A head as text, for both EUF dumps. Addresses masked; memoised because a dump can run after every solver call."""
    k = (type(o), o)
    r = _shown.get(k)
    if r is None:
        r = _shown[k] = re.sub(r"0x[0-9a-f]+", "0xX", repr(o))
    return r


def dump_euf_py(th):
    """The same field -> string dict as the crate's `EUFTheory.dump(show_head)` (`euf_py.rs`), on Python's class."""
    def key(k, t):
        if k[0] == "a":
            return f"{t}=a:{k[1]}:{k[2]}"
        if k[0] == "h":
            return f"{t}=h:{show_head(k[1])}:{k[2]}"
        return f"{t}={k[0]}:{show_head(k[1])}"

    def lab(x):
        if x is None:
            return "N"
        return str(x) if isinstance(x, int) else f"{x[0]},{x[1]}"

    def op(e):
        o = e[0]
        if o == 0:
            return "U" + ",".join(str(int(x)) for x in e[1:])
        if o == 1:
            return f"L{e[1][0]},{e[1][1]}"
        return "..ADPTS"[o] + ",".join(map(str, e[1:]))

    # opcodes: _UNION, _LOOKUP, _ASSIGN, _DISEQ, _REG_APP, _REG_ATOM, _USE = range(7)
    return {f"euf.{k}": v for k, v in {
        "keys": ";".join(key(k, t) for k, t in th._keys.items()),
        "app": _join("N" if a is None else f"{a[0]},{a[1]}" for a in th._app),
        "rep": _join(th.rep),
        "members": ";".join(_join(m) for m in th.members),
        "use": ";".join(_join(m) for m in th._use),
        "lookup": _join(f"{a},{b}:{t}" for (a, b), t in sorted(th._lookup.items())),
        "pfp": _join(th._pfp),
        "pfl": _join(lab(x) for x in th._pfl),
        "val": _join(th._val),
        "diseq": ";".join(_join(f"{d[0]},{d[1]},{d[2]}" for d in l) for l in th._diseq),
        "atoms_of": ";".join(_join(m) for m in th._atoms_of),
        "atoms": _join(f"{v}:{a[0]},{a[1]},{int(a[2])}" for v, a in sorted(th._atoms.items())),
        "assigned": _join(f"{v}:{l}" for v, l in sorted(th._assigned.items())),
        "pending": _join(f"{a},{b},{lab(l)}" for a, b, l in th._pending),
        "propq": _join(th._propq),
        "conflict": "N" if th._conflict is None else _join(th._conflict[1]),
        "trail": _join(op(e) for e in th._trail),
        "lims": _join(th._lims),
    }.items()}


def with_euf(dump, theories):
    """`dump` plus, per attached EUF theory, its own fields under the theory's index. `theories` is the solver class's
    unwrapped method, so a traced solver doesn't see this read as a call."""
    rust = sys.modules.get("sa_solver")

    def f(s):
        d = dict(dump(s))
        for i, th in enumerate(theories(s)):
            if rust is not None and isinstance(th, rust.EUFTheory):
                e = th.dump(show_head)
            elif hasattr(th, "_pfp"):
                e = dump_euf_py(th)
            else:
                continue
            d.update((f"{i}.{k}", v) for k, v in e.items())
        return d
    return f


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


def lra_text(t):
    """The whole of an LRATheory's state, as canonical text. Insertion order is kept where Python's order can be read
    later (row entries, atoms, assigned literals, slack forms); it's sorted where only membership counts (`_rows`'
    outer order, `_cols`, `_forms`, `_dirty`). The `_ONE`/`_ZERO` identity shows as `I` on an integrality atom."""
    from satassume.theories.lra.lra import _ONE, _ZERO

    def fast(m, k):
        return "I" if m is _ONE and k is _ZERO else repr((m, k))
    d = t.__dict__
    get = lambda n: d[n]
    parts = dict(
        key=[None if k is None else str(k) for k in get("_key")],
        var_of=[(str(k), v) for k, v in get("_var_of").items()],
        slack_of=list(get("_slack_of").items()),
        forms=sorted((sorted((str(a), repr(b)) for a, b in k), repr(v)) for k, v in get("_forms").items()),
        lo=get("_lo"), up=get("_up"), lo_r=get("_lo_r"), up_r=get("_up_r"), vq=get("_vq"), vd=get("_vd"),
        rows=sorted((b, list(r.items())) for b, r in get("_rows").items()),
        cols=[sorted(c) for c in get("_cols")],
        atoms=list(get("_atoms").items()), ground=list(get("_ground").items()), atoms_on=get("_atoms_on"),
        assigned=list(get("_assigned").items()), diseqs=get("_diseqs"),
        ints=[(a, v, fast(m, k)) for a, (v, m, k) in get("_ints").items()],
        ints_on=list(get("_ints_on").items()),
        int_lits=[(v, fast(m, k), lit) for v, m, k, lit in get("_int_lits")],
        int_memo=sorted(repr(x) for x in get("_int_memo").items()),
        trail=get("_trail"), lims=get("_lims"), dirty=sorted(get("_dirty")), pending=get("_pending_ground"),
        fields=get("_fields"), gave_up=get("gave_up"), eager=get("eager"),
        exhausted=t.exhausted, branched=t.branched_rational, stats=t.stats)
    return repr(parts)


def lra_of(solver):
    """(digest of the state of each LRATheory of a solver, group), or (None, None) without one. Group: "python" from
    the start, "rust" throughout, or "moved:REASON:CALL:LEVEL"."""
    out, group = [], None
    for t in solver.theories():
        if not any(k.__name__ == "LRATheory" for k in type(t).__mro__):
            continue
        core = t.__dict__.get("_core", 0)
        if core == 0:
            group = "python"
            v = t
        elif core is None:
            r, c, lev = t.__dict__["_moved"]
            group = f"moved:{r}:{c}:{lev}"
            v = t
        else:
            group = "rust"
            v = t._view()
        out.append(lra_text(v))
    if not out:
        return None, None
    return hashlib.blake2b("".join(out).encode(), digest_size=16).hexdigest(), group
