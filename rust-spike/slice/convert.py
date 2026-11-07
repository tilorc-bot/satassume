"""Conversion: one top-level query's SymPy input as flat tables for Rust (component 0, issue 323).

Section 9 of PORT-INVENTORY.md is the format; TERMS-INTERFACE.md is the interface. No state crosses queries:
everything lives in one `_Walk`. Rows are token streams of ints (see `_enc`), read by solver_rs/src/term/table.rs.

Conversion reads SymPy and may construct inside it: default_sort_key, decompose_power and `.has` on input terms belong
to the Python input layer (planner's ruling 5); the shadow counts them separately. A Pow whose decompose_power base
isn't an input term gets base -1 here and refuses at run time when a key needs it, which is section 9's "refused during
a run" (planner's ruling 1).
"""
import numbers
import struct

from sympy import Add, Function, Integral, Mul, Pow, Product, S, Sum
from sympy.polys.rootoftools import ComplexRootOf
from sympy.assumptions.assume import AppliedPredicate, Predicate
from sympy.core.basic import Basic, ordering_of_classes
from sympy.core.expr import Expr
from sympy.core.exprtools import decompose_power
from sympy.core.function import AppliedUndef
from sympy.core.numbers import ComplexInfinity, Float, ImaginaryUnit, Integer, Number, NumberSymbol, Rational
from sympy.core.sorting import default_sort_key
from sympy.core.symbol import Dummy, Symbol, Wild
from sympy.logic.boolalg import BooleanAtom, BooleanFunction

from satassume import sympy_api as A
from satassume.knowledge.domain import constructed_noncommutative
from satassume.knowledge.templates import _may_be_nan, registry
from satassume.knowledge.templates._common import const_value
from satassume.knowledge.templates.atoms import _CONST_BASIS
from satassume.theories.euf.euf_adapter import _STRUCTURAL, _inherits_from_basic
from satassume.theories.lra.lra_adapter import _BAD
from sympy.integrals.transforms import IntegralTransform

REASONS = (
    'non-basic',            # a non-Basic value in a query or a term's args
    'class-no-row',         # a class conversion can't row
    'non-default-registry',
    'sum-product-integral',
    'args-eq-not-is',       # R12
    'out-of-scope',
    'too-deep',
    'complex-unbounded',    # a ComplexRootOf: complex(t) has no bound (CRootOf(x**50 - x + 1, 3): over 120 s). Planner's ruling pending
)

# Tokens of a value: Rust's `V`, solver_rs/src/term/table.rs. Keep the two in step.
T_NONE, T_FALSE, T_TRUE, T_INT, T_BIG, T_STR, T_TUPLE, T_TERM, T_RAT, T_OPAQUE = range(10)
_I64 = 1 << 63

# Kind enum: Rust's `Kind`, same order. Exact class only: a subclass is Other, or Function for a function.
KINDS = ('Add', 'Mul', 'Pow', 'Symbol', 'Dummy', 'Wild', 'Integer', 'Rational', 'Float', 'Zero', 'One', 'Half',
         'NegativeOne', 'Infinity', 'NegativeInfinity', 'NaN', 'ComplexInfinity', 'ImaginaryUnit', 'Pi', 'Exp1',
         'GoldenRatio', 'TribonacciConstant', 'EulerGamma', 'Catalan', 'AppliedUndef', 'Function', 'Other')
_KIND_OF = {Add: 'Add', Mul: 'Mul', Pow: 'Pow', Symbol: 'Symbol', Dummy: 'Dummy', Wild: 'Wild', Integer: 'Integer',
            Rational: 'Rational', Float: 'Float'}
for _s in (S.Zero, S.One, S.Half, S.NegativeOne, S.Infinity, S.NegativeInfinity, S.NaN, S.ComplexInfinity,
           S.ImaginaryUnit, S.Pi, S.Exp1, S.GoldenRatio, S.TribonacciConstant, S.EulerGamma, S.Catalan):
    _KIND_OF[type(_s)] = type(_s).__name__
