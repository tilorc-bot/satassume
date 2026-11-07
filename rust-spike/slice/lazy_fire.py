"""Does handler_count see a raise from the lazy path itself, at the two quiet handlers (engine.py:1906, sympy_api.py:1107)?

    lazy_fire.py

quiet_fire.py's four plants, with what's raised being Rust's own refusal from `table.sort_key` on a lazy read, not a
planted ValueError: a read that raises (`read_raised`) and a key holding a term the table doesn't (`read_term_missing`).
Plus a BaseException from a read, which must come through and which the counter must not see, and an unplanted run, which
must see nothing. A plant that never ran says "not reached", which is not a pass. Exit 1 if any row isn't as it must be.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sympy import Q, Symbol  # noqa: E402
from sympy.core.expr import Expr  # noqa: E402
import sa_solver  # noqa: E402
from satassume import engine as E, sympy_api as A  # noqa: E402
import convert as C  # noqa: E402
import handler_count as H  # noqa: E402

path = tempfile.mktemp(dir=os.environ.get("SCRATCH", "."))
H.install(path)


def seen():
    H._out.flush()
    rows = [json.loads(r) for r in open(path).read().splitlines()]
    open(path, "w").close()
    return rows


x = Symbol("x", real=True)
y = Symbol("y", real=True)


class Raises(Expr):
    is_number = False

    def sort_key(self, order=None):
        raise ValueError("planted read")


class Holds(Expr):
    is_number = False

    def sort_key(self, order=None):
        return (Symbol("never_in_the_table"),)


class Stops(BaseException):
    pass


class RaisesBase(Expr):
    is_number = False

    def sort_key(self, order=None):
        raise Stops()


def lazy_raise(cls):
    """The lazy path: a query's table, and a key read of a term whose read goes wrong."""
    t = cls(y)
    c = C.convert(Q.positive(t), True, E.Engine())
    table = sa_solver.TermTable(c.tables)
    table.sort_key(c.ids[t])
    raise AssertionError("the read did not raise")


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
    except BaseException as e:
        return f"came through {type(e).__name__}"
    return "ok"


fail = 0
r = run()
n = seen()
print(json.dumps(dict(plant="unplanted", run=r, counter_saw=len(n))))
fail += r != "ok" or len(n) != 0
for name, owner, attr in PLANTS:
    real = getattr(owner, attr)
    for cls, must_see in ((Raises, True), (Holds, True), (RaisesBase, False)):
        fired = [0]

        def plant(*args, _real=real, _cls=cls, **kw):
            fired[0] += 1
            if fired[0] == 1:
                lazy_raise(_cls)
            return _real(*args, **kw)
        setattr(owner, attr, plant)
        r = run()
        setattr(owner, attr, real)
        n = seen()
        row = dict(plant=name, read=cls.__name__, reached=fired[0] > 0, run=r, counter_saw=len(n),
                   types=sorted({x["type"] for x in n}), site=sorted({x["site"] for x in n}), text=sorted({x["text"][:70] for x in n}))
        ok = fired[0] > 0 and (len(n) > 0 if must_see else (len(n) == 0 and r == "came through Stops"))
        row["as_it_must_be"] = ok
        fail += not ok
        print(json.dumps(row))
os.unlink(path)
sys.exit(1 if fail else 0)
