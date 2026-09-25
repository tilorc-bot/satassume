"""gate2's frozen SymPy assumption-test queries under an engine option.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/scripts/facts2_gate2.py \\
        [FROZEN] [--free] [--no-transfer]

Replays ``~/.cache/satassume/gate2-frozen.jsonl`` like ``tools/gate2.py``
with ``Engine(uninterpreted="free")`` (``--free``) and/or
``Engine(transfer=False)``, and lists every answer that differs from the
frozen one, with SymPy's recorded answer.
"""
import json, os, sys
from collections import Counter
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
from compare import rebuild
from satassume import Engine
from satassume.sympy_api import ask, out_of_scope

args = [a for a in sys.argv[1:] if not a.startswith("--")]
path = args[0] if args else os.path.expanduser("~/.cache/satassume/gate2-frozen.jsonl")
kw = {}
if "--free" in sys.argv:
    kw["uninterpreted"] = "free"
if "--no-transfer" in sys.argv:
    kw["transfer"] = False
eng = Engine(**kw)
C = Counter()
for i, line in enumerate(open(path)):
    rec = json.loads(line)
    prop, assum = rebuild(rec["prop"]), rebuild(rec["assum"])
    try:
        got = ask(prop, assum, engine=eng)
    except ValueError:
        got = "error:ValueError"
    want = rec["answer"]
    if got == want:
        C["same"] += 1
        continue
    kind = ("more definite" if want is None and got in (True, False) else
            "new error" if isinstance(got, str) else
            "lost error" if isinstance(want, str) else
            "less definite" if got is None else "contradiction")
    C[kind] += 1
    print(f"{kind} #{i} [{rec['group']}] {prop} | {assum}: frozen {want} now {got} (sympy {rec['sympy']})")
print(kw, dict(C))