_KIND_INDEX = {n: i for i, n in enumerate(KINDS)}

# Class flags (R2), in bit order: Rust's `flag` constants.
FLAGS = ('is_Add', 'is_Mul', 'is_Pow', 'is_Atom', 'is_Number', 'is_Rational', 'is_Integer', 'is_Float', 'is_Symbol',
         'is_Dummy', 'is_Order', 'is_Function', 'is_NumberSymbol', 'is_commutative_fixed')
# Term fact bits, in order: Rust's `fact` constants.
F_NUMBER, F_NAN, F_BAD, F_FLOAT, F_UNDEF, F_MAYBE_NAN, F_READ, F_COMMUTATIVE = 1, 2, 4, 8, 16, 32, 64, 128
# Class flags past FLAGS: `flag::PLAIN_OPS`, `flag::PLAIN_BASE`. The algebra refuses a class that overrides any of these.
_PLAIN_OPS, _PLAIN_BASE = 1 << 14, 1 << 15
_OPS = ('__neg__', '__add__', '__radd__', '__sub__', '__rsub__', '__mul__', '__rmul__', '__truediv__', 'as_coeff_Add',
        'as_coeff_Mul', 'as_coeff_mul')

# Rust can build these with none in the input, so their rows are always sent, first.
_PREFIX = (Add, Mul, Pow, Integer, Rational, type(S.Zero), type(S.One), type(S.NegativeOne), type(S.Half))
_KEPT_CLASSES = (Sum, Product, Integral)
_CONSTANT = (Number, NumberSymbol, ImaginaryUnit, ComplexInfinity)  # as `atoms.py` registers constant_units
# The formula's skeleton carries no term facts: section 9 has them in the formula table, not the term rows.
_SKELETON = (AppliedPredicate, Predicate, BooleanFunction, BooleanAtom)


class Kept:
    """The query runs on Python as if Rust didn't exist. `reason` is one of REASONS."""
    __slots__ = ('reason', 'detail')

    def __init__(self, reason, detail=''):
        assert reason in REASONS, reason
        self.reason = reason
        self.detail = detail


class Converted:
    """`tables`: for sa_solver.TermTable. `ids`: {term: id} by SymPy's hash and ==. `objects`: term by id."""
    __slots__ = ('__dict__', 'tables', 'ids', 'objects', 'counts', 'classes')

    def __init__(self, tables, ids, objects, counts, classes):
        self.tables = tables
        self.ids = ids
        self.objects = objects
        self.counts = counts
        self.classes = classes


class _Keep(Exception):
    def __init__(self, reason, detail=''):
        self.reason = reason
        self.detail = detail


def _template_name(f):
    return f'{getattr(f, "__module__", "?")}.{getattr(f, "__qualname__", repr(type(f)))}'


