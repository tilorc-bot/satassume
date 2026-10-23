"""The rows of ``Abs``, ``re``, ``im``, ``sign`` and ``conjugate``
(``templates/complex_parts.py``, compiled by ``templates/wiring.py``,
#249): a row without premises, and the family compiled on its own first
use, with ``wiring.AFTER_ROWS``.  Whether each compiled rule is true is
checked at concrete points in ``tests/test_rows_numeric.py``.
"""
import subprocess
import sys

import pytest

pytest.importorskip("sympy")

from sympy import Q, sign  # noqa: E402

from satassume.knowledge.templates import _common  # noqa: E402
from satassume.knowledge.templates._rows import rules, x  # noqa: E402


def test_a_row_without_premises_is_its_conclusion():
    R = _common.Rules()
    rules(sign, (Q.complex(sign(x)), Q.zero(sign(x)) | Q.odd(sign(x))), __name__)(R, None)
    assert sorted(R.rules) == [([], [(1, 'complex', True)]),
                               ([], sorted([(1, 'zero', True), (1, 'odd', True)]))]
    # under a condition, it is the conclusion of a row
    R = _common.Rules()
    rules(sign, Q.real(x) >> (Q.complex(sign(x)) & Q.zero(sign(x))), __name__)(R, None)
    assert sorted(R.rules) == [([(0, 'real', True)], [(1, 'complex', True)]),
                               ([(0, 'real', True)], [(1, 'zero', True)])]
    # a conjunction is what a & b >> c parses to
    with pytest.raises(TypeError, match="not an implication"):
        rules(sign, Q.complex(sign(x)) & Q.zero(sign(x)), __name__)


def test_complex_parts_is_compiled_on_its_own_first_use():
    # parts_of_round_templates comes after the rows of re and im, as it did
    # when functions.py registered both
    code = """
import sys
from sympy import Abs, Q, Symbol, conjugate, floor, im, re, sign
from satassume.knowledge.templates.registry import registry
from satassume.sympy_api import ask
COMPLEX = "satassume.knowledge.templates.complex_parts"
TRIG = "satassume.knowledge.templates.trig"
WIRING = "satassume.knowledge.templates.wiring"
x = Symbol('x')
assert ask(Q.nonnegative(Abs(x)), Q.finite(x)) is True
pending = {m for _, m in registry._lazy}
assert WIRING + ":complex_parts" not in pending and WIRING + ":trig" in pending
# the rows are read compiled: no family module is imported
assert COMPLEX not in sys.modules and TRIG not in sys.modules
for h in (Abs, sign, conjugate):
    assert [t.__module__ for t in registry._by_class[h]] == [WIRING + ":complex_parts"]
for h in (re, im):
    assert [(t.__module__, t.__name__) for t in registry._by_class[h]] == [
        (WIRING + ":complex_parts", h.__name__ + "_templates"),
        (WIRING + ":complex_parts", "parts_of_round_templates")]
assert ask(Q.integer(re(floor(x))), Q.finite(x)) is True
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
