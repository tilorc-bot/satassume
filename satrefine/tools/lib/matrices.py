"""The matrix family (``--matrices``): generation, explicit sample matrices, values, comparison.

A case stream of its own (:func:`mat_generate`, seeded with the string
"matrix-SEED-CASE"), so the scalar seeds generate the same cases as without
it.  Sample points are explicit small matrices (0x0 to 3x3, exact rational
and Gaussian-rational entries) built to satisfy each matrix symbol's
predicates and verified against a numeric definition of every predicate
(``MPREDS``) before use (rejection sampling), together with values for the
scalar factor, the element indices and symbolic sizes.  Values are computed
operation by operation on the explicit matrices (:func:`mat_value`), so no
symbolic rule of SymPy's decides one.
"""
from __future__ import annotations

import random
from collections import Counter

from sympy import (Adjoint, Determinant, HadamardProduct, I, Identity, ImmutableMatrix, Integer, Inverse, MatMul,
                   MatrixSymbol, OneMatrix, Q, Rational, S, Symbol, Trace, Transpose, ZeroMatrix, expand, im)
from sympy.core.basic import Basic
from sympy.matrices.expressions.matexpr import MatrixExpr

from .assumptions import PREDS, conjunction, draw, rel_holds
from .numeric import agree, numeric

def _zero(e):
    return expand(e) == 0


def _same(A, B):
    return A.shape == B.shape and all(_zero(a - b) for a, b in zip(A, B))


def _eye(k):
    return ImmutableMatrix.eye(k)


def _sq(M):
    return M.rows == M.cols


def _upper(M):
    return _sq(M) and all(_zero(M[r, c]) for r in range(M.rows) for c in range(r))


def _lower(M):
    return _sq(M) and all(_zero(M[r, c]) for r in range(M.rows) for c in range(r + 1, M.cols))


def _det(M):
    return expand(M.det()) if M.rows else S.One


def _pd(M):
    if not (_sq(M) and _same(M, M.T) and all(_zero(im(e)) for e in M)):
        return False
    return all(expand(M[:r, :r].det()) > 0 for r in range(1, M.rows + 1))


MPREDS = {  # name -> (Q builder, numeric definition on an explicit matrix)
    "zero": (Q.zero, lambda M: all(_zero(e) for e in M)),
    "square": (Q.square, _sq),
    "symmetric": (Q.symmetric, lambda M: _sq(M) and _same(M, M.T)),
    "diagonal": (Q.diagonal, lambda M: _upper(M) and _lower(M)),
    "orthogonal": (Q.orthogonal, lambda M: _sq(M) and _same(M.T * M, _eye(M.rows)) and _same(M * M.T, _eye(M.rows))),
    "unitary": (Q.unitary, lambda M: _sq(M) and _same(M.H * M, _eye(M.rows)) and _same(M * M.H, _eye(M.rows))),
    "normal": (Q.normal, lambda M: _sq(M) and _same(M * M.H, M.H * M)),
    "invertible": (Q.invertible, lambda M: _sq(M) and not _zero(_det(M))),
    "singular": (Q.singular, lambda M: _sq(M) and _zero(_det(M))),
    "fullrank": (Q.fullrank, lambda M: M.rank() == min(M.shape)),
    "upper_triangular": (Q.upper_triangular, _upper),
    "lower_triangular": (Q.lower_triangular, _lower),
    "triangular": (Q.triangular, lambda M: _upper(M) or _lower(M)),
    "unit_triangular": (Q.unit_triangular, lambda M: (_upper(M) or _lower(M)) and all(_zero(M[r, r] - 1) for r in range(M.rows))),
    "positive_definite": (Q.positive_definite, _pd),
    "real_elements": (Q.real_elements, lambda M: all(_zero(im(e)) for e in M)),
    "integer_elements": (Q.integer_elements, lambda M: all(expand(e).is_Integer for e in M)),
    "complex_elements": (Q.complex_elements, lambda M: True),
}
# Per square matrix symbol; each combination is satisfiable at every size 1..3.
MCOMBOS = [(), (), ("zero",), ("symmetric",), ("diagonal",), ("orthogonal",), ("orthogonal", "real_elements"),
           ("unitary",), ("unitary", "real_elements"), ("invertible",), ("singular",), ("unit_triangular",),
           ("upper_triangular",), ("lower_triangular",), ("triangular",), ("positive_definite",), ("real_elements",),
           ("symmetric", "real_elements"), ("diagonal", "invertible"), ("diagonal", "singular"),
           ("symmetric", "singular"), ("upper_triangular", "singular"), ("normal",), ("integer_elements",),
           ("fullrank",), ("symmetric", "orthogonal"), ("diagonal", "unitary"), ("complex_elements",),
           ("orthogonal", "unitary"), ("symmetric", "unitary"), ("diagonal", "real_elements"), ("square",)]
