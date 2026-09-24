"""Refine handlers written as identities (data) instead of procedures.

An experiment on one key, ``log``, selected with
``SATREFINE_HANDLERS=handlers_identities``.  The package registers two keys:

* ``log``: two facts about the logarithm and two exponential forms of
  powers and products, composed at import into four rows of
  ``(lhs, rhs, domain)``; the engine in :mod:`._engine` matches a row,
  substitutes, refines the right side, and keeps it only if the
  branch bookkeeping (``floor``, ``im``, ``arg``) collapsed and a rewrite
  ordering strictly decreases;
* ``im``: three simple rules ahead of the vendored handler, which the
  identities need to reduce their bookkeeping.

Every other key falls through to the vendored handlers in
:mod:`satrefine._upstream`, so this package is not a fourth implementation
of the 56 keys.  ``tools/refine_specialize.py`` generates the familiar
conditional rules from these rows by running the engine under a catalog of
assumption profiles, verifies each generated rule numerically, and compiles
the survivors into cheap handlers.  See
``agent-reports/2026-09-24-refine-from-identities.md``.
"""
