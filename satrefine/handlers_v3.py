"""``SATREFINE_HANDLERS=handlers_v3``: an alias of the reference package :mod:`satrefine.reference.v3`.

Importing it imports the reference package and its public modules (in the order
:mod:`satrefine` loads a handler package, so the handlers register as before),
then binds ``satrefine.handlers_v3`` and ``satrefine.handlers_v3.<module>`` in
``sys.modules`` to those same module objects: the old names keep working and no
module is loaded twice.  A source checkout only: the distribution leaves out
:mod:`satrefine.reference` (see ``pyproject.toml``).
"""
import importlib
import pkgutil
import sys

from .reference import v3 as _v3

for _info in pkgutil.iter_modules(_v3.__path__):
    if not _info.name.startswith("_"):
        importlib.import_module(f"{_v3.__name__}.{_info.name}")
for _name, _module in list(sys.modules.items()):
    if _name.startswith(_v3.__name__ + "."):
        sys.modules[__name__ + _name[len(_v3.__name__):]] = _module
sys.modules[__name__] = _v3
