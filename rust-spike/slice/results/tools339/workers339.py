"""workers339.py BAR_DIR IDS21 (sa-port-339, issue 323): for each suite row of a bar, per worker (rows.PID.jsonl is in
run order): where the two tests that leave a template ran, where test_witness.py's ids ran, where its [template] case
ran, and which of the 21 lost-template ids ran after [template] in the same worker, with outcomes. Read-only."""
import glob, json, os, sys
B, IDS = sys.argv[1], sys.argv[2]
LEAK = ["tests/test_templates.py::test_template_key_error_is_not_read_as_inconsistent",
        "tests/test_p4_review.py::test_reregistered_template_key_does_not_reuse_compiled_pattern"]
TPL = "tests/test_witness.py::test_a_users_knowledge_falls_through_and_the_engines_answer_is_used[template]"
ids21 = [l.split()[2] for l in open(IDS) if l.startswith("NOT-PASSED ")]
print("ids21", len(ids21))
for d in sorted(glob.glob(B + "/suite*")):
    if not os.path.isdir(d): continue
    print("==", os.path.basename(d))
    for f in sorted(glob.glob(d + "/rows.*.jsonl")):
        rows = [json.loads(l) for l in open(f)]
        pos = {r["id"]: i for i, r in enumerate(rows)}
        out = {r["id"]: r["outcome"] for r in rows}
        leak = [(os.path.basename(l.split("::")[0]), pos[l]) for l in LEAK if l in pos]
        w = [i for i, r in enumerate(rows) if r["id"].startswith("tests/test_witness.py::")]
        wf = [r["id"].split("::")[1] for r in rows if r["id"].startswith("tests/test_witness.py::") and r["outcome"] != "passed"]
        t = pos.get(TPL)
        here = [i for i in ids21 if i in pos]
        after = [i for i in here if t is not None and pos[i] > t]
        bad = [i for i in here if out[i] != "passed"]
        print(f"  {os.path.basename(f)} n={len(rows)} leak={leak} witness ids={len(w)} at {w[0] if w else None}..{w[-1] if w else None}"
              f" not passed={len(wf)} [template] at {t}; of the 21: here {len(here)}, after [template] {len(after)}, not passed {len(bad)}")
        if len(wf) <= 12:
            for x in wf: print("      witness not passed:", x)
        for x in bad: print("      21 not passed:", x)