class _Walk:
    def __init__(self):
        self.ids = {}
        self.objects = []
        self.strings = []
        self.string_ids = {}
        self.classes = {}
        self.class_rows = []
        self.opaque = []
        self.counts = {'atom_symbol_reads': 0, 'atom_constant_reads': 0, 'keys': 0, 'decompose_power': 0, 'pow_base_not_input': 0, 'opaque': 0, 'closed': 0}

    def s(self, text):
        i = self.string_ids.get(text)
        if i is None:
            i = self.string_ids[text] = len(self.strings)
            self.strings.append(text)
        return i

    # ---- values

    def enc(self, v, out, key=False):
        """One value's tokens. In a key a Rational is its value, since keys compare by it. Elsewhere a Basic is a term."""
        if isinstance(v, Basic):        # first: SymPy registers Integer as numbers.Integral
            if key and isinstance(v, Rational):
                out.append(T_RAT)
                self.enc_int(v.p, out)
                self.enc_int(v.q, out)
            else:
                out += (T_TERM, self.term(v))
        elif v is None:
            out.append(T_NONE)
        elif v is True:
            out.append(T_TRUE)
        elif v is False:
            out.append(T_FALSE)
        elif isinstance(v, numbers.Integral):
            self.enc_int(int(v), out)
        elif isinstance(v, str):
            out += (T_STR, self.s(v))
        elif isinstance(v, tuple):
            out += (T_TUPLE, len(v))
            for x in v:
                self.enc(x, out, key)
        else:
            self.counts['opaque'] += 1
            out += (T_OPAQUE, len(self.opaque))
            self.opaque.append(v)

    def enc_int(self, n, out):
        if -_I64 < n < _I64:
            out += (T_INT, n)
        else:
            out += (T_BIG, self.s(str(n)))

    def term(self, t):
        """The id of a term not necessarily walked yet: a Basic in a key or a hashable content that isn't in `.args`."""
        i = self.ids.get(t)
        if i is None:
            self.walk(t)
            i = self.ids[t]
        return i

    # ---- the walk

    def walk(self, root):
        """Preorder over `.args`, ids by first sight."""
        ids, objects = self.ids, self.objects
        stack = [root]
        while stack:
            t = stack.pop()
            if not isinstance(t, Basic):
                raise _Keep('non-basic', type(t).__name__)
            if t in ids:
                continue
            ids[t] = len(objects)
            objects.append(t)
            if isinstance(t, _KEPT_CLASSES):
                raise _Keep('sum-product-integral', type(t).__name__)
            self.klass(type(t))
            args = t.args
            if len(args) > 1:
                seen = {}
                for a in args:
                    if not isinstance(a, Basic):
                        raise _Keep('non-basic', type(a).__name__)
                    if seen.setdefault(a, a) is not a:
                        raise _Keep('args-eq-not-is', type(t).__name__)
            stack.extend(reversed(args))

    def klass(self, cls):
        c = self.classes.get(cls)
        if c is not None:
            return c
        c = self.classes[cls] = len(self.classes)
        name = cls.__name__
        try:
            rank = ordering_of_classes.index(name)
        except ValueError:
            rank = -1
        if issubclass(cls, AppliedUndef):
            kind = 'AppliedUndef'
        else:
            kind = _KIND_OF.get(cls) or ('Function' if issubclass(cls, Function) else 'Other')
        flags = 0
        for bit, f in enumerate(FLAGS):
            if getattr(cls, f, False) is True:
                flags |= 1 << bit
        if (issubclass(cls, Expr) and not getattr(cls, 'is_Order', False) and cls._op_priority == Expr._op_priority
                and all(getattr(cls, f) is getattr(Expr, f) for f in _OPS)):
            flags |= _PLAIN_OPS
        if issubclass(cls, Expr) and cls.as_base_exp is Expr.as_base_exp:
            flags |= _PLAIN_BASE
        try:
            ckey = cls.class_key()
            found = registry.templates_for(cls)
        except Exception as e:
            raise _Keep('class-no-row', f'{name}: {type(e).__name__}')
        names = tuple(sorted(_template_name(f) for f in found))
        if any(not getattr(f, '__module__', '').startswith('satassume.') for f in found):
            raise _Keep('non-default-registry', name)
        out = self.class_rows
        out += (T_TUPLE, 8)
        out += (T_STR, self.s(name), T_INT, _KIND_INDEX[kind], T_INT, rank, T_INT, flags)
        self.enc(ckey, out)
        self.enc(names, out)
        self.enc(_structural_class(cls), out)
        self.enc(cls._hashable_content is not Basic._hashable_content, out)
        return c

    # ---- rows

    def term_row(self, t, out):
        out += (T_TUPLE, 8, T_INT, self.classes[type(t)], T_TUPLE, len(t.args))
        ids = self.ids
        for a in t.args:
            out += (T_TERM, ids[a])
        if type(t)._hashable_content is Basic._hashable_content:
            out.append(T_NONE)
        else:
            self.enc(tuple(t._hashable_content()), out)
        if isinstance(t, _SKELETON):
            out += (T_NONE, T_NONE, T_INT, 0, T_INT, 0, T_NONE)
            return
        # The key, and the facts of section 9's Term facts row, each read as its site reads it.
        self.counts['keys'] += 1
        try:
            k = default_sort_key(t)
        except Exception:
            out.append(T_NONE)
        else:
            self.enc(k, out, True)
        free = t.free_symbols
        # Ordered by id: free_symbols is a set, so no hash order reaches the row.
        fid = sorted(self.term(x) for x in free)
        out += (T_TUPLE, len(fid))
        for i in fid:
            out += (T_TERM, i)
        number = getattr(t, 'is_number', False) is True
        bits = F_READ
        if number:
            bits |= F_NUMBER
        if t.has(S.NaN):
            bits |= F_NAN
        if t.has(*_BAD):
            bits |= F_BAD
        if t.has(Float):
            bits |= F_FLOAT
        if t.atoms(AppliedUndef):
            bits |= F_UNDEF
        if _may_be_nan(t):
            bits |= F_MAYBE_NAN
        if t.is_commutative is True:
            bits |= F_COMMUTATIVE
        out += (T_INT, bits, T_INT, constructed_noncommutative(t))
        if number and isinstance(t, Expr):
            self.closed(t, out)
        else:
            out.append(T_NONE)

    def atom_rows(self):
        """Section 9's Symbols and Atomic numbers rows, one per input atom: what `atoms.py`'s templates read. Rust's
        `_CONST_BASIS` comes from the offline file and has to be this one, in this order; it refuses another length."""
        out = []
        n = 0
        for i, t in enumerate(self.objects):
            if isinstance(t, Symbol):
                self.counts['atom_symbol_reads'] += 1
                self.enc((i, 0, tuple(t.assumptions0.items())), out)
            elif isinstance(t, _CONSTANT):
                self.counts['atom_constant_reads'] += 1
                self.enc((i, 1, tuple(const_value(t, p) for p in _CONST_BASIS)), out)
            else:
                continue
            n += 1
        return out, n

    def closed(self, t, out):
        """Closed term: is_finite and complex() as bit patterns (R17, section 3). Either read can write SymPy's caches."""
        if isinstance(t, ComplexRootOf):    # a term only a key reached; the rest are refused before any row
            raise _Keep('complex-unbounded', type(t).__name__)
        self.counts['closed'] += 1
        out += (T_TUPLE, 3)
        self.enc(t.is_finite, out)
        try:
            z = complex(t)
        except Exception:
            out += (T_NONE, T_NONE)
            return
        for x in (z.real, z.imag):
            self.enc_int(struct.unpack('<q', struct.pack('<d', x))[0], out)

    def power_rows(self, n):
        """(term, base id or -1, exponent): decompose_power of each term whose as_base_exp can split. Last, so a base
        counts as an input term wherever in the walk it appears. Never walks the base: that's the refusal's point."""
        out = []
        for i in range(n):
            t = self.objects[i]
            if (not isinstance(t, Expr) or t.is_Mul or t.is_Number
                    or type(t).as_base_exp is Expr.as_base_exp or getattr(t, 'is_number', False)):
                continue
            self.counts['decompose_power'] += 1
            base, e = decompose_power(t)
            b = self.ids.get(base, -1)
            if b < 0:
                self.counts['pow_base_not_input'] += 1
            out += (T_TUPLE, 3, T_INT, i, T_INT, b)
            self.enc(e, out)
        return out


