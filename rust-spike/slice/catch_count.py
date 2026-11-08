"""Counts exceptions on their way into the two handlers that turn them into a quiet answer.

`engine.py:1906` (`_build_context`, around `_complete_check`) and `sympy_api.py:1107` (`_consistent`, around
`Engine.verdict`) both catch `Exception`, so a fault in a ported theory or in Rust there looks like a lost answer.
The wrappers only record and re-raise, and the engine is unchanged. `sink` gets one (site, type name, text) per
exception. `Uninterpreted` is kept apart by its type name: it's re-raised at 1904 and is an expected route.
"""
import sys

sink = []
#: relevance.rs (5c8) names the caller it stands in for (`_consistent`); read and cleared on entry, so nested calls don't see it.
NEXT_CALLER = None


def _take_hint():
    global NEXT_CALLER
    h, NEXT_CALLER = NEXT_CALLER, None
    return h


def install():
    from satassume.engine import Engine
    check, verdict = Engine._complete_check, Engine.verdict

    def complete_check(s, lits):
        try:
            return check(s, lits)
        except Exception as e:
            sink.append(("complete_check", type(e).__name__, str(e)[:200]))
            raise

    def counted_verdict(self, assumptions):
        hint = _take_hint()
        try:
            return verdict(self, assumptions)
        except Exception as e:
            caller = hint or sys._getframe(1).f_code.co_name
            sink.append((f"verdict<{caller}", type(e).__name__, str(e)[:200]))
            raise
    Engine._complete_check = staticmethod(complete_check)
    Engine.verdict = counted_verdict
    # `_consistent`'s handler at sympy_api.py:1107 also covers `_formula`, which `verdict` doesn't see.
    from satassume import sympy_api
    formula = sympy_api._formula

    def counted_formula(*a, **k):
        hint = _take_hint()
        try:
            return formula(*a, **k)
        except Exception as e:
            if (hint or sys._getframe(1).f_code.co_name) == "_consistent":
                sink.append(("formula<_consistent", type(e).__name__, str(e)[:200]))
            raise
    sympy_api._formula = counted_formula


def take():
    out = list(sink)
    sink.clear()
    return out
