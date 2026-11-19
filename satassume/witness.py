"""An exact witness check before a contextual query's session (issue 323, a prototype; OFF by default).

``SLICE_WITNESS=1`` turns it on. Off, nothing here runs and the query path is unchanged. On,
:func:`independent` runs in ``sympy_api._engine_ask`` before ``Engine.ask`` (so before any session is built, in
Python's entry and in Rust's alike) and the query returns None when it returns True. In every other case the query
goes on exactly as before.

What it does. A *point* gives every symbol of the query a rational value (in a query that holds the constant pi
outside every function: a value of Q[pi], see "Exact pi" below). :func:`independent` returns True only when
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
   satisfies its own assumptions. A symbol is given rational values only, also in a query that holds pi. Nothing
   else is given a value: any other leaf but a rational constant and pi is undecided.
3. *The formula is the query*: the check reads the formula ``to_formula`` made (``P`` atoms over the input terms, a
   relation as ``eq``/``lt`` atoms). It assumes that translation keeps the truth value at a point.
4. *Evaluation is exact*: a term has a value only by integer and ``Fraction`` arithmetic on ``Add``, ``Mul``, ``Pow``
   with an integer exponent, rational constants and the point (:func:`_term`); a predicate has a value only by the
   tables below: :data:`TABLE`, 16 entries (the 14 basis predicates of ``rules.BASIS`` from sa-port-325's table,
   at a rational value, and ``eq`` and ``lt`` of two rational values), and for a derived predicate
   ``rules.DEFINITIONS`` where the definition is two-way in SymPy's own rule base (:data:`TWO_WAY`, 16 entries) or
   the value a one-way SymPy rule gives every rational (:data:`ONE_WAY`: ``hermitian`` and ``commutative``;
   ``antihermitian`` is undecided). Every line carries its argument. SymPy's evaluation is never asked (satassume
   issue 247). Exact pi (sa-port-341): the constant pi has the value pi, a term's value is then in Q[pi]
   (:class:`_PiPoly`: Add, Mul and a power by a non-negative integer; anything that leaves Q[pi] is undecided),
   and a predicate at a non-rational value of Q[pi] is read off :data:`PI_TABLE`, 16 entries whose arguments rest
   on the transcendence of pi and on one fixed rational enclosure of pi to 50 decimals (:func:`_sign`; a sign the
   enclosure does not give is undecided). A query without pi is compiled and evaluated as before, on rationals
   only; pi inside a function is undecided with the function.
5. *No registered knowledge*: with any function registered in the engine's ``extensions`` the check falls through,
   since a registration can state facts no table here knows. So it does on any other knowledge a user gave
   (:func:`_users_knowledge`): a function in the default registry, a template in the registry the engine reads
   (``TemplateRegistry.register``, or a module declared with ``lazy``), a templates function of the user's
   (``Engine(templates=...)``, ``Engine.templates``) and a relation adapter that is not the package's
   (``Engine(relations=...)``, ``Engine.relation_specs``). A user's template may be unsound: the engine then
   gives a definite answer where two points exist, and with the switch off that answer is the one returned.
6. *The engine's methods are its own*: a certified query calls none of ``Engine.ask``, ``verdict``,
   ``_context_session`` and ``_within_budget`` (:data:`GUARDED`; formula ruling P1's methods and ``ask``). If one
   of them is not the engine's own, on the instance or on the class, the check falls through, so a user's method
   is called and its result used exactly as with the switch off. The engine's own are the methods the class had
   when ``sympy_api`` was imported, a backend's replacements and registered instruments (:func:`accept`).

Undecided is strict: if any atom of the proposition or the assumptions has no exact value at a point, the point is
not used, and if an atom can have none at any point (``polar``, a function, a Float, an infinity, a relation of
non-terms, ``antihermitian``, a predicate outside the vocabulary) the check falls through at once without trying a
point. (pi is not such an atom since sa-port-341; a power of pi by a negative or a non-integer rational literal,
``1/pi`` or ``sqrt(pi)``, is one.)

No SymPy object is constructed and no SymPy method that evaluates is called: the check reads ``type``, ``args``,
``Rational.p``/``.q`` and ``assumptions0``. This module imports no SymPy: ``sympy_api``, the SymPy front end, gives
it the seven classes it compares types with (:func:`bind`); until then every term is undecided. It keeps nothing across queries: no cache, no table, no counter.

The engine's exits that need no session come first (sa-port-346): once a query is compiled and before a point is
tried, the check asks ``Engine._ends_without_session``, and falls through if the query is over the discovery budget
or its set has a memoized INCONSISTENT. Such a query is the engine's as with the switch off, with
``last_budget_limited`` and ``stats["budget_limited"]`` set by it.

What still differs with the switch on (state, not answers): a certified query builds no session, so of
``Engine.stats`` it moves only ``queries``, like any other query, and ``witness_certified``
(``Engine._record_certified``, called by ``sympy_api``); of the engine's memos and caches it fills only the ones
the budget test reads (the structural cones: ``_kids``, ``_cones``, ``_qcones``).
"""
import os
from fractions import Fraction

