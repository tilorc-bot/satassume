"""Which of two equal term objects each backend keeps. Hook-level, one process, because ids can't be compared across
the two processes the state comparison runs in, so `state.py` can't see this. `term:last_object` has to fail it.
Terms here are equal and hash alike but aren't the same object, which `ask` doesn't make through SymPy's canonical forms."""
import os
import sys
from fractions import Fraction as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lra_backend  # noqa: E402
from satassume.theories.lra.lra import LRATheory as Py  # noqa: E402


class T:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return f"T({self.name})"


def le(pairs, rhs):
    return (tuple((t, F(c)) for t, c in pairs), F(rhs), False, False)


def kept(cls, atoms):
    t = cls()
    for lit, atom in enumerate(atoms, 1):
        t.register_atom(lit, atom)
    t.propagate()
    state = t._state() if hasattr(t, "_state") else {"_key": t._key}
    return [None if k is None else id(k) for k in state["_key"]]


def test_key_keeps_the_first_object_on_both():
    x1, x2, x3, y1, y2 = T("x"), T("x"), T("x"), T("y"), T("y")
    atoms = [le([(x1, 1)], 1), le([(x2, 1)], 2), le([(x3, 1), (y1, 1)], 3), le([(y2, 1), (x2, 1)], 4), le([(y2, 1)], 5)]
    py, rs = kept(Py, atoms), kept(lra_backend.LRATheory, atoms)
    assert py == rs
    assert id(x1) in py and id(x2) not in py and id(x3) not in py, "first object kept, or this isn't testing that"
