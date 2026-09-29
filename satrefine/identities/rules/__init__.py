"""The rule families (one module per family) and the helpers their tables share.

Each family states its standing facts in an ``ASSUMED`` set (see
:class:`..core.spec.Family`), so a letter carries its assumptions.  A letter
means the same in every family; a family may add facts to a reserved letter
(``n`` even, ``p`` a positive integer), said at its ``ASSUMED`` line, but
never contradict it:

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
