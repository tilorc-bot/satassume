"""ana356.py TOOLS RUNDIR WL OUT.json (sa-port-356): each sample of pys356.sh's pysample3 rows charged to one owner, by
sa-port-143's decoder and sa-port-195's classifier (TOOLS = sa-port-327's s1/tools: dec143.py, ana195.py; GD_NM = the nm
tables). Per in-loop sample:
  rust         ana195's rust, glue and capi<-rust: sa_solver's own code and the C API it calls with no eval loop between
  own[F]       every other attributed sample goes to the file F of the innermost Python frame: `byte` when the native
               leaf is the eval loop (F's bytecode), `c` when it is C that F's bytecode called (dict, isinstance, hash,
               ...). ownf is the same by function.
  incl[F]      F anywhere on the Python stack, once per sample.
  under[F][G]  own samples of G with F on the stack and no other repository file's frame nearer the leaf than F's:
               what F's code reaches in SymPy and the stdlib (the cost that goes with F), keyed sympy / stdlib.
Files: sa/X (satassume), slice/X, sympy (one group), stdlib (one group), harness (the driver)."""
import collections, glob, json, os, sys
sys.path.insert(0, sys.argv[1])
import dec143 as D
import ana195 as A


def fk(f):
    if not f.known:
        return "?"
    tag, rel = A.relpath(f.file)
    return tag if tag in ("sympy", "stdlib", "harness", "other") else tag + "/" + rel


def main(d, wl, out):
    syms = D.Syms()
    cats, byte, c, ownf, incl = (collections.Counter() for _ in range(5))
    under = collections.defaultdict(collections.Counter)
    N = 0
    runs = []
    for b in sorted(glob.glob(f"{d}/{wl}-rust-pysample3-*.bin")):
        base = b[:-4]
        row, codes, maps, recs = D.load(base)
        runs.append((os.path.basename(base), row["digest"], row["s"], row["samples"], row.get("so")))
        for r in recs:
            if r[0] == 0xffffffff:
                continue
            m = D.merge(r, codes, maps, syms)
            cat = A.classify(m)["cat"]
            N += 1
            cats[cat] += 1
            frames = [f for s in m["segs"] for f in s]
            for k in {fk(f) for f in frames}:
                incl[k] += 1
            if cat in ("rust", "glue", "capi<-rust", "unattributed") or not frames:
                continue
            f0 = frames[0]
            k = fk(f0)
            leaf = m["nat"][0] if m["nat"] else ("?",)
            (byte if leaf[0] == "eval" else c)[k] += 1
            ownf[k + ":" + (f0.qual if f0.known else "?")] += 1
            if k in ("sympy", "stdlib"):
                near = next((fk(f) for f in frames if fk(f).startswith(("sa/", "slice/"))), None)
                if near:
                    under[near][k] += 1
    json.dump(dict(wl=wl, N=N, runs=runs, cats=cats, byte=byte, c=c, ownf=ownf, incl=incl, under=under), open(out, "w"))
    print(f"{d} {wl}: {N} samples, {len(runs)} runs; cats", dict(cats))


if __name__ == "__main__":
    main(*sys.argv[2:5])
