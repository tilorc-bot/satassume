"""Values at infinities, nan and poles for the test oracles (#247).

The soundness oracles evaluate a node at a concrete point.  At ordinary
finite numbers SymPy's evaluation is used.  Where an infinity, ``nan`` or a
pole is involved, the value comes from the table in
``docs/special-values.md``, coded here (the comments name its rows), and
not from what SymPy evaluates to.  A special point the table has no row
for keeps SymPy's value as a *candidate*: a disagreement found with it is
reported as a candidate, not as a verdict (#247).

:func:`evaluate` returns ``(value, source)``: ``source`` is ``"number"``
(no table row was needed), ``"table"`` (a row decided some node) or
``"candidate"`` (SymPy's value at a special point without a row).
:func:`facts` gives the truth of a predicate at a value that is no finite
number.  ``tests/test_special_values.py`` compares the rows with SymPy.
"""
from sympy import AccumBounds, Abs, Add, Basic, Mul, Pow, S, exp, log, re
from sympy.core.function import Application

_SPECIAL = (S.Infinity, S.NegativeInfinity, S.ComplexInfinity, S.NaN)


class _NoRow(Exception):
    """The table has no row for a node at a special point."""


def is_special(v):
    """``v`` holds an infinity, ``nan`` or ``AccumBounds``."""
    return isinstance(v, Basic) and (v.has(*_SPECIAL) or v.has(AccumBounds))


def directed(d):
    """The directed infinity of direction ``d`` (a nonzero finite number),
    the value of ``t*d`` as real ``t -> +oo`` (V2): ``oo``/``-oo`` for a
    real ``d``, else ``oo*u`` with ``u = d/|d|``."""
    s = _sign(d)
    if s:
        return S.Infinity if s > 0 else S.NegativeInfinity
    if d.is_extended_real is not False or d.is_zero is not False:
        raise _NoRow
    return Mul(S.Infinity, (d/Abs(d)).expand(), evaluate=False)


def direction(v):
    """``d`` of a directed infinity (1 for ``oo``, -1 for ``-oo``), else
    None."""
    if v is S.Infinity:
        return S.One
    if v is S.NegativeInfinity:
        return S.NegativeOne
    if isinstance(v, Mul) and len(v.args) == 2 and S.Infinity in v.args:
        d = v.args[0] if v.args[1] is S.Infinity else v.args[1]
        if not is_special(d) and d.is_number and d.is_extended_real is False:
            return d
    return None


def kind(v):
    """``"num"`` (a finite number), ``"pinf"``, ``"ninf"``, ``"dir"`` (a
    directed infinity off the real line, ``oo*I``), ``"zoo"``, ``"nan"``,
    or None (anything else: ``AccumBounds``, an unevaluated object)."""
    if v is S.NaN:
        return "nan"
    if v is S.Infinity:
        return "pinf"
    if v is S.NegativeInfinity:
        return "ninf"
    if v is S.ComplexInfinity:
        return "zoo"
    if not isinstance(v, Basic):
        return None
    if direction(v) is not None:
        return "dir"
    if not is_special(v) and v.is_number:
        return "num"
    return None


_TRUE = {
    "pinf": {"extended_real", "extended_positive", "extended_nonnegative",
             "extended_nonzero", "positive_infinite", "noninteger"},
    "ninf": {"extended_real", "extended_negative", "extended_nonpositive",
             "extended_nonzero", "negative_infinite", "noninteger"},
    "zoo": set(),
    "dir": set(),
}


def facts(v, pred):
    """Truth of ``pred`` at the value ``v``, no finite number (V1-V3).

    ``nan`` is no number: every predicate is False but ``finite``,
    ``infinite`` and ``commutative`` (None).  An infinity is no complex
    number, so every predicate implying ``complex`` is False; ``infinite``
    and ``commutative`` are True, and ``+oo``/``-oo`` are extended reals
    of their sign.  ``polar`` is not stated."""
    k = kind(v)
    if k == "nan":
        return None if pred in ("finite", "infinite", "commutative") else False
    if k not in _TRUE:
        raise ValueError(f"no special value: {v!r}")
    if pred == "polar":
        return None
    if pred in ("infinite", "commutative"):
        return True
    return pred in _TRUE[k]


