"""Structural rule templates for :mod:`satassume`.

Importing this package registers every template module with
:data:`registry`; the engine then calls ``registry.facts_for(expr)`` for each
expression node it visits.  This package imports SymPy; the core
:mod:`satassume` modules do not.
"""
from . import atoms, core, functions  # noqa: F401  (registration side effects)
from .registry import TemplateRegistry, registry

__all__ = ['TemplateRegistry', 'registry']
