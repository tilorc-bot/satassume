"""Pytest plugin for stage 0 of the fact-lattice plan: the refine scoreboard.

Load it in the pytest subprocesses that ``tools/refine_scoreboard.py`` (on
the ``refine-monorepo`` branch) starts, e.g. from the monorepo worktree::

    PYTHONSAFEPATH=1 \\
    PYTHONPATH=<this dir>:<oracle dir>:<engine root>:.:/work/src/sympy-pin \\
    PYTEST_ADDOPTS="-p facts_scoreboard_plugin" FACTS_SB_MODE=transfer \\
    FACTS_SB_QLOG=/path/queries.jsonl FACTS_SB_INFO=/path/info.txt \\
        python tools/refine_scoreboard.py --backends satassume --junit-dir DIR

(``PYTHONSAFEPATH=1`` stops ``python -m pytest`` from putting the worktree
root, and with it the worktree's old ``satassume``, first on ``sys.path``.)

Environment:

``FACTS_SB_INFO``   file that gets ``satassume.__file__`` and the mode.
``FACTS_SB_MODE``   ``transfer``, ``free``, ``both`` or ``base``: the
                    ``satassume`` backend answers through
                    ``facts_capability.answer(eng, p, a, mode)`` (one Engine
                    and one answer memo per (proposition, assumptions) for
                    the session, like ``sympy_api.ask``); ``"error"``
                    becomes a ``ValueError`` caused by
                    ``InconsistentAssumptions`` like ``sympy_api.ask``.
                    Unset: the backend is untouched.
``FACTS_SB_QLOG``   JSONL file: one line per query of the selected backend
                    (test id, proposition, assumptions, answer or exception,
                    and under a mode how the oracle answered).
"""
from __future__ import annotations

import json
import os

_CURRENT = [""]
_HOW = [None]
_FILES = []


def pytest_configure(config):
    import satassume
    from satrefine import backend

    mode = os.environ.get("FACTS_SB_MODE")
    info = os.environ.get("FACTS_SB_INFO")
    if info:
        with open(info, "a") as f:
            f.write(f"satassume={satassume.__file__} backend={backend.current()} mode={mode}\n")

    if mode:
        from facts_capability import answer
        from satassume.engine import Engine, InconsistentAssumptions

        eng = Engine()
        memo: dict = {}
        verify = os.environ.get("FACTS_SB_VERIFY")
        if verify:
            from satassume import sympy_api
            plain_eng = Engine()
            vout = open(verify, "w")
            _FILES.append(vout)
            seen: set = set()

            def _verify(proposition, assumptions, value):
                # every answer that differs from plain sympy_api.ask is
                # re-asked of SymPy's ask (10 s alarm) and logged
                key = (proposition, assumptions)
                if key in seen:
                    return
                seen.add(key)
                try:
                    plain = sympy_api._ask(proposition, assumptions, plain_eng)
                except ValueError:
                    plain = "error"
                if plain == value:
                    return
                sym = _sympy_answer(proposition, assumptions, 10)
                vout.write(json.dumps({"t": _CURRENT[0], "p": str(proposition), "a": str(assumptions),
                                       "plain": plain, "oracle": value, "sympy": sym}, default=str) + "\n")
                vout.flush()

        def oracle_ask(proposition, assumptions=True):
            key = (proposition, assumptions)
            r = memo.get(key)
            if r is None:
                r = memo[key] = answer(eng, proposition, assumptions, mode)
            value, how = r
            _HOW[0] = how
            if verify:
                _verify(proposition, assumptions, value)
            if value == "error":
                raise ValueError(f"inconsistent assumptions {assumptions}") from InconsistentAssumptions()
            return value

        backend._IMPLEMENTATIONS["satassume"] = oracle_ask
        backend._satassume_ask = oracle_ask      # what _combined_ask calls

    qlog = os.environ.get("FACTS_SB_QLOG")
    if qlog:
        name = backend.current()
        inner = backend._IMPLEMENTATIONS[name]
        out = open(qlog, "w")
        _FILES.append(out)

        def logged(proposition, assumptions=True):
            _HOW[0] = None
            rec = {"t": _CURRENT[0], "p": str(proposition), "a": str(assumptions)}
            try:
                r = inner(proposition, assumptions)
            except Exception as e:  # noqa: BLE001 - logged and re-raised
                rec["r"] = f"raise {type(e).__name__}"
                rec["how"] = _HOW[0]
                out.write(json.dumps(rec) + "\n")
                raise
            rec["r"] = r
            rec["how"] = _HOW[0]
            out.write(json.dumps(rec) + "\n")
            return r

        backend._IMPLEMENTATIONS[name] = logged

        if name == "combined":
            # mark the queries _combined_ask re-asks of SymPy
            sympy_inner = backend._sympy_ask

            def sympy_fallback(proposition, assumptions=True):
                _HOW[0] = "sympy-fallback"
                return sympy_inner(proposition, assumptions)

            backend._sympy_ask = sympy_fallback


def _sympy_answer(p, a, secs):
    import signal
    from sympy.assumptions.ask import ask

    def alarm(*_):
        raise TimeoutError

    old = signal.signal(signal.SIGALRM, alarm)
    signal.alarm(secs)
    try:
        return ask(p, a)
    except TimeoutError:
        return "timeout"
    except ValueError:
        return "error"
    except Exception as e:  # noqa: BLE001 - recorded
        return f"exception {type(e).__name__}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def pytest_runtest_setup(item):
    _CURRENT[0] = item.nodeid


def pytest_unconfigure(config):
    for f in _FILES:
        f.close()
