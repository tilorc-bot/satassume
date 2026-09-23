"""Second, independent implementation of the assumption-driven refine handlers.

Every public module in this package registers one or more entries of
:data:`satrefine._upstream.handlers_dict` when imported; the package is
selected with ``SATREFINE_HANDLERS=handlers_v2``.  Shared helpers live in
:mod:`satrefine.handlers_v2._common`.  Each module's docstring states the
rules it implements and the precondition of every rule; a handler returns
``None`` whenever no rule applies and never returns Python numbers.
"""