RCOMBOS = [(), (), ("zero",), ("real_elements",), ("integer_elements",), ("fullrank",), ("complex_elements",)]
SCALAR_COMBOS = [(), ("zero",), ("zero",), ("positive",), ("real",), ("nonzero",), ("imaginary",), ("integer",), ("negative",)]
INDEX_COMBOS = [(), ("integer",), ("integer",), ("nonnegative", "integer"), ("negative", "integer"),
                ("positive", "integer"), ("nonzero", "integer"), ("zero",)]
SIZE_COMBOS = [(), ("positive",), ("positive", "integer"), ("nonnegative", "integer"), ("nonzero",)]

_msn, _msp = Symbol("n"), Symbol("p")          # symbolic sizes
_mc, _mi, _mj = Symbol("c"), Symbol("i"), Symbol("j")
SIZE_SYMS, INDEX_SYMS = (_msn, _msp), (_mi, _mj)


def _gauss(rng, real):
    re_ = Integer(rng.randint(-3, 3))
    return re_ if real or rng.random() < 0.4 else re_ + I * Integer(rng.randint(-3, 3))


def _block_diag(blocks, k):
    M = [[S.Zero] * k for _ in range(k)]
    at = 0
    for b in blocks:
        for r in range(b.rows):
            for c_ in range(b.cols):
                M[at + r][at + c_] = b[r, c_]
        at += b.rows
    return ImmutableMatrix(k, k, [e for row in M for e in row]) if k else ImmutableMatrix.zeros(0, 0)


def _perm(rng, k):
    idx = list(range(k))
    rng.shuffle(idx)
    return ImmutableMatrix(k, k, lambda r, c_: 1 if idx[r] == c_ else 0) if k else ImmutableMatrix.zeros(0, 0)


_R = Rational
ORTH2 = [ImmutableMatrix([[a, -b], [b, a]]) for a, b in ((_R(3, 5), _R(4, 5)), (0, 1), (_R(5, 13), _R(12, 13)))] + \
        [ImmutableMatrix([[a, b], [b, -a]]) for a, b in ((_R(3, 5), _R(4, 5)), (0, 1))]
# complex orthogonal (M.T*M = I), not unitary
CORTH2 = [ImmutableMatrix([[_R(5, 4), 3 * I / 4], [-3 * I / 4, _R(5, 4)]]),
          ImmutableMatrix([[_R(5, 3), 4 * I / 3], [-4 * I / 3, _R(5, 3)]]),
          ImmutableMatrix([[_R(5, 4), 3 * I / 4], [3 * I / 4, -_R(5, 4)]])]
# unitary (M.H*M = I), not orthogonal
UNIT2 = [ImmutableMatrix([[_R(3, 5), 4 * I / 5], [4 * I / 5, _R(3, 5)]]),
         ImmutableMatrix([[_R(3, 5), -4 * I / 5], [-4 * I / 5, _R(3, 5)]])]


def _blocks(rng, k, pool, ones):
    out, left = [], k
    while left:
        if left >= 2 and pool and rng.random() < 0.7:
            out.append(rng.choice(pool)); left -= 2
        else:
            out.append(ImmutableMatrix([[rng.choice(ones)]])); left -= 1
    return out


