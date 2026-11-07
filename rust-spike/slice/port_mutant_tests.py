"""port_mutant_tests.py NAME [pytest args]: pytest with `lra_backend` built from a Python mutant in port_mutants.PY, for the hook-level tests.
These drive LRATheory directly with payloads the engine doesn't make, so a catch here isn't a catch on the real-engine path."""
import os
import sys
import types

import port_mutants as P

name = sys.argv[1]
old, new = P.PY[name]
path = os.path.join(P.HERE, "lra_backend.py")
text = open(path).read()
assert text.count(old) == 1, name
m = types.ModuleType("lra_backend")
m.__file__ = path
sys.modules["lra_backend"] = m
exec(compile(text.replace(old, new), path, "exec"), m.__dict__)
import pytest  # noqa: E402
sys.exit(pytest.main(sys.argv[2:]))
