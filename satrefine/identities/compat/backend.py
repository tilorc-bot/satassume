"""Which ``ask`` answers the refine handlers' questions.

Every handler in :mod:`satrefine` asks predicate questions through
:func:`.upstream.ask`, which delegates to the backend selected
here.  Three backends exist:

``sympy``
    SymPy's own :func:`sympy.assumptions.ask.ask`.  The reference: the
    handlers refine exactly like SymPy's ``refine`` would with the same
    handler logic.
``satassume``
    :func:`satassume.sympy_api.ask` alone.  Out-of-scope queries (relations,
    matrix predicates) and undecided in-scope queries return ``None``, so a
    handler that needs them never fires.  This is the strict measurement of
    the engine: a refine test that passes under ``sympy`` and fails here is
    a satassume gap.  Assumptions that contradict a symbol's declared facts
    raise :class:`satassume.InconsistentAssumptions`, as the engine does.
``combined`` (the default)
    satassume, with SymPy's ``ask`` asked only where satassume has no model
    of the query (see "Routing" below).  While it asks SymPy, three of SymPy's
    ``Q.nonzero`` handlers are guarded against a wrong ``False`` (below),
    which otherwise makes ``Abs(x)`` and ``x**2`` zero for imaginary ``x``.
``union``
    satassume first; every ``None`` (and every inconsistency error) is
    re-asked of SymPy's ``ask``, with the same guard.  The union of both.
    This was ``combined`` until issue #7 showed that 82% of refine's time went
    to these SymPy calls, which answered 10% of the queries they got; it is
    kept for measurements (``tools/ask_fuzz.py``) and comparisons.

Routing (``combined``)
----------------------
satassume answers every query it has a model of.  SymPy is asked only when
satassume said ``None`` and either

* the query is outside satassume's vocabulary:
  :func:`satassume.sympy_api.out_of_scope` reports ``"matrix"`` (a matrix
  predicate, or a predicate on a matrix argument), ``"custom"`` (a predicate
  with no registered clause function) or ``"other"`` (not a Boolean over
  applied predicates); or
* a relation in the query has no theory that interprets it (a bound such as
  a float or an ``AccumBounds``): satassume then drops the whole
  query, including trivial facts such as ``Q.nonnegative(x)`` under
  ``Q.nonnegative(x) & Q.le(x, 1.5)``, which SymPy answers cheaply.
  Irrational constants (``pi/2``, ``sqrt(2)``, ``E``) are bounded LRA
  variables in satassume since its b208af3, and relations are read over
  the extended reals since its #26 (``x < oo`` says ``x`` is extended real
  and not ``+oo``), so such bounds and ``oo`` stay with it.

Relations that satassume's theories do interpret are not re-asked: where the
engine is undecided on them SymPy almost never decides either (28 of 1,678
battery queries, 128 s of SymPy time; ``Q.eq`` alone took 116 s).  In-scope
queries without relations are not re-asked either (31 of 3,989 answered,
several of them unsoundly, e.g. ``Q.zero(y/x)`` under ``Q.zero(x) & Q.zero(y)``).
A satassume error that is not an inconsistency makes the query go to SymPy
too: a backend answers ``None`` rather than crash the refine call.

Assumptions satassume finds inconsistent raise ``ValueError("inconsistent
assumptions ...")``, as SymPy's ``ask`` does for an atom; they are not
re-asked of SymPy, which answers a compound query under them ``True``
(``Q.nonnegative(x) | Q.zero(x)`` under ``Q.positive(x) & Q.negative(x)``), and
the engine asks its conditions whole under this backend (:func:`decides_whole`),
so rows would fire on that (issue #18).

Whole conditions
----------------
satassume decides a compound condition as a whole, case splits included
(``floor(y)`` is a Gaussian integer or infinite, by whether ``y`` is finite,
although neither alternative holds alone), and raises on inconsistent
assumptions instead of calling an ``Or`` true.  Under ``satassume`` and
``combined`` the engine therefore hands each condition whose atoms satassume
can translate to one ``ask`` (:func:`decides_whole`, read through
:data:`..core.hooks.whole`); under ``sympy`` and ``union`` (where SymPy has the
last word on inconsistent assumptions) it decides conditions connective by
connective.

The backend is chosen with :func:`set_backend`, temporarily with
:func:`using`, or at import time from the ``SATREFINE_BACKEND`` environment
variable.  The default is ``combined``.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Callable, Iterator

Ask = Callable[..., "bool | None"]

BACKENDS = ("sympy", "satassume", "combined", "union")
DEFAULT = "combined"
ENV_VAR = "SATREFINE_BACKEND"


def _sympy_ask(proposition: Any, assumptions: Any = True) -> bool | None:
    from sympy.assumptions.ask import ask
    return ask(proposition, assumptions)


def _satassume_ask(proposition: Any, assumptions: Any = True) -> bool | None:
    from satassume.sympy_api import ask
    known, answer = _answered(proposition, assumptions)
    return answer if known else ask(proposition, assumptions)


# --- the guard on SymPy's ``Q.nonzero`` handlers (combined and union) ---------
#
# SymPy's ``Q.nonzero(e)`` means "e is real and nonzero", so ``False`` means
# "zero or not real".  Its handlers for ``Abs``, ``Pow`` and ``Mul`` answer
# ``False`` as soon as an argument is not a real nonzero number, although the
# expression itself can be real and nonzero: ``Abs(x)``, ``x**2`` and ``x*y``
# for imaginary ``x``, ``y``.  ``Q.zero(e)`` is derived as "not nonzero and
# real", so SymPy then calls ``Abs(x)`` and ``x**2`` *zero* for imaginary
# ``x``, and everything built on that inherits it (``exp(I*Abs(x))`` positive,
# ``c**2*X`` the zero matrix).  While the combined backend asks SymPy, these
# three handlers keep every ``True`` and every ``None`` but replace a ``False``
# with an answer that is sound under SymPy's own definition (see
# ``_nonzero_false_checked``).  The ``sympy`` backend stays SymPy's reference
# behaviour.

_guard_on = False
_guard_installed = False


def _nonzero_false_checked(expr: Any, assumptions: Any) -> bool | None:
    """``Q.nonzero(expr)`` for an ``Abs``, ``Pow`` or ``Mul`` on which SymPy said False.

    False only when ``expr`` is provably not real or provably zero (a zero
    factor with all factors finite; a zero base with a positive exponent; the
    ``Abs`` of zero); True when it is real and every part is finite and not zero
    (for ``Pow``: a finite nonzero base and a finite exponent, since
    ``b**e = exp(e*log(b))``; ``Abs`` is real for a finite argument); else None.
    """
    from sympy import Abs, Mul, Pow, Q
    from sympy.assumptions.ask import _ask_recursive as ask_
    if isinstance(expr, Abs):
        (a,) = expr.args
        if ask_(Q.zero(a), assumptions):
            return False
        if ask_(Q.zero(a), assumptions) is False and ask_(Q.finite(a), assumptions):
            return True
        return None
    real = ask_(Q.real(expr), assumptions)
    if real is False:
        return False
    if isinstance(expr, Pow):
        b, e = expr.base, expr.exp
        if ask_(Q.zero(b), assumptions) and ask_(Q.positive(e), assumptions):
            return False
        parts = [b]
        finite = [b, e]
    elif isinstance(expr, Mul):
        parts = finite = list(expr.args)
        if (any(ask_(Q.zero(p), assumptions) for p in parts)
                and all(ask_(Q.finite(p), assumptions) for p in finite)):
            return False
    else:
        return None
    if (real and all(ask_(Q.zero(p), assumptions) is False for p in parts)
            and all(ask_(Q.finite(p), assumptions) for p in finite)):
        return True
    return None


# SymPy's ``Q.extended_real`` handler for ``Pow`` is the closure of the extended
# reals, so a root of a negative number is called extended real:
# ``ask(Q.extended_real(sqrt(z)), Q.negative(z))`` is True.  While the combined
# backend asks SymPy, a ``True`` for a power is kept only for an integer
# exponent, or an extended nonnegative base and a real exponent
# (``_extended_real_true_checked``); otherwise it becomes None.  Rows stated over
# the extended reals (``conjugate(a) -> a`` if ``Q.extended_real(a)``) rely on it
# when satassume leaves the query open (a relation against a float).

def _extended_real_true_checked(expr: Any, assumptions: Any) -> bool | None:
    """``Q.extended_real(b**e)`` where SymPy's closure said True: True for an integer
    ``e``, or an extended nonnegative ``b`` and a real ``e``; else None."""
    from sympy import Q
    from sympy.assumptions.ask import _ask_recursive as ask_
    b, e = expr.base, expr.exp
    if ask_(Q.integer(e), assumptions):
        return True
    if ask_(Q.extended_nonnegative(b), assumptions) and ask_(Q.real(e), assumptions):
        return True
    return None


def _install_guard() -> None:
    global _guard_installed
    from sympy import Abs, Mul, Pow, Q
    dispatcher = Q.nonzero.handler
    for cls in (Abs, Pow, Mul):
        original = dispatcher.funcs[(cls,)]

        def guarded(expr: Any, assumptions: Any, _original: Any = original) -> bool | None:
            answer = _original(expr, assumptions)
            if answer is False and _guard_on:
                return _nonzero_false_checked(expr, assumptions)
            return answer
        dispatcher.funcs[(cls,)] = guarded
    dispatcher._cache.clear()
    extended = Q.extended_real.handler
    original_ext = extended.funcs[(Pow,)]

    def guarded_ext(expr: Any, assumptions: Any) -> bool | None:
        answer = original_ext(expr, assumptions)
        if answer is True and _guard_on:
            return _extended_real_true_checked(expr, assumptions)
        return answer
    extended.funcs[(Pow,)] = guarded_ext
    extended._cache.clear()
    _guard_installed = True


def _guarded_sympy_ask(proposition: Any, assumptions: Any = True) -> bool | None:
    global _guard_on
    if not _guard_installed:
        _install_guard()
    previous, _guard_on = _guard_on, True
    try:
        return _sympy_ask(proposition, assumptions)
    finally:
        _guard_on = previous


def _union_ask(proposition: Any, assumptions: Any = True) -> bool | None:
    from satassume import InconsistentAssumptions
    try:
        answer = _satassume_ask(proposition, assumptions)
    except ValueError as e:
        # satassume.sympy_api.ask re-raises InconsistentAssumptions as a
        # ValueError; SymPy then gets the last word on whether to raise.
        if not isinstance(e.__cause__, InconsistentAssumptions):
            raise
        answer = None
    if answer is None:
        answer = _guarded_sympy_ask(proposition, assumptions)
    return answer


# --- routing (combined backend) ----------------------------------------------

class _NoTheory(Exception):
    """A relation in the query that no theory of satassume interprets."""


class _FlagUninterpreted:
    """The default engine, except that a relation no theory interprets raises
    :class:`_NoTheory` instead of ``Uninterpreted``, which
    :func:`satassume.sympy_api.ask` would turn into a plain ``None``."""

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    def __getattr__(self, name: str) -> Any:
        return getattr(self._engine, name)

    def ask(self, *args: Any, **kwargs: Any) -> bool | None:
        from satassume.relations import Uninterpreted
        try:
            return self._engine.ask(*args, **kwargs)
        except Uninterpreted as e:
            raise _NoTheory(str(e)) from e

    def is_(self, *args: Any, **kwargs: Any) -> bool | None:
        from satassume.relations import Uninterpreted
        try:
            return self._engine.is_(*args, **kwargs)
        except Uninterpreted as e:
            raise _NoTheory(str(e)) from e


def route(proposition: Any, assumptions: Any = True) -> tuple["bool | None", str | None]:
    """satassume's answer, and why SymPy should be asked instead.

    Returns ``(answer, reason)``.  ``reason`` is None when satassume's answer
    stands, including an undecided ``None``.  Otherwise the answer is None and
    ``reason`` says why satassume has no model of the query:

    * ``"matrix"``, ``"custom"``, ``"other"`` or ``"relation"``: the category
      of the part of the query satassume cannot translate (``Unsupported``
      from :func:`satassume.sympy_api.to_formula`, the same test with which
      ``sympy_api.ask`` returns None without touching the engine).
      ``"relation"`` here means a relation satassume cannot even translate
      (a relation over matrices, a wrong arity, or an engine without
      theories), not a relation as such;
    * ``"no-theory"``: the query translates, but no theory interprets one of
      its relations;
    * ``"inconsistent"``: satassume found the assumptions inconsistent (the
      combined backend raises);
    * ``"error"``: satassume raised anything else.

    Translation is checked on the proposition and the assumptions separately,
    so every out-of-scope part is found, not only the first category
    ``out_of_scope`` would report (it reports ``"relation"`` before
    ``"matrix"``, although satassume models relations).
    """
    from satassume import InconsistentAssumptions
    from satassume.sympy_api import Unsupported, ask, default_engine, to_formula
    try:
        engine = default_engine()
        relations = bool(engine.relation_specs)
        to_formula(proposition, relations)
        if assumptions is not True:
            to_formula(assumptions, relations)
    except Unsupported as e:
        return None, e.category
    except Exception:  # noqa: BLE001 - a backend answers None, it does not crash
        return None, "error"
    try:
        return ask(proposition, assumptions, engine=_FlagUninterpreted(engine)), None
    except _NoTheory:
        return None, "no-theory"
    except ValueError as e:
        if isinstance(e.__cause__, InconsistentAssumptions):
            return None, "inconsistent"
        return None, "error"
    except Exception:  # noqa: BLE001
        return None, "error"


def _combined_ask(proposition: Any, assumptions: Any = True) -> bool | None:
    known, answer = _answered(proposition, assumptions)
    if known:
        return answer
    answer, reason = route(proposition, assumptions)
    if reason is None:
        return answer
    if reason == "inconsistent":
        raise ValueError(f"inconsistent assumptions {assumptions}")
    if reason == "error":
        try:
            return _guarded_sympy_ask(proposition, assumptions)
        except Exception:  # noqa: BLE001 - neither engine takes this query
            return None
    return _guarded_sympy_ask(proposition, assumptions)


_IMPLEMENTATIONS: dict[str, Ask] = {
    "sympy": _sympy_ask,
    "satassume": _satassume_ask,
    "combined": _combined_ask,
    "union": _union_ask,
}


def _validate(name: str) -> str:
    if name not in _IMPLEMENTATIONS:
        raise ValueError(f"unknown satrefine backend {name!r}; expected one of {BACKENDS}")
    return name


_current: str = _validate(os.environ.get(ENV_VAR, DEFAULT))


def current() -> str:
    """Name of the selected backend."""
    return _current


def decides_whole(condition: Any, assumptions: Any = True) -> bool:
    """Whether the selected backend decides ``condition`` in one ``ask``
    (:data:`..core.hooks.whole`): the backend is ``satassume`` or ``combined``
    and satassume itself answers the query (:func:`route` gives no reason to
    ask SymPy, or finds the assumptions inconsistent).  Otherwise (a matrix or
    custom predicate, or a relation whose bound no theory interprets, such as
    a float, in the condition or the assumptions) the engine decides the
    condition connective by connective, so satassume still answers the parts
    it can, and SymPy, which the ``combined`` backend asks for the rest, never
    gets a compound condition: it calls an ``Or`` true under inconsistent
    assumptions, and its relation ``ask`` is unsound at infinity."""
    return _current in ("satassume", "combined") and _satassume_answers(condition, assumptions)


@lru_cache(maxsize=16384)
def _satassume_answers(condition: Any, assumptions: Any) -> bool:
    answer, reason = route(condition, assumptions)
    if reason is None:     # the engine asks this next (prove._whole): answered already
        _routed[0] = (condition, assumptions, answer)
    return reason in (None, "inconsistent")


_routed: list = [None]
"""``(proposition, assumptions, answer)`` of the last query :func:`decides_whole`
found satassume answering: the ``ask`` of the same objects that follows it
takes the answer instead of asking satassume a second time."""


def _answered(proposition: Any, assumptions: Any) -> tuple[bool, Any]:
    routed = _routed[0]
    if routed is not None and routed[0] is proposition and routed[1] is assumptions:
        _routed[0] = None
        return True, routed[2]
    return False, None


def set_backend(name: str) -> None:
    """Select the backend for all following refine calls."""
    global _current
    _current = _validate(name)
    _satassume_answers.cache_clear()


Observer = Callable[[Any, Any, str, "bool | None"], None]
observers: list[Observer] = []
"""Callables told about every answered query: ``(proposition, assumptions,
backend name, answer)``.  The test suite uses this to count out-of-scope
queries per test."""


def ask(proposition: Any, assumptions: Any = True) -> bool | None:
    """Answer with the selected backend."""
    answer = _IMPLEMENTATIONS[_current](proposition, assumptions)
    for observe in observers:
        observe(proposition, assumptions, _current, answer)
    return answer


@contextmanager
def using(name: str) -> Iterator[None]:
    """Select ``name`` for the duration of a ``with`` block."""
    previous = _current
    set_backend(name)
    try:
        yield
    finally:
        set_backend(previous)