from .knowledge.extensions import Args, extensions as _DEFAULT
from .knowledge.rules import BASIS, DEFINITIONS
from .sat.formula import And, Equivalent, Exclusive, Implies, ITE, Not, Or, P


class _Unbound:
    """Stands for a SymPy class before :func:`bind`: no object is one, so every term is undecided."""


#: SymPy's classes, compared with ``type(e)`` only. Set by :func:`bind` from ``sympy_api`` at its import.
Add = Mul = Pow = Rational = Symbol = Dummy = Pi = _Unbound


def bind(add, mul, pow_, rational, symbol, dummy, pi):
    """Called once by ``sympy_api``, which imports SymPy: the classes :func:`_term` and :func:`_formula` read.
    ``pi`` is the class of the constant pi, ``type(S.Pi)``."""
    global Add, Mul, Pow, Rational, Symbol, Dummy, Pi
    Add, Mul, Pow, Rational, Symbol, Dummy, Pi = add, mul, pow_, rational, symbol, dummy, pi


#: the switch, read once at import; a one-element list so a test or a driver can flip it
ENABLED = [os.environ.get("SLICE_WITNESS") == "1"]
#: points tried per query at most (SLICE_WITNESS_CAP; 0: no cap but LIMIT)
CAP = [int(os.environ.get("SLICE_WITNESS_CAP", "32"))]
LIMIT = 2000
#: planted bugs for the plant table (SLICE_WITNESS_PLANT), never set in normal use:
#: 749 ``integer-half`` (the table says 1/2 is an integer), 750 ``single`` (one witness is enough),
#: 751 ``skip-own`` (the symbols' own assumptions are not checked), 752 ``skip-patched`` (a user's method on the
#: engine is passed over), 754 ``skip-users`` (a user's templates, adapters and default-registry functions are
#: passed over), 755 ``pi-sign`` (:func:`_sign` calls a positive value of Q[pi] negative), 756 ``pi-rational``
#: (:data:`PI_TABLE` says a non-rational value of Q[pi] is rational), 757 ``pi-enclosure`` (:func:`_sign` reads an
#: interval that does not hold pi)
#: how often a planted site read its own plant as set (the bar's fired column for a witness row, counter 740); it
#: stays 0 unless the plant came from SLICE_WITNESS_PLANT
FIRED = [0]


class _Plant(str):
    """A plant's name that counts each site that finds it set, by ``==`` or ``!=``. A count of 0 under a plant means
    no query reached the planted site, so that row shows nothing about the plant."""

    __hash__ = str.__hash__

    def __eq__(self, o):
        r = str.__eq__(self, o)
        if r is True:
            FIRED[0] += 1
        return r

    def __ne__(self, o):
        r = str.__ne__(self, o)
        if r is False:
            FIRED[0] += 1
        return r


PLANT = [_Plant(os.environ["SLICE_WITNESS_PLANT"]) if os.environ.get("SLICE_WITNESS_PLANT") else ""]

#: the Engine methods a certified query does not call: formula ruling P1's three and ``ask`` itself
GUARDED = ("ask", "verdict", "_context_session", "_within_budget")
#: name -> the objects that count as the engine's own method of that name (:func:`accept`). Registrations, not
#: history: nothing a query does writes here.
ACCEPTED = {n: [] for n in GUARDED}


