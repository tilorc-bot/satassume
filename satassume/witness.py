"""An exact witness check before a contextual query's session (issue 323, a prototype; OFF by default).

``SLICE_WITNESS=1`` turns it on. Off, nothing here runs and the query path is unchanged. On,
:func:`independent` runs in ``sympy_api._engine_ask`` before ``Engine.ask`` (so before any session is built, in
Python's entry and in Rust's alike) and the query returns None when it returns True. In every other case the query
goes on exactly as before.

What it does. A *point* gives every symbol of the query a rational value. :func:`independent` returns True only when
it holds two points, each of which satisfies every assumption of the query and each symbol's own assumptions
(``assumptions0``, the facts the engine's symbol template reads), with the proposition True at one and False at the
other. The search (:func:`_pools`) only proposes points; :func:`_holds` decides, and it runs again on the two points
that are returned.

Soundness. If the engine's definite answers are sound, a verified pair means no definite answer is entailed: True is
refuted by the point where the proposition is False, False by the point where it is True, and the assumptions are
not inconsistent because a point satisfies them. So the engine returns None, and returning None first cannot change
an answer. The argument assumes:

1. *The engine is sound*: it answers True or False, or raises for an inconsistent set, only when that holds at every
   valuation of the symbols that satisfies the assumptions. Where the engine is unsound the check can replace a
   wrong definite answer by None; the answers then differ, which is what the gate compares.
2. *Rational points are valuations*: a commutative ``Symbol`` or ``Dummy`` may stand for any rational number that
   satisfies its own assumptions. Nothing else is given a value: any other leaf is undecided.
3. *The formula is the query*: the check reads the formula ``to_formula`` made (``P`` atoms over the input terms, a
   relation as ``eq``/``lt`` atoms). It assumes that translation keeps the truth value at a rational point.
4. *Evaluation is exact*: a term has a value only by integer and ``Fraction`` arithmetic on ``Add``, ``Mul``, ``Pow``
   with an integer exponent, rational constants and the point (:func:`_term`); a predicate has a value only by the
   table below (:data:`TABLE`: the 14 basis predicates of ``rules.BASIS`` from sa-port-325's table, at a rational
   value; ``rules.DEFINITIONS`` for the derived ones; ``eq`` and ``lt`` by comparing two rationals). Every line of
   the table carries its argument. SymPy's evaluation is never asked (satassume issue 247).
5. *No registered knowledge*: with any function registered in the engine's ``extensions`` the check falls through,
   since a registration can state facts no table here knows. Templates registered by a user are not detected.

Undecided is strict: if any atom of the proposition or the assumptions has no exact value at a point, the point is
not used, and if an atom can have none at any point (``polar``, a function, a Float, an infinity, a relation of
non-terms, a predicate outside the vocabulary) the check falls through at once without trying a point.

No SymPy object is constructed and no SymPy method that evaluates is called: the check reads ``type``, ``args``,
``Rational.p``/``.q`` and ``assumptions0``. It keeps nothing across queries: no cache, no table, no counter.

What still differs with the switch on (state, not answers): a certified query builds no session, so
``Engine.stats`` counts it nowhere, the engine's memos and caches are not filled by it, and
``last_budget_limited`` stays False for a certified query that is over the discovery budget (its None is then
memoized like any other).
"""
import os
from fractions import Fraction

from sympy.core.add import Add
from sympy.core.mul import Mul
from sympy.core.numbers import Rational
from sympy.core.power import Pow
from sympy.core.symbol import Dummy, Symbol

from .knowledge.extensions import Args
from .knowledge.rules import BASIS, DEFINITIONS
from .sat.formula import And, Equivalent, Exclusive, Implies, ITE, Not, Or, P

#: the switch, read once at import; a one-element list so a test or a driver can flip it
ENABLED = [os.environ.get("SLICE_WITNESS") == "1"]
#: points tried per query at most (SLICE_WITNESS_CAP; 0: no cap but LIMIT)
CAP = [int(os.environ.get("SLICE_WITNESS_CAP", "32"))]
LIMIT = 2000
#: planted bugs for the plant table (SLICE_WITNESS_PLANT), never set in normal use:
#: 749 ``integer-half`` (the table says 1/2 is an integer), 750 ``single`` (one witness is enough),
#: 751 ``skip-own`` (the symbols' own assumptions are not checked)
PLANT = [os.environ.get("SLICE_WITNESS_PLANT", "")]

