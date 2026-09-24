"""Acceptance battery: the ``refine`` cases of ``tests/refine_v3``, as data.

Filled by the checker agent from ``tests/refine_v3``.  ``BATTERY`` is a list
of tuples ``(expr, assumptions, expected, source)``:

* ``expr`` and ``assumptions`` are what the v3 test passes to ``refine``;
* ``expected`` is the refined expression the test asserts, or ``None``
  when the test asserts the expression stays unchanged (a negative test);
* ``source`` is ``"<module>::<test function>"`` in ``tests/refine_v3``.

``tools/refine_identity_scoreboard.py`` runs it through the dispatcher with
any handler package.  Expressions are built with ``symbols`` of the same
names as in the source test so cases stay readable.
"""
from __future__ import annotations

BATTERY: list = []