def accept(cls, *names):
    """Record what ``cls`` holds now under ``names`` (default: all of :data:`GUARDED`) as the engine's own.
    ``sympy_api`` calls it at import for Python's methods; a backend that replaces one, or an instrument of ours
    that wraps one without changing its result, calls it after installing. A method never accepted is a user's."""
    for n in names or GUARDED:
        f = cls.__dict__.get(n)
        if f is not None and not any(f is g for g in ACCEPTED[n]):
            ACCEPTED[n].append(f)


def _patched(eng):
    """True if one of :data:`GUARDED` is not the engine's own, on the instance or on its class (the rule of
    context.rs ``method_of``: the instance's ``__dict__`` first, then the class's attribute by identity)."""
    d = getattr(eng, "__dict__", ())
    cls = type(eng)
    for n in GUARDED:
        if n in d:
            return True
        f = getattr(cls, n, None)
        for g in ACCEPTED[n]:
            if f is g:
                break
        else:
            return True
    return False

#: the package whose modules register the engine's own templates, and the one that holds its relation adapters
_TEMPLATES = __package__ + ".knowledge.templates."
_THEORIES = __package__ + ".theories."


def _users_knowledge(eng):
    """True if knowledge a user gave may be in force besides the functions of the engine's own registry, which
    :func:`witnesses` asks first (assumption 5). The entry points: ``extensions.register`` on the default registry
    while the engine uses another (it still decides ``sympy_api``'s scope), ``TemplateRegistry.register`` and
    ``lazy``, ``Engine(templates=...)`` and ``Engine.templates``, ``Engine(relations=...)`` and
    ``Engine.relation_specs``. Whose a template or an adapter is, is read off its module: the package's own are
    the engine's, a backend's replacements keep the module of what they replace. Nothing is written here."""
    if _DEFAULT._handlers or _DEFAULT._vocab:
        return True
    if eng.clause_templates is None:
        # a templates function given by the user (or no SymPy): the registry's compiled path is off
        return True
    reg = getattr(eng._templates, "__self__", None)
    by_class, lazy = getattr(reg, "_by_class", None), getattr(reg, "_lazy", None)
    if by_class is None or lazy is None:
        return True
    for spec in eng._relation_specs:
        if not str(getattr(spec.factory, "__module__", "")).startswith(_THEORIES):
            return True
    own = _TEMPLATES
    for _, module in lazy:
        # a module declared by a user registers like a built-in one, without a new epoch, when it is first used
        if not module.startswith(own):
            return True
    for ts in by_class.values():
        for t in ts:
            if not str(getattr(t, "__module__", "")).startswith(own):
                return True
    return False


_MAX_EXP = 64         # |integer exponent| above this: undecided
_MAX_BITS = 4096      # a power whose result could be longer: undecided
_MAX_PRIME = 10 ** 6  # primality is decided by trial division up to here; above: undecided
_MAX_DEG = 16         # a value of Q[pi] of a higher degree in pi: undecided


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


# 16 entries, one exactness argument each: the 14 basis predicates (rules.BASIS) at a rational value v = p/q in lowest
# terms, then the two relations of two rational values.
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
    # eq: p1/q1 and p2/q2 with positive denominators are the same number exactly when p1*q2 == p2*q1 (Fraction.__eq__)
    'eq': lambda a, b: a == b,
    # lt: with positive denominators p1/q1 < p2/q2 exactly when p1*q2 < p2*q1 (Fraction.__lt__); the order is total
    'lt': lambda a, b: a < b,
}
RELATIONS = ('eq', 'lt')
BASIS_SET = frozenset(BASIS)
assert tuple(TABLE) == BASIS + RELATIONS