def _gen(rng, r, c_, kind):
    """A random candidate matrix of shape (r, c_) of a given construction."""
    real = rng.random() < 0.5
    generic = lambda re_=real: ImmutableMatrix(r, c_, lambda a, b: _gauss(rng, re_))  # noqa: E731
    if kind == "generic":
        return generic()
    if kind == "zero":
        return ImmutableMatrix.zeros(r, c_)
    if r != c_:
        return generic()
    k = r
    if kind == "identity":
        return _eye(k)
    if kind == "diagonal":
        return ImmutableMatrix.diag(*[_gauss(rng, real) for _ in range(k)]) if k else ImmutableMatrix.zeros(0, 0)
    if kind == "symmetric":
        G = generic()
        return G + G.T
    if kind == "rank1":
        v = ImmutableMatrix(k, 1, lambda a, b: _gauss(rng, real))
        return v * v.T if rng.random() < 0.5 else v * ImmutableMatrix(1, k, lambda a, b: _gauss(rng, real))
    if kind in ("orthogonal", "unitary"):
        if kind == "orthogonal":
            pool, ones = ORTH2 + (CORTH2 if rng.random() < 0.5 else []), [1, -1]
        else:
            pool, ones = ORTH2 + UNIT2, [1, -1, I, -I]
        B = _block_diag(_blocks(rng, k, pool, ones), k)
        P = _perm(rng, k)
        return P * B * P.T if rng.random() < 0.5 else P * B
    if kind == "singular":
        G = generic()
        if k == 0:
            return G
        rows = [list(G.row(t)) for t in range(k)]
        src, dst = rng.randrange(k), rng.randrange(k)
        f = _gauss(rng, True)
        rows[dst] = [f * e for e in rows[src]] if src != dst else [S.Zero] * k
        return ImmutableMatrix(rows)
    if kind in ("upper", "lower", "unit_upper", "unit_lower"):
        M = [[_gauss(rng, real) for _ in range(k)] for _ in range(k)]
        for a in range(k):
            for b in range(k):
                if (kind.endswith("upper") and a > b) or (kind.endswith("lower") and a < b):
                    M[a][b] = S.Zero
            if kind.startswith("unit"):
                M[a][a] = S.One
        return ImmutableMatrix(M) if k else ImmutableMatrix.zeros(0, 0)
    if kind == "pd":
        G = ImmutableMatrix(k, k, lambda a, b: Integer(rng.randint(-2, 2)))
        return G.T * G + _eye(k)
    return generic()


_KINDS = ["generic", "zero", "identity", "diagonal", "symmetric", "rank1", "orthogonal", "unitary", "singular",
          "upper", "lower", "unit_upper", "unit_lower", "pd"]


def mdraw(combo, shape, rng, tries=400):
    """An explicit matrix of ``shape`` satisfying every predicate in ``combo``, or None."""
    r, c_ = shape
    for _ in range(tries):
        M = _gen(rng, r, c_, rng.choice(_KINDS))
        if all(MPREDS[p][1](M) for p in combo):
            return M
    return None


# --- grammar: square X, Y (k x k); rectangular R, R2 (k x l) and W (l x k); scalar c; indices i, j

def _mat_inner(rng, X, Y, c):
    choices = [
        lambda: X, lambda: Y, lambda: X.T, lambda: -X, lambda: 2 * X, lambda: c * X, lambda: X * Y,
        lambda: X * Y * X, lambda: X.T * Y * X, lambda: Inverse(X), lambda: X + Y, lambda: X - X.T,
        lambda: MatMul(X, X), lambda: X.T * X, lambda: X * X.T, lambda: Adjoint(X), lambda: Adjoint(X) * X,
        lambda: X * Adjoint(X), lambda: MatMul(Inverse(X), X), lambda: MatMul(X, Inverse(X)),
        lambda: HadamardProduct(X, Y), lambda: X ** 2, lambda: X * Y.T, lambda: Inverse(X.T),
        lambda: Inverse(X * Y), lambda: c * X * Y, lambda: X + Y + X.T, lambda: X - X, lambda: Transpose(X * Y),
    ]
    return rng.choice(choices)()


def _index(rng, k):
    if rng.random() < 0.5:
        return rng.choice(INDEX_SYMS)
    return Integer(rng.choice([0, 1, -1, 2, -2]) if not isinstance(k, int) else rng.randrange(-k, k) if k else 0)


MAT_OUTER = {
    "Transpose": lambda e, g: Transpose(e),
    "Inverse": lambda e, g: Inverse(e),
    "Determinant": lambda e, g: Determinant(e),
    "Trace": lambda e, g: Trace(e),
    "MatAdd": lambda e, g: e + g.inner(),
    "MatAdd3": lambda e, g: e + g.inner() + g.inner(),
    "MatMul": lambda e, g: e * g.inner(),
    "MatMul3": lambda e, g: e * g.inner() * g.inner(),
    "scalar": lambda e, g: g.c * e,
    "Hadamard": lambda e, g: HadamardProduct(e, g.inner()),
    "MatrixElement": lambda e, g: e[_index(g.rng, g.k), _index(g.rng, g.k)],
    "Adjoint": lambda e, g: Adjoint(e),
    "Trace_sum": lambda e, g: Trace(e + g.inner()),
    "Det_prod": lambda e, g: Determinant(e * g.inner()),
    "Inverse_prod": lambda e, g: Inverse(g.X * g.Y),
    "rect": None,  # below
}


