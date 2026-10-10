"""MONO as an LRA propagator (``lra.MonoLink``, ``lra.MonoPiece``): every
bound the links derive is valid.

For each listed function ``f`` and a linear argument ``u = a*x + b`` this
registers threshold atoms on ``x`` and on ``t = f(u)``, the link's enable
variable ``e`` and its piece-enable variables, and drives the theory
through random assertions, pushes and pops.  Every conflict clause and
every propagation reason must hold at every sample point: a real ``x``
with a real ``f(u)``, ``t`` its value, ``e`` true and each piece variable
true exactly when ``u`` lies in its piece.  After each pop the bounds must
be those before the matching push."""
import random
from fractions import Fraction

import pytest
from sympy import (Rational, S, Symbol, acot, asinh, atan, cosh, exp, log, pi,
                   sinh, sqrt, tanh)

from satassume.theories.lra.constfield import from_sympy
from satassume.theories.lra.lra import LRATheory, MonoLink, MonoPiece, constraint
from satassume.theories.mono import link_map
from satassume.relations import _mono_field

x = Symbol("x")
FAMILIES = [exp(x), log(x), atan(x), tanh(x), sinh(x), asinh(x), cosh(x), acot(x),
            x**2, x**3, x**-1, x**-2, sqrt(x), x**Rational(1, 3), x**Rational(2, 3),
            x**Rational(-1, 2), x**Rational(3, 2), x**4,
            exp(2*x - 1), log(1 - x), atan(2*x - Rational(1, 2)), (1 - x)**2,
            (2*x + 1)**-1, cosh(3*x - 2), sqrt(2 - x), acot(2*x - 1), x**-3, asinh(3*x)]
CS = [Fraction(v, 4) for v in range(-12, 13, 2)] + [Fraction(1, 3), Fraction(-5, 7)]
OPS = ["<", "<=", ">", ">=", "="]


def _samples():
    pts = set(CS) | {c + d for c in CS for d in (Fraction(1, 1000), Fraction(-1, 1000))}
    pts |= {Fraction(50), Fraction(-50), Fraction(1, 50), Fraction(-1, 50)}
    return sorted(pts)


SAMPLES = _samples()


def _truth(op, lhs, rhs):
    d = lhs - rhs
    v = d.evalf(60)
    if not v.is_real:
        return None
    z = abs(v) < 1e-45
    if op == "=":
        return z
    if op == "<":
        return v < 0 and not z
    if op == "<=":
        return v < 0 or z
    if op == ">":
        return v > 0 and not z
    return v > 0 or z


def _setup(app):
    from satassume.theories.lra.lra_adapter import integer_form
    fm = link_map(app, _mono_field())
    sp = fm.sp
    th = LRATheory()
    atoms = {}                   # var -> (key, op, value)
    v = 0
    tvals = set()
    for c in CS:
        try:
            fc = sp.apply(Rational(c.numerator, c.denominator))
        except Exception:
            continue
        if fc.is_real and fc.is_finite and fc.free_symbols == set():
            tvals.add(fc)
    tvals |= {S(-2), S(-1), S.Half, S.Zero, S.One, S(2), pi / 2, -pi / 2, S(4)}
    for key, vals in ((x, [Rational(c.numerator, c.denominator) for c in CS]),
                      (app, sorted(tvals, key=lambda e: float(e)))):
        for c in vals:
            fv = from_sympy(c)
            if fv is None:
                continue
            for op in OPS:
                v += 1
                th.register_atom(v, constraint([(key, 1)], op, fv))
                atoms[v] = (key, op, c)
    form = integer_form(sp.arg)
    e = v + 1
    th.register_atom(e, MonoLink(app, form[0].terms, form[0].offset, fm))
    pieces = {}
    for i, pc in enumerate(sp.pieces):
        if fm.covered or (pc.lo == "-oo" and pc.hi == "oo"):
            continue
        v = e + 1 + i
        th.register_atom(v, MonoPiece(e, i))
        pieces[v] = pc
    return th, atoms, e, pieces, sp


def _in_piece(pc, u):
    if pc.lo == "0" and u < 0 or pc.lo == "0+" and u <= 0:
        return False
    if pc.hi == "0" and u > 0 or pc.hi == "0-" and u >= 0:
        return False
    return True