# The derived predicates (rules.DEFINITIONS: the engine reads each as its definition in both directions). A
# definition is used here only where SymPy's own rule base (sympy/core/assumptions.py, sympy/assumptions/facts.py)
# also states or entails it in both directions; the rules it rests on are given per entry, and
# tests/test_witness.py::test_two_way_definitions_follow_from_sympys_rules checks the entailment mechanically.
TWO_WAY = {
    'real': "real == extended_real & finite",
    'infinite': "infinite == !finite",
    'positive': "positive == extended_positive & finite",
    'negative': "negative == extended_negative & finite",
    'nonnegative': "nonnegative == real & !negative, with real and negative as above",
    'nonpositive': "nonpositive == real & !positive, with real and positive as above",
    'nonzero': "nonzero == extended_nonzero & finite, with extended_nonzero as below",
    'extended_nonnegative': "extended_nonnegative == extended_real & !extended_negative",
    'extended_nonpositive': "extended_nonpositive == extended_real & !extended_positive",
    'extended_nonzero': "extended_nonzero == extended_real & !zero",
    'positive_infinite': "facts.py: extended_positive == positive | positive_infinite, the two exclusive, "
                         "positive_infinite -> infinite; with positive as above",
    'negative_infinite': "facts.py: extended_negative == negative | negative_infinite, the two exclusive, "
                         "negative_infinite -> infinite; with negative as above",
    'odd': "odd == integer & !even",
    'irrational': "irrational == real & !rational",
    'noninteger': "noninteger == extended_real & !integer",
    'transcendental': "transcendental == complex & !algebraic",
}
# SymPy's rule base has only a one-way rule for these three; the engine's two-way reading is its own (scalars only,
# rules.py). The definition is not used: the value is what the one-way rule gives every rational, or undecided.
ONE_WAY = {
    # rational -> real -> hermitian: True at every rational by the rule's own direction
    'hermitian': lambda v: True,
    # rational -> extended_real -> commutative: True at every rational by the rule's own direction
    'commutative': lambda v: True,
    # imaginary -> antihermitian and zero -> hermitian | antihermitian decide it at no rational: undecided
    'antihermitian': None,
}
assert set(TWO_WAY) | set(ONE_WAY) == set(DEFINITIONS) and not set(TWO_WAY) & set(ONE_WAY)


# ---- exact pi (sa-port-341) ----
#
# A query that holds the constant pi outside every function has its terms' values in Q[pi], the polynomials in pi
# with rational coefficients. Everything below rests on one theorem and one enclosure:
#
# (T) pi is transcendental (Lindemann 1882): p(pi) != 0 for every non-zero polynomial p with rational coefficients.
#     So a value of Q[pi] has exactly one polynomial, two values are equal exactly when their polynomials are, and
#     a non-constant p gives a transcendental number: were a = p(pi) algebraic, pi would be a root of the
#     non-constant polynomial p(t) - a with algebraic coefficients, and so algebraic.
# (E) _PI_LO < pi < _PI_HI, where _PI_LO is pi's decimal expansion cut after 50 places and _PI_HI is _PI_LO plus
#     10**-50. Source of the digits: OEIS A000796 (the decimal expansion of pi), whose places 51 to 55 are 58209,
#     so the cut is strict on both sides. tests/test_witness.py::test_the_enclosure_holds_pi proves (E) again
#     from Machin's formula pi = 16*atan(1/5) - 4*atan(1/239) with the alternating series' own error bounds, in
#     Fraction arithmetic. Nothing here computes pi, and SymPy's evaluation is not asked (issue 247).
_PI_N, _PI_D = 314159265358979323846264338327950288419716939937510, 10 ** 50
# the powers 0.._MAX_DEG of the two bounds: 0 < _PI_LO, so _PI_LO**k < pi**k < _PI_HI**k for every k >= 1
_LO = [Fraction(_PI_N, _PI_D) ** k for k in range(_MAX_DEG + 1)]
_HI = [Fraction(_PI_N + 1, _PI_D) ** k for k in range(_MAX_DEG + 1)]
# plant 757 only: an interval that does not hold pi (3.2 < t < 3.3)
_BAD_LO = [Fraction(32, 10) ** k for k in range(_MAX_DEG + 1)]
_BAD_HI = [Fraction(33, 10) ** k for k in range(_MAX_DEG + 1)]


