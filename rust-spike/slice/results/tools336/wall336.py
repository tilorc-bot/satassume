"""wall336.py BAR_DIR (sa-port-336, issue 323): the bar's wall times from its own records. Phases: phases.txt (each line
is a phase's end) against commands.txt's first command. Suite rows: the time from a suite command (it names its row by
SLICE_SUITE_OUT) to the next command; they run one after another. Extra workloads: from a workload's reference command
to the next workload's (its Python twice, Rust, the witness reference, then its plant rows). Workload plant rows: the
seconds bar.sh wrote to plant-WL-ROW.wall (the row's own run; rows of a phase run side by side, so they do not add up
to the phase)."""
import glob, os, re, sys
from datetime import datetime
B = sys.argv[1]
ts = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
fmt = lambda d: f"{int(d.total_seconds()) // 60} m {int(d.total_seconds()) % 60:02d} s"
cmds = [(ts(l[:20]), l[21:]) for l in open(B + "/commands.txt") if re.match(r"\d{4}-\d\d-\d\dT", l)]
ph = [l.split() for l in open(B + "/phases.txt")]
prev = cmds[0][0]
print(f"first command {cmds[0][0]} last phase end {ph[-1][1]} total {fmt(ts(ph[-1][1]) - cmds[0][0])}")
for name, end, *_ in ph:
    print(f"phase {name}: {fmt(ts(end) - prev)} (ends {end})")
    prev = ts(end)
nxt = {i: cmds[i + 1][0] if i + 1 < len(cmds) else ts(ph[-1][1]) for i in range(len(cmds))}
print("suite rows:")
for i, (t, c) in enumerate(cmds):
    m = re.search(r"SLICE_SUITE_OUT=(\S+)", c)
    if m and "pytest" in c:
        print(f"  {os.path.basename(m.group(1))}: {fmt(nxt[i] - t)}")
print("extra workloads (reference runs, then the plant rows):")
xs = [(t, re.search(r"live\.py (\S+) py \S+/extra/", c).group(1)) for t, c in cmds if re.search(r"^\( \$PY live\.py \S+ py \S+/extra/", c)]
end_extra = next((ts(e) for n, e, *_ in ph if n == "extra"), None)
for j, (t, wl) in enumerate(xs):
    print(f"  {wl}: {fmt((xs[j + 1][0] if j + 1 < len(xs) else end_extra) - t)}")
print("workload plant rows, seconds (plant-WL-ROW.wall):")
rows = {}
for d in ("live", "extra"):
    for p in sorted(glob.glob(f"{B}/{d}/plant-*.wall")):
        wl, pl = re.match(r"plant-([^-]+)-(.*)\.wall$", os.path.basename(p)).groups()
        rows.setdefault(pl, {})[wl] = int(open(p).read().split()[0])
for pl, d in sorted(rows.items()):
    print(f"  {pl}: sum {sum(d.values())} s over {len(d)} workloads; " + ", ".join(f"{w} {s}" for w, s in sorted(d.items(), key=lambda x: -x[1])))
