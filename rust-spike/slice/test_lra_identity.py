"""Which of two equal term objects each backend keeps. Hook-level, one process, because ids can't be compared across
the two processes the state comparison runs in, so `state.py` can't see this. `term:last_object` has to fail it.
Terms here are equal and hash alike but aren't the same object, which `ask` doesn't make through SymPy's canonical forms."""
import os
import sys
from fractions import Fraction as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402
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
    state = t._state() if hasattr(t, "_state") else {k: getattr(t, k) for k in ("_key", "_forms")}
    keys = [None if k is None else id(k) for k in state["_key"]]
    forms = sorted(sorted(id(a) for a, _ in f) for f in state["_forms"])
    return keys, forms


def test_key_keeps_the_first_object_on_both():
    x1, x2, x3, y1, y2 = T("x"), T("x"), T("x"), T("y"), T("y")
    atoms = [le([(x1, 1)], 1), le([(x2, 1)], 2), le([(x3, 1), (y1, 1)], 3), le([(y2, 1), (x2, 1)], 4), le([(y2, 1)], 5)]
    py, rs = kept(Py, atoms)[0], kept(lra_backend.LRATheory, atoms)[0]
    assert py == rs
    assert id(x1) in py and id(x2) not in py and id(x3) not in py, "first object kept, or this isn't testing that"


@pytest.mark.xfail(strict=True, reason="found by this test, reported, not fixed: Python's _forms key holds the objects of "
                   "the first atom with that form, `_state` rebuilds it from the first object per term. lra.py only "
                   "hashes those keys (:707, :716). Equal SymPy terms can be distinct objects: x*y, y*x.")
def test_forms_key_keeps_the_same_objects_on_both():
    x1, x2, y1 = T("x"), T("x"), T("y")
    atoms = [le([(x1, 1)], 1), le([(x2, 1), (y1, 1)], 3)]
    assert kept(Py, atoms)[1] == kept(lra_backend.LRATheory, atoms)[1]


@pytest.mark.xfail(strict=True, reason="found by identity_rule.py, reported, not fixed: `_forms` iterates in first-registration order "
                   "on Python, and the Rust dump sorts by key (lra_py.rs, `forms.sort_by`). state.py sorts it too, so the "
                   "comparison can't see this, which is `order:_forms` not caught. No aliasing needed.")
def test_forms_iterate_in_the_same_order_on_both():
    x, y = T("x"), T("y")
    atoms = [le([(x, 1), (y, 1)], 1), le([(x, 1)], 2)]

    def order(cls):
        t = cls()
        for lit, atom in enumerate(atoms, 1):
            t.register_atom(lit, atom)
        st = t._state() if hasattr(t, "_state") else {"_forms": t._forms}
        return [sorted(a.name for a, _ in f) for f in st["_forms"]]
    assert order(Py) == order(lra_backend.LRATheory)
