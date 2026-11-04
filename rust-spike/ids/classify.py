"""classify.py NAME...: read $W/suite-NAME.xml. Prints counts, and the failures only under live, by the first rung that clears them.
With --sig NAME: failure signatures (exception type, last repo frame) with counts, for tests in the live-only set."""
import collections
import os
import re
import sys
import xml.etree.ElementTree as ET

W = os.path.expanduser("~/sa-rust-ids-work")


def load(name):
    out = {}
    for tc in ET.parse(f"{W}/suite-{name}.xml").getroot().iter("testcase"):
        t = f"{tc.get('classname')}::{tc.get('name')}"
        for k in ("failure", "error"):
            e = tc.find(k)
            if e is not None:
                out[t] = (e.get("message") or "", e.text or "")
    return out


def sig(msg, text):
    frames = re.findall(r"^(\S+\.py):(\d+): in (\S+)", text, re.M)
    last = re.findall(r"^(\S+\.py):(\d+): (\w*Error|\w*Exception|Failed)?", text, re.M)
    exc = re.search(r"^E\s+(\w[\w.]*(?:Error|Exception|Exhausted|Unsatisfiable|Failed|Warning)?)\b", text, re.M)
    repo = [f for f in frames if not f[0].startswith(("/", "../", "sympy/"))]
    loc = f"{repo[-1][0]}:{repo[-1][1]}" if repo else (last[-1][0] if last else "?")
    return f"{(msg.splitlines() or ['?'])[0][:70]} @ {loc}"


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "--sig":
        base, r = load("base"), load(a[1])
        g = collections.defaultdict(list)
        for t, (m, x) in r.items():
            if t not in base:
                g[sig(m, x)].append(t)
        for s, ts in sorted(g.items(), key=lambda kv: -len(kv[1])):
            print(len(ts), s, "e.g.", ts[0].split("tests.")[-1][:60])
    elif a[0] == "--list":
        base, r = load("base"), load(a[1])
        print("\n".join(sorted(t for t in r if t not in base)))
    else:
        rs = {n: load(n) for n in a}
        base = set(rs["base"])
        live = set(rs["live"]) - base
        for n, r in rs.items():
            print(n, "failed", len(r), "beyond base", len(set(r) - base), "of live-only still failing", len(live & set(r)), "new", len(set(r) - base - live), "base not failing", len(base - set(r)))