def _models(app, sp):
    out = []
    for xv in SAMPLES:
        xs = Rational(xv.numerator, xv.denominator)
        u = sp.arg.subs(x, xs)
        tv = app.subs(x, xs)
        if not (tv.is_real and tv.is_finite) or not (u.is_real and u.is_finite):
            continue
        out.append((xs, u, tv))
    return out


def _clause_holds(clause, atoms, e, pieces, model):
    xs, u, tv = model
    for lit in clause:
        a = abs(lit)
        if a == e:
            val = True
        elif a in pieces:
            val = _in_piece(pieces[a], u)
        else:
            key, op, c = atoms[a]
            val = _truth(op, xs if key == x else tv, c)
            if val is None:
                return True
        if val == (lit > 0):
            return True
    return False


@pytest.mark.parametrize("app", FAMILIES, ids=str)
def test_mono_link_reasons_valid(app):
    th, atoms, e, pieces, sp = _setup(app)
    models = _models(app, sp)
    assert models
    rng = random.Random(str(app))
    lits = list(atoms) + list(pieces)
    checked = 0
    for run in range(40):
        assigned = {}
        th.push_level()
        th_e = th.assert_lit(e)
        assert th_e is None or all(_clause_holds(th_e[1], atoms, e, pieces, m) for m in models)
        if th_e is not None:
            th.pop_level()
            continue
        stack = []
        for step in range(6):
            free = [a for a in lits if a not in assigned]
            a = rng.choice(free)
            lit = a if rng.random() < 0.5 else -a
            snap = (list(th._lo), list(th._up), list(th._lo_r), list(th._up_r))
            th.push_level()
            stack.append((snap, dict(assigned)))
            assigned[a] = lit > 0
            r = th.assert_lit(lit)
            if r is not None:
                clause = r[1]
                for l in clause:
                    if abs(l) != e:
                        assert assigned.get(abs(l)) == (l < 0), (app, clause, l)
                for m in models:
                    assert _clause_holds(clause, atoms, e, pieces, m), (app, clause, m)
                checked += 1
                snap, assigned = stack.pop()
                th.pop_level()
                assert (list(th._lo), list(th._up), list(th._lo_r), list(th._up_r)) == snap
                continue
            for plit, reason in th.propagate():
                assert plit in reason
                for l in reason:
                    if l != plit and abs(l) != e:
                        assert assigned.get(abs(l)) == (l < 0), (app, reason, l)
                for m in models:
                    assert _clause_holds(reason, atoms, e, pieces, m), (app, reason, m)
                checked += 1
        while stack:
            snap, assigned = stack.pop()
            th.pop_level()
            assert (list(th._lo), list(th._up), list(th._lo_r), list(th._up_r)) == snap
        th.pop_level()
    assert checked > 0


def test_no_link_without_enable():
    """Without its enable literal a link derives nothing."""
    th, atoms, e, pieces, sp = _setup(exp(x))
    v = next(a for a, (k, op, c) in atoms.items() if k == x and op == ">" and c == 1)
    th.push_level()
    assert th.assert_lit(v) is None
    out = th.propagate()
    assert all(atoms[abs(l)][0] == x for l, _r in out)


# -- end-to-end: infinite arguments, enclosures, piece exclusion ----------

from sympy import AccumBounds, Basic, E, I, oo, zoo, Q, Symbol, sqrt, sinh, tanh, asinh as _asinh, acot as _acot, tan as _tan, atan as _atan
from satassume.sympy_api import ask as _ask

_z = Symbol("z")
_INF_FAMILIES = [exp(_z), log(_z), atan(_z), tanh(_z), sinh(_z), asinh(_z), cosh(_z),
                 acot(_z), _z**2, _z**3, 1 / _z, _z**-2, sqrt(_z), _z**Rational(1, 3),
                 _z**Rational(-1, 2)]
_INF_VALUES = [oo, -oo, zoo, oo * I, -oo * I]


def _num_truth(pred, w):
    """``pred`` of the SymPy number ``w``, None if SymPy cannot say."""
    from sympy import ask as sask
    try:
        return sask(pred(w))
    except TypeError:             # SymPy's own ask on oo*I
        return None


