"""The canonical text of one LRATheory call's result and of the theory's visible state after it. The recorder and both
replays hash this (the Rust replay writes the same text), so a difference anywhere shows up on that call."""


def _lits(xs):
    return ",".join(map(str, xs))


def result_str(r, ids=None):
    """ids: the recorder's term -> id; in a replay the terms already are ids."""
    if r is None:
        return "N"
    if isinstance(r, list):             # propagate
        return "G" + ";".join(f"{x}:{_lits(why)}" for x, why in r)
    if r[0] is False:
        return "F" + _lits(r[1])
    return "T" + ",".join(f"{ids[t] if ids is not None else t}={q.numerator}/{q.denominator}"
                          for t, q in r[1].items())


def state_str(th):
    s = th.stats
    return (f"|{s['pivots']},{s['checks']},{s['conflicts']},{s['propagations']},{s['branches']},{s['exhausted']},"
            f"{int(th.exhausted)},{len(th._key)},{len(th._rows)}")
