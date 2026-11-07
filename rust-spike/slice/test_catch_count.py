"""`catch_count` has to fire, or its "0 catches" means nothing. One planted raise on each route into the two handlers.
By pytest with `-p rust_plugin` (either backend), which installs the counter and puts it in the row's `caught`; or as a
script, which installs it as live.py does."""
from sympy import Q, Symbol

import catch_count
from satassume import sympy_api
from satassume.engine import Engine, Session


class Planted(Exception):
    pass


def _boom(*a, **k):
    raise Planted("planted")


def _new_sites(before):
    return [x[0] for x in catch_count.sink[before:]]


def _with_plant(owner, name, run):
    real = owner.__dict__[name]
    setattr(owner, name, _boom)
    before = len(catch_count.sink)
    try:
        return run(), _new_sites(before)
    finally:
        setattr(owner, name, real)


def test_formula_route_into_1107():
    # Nothing to patch: the counter's wrapper holds the real `_formula`, and this assumption is one it can't read.
    before = len(catch_count.sink)
    r = sympy_api._consistent(object(), Engine())
    assert r is False
    assert _new_sites(before) == ["formula<_consistent"]


def test_verdict_route_into_1107():
    a = Q.positive(Symbol("cc_v"))
    r, sites = _with_plant(Engine, "_build_context_memoized", lambda: sympy_api._consistent(a, Engine()))
    assert r is False
    assert sites == ["verdict<_consistent"]


class _Raises:
    def __getattr__(self, name):
        raise Planted("planted")


def test_complete_check_route_into_1906():
    # `assumption_lits` is the last thing to run before the check: from there on the session's solver raises.
    real = Session.assumption_lits

    def plant(self):
        r = real(self)
        self.solver = _Raises()
        return r
    Session.assumption_lits = plant
    before = len(catch_count.sink)
    try:
        sympy_api._consistent(Q.positive(Symbol("cc_c")), Engine())
    finally:
        Session.assumption_lits = real
    assert "complete_check" in _new_sites(before), catch_count.sink[before:]


if __name__ == "__main__":
    catch_count.install()
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
            print("ok", k)
