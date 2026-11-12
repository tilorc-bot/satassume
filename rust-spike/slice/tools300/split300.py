"""split300.py (sa-port-300, item 0) RUNDIR WL OUT.json: split of convert.py's inclusive samples by what the time is spent on.

Reads the pysampler records prof292.py reads (dec143 merge). For each in-loop sample with a convert.py frame on the Python
stack, take the INNERMOST convert.py frame F (a _Walk method, convert, formula, ...) and classify the sample by what runs
below F:
  bytecode       F is the innermost Python frame and the native leaf is the eval loop: F's own bytecode.
  c:<symbol>     F is the innermost Python frame and the leaf is C called from F's bytecode with no Python frame in between
                 (dict/list/int work, isinstance, getattr on a class, ...). Keyed by the C function the eval loop called.
  py:<callee>    a Python frame runs below F: keyed by the Python function F reached first (the frame just inside F),
                 e.g. Basic.__hash__ from a dict lookup, Basic.args, free_symbols, has, class_key.
  rust           a sa_solver.so frame sits between F and the leaf (TEMPLATES_FOR -> Dispatch.templates_for).
The 'root' of a sample says who asked: 'convert' (under convert.convert: the per-query conversion) or 'read' (under
_Walk.read: a lazy read Rust asked for at run time), or 'other'.
"""
import collections, json, glob, os, sys
sys.path.insert(0, os.path.expanduser("~/sa-rust-ids-work/sa-port-295/gd/tools"))
import dec143 as D
import ana195 as A
import prof292 as P


def main(d, wl, out):
    syms = D.Syms()
    N = 0
    tab = collections.Counter()      # (root, F, kind, key)
    for b in sorted(glob.glob(f"{d}/{wl}-rust-pysample3-*.bin")):
        row, codes, maps, recs = D.load(b[:-4])
        for r in recs:
            if r[0] == 0xffffffff:
                continue
            m = D.merge(r, codes, maps, syms)
            N += 1
            py = [(si, f) for si, s in enumerate(m["segs"]) for f in s]
            conv = [j for j, (si, f) in enumerate(py) if f.known and A.relpath(f.file) == ("slice", "convert.py")]
            if not conv:
                continue
            j = conv[0]
            quals = [py[k][1].qual for k in conv]
            root = "read" if "_Walk.read" in quals else "convert" if "convert" in quals else "other"
            F = py[j][1].qual
            nat = m["nat"]
            evals = [k for k, v in enumerate(nat) if v[0] == "eval"]
            seg = py[j][0]
            # native frames below (inside) the eval invocation that runs F's segment
            lim = evals[seg] if seg < len(evals) else len(nat)
            below = nat[:lim]
            if any(v[0] in ("rust", "glue") for v in below):
                kind, key = "rust", "rust"
            elif j > 0:
                kind, key = "py", P.pyname(py[j - 1][1])
            elif not below:
                kind, key = "bytecode", "bytecode"
            else:
                kind, key = "c", "c:" + P.dem(below[-1][2])     # the C function the eval loop called
            tab[(root, F, kind, key)] += 1
    json.dump(dict(N=N, rows=[list(k) + [v] for k, v in tab.items()]), open(out, "w"))
    print(wl, N, sum(tab.values()))


main(*sys.argv[1:4])