def _rect_expr(g):
    R, R2, W, X = g.R, g.R2, g.W, g.X
    choices = [
        lambda: Transpose(R), lambda: R.T, lambda: R + R2, lambda: HadamardProduct(R, R2), lambda: R * W,
        lambda: W * R, lambda: g.c * R, lambda: R[_index(g.rng, g.k), _index(g.rng, g.l)], lambda: Transpose(R * W),
        lambda: Trace(R * W), lambda: Determinant(R * W), lambda: R.T * X * R, lambda: Transpose(R.T * X * R),
        lambda: R * W * X, lambda: X * R * W, lambda: Transpose(R + R2), lambda: R - R, lambda: R * (W * R),
        lambda: (R * W)[_index(g.rng, g.k), _index(g.rng, g.k)], lambda: Inverse(R * W), lambda: Adjoint(R) * R,
    ]
    return g.rng.choice(choices)()


class _MatCase:
    """The symbols of one matrix case."""

    def __init__(self, rng):
        self.rng = rng
        self.k = rng.choice([1, 2, 2, 3, 3, _msn])
        self.l = rng.choice([1, 2, 3, _msp]) if rng.random() < 0.8 else self.k
        k, l = self.k, self.l
        self.X, self.Y = MatrixSymbol("X", k, k), MatrixSymbol("Y", k, k)
        self.R, self.R2 = MatrixSymbol("R", k, l), MatrixSymbol("R2", k, l)
        self.W = MatrixSymbol("W", l, k)
        self.c = _mc

    def inner(self):
        if self.rng.random() < 0.25:          # a bare symbol: what most rows are stated for
            return self.rng.choice([self.X, self.Y])
        return _mat_inner(self.rng, self.X, self.Y, self.c)


def mat_generate(seed, case):
    """Matrix case ``case`` of ``seed``: (head, expr, assumptions, combos, rel) or None.

    ``combos`` maps every free symbol of ``expr`` (matrix, scalar, index and
    size symbols) to its predicate names; ``rel`` is a relation between the
    indices or None.  The stream is separate from the scalar one.
    """
    rng = random.Random(f"matrix-{seed}-{case}")
    g = _MatCase(rng)
    head = rng.choice(list(MAT_OUTER))
    try:
        e = _rect_expr(g) if head == "rect" else MAT_OUTER[head](g.inner(), g)
    except Exception:
        return None
    if not isinstance(e, Basic) or not e.free_symbols:
        return None
    free = set(e.free_symbols)
    free |= {d for s in e.atoms(MatrixSymbol) for d in s.shape if d in SIZE_SYMS}  # MatrixSymbol hides its size
    combos = {}
    for s in sorted(free, key=str):
        if isinstance(s, MatrixSymbol):
            combos[s] = rng.choice(MCOMBOS if s.name in ("X", "Y") else RCOMBOS)
        elif s in SIZE_SYMS:
            combos[s] = rng.choice(SIZE_COMBOS)
        elif s in INDEX_SYMS:
            combos[s] = rng.choice(INDEX_COMBOS)
        else:
            combos[s] = rng.choice(SCALAR_COMBOS)
    facts = []
    for s, combo in combos.items():
        table = MPREDS if isinstance(s, MatrixSymbol) else PREDS
        facts += [table[p][0](s) for p in combo]
    rel = None
    idx = [s for s in INDEX_SYMS if s in combos]
    if idx and rng.random() < 0.4:
        a = rng.choice(idx)
        b = rng.choice([t for t in idx if t != a] + [S.Zero, S.One])
        rel = rng.choice([Q.gt, Q.ge, Q.lt, Q.le, Q.eq, Q.ne])(a, b)
        facts.append(rel)
    return head, e, conjunction(facts), combos, rel


