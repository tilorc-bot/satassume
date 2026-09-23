"""The v3 package must register every key exactly once, from the owning module."""
from __future__ import annotations

import ast
import pathlib

import satrefine.handlers_v3 as package

EXPECTED = {
    "power_exp_log": {"Pow", "exp", "log"},
    "inverse": {"asin", "acos", "atan", "atan2", "asinh", "acosh", "atanh", "acoth", "asech", "acsch"},
    "complex_parts": {"re", "im", "arg", "sign", "Abs", "conjugate", "Mul"},
    "trig": {"sin", "cos", "tan", "cot", "sec", "csc", "sinc"},
    "hyperbolic": {"sinh", "cosh", "tanh", "coth", "sech", "csch"},
    "integer_funcs": {"floor", "ceiling", "frac", "Mod", "Rem"},
    "combinatorial": {"factorial", "binomial", "RisingFactorial", "FallingFactorial", "gamma"},
    "minmax_deltas": {"Min", "Max", "DiracDelta", "KroneckerDelta", "Heaviside"},
    "matrices": {"Determinant", "HadamardProduct", "Inverse", "MatAdd", "MatMul", "MatrixElement", "Trace", "Transpose"},
}


def registered_keys(path: pathlib.Path) -> set[str]:
    keys = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id == "handlers_dict" and isinstance(node.ctx, ast.Store)):
            keys.add(ast.literal_eval(node.slice))
    return keys


def test_each_module_registers_exactly_its_keys():
    pkg = pathlib.Path(package.__file__).parent
    for module, keys in EXPECTED.items():
        path = pkg / f"{module}.py"
        if not path.exists():
            continue  # not written yet
        assert registered_keys(path) == keys, module


def test_no_key_registered_twice():
    pkg = pathlib.Path(package.__file__).parent
    owners: dict[str, str] = {}
    for path in sorted(pkg.glob("*.py")):
        for key in registered_keys(path):
            assert key not in owners, f"{key}: {owners[key]} and {path.name}"
            owners[key] = path.name
