"""Print the rows of a function's template, each with the constant it comes from (#249).

    python tools/show_rows.py [NAME ...]

A function's rules are a tuple in its family module (``SIN`` in
``templates/trig.py``): shared constants (``ENTIRE``, ``LINDEMANN``, ...)
and its own rows.  Each row is printed for the function itself, labelled
with the shared constant it comes from, or with the function's tuple.
Without names, every function written in rows is printed.
"""
import sys

from sympy import And, Or


def _side(e):
    return f"({e})" if isinstance(e, (And, Or)) else str(e)


def main(names):
    from satassume.knowledge.templates import trig
    from satassume.knowledge.templates._rows import rows_for
    families = (trig,)
    declared = {f.__name__: (fam, f, table) for fam in families for f, table in fam.ROWS}
    for name in names or declared:
        fam, f, table = declared[name]
        shared = {id(v): k for k, v in vars(fam).items() if k.isupper()}
        own = next(k for k, v in vars(fam).items() if v is table)
        print(name)
        for item in table:
            label = shared.get(id(item), own)
            for row in rows_for(f, item):
                prem, concl = row.args
                print(f"  {label:20} {_side(prem)} >> {_side(concl)}")


if __name__ == "__main__":
    main(sys.argv[1:])
