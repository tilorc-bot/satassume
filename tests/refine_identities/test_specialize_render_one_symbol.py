"""Request from "defs" (generator): a generated module whose rules use one
symbol does not import.

:func:`._specialize.render_module` writes ``x, = symbols('x')``, but
``symbols('x')`` returns a ``Symbol``, not a tuple, so the import raises
``TypeError: cannot unpack non-iterable Symbol object`` and with it the
whole ``generated`` package (every family's table).  Seen when
``integer_funcs``' table was ``frac(x) -> 0`` alone; it now has more
symbols.  Wanted: ``symbols('x,')`` (or ``(x,) = symbols('x',
seq=True)``).
"""
from __future__ import annotations

from sympy import Q, S, frac, symbols

from satrefine.handlers_identities._specialize import render_module

x = symbols('x')


def test_render_module_with_one_symbol_imports():
    source = render_module("demo", [(frac(x), S.Zero, Q.integer(x))], ["frac"])
    source = source.replace("generated_handlers as handlers_dict", "generated_handlers as _unused")
    namespace: dict = {"handlers_dict": {}}
    exec(compile(source.replace("\nhandlers_dict[", "\n_registered = handlers_dict["), "demo", "exec"),
         namespace)
    assert namespace["RULES"][0][0] == frac(x)
