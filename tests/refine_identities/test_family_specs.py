"""Families as specs (:mod:`satrefine.identities.core.spec`): importing a family
registers nothing, :func:`satrefine.identities.load` registers every ``SPEC``,
and every row a family's handlers use is one of the rows its ``SPEC`` states
(``facts``, ``rules``), derived from them (``derive(facts, exp_forms)``), or a
stated row over a generic head (an undefined function such as ``G``) with the
key's head put in (``integer_funcs.MOD_FACTS``)."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest
from sympy import sympify
from sympy.core.function import UndefinedFunction

from satrefine._upstream import handlers_dict
from satrefine.identities import families, family_module_name, family_modules
from satrefine.identities.core.spec import Family, Identities, Rules, build
from satrefine.identities.rules._tables import derive


def test_importing_a_family_registers_nothing():
    """Re-import every family module fresh (in a subprocess, after ``load``):
    ``handlers_dict`` and the range rows stay as they are."""
    code = textwrap.dedent(f"""
        import importlib, sys
        import satrefine
        from satrefine._upstream import handlers_dict
        from satrefine.identities.rules import _simple
        before = {{k: id(v) for k, v in handlers_dict.items()}}
        ranges = {{k: list(v) for k, v in _simple.RANGES.items()}}
        names = {[family_module_name(f) for f in families()]!r}
        for name in names:
            del sys.modules[name]
        for name in names:
            mod = importlib.import_module(name)
            assert not hasattr(mod, "handlers_dict"), name
        assert {{k: id(v) for k, v in handlers_dict.items()}} == before
        assert {{k: list(v) for k, v in _simple.RANGES.items()}} == ranges
        print("ok")
    """)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in sys.path if p))
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=600)
    assert out.returncode == 0 and out.stdout.strip() == "ok", out.stderr[-2000:]


def _norm(row) -> tuple:
    return tuple(sympify(t) for t in row if t is not None)


def _parts(value) -> tuple:
    return value if isinstance(value, tuple) else (value,)


@pytest.mark.parametrize("module", family_modules(), ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_handler_rows_are_stated_or_derived(module):
    spec = module.SPEC
    assert isinstance(spec, Family)
    stated = [_norm(r) for r in [*spec.facts, *spec.rules]]
    allowed = set(stated) | {_norm(r) for r in derive([f for f in spec.facts if len(f) == 3], spec.exp_forms)}
    generic = [r for r in stated if isinstance(r[0].func, UndefinedFunction)]
    for key, value in spec.handlers.items():
        for part in _parts(value):
            assert isinstance(part, (Rules, Identities)), key
            for row in map(_norm, part.rows):
                if row in allowed:
                    continue
                head = row[0].func
                assert any(tuple(t.replace(g[0].func, head) for t in g) == row for g in generic), \
                    f"{key}: {row} is neither stated nor derived in {module.__name__}.SPEC"


@pytest.mark.parametrize("module", family_modules(), ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_registered_handlers_are_the_spec(module):
    """``load`` registered each key of the spec with handlers of the spec's rows;
    a part named twice is one handler object; a one-part key is that part's handler."""
    built = build(module.SPEC)
    for key, value in module.SPEC.handlers.items():
        live, fresh = handlers_dict[key], built[key]
        if isinstance(value, tuple) and len(value) > 1:
            assert [p.rows for p in live.parts] == [p.rows for p in fresh.parts], key
        else:
            assert live.rows == fresh.rows and live.kind == fresh.kind, key
    parts = {}
    for key, value in module.SPEC.handlers.items():
        live = handlers_dict[key]
        for i, part in enumerate(_parts(value)):
            obj = live.parts[i] if len(_parts(value)) > 1 else live
            assert parts.setdefault(part, obj) is obj, key
