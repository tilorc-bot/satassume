"""byid349.py BAR BASE_SUITE (sa-port-349, issue 323): the bar's suite rows by failed id, from each row's pytest.log
(-rf lines), against the base suite's and against this bar's plain row; the planted-history assertion per row;
test_witness.py's failed ids per row; the witness plant counter (740) summed over a row's counts.*.json."""
import collections, glob, json, os, re, sys
B, BASE = sys.argv[1], sys.argv[2]
PH = "tests/test_public_incremental.py::test_public_comparison_catches_a_planted_history_dependence"
def failed(d):
    return {l.split()[1] for l in open(d + "/pytest.log", errors="replace") if l.startswith("FAILED ")}
def last(d):
    return [l.strip() for l in open(d + "/pytest.log", errors="replace") if re.search(r"\d+ (passed|failed)", l)][-1]
base = failed(BASE); plain = failed(B + "/suite")
print("base", BASE, len(base), "failed |", last(BASE))
for row in ["suite"] + sorted(os.path.basename(p) for p in glob.glob(B + "/suite-witness:*")):
    d = B + "/" + row; f = failed(d)
    print(f"{row}: {len(f)} failed | {last(d)}")
    print(f"   against base: failed only here {sorted(f - base)}; failed only in base {sorted(base - f)}")
    print(f"   against plain: failed only here {sorted(f - plain)}; failed only in plain {sorted(plain - f)}")
    print("   by file:", dict(collections.Counter(i.split("::")[0] for i in f).most_common()))
    log = open(d + "/pytest.log", errors="replace").read()
    print("   planted-history:", "failed" if PH in f else "not failed", sorted(set(re.findall(r"test_public_incremental\.py:\d+: [^\n]{0,60}", log))))
    w = collections.Counter()
    for c in glob.glob(d + "/counts.*.json"):
        j = json.load(open(c))
        for k, v in (j.items() if isinstance(j, dict) else []):
            if "witness" in k and isinstance(v, (int, float)): w[k] += v
    print("   witness counters over counts.*.json:", dict(w))
