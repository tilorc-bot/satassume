"""Print the compiled structural rules an expression gets, in template notation.

    PYTHONPATH=. python tools/dump_rules.py 'x**2' '2*x' 'exp(I*pi*n/2)'

Each expression is parsed with ``sympify`` (``x``, ``y``, ``z`` are plain
symbols, ``n`` and ``m`` integers, ``p`` positive).  The output lists, per
template, what each name stands for and then every rule after constants
have been resolved and subsumed rules dropped, i.e. exactly the clauses
the engine asserts for that node.
"""
import argparse

from sympy import Symbol, sympify

from satassume.templates import registry  # noqa: F401  (registers templates)
from satassume.templates.dsl import show_rules

NAMES = {
    'x': Symbol('x'), 'y': Symbol('y'), 'z': Symbol('z'),
    'n': Symbol('n', integer=True), 'm': Symbol('m', integer=True),
    'p': Symbol('p', positive=True),
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('exprs', nargs='+', help="expressions, e.g. 'x**2'")
    args = ap.parse_args(argv)
    for i, text in enumerate(args.exprs):
        expr = sympify(text, locals=NAMES)
        if i:
            print()
        print(f"### {expr}")
        print(show_rules(expr))


if __name__ == '__main__':
    main()