class _PiPoly:
    """A value of Q[pi] that is not rational: ``c[0] + c[1]*pi + ... + c[d]*pi**d`` with rational ``c``, ``d >= 1``
    and ``c[d] != 0``. By (T) the tuple ``c`` is the value's only representation, so ``==`` and ``hash`` read the
    tuple. A rational result of an operation is returned as an int or a Fraction (:func:`_poly`), never as a
    _PiPoly. The operations are the ring's: + - * with a rational or a _PiPoly, / by a non-zero rational, ** by an
    int n >= 0; what leaves Q[pi] (a division by a _PiPoly, a negative power) is undecided."""
    __slots__ = ("c",)

    def __init__(self, c):
        self.c = c

    def __repr__(self):
        return "_PiPoly(%r)" % (self.c,)

    def __eq__(self, o):
        # a rational is never equal to a non-rational value
        return type(o) is _PiPoly and self.c == o.c

    def __hash__(self):
        return hash(self.c)

    def __add__(self, o):
        a = self.c
        if type(o) is _PiPoly:
            b = o.c
            if len(a) < len(b):
                a, b = b, a
            return _poly([x + y for x, y in zip(a, b)] + list(a[len(b):]))
        return _PiPoly((a[0] + o,) + a[1:])     # a rational moves c[0] only: the degree stays

    __radd__ = __add__

    def __neg__(self):
        return _PiPoly(tuple([-x for x in self.c]))

    def __sub__(self, o):
        return self + (-o)

    def __rsub__(self, o):
        return (-self) + o

    def __mul__(self, o):
        a = self.c
        if type(o) is _PiPoly:
            b = o.c
            if len(a) + len(b) - 2 > _MAX_DEG:
                raise _Undecided
            out = [0] * (len(a) + len(b) - 1)
            for i, x in enumerate(a):
                for j, y in enumerate(b):
                    out[i + j] += x * y
            return _poly(out)
        return _poly([x * o for x in a])        # by 0 this is the rational 0

    __rmul__ = __mul__

    def __truediv__(self, o):
        if type(o) is _PiPoly or o == 0:        # 1/p(pi) is not in Q[pi]; 1/0 is no number
            raise _Undecided
        return self * (Fraction(1) / o)

    def __rtruediv__(self, o):
        raise _Undecided

    def __pow__(self, n):
        """``n`` an int >= 0. The product of n factors, undecided where it could pass _MAX_DEG or _MAX_BITS."""
        c = self.c
        bits = max([abs(x.numerator).bit_length() + x.denominator.bit_length() for x in c]) + len(c).bit_length()
        if n < 0 or (len(c) - 1) * n > _MAX_DEG or bits * n > _MAX_BITS:
            raise _Undecided
        r = 1
        for _ in range(n):
            r = r * self
        return r

    def __lt__(self, o):
        return _sign(self - o) < 0

    def __gt__(self, o):
        return _sign(self - o) > 0

    def __le__(self, o):
        return _sign(self - o) <= 0

    def __ge__(self, o):
        return _sign(self - o) >= 0


def _poly(c):
    """The value with the coefficient list ``c``: a _PiPoly, or the rational c[0] when no power of pi is left."""
    n = len(c)
    while n > 1 and c[n - 1] == 0:
        n -= 1
    return c[0] if n == 1 else _PiPoly(tuple(c[:n]))


def _sign(v):
    """The sign of a value of Q[pi]: 1, 0 or -1, or _Undecided. A rational's sign is its own. For a _PiPoly, (E)
    bounds each term: c*_PI_LO**k < c*pi**k < c*_PI_HI**k for c > 0 and k >= 1, the other way round for c < 0. The
    sum of the lower bounds is below the value and the sum of the upper bounds above it; a lower sum above 0 is a
    positive value, an upper sum below 0 a negative one, and anything else is undecided (never 0: by (T) a _PiPoly
    is not 0)."""
    if type(v) is not _PiPoly:
        return (v > 0) - (v < 0)
    c = v.c
    lo, hi = (_BAD_LO, _BAD_HI) if PLANT[0] == "pi-enclosure" else (_LO, _HI)
    low = up = c[0]
    for k in range(1, len(c)):
        x = c[k]
        if x > 0:
            low += x * lo[k]
            up += x * hi[k]
        elif x < 0:
            low += x * hi[k]
            up += x * lo[k]
    if low > 0:
        return -1 if PLANT[0] == "pi-sign" else 1
    if up < 0:
        return -1
    raise _Undecided


def _pi_rational(v):
    return PLANT[0] == "pi-rational"


