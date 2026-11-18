"""ivcmp329.py IV_DIR (sa-port-329, issue 323): the iv history check with the witness switch off against on. Per run
name (order, backend, cache, frames, repeat): the failing ids of NAME-off and NAME-on from pytest's -rf lines and the
exit line. "No moved id" = the same failing ids off and on in every run. Also printed: the failing ids per backend
over all runs with how many runs show each, so a flake (an id failing in some repeats only) is visible."""
import glob, os, re, sys
from collections import Counter
iv = sys.argv[1]


def fails(d):
    log = open(d + "/pytest.log", errors="replace").read()
    return sorted(set(re.findall(r"^FAILED (\S+)", log, re.M))), open(d + "/exit.txt").read().strip()


names = sorted(os.path.basename(d)[:-4] for d in glob.glob(iv + "/*-off"))
moved, seen, exits = 0, Counter(), Counter()
for n in names:
    (fo, eo), (fn, en) = fails(f"{iv}/{n}-off"), fails(f"{iv}/{n}-on")
    be = n.split("-")[1]
    for sw, f, e in (("off", fo, eo), ("on", fn, en)):
        exits[(be, sw, e.split()[0])] += 1
        for i in f:
            seen[(be, sw, i)] += 1
    if fo != fn:
        moved += 1
        print(f"MOVED {n}: off only {sorted(set(fo) - set(fn))}; on only {sorted(set(fn) - set(fo))}")
print(f"runs {len(names)} off + {len(names)} on; runs whose failing ids differ off against on: {moved}")
print("exit codes (backend, switch, rc): runs", dict(sorted(exits.items())))
for (be, sw, i), c in sorted(seen.items()):
    print(f"  {be} {sw} {i}: fails in {c} runs")