def _structural_class(cls):
    """euf_adapter.structural's per-class part: a term is structural when this holds and it has args."""
    return (issubclass(cls, _STRUCTURAL) and not issubclass(cls, IntegralTransform)
            and _inherits_from_basic(cls, "free_symbols") and _inherits_from_basic(cls, "bound_symbols"))


def default_engine_settings(eng):
    """Section 9's Settings row. None if the engine isn't on the default registry."""
    from satassume.relations import default_specs
    if eng._templates != registry.facts_for:
        return None
    if tuple(r.name for r in eng._relation_specs) != tuple(r.name for r in default_specs()):
        return None
    return (eng.discovery_budget, eng._transfer, eng._uninterpreted, eng._relevance)


def _rel(parts, rel):
    name, lhs, rhs = parts
    if not rel or not (A._is_scalar(lhs) and A._is_scalar(rhs)):
        raise A.Unsupported('relation', 'relation')
    return ('rel', name, lhs, rhs)


_CONNECTIVE = ((A._SAnd, 'and'), (A._SOr, 'or'), (A._SNot, 'not'), (A._SImplies, 'implies'),
               (A._SEquivalent, 'equivalent'), (A._SXor, 'xor'), (A._SITE, 'ite'))


def formula(e, rel, opq=False):
    """Mirrors sympy_api.to_formula, reads only, and raises Unsupported where it does. Relation atoms stay (name, lhs,
    rhs): relation_atom builds terms and is component 4. `out_of_scope` is NOT this: it's a diagnostic, and it names a
    category for relation queries the engine answers (sa-port-10's first run kept those by mistake)."""
    if e is True or isinstance(e, A._BTrue):
        return ('true',)
    if e is False or isinstance(e, A._BFalse):
        return ('false',)
    if isinstance(e, A._Applied):
        name = str(e.function.name)
        if name == 'is_true' and len(e.arguments) == 1:
            a = e.arguments[0]
            if a is True or isinstance(a, A._BTrue):
                return ('true',)
            if a is False or isinstance(a, A._BFalse):
                return ('false',)
        if name in A.RELATION_PREDICATES or name == 'is_true':
            parts = A.relation_parts(e)
            if parts is not None:
                return _rel(parts, rel)
        c = A._applied_category(e)
        if c is not None:
            if opq and c in A.OPAQUE_CATEGORIES:
                return ('opaque', e)
            raise A.Unsupported(c, c)
        return ('atom', name) + tuple(e.arguments)
    for cls, tag in _CONNECTIVE:
        if isinstance(e, cls):
            return (tag,) + tuple(formula(a, rel, opq) for a in e.args)
    if isinstance(e, A._Relational):
        return _rel(A.relation_parts(e), rel)
    raise A.Unsupported('other', 'other')


