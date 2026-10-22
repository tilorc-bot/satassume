"""The templates of sums, products, powers (``satassume.knowledge.templates.core``)
and functions (``satassume.knowledge.templates.functions``) are imported on first use
(``TemplateRegistry.lazy``).  What is loaded depends on what the process has
already done, so the checks that look at ``sys.modules`` run in a fresh
interpreter."""
import subprocess
import sys

import pytest

sympy = pytest.importorskip("sympy")

from sympy import Add, Mul, Symbol  # noqa: E402

from satassume.state.epoch import EPOCH  # noqa: E402
from satassume.knowledge.templates.registry import TemplateRegistry  # noqa: E402


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
CORE, FUNCS = "satassume.knowledge.templates.core", "satassume.knowledge.templates.functions"
x, y, z = (Symbol(n, real=True) for n in "xyz")
assert ask(Q.positive(x), Q.gt(x, y) & Q.positive(y)) is True
assert ask(Q.gt(x, z), Q.gt(x, y) & Q.gt(y, z)) is True
assert CORE not in sys.modules and FUNCS not in sys.modules
# the first Add node loads the templates of sums, not those of functions
assert ask(Q.positive(x + y), Q.positive(x) & Q.positive(y)) is True
assert CORE in sys.modules and FUNCS not in sys.modules
""")


def test_tables_on_first_read_and_no_bounds_without_constants():
    # templates.core builds MUL_TABLE on first read (the module __getattr__),
    # and a relation query without constants never imports lra_bounds.
    _run("""
import sys
from sympy import Q, Symbol
import satassume.knowledge.templates.core as core
assert "MUL_TABLE" not in vars(core)
table = core.MUL_TABLE
assert table == core._table("MUL_TABLE") and table is core.MUL_TABLE
from satassume.sympy_api import ask
x, y, z = (Symbol(n, real=True) for n in "xyz")
assert ask(Q.gt(x, z), Q.gt(x, y) & Q.gt(y, z)) is True
assert ask(Q.positive(x + y), Q.positive(x) & Q.positive(y)) is True
assert ask(Q.positive(x*y), Q.positive(x) & Q.positive(y)) is True
assert "satassume.theories.lra.lra_adapter" in sys.modules
assert "satassume.theories.lra.lra_bounds" not in sys.modules
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
from sympy import Add, exp
from satassume.state.epoch import EPOCH
from satassume.knowledge.templates.registry import registry
CORE, FUNCS = "satassume.knowledge.templates.core", "satassume.knowledge.templates.functions"
WIRING = "satassume.knowledge.templates.wiring"
assert CORE not in sys.modules and FUNCS not in sys.modules
epoch = EPOCH[0]

@registry.register(Add)
def user_add(expr):
    return None

@registry.register(exp)
def user_function(expr):
    return None

assert CORE in sys.modules and FUNCS in sys.modules
# left: the modules declared by class name whose module is not imported
# (sympy.codegen.cfunctions, sympy.physics, sympy.stats), which no node can need yet
assert "sympy.codegen" not in sys.modules and "sympy.physics" not in sys.modules
assert "sympy.stats" not in sys.modules
assert registry._lazy and all(not registry._imported(c) for c, m in registry._lazy)
assert EPOCH[0] > epoch
for cls, user, mod in ((Add, user_add, CORE), (exp, user_function, WIRING + ":exp_log")):
    ts = registry.templates_for(cls)
    own = registry._by_class[cls]
    assert own[-1] is user and len(own) > 1
    assert all(t.__module__ == mod for t in own[:-1])
    assert ts[len(own) - 1] is user
""")


def test_named_classes_load_on_first_use():
    # expm1 and log1p are declared by name: sympy.codegen is not imported
    # by satassume, and the templates load with the first node of the class
    _run("""
import sys
from sympy import Q, Symbol, exp
from satassume.sympy_api import ask
CF = "satassume.knowledge.templates.cfunctions"
x = Symbol('x', real=True)
assert ask(Q.positive(exp(x))) is True
assert "sympy.codegen" not in sys.modules and CF not in sys.modules
from sympy.codegen.cfunctions import expm1
assert CF not in sys.modules
assert ask(Q.real(expm1(x))) is True
assert CF in sys.modules
PH = "satassume.knowledge.templates.physics"
assert "sympy.physics" not in sys.modules and PH not in sys.modules
from sympy.physics.units import meter
assert PH not in sys.modules
assert ask(Q.positive(meter)) is True
assert PH in sys.modules
ST = "satassume.knowledge.templates.stats"
assert "sympy.stats" not in sys.modules and ST not in sys.modules
from sympy.stats import Normal
assert ST not in sys.modules
assert ask(Q.real(Normal('X', 0, 1))) is True
assert ST in sys.modules
""")


def test_user_registration_after_named_module_import_loads_it_first():
    _run("""
import sys
from sympy.codegen.cfunctions import log1p
from satassume.knowledge.templates.registry import registry
CF = "satassume.knowledge.templates.cfunctions"
assert CF not in sys.modules

@registry.register(log1p)
def user_log1p(expr):
    return None

# left: physics and stats (declared by name, sympy.physics and sympy.stats are not imported)
assert CF in sys.modules and [m for c, m in registry._lazy] == ["satassume.knowledge.templates.physics",
                                                                "satassume.knowledge.templates.stats"]
own = registry._by_class[log1p]
assert own[-1] is user_log1p and len(own) > 1
assert own[0].__module__ == "satassume.knowledge.templates.wiring:cfunctions"
""")


def test_named_declaration_covers():
    r = TemplateRegistry()
    from sympy import exp, log
    assert r._covers(exp, ("sympy.functions.elementary.exponential:exp",))
    assert not r._covers(log, ("sympy.functions.elementary.exponential:exp",))
    assert r._covers(log, (Add, "sympy.functions.elementary.exponential:log"))
    assert r._imported(("sympy.core.add:Add",))
    assert not r._imported(("satassume_no_such_module:C",))
