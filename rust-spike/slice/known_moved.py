"""known_moved.py: test-only. Writes known_moved.json, livecmp.py's exact known-difference rows (issue 323, the planner's (A)
ruling of 10 Nov with sa-port-239's numbers): per workload and engine point `[_SPLIT python, rust, _CACHE python, rust]`,
read from livecmp.py's own output on a clean build's Python and Rust rows.

`python known_moved.py A.cmp B.cmp ...` merges the rows of each comparison that has no other difference into the table; a
workload whose counts are equal at every point gets no row (livecmp.py then requires them equal). A comparison with any
other difference is refused: a known row is taken only from a run that is otherwise a MATCH.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEEN = re.compile(r"per engine point\): (\[.*?\]) \| known rows \((.*?)\):")


def main(paths):
    path = os.path.join(HERE, "known_moved.json")
    table = json.load(open(path)) if os.path.exists(path) else {}
    for p in paths:
        text = open(p).read()
        n = json.loads(next(l for l in text.splitlines() if l.startswith('{"queries_a"')))
        m = SEEN.search(text)
        other = sorted(k for k, v in n.items() if v and k.endswith("_diff") and k != "moved_known_diff")
        if m is None or m.group(2) == "None" or other or n["queries_a"] != n["queries_b"]:
            print("refused", p, other or "no known-rows line")
            continue
        rows = json.loads(m.group(1))
        if any(r[0] != r[1] or r[2] != r[3] for r in rows):
            table[m.group(2)] = rows
        else:
            table.pop(m.group(2), None)
        print("taken", m.group(2), len(rows), "points")
    with open(path, "w") as f:
        f.write("{\n" + ",\n".join("%s: %s" % (json.dumps(k), json.dumps(table[k])) for k in sorted(table)) + "\n}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
