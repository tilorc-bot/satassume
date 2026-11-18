"""mark317.py RUNDIR WL (sa-port-317): per run, the inclusive samples of _Mark's Rust functions. GD_NM=RUNDIR/nm.
A sample counts for a function when a sa_solver frame with that name is anywhere on its stack (prof292's incl, per run).
mark = TermFrames::__pymethod_mark__ or mark_note/mark_add entries or note or add_in on the stack (all of _Mark's filling);
note = TermFrames::note; attr_or = term::live::attr_or. The sampler's period is fixed, so samples per run are time;
ms = share x the run's own wall. Prints one JSON line: per-run lists."""
import glob, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
import dec143 as D
from prof292 import dem
PAT = dict(mark=re.compile(r'TermFrames>::(__pymethod_mark|note$|add_in$)'), note=re.compile(r'TermFrames>::note$'),
           attr_or=re.compile(r'term::live::attr_or'), live=re.compile(r'term::live'))
def main(d, wl):
    syms = D.Syms(); out = []
    for b in sorted(glob.glob(f"{d}/{wl}-rust-pysample3-*.bin"), key=lambda p: int(p[:-4].rsplit("-", 1)[1])):
        row, codes, maps, recs = D.load(b[:-4])
        n = 0; c = dict.fromkeys(PAT, 0)
        for r in recs:
            if r[0] == 0xffffffff:
                continue
            m = D.merge(r, codes, maps, syms); n += 1
            names = [dem(v[2]) for v in m["nat"] if v[0] in ("rust", "glue")]
            for k, p in PAT.items():
                if any(p.search(x) for x in names):
                    c[k] += 1
        out.append(dict(run=os.path.basename(b)[:-4], n=n, s=row["s"], digest=row["digest"], **c))
    print(json.dumps(dict(dir=os.path.basename(d.rstrip("/")), wl=wl, runs=out)))
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