def _sign(v):
    """+1/-1 for a nonzero real number, 0 for zero, None otherwise (a
    non-real number, or a sign SymPy cannot decide)."""
    if v.is_zero:
        return 0
    if v.is_extended_real is not True:
        return None
    return 1 if v.is_positive else (-1 if v.is_negative else None)


def _same_direction(d1, d2):
    """``d1/d2`` is a positive real (True), is not (False), or unknown."""
    s = _sign((d1/d2).expand())
    if s is not None:
        return s > 0
    return False if (d1/d2).expand().is_extended_real is False else None


def _add(vals):
    """Rows A1-A3."""
    ks = [kind(v) for v in vals]
    if "nan" in ks:
        return S.NaN                                       # N1
    if None in ks:
        raise _NoRow
    inf = [v for k, v in zip(ks, vals) if k != "num"]
    if not inf:
        raise _NoRow
    if S.ComplexInfinity in inf:
        return S.ComplexInfinity if len(inf) == 1 else S.NaN   # A3
    d = direction(inf[0])
    same = [_same_direction(direction(v), d) for v in inf[1:]]
    if all(same):
        return inf[0]                                      # A1, A2
    if any(_sign((direction(v)/d).expand()) == -1 for v in inf[1:]):
        return S.NaN                                       # A2: oo - oo
    raise _NoRow


def _mul(vals):
    """Rows M1-M3; the finite factors are multiplied first (``c``)."""
    ks = [kind(v) for v in vals]
    if "nan" in ks:
        return S.NaN                                       # N1
    if None in ks:
        raise _NoRow
    inf = [v for k, v in zip(ks, vals) if k != "num"]
    if not inf:
        raise _NoRow
    c = Mul(*[v for k, v in zip(ks, vals) if k == "num"]).expand()
    if c.is_zero:
        return S.NaN                                       # M1
    if c.is_zero is not False:
        raise _NoRow
    if S.ComplexInfinity in inf:
        return S.ComplexInfinity                           # M3
    return directed(Mul(c, *[direction(v) for v in inf]).expand())   # M2


def _pow(b, e):
    """Rows P1-P6."""
    kb, ke = kind(b), kind(e)
    if "nan" in (kb, ke):
        return S.NaN                                       # N1
    if None in (kb, ke):
        raise _NoRow
    if kb == "num" and ke == "num":
        # finite base and exponent, SymPy's value is special: the pole
        if b.is_zero and _sign(e) == -1:
            return S.ComplexInfinity                       # P1
        raise _NoRow
    if ke == "num":
        if e.is_zero:
            return S.One                                   # P2
        se = _sign(e)
        if se is None:
            raise _NoRow
        if se < 0:
            return S.Zero                                  # P3
        if kb == "zoo":
            return S.ComplexInfinity                       # P3
        return directed(Pow(direction(b), e).expand())     # P3
    if ke in ("pinf", "ninf"):
        up = ke == "pinf"
        if kb == "num":
            if b.is_zero:
                return S.Zero if up else S.ComplexInfinity  # P4
            m = Abs(b)
            if m == 1:
                return S.NaN                               # P5
            gt = m > 1
            if gt not in (S.true, S.false):
                raise _NoRow
            big = bool(gt)
            if big != up:
                return S.Zero                              # P4
            return S.Infinity if b.is_positive else S.ComplexInfinity  # P4
        if not up:
            return S.Zero                                  # P6
        return S.Infinity if kb == "pinf" else S.ComplexInfinity  # P6
    raise _NoRow


def _exp(v):
    """Row F1."""
    k = kind(v)
    if k in ("nan", "zoo"):
        return S.NaN                                       # N1, F1
    d = direction(v)
    if d is None:
        raise _NoRow
    s = _sign(re(d))
    if s is None:
        raise _NoRow
    if s < 0:
        return S.Zero
    if s == 0:
        return S.NaN
    return S.Infinity if k == "pinf" else S.ComplexInfinity


