"""The rule families (one module per family) and the helpers their tables share.

Each family states its standing facts in an ``ASSUMED`` set (see
:class:`..core.spec.Family`), so a letter carries its assumptions, and every
table is built with ``add_rules(rows, assuming=...)``, whose facts are the
hypotheses of those rows only.  Rows are ``(lhs, rhs)``.  A letter means the
same in every family; a family may add facts to a reserved letter (``n`` even,
``p`` a positive integer), said at its ``ASSUMED`` line, but never contradict
it.  Arbitrary letters get no facts in ``ASSUMED``; an ``add_rules`` block may
state any hypothesis about its rows ("for 0 <= a < d"):

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
``f``, ``g``, ``h``, ``l``      one-off roles, said at their ``ASSUMED`` line (or
                                a short descriptive name when a family needs more)
capitals                        matrices, named for their property (``S``
                                symmetric, ``D`` diagonal, ``O`` orthogonal, ...)
==============================  ================================================
"""
