"""What a query needs of the rows (#309): :func:`generator`, which gives
the rules of a function's compiled rows (``_compiled_rows.py``, written by
``tools/compile_rows.py``), and the readers of their texts.

:mod:`._rows` is the language the family modules write rows in, and the
compiler of ``tools/compile_rows.py``; importing it makes the symbols and
the classes of the language (about 2 ms), which :mod:`.wiring` does not
need to register the compiled rows.  :mod:`._rows` imports these names
from here, so a row is compiled and read back by the same code.
"""
from __future__ import annotations

import ast
import operator
from types import MappingProxyType

from sympy import Abs, Integer, S, exp, sqrt

from ._common import Rules

#: what the texts of :func:`._rows.compile_rows` name: the numbers and
#: functions of exact real numbers (``'1/2'``, ``'-1/E'``, ``'exp(-1)'``,
#: ``'-I'``); the constant variables of the terms of a constant
#: (``'Abs(number) - 1'``) are :mod:`._rows`'s, or the constant itself
#: (:func:`constant_value`)
_TEXT_NAMES = MappingProxyType({'E': S.Exp1, 'I': S.ImaginaryUnit, 'pi': S.Pi})
_TEXT_CALLS = MappingProxyType({'Abs': Abs, 'exp': exp, 'sqrt': sqrt})
_TEXT_OPS = MappingProxyType({ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                              ast.Div: operator.truediv, ast.Pow: operator.pow})


def from_text(text, names=_TEXT_NAMES):
    """The SymPy expression of a text of :func:`._rows.compile_rows` (an
    int is an ``Integer``), read with :mod:`ast` and built with SymPy's
    arithmetic as SymPy's parser would build it, but without the parser,
    whose first use costs tens of milliseconds (the generator reads the
    texts when a function is first used); a text it does not read goes to
    ``S``.  ``names`` are the names a text may use."""
    if not isinstance(text, str):
        return S(text)
    try:
        return _read(ast.parse(text, mode='eval').body, names)
    except (KeyError, TypeError, SyntaxError):
        return S(text)


def constant_value(text, c):
    """The term of the constant variable whose text is ``text`` at the
    constant ``c``, a SymPy ``Number``: ``constant_term(text).xreplace({number:
    c})`` (:func:`._rows.constant_term`), computed from the text with ``c``
    for ``number``, so that no term is built (the first sum SymPy builds in
    a process imports ``sympy.tensor``)."""
    names = {'number': c, 'coefficient': c}
    try:
        return _read(ast.parse(text, mode='eval').body, {**_TEXT_NAMES, **names})
    except (KeyError, TypeError, SyntaxError):
        return S(text, locals=names)


def _read(e, names):
    if isinstance(e, ast.Constant) and type(e.value) is int:
        return Integer(e.value)
    if isinstance(e, ast.Name):
        return names[e.id]
    if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.USub):
        return -_read(e.operand, names)
    if isinstance(e, ast.BinOp):
        return _TEXT_OPS[type(e.op)](_read(e.left, names), _read(e.right, names))
    if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and not e.keywords:
        return _TEXT_CALLS[e.func.id](*(_read(a, names) for a in e.args))
    raise TypeError(ast.dump(e))


def _shape_object(shape):
    """A shape of :func:`._rows._shape` with its numbers as SymPy numbers again."""
    return tuple(('value', from_text(s[1])) if s is not None and s[0] == 'value' else s
                 for s in shape)


def _term_object(t):
    """A term of :func:`._rows.compile_rows` with its numbers as SymPy
    numbers again; a term of the constant stays text
    (:func:`._rows.constant_term`, :func:`constant_value`)."""
    if t[0] == 'times':
        return ('times', t[1], from_text(t[2]))
    if t[0] in ('of_constant', 'inner'):
        return t
    return (t[0], from_text(t[1]))


def generator(name: str, arity, terms: tuple, specs: tuple, module: str, schemas=()):
    """The ``gen(R, c)`` that adds the rules ``specs`` (:func:`._rows.compile_rows`);
    ``module`` is the module the registry attributes the template to
    (``TemplateRegistry.lazy``).  ``gen.arity``, ``gen.terms`` (``{n: ((i,
    c), ...)}``, ``c`` a SymPy number again) and ``gen.shifts`` (the ``c``
    of the rows of one argument) tell :func:`.wiring.template` the slots:
    for several numbers of arguments, ``gen(R, n)`` is
    :func:`.functions.nary`'s, and gives the rules of the rows of ``n``
    arguments.

    ``gen.plain`` is false for rows with a shape or a term other than
    ``x + c``: ``gen.specs`` (``{n: rules}``, the rules of
    :func:`._rows.compile_rows` with the numbers of the shapes as SymPy numbers)
    and ``gen.terms`` (the other terms too, :func:`_term_object`) are then
    for the template that matches the node against the shapes and builds
    the terms; ``gen(R, c)`` would add every rule, shaped or not.

    ``gen.schemas`` are the schemas of the rows with a star
    (:func:`._rows._schema`), with their numbers as SymPy numbers again, which
    :func:`.wiring.expand` expands for a node."""
    terms = {n: tuple(_term_object(t) for t in ts) for n, ts in terms}
    specs = dict(specs)
    one = tuple(spec for sp in specs.values() for spec in sp)

    def gen(R: Rules, c) -> None:
        # c: the constant argument (functions._unary) or the number of
        # arguments (functions.nary), which picks the rows for several
        for prem, concl, *_ in specs.get(c, ()) if len(specs) > 1 else one:
            R.rule(list(prem), list(concl))
    gen.__module__ = module
    gen.__name__ = gen.__qualname__ = f'{name}_rows'
    gen.arity = arity
    gen.terms = terms
    gen.shifts = tuple(t[1] for t in terms.get(1, ()) if isinstance(t[0], int))
    gen.specs = {n: tuple((*r[:2], _shape_object(r[2])) if len(r) > 2 else r for r in rs)
                 for n, rs in specs.items()}
    gen.plain = (all(isinstance(t[0], int) for ts in terms.values() for t in ts)
                 and all(len(r) == 2 for r in one))
    gen.schemas = tuple((at_most, tuple(zip(_shape_object(k for k, _ in picks), (g for _, g in picks))), rs)
                        for at_most, picks, rs in schemas)
    return gen