def mat_point(combos, rel, rng):
    """One random point satisfying ``combos`` and ``rel``: {symbol: value}, or None.

    Sizes first (0 to 3), then scalars, indices (integers that are valid
    indices, negative ones wrapping, of every dimension in play) and matrices of
    the substituted shapes.
    """
    pt = {}
    for s in combos:
        if s in SIZE_SYMS:
            vals = [Integer(v) for v in range(4) if all(PREDS[p][1](Integer(v)) for p in combos[s])]
            if not vals:
                return None
            pt[s] = rng.choice(vals)
    dims = [int(d.xreplace(pt)) for s in combos if isinstance(s, MatrixSymbol) for d in s.shape]
    lim = min(dims) if dims else 3
    for s, combo in combos.items():
        if s in INDEX_SYMS:
            vals = [Integer(v) for v in range(-lim, lim) if all(PREDS[p][1](Integer(v)) for p in combo)]
            if not vals:
                return None
            pt[s] = rng.choice(vals)
        elif not isinstance(s, MatrixSymbol) and s not in SIZE_SYMS:
            v = draw(combo, rng)
            if v is None:
                return None
            pt[s] = v
    for s, combo in combos.items():
        if isinstance(s, MatrixSymbol):
            shape = tuple(int(d.xreplace(pt)) for d in s.shape)
            M = mdraw(combo, shape, rng)
            if M is None:
                return None
            pt[s] = M
    if rel is not None and rel_holds(rel, {s: v for s, v in pt.items() if not isinstance(s, MatrixSymbol)}) is not True:
        return None
    return pt


def mat_points(combos, rel, rng, count=12, tries=60):
    pts = []
    for _ in range(tries):
        if len(pts) >= count:
            break
        p = mat_point(combos, rel, rng)
        if p is not None:
            pts.append(p)
    return pts


class _Unsupported(Exception):
    pass


def _explicit(node, mats, scal):
    """``node`` evaluated with explicit matrices, operation by operation.

    Every matrix operation is done on explicit matrices (so no symbolic rule of
    SymPy's, such as ``det(ZeroMatrix(0, 0)) = 0`` or ``0*X -> ZeroMatrix``,
    decides a value).  Raises ``_Unsupported`` for a node it does not know.
    """
    from sympy import MatAdd, MatPow, Sum
    from sympy.matrices.expressions.matexpr import MatrixElement as ME
    ev = lambda a: _explicit(a, mats, scal)  # noqa: E731
    if isinstance(node, MatrixSymbol):
        M = mats.get(node.name)
        if M is None or tuple(d.xreplace(scal) for d in node.shape) != M.shape:
            raise ValueError("shape")
        return M
    if isinstance(node, (ZeroMatrix, Identity, OneMatrix)):
        node = node.xreplace(scal)
        if not all(d.is_Integer for d in node.shape):
            raise _Unsupported
        return ImmutableMatrix(node.as_explicit())
    if isinstance(node, MatAdd):
        out = ev(node.args[0])
        for a in node.args[1:]:
            out = out + ev(a)
        return out
    if isinstance(node, MatMul):
        out = S.One
        for a in node.args:
            out = out * ev(a)
        return out
    if isinstance(node, MatPow):
        return ev(node.base) ** ev(node.exp)
    if isinstance(node, Inverse):
        return ev(node.arg).inv()          # a singular matrix raises: undefined, as it should
    if isinstance(node, Transpose):
        return ev(node.arg).T
    if isinstance(node, Adjoint):
        return ev(node.arg).H
    if isinstance(node, HadamardProduct):
        out = ev(node.args[0])
        for a in node.args[1:]:
            out = out.multiply_elementwise(ev(a))
        return out
    if isinstance(node, Determinant):
        M = ev(node.arg)
        return M.det() if M.rows else S.One
    if isinstance(node, Trace):
        M = ev(node.arg)
        return M.trace() if M.rows else S.Zero
    if isinstance(node, ME):
        M, i, j = ev(node.parent), ev(node.i), ev(node.j)
        if not (i.is_Integer and j.is_Integer and -M.rows <= i < M.rows and -M.cols <= j < M.cols):
            raise ValueError("index out of range")
        return M[int(i), int(j)]
    if isinstance(node, Sum):
        raise _Unsupported
    if isinstance(node, MatrixExpr):
        raise _Unsupported
    if not node.args or not node.has(MatrixSymbol, ZeroMatrix, Identity, OneMatrix):
        return node.xreplace(scal)
    return node.func(*[ev(a) for a in node.args])