# 16 entries, as TABLE, at a value v = p(pi) of Q[pi] that is not rational (a _PiPoly: p is not constant), then the
# two relations of two values of Q[pi], rational or not. One argument each, from (T) and (E).
PI_TABLE = {
    # (T): p(pi) is transcendental
    'algebraic': lambda v: False,
    # pi is a real number and p has rational coefficients, so p(pi) is real, and a real number is complex
    'complex': lambda v: True,
    # a composite number is an integer, and v is not rational (see 'rational')
    'composite': lambda v: False,
    # an even number is an integer
    'even': lambda v: False,
    # v is real and not 0, so it has a sign; (E) gives it or leaves it undecided (_sign)
    'extended_negative': lambda v: _sign(v) < 0,
    'extended_positive': lambda v: _sign(v) > 0,
    # v is real
    'extended_real': lambda v: True,
    # v is a real number, not an infinity
    'finite': lambda v: True,
    # an imaginary number is a non-zero real multiple of I; v is real
    'imaginary': lambda v: False,
    # an integer is rational
    'integer': lambda v: False,
    # polar: not decided, as in TABLE
    'polar': None,
    # a prime is an integer
    'prime': lambda v: False,
    # a rational number is algebraic (the root of q*t - p), and v is transcendental by (T)
    'rational': _pi_rational,
    # 0 is rational
    'zero': lambda v: False,
    # eq: by (T) two values of Q[pi] are the same number exactly when their polynomials are (_PiPoly.__eq__; a
    # rational and a _PiPoly are never equal; two rationals as in TABLE)
    'eq': lambda a, b: a == b,
    # lt: a < b exactly when b - a, a value of Q[pi], is positive (_sign: exact, or undecided)
    'lt': lambda a, b: _sign(b - a) > 0,
}
assert tuple(PI_TABLE) == BASIS + RELATIONS
# TWO_WAY's definitions are read at a _PiPoly as at a rational, over PI_TABLE. ONE_WAY's two values hold at a
# _PiPoly for the same one-way rules, since it is real: real -> hermitian, extended_real -> commutative.


def _pred(name, table=TABLE):
    """``name`` at a rational value as a function: by TABLE for a basis predicate, by its definition
    (rules.DEFINITIONS, a conjunction or disjunction of basis literals) for a TWO_WAY derived predicate, by ONE_WAY
    for the other three. With ``table=PI_TABLE``: at a _PiPoly."""
    if name in BASIS_SET:
        f = table[name]
        if f is None:       # polar
            raise _Undecided
        return f
    if name in ONE_WAY:
        f = ONE_WAY[name]
        if f is None:       # antihermitian
            raise _Undecided
        return f
    if name not in TWO_WAY:     # a predicate outside the vocabulary (eq and lt are not unary: _formula reads them)
        raise _Undecided
    d = DEFINITIONS[name].strip()
    disj = "|" in d
    lits = []
    for t in d.split("|" if disj else "&"):
        t = t.strip()
        f = table[t.lstrip("!")]
        if f is None:
            raise _Undecided
        lits.append((f, not t.startswith("!")))
    if disj:
        return lambda v: any([f(v) == want for f, want in lits])
    return lambda v: all([f(v) == want for f, want in lits])


def _pi_pred(name):
    """``name`` at a value of Q[pi]: by PI_TABLE at a _PiPoly, as before at a rational."""
    r, p = _pred(name), _pred(name, PI_TABLE)
    return lambda v: p(v) if type(v) is _PiPoly else r(v)


class _NeedPi(_Undecided):
    """The query holds pi outside a function: :func:`witnesses` compiles it again with values in Q[pi]."""


class _Query:
    """One query's compiled form. Lives for one call of :func:`independent`."""
    __slots__ = ("syms", "consts", "probes", "pi")

    def __init__(self, pi=False):
        self.pi = pi        # True: values are in Q[pi] (the second compile of a query that holds pi)
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
        if q.pi:
            b, x = e.args
            if type(b) is Pi and isinstance(x, Rational) and (x.q != 1 or x.p < 0):
                raise _Undecided    # 1/pi, sqrt(pi): outside Q[pi] at every point, so no point is tried
            return _pi_power(fb, fx)

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
    if t is Pi:
        if not q.pi:
            raise _NeedPi
        return lambda pt: _PI
    raise _Undecided        # a function, a Float, an infinity, another named constant, a Wild, a matrix, a non-term