_MAX_EXP = 64         # |integer exponent| above this: undecided
_MAX_BITS = 4096      # a power whose result could be longer: undecided
_MAX_PRIME = 10 ** 6  # primality is decided by trial division up to here; above: undecided


class _Undecided(Exception):
    """No exact value: for a term or atom as such (raised while compiling) or at one point (raised while evaluating)."""


def _is_prime(n):
    """Exact for 2 <= n <= _MAX_PRIME: trial division by every d with d*d <= n."""
    if n > _MAX_PRIME:
        raise _Undecided
    if n % 2 == 0:
        return n == 2
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def _integer(v):
    if PLANT[0] == "integer-half" and v == Fraction(1, 2):
        return True
    return v.denominator == 1


# The 14 basis predicates (rules.BASIS) at a rational value v = p/q in lowest terms. One exactness argument each.
TABLE = {
    # v is the root of the integer polynomial q*t - p
    'algebraic': lambda v: True,
    # a rational is a complex number (with imaginary part 0)
    'complex': lambda v: True,
    # composite: an integer above 1 that is not prime; decided by trial division, undecided above _MAX_PRIME
    'composite': lambda v: _integer(v) and v > 1 and not _is_prime(int(v)),
    # even: an integer whose remainder by 2 is 0
    'even': lambda v: _integer(v) and int(v) % 2 == 0,
    # the order of two rationals is the order of their cross products: v < 0 exactly
    'extended_negative': lambda v: v < 0,
    'extended_positive': lambda v: v > 0,
    # a rational is a real number, so an extended real
    'extended_real': lambda v: True,
    # a rational is not an infinity
    'finite': lambda v: True,
    # imaginary: a nonzero real multiple of I; a rational has imaginary part 0, and 0 is not imaginary
    'imaginary': lambda v: False,
    # integer: the denominator in lowest terms is 1
    'integer': _integer,
    # polar: not decided by this table (sa-port-325: SymPy says False of a number, the engine leaves it open)
    'polar': None,
    # prime: an integer above 1 with no divisor d, 1 < d, d*d <= v; trial division, undecided above _MAX_PRIME
    'prime': lambda v: _integer(v) and v > 1 and _is_prime(int(v)),
    # v is p/q
    'rational': lambda v: True,
    # p == 0
    'zero': lambda v: v == 0,
}
assert tuple(TABLE) == BASIS


def _pred(name):
    """``name`` at a rational value as a function, by TABLE or by the definition of a derived predicate
    (rules.DEFINITIONS: a conjunction or disjunction of basis literals, the engine's own reading)."""
    f = TABLE.get(name)
    if f is not None:
        return f
    d = DEFINITIONS.get(name)
    if d is None:           # polar, or a predicate outside the vocabulary
        raise _Undecided
    d = d.strip()
    if not d:
        return lambda v: True       # commutative: the empty conjunction
    disj = "|" in d
    lits = []
    for t in d.split("|" if disj else "&"):
        t = t.strip()
        f = TABLE[t.lstrip("!")]
        if f is None:
            raise _Undecided
        lits.append((f, not t.startswith("!")))
    if disj:
        return lambda v: any([f(v) == want for f, want in lits])
    return lambda v: all([f(v) == want for f, want in lits])


class _Query:
    """One query's compiled form. Lives for one call of :func:`independent`."""
    __slots__ = ("syms", "consts", "probes")

    def __init__(self):
        self.syms = {}      # symbol -> index in a point
        self.consts = []    # the query's rational constants, in walk order
        self.probes = []    # (difference of an atom's sides, or its term; the indices of its symbols)


