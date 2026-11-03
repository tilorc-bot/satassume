"""Optional compiled build (docs/performance.md, "Optional compiled build").

Pure Python is the default: without SATASSUME_CYTHON=1 this file changes
nothing.  With it, the unchanged modules in COMPILED are compiled in place
with Cython (installed by hand, not a dependency):

    SATASSUME_CYTHON=1 python setup.py build_ext --inplace

Python then imports the .so next to each .py; delete the .so files to go
back to pure Python, and rebuild after editing a compiled module (a stale
.so shadows the edited .py; tests/test_compiled_build.py checks that).
"""
import os
import re

from setuptools import setup

# knowledge/rules.py stays pure Python: tests/test_layering.py checks that its
# old-name alias keeps the module's own (source) loader.
COMPILED = [
    "satassume/sat/solver.py",
    "satassume/sat/formula.py",
    "satassume/sat/theory.py",
    "satassume/engine.py",
    "satassume/relations.py",
    "satassume/scope.py",
    "satassume/sympy_api.py",
    "satassume/state/memos.py",
    "satassume/state/epoch.py",
    "satassume/knowledge/compile.py",
    "satassume/knowledge/domain.py",
    "satassume/theories/transfer.py",
    "satassume/theories/euf/euf.py",
    "satassume/theories/euf/euf_adapter.py",
    "satassume/theories/lra/lra.py",
    "satassume/theories/lra/lra_adapter.py",
    "satassume/theories/lra/lra_bounds.py",
    "satassume/theories/lra/constfield.py",
]

# Cython turns `1 << len(x)` and `2 ** len(x)` into C arithmetic (len() is a
# Py_ssize_t), which overflows where Python's ints would not.  Refuse any
# shift or pow on a C temporary or C local in the generated code.
_C_INT_OP = re.compile(r"(__pyx_[tv]_\w+\s*<<|<<\s*__pyx_[tv]_\w+|\bpow\([^;]*__pyx_[tv]_\w+)")


def _check_c_int_ops(c_files):
    hits = []
    for path in c_files:
        with open(path) as f:
            hits += [f"{path}:{n}: {line.strip()}" for n, line in enumerate(f, 1)
                     if _C_INT_OP.search(line) and not line.lstrip().startswith(("*", "/*", "#"))]
    if hits:
        raise SystemExit("C integer shift/pow on a Python int (overflows):\n" + "\n".join(hits))


if os.environ.get("SATASSUME_CYTHON") == "1":
    from Cython.Build import cythonize
    build_dir = os.path.join("build", "cython")
    extensions = cythonize(
        COMPILED, build_dir=build_dir, force=True, language_level=3,
        # annotations are documentation here, not C types: `x: float` must
        # stay a Python object (a Fraction), `c: list` must accept a tuple
        compiler_directives={"annotation_typing": False})
    for ext in extensions:
        # heap types: tests monkeypatch methods of cdef classes (solver.pxd)
        ext.define_macros.append(("CYTHON_USE_TYPE_SPECS", "1"))
    _check_c_int_ops([source for ext in extensions for source in ext.sources])
    setup(ext_modules=extensions)
else:
    setup()
