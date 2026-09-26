"""The matrix patterns of the matcher (expected to change): a hook for :mod:`..core.match`.

Pattern forms:

``Z`` a ``MatrixSymbol``
    binds a plain ``MatrixSymbol`` only, and its shape symbols bind that
    matrix's shape; ``Z + R``, ``HadamardProduct(Z, R)`` bind one atom
    term and the rest (the rest binds ``R`` with its shape); ``c*Z`` over a
    ``MatMul`` binds one scalar factor and the product of the others;
    a ``MatMul`` of matrix factors (at the top of a left side) matches any
    run of adjacent factors, the right side replaces the run and the other
    factors stay in order, simplified with ``doit(deep=False)``;

Importing this module installs :func:`match_matrix` in :data:`..core.hooks.match`,
``MatrixExpr`` as a non-scalar head (:data:`..core.hooks.non_scalar`: ``MatAdd``
and ``MatMul`` are ``Add`` and ``Mul`` subclasses) and ``MatAdd``,
``HadamardProduct`` as commutative heads (:data:`..core.hooks.commutative`);
:mod:`satrefine.identities` imports it.
"""
from __future__ import annotations

from typing import Any, Iterator

from sympy.matrices.expressions import HadamardProduct, MatAdd, MatMul, MatrixExpr, MatrixSymbol

from ..core import hooks
from ..core.match import REBUILD, Binding, _bind, _match_seq


def _is_matrix(e: Any) -> bool:
    return isinstance(e, MatrixExpr)


def _bind_matrix(b: Binding, pattern: Any, target: Any) -> Binding | None:
    """Bind a ``MatrixSymbol`` pattern to a matrix expression and its shape symbols."""
    if not _is_matrix(target):
        return None
    nb = _bind(b, pattern, target)
    for dim, size in zip(pattern.shape, target.shape):
        if nb is None:
            return None
        nb = _bind(nb, dim, size) if dim.is_Symbol else (nb if dim == size else None)
    return nb


def match_matrix(pattern: Any, target: Any, assumptions: Any, b: Binding, top: bool) -> Iterator[Binding] | None:
    """The bindings of a matrix pattern, or ``None`` when ``pattern`` is none of the
    matrix forms (the generic matcher goes on)."""
    if isinstance(pattern, MatrixSymbol):
        return _matrix_symbol(pattern, target, b)
    if isinstance(pattern, (MatAdd, HadamardProduct)) and len(pattern.args) == 2 \
            and all(isinstance(a, MatrixSymbol) for a in pattern.args):
        return _atom_and_rest(pattern, target, b)
    if isinstance(pattern, MatMul):
        scalars = [a for a in pattern.args if not _is_matrix(a)]
        matrices = [a for a in pattern.args if _is_matrix(a)]
        if len(scalars) == 1 and scalars[0].is_Symbol and len(matrices) == 1 \
                and isinstance(matrices[0], MatrixSymbol):
            return _scalar_factor(scalars, matrices, target, b)
        if not scalars and isinstance(target, MatMul):
            return _run(matrices, target, assumptions, b, top)
    return None


def _matrix_symbol(pattern: Any, target: Any, b: Binding) -> Iterator[Binding]:
    """A plain matrix atom."""
    if isinstance(target, MatrixSymbol):
        nb = _bind_matrix(b, pattern, target)
        if nb is not None:
            yield nb


def _atom_and_rest(pattern: Any, target: Any, b: Binding) -> Iterator[Binding]:
    """``Z + R``, ``HadamardProduct(Z, R)``: one atom term and the rest."""
    if not isinstance(target, pattern.func):
        return
    # the pattern's argument order is canonical, not the author's, so either
    # symbol may be the atom and the other the rest
    for atom, rest_sym in (pattern.args, pattern.args[::-1]):
        for k, t in enumerate(target.args):
            if not isinstance(t, MatrixSymbol):
                continue
            others = target.args[:k] + target.args[k + 1:]   # by position: an equal copy stays
            if not others:
                continue                                        # a one-term sum has no rest
            rest = others[0] if len(others) == 1 else pattern.func(*others)
            nb = _bind_matrix(b, atom, t)
            nb = _bind_matrix(nb, rest_sym, rest) if nb is not None else None
            if nb is not None:
                yield nb


def _scalar_factor(scalars: list, matrices: list, target: Any, b: Binding) -> Iterator[Binding]:
    """``c*Z``: a scalar factor and the rest."""
    if not isinstance(target, MatMul):
        return
    for k, f in enumerate(target.args):
        if _is_matrix(f):
            continue
        others = target.args[:k] + target.args[k + 1:]
        rest = others[0] if len(others) == 1 else MatMul(*others)
        nb = _bind(b, scalars[0], f)
        nb = _bind_matrix(nb, matrices[0], rest) if nb is not None else None
        if nb is not None:     # the right side in canonical form (scalars in front, combined)
            yield {**nb, REBUILD: (lambda r: r.doit(deep=False) if isinstance(r, MatrixExpr) else r)}


def _run(matrices: list, target: Any, assumptions: Any, b: Binding, top: bool) -> Iterator[Binding]:
    """A ``MatMul`` of matrix factors: a run of adjacent factors."""
    k = len(matrices)
    T = list(target.args)
    for i in range(len(T) - k + 1):
        run = T[i:i + k]
        if not all(_is_matrix(f) for f in run):
            continue
        before, after = T[:i], T[i + k:]
        if (before or after) and not top:
            continue
        for nb in _match_seq(matrices, run, assumptions, b):
            if before or after:
                nb = {**nb, REBUILD: (lambda r, before=before, after=after:
                                      MatMul(*before, r, *after).doit(deep=False))}
            else:
                nb = {**nb, REBUILD: (lambda r: r.doit(deep=False) if isinstance(r, MatrixExpr) else r)}
            yield nb


hooks.match.append(match_matrix)
hooks.non_scalar += (MatrixExpr,)
hooks.commutative += (MatAdd, HadamardProduct)
