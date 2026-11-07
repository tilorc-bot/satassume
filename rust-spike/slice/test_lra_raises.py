"""Condition 6 and 4 of the planner's transfer ruling. `python test_lra_raises.py [-v]`, or under pytest.

Bad input stays in the Rust core and raises what Python raises, leaving the same state behind (`state.lra_text`); it
doesn't move. A transfer that fails raises, out through `ask()` too, and never carries on.
"""
import os
import sys
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.append(HERE)
import lra_backend  # noqa: E402
import state  # noqa: E402
from satassume.theories.lra import lra as L  # noqa: E402

Py = L.LRATheory
Rs = lra_backend.LRATheory


class Raises:
    def __init__(self, x=None):
        pass

    def __hash__(self):
        raise TypeError("no hash")


def le(pairs, rhs, strict=False, eq=False):
    return (tuple(pairs), F(rhs), strict, eq)


GOOD = le([("x", F(1))], 1)
X1 = ("x", F(1))
# name: (literal, payload), run after one good atom on literal 1 and one assertion
BAD = {
    "literal zero": (0, GOOD),
    "literal negative": (-3, GOOD),
    "literal repeated": (1, GOOD),
    "literal repeated, other payload": (1, le([("y", F(1))], 2)),
    "payload is an int": (3, 5),
    "payload is None": (3, None),
    "payload too short": (3, (((X1),), F(1))),
    "payload too long": (3, ((X1,), F(1), False, False, 7)),
    "terms is an int": (3, (5, F(1), False, False)),
    "terms is None": (3, (None, F(1), False, False)),
    "term not a pair": (3, ((("x",),), F(1), False, False)),
    "term a triple": (3, ((("x", F(1), 2),), F(1), False, False)),
    "coefficient a string": (3, ((("z", "abc"),), F(1), False, False)),
    "coefficient None": (3, ((("z", None),), F(1), False, False)),
    "coefficient an object": (3, ((("z", object()),), F(1), False, False)),
    "coefficient bad after a new term": (3, (("w", F(1)), ("z", "abc"),) and ((("w", F(1)), ("z", "abc")), F(1), False, False)),
    "unhashable term": (3, (([], F(1)),) and ((([], F(1)),), F(1), False, False)),
    "term whose hash raises": (3, ((Raises(), F(1)),) and (((Raises(), F(1)),), F(1), False, False)),
    "constant a string": (3, ((("z", F(1)),), "abc", False, False)),
    "constant None": (3, ((("z", F(1)),), None, False, False)),
    "constant bad, new term stays": (3, ((("z", F(1)), ("w", F(2))), object(), False, False)),
    "Negated of an int": (3, L.Negated(5)),
    "Negated of None": (3, L.Negated(None)),
    "Integral of an int": (3, L.Integral(5, F(0))),
    "Integral offset a string": (3, L.Integral((("z", F(1)),), "abc")),
    "Integral offset None": (3, L.Integral((("z", F(1)),), None)),
    "Integral coefficient a string": (3, L.Integral((("z", "abc"),), F(0))),
}
# Not errors, and reach `_ground`, `_pending_ground`, generators, zero and repeated coefficients.
ODD = {
    "ground true": (3, ((), F(1), False, False)),
    "ground false": (3, ((), F(-1), False, False)),
    "ground strict at zero": (3, ((), F(0), True, False)),
    "ground equality": (3, ((), F(0), False, True)),
    "ground Negated": (3, L.Negated(((), F(0), False, True))),
    "zero coefficient": (3, ((("z", F(0)),), F(1), False, False)),
    "cancelling terms": (3, ((("z", F(1)), ("z", F(-1))), F(1), False, False)),
    "repeated term": (3, ((("z", F(1)), ("z", F(1))), F(1), False, False)),
    "dict of terms": (3, ({"z": F(2), "w": F(3)}, F(1), False, False)),
    "generator of terms": (3, None),
    "int coefficient": (3, ((("z", 2),), F(1), False, False)),
    "int constant": (3, ((("z", F(1)),), 1, False, False)),
    "truthy flags": (3, ((("z", F(1)),), F(1), 1, 0)),
    "double Negated": (3, L.Negated(L.Negated(GOOD))),
    "Integral plain": (3, L.Integral((("z", F(1)),), F(0))),
    "Integral offset": (3, L.Integral((("z", F(2)),), F(1, 2))),
    "Integral empty": (3, L.Integral((), F(1, 2))),
}


def payload_of(name, table):
    lit, p = table[name]
    if name == "generator of terms":
        p = (((t, c) for t, c in [("z", F(1)), ("w", F(2))]), F(1), False, False)
    return lit, p


def view(t):
    return state.lra_text(t._view() if "_core" in t.__dict__ else t)


def attempt(f, *a):
    try:
        return ("ok", repr(f(*a)))
    except Exception as e:      # what Python raises, by type and text
        return ("raise", type(e).__name__, str(e))


def scenario(cls, name, table):
    t = cls()
    out = [attempt(t.register_atom, 1, GOOD), attempt(t.assert_lit, 1), attempt(t.propagate)]
    lit, p = payload_of(name, table)
    out.append(attempt(t.register_atom, lit, p))
    # State after, and that the session carries on the same way.
    out.append(view(t))
    out.append(attempt(t.push_level))
    out.append(attempt(t.register_atom, 9, le([("x", F(1))], 2)))
    out.append(attempt(t.assert_lit, 9))
    out.append(attempt(t.check))
    out.append(attempt(t.propagate))
    out.append(attempt(t.pop_level))
    out.append(view(t))
    return out, False


def calls(cls):
    """Misuse of the other hooks."""
    res = {}
    for name, f in {
        "assert unregistered": lambda t: t.assert_lit(77),
        "assert zero": lambda t: t.assert_lit(0),
        "pop at level 0": lambda t: t.pop_level(),
        "assert twice": lambda t: (t.register_atom(1, GOOD), t.assert_lit(1), t.assert_lit(1)),
        "assert both signs": lambda t: (t.register_atom(1, GOOD), t.assert_lit(1), t.assert_lit(-1)),
        "check empty": lambda t: t.check(),
        "propagate empty": lambda t: t.propagate(),
    }.items():
        t = cls()
        res[name] = attempt(f, t), view(t)
    return res


def compare():
    bad, moved = [], []
    for table in (BAD, ODD):
        for name in table:
            a, _ = scenario(Py, name, table)
            b, m = scenario(Rs, name, table)
            if m:
                moved.append(name)
            if a != b:
                i = next(i for i, (x, y) in enumerate(zip(a, b)) if x != y)
                bad.append((name, i, str(a[i])[:300], str(b[i])[:300]))
    a, b = calls(Py), calls(Rs)
    for k in a:
        if a[k] != b[k]:
            bad.append((k, "call", str(a[k][0])[:200], str(b[k][0])[:200]))
    return bad, moved


def test_bad_input_raises_what_python_raises_and_stays_in_rust():
    bad, moved = compare()
    assert not bad, bad
    assert not moved, moved


if __name__ == "__main__":
    test_failed_transfer_raises_through_ask()
    print("failed transfer raises through ask: ok")
    bad, moved = compare()
    print(len(BAD), "bad", len(ODD), "odd; differences:", len(bad), "moved:", moved)
    for x in bad:
        print(x)
