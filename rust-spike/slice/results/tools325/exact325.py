"""exact325.py (sa-port-325, issue 323): the exact evaluator of the None-certify scratch check. OFFLINE ONLY: SymPy is used
here to substitute a point into the query's ORIGINAL proposition and assumptions; nothing here is on any query path.

A point maps every free symbol to a value. After substitution (``xreplace``, so SymPy's automatic evaluation of explicit
numbers runs, never an assumption query) a term's value must be of a KIND this file decides by its own table:
  q    a rational (Fraction)
  +oo, -oo, zoo
  c    a + b*I with rational a, b and b != 0
  p    a + b*pi with rational a, b and b != 0: irrational and transcendental because pi is; its sign, and its order
       against a rational or another such value, by exact rational comparison with PI_LO < pi < PI_HI (a comparison the
       two bounds do not settle is uncheckable)
  k    exactly one of the named irrational constants of NAMED (decided by table, only when the term IS that constant)
Anything else (a transcendental or algebraic expression, an unevaluated function, nan, a matrix) is UNCHECKABLE, with the
reason kept: SymPy's own evaluation of predicates is never asked (satassume issue 247).

Truth values are Kleene: True, False, or a string (the reason it is uncheckable). The basis predicates follow
satassume.knowledge.rules.BASIS; a derived predicate is its definition there (rules.DEFINITIONS), which are SymPy's
definitional identities (real = extended_real & finite, ...), not rules of inference.
"""
from fractions import Fraction
from sympy import I, S, Symbol, pi, sqrt, isprime, Rational
from sympy.assumptions.assume import AppliedPredicate
from sympy.core.relational import Relational
from sympy.logic.boolalg import And, Or, Not, Implies, Equivalent, Xor, BooleanTrue, BooleanFalse
from satassume.knowledge.rules import BASIS, DEFINITIONS

T, F = True, False
#           algebraic complex composite even ext_neg ext_pos ext_real finite imaginary integer polar prime rational zero
_ROW = {
    "+oo": (F, F, F, F, F, T, T, F, F, F, F, F, F, F),
    "-oo": (F, F, F, F, T, F, T, F, F, F, F, F, F, F),
    "zoo": (F, F, F, F, F, F, F, F, F, F, F, F, F, F),
}
# named irrational constants: value -> basis row (decided by hand: sqrt(2) algebraic positive irrational, pi transcendental)
NAMED = {
    sqrt(2):      (T, T, F, F, F, T, T, T, F, F, F, F, F, F),
    -sqrt(2):     (T, T, F, F, T, F, T, T, F, F, F, F, F, F),
    sqrt(2) * I:  (T, T, F, F, F, F, F, T, T, F, F, F, F, F),
    pi * I:       (F, T, F, F, F, F, F, T, T, F, F, F, F, F),
    sqrt(2) + I:  (T, T, F, F, F, F, F, T, F, F, F, F, F, F),
    pi + I:       (F, T, F, F, F, F, F, T, F, F, F, F, F, F),
}
assert BASIS == ('algebraic', 'complex', 'composite', 'even', 'extended_negative', 'extended_positive', 'extended_real',
                 'finite', 'imaginary', 'integer', 'polar', 'prime', 'rational', 'zero')


PI_LO, PI_HI = Fraction(314159265358979, 10**14), Fraction(314159265358980, 10**14)   # pi = 3.14159265358979323846...


def sign_qpi(a, b):
    """Sign (-1, 0, 1) of a + b*pi, or None when the rational bounds on pi do not settle it."""
    if b == 0:
        return (a > 0) - (a < 0)
    lo, hi = (a + b * PI_LO, a + b * PI_HI) if b > 0 else (a + b * PI_HI, a + b * PI_LO)
    if lo > 0:
        return 1
    if hi < 0:
        return -1
    return None


def _qpi(v):
    try:
        d = v.as_coefficients_dict()
    except Exception:
        return None
    a = b = Fraction(0)
    for k, c in d.items():
        if not getattr(c, "is_Rational", False):
            return None
        c = Fraction(int(c.p), int(c.q))
        if k is S.One:
            a = c
        elif k is pi:
            b = c
        else:
            return None
    return (a, b) if b != 0 else None


