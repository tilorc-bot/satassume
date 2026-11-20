"""The witness check's native path (sa-port-351, issue 323): SLICE_WITNESS_RUST=1 puts solver_rs/src/witness.rs behind
`satassume.witness.NATIVE`. Off by default, and it acts only with SLICE_WITNESS=1 and SLICE_CONVERT=rust (the planner's
tie for this step; the code itself needs only the query's table, which the Python walker gives as well). Python's
`satassume/witness.py` stays the default and the reference: this hook mirrors `witnesses` from its compile on, in the
same order, and hands the whole query back (`NotImplemented`) wherever the native side does not mirror it.

Native: the compile (`sa_solver.witness_compile`, on the term ids of `term_live.current()`'s table; the `P` formula
is read once and each atom side is one lookup in the query's `ids`), the pools, the search and the second decision on
the two points (`WitnessQuery.search`). Python, by design (formula ruling P1: a user's method is called by name, and
what a user registered is read off the engine): `witness._patched`, `Engine._known_inconsistent`,
`witness._users_knowledge`, each at the place witness.py calls it.

To Python's witness.py, counted: no table (outside a slice query, a kept or refused one), a witness.py plant set
(SLICE_WITNESS_PLANT: those rows keep testing the reference), or one of witness.py's own functions or classes replaced
since this module was imported (a test's wrapper, an instrument: what was put there is the reference's to call, and
only witness.py calls it): `wn:fallback:off`, counter 713, here; a side that is not
in the table, of another type, or a shape that is not mirrored: `wn:fallback:miss`, `:type`, `:shape`, in witness.rs.
Nothing is kept across queries: the compiled query dies with the call.

Plants (SLICE_WITNESS_RUST_PLANT; each acts only with the native path on): 760 `wn-integer-half`, 761 `wn-work-one`,
763 `wn-int-side` in witness.rs; here 762 `wn-skip-patched` (a user's method on the engine is passed over) and 764
`wn-skip-own` (a replaced function of witness.py is passed over).
"""
import os
import types

import sa_solver
from satassume import witness

import term_live

#: counter 713: queries left to witness.py before the native compile (no table, or a witness.py plant)
COUNTS = {'wn:fallback:off': 0}
PLANT = [None]
#: how often 762's or 764's site read its plant as set
FIRED = [0]
_HERE = ('wn-skip-patched', 'wn-skip-own')
_CLASSES = [()]
#: what witness.py calls by name with the hook set as without it: its two entry points and the guards
_BY_NAME = ('independent', 'witnesses', 'accept', '_patched', '_users_knowledge')
#: witness.py's other functions and classes as imported, the code this hook stands in for: a constant
_OWN = tuple((n, f) for n, f in vars(witness).items()
             if isinstance(f, (types.FunctionType, type)) and f.__module__ == witness.__name__ and n not in _BY_NAME)


def _classes():
    c = _CLASSES[0]
    if not c or c[0] is not witness.P:
        c = _CLASSES[0] = (witness.P, witness.Not, witness.And, witness.Or, witness.Implies, witness.Equivalent,
                           witness.Exclusive, witness.ITE, witness.Args)
    return c


def _replaced():
    """True if a name of `_OWN` no longer holds witness.py's own object."""
    if PLANT[0] == 'wn-skip-own':
        FIRED[0] += 1
        return False
    d = witness.__dict__
    for n, f in _OWN:
        if d.get(n) is not f:
            return True
    return False


def native(proposition, assumptions, eng):
    """`witness.NATIVE`'s function: `witnesses` after its extensions test."""
    q = term_live.current()
    if q is None or q.table is None or witness.PLANT[0] or _replaced():
        COUNTS['wn:fallback:off'] += 1
        return NotImplemented
    h = sa_solver.witness_compile(q.table, q.ids, q.objects, assumptions, proposition, _classes())
    if h is None:
        return None
    if h is False:
        return NotImplemented
    if eng is not None:
        if PLANT[0] == 'wn-skip-patched':
            FIRED[0] += 1
        elif witness._patched(eng):
            return None
        if eng._known_inconsistent(assumptions):
            return None
    r = h.search(witness.CAP[0], witness.LIMIT, witness.WORK[0])
    if r is None:
        return None
    if eng is not None and witness._users_knowledge(eng):
        return None
    objects = q.objects
    return [objects[i] for i in h.syms], r[0], r[1], r[2]


def counts():
    """Counters 706-713."""
    out = dict(sa_solver.witness_counts())
    out.update(COUNTS)
    return out


def install(on=True):
    witness.NATIVE[0] = native if on else None


def plant(name):
    """A native plant by name, or None."""
    PLANT[0] = name if name in _HERE else None
    sa_solver.witness_plant(None if name in _HERE else name)


def from_env():
    """SLICE_WITNESS_RUST=1 with SLICE_WITNESS=1 and SLICE_CONVERT=rust; SLICE_WITNESS_RUST_PLANT names a plant."""
    on = (os.environ.get('SLICE_WITNESS_RUST') == '1' and witness.ENABLED[0]
          and os.environ.get('SLICE_CONVERT') == 'rust')
    install(on)
    plant((os.environ.get('SLICE_WITNESS_RUST_PLANT') or None) if on else None)
    return on
