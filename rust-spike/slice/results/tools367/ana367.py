"""ana367.py TOOLS RUNDIR WL OUT.json MODE (sa-port-367; tools356/ana356.py with MODE = rust | py picking the rows, and
per-function inclusive and SymPy-under counts added: inclf, underf, undern): each sample of pys367.sh's pysample3 rows
charged to one owner, by
sa-port-143's decoder and sa-port-195's classifier (TOOLS = sa-port-327's s1/tools: dec143.py, ana195.py; GD_NM = the nm
tables). Per in-loop sample:
  rust         ana195's rust, glue and capi<-rust: sa_solver's own code and the C API it calls with no eval loop between
  own[F]       every other attributed sample goes to the file F of the innermost Python frame: `byte` when the native
               leaf is the eval loop (F's bytecode), `c` when it is C that F's bytecode called (dict, isinstance, hash,
               ...). ownf is the same by function.
  incl[F]      F anywhere on the Python stack, once per sample.
  under[F][G]  own samples of G with F on the stack and no other repository file's frame nearer the leaf than F's:
               what F's code reaches in SymPy and the stdlib (the cost that goes with F), keyed sympy / stdlib.
  inclf[F:Q]   function Q of repository file F anywhere on the Python stack, once per sample (the time a
               computation carries: its own, its callees' and the Rust and C entered under it).
  underf[F:Q]  own samples of SymPy and the stdlib whose nearest repository frame is Q of F.
  undern[F:Q]  rust-category samples whose innermost Python frame is Q of F (Rust entered from Q).
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


def main(d, wl, out, mode="rust"):
    syms = D.Syms()
    cats, byte, c, ownf, incl, inclf, underf, undern = (collections.Counter() for _ in range(8))
    under = collections.defaultdict(collections.Counter)
    N = 0
    runs = []
    for b in sorted(glob.glob(f"{d}/{wl}-{mode}-pysample3-*.bin")):
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
            for k in {fk(f) + ":" + f.qual for f in frames if f.known and fk(f).startswith(("sa/", "slice/"))}:
                inclf[k] += 1
            if cat in ("rust", "glue", "capi<-rust") and frames and frames[0].known:
                undern[fk(frames[0]) + ":" + frames[0].qual] += 1
            if cat in ("rust", "glue", "capi<-rust", "unattributed") or not frames:
                continue
            f0 = frames[0]
            k = fk(f0)
            leaf = m["nat"][0] if m["nat"] else ("?",)
            (byte if leaf[0] == "eval" else c)[k] += 1
            ownf[k + ":" + (f0.qual if f0.known else "?")] += 1
            if k in ("sympy", "stdlib"):
                nf = next((f for f in frames if fk(f).startswith(("sa/", "slice/"))), None)
                if nf:
                    under[fk(nf)][k] += 1
                    underf[fk(nf) + ":" + nf.qual] += 1
    json.dump(dict(wl=wl, N=N, runs=runs, cats=cats, byte=byte, c=c, ownf=ownf, incl=incl, under=under, inclf=inclf, underf=underf, undern=undern, mode=mode), open(out, "w"))
    print(f"{d} {wl}: {N} samples, {len(runs)} runs; cats", dict(cats))


if __name__ == "__main__":
    main(*sys.argv[2:6])
