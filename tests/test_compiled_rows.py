"""The templates are registered from the compiled rows
(``templates/_compiled_rows.py``, #249), which must be those of the family
modules: ``tools/compile_rows.py`` writes the file, and this fails when a
row was edited without running it.  ``tests/test_rows_numeric.py`` checks
that every compiled rule is true at concrete points.
"""
import os
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(*args, seed="0"):
    return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "compile_rows.py"), *args],
                          capture_output=True, text=True, timeout=300,
                          env={**os.environ, "PYTHONPATH": ROOT, "PYTHONHASHSEED": seed})


def test_the_compiled_rows_are_up_to_date():
    out = _run("--check")
    assert out.returncode == 0, out.stdout + out.stderr


def test_the_compiled_rows_do_not_depend_on_the_hash_seed():
    # SymPy orders the arguments of And canonically: the file is the same
    # whatever the seed, so it does not churn
    out = _run("--check", seed="12345")
    assert out.returncode == 0, out.stdout + out.stderr


def test_the_compiled_rows_hold_plain_data_only():
    from satassume.knowledge.templates import ROW_FAMILIES, _compiled_rows

    def plain(v):
        if isinstance(v, tuple):
            return all(plain(i) for i in v)
        return type(v) in (str, int, bool)
    assert plain(_compiled_rows.FAMILIES)
    assert [f for f, _ in _compiled_rows.FAMILIES] == [f for f, _ in ROW_FAMILIES]


def test_a_function_this_sympy_may_lack_is_compiled_too():
    # owens_t is new in SymPy 1.15: tools/compile_rows.py compiles its rows
    # with a stand-in where SymPy lacks it, so the file is the same on every
    # SymPy, and wiring.load skips the function there
    from satassume.knowledge.templates import _compiled_rows
    assert "owens_t" in [e[0] for e in dict(_compiled_rows.FAMILIES)["error_functions"]]
