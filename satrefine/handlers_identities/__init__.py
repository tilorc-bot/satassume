"""Refine handlers written as tables of identities and rules.

Select with ``SATREFINE_HANDLERS=handlers_identities``.  Every public module
in this package is imported by :mod:`satrefine` and registers its keys into
``satrefine._upstream.handlers_dict``; keys no module registers fall through
to the vendored handlers.  Infrastructure (underscore modules):

``_dispatch``   the driver: the vendored ``refine`` with re-refinement after
                auto-evaluation and a firing cap (:class:`RefineLoopError`);
                importing this package rebinds ``satrefine.refine`` to it
                (the attribute on the partially initialized ``satrefine``
                module is replaced during ``_load_handlers``), so
                ``from satrefine import refine`` and every tool get it;
``_engine``     tables: ``identity_handler`` (rows ``(lhs, rhs, domain)``
                whose bookkeeping must collapse) and ``rule_handler`` (rows
                ``(lhs, rhs, hypothesis)``), the pattern forms, ``derive``;
``_wraps``      the branch bookkeeping (``principal``, ``sawtooth``,
                ``reflect_half``, ``reflect_full``, ``fractional``);
``_simple``     the simple rules (``re``/``im``/``arg``/``Abs`` of
                exponentials, logarithms and products; ``floor`` of a
                bounded head; ``Piecewise`` branches under their conditions),
                registered here before the family modules load so a family
                that registers one of those keys overrides and chains to them;
``_specialize`` generation of conditional rules from identity rows under
                assumption profiles, numeric verification, compilation;
``generated/``  the generated rule tables, one module per family, used by
                the dispatcher when ``SATREFINE_IDENTITIES=generated`` (the
                default); ``live`` runs the identity rows instead.

A family module declares its tables under the names the scoreboard counts:
``FACTS`` (identity rows about the family's own functions), ``EXP_FORMS``
(exponential forms of other heads, reusable), ``RULES`` (plain conditional
rows) and ``SIMPLE_RULES`` (rows, or an int for procedural simple rules),
and registers with literal ``handlers_dict['key'] = handler`` statements.
It may also declare ``CATALOG`` (the assumption profiles the generator
tries per variable; see ``_specialize.CATALOG``) and ``EDGE_POINTS``
(values every generated rule is checked at, in addition to 0, 1, -1, I,
-I: the family's branch-cut points).
"""
from __future__ import annotations

import sys

from . import _dispatch, _simple
from .._upstream import handlers_dict

_satrefine = sys.modules.get("satrefine")
if _satrefine is not None:
    _satrefine.refine = _dispatch.refine

_simple.install(handlers_dict)

from . import generated  # noqa: E402  (registers the generated tables; used when SATREFINE_IDENTITIES=generated)
