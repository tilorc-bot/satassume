"""quiet_fire.py {mine|port2 PATH}: does a quiet-handler counter see a raise from every call inside the two `try`s?
Plants a one-shot ValueError at each call in turn, runs one query, and prints what the counter saw for that plant, plus an
unplanted run that must see nothing. A plant that never ran says "not reached", which is not a pass.
  engine.py:1906's try: s.assumption_lits(), self._complete_check. sympy_api.py:1107's try: _formula, eng.verdict."""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sympy import Q, Symbol  # noqa: E402
from satassume import engine as E, sympy_api as A  # noqa: E402

mode = sys.argv[1]
if mode == "mine":
    import transfer_shadow as X
    X.count_quiet_catches()

    def seen():
        out = sum(X.catches.values())
        X.catches.clear()
        return out
else:
    spec = importlib.util.spec_from_file_location("handler_count", sys.argv[2])
    H = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(H)
    path = tempfile.mktemp(dir=os.environ.get("SCRATCH", "."))
    H.install(path)

    def seen():
        H._out.flush()
        rows = open(path).read().splitlines()
        open(path, "w").close()
        return len(rows)

x = Symbol("x", real=True)
y = Symbol("y", real=True)
PLANTS = [("engine.py:1906 s.assumption_lits", E.Session, "assumption_lits"),
          ("engine.py:1906 _complete_check", E.Engine, "_complete_check"),
          ("sympy_api.py:1107 _formula", A, "_formula"),
          ("sympy_api.py:1107 eng.verdict", E.Engine, "verdict")]


def run():
    eng = E.Engine()
    a = Q.positive(x) & Q.negative(y)
    try:
        A._consistent(a, eng)
    except Exception as e:
        return f"escaped {type(e).__name__}"
    return "ok"


print("unplanted", run(), "counter saw", seen())
for name, owner, attr in PLANTS:
    real = getattr(owner, attr)
    fired = [0]

    def plant(*args, **kw):
        fired[0] += 1
        if fired[0] == 1:
            raise ValueError("planted " + name)
        return real(*args, **kw)
    setattr(owner, attr, plant)
    r = run()
    setattr(owner, attr, real)
    print(json.dumps(dict(plant=name, reached=fired[0] > 0, run=r, counter_saw=seen())))
