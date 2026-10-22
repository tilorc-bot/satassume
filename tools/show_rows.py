"""Print the rows of a function's template, each with the property it states (#249).

    python tools/show_rows.py [NAME ...]

A family module (``templates/trig.py``, ``templates/hyperbolic.py``)
states its rules as ``for_all`` statements, each under a comment whose
first line is the property's title.  This prints each function's rows,
``f`` replaced by the function, labelled with that title.  Without names,
every function written in rows is printed.
"""
import ast
import inspect
import sys

from sympy import And, Implies, Or


def _side(e):
    return f"({e})" if isinstance(e, (And, Or)) else str(e)


def labels(module):
    """The title of each ``for_all`` statement of ``module``, in order: the
    first line of the comment above it."""
    src = inspect.getsource(module).splitlines()
    calls = sorted((n for n in ast.walk(ast.parse("\n".join(src)))
                    if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "for_all"),
                   key=lambda n: n.lineno)
    out = []
    for c in calls:
        i = c.lineno - 2
        while i >= 0 and src[i].strip().startswith("#"):
            i -= 1
        first = src[i + 1].strip().lstrip("#").strip() if i + 1 < c.lineno - 1 else ""
        out.append(first)
    return out


def main(names):
    import importlib
    from satassume.knowledge.templates import ROW_FAMILIES
    from satassume.knowledge.templates._rows import f, x
    rows = {}
    for name, _ in ROW_FAMILIES:
        family = importlib.import_module(f"satassume.knowledge.templates.{name}")
        names_of = labels(family)
        assert len(names_of) == len(family.RULES), (family.__name__, len(names_of))
        for label, st in zip(names_of, family.RULES):
            for fn in st.functions:
                rows.setdefault(fn.__name__, []).extend(
                    (label, r.xreplace({f(x): fn(x)})) for r in st.rows)
    width = max(len(label) for rs in rows.values() for label, _ in rs)
    for name in names or rows:
        print(name)
        for label, row in rows[name]:
            if isinstance(row, Implies):
                prem, concl = row.args
                row = f"{_side(prem)} >> {_side(concl)}"
            print(f"  {label:{width}}  {row}")


if __name__ == "__main__":
    main(sys.argv[1:])
