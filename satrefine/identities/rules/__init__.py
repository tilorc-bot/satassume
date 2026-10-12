"""The rule families (one module per family) and the helpers their tables share.

A family module holds rows only: its symbols, its tables and, when it needs
one, ``ASSUMED``.  Which handlers serve which key is :mod:`..wiring` (derived
from the rows for a family of rule rows only).

Every table is built with ``add_rules(assume, rows)``, and a block's facts
(``set()`` for none) are stated where its rows are: ``assume`` holds the
facts about the letters the block uses ("for k a nonzero integer", "for 0 <=
a < d"), each added to the condition of every row of the block whose left
side holds all its variables.  Rows are ``(lhs, rhs)``.  A letter used by a
few blocks has its facts repeated in each, so every block reads on its own.
``ASSUMED`` (see :class:`..core.spec.Family`) is for what a block cannot
state or should not repeat: facts about a letter that runs through many of
the family's blocks, and definitions ``Eq(g, e1) | Eq(g, e2)``, which expand
a row into one row per form (the facts about the letters of those forms stay
in ``ASSUMED`` too).  A module without ``ASSUMED`` has no standing facts.

Letters are usually named as below (a block may narrow one: ``n`` even, ``p`` a
positive integer), as a reading aid only: a letter's facts are always stated, in
its block or in ``ASSUMED``, never implied by its name.

==============================  ================================================
``x``, ``y``, ``z``, ``w``      arbitrary values: no facts
``a``, ``b``, ``c``, ``e``,     arbitrary, in their usual roles (base, exponent,
``r``                           coefficient, rest of a sum or product): no facts
``i``, ``j``                    indices: no facts of their own
``t``, ``s``                    real
``u``                           extended real (real or +-oo)
``n``, ``m``                    integer
``k``                           nonzero integer
``p``                           positive
``q``                           negative
``d``                           nonzero
``v``                           imaginary
``zero``, ``one``, ``inf``,     a symbol standing for one value (0, 1, +oo, -oo)
``ninf``
``f``, ``g``, ``h``, ``l``      one-off roles, said where their facts are stated (or
                                a short descriptive name when a family needs more)
capitals                        matrices, named for their property (``S``
                                symmetric, ``D`` diagonal, ``O`` orthogonal, ...)
==============================  ================================================
"""