def _term(e, q, used):
    """``e`` as a function of a point, exact or raising _Undecided. ``used``: the symbol indices seen, added to."""
    t = type(e)
    if t is Symbol or t is Dummy:
        i = q.syms.setdefault(e, len(q.syms))
        used.add(i)
        return lambda pt: pt[i]
    if isinstance(e, Rational):     # Integer, Rational and their singletons: p/q exactly, as Python ints
        c = e.p if e.q == 1 else Fraction(e.p, e.q)
        q.consts.append(c)
        return lambda pt: c
    if t is Add:
        fs = [_term(a, q, used) for a in e.args]

        def add(pt):
            s = 0
            for f in fs:
                s += f(pt)
            return s
        return add
    if t is Mul:
        fs = [_term(a, q, used) for a in e.args]

        def mul(pt):
            s = 1
            for f in fs:
                s *= f(pt)
            return s
        return mul
    if t is Pow:
        fb, fx = _term(e.args[0], q, used), _term(e.args[1], q, used)

        def power(pt):
            b, n = fb(pt), fx(pt)
            # an integer power of a rational is exact; a root, 0**0 and 1/0 are left undecided
            if n.denominator != 1:
                raise _Undecided
            n = int(n)
            if abs(n) > _MAX_EXP or (b == 0 and n <= 0):
                raise _Undecided
            if (abs(b.numerator).bit_length() + b.denominator.bit_length()) * abs(n) > _MAX_BITS:
                raise _Undecided
            return b ** n if n >= 0 else Fraction(b) ** n
        return power
    raise _Undecided        # a function, a Float, an infinity, a named constant, a Wild, a matrix, a non-term


def _formula(f, q):
    """The formula ``f`` as a function of a point giving True or False, or raising _Undecided. Strict: every argument
    is evaluated, so an undecided atom anywhere leaves the point unused."""
    if f is True or f is False:
        return lambda pt: f
    t = type(f)
    if t is P:
        name, e = f.pred, f.expr
        used = set()
        if name == "eq" or name == "lt":
            if type(e) is not Args or len(e) != 2:
                raise _Undecided
            fa, fb = _term(e[0], q, used), _term(e[1], q, used)
            q.probes.append((lambda pt: fa(pt) - fb(pt), used))
            if name == "eq":
                return lambda pt: fa(pt) == fb(pt)      # two rationals are equal when p1*q2 == p2*q1
            return lambda pt: fa(pt) < fb(pt)           # and ordered as p1*q2 < p2*q1 (positive q)
        if type(e) is Args:
            raise _Undecided
        pr, ft = _pred(name), _term(e, q, used)
        if type(e) is not Symbol and type(e) is not Dummy:
            q.probes.append((ft, used))
        return lambda pt: pr(ft(pt))
    if t is Not:
        g = _formula(f.args[0], q)
        return lambda pt: not g(pt)
    gs = [_formula(a, q) for a in f.args]
    if t is And:
        return lambda pt: all([g(pt) for g in gs])
    if t is Or:
        return lambda pt: any([g(pt) for g in gs])
    if t is Implies:
        return lambda pt: [g(pt) for g in gs] != [True, False]
    if t is Equivalent:
        return lambda pt: len(set([g(pt) for g in gs])) <= 1
    if t is Exclusive:
        return lambda pt: sum([g(pt) for g in gs]) <= 1
    if t is ITE:
        def ite(pt):
            c, a, b = [g(pt) for g in gs]
            return a if c else b
        return ite
    raise _Undecided


def _own(sym):
    """The symbol's own assumptions as a function of its value: every fact of ``assumptions0`` holds. A fact the
    table does not decide makes the query undecided."""
    lits = [(_pred(str(k)), v) for k, v in sym.assumptions0.items() if v is not None]
    return lambda v: all([f(v) == want for f, want in lits])


_HEAD = (0, 1, -1, 2, -2, Fraction(1, 2), Fraction(-1, 2))
_TAIL = (3, -3, Fraction(3, 2), Fraction(-3, 2), 4, -4, Fraction(1, 3), Fraction(-1, 3), 5, -5, 6, 7, 9, 10, -10,
         Fraction(1, 4), Fraction(5, 2), Fraction(-5, 2), 100, -100)


def _roots(q, n):
    """Per symbol, exact roots of the query's atoms: for a relation the difference of its sides, for a predicate of a
    compound term the term. With the other symbols at 0 and then at 1, the secant through t = 0 and t = 1 gives a
    candidate, kept only if the atom's function is exactly 0 there. Proposes values; decides nothing."""
    out = [[] for _ in range(n)]
    for d, used in q.probes:
        for i in used:
            for other in (0, 1):
                pt = [other] * n
                try:
                    pt[i] = 0
                    d0 = d(pt)
                    pt[i] = 1
                    d1 = d(pt)
                    if d1 == d0:
                        continue
                    r = Fraction(-d0) / (d1 - d0)
                    pt[i] = r
                    if d(pt) == 0 and r not in out[i]:
                        out[i].append(r)
                except _Undecided:
                    continue
    return out