def kind(v):
    """(kind, payload) of a substituted term, or (None, reason)."""
    if v.is_Rational:
        return "q", Fraction(int(v.p), int(v.q))
    if v is S.Infinity:
        return "+oo", None
    if v is S.NegativeInfinity:
        return "-oo", None
    if v is S.ComplexInfinity:
        return "zoo", None
    if v is S.NaN:
        return None, "nan"
    if v in NAMED:
        return "k", v
    if v is pi or v.is_Add or v.is_Mul:
        ab = _qpi(v)
        if ab is not None:
            return "p", ab
    if v.is_Add or v.is_Mul or v is I:
        a, b = v.as_coeff_Add()
        if a.is_Rational:
            c, r = b.as_coeff_Mul()
            if r is I and c.is_Rational and c != 0:
                return "c", (Fraction(int(a.p), int(a.q)), Fraction(int(c.p), int(c.q)))
    if getattr(v, "free_symbols", None):
        return None, "free symbol left"
    if not getattr(v, "is_number", False):
        return None, "not a number: " + type(v).__name__
    if v.is_Function:
        return None, "function value: " + type(v).__name__
    from sympy import Pow
    if v.has(pi) or v.has(S.Exp1) or v.has(S.EulerGamma) or v.has(S.GoldenRatio) or v.has(S.Catalan):
        return None, "constant expression (transcendental)"
    if v.atoms(Pow) and not any(f.is_Function for f in v.atoms() if hasattr(f, "is_Function")):
        return None, "radical expression"
    return None, "other number: " + type(v).__name__


POLAR = BASIS.index("polar")


def same(row, block):
    """Does a value's row equal a model's block? ``polar`` is left out: this table does not decide it (SymPy's is_polar
    is False for an ordinary number, the engine's models leave it free), so it is never compared and a query that asks
    for it is uncheckable."""
    return all(a == b for j, (a, b) in enumerate(zip(row, block)) if j != POLAR)


def basis_row(k, x):
    r = _basis_row(k, x)
    return r[:POLAR] + (None,) + r[POLAR + 1:]


def _basis_row(k, x):
    if k == "q":
        n = x.numerator if x.denominator == 1 else None
        pr = n is not None and n > 1 and isprime(n)
        return (T, T, n is not None and n > 1 and not pr, n is not None and n % 2 == 0, x < 0, x > 0, T, T, F,
                n is not None, F, pr, T, x == 0)
    if k == "c":
        return (T, T, F, F, F, F, F, T, x[0] == 0, F, F, F, F, F)
    if k == "k":
        return NAMED[x]
    if k == "p":
        sg = sign_qpi(*x)
        return (F, T, F, F, None if sg is None else sg < 0, None if sg is None else sg > 0, T, T, F, F, F, F, F, F)
    return _ROW[k]


def _defs():
    out = {}
    for name, d in DEFINITIONS.items():
        d = d.strip()
        if not d:
            out[name] = ("&", ())
            continue
        op = "|" if "|" in d else "&"
        lits = []
        for t in d.split(op):
            t = t.strip()
            neg = t.startswith("!")
            lits.append((BASIS.index(t.lstrip("!")), neg))
        out[name] = (op, tuple(lits))
    return out


DEFS = _defs()
BIDX = {p: i for i, p in enumerate(BASIS)}
REL = {"gt": ">", "lt": "<", "ge": ">=", "le": "<=", "eq": "==", "ne": "!="}
RELCLS = {"StrictGreaterThan": ">", "StrictLessThan": "<", "GreaterThan": ">=", "LessThan": "<=", "Equality": "==",
          "Unequality": "!="}


def pred_value(name, row):
    close = "sign too close to settle with the rational bounds on pi"
    i = BIDX.get(name)
    if i == POLAR:
        return "polar is not decided by this table"
    if i is not None:
        return close if row[i] is None else row[i]
    d = DEFS.get(name)
    if d is None:
        return "predicate outside the vocabulary: " + name
    op, lits = d
    vals = [close if row[j] is None else row[j] != neg for j, neg in lits]
    return k_and(vals) if op == "&" else k_or(vals)


def _ext(k, x):
    """An extended real as a comparable key, or None."""
    if k == "q":
        return (0, (x, Fraction(0)))
    if k == "p":
        return (0, x)
    if k == "+oo":
        return (1, 0)
    if k == "-oo":
        return (-1, 0)
    return None


