"""bis368.py WL MODE OUT.json FILE... (sa-port-368, issue 323): tools367/cnt367.py run unchanged but for the knobs below,
to bisect which of its wraps moves the Rust path's answers. cnt367.py's source is read, patched at named lines (each
patch must match exactly once, else this stops) and executed as the main script; nothing else differs from gocnt367's
cell. Knobs (environment):

  B368_MON=0       no sys.monitoring PY_START/PY_RETURN callbacks (descriptors only)
  B368_ONLY=FILE   install only the field descriptors whose key (FILE:Class.name, as cnt367 names them) is a line of FILE
  B368_SKIP=FILE   install every field descriptor but those listed
  B368_ANS=FILE    the answers of the pass, one JSON list (index = query index), written right after the pass
  B368_STOP=1      stop after the pass (no plants, no OUT.json): for cells with no FILE at all
  B368_LAST=0      Field.__set__ does not keep `self.last = obj` (the strong reference to the last written object)
  B368_CNT=FILE    run this copy of cnt367.py instead of tools367/cnt367.py (e.g. the instrument as it was at b832e5f)
  B368_PRE=FILE    python source executed after the instrument is installed and before the pass (a probe; name `G` = cnt367's globals)

Prints cnt367's JSON line, with `installed` (the field keys installed) added to OUT.json's sibling OUT.keys.
"""
import json, os, sys
T7 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools367", "cnt367.py")
T7 = os.environ.get("B368_CNT") or T7      # another copy of cnt367.py (the one before the fix: git show b832e5f:.../cnt367.py)
src = open(T7).read()


def patch(old, new):
    global src
    assert src.count(old) == 1, (src.count(old), old)
    src = src.replace(old, new)


E = os.environ
_only = set(open(E["B368_ONLY"]).read().split("\n")) - {""} if E.get("B368_ONLY") else None
_skip = set(open(E["B368_SKIP"]).read().split("\n")) - {""} if E.get("B368_SKIP") else set()


def _keep368(key):
    return (_only is None or key in _only) and key not in _skip


def _after368(G):
    if E.get("B368_ANS"):
        json.dump(G["ans"], open(E["B368_ANS"], "w"))
    if E.get("B368_STOP") == "1":
        print(json.dumps(dict(wl=G["wl"], mode=G["mode"], n=len(G["pairs"]), digest=G["digest"], so=G["so"], files=G["FILES"],
                              env={k: v for k, v in E.items() if (k.startswith("SLICE_") and k != "SLICE_DIR") or k.startswith("B368_")},
                              nfields=len(G["FIELDS"]), stopped=True)))
        sys.stdout.flush()
        os._exit(0)


def _pre368(G):
    json.dump(sorted(d.key for d in G["FIELDS"]), open(sys.argv[3] + ".keys", "w"))
    if E.get("B368_PRE"):
        exec(compile(open(E["B368_PRE"]).read(), E["B368_PRE"], "exec"), {"G": G})


patch("                cur = cls.__dict__.get(name, _MISSING)\n",
      "                if not _keep368(f\"{f}:{q}.{name}\"):\n                    continue\n"
      "                cur = cls.__dict__.get(name, _MISSING)\n")
if E.get("B368_MON") == "0":
    patch("M.set_events(TOOL, M.events.PY_START | M.events.PY_RETURN)\n", "M.set_events(TOOL, 0)\n")
if E.get("B368_LAST") == "0":
    patch("            self.last = obj\n", "")
patch("ans = [None] * len(pairs)\n", "ans = [None] * len(pairs)\n_pre368(globals())\n")
patch("digest = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]\n",
      "digest = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]\n_after368(globals())\n")
G = {"__name__": "__main__", "__file__": T7, "_keep368": _keep368, "_after368": _after368, "_pre368": _pre368}
exec(compile(src, T7, "exec"), G)
