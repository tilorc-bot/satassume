# probe_catch368.py (B368_PRE; sa-port-368): the slice's catch_count.py installed (the quiet handlers at engine.py:1953,
# `except Exception` around _complete_check, and sympy_api._consistent around Engine.verdict), its sink summarised on stderr
# after the pass. P368_PLANT=1: one planted raise through the wrapped _complete_check before the pass, to show the counter fires.
import collections, os, sys
import catch_count
catch_count.install()
if os.environ.get("P368_PLANT") == "1":
    from satassume.engine import Engine
    try:
        Engine._complete_check(None, None)      # raises inside the original (None has no solver): must reach the sink
    except Exception:
        pass
    print("PLANT sink", len(catch_count.sink), catch_count.sink[-1:][0][:2] if catch_count.sink else None, file=sys.stderr)
    del catch_count.sink[:]
_after = G["_after368"]


def after(g):
    c = collections.Counter((s[0], s[1]) for s in catch_count.sink)
    print("CATCHES total", len(catch_count.sink), sorted(c.items()), file=sys.stderr)
    _after(g)


G["_after368"] = after