def rel_value(op, a, b):
    (ka, xa), (kb, xb) = a, b
    if op in ("==", "!="):
        same = ka == kb and xa == xb
        return same if op == "==" else not same
    ea, eb = _ext(ka, xa), _ext(kb, xb)
    if ea is None or eb is None:
        return "order relation at a value that is not an extended real"
    if ea[0] != eb[0] or ea[0] != 0:
        c = (ea[0] > eb[0]) - (ea[0] < eb[0])
    else:
        c = sign_qpi(ea[1][0] - eb[1][0], ea[1][1] - eb[1][1])
        if c is None:
            return "order too close to settle with the rational bounds on pi"
    return {">": c > 0, "<": c < 0, ">=": c >= 0, "<=": c <= 0}[op]


def term(e, point):
    try:
        v = e.xreplace(point) if point else e
    except Exception as ex:                       # a substitution SymPy refuses is uncheckable, not a failure
        return None, "substitution raised " + type(ex).__name__
    if not hasattr(v, "is_Rational"):
        return None, "not a term: " + type(v).__name__
    return kind(v)


def k_not(a):
    return (not a) if a is True or a is False else a


def k_and(vals):
    unk = None
    for v in vals:
        if v is False:
            return False
        if v is not True and unk is None:
            unk = v
    return True if unk is None else unk


def k_or(vals):
    unk = None
    for v in vals:
        if v is True:
            return True
        if v is not False and unk is None:
            unk = v
    return False if unk is None else unk


def truth(e, point):
    """Kleene truth value of the SymPy boolean ``e`` at ``point``: True, False or a reason string."""
    if e is True or isinstance(e, BooleanTrue):
        return True
    if e is False or isinstance(e, BooleanFalse):
        return False
    if isinstance(e, And):
        return k_and(truth(a, point) for a in e.args)
    if isinstance(e, Or):
        return k_or(truth(a, point) for a in e.args)
    if isinstance(e, Not):
        return k_not(truth(e.args[0], point))
    if isinstance(e, Implies):
        return k_or([k_not(truth(e.args[0], point)), truth(e.args[1], point)])
    if isinstance(e, (Equivalent, Xor)):
        vs = [truth(a, point) for a in e.args]
        for v in vs:
            if v is not True and v is not False:
                return v
        if isinstance(e, Equivalent):
            return all(vs) or not any(vs)
        return sum(vs) % 2 == 1
    if isinstance(e, AppliedPredicate):
        name = getattr(e.function, "name", None) or str(e.function)
        args = e.arguments
        if name in REL and len(args) == 2:
            a, b = term(args[0], point), term(args[1], point)
            if a[0] is None:
                return a[1]
            if b[0] is None:
                return b[1]
            return rel_value(REL[name], a, b)
        if len(args) != 1:
            return "predicate with %d arguments: %s" % (len(args), name)
        if not hasattr(args[0], "is_Rational"):
            return "predicate of a non-term: " + type(args[0]).__name__
        a = term(args[0], point)
        if a[0] is None:
            return a[1]
        return pred_value(name, basis_row(*a))
    if isinstance(e, Relational):
        op = RELCLS.get(type(e).__name__)
        if op is None:
            return "relation class " + type(e).__name__
        a, b = term(e.lhs, point), term(e.rhs, point)
        if a[0] is None:
            return a[1]
        if b[0] is None:
            return b[1]
        return rel_value(op, a, b)
    if isinstance(e, Symbol):
        return "boolean symbol"
    return "boolean of class " + type(e).__name__


def witness(p, a, point, want):
    """'ok' if the assumptions hold and the proposition has truth value ``want`` at ``point``, both decided exactly;
    ('fail', what) if one is decided the other way; ('unk', reason) if not failed and something is uncheckable."""
    ta = truth(a, point)
    if ta is False:
        return ("fail", "assumptions false")
    tp = truth(p, point)
    if tp is (not want):
        return ("fail", "proposition has the other value")
    if ta is not True:
        return ("unk", "assumptions: " + ta)
    if tp is not want:
        return ("unk", "proposition: " + tp)
    return ("ok", "")


def arith_only(e):
    """Is every term of ``e`` built from symbols, rationals, + and * and integer powers only (field arithmetic)?"""
    from sympy import preorder_traversal, Add, Mul, Pow, Expr
    for n in preorder_traversal(e):
        if not isinstance(n, Expr):
            continue        # the boolean structure and the predicate objects
        if getattr(n, "is_Symbol", False) or getattr(n, "is_Rational", False):
            continue
        if isinstance(n, (Add, Mul)):
            continue
        if isinstance(n, Pow) and n.exp.is_Integer:
            continue
        if not hasattr(n, "is_Rational"):
            continue        # the predicate object itself
        return False
    return True
