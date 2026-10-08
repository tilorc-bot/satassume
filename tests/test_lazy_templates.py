"""The templates of sums, products, powers (``satassume.templates.core``)
and functions (``satassume.templates.functions``) are imported on first use
(``TemplateRegistry.lazy``).  What is loaded depends on what the process has
already done, so the checks that look at ``sys.modules`` run in a fresh
interpreter."""
import subprocess
import sys

import pytest

sympy = pytest.importorskip("sympy")

from sympy import Add, Mul, Symbol  # noqa: E402

from satassume.epoch import EPOCH  # noqa: E402
from satassume.templates.registry import TemplateRegistry  # noqa: E402


def _run(code):
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_symbol_only_query_does_not_load_core():
    _run("""
import sys
from sympy import Q, Symbol
from satassume.sympy_api import ask
CORE, FUNCS = "satassume.templates.core", "satassume.templates.functions"
x, y, z = (Symbol(n, real=True) for n in "xyz")
assert ask(Q.positive(x), Q.gt(x, y) & Q.positive(y)) is True
assert ask(Q.gt(x, z), Q.gt(x, y) & Q.gt(y, z)) is True
assert CORE not in sys.modules and FUNCS not in sys.modules
# the first Add node loads the templates of sums, not those of functions
assert ask(Q.positive(x + y), Q.positive(x) & Q.positive(y)) is True
assert CORE in sys.modules and FUNCS not in sys.modules
""")


def test_declared_module_registering_outside_its_classes():
    r = TemplateRegistry()
    r.lazy("satassume_test_lazy_mod", Add)

    def t(expr):
        return None
    t.__module__ = "satassume_test_lazy_mod"
    epoch = EPOCH[0]
    for cls in (Symbol, Mul):
        with pytest.raises(TypeError, match="outside its declared classes"):
            r.register(cls)(t)
    assert r._by_class == {}
    # a class it declared is accepted, as part of the templates in force
    # from the start: no epoch bump
    r.register(Add)(t)
    assert r._by_class == {Add: [t]} and EPOCH[0] == epoch


def test_user_registration_loads_all_builtins_first():
    _run("""
import sys
from sympy import Add, Function
from satassume.epoch import EPOCH
from satassume.templates.registry import registry
CORE, FUNCS = "satassume.templates.core", "satassume.templates.functions"
assert CORE not in sys.modules and FUNCS not in sys.modules
epoch = EPOCH[0]

@registry.register(Add)
def user_add(expr):
    return None

@registry.register(Function)
def user_function(expr):
    return None

assert CORE in sys.modules and FUNCS in sys.modules and not registry._lazy
assert EPOCH[0] > epoch
for cls, user, mod in ((Add, user_add, CORE), (Function, user_function, FUNCS)):
    ts = registry.templates_for(cls)
    own = registry._by_class[cls]
    assert own[-1] is user and len(own) > 1
    assert all(t.__module__ == mod for t in own[:-1])
    assert ts[len(own) - 1] is user
""")