def mat_value(e, pt):
    """The numeric value of ``e`` at ``pt``: a complex, a ('M', shape, values) triple, or a failure string."""
    try:
        mats = {s.name: v for s, v in pt.items() if isinstance(s, MatrixSymbol)}
        scal = {s: v for s, v in pt.items() if not isinstance(s, MatrixSymbol)}
        try:
            v = _explicit(e, mats, scal)
        except _Unsupported:
            v = _mat_value_doit(e, pt, mats)
        if isinstance(v, str):
            return v
        if isinstance(v, MatrixExpr) or getattr(v, "is_Matrix", False):
            v = ImmutableMatrix(v.as_explicit()) if isinstance(v, MatrixExpr) else ImmutableMatrix(v)
            vals = tuple(numeric(x) for x in v)
            bad = [x for x in vals if isinstance(x, str)]
            return bad[0] if bad else ("M", v.shape, vals)
        return numeric(v)
    except Exception:
        return "error"


def _mat_value_doit(e, pt, byname):
    """Fallback for nodes ``_explicit`` does not know (``Sum``): substitute, then ``doit``."""
    # sizes first (they are part of a MatrixSymbol), then everything else in one
    # simultaneous replacement, so no symbolic cancellation happens between the steps
    e1 = e.xreplace({s: v for s, v in pt.items() if s in SIZE_SYMS})
    rep = {s: v for s, v in pt.items() if not isinstance(s, MatrixSymbol) and s not in SIZE_SYMS}
    for ms in e1.atoms(MatrixSymbol):
        M = byname.get(ms.name)
        if M is None or tuple(ms.shape) != M.shape:
            return "error"
        rep[ms] = M
    for sm in e1.atoms(ZeroMatrix, Identity, OneMatrix):
        if all(d.is_Integer for d in sm.shape):
            rep[sm] = ImmutableMatrix(sm.as_explicit())
    return e1.xreplace(rep).doit()


def mat_agree(a, b):
    if isinstance(a, tuple) and isinstance(b, tuple):
        return a[1] == b[1] and all(agree(x, y) for x, y in zip(a[2], b[2]))
    if isinstance(a, tuple) or isinstance(b, tuple):
        return False
    return agree(a, b)


def mat_compare(left, right, points, ref=None):
    """(n_checked, counterexample or None): ``left`` and ``right`` at ``points``.

    A point counts as checked only when both sides have a finite value there.
    A point where ``left`` (the input), or ``ref`` if given (the input when two
    rewrites are compared), is undefined is skipped; one where only ``right``
    is undefined is a counterexample.
    """
    bad = ("error", "unevaluated", "nan", "inf")
    checked = 0
    for pt in points:
        if ref is not None and mat_value(ref, pt) in bad:
            continue
        a, b = mat_value(left, pt), mat_value(right, pt)
        if a in bad:
            continue
        if b in bad or not mat_agree(a, b):
            return checked, (pt, a, b)
        checked += 1
    return checked, None


class MatrixRowCoverage:
    """Counts, per row of ``satrefine.identities.compat.matrices``, how often it fired.

    Inside the ``with`` block every matrix key's handler is wrapped; when it
    returns a rewrite, the first row that alone gives the same rewrite is
    credited.  (Only for the ``handlers_identities`` package.)
    """

    def __init__(self):
        self.counts = Counter()
        self.saved = {}

    def __enter__(self):
        import importlib

        from satrefine._upstream import handlers_dict
        from satrefine.identities.core.rewrite import rule_handler
        mod = importlib.import_module("satrefine.identities.compat.matrices")
        tables = {"Determinant": mod.DETERMINANT, "HadamardProduct": mod.HADAMARD, "Inverse": mod.INVERSE,
                  "MatAdd": mod.MATADD, "MatMul": mod.MATMUL, "MatrixElement": mod.MATRIXELEMENT,
                  "Trace": mod.TRACE, "Transpose": mod.TRANSPOSE}
        self.all_rows = [row for rows in tables.values() for row in rows]
        for key, rows in tables.items():
            original = handlers_dict[key]
            singles = [(row, rule_handler([row])) for row in rows]

            def wrapped(expr, assumptions, _original=original, _singles=singles):
                out = _original(expr, assumptions)
                if out is not None:
                    for row, h in _singles:
                        if h(expr, assumptions) == out:
                            self.counts[row] += 1
                            break
                return out
            self.saved[key] = original
            handlers_dict[key] = wrapped
        return self

    def __exit__(self, *exc):
        from satrefine._upstream import handlers_dict
        handlers_dict.update(self.saved)
        return False


def short(v, width=300):
    s = str(v).replace("\n", "")
    return s if len(s) <= width else s[:width] + "..."
