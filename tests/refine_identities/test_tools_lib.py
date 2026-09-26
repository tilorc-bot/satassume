"""``satrefine.tools.lib`` and the scoreboard's command line (the tools' own tests are
test_fuzz_ext, test_matrix_fuzz and test_ablate; the gates run the tools end to end)."""
from __future__ import annotations

import random
import signal

from sympy import Abs, Q, S, log, sqrt, symbols, srepr

from satrefine.tools import scoreboard
from satrefine.tools.lib import battery, numeric, points, workers
from satrefine.tools.lib.report import table

x, y = symbols("x y")


def test_scoreboard_subcommands():
    assert scoreboard.parse([]).command == "battery"
    args = scoreboard.parse(["--family", "trig", "--show"])
    assert (args.command, args.family, args.show, args.lines) == ("battery", ["trig"], True, False)
    assert scoreboard.parse(["lines"]).lines
    args = scoreboard.parse(["suite", "--backends", "sympy", "--", "-k", "abs"])
    assert (args.command, args.backends, args.pytest_args) == ("suite", "sympy", ["-k", "abs"])


def test_battery_classify():
    limit = battery.known_oracle_limit()
    assert battery.classify(Abs(x), Q.positive(x), x, "test_complex_parts.py::t", limit).key == "fired, same as v3"
    assert battery.classify(Abs(x), Q.positive(x), None, "test_complex_parts.py::t", limit).key == \
        "fired where v3 expects unchanged"
    assert battery.classify(Abs(x), S.true, None, "test_complex_parts.py::t", limit).key == "unchanged as expected"
    assert battery.classify(Abs(x), S.true, x, "test_complex_parts.py::t", limit).key == \
        "did not fire, v3 expects a result"
    assert battery.family_of("test_power_exp_log.py::test_x[1]") == "power_exp_log"


def test_refine_case_records_every_status():
    saved = signal.getsignal(signal.SIGALRM)
    workers.install_case_alarm()
    try:
        _refine_case_statuses()
    finally:
        signal.signal(signal.SIGALRM, saved)


def _refine_case_statuses():
    def check(r, rec, e):
        return numeric.compare(e, r, points.check_points([e, r], {x: ("positive",)}, None, random.Random(0)))
    rec = workers.refine_case(Abs(x), Q.positive(x), 20, lambda r, rec: check(r, rec, Abs(x)))
    assert rec["status"] == "fired" and rec["result"] == srepr(x) and rec["checked"] > 0 and "unsound" not in rec
    assert workers.refine_case(Abs(x), S.true, 20, None)["status"] == "unchanged"
    assert workers.refine_case(Abs(x), Q.positive(x) & Q.negative(x), 20, None)["status"] in ("inconsistent", "unchanged")
    rec = workers.refine_case(sqrt(x**2), Q.real(x), 20, lambda r, rec: (0, ({x: S(-2)}, 2j, 1j)))
    assert rec["unsound"] == {"point": {"x": "-2"}, "orig": "0+2j", "refined": "0+1j"}


def test_srepr_round_trip_keeps_unevaluated_nodes():
    from sympy import Add
    e = Add(x, x, evaluate=False)
    assert srepr(workers.load_srepr(srepr(e))) == srepr(e)
    assert workers.load_srepr(srepr(log(y))) == log(y)


def test_table(capsys):
    table([["a", 1], ["bb", 22]], ["k", "n"])
    table([["a", 1]], ["key", "n"], right=True)
    assert capsys.readouterr().out.splitlines() == ["k   n ", "--  --", "a   1 ", "bb  22", "key  n", "------", "a    1"]