def convert(proposition, assumptions, eng):
    """Tables for this query, or `Kept`."""
    try:
        settings = default_engine_settings(eng)
        if settings is None:
            return Kept('non-default-registry')
        rel = bool(eng.relation_specs)
        try:
            fp = formula(proposition, rel)
            fa = None if assumptions is True else formula(assumptions, rel, True)
        except A.Unsupported:
            return Kept('out-of-scope')
        w = _Walk()
        for cls in _PREFIX:
            w.klass(cls)
        for x in (proposition, assumptions):
            if x is True or x is False:
                continue
            w.walk(x)
        for t in w.objects:                 # before any row, so no complex(t) has run on a query that stays on Python
            if isinstance(t, ComplexRootOf):
                raise _Keep('complex-unbounded', type(t).__name__)
        form = []
        w.enc((fp, fa), form)
        rows = []
        i = 0
        while i < len(w.objects):       # grows if a key or a content holds a term `.args` doesn't reach
            w.term_row(w.objects[i], rows)
            i += 1
        powers = w.power_rows(len(w.objects))
        atoms, n_atoms = w.atom_rows()
    except _Keep as e:
        return Kept(e.reason, e.detail)
    except RecursionError:
        return Kept('too-deep')
    sets = []
    w.enc(settings, sets)
    tables = dict(strings=w.strings, classes=w.class_rows, terms=rows, powers=powers, settings=sets, formula=form,
                  n_classes=len(w.classes), n_terms=len(w.objects), n_powers=_count(powers), n_opaque=len(w.opaque),
                  atoms=atoms, n_atoms=n_atoms)
    return Converted(tables, w.ids, w.objects, w.counts, w.classes)


def _count(powers):
    n = 0
    i = 0
    while i < len(powers):      # (T_TUPLE, 3, T_INT, id, T_INT, base, <exponent: T_INT n or T_BIG s>)
        n += 1
        i += 8
    return n
