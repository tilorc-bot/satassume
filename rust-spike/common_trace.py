"""What record.py and replay_py.py share: opcodes, result normalization, counters."""
import zlib
from array import array

OPS = dict(QUERY=1, NEW=2, DROP=3, attach_theory=10, register_atom=11, ensure_vars=12, new_var=13,
           add_clause=14, add_clauses=15, add_internal=16, add_pattern=17, set_rule_block=18,
           register_block=19, mention_blocks=20, mention=21, propagate=22, value=23, root_trail=24,
           implied=25, release=26, set_inert=27, solve=28, consistent=29, entails=30, entails_all=31,
           theories=32, nvars=33, stats=34, model=35, conflict=36, theory_models=37,
           BLOCK=40, PATTERN=41)
MAGIC = 0x53525431
# Tape kinds, per theory, chronological
T_ASSERT, T_PROP, T_CHECK, T_DECIDE = 1, 2, 3, 4
COUNTERS = ("_n_decisions", "_n_conflicts", "_n_props", "_n_learned", "_n_restarts", "_n_reductions",
            "_n_ring_hits", "_n_tdecisions")


def norm(r):
    """The result of a public call as a list of ints, for the per-call checksum."""
    if r is None:
        return [-2]
    if r is True:
        return [1]
    if r is False:
        return [0]
    if isinstance(r, int):
        return [r]
    if isinstance(r, list):
        if r and not isinstance(r[0], int):      # theories(): opaque objects
            return [len(r)]
        return [len(r), *r]
    if isinstance(r, dict):
        return [len(r), *(x for kv in r.items() for x in kv)]
    raise TypeError(f"no normal form for {type(r)}")


def crc(words):
    return zlib.crc32(array("i", words).tobytes())


EXC = [-3]      # a ValueError from the solver
