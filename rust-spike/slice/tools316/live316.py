"""live316.py (sa-port-316) RUNDIR WL: where the samples under term/live.rs go. Run with GD_NM=RUNDIR/nm and
sa-port-314's s1/tools on sys.path (dec143, ana195, prof292 for dem).

For each sample in the query loop, take the innermost sa_solver frame in term::live (L). Frames leafward of L:
  callee   an eval loop entered with no dict/hash/compare frame between it and L: a Python callable live.rs was asked to
           run (the guarded function, the relation's atoms). Not live.rs's own cost; left out of T.
  T        live.rs's own cost = everything else:
    dict+py   a dict/set/hash/compare C frame directly under L, leading into Python `__hash__`/`__eq__` (SymPy keys)
    dict-c    such a C frame, leaf in C (the probe itself, str/int keys, identity hits)
    capi      other C API directly under L (getattr, call, alloc, tuple, long)
    rust      other sa_solver Rust under L (TermTable's methods, formula)
    self      L is the leaf
Also printed: term_live.py's own Python self samples (innermost Python frame in term_live.py, leaf in the eval loop).
"""
import collections, glob, os, re, sys
sys.path.insert(0, os.path.expanduser("~/sa-rust-ids-work/sa-port-314/s1/tools"))
import dec143 as D, ana195 as A
from prof292 import dem, pyname

DICT = re.compile(r'[Dd]ict|PyObject_Hash|RichCompare|PySet_|set_contains|set_add|_lookup|PyObject_GetItem|PyObject_SetItem|PyMapping')
LIVE = re.compile(r'term::live')


