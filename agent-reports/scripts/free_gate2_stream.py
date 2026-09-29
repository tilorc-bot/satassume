"""Free-Boolean re-measurement: gate2's frozen queries as a stream file.

    PYTHONPATH=.:/path/to/sympy python agent-reports/scripts/free_gate2_stream.py \\
        [FROZEN] OUT.pkl

Rebuilds every record of ``~/.cache/satassume/gate2-frozen.jsonl`` (as
``tools/gate2.py`` does) into ``(prop, assum, sympy_recorded)`` triples in
``stream.pkl`` format, so ``free_stream.py`` and ``free_compare.py`` run
on gate2 unchanged.
"""
import json, os, pickle, sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
from compare import rebuild

args = sys.argv[1:]
path = args[0] if len(args) > 1 else os.path.expanduser("~/.cache/satassume/gate2-frozen.jsonl")
out = []
for line in open(path):
    rec = json.loads(line)
    out.append((rebuild(rec["prop"]), rebuild(rec["assum"]), rec["sympy"]))
pickle.dump(out, open(args[-1], "wb"))
print(len(out), "records")