@pytest.mark.parametrize("f", _INF_FAMILIES, ids=str)
def test_infinite_argument_never_contradicted(f):
    """``ask(P(f(z)), Q.eq(z, v))`` at each infinity ``v``: never a
    definite answer SymPy's value ``f(v)`` contradicts, and never a
    spurious inconsistency (the assumptions hold at ``z = v``)."""
    preds = [Q.real, Q.extended_real, Q.finite, Q.zero, Q.positive, Q.negative,
             Q.extended_positive, Q.extended_negative]
    for v in _INF_VALUES:
        w = f.subs(_z, v)
        if not isinstance(w, Basic) or w.has(AccumBounds) or w is S.NaN:
            continue              # no value SymPy states
        for P in preds:
            truth = _num_truth(P, w)
            got = _ask(P(f), Q.eq(_z, v))
            assert got is None or truth is None or got == truth, (f, v, P, w, got)
        if w.is_extended_real:
            for c in (S(-2), S.Zero, S.One, pi / 2):
                try:
                    truth = bool(w < c)
                except TypeError:
                    continue
                got = _ask(Q.lt(f, c), Q.eq(_z, v))
                assert got is None or got == truth, (f, v, c, w, got)


@pytest.mark.parametrize("q, a, want", [
    # enclosures of images the field does not read (asinh(-3))
    ("Q.ne(asinh(n), E)", "Q.lt(n, 0) & Q.eq(-n - 1, 2)", True),
    ("Q.ne(3*asinh(z) + 1, 0)", "Q.eq(z, pi/2)", True),
    ("Q.eq(asinh(-2*z), -2)", "Q.gt(-4*z - 1, S.Half)", False),
    ("Q.le(r, -pi/2)", "Q.eq(3*sinh(r) - 1, -S.Half)", False),
    # a bound of f(u) beyond a piece's image (acot(u) > 0 excludes u < 0)
    ("Q.gt(r, 1)", "Q.lt(acot(r), pi/4) & Q.gt(acot(r), 0)", True),
    ("Q.ge(r, 0)", "Q.gt(acot(r), 0)", True),
    ("Q.gt(r, 0)", "Q.gt(acot(r), 0)", None),          # acot(0) = pi/2
    ("Q.negative(r)", "Q.lt(1/r, -2)", True),
    # an undecidable comparison skips a bound (no give-up of LRA)
    ("Q.le(-sqrt(2)*sqrt(r), S.Half)", "Q.gt(sqrt(2)*sqrt(r), 1)", True),
    # u not a rational linear form: one opaque term (range, realness)
    ("Q.eq(tanh(n + 0.5), -2)", "True", False),
    ("Q.extended_real(asinh(sqrt(e/2)))", "Q.lt(sqrt(e/2), log(2))", True),
    # regressions of session 2
    ("Q.zero(1/y)", "Q.gt(y, pi/2)", None),
    ("Q.eq(z, oo)", "Q.eq(atan(z), pi/2)", None),
    ("Q.real(n**3)", "Q.lt(2*n - 1, 1)", True),
    ("Q.lt(exp(e)**2, S(1)/9)", "Q.lt(e, -2)", True),
    ("Q.lt((2*r + 1)**-1, -1)", "Q.gt(r, -1) & Q.lt(r, -S.Half)", True),
    # Q.nonzero and Q.negative are real: real(1/y) gives real(y) or an
    # infinite y, where 1/y = 0 (new answers once the glue is on; the
    # invariant harness's I2 found them through an unrelated relation atom)
    ("Q.extended_real(y)", "Q.nonzero(1/y) & Q.ne(y, 5)", True),
    ("Q.real(y)", "Q.negative(1/y) & Q.ne(y, 5)", True),
    ("Q.real(y)", "Q.positive(1/y) & Q.ne(y, 5)", True),
    ("~(Implies(Q.positive(sre(x)**2), Q.infinite(y**2)))",
     "Q.negative(1/y) & Q.irrational(x*y**2*(2*y + sre(x))**2) & Q.ne(y, 5)", True),
])
def test_mono_answers(q, a, want):
    ns = dict(globals())
    ns.update(n=Symbol("n", integer=True), r=Symbol("r", real=True),
              e=Symbol("e", extended_real=True), y=Symbol("y"), z=_z,
              E=E, asinh=_asinh, acot=_acot, sre=__import__("sympy").re,
              Implies=__import__("sympy").Implies)
    assert _ask(eval(q, ns), eval(a, ns)) == want
