"""`handler_count` has to fire, or its zero means nothing. One planted raise on each route into the two handlers,
including the one `catch_count` can't see: `s.assumption_lits()`, an argument inside 1906's `try`.
By pytest with `-p rust_plugin -p handler_count` (either backend, as run_suite.sh installs it), or as a script:
`python test_handler_count.py OUT.jsonl`, which exits 1 if a route isn't seen, or an excluded one is.
sa-port-25's `quiet_fire.py` (port/3) checks the same four calls by a one-shot raise; this one runs where the counter's
installed, on either backend. live.py's own install is shown by `SLICE_PLANT_HANDLER`."""
import json
import sys

from sympy import Q, Symbol

import handler_count
from satassume import sympy_api
from satassume.engine import Engine, Session, Uninterpreted


class Planted(Exception):
    pass


def _boom(*a, **k):
    raise Planted("planted")


def _patched(owner, name, value, run):
    real = owner.__dict__[name]
    setattr(owner, name, value)
    try:
        return run()
    finally:
        setattr(owner, name, real)


def _ask(tag):
    return sympy_api._consistent(Q.positive(Symbol(tag)), Engine())


def _raising_check(s, lits):
    raise Planted("planted")


def _uninterpreted(s, lits):
    raise Uninterpreted("planted")


def routes():
    yield "assumption_lits, 1906", "_build_context", lambda: _patched(Session, "assumption_lits", _boom, lambda: _ask("hc_a"))
    yield "complete_check, 1906", "_build_context", lambda: _patched(Engine, "_complete_check", staticmethod(_raising_check), lambda: _ask("hc_c"))
    yield "verdict, 1107", "_consistent", lambda: _patched(Engine, "_build_context_memoized", _boom, lambda: _ask("hc_v"))
    yield "_formula, 1107", "_consistent", lambda: _patched(sympy_api, "_formula", _boom, lambda: _ask("hc_f"))


def _rows():
    handler_count._out.flush()
    return [json.loads(x) for x in open(handler_count._out.name)]


def _route(site, run):
    before = len(_rows())
    run()
    return [(r["site"], r["type"]) for r in _rows()[before:] if r["site"].endswith(site)]


def _uninterpreted_route():
    try:
        _patched(Engine, "_complete_check", staticmethod(_uninterpreted),
                 lambda: Engine()._build_context(sympy_api._formula(Q.positive(Symbol("hc_u")), False, True)))
    except Uninterpreted:
        return
    raise AssertionError("Uninterpreted didn't reach the caller of _build_context")


def test_each_route_is_seen():
    for name, site, run in routes():
        seen = _route(site, run)
        assert [t for _, t in seen] == ["Planted"], (name, seen)


def test_uninterpreted_is_not_counted():
    # Re-raised at 1904: an expected route, not a quiet answer.
    assert _route("_build_context", _uninterpreted_route) == []


if __name__ == "__main__":
    handler_count.install(sys.argv[1])
    bad = 0
    for name, site, run in routes():
        seen = _route(site, run)
        ok = [t for _, t in seen] == ["Planted"]
        bad += not ok
        print("seen" if ok else "NOT SEEN", name, seen)
    seen = _route("_build_context", _uninterpreted_route)
    print("Uninterpreted counted at 1906:", len(seen))
    sys.exit(1 if bad or seen else 0)