def _pools(q, owns):
    """One list of candidate values per symbol, simplest first: the head, the symbol's roots with their midpoints and
    a step outside, the query's constants and their neighbours, the tail; without the values the symbol's own
    assumptions exclude. (sa-port-325's search without SymPy.)"""
    n = len(q.syms)
    roots = _roots(q, n)
    consts = []
    for c in sorted(set(q.consts), key=lambda c: (abs(c), c))[:8]:
        consts += [c, c + 1, c - 1, c + Fraction(1, 2), c - Fraction(1, 2)]
    pools = []
    for i in range(n):
        rs = sorted(roots[i][:12])
        crit = list(rs)
        for a, b in zip(rs, rs[1:]):
            crit.append((a + b) / 2)
        if rs:
            crit += [rs[0] - 1, rs[-1] + 1, rs[0] - Fraction(1, 2), rs[-1] + Fraction(1, 2)]
        seen, pool = set(), []
        own = owns[i]
        for v in list(_HEAD) + crit + consts + list(_TAIL):
            if v not in seen:
                seen.add(v)
                if own is None or own(v):
                    pool.append(v)
        pools.append(pool)
    return pools


def _by_index_sum(sizes):
    """All index tuples over the given sizes, smallest index sum first."""
    for tot in range(sum(m - 1 for m in sizes) + 1):
        yield from _compositions(sizes, 0, tot)


def _compositions(sizes, k, tot):
    m = sizes[k]
    if k == len(sizes) - 1:
        if tot < m:
            yield (tot,)
        return
    for i in range(min(tot, m - 1) + 1):
        for rest in _compositions(sizes, k + 1, tot - i):
            yield (i,) + rest


def _holds(pt, owns, fa, fp):
    """The proposition's value at ``pt`` (True or False) if every own assumption and the assumptions hold there
    exactly; None if one fails or anything is undecided. This, not the search, is what a witness rests on."""
    try:
        for own, v in zip(owns, pt):
            if own is not None and not own(v):
                return None
        if fa(pt) is not True:
            return None
        r = fp(pt)
    except _Undecided:
        return None
    return r if r is True or r is False else None


def independent(proposition, assumptions, eng=None):
    """True only if two rational points both satisfy ``assumptions`` and every symbol's own assumptions, and
    ``proposition`` is exactly True at one and exactly False at the other (see the module docstring for why the
    query's answer is then None, and what that assumes). False in every other case: the caller goes on unchanged.

    ``proposition`` and ``assumptions`` are formulas over ``P`` atoms (``sympy_api.to_formula``)."""
    return witnesses(proposition, assumptions, eng) is not None


def witnesses(proposition, assumptions, eng=None):
    """The pair behind :func:`independent`: ``(symbols, point where the proposition is True, point where it is
    False, points tried)``, or None."""
    if eng is not None:
        ext = eng.extensions
        if ext is not None and (ext._handlers or ext._vocab):
            return None
    q = _Query()
    try:
        fa = _formula(assumptions, q)
        fp = _formula(proposition, q)
        skip = PLANT[0] == "skip-own"
        owns = [None if skip else _own(s) for s in q.syms]
    except _Undecided:
        return None
    if not q.syms:
        return None
    pools = _pools(q, owns)
    sizes = [len(p) for p in pools]
    if 0 in sizes:
        return None
    cap = CAP[0] or LIMIT
    found = {}
    tried = 0
    for idx in _by_index_sum(sizes):
        if tried >= cap or tried >= LIMIT:
            return None
        tried += 1
        pt = [pool[i] for pool, i in zip(pools, idx)]
        r = _holds(pt, owns, fa, fp)
        if r is None:
            continue
        found.setdefault(r, pt)
        if len(found) == 2 or PLANT[0] == "single":
            break
    else:
        return None
    yes, no = found.get(True), found.get(False)
    if PLANT[0] == "single":
        return list(q.syms), yes, no, tried
    # decide again on the two points returned: the search above only proposed them
    if _holds(yes, owns, fa, fp) is not True or _holds(no, owns, fa, fp) is not False:
        return None
    return list(q.syms), yes, no, tried
