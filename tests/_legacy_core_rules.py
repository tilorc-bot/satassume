"""A verbatim copy of ``ipi_rules`` from ``satassume/templates/core.py`` at
876f37d, before it became a table (issue #97, P6).  Test-only:
``tests/test_template_tables.py`` compares the clauses the table emits
with the clauses this function emits.  The copies of ``_pow_rules`` and
``_mul_rules`` went with ``POW_TABLE`` and ``MUL_TABLE`` (#294, #299: the
rows of Pow and Mul are checked by ``tests/test_rows_numeric.py`` and
``tests/test_rows_baseline.py``).  Do not edit it to follow a later rule
change; change the test's reference instead (``git show
876f37d:satassume/templates/core.py``)."""


def ipi_rules(rule, c, iS, N):
    """Rules for ``node == exp(I*pi*c*s)``: a root of unity when ``s`` is an
    integer, on the unit circle when ``s`` is real.  ``iS`` is the slot of
    ``s`` (None: ``s == 1``)."""
    if iS is None:
        if c.is_integer:
            rule([], (N, 'odd', True))
            rule([], (N, 'positive' if c.p % 2 == 0 else 'negative', True))
        elif c.q == 2:
            rule([], (N, 'imaginary', True))
            rule([], (N, 'algebraic', True))
        else:
            for lit in ((N, 'algebraic', True), (N, 'extended_real', False),
                        (N, 'imaginary', False), (N, 'zero', False)):
                rule([], lit)
        return
    rule([(iS, 'integer', True)], (N, 'algebraic', True))
    rule([(iS, 'real', True)], (N, 'complex', True))
    rule([(iS, 'real', True)], (N, 'zero', False))
    if c.is_integer:
        rule([(iS, 'integer', True)], (N, 'odd', True))
        if c.p % 2 == 0:
            rule([(iS, 'integer', True)], (N, 'positive', True))
        else:
            rule([(iS, 'even', True)], (N, 'positive', True))
            rule([(iS, 'odd', True)], (N, 'negative', True))
            rule([(iS, 'integer', True), (N, 'positive', True)], (iS, 'even', True))
            rule([(iS, 'integer', True), (N, 'negative', True)], (iS, 'odd', True))
    elif c.q == 2:
        rule([(iS, 'even', True)], (N, 'odd', True))
        rule([(iS, 'odd', True)], (N, 'imaginary', True))
