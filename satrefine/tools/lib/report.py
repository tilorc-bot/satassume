"""Plain-text tables for the tools' reports."""
from __future__ import annotations


def table(rows, header, right: bool = False) -> None:
    """Print ``rows`` under ``header`` in aligned columns.

    ``right=False``: every column left-aligned, a dashed rule per column.
    ``right=True``: the first column left-aligned, the others right-aligned
    (numbers), one rule across the whole line."""
    widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]

    def line(cells):
        return "  ".join(str(c).rjust(w) if right and i else str(c).ljust(w)
                         for i, (c, w) in enumerate(zip(cells, widths)))
    head = line(header)
    print(head)
    print("-" * len(head) if right else "  ".join("-" * w for w in widths))
    for r in rows:
        print(line(r))