def _log(v):
    """Row F2."""
    k = kind(v)
    if k == "nan":
        return S.NaN                                       # N1
    if k == "num" and v.is_zero:
        return S.ComplexInfinity
    if k == "zoo":
        return S.ComplexInfinity
    if direction(v) is not None:
        return S.Infinity
    raise _NoRow


def _abs(v):
    """Row F3."""
    k = kind(v)
    if k == "nan":
        return S.NaN                                       # N1
    if k in ("pinf", "ninf", "zoo", "dir"):
        return S.Infinity
    raise _NoRow


def table_value(func, vals):
    """The table's value of ``func(*vals)``; :class:`_NoRow` if no row."""
    if func is Add:
        return _add(vals)
    if func is Mul:
        return _mul(vals)
    if func is Pow:
        return _pow(*vals)
    if func is exp:
        return _exp(vals[0])
    if func is log and len(vals) == 1:
        return _log(vals[0])
    if func is Abs:
        return _abs(vals[0])
    if isinstance(func, type) and issubclass(func, Application) and S.NaN in vals:
        return S.NaN                                       # N1
    raise _NoRow


def evaluate(expr, assignment, doit=False):
    """``(value, source)`` of ``expr`` at ``assignment`` (see the module
    docstring).  ``doit`` applies ``doit()`` at every node, as
    ``expr.xreplace(assignment).doit()`` does.  Raises what SymPy raises."""
    memo = {}
    assignment = {k: S(v) for k, v in assignment.items()}
    tv, sv, cand = _walk(expr, assignment, doit, memo)
    if cand:
        return sv, "candidate"
    return tv, ("table" if any(r[3] for r in memo.values()) else "number")


def _build(func, args, doit):
    v = func(*args)
    if not (doit and isinstance(v, Basic)) or v.is_Atom:
        return v
    try:
        return v.doit(deep=False)
    except TypeError:  # a doit without ``deep``
        return v.doit()


def _walk(e, asg, doit, memo):
    """(table value, SymPy's value, candidate?) of ``e``; the memo also
    records whether a row decided ``e``."""
    if e in memo:
        return memo[e][:3]
    if e in asg:
        res = (asg[e], asg[e], False, False)
    elif not isinstance(e, Basic) or e.is_Atom or not e.args:
        res = (e, e, False, False)
    else:
        parts = [_walk(a, asg, doit, memo) for a in e.args]
        tvs, svs = [p[0] for p in parts], [p[1] for p in parts]
        sv = _build(e.func, svs, doit)
        if any(p[2] for p in parts):
            res = (sv, sv, True, False)
        else:
            tv = sv if tvs == svs else _build(e.func, tvs, doit)
            if not any(is_special(v) for v in tvs) and not is_special(tv):
                res = (tv, sv, False, False)
            else:
                try:
                    res = (table_value(e.func, tvs), sv, False, True)
                except _NoRow:
                    res = (sv, sv, True, False)
    memo[e] = res
    return res[:3]


def point_value(term, assignment):
    """The value of ``term`` at ``assignment`` for a two-valued oracle,
    which reads SymPy's ``is_*`` of it: on the table's values that are no
    finite number (``oo``, ``-oo``, ``zoo``, ``oo*u``) these agree with
    :func:`facts` (``tests/test_special_values.py``).  A candidate (SymPy's
    value at a special point without a row) has no value such an oracle
    could use: AssertionError."""
    v, source = evaluate(term, assignment)
    assert source != "candidate", (
        f"{term} at {assignment}: no row in docs/special-values.md, SymPy "
        f"gives {v}; add a row with its argument (#247)")
    return v


def same_value(a, b):
    """Value equality of two table values; ``nan`` equals nothing (as in
    ``Eq(nan, nan)``), two directed infinities are equal when their
    directions are (None: unknown)."""
    if a is S.NaN or b is S.NaN:
        return False
    da, db = direction(a), direction(b)
    if da is not None and db is not None:
        return _same_direction(da, db)
    return a == b
