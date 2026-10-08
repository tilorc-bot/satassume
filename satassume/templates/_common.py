"""Helpers shared by the template modules (no SymPy imports here).

Templates describe their rules as *index-based specs*: a literal is
``(k, pred, pos)`` where ``k`` indexes a tuple of objects (the arguments
followed by the node), and a rule is ``(premises, conclusion)`` meaning
``And(premises) -> Or(conclusion)``.  Only these clausal shapes are emitted,
so compilation needs no Tseitin variables.

A spec list depends only on the *pattern* of a node (its class, arity and
which argument positions hold which constants), so it is generated once
per pattern, resolved against the constants (a premise a constant satisfies
is dropped, one it violates kills the rule, a violated conclusion negates the
premises), pruned of subsumed rules, and cached.  Per node only the atoms
are instantiated.  No ``is_*`` property is ever read on a symbolic object,
except the structural ``is_commutative`` (``atoms.structural_commutative``).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from ..formula import And, Implies, Not, Or, P
from ..rules import NPRED, PRED_INDEX, PREDICATES, RULE_FREE, RULE_INSTANTIATED, unit_propagate

#: The predicate vocabulary templates may emit.
VOCAB = frozenset({
    'algebraic', 'antihermitian', 'commutative', 'complex', 'composite',
    'even', 'extended_negative', 'extended_nonnegative',
    'extended_nonpositive', 'extended_nonzero', 'extended_positive',
    'extended_real', 'finite', 'hermitian', 'imaginary', 'infinite',
    'integer', 'irrational', 'negative', 'negative_infinite', 'noninteger',
    'nonnegative', 'nonpositive', 'nonzero', 'odd', 'polar', 'positive',
    'positive_infinite', 'prime', 'rational', 'real', 'transcendental',
    'zero',
})

#: Sign predicate swapped when multiplying by a negative number.
SIGN_FLIP = {
    'positive': 'negative', 'negative': 'positive',
    'nonnegative': 'nonpositive', 'nonpositive': 'nonnegative',
    'extended_positive': 'extended_negative',
    'extended_negative': 'extended_positive',
    'extended_nonnegative': 'extended_nonpositive',
    'extended_nonpositive': 'extended_nonnegative',
}

Lit = Tuple[int, str, bool]
Rule = Tuple[Tuple[Lit, ...], Tuple[Lit, ...]]


def is_constant(obj) -> bool:
    """True for SymPy atoms whose ``is_*`` properties are static facts.

    Both flags are class attributes on atoms: no assumption query is made.
    """
    return bool(obj.is_Atom and obj.is_number)


def const_key(obj):
    """Cache-key component for a constant (``Float(2.0) == Integer(2)``!)."""
    return (type(obj), obj)


def lits(ks, pred: str, pos: bool = True) -> List[Lit]:
    return [(k, pred, pos) for k in ks]


class Rules:
    """Collects rule specs."""
    __slots__ = ('rules',)

    def __init__(self):
        self.rules: List[Tuple[list, list]] = []

    def rule(self, premises, conclusion) -> None:
        """``And(premises) -> conclusion`` (a literal or a list = ``Or``)."""
        self.rules.append((list(premises),
                           conclusion if isinstance(conclusion, list) else [conclusion]))

    def equiv(self, cond, a: Lit, b: Lit) -> None:
        """``cond -> (a <-> b)`` as two rules."""
        self.rule([*cond, a], b)
        self.rule([*cond, b], a)


def ge2_alternatives(k: int):
    """Premise alternatives meaning ``objs[k]`` is an integer >= 2."""
    return ([(k, 'prime', True)], [(k, 'composite', True)],
            [(k, 'even', True), (k, 'positive', True)])


def const_value(c, pred: str):
    """Static truth value of ``pred`` for the constant ``c`` (None if the
    constant does not decide it).  Beyond the old-system property this
    derives the new-system predicates the old system does not store."""
    v = getattr(c, 'is_' + pred, None)
    if v is None:
        if pred in _SIGNED_INFINITE:
            inf, sign = c.is_infinite, getattr(c, 'is_extended_' + _SIGNED_INFINITE[pred])
            if inf is False or sign is False:
                v = False
            elif inf and sign:
                v = True
        elif pred == 'hermitian':
            v = c.is_real
        elif pred == 'antihermitian':
            z, im = c.is_zero, c.is_imaginary
            v = True if (z or im) else (False if z is False and im is False else None)
    return v


def _resolve_lit(lit: Lit, consts):
    c = dict.get(consts, lit[0])
    if c is not None:
        i = PRED_INDEX.get(lit[1])
        if i is None:
            v = const_value(c, lit[1])
            if _REC is not None:
                _REC.raw = True
        else:
            v = const_facts(c)[i]
        if v is not None:
            return v is lit[2]
        # A constant decides all it ever will right here (its node would
        # only repeat these static facts), so a rule with an undecidable
        # literal about a constant (``polar(2)``) can never fire: drop it
        # rather than make the constant a node of the engine.
        return None
    return lit


_SIGNED_INFINITE = {'positive_infinite': 'positive', 'negative_infinite': 'negative'}


def resolve(rules, consts: Dict[int, Any]) -> List[Rule]:
    """Resolve constants, then drop duplicate and subsumed rules."""
    keyed = []
    for prem, concl in rules:
        ps = []
        for lit in prem:
            r = _resolve_lit(lit, consts)
            if r is True:
                continue
            if r is False or r is None:
                break
            ps.append(r)
        else:
            cs = []
            for lit in concl:
                r = _resolve_lit(lit, consts)
                if r is True or r is None:
                    break
                if r is not False:
                    cs.append(r)
            else:
                if not cs:
                    # A constant violates the conclusion: the premises
                    # cannot all hold.
                    if not ps:
                        raise ValueError("template asserts a contradiction")
                    cs = [(k, pred, not pos) for k, pred, pos in ps]
                    ps = []
                keyed.append((len(ps), frozenset(ps), tuple(cs), tuple(ps)))
    keyed.sort(key=lambda t: t[0])
    seen: Dict[tuple, list] = {}
    out: List[Rule] = []
    for _, key, cs, ps in keyed:
        lst = seen.setdefault(cs, [])
        if any(k <= key for k in lst):
            continue
        lst.append(key)
        out.append((ps, cs))
    return out


def instantiate(resolved: List[Rule], objs) -> List:
    """Build the formulas of ``resolved`` over the concrete ``objs``."""
    atoms: Dict[Tuple[int, str], P] = {}
    out = []

    def mk(lit):
        key = (lit[0], lit[1])
        a = atoms.get(key)
        if a is None:
            a = atoms[key] = P(lit[1], objs[lit[0]])
        return a if lit[2] else Not(a)

    for ps, cs in resolved:
        c = mk(cs[0]) if len(cs) == 1 else Or(*[mk(l) for l in cs])
        if not ps:
            out.append(c)
        elif len(ps) == 1:
            out.append(Implies(mk(ps[0]), c))
        else:
            out.append(Implies(And(*[mk(l) for l in ps]), c))
    return out


class Pattern:
    """The resolved rules of one template pattern, also as clauses in
    *slot space*: a literal is ``(k, pidx, neg)`` for predicate index
    ``pidx`` of the object in slot ``k``.  Slots below ``node`` are the
    direct arguments, slot ``node`` is the node, slots above are derived
    nodes (``2*e``, ``x - 1``, ...).

    ``complete`` is set on a unit pattern whose facts, closed under the rule
    base, decide every predicate the rule base mentions: the engine then
    asserts the closed units and skips the rule base for the node."""
    __slots__ = ('rules', 'node', 'clauses', 'used', 'child_preds', 'complete')

    def __init__(self, rules: List[Rule], node: int):
        self.rules = rules
        self.node = node
        self.complete = False
        clauses = []
        used = set()
        child_preds: Dict[int, set] = {}
        for ps, cs in rules:
            lits = [(k, PRED_INDEX[p], pos) for k, p, pos in ps]
            lits += [(k, PRED_INDEX[p], not pos) for k, p, pos in cs]
            lits = list(dict.fromkeys(lits))
            if any((k, i, not neg) in lits for k, i, neg in lits):
                continue    # tautology
            npreds = frozenset(i for k, i, _ in lits if k == node)
            # internal literal = 2*base_of_slot + (2*pidx + neg)
            clauses.append((tuple(lits), npreds, tuple((k, 2 * i + (1 if neg else 0)) for k, i, neg in lits)))
            for k, i, _ in lits:
                used.add(k)
                if k != node:
                    child_preds.setdefault(k, set()).add(i)
        self.clauses = clauses
        self.used = tuple(sorted(used))
        self.child_preds = {k: frozenset(v) for k, v in child_preds.items()}


class Compiled:
    """A pattern applied to concrete objects: what a template hands the
    engine.  ``instantiate(c.pattern.rules, c.objs)`` gives the formulas."""
    __slots__ = ('objs', 'pattern')

    def __init__(self, objs, pattern: Pattern):
        self.objs = objs
        self.pattern = pattern

    def formulas(self) -> List:
        return instantiate(self.pattern.rules, self.objs)


#: compiled patterns by the key the template passes to :func:`facts` or
#: :func:`units`.  Keyed on that key and the registry epoch: a key names
#: one generator only among the templates registered at a time, and
#: ``TemplateRegistry.register`` (the only way the set of templates
#: changes) empties this table before bumping the epoch, so a later
#: template that reuses a key never gets an earlier template's pattern.
#: Registered with ``satassume.memos.PROCESS`` as ``"epoch"``.
_CACHE: Dict[Any, Pattern] = {}
MAX_CACHE = 4096


def facts(key, gen: Callable[[], list], consts: Dict[int, Any], objs, node: int) -> Compiled:
    """The (cached) resolved rules of ``key`` applied to ``objs``; slot
    ``node`` holds the node itself.

    A key with constants is also looked up by its *value signature* (see
    :data:`_SIG`): a pattern compiled for other values of the constants is
    reused when the new values give the same outcome to everything the
    compilation read about them."""
    pat = _CACHE.get(key)
    if pat is None:
        if len(_CACHE) >= MAX_CACHE:
            _CACHE.clear()
            _SIG.clear()
        if consts and SIGNATURES and type(consts) is ConstView:
            pat = _signature_facts(key, gen, consts, node)
        else:
            pat = Pattern(resolve(gen(), consts), node)
        _CACHE[key] = pat
    return Compiled(objs, pat)


class ConstView(dict):
    """The constants of a node by slot, as the template hands them to its
    rule generator.  While a pattern is compiled for :data:`_SIG`, reading a
    value outside a table guard (``consts[k]``, ``consts.get(k)``, iterating
    the values) marks the compilation as value-dependent, so its pattern is
    kept under the exact key only.  ``k in consts`` (which slots hold
    constants) is part of the signature key and free to read."""
    __slots__ = ()

    def __getitem__(self, k):
        _raw_read()
        return dict.__getitem__(self, k)

    def get(self, k, default=None):
        _raw_read()
        return dict.get(self, k, default)

    def values(self):
        _raw_read()
        return dict.values(self)

    def items(self):
        _raw_read()
        return dict.items(self)

    def __iter__(self):
        _raw_read()
        return dict.__iter__(self)

    def copy(self):
        _raw_read()
        return dict.copy(self)

    def __eq__(self, other):
        _raw_read()
        return dict.__eq__(self, other)

    def __ne__(self, other):
        _raw_read()
        return dict.__ne__(self, other)

    __hash__ = None

    def __or__(self, other):
        _raw_read()
        return dict.__or__(self, other)

    def __ror__(self, other):
        _raw_read()
        return dict.__ror__(self, other)

    def pop(self, *a):
        _raw_read()
        return dict.pop(self, *a)

    def popitem(self):
        _raw_read()
        return dict.popitem(self)

    def setdefault(self, *a):
        _raw_read()
        return dict.setdefault(self, *a)


class _Recorder:
    """What one compilation read about its constants: ``guards`` the table
    guard calls ``(guard, name, rest, result)`` whose context holds the
    :class:`ConstView` under ``name`` (``rest``: the other context items);
    ``raw`` a value read outside them."""
    __slots__ = ('view', 'guards', 'results', 'seen', 'raw', 'depth', 'ctxs', 'keep')

    def __init__(self, view):
        self.view = view
        self.guards = []
        self.results = []
        self.seen = set()
        self.ctxs = {}
        self.keep = []
        self.raw = False
        self.depth = 0


#: the recorder of the compilation in progress (None: not recording)
_REC = None


def _raw_read():
    rec = _REC
    if rec is not None and not rec.depth:
        rec.raw = True


def guard(fn, ctx):
    """``fn(ctx)`` for a table guard; recorded when ``ctx`` holds the
    constants being compiled (see :data:`_SIG`)."""
    rec = _REC
    if rec is None:
        return fn(ctx)
    rest = rec.ctxs.get(id(ctx))
    if rest is None:
        view = rec.view
        name = None
        for k, v in ctx.items():
            if v is view:
                name = k
                break
        if name is None:
            rest = ()
        else:
            rest = (name, tuple([(k, v) for k, v in ctx.items() if k != name]))
            try:
                hash(rest)
            except TypeError:
                rec.raw = True      # cannot be keyed: keep the pattern exact
                rest = ()
        rec.ctxs[id(ctx)] = rest
        rec.keep.append(ctx)        # ids stay unique while recording
    if not rest:
        return fn(ctx)
    rec.depth += 1
    try:
        r = bool(fn(ctx))
    finally:
        rec.depth -= 1
    tag = (fn, rest)
    if tag not in rec.seen:
        rec.seen.add(tag)
        rec.guards.append(tag)
        rec.results.append(r)
    return r


#: Patterns by *value signature*.  A compilation is a deterministic
#: function of the key's parts other than the constant values, the slots
#: that hold constants, the outcomes of the table guards it evaluated on
#: the constants (:class:`ConstView` and :func:`guard` record them; a
#: compilation that read a value any other way is not entered here), and
#: the values of the constant literals of the generated rules, which is all
#: ``resolve`` can read (``const_value`` of each).
#: ``_SIG[skey]`` (``skey``: the key with its constant values abstracted,
#: :func:`_abstract`) lists *probes* ``(guards, facts, table)``: the reads
#: of a compilation (the guard calls and the constant literals of its rules)
#: and ``table[answers] = pattern``, where ``answers`` are the guard
#: outcomes then the literals' values.  New constants whose answers to
#: a probe's reads are in its table get that pattern: the compilation would
#: have read the same things in the same order, with the same results.
#: Emptied with ``_CACHE``.  Registered with ``satassume.memos.PROCESS``
#: as ``"epoch"``.
_SIG: Dict[Any, list] = {}
#: switch for :data:`_SIG` (False: exact keys only)
SIGNATURES = True


class _Slot:
    """Stands for a constant value in a signature key."""
    __slots__ = ()

    def __repr__(self):
        return '<const>'


_SLOT = _Slot()


def _abstract(key, ids):
    """``key`` with each constant value that it holds as ``type(c), c`` (the
    form of :func:`const_key` and :func:`pattern_key`) replaced by
    ``_SLOT, _SLOT``; anything else, values derived from a constant
    included, stays as it is."""
    if type(key) is not tuple:
        return key
    out = []
    i, n = 0, len(key)
    while i < n:
        x = key[i]
        if i + 1 < n and id(key[i + 1]) in ids and type(key[i + 1]) is x:
            out += (_SLOT, _SLOT)
            i += 2
            continue
        out.append(_abstract(x, ids) if type(x) is tuple else x)
        i += 1
    return tuple(out)


def _captures(obj, ids, depth=0) -> bool:
    """``obj`` is, or holds in a tuple, list or plain dict (to depth 2), one
    of the objects ``ids``."""
    if id(obj) in ids:
        return True
    if depth < 2:
        t = type(obj)
        if t is tuple or t is list:
            return any(_captures(x, ids, depth + 1) for x in obj)
        if t is dict:
            return any(_captures(x, ids, depth + 1) for x in obj.values())
    return False


def _signature_facts(key, gen, consts, node) -> Pattern:
    global _REC
    ids = {id(c) for c in dict.values(consts)}
    skey = _abstract(key, ids)
    if skey == key or any(_captures(cell.cell_contents, ids)
                          for cell in getattr(gen, '__closure__', None) or ()):
        # nothing to share, or the generator holds a constant value itself
        # (not through the ConstView): exact key only
        return Pattern(resolve(gen(), consts), node)
    probes = _SIG.get(skey)
    classes = None
    if probes is not None:
        classes = tuple([const_class(c) for _, c in sorted(dict.items(consts))])
        for guards, table in probes:
            pat = table.get((_answers(guards, consts), classes))
            if pat is not None:
                return pat
    rec = _REC = _Recorder(consts)
    try:
        pat = Pattern(resolve(gen(), consts), node)
    finally:
        _REC = None
    if not rec.raw:
        guards = tuple(rec.guards)
        if classes is None:
            classes = tuple([const_class(c) for _, c in sorted(dict.items(consts))])
        answers = (tuple(rec.results), classes)
        if probes is None:
            probes = _SIG[skey] = []
        for g, table in probes:
            if g == guards:
                table[answers] = pat
                break
        else:
            probes.append((guards, {answers: pat}))
    return pat


_FAILED = object()


def _answers(guards, consts) -> tuple:
    out = []
    ctxs = {}
    for fn, (name, rest) in guards:
        ctx = ctxs.get(rest)
        if ctx is None:
            ctx = ctxs[rest] = dict(rest)
            ctx[name] = consts
        try:
            out.append(bool(fn(ctx)))
        except Exception:   # noqa: BLE001  (a read the compilation did not make)
            return (_FAILED,)
    return tuple(out)


def const_class(c):
    """The *fact class* of a constant: constants of one class have the
    same ``const_value`` for every predicate.  An integer's facts are fixed
    by its sign, parity and whether it is 1, a prime or composite; a
    non-integer rational's by its sign.  Any other constant is its own
    class (:func:`const_key`).  ``tests/test_value_signatures.py`` checks
    the claim against SymPy."""
    k = (type(c), c)
    cls = _CLASS.get(k)
    if cls is None:
        if len(_CLASS) >= _CFACTS_MAX:
            _CLASS.clear()
        if c.is_Integer:
            from sympy.ntheory.primetest import isprime
            p = c.p
            cls = ('Z', (p > 0) - (p < 0), p & 1,
                   0 if p <= 0 else 1 if p == 1 else 2 if isprime(p) else 3)
        elif c.is_Rational:
            cls = ('Q', (c.p > 0) - (c.p < 0))
        else:
            cls = k
        _CLASS[k] = cls
    return cls


#: ``const_value`` of every predicate (by ``PRED_INDEX``) for the constants
#: of a fact class (:func:`const_class`), filled lazily; and the class of a
#: constant by :func:`const_key`.  Pure functions of their keys.
#: Registered with ``satassume.memos.PROCESS``.
_CFACTS: Dict[Any, Any] = {}
_CLASS: Dict[Any, Any] = {}
_CFACTS_MAX = 4096
_UNKNOWN = object()


def const_facts(c):
    """``const_value(c, pred)`` by predicate index (``const_facts(c)[i]``),
    shared by the constants of a fact class (:func:`const_class`) and
    computed on first use of each entry."""
    cls = const_class(c)
    fv = _CFACTS.get(cls)
    if fv is None:
        if len(_CFACTS) >= _CFACTS_MAX:
            _CFACTS.clear()
        fv = _CFACTS[cls] = _Facts(c)
    return fv


class _Facts:
    """``const_value(c, PREDICATES[i])`` as ``self[i]``, memoized."""
    __slots__ = ('c', 'v')

    def __init__(self, c):
        self.c = c
        self.v = [_UNKNOWN] * NPRED

    def __getitem__(self, i):
        v = self.v[i]
        if v is _UNKNOWN:
            v = self.v[i] = const_value(self.c, PREDICATES[i])
        return v


def units(key, gen: Callable[[], list], obj) -> Compiled:
    """Unit facts about one object: ``gen()`` returns ``(pred, value)``
    pairs; the pattern is cached under ``key``.  The facts are closed under
    the rule base (unit propagation); when the closure decides every
    predicate the rule base mentions the pattern is ``complete``."""
    pat = _CACHE.get(key)
    if pat is None:
        if len(_CACHE) >= MAX_CACHE:
            _CACHE.clear()
        facts = list(gen())
        lits = [PRED_INDEX[pred] + 1 if value else -(PRED_INDEX[pred] + 1) for pred, value in facts]
        closed = unit_propagate(RULE_INSTANTIATED, lits)
        if closed is not None:
            facts = [(PREDICATES[abs(l) - 1], l > 0) for l in sorted(closed, key=abs)]
        pat = Pattern([((), ((0, pred, value),)) for pred, value in facts], 0)
        if closed is not None:
            decided = {abs(l) - 1 for l in closed}
            pat.complete = len(decided | RULE_FREE) == NPRED
        _CACHE[key] = pat
    return Compiled((obj,), pat)


def consts_of(args) -> ConstView:
    return ConstView([(k, a) for k, a in enumerate(args) if a.is_Atom and a.is_number])


def pattern_key(tag, n: int, consts: Dict[int, Any]):
    return (tag, n, tuple((k, type(c), c) for k, c in sorted(dict.items(consts))))