#: the value of the constant pi
_PI = _PiPoly((0, 1))


def _pi_power(fb, fx):
    """A power with values in Q[pi]: an integer power of a rational as in :func:`_term`; of a _PiPoly, a power by an
    int n >= 0 (the product of n factors, 1 for n = 0 since a _PiPoly is not 0). An exponent that is a _PiPoly and a
    negative power of a _PiPoly are not in Q[pi]: undecided."""
    def power(pt):
        b, n = fb(pt), fx(pt)
        if type(n) is _PiPoly or n.denominator != 1:
            raise _Undecided
        n = int(n)
        if type(b) is _PiPoly:
            if n < 0 or n > _MAX_EXP:
                raise _Undecided
            return b ** n
        if abs(n) > _MAX_EXP or (b == 0 and n <= 0):
            raise _Undecided
        if (abs(b.numerator).bit_length() + b.denominator.bit_length()) * abs(n) > _MAX_BITS:
            raise _Undecided
        return b ** n if n >= 0 else Fraction(b) ** n
    return power


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
            rel = PI_TABLE[name] if q.pi else TABLE[name]
            return lambda pt: rel(fa(pt), fb(pt))
        if type(e) is Args:
            raise _Undecided
        pr, ft = _pi_pred(name) if q.pi else _pred(name), _term(e, q, used)
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
    # sympy-boundary: declared symbol facts, the ones the engine's symbol template reads; the table decides each
    lits = [(_pred(str(k)), v) for k, v in sym.assumptions0.items() if v is not None]
    return lambda v: all([f(v) == want for f, want in lits])


_HEAD = (0, 1, -1, 2, -2, Fraction(1, 2), Fraction(-1, 2))
_TAIL = (3, -3, Fraction(3, 2), Fraction(-3, 2), 4, -4, Fraction(1, 3), Fraction(-1, 3), 5, -5, 6, 7, 9, 10, -10,
         Fraction(1, 4), Fraction(5, 2), Fraction(-5, 2), 100, -100)


def _roots(q, n):
    """Per symbol, exact roots of the query's atoms: for a relation the difference of its sides, for a predicate of a
    compound term the term. With the other symbols at 0 and then at 1, the secant through t = 0 and t = 1 gives a
    candidate, kept only if the atom's function is exactly 0 there. Proposes values; decides nothing. Only a
    rational root is proposed: in a query that holds pi the secant can give a value outside Q, which is left out."""
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
                    s = d1 - d0
                    if type(s) is _PiPoly or type(d0) is _PiPoly:   # the secant's root is not rational
                        continue
                    r = Fraction(-d0) / s
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
                try:
                    if own is None or own(v):
                        pool.append(v)
                except _Undecided:
                    # an own assumption without an exact value here (a prime symbol above _MAX_PRIME): not proposed
                    pass
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
        try:
            fa = _formula(assumptions, q)
            fp = _formula(proposition, q)
        except _NeedPi:
            # pi outside a function: compile again with values in Q[pi]. A query without pi never comes here and
            # runs the closures above on rationals only.
            q = _Query(True)
            fa = _formula(assumptions, q)
            fp = _formula(proposition, q)
        skip = PLANT[0] == "skip-own"
        owns = [None if skip else _own(s) for s in q.syms]
    except _Undecided:
        return None
    if not q.syms:
        return None
    if eng is not None:
        # before any point is tried (sa-port-346): a user's method on the engine gets the query as with the switch
        # off, and so does the engine where it ends without a session (the set's memoized INCONSISTENT, or a query
        # over the discovery budget), with its own flag and counters
        if PLANT[0] != "skip-patched" and _patched(eng):
            return None
        if eng._ends_without_session(proposition, assumptions):
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
    # asked last, so only a query that would be certified pays for it: knowledge a user registered may decide the
    # query
    if eng is not None and PLANT[0] != "skip-users" and _users_knowledge(eng):
        return None
    return list(q.syms), yes, no, tried
