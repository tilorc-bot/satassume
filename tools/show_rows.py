"""Print the rows of a function's template, each with where it comes from (#249).

    python tools/show_rows.py [NAME ...]

A function's rows are those of its properties (``templates/properties.py``,
labelled with the property), its signature (``signature``) and the rows
of its family module (labelled with the module).  Without names, every
function written in rows is printed.
"""
import sys

from sympy import And, Or


def _side(e):
    return f"({e})" if isinstance(e, (And, Or)) else str(e)


def main(names):
    from satassume.knowledge.templates import trig
    declared = {f.__name__: rs for family in (trig,) for f, rs in family.ROWS}
    for name in names or declared:
        print(name)
        for label, row in declared[name]:
            prem, concl = row.args
            print(f"  {label:18} {_side(prem)} >> {_side(concl)}")


if __name__ == "__main__":
    main(sys.argv[1:])