def main(d, wl):
    syms = D.Syms()
    N = 0
    cat = collections.Counter(); byfn = collections.defaultdict(collections.Counter)
    callee = collections.Counter(); pyq = collections.Counter(); capi = collections.Counter(); dictc = collections.Counter()
    tl_self = 0; hasheq = collections.Counter(); grp = collections.Counter(); markd = collections.Counter()
    tl_inner = collections.Counter(); tl_he = collections.Counter(); m7 = collections.Counter(); M7 = re.compile(r'term_id_in|int_id|same_class|ids_in|pymethod_term_id__|pymethod_ids__')
    for b in sorted(glob.glob(f"{d}/{wl}-rust-pysample3-*.bin")):
        row, codes, maps, recs = D.load(b[:-4])
        for r in recs:
            if r[0] == 0xffffffff:
                continue
            m = D.merge(r, codes, maps, syms)
            N += 1
            nat = m["nat"]
            if nat and nat[0][0] == "eval" and m["segs"] and m["segs"][0] and pyname(m["segs"][0][0]).startswith("py:term_live.py"):
                tl_self += 1
            flat = [f for sg in m["segs"] for f in sg]
            if flat:
                n0 = pyname(flat[0])
                if n0.startswith("py:term_live.py"):
                    tl_inner[n0[16:]] += 1
                elif re.search(r'__(hash|eq)__$', n0) and len(flat) > 1 and pyname(flat[1]).startswith("py:term_live.py"):
                    tl_he[pyname(flat[1])[16:] + " <- " + n0.split(":")[-1]] += 1
            i = next((j for j, v in enumerate(nat) if v[0] in ("rust", "glue") and LIVE.search(dem(v[2]))), None)
            if i is None:
                continue
            L = re.sub(r'<|>|sa_solver::|term::live::', '', dem(nat[i][2]))[:60]
            inner = nat[:i]
            ev = [j for j, v in enumerate(inner) if v[0] == "eval"]
            direct = inner[(ev[-1] + 1) if ev else 0:]
            names = [dem(v[2]) for v in direct]
            isdict = any(v[0] not in ("rust", "glue") and DICT.search(n) for v, n in zip(direct, names))
            if ev:
                k = len(ev) - 1
                seg = m["segs"][k] if k < len(m["segs"]) else []
                q = pyname(seg[-1]) if seg else "py:?"
                if re.search(r'__(hash|eq|ne)__$', q):   # however the C frames between are named (slot_tp_hash, inlined dict_get)
                    c = "dict+py"; hasheq[q + ("" if isdict else " [no dict frame: " + (names[-1] if names else "?")[:40] + "]")] += 1
                else:
                    c = "callee"; callee[L + " -> " + q] += 1
                    if isdict:
                        pyq[q] += 1
            elif not inner:
                c = "self"
            elif any(v[0] == "rust" and not LIVE.search(n) for v, n in zip(direct, names)):
                c = "rust"
            elif isdict:
                c = "dict-c"; dictc[next(n for v, n in zip(reversed(direct), reversed(names)) if DICT.search(n))] += 1
            else:
                c = "capi"; capi[names[-1] if names else "?"] += 1
            cat[c] += 1; byfn[L][c] += 1
            if c != "callee" and any(v[0] in ("rust", "glue") and M7.search(dem(v[2])) for v in nat[i:]):
                # only while no callee eval sits between: nat[i:] rootward of L may hold an older term_id frame, so require
                # the nearest live frames rootward up to the first eval
                up = []
                for v in nat[i:]:
                    if v[0] == "eval":
                        break
                    up.append(dem(v[2]))
                if any(M7.search(n) for n in up):
                    m7[c + ("/count" if re.search(r'::count|::planted', L) else "")] += 1
            if c != "callee":
                up = []
                for v in nat[i:]:
                    if v[0] == "eval":
                        break
                    up.append(dem(v[2]))
                u = " ".join(up)
                g = ("maps" if M7.search(u) else "mark" if re.search(r'::note|::add_in|pymethod_mark|mark_note|mark_add', u) else
                     "current" if re.search(r'current', u) else "wrappers" if re.search(r'Guarded|RelationRun', u) else "other")
                grp[g] += 1
                if g == "mark":
                    markd[L[:22] + " / " + c + " / " + (names[-1] if names else "-")[:70]] += 1
    T = sum(v for k, v in cat.items() if k != "callee")
    print(f"## {os.path.basename(d)} {wl}: N={N} samples; term_live.py Python self {tl_self} ({100*tl_self/N:.2f}%)")
    print(f"under term::live: {sum(cat.values())}; callee (not live.rs's) {cat['callee']}; T = live.rs's own = {T} ({100*T/N:.2f}% of N)")
    for c in ("dict+py", "dict-c", "capi", "rust", "self"):
        print(f"  {c:8} {cat[c]:6} {100*cat[c]/max(T,1):5.1f}% of T {100*cat[c]/N:5.2f}% of N")
    print("by innermost term::live function (dict+py dict-c capi rust self | callee):")
    for L, cs in sorted(byfn.items(), key=lambda kv: -sum(v for k, v in kv[1].items() if k != 'callee'))[:14]:
        print(f"  {L:60} {cs['dict+py']:5} {cs['dict-c']:5} {cs['capi']:5} {cs['rust']:5} {cs['self']:5} | {cs['callee']:6}")
    print(f"seven-maps functions (term_id_in, int_id, same_class, ids_in and their entries), T samples: {sum(m7.values())} ({100*sum(m7.values())/N:.2f}% of N):", dict(m7))
    print(f"innermost Python frame in term_live.py: {sum(tl_inner.values())} ({100*sum(tl_inner.values())/N:.2f}% of N):", [(k, v) for k, v in tl_inner.most_common() if re.search(r'^(_Mark|current|term_id|_ids|same_class|_int_id|stack|_guarded|_note_query|_Query)', k)])
    print(f"SymPy __hash__/__eq__ called from term_live.py's Python: {sum(tl_he.values())} ({100*sum(tl_he.values())/N:.2f}% of N):", tl_he.most_common(8))
    print("live.rs's own time by group:", {k: f"{v} ({100*v/N:.2f}% of N)" for k, v in grp.most_common()})
    print("mark group by function / kind / C frame under it:")
    for k, v in markd.most_common(14):
        print(f"  {v:5} {k}")
    print("dict+py by Python function:", hasheq.most_common(8))
    print("dict-c by C frame under L:", dictc.most_common(8))
    print("capi by C frame under L:", capi.most_common(12))
    print("callee, dict frame but not hash/eq:", pyq.most_common(5))
    print("callee top:", callee.most_common(6))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
