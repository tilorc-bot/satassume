"""The atoms family of runtime knowledge (component 6, issue 323), wired into the real engine.

`install()` makes these changes, from outside satassume, and returns a function that undoes them. Pure Python stays the
default. The Rust backend installs it by default (`from_env()`, called by `rust_plugin.py` and `live.py` in rust mode,
after `term_live`'s); SLICE_KNOWLEDGE=py keeps it off there.

1. `term_live`'s wrapper on `sympy_api._ask` holds the query's table, and this reads it. Nothing outlives the query: ids
   mean nothing outside it.
2. `symbol_units` and `constant_units` in the real registry read Rust's closed pattern for an input atom. The registry's
   dispatch, the engine and everything else stay Python and take the pattern as they take Python's.
3. `value_units`, as `functions._value_units` and `special.py` call it, gets its pattern the same way. Those callers stay
   Python, so the value they pass was built there: it usually isn't an input term, and takes the derived path below.
4. `_common.resolve` and `_common.Pattern`, the module globals `facts` and `units` call, are Rust's, so every template in the
   engine goes through them, except on a kept query, which stays wholly on Python (`common:kept`). They take no term table, so
   no query on the stack still runs Rust. A kept query can be served a pattern `_CACHE` got from Rust earlier: plain Python data,
   and no Rust runs for it. `facts`, `units` and `_CACHE` stay Python, and a constant's facts are read by `const_value`, in Python, in Python's order.

Stays on Python, counted by reason in `COUNTS`: a query conversion keeps (`kept:<reason>`). A template reached with no query
on the stack, by a caller using `Engine` directly, is read as a derived node is (`<kind>:no-query`, 6g(a)). A node that isn't an input term (`derived`, such
as a Zero the engine built): Python reads its facts, and Rust closes them. That read is the "`is_` by callback" of
section 10's row, and it goes when 4 and 5 stop building those nodes in Python.

A fault from Rust raises `KnowledgeFault`, a BaseException, so `engine.py:1906` and `sympy_api.py:1107` can't turn it into
a quiet "unknown". What `const_value` raises and `cnf_of`'s KeyError for an unknown predicate come through as themselves, as
on Python. A read that raises is a refusal, not a fault: `sa_solver.TermRefuse` goes past the `except Exception` here to
`term_live`, which discards the run and answers on Python.
"""
import importlib.util
import os
import sys

import sa_solver
import sympy

import satassume
from satassume.knowledge import realroots
from satassume.knowledge.templates import _rows_runtime, wiring
from satassume.knowledge.templates import _common, atoms, registry
from satassume.knowledge.templates._common import Compiled, Pattern, VOCAB, const_value

import knowledge_core_live
import knowledge_common_live
import knowledge_f6_live
import term_live

HERE = os.path.dirname(os.path.abspath(__file__))
#: Modules that take `atoms.value_units` by name at import. Both load lazily, so naming them here must not import them.
VALUE_UNITS_CALLERS = ('satassume.knowledge.templates.functions', 'satassume.knowledge.templates.special')
#: The public names of `knowledge/realroots.py`, each `sa_solver.realroots_<name>` under `install()`. The private ones have no other reader.
REALROOTS = ('gcd', 'squarefree', 'real_root_counts', 'imaginary_root_count', 'root_facts')
#: Takes `root_facts` by name at import, and loads lazily.
ROOT_FACTS_CALLER = 'satassume.knowledge.templates.rootof'
COUNTS = term_live.COUNTS
#: With `shadow=True`: (kind, repr of the term, field, Rust's, Python's), the first few of each run's differences.
MISMATCHES = []
MAX_MISMATCHES = 50
#: With `shadow=True`: a field that's equal but prints differently: a dict's order, or a set's. The engine iterates `child_preds`.
ORDER_DIFFS = []
CONTRADICTION = 'template asserts a contradiction'
#: (kind, id, exception type) of the first few reads that raised, across queries.
RAISED = term_live.RAISED
#: Test plants, by SLICE_SESSION_PLANT (the bar's channel): 'knowledge-rows-kept-raise' raises NameError inside `rows_kept`, the
#: fault sa-port-63's first rebase hit; 'knowledge-pattern-drop' drops the last clause of each non-empty pattern Rust builds;
#: 'knowledge-value-multigamma-drop' drops the last clause of Rust's `value_units` pattern when multigamma's template calls it
#: (special.py's `value_units(v, expr)`), for the reached-code ruling's value_units footnote; 'knowledge-no-query-drop' drops
#: the last clause of a pattern Rust builds with no query on the stack (atoms' no-query path, 6g(a)); the dispatch-* plants
#: are term/dispatch.rs's.
PLANTS = ('knowledge-rows-kept-raise', 'knowledge-pattern-drop', 'knowledge-value-multigamma-drop',
          'dispatch-ignores-epoch', 'dispatch-opaque-off', 'dispatch-redefines-off', 'dispatch-user-off',
          'knowledge-no-query-drop') + knowledge_common_live.PLANTS
PLANT = [None]
_UNDO = [None]


class KnowledgeFault(BaseException):
    """Rust failed where it has no reason to. Not an `Exception`, so no quiet handler reads it as "unknown"."""


def _wrap(r):
    """A `Pattern` holding what Rust returned. Its `__init__` isn't run: Rust did that work."""
    rules, clauses, used, complete = r
    p = Pattern.__new__(Pattern)
    p.rules = rules
    p.node = 0
    p.nobjs = 1
    p.clauses = clauses
    p.used = (0,) if used else ()
    p.child_preds = {}
    p.complete = complete
    p.wide = []
    return p


FIELDS = ('rules', 'node', 'nobjs', 'clauses', 'used', 'child_preds', 'complete', 'wide')


def _mismatch(kind, expr, f, a, b):
    if a != b or type(a) is not type(b):
        COUNTS['shadow:mismatch'] += 1
        if len(MISMATCHES) < MAX_MISMATCHES:
            MISMATCHES.append((kind, repr(expr), f, repr(a)[:300], repr(b)[:300]))
    elif repr(a) != repr(b):
        COUNTS['shadow:order'] += 1
        if len(ORDER_DIFFS) < MAX_MISMATCHES:
            ORDER_DIFFS.append((kind, repr(expr), f, repr(a)[:300], repr(b)[:300]))


def _compare(kind, expr, ours, theirs):
    COUNTS['shadow:compared'] += 1
    for f in FIELDS:
        _mismatch(kind, expr, f, getattr(ours, f), getattr(theirs, f))


def _derived_facts(kn, expr, is_symbol):
    """What conversion would have sent for this node, read here. Each is a read of a node Python already built."""
    if is_symbol:
        return [(f, v) for f, v in expr.assumptions0.items()
                if f in VOCAB and v is not None and f != 'commutative']
    return [(p, v) for p, v in ((p, const_value(expr, p)) for p in atoms._CONST_BASIS) if v is not None]


def _bind_value_units(f):
    """`atoms` for a caller that imports later, and each caller that has already taken the name."""
    atoms.value_units = f
    for name in VALUE_UNITS_CALLERS:
        m = sys.modules.get(name)
        if m is not None:
            m.value_units = f


def _same_objects(a, b):
    """`a` and `b` are the same data: the same classes all the way down, and equal SymPy objects with the same print."""
    if type(a) is not type(b):
        return False
    if isinstance(a, (tuple, list)):
        return len(a) == len(b) and all(map(_same_objects, a, b))
    if isinstance(a, dict):
        return list(a) == list(b) and all(_same_objects(a[k], b[k]) for k in a)
    return a == b and repr(a) == repr(b)


def _rows_compare(kind, expr, ours, theirs):
    COUNTS['shadow:rows'] += 1
    if not _same_objects(ours, theirs):
        COUNTS['shadow:mismatch'] += 1
        if len(MISMATCHES) < MAX_MISMATCHES:
            MISMATCHES.append((kind, repr(expr), 'rows', repr(ours)[:300], repr(theirs)[:300]))


def _python_realroots():
    """A private copy of the module. Its functions call each other by module global, so with `realroots` swapped the module's own
    `root_facts` would run on Rust's `squarefree`, and a shadow would compare Rust with Rust."""
    spec = importlib.util.spec_from_file_location('_satassume_python_realroots', realroots.__file__)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m              # `from __future__ import annotations` and typing read it while it runs
    spec.loader.exec_module(m)
    return m


def _bind_realroots(fs):
    for name, f in fs.items():
        setattr(realroots, name, f)
    m = sys.modules.get(ROOT_FACTS_CALLER)
    if m is not None:
        m.root_facts = fs['root_facts']


def installed():
    return _UNDO[0] is not None


def _fired():
    """Counted where the bar's `fired` reads it: `session_live`'s report."""
    COUNTS['knowledge:plant_fired'] += 1
    m = sys.modules.get('session_live')
    if m is not None:
        m.PLANT_FIRED[0] += 1


def from_env():
    """SLICE_KNOWLEDGE: `rust` (the default) or `atoms` installs, `shadow` installs with the field comparison, `py` doesn't.
    Needs `term_live`'s table: with SLICE_TERM=py it stays off. With SESSION_REPORT set, writes COUNTS beside it."""
    mode = os.environ.get('SLICE_KNOWLEDGE', 'rust')
    if mode == 'py' or not term_live.installed():
        return None
    if mode not in ('rust', 'atoms', 'shadow'):
        print(f'SLICE_KNOWLEDGE={mode}: not a mode', file=sys.stderr)
        raise SystemExit(2)
    if os.environ.get('SLICE_SESSION_PLANT') in PLANTS:
        PLANT[0] = os.environ['SLICE_SESSION_PLANT']
    rep = os.environ.get('SESSION_REPORT')
    if rep:
        import atexit
        import json
        out = rep[:-len('.session.json')] if rep.endswith('.session.json') else rep
        atexit.register(lambda: json.dump(dict(mode=mode, plant=PLANT[0], counts=dict(COUNTS)),
                                          open(out + '.knowledge.json', 'w'), sort_keys=True))
    return install(shadow=mode == 'shadow')


DISPATCH = [None]


def install_dispatch():
    """Bind `registry.clauses_for` to Rust's `Dispatch.clauses_for` (an instance attribute over the class's method),
    so `Engine.__init__` hands the engine Rust's bound method. Its counts join COUNTS at exit and at undo."""
    from sympy.core.basic import Basic
    from sympy.core.function import Application
    from sympy.core.singleton import S
    from satassume.sat.formula import Formula, P
    from satassume.state import epoch
    from satassume.knowledge.templates import TemplateRegistry
    builtin = ['satassume.knowledge.templates'] + [m.__name__ for m in (
        sys.modules[__name__], knowledge_core_live, knowledge_f6_live, term_live)]
    d = sa_solver.Dispatch(registry, TemplateRegistry.clauses_for.__get__(registry), epoch.EPOCH, Compiled, P, Formula,
                           Application, Basic, S.NaN, [S.NaN, S.Infinity, S.NegativeInfinity, S.ComplexInfinity],
                           set(VOCAB), builtin)
    if PLANT[0] and PLANT[0].startswith('dispatch-'):
        d.set_plant(PLANT[0])
    DISPATCH[0] = d
    registry.clauses_for = d.clauses_for
    import convert
    convert.TEMPLATES_FOR[0] = d.templates_for

    def flush():
        for k, v in d.counts().items():
            COUNTS[k] += v
            if k == 'plant:fired':
                m = sys.modules.get('session_live')
                if m is not None:
                    m.PLANT_FIRED[0] += v
        d.clear_counts()
    import atexit
    atexit.register(flush)

    def undo():
        flush()
        atexit.unregister(flush)
        DISPATCH[0] = None
        registry.__dict__.pop('clauses_for', None)
        convert.TEMPLATES_FOR[0] = None
    return undo


def install(shadow=False, data=None):
    """`shadow`: also run Python's template on each call and compare every field. Rust's result is still the one used.
    A second install before the first's undo raises: wrapping Rust's functions in Rust's would compare Rust with Rust."""
    if _UNDO[0] is not None:
        raise RuntimeError('knowledge_live is already installed')
    py_symbol, py_constant, py_value = atoms.symbol_units, atoms.constant_units, atoms.value_units
    py_resolve, py_pattern = _common.resolve, _common.Pattern
    offline = sa_solver.OfflineData(data or os.path.join(HERE, 'offline_data.json'),
                                    os.path.dirname(os.path.dirname(os.path.abspath(satassume.__file__))), sympy.__version__)
    kn = sa_solver.Knowledge(offline)
    if kn.const_basis() != list(atoms._CONST_BASIS):
        raise ValueError('offline _CONST_BASIS differs from atoms.py')

    def rust_compiled(py, kind, is_symbol, value, obj):
        """`py()`'s `Compiled`, with Rust's pattern for the facts of `value`, as facts of `obj`."""
        q = term_live.current()
        if q is not None and q.kept is not None:
            COUNTS['py:kept'] += 1
            return py()
        # No query on the stack (a caller using `Engine` directly): no term table, so the node is read as a derived one
        # is (6g(a); it was `py:no-query`, wholly Python).
        i = None if q is None else q.ids.get(value)
        try:
            if q is None:
                COUNTS[kind + ':no-query'] += 1
                r = kn.units(_derived_facts(kn, value, is_symbol))
            # `==` can join classes (const_key's Float against Integer), so a row counts only for its own class.
            elif i is not None and type(q.objects[i]) is type(value):
                COUNTS[kind + ':input'] += 1
                r = kn.symbol_units(q.table, i) if is_symbol else kn.constant_units(q.table, i)
            else:
                COUNTS[kind + ':derived'] += 1
                r = kn.units(_derived_facts(kn, value, is_symbol))
        except Exception as e:
            COUNTS['fault'] += 1
            raise KnowledgeFault(f'{kind} {value!r}: {e}') from e
        pat = _wrap(r)
        if PLANT[0] == 'knowledge-no-query-drop' and q is None and pat.clauses:
            _fired()
            pat.clauses = pat.clauses[:-1]
        if PLANT[0] == 'knowledge-value-multigamma-drop' and kind == 'value' and type(obj).__name__ == 'multigamma' \
                and pat.clauses:
            _fired()
            COUNTS['value:multigamma:plant'] += 1
            pat.clauses = pat.clauses[:-1]
        if shadow:
            _compare(kind, value, pat, py().pattern)
        return Compiled((obj,), pat)

    def template(py, kind, is_symbol, python=None):
        python = python or py

        def rust_units(expr):
            return rust_compiled(lambda: python(expr), kind, is_symbol, expr, expr)
        rust_units.__name__ = py.__name__
        rust_units.__qualname__ = py.__qualname__
        rust_units.__module__ = py.__module__
        rust_units.__wrapped__ = py
        rust_units.__dict__.update(py.__dict__)     # `_satassume_own_facts`
        return rust_units

    def rust_value_units(value, obj):
        return rust_compiled(lambda: py_value(value, obj), 'value', False, value, obj)
    rust_value_units.__wrapped__ = py_value

    def kept():
        q = term_live.current()
        if q is not None and q.kept is not None:
            COUNTS['common:kept'] += 1
            return True
        return False

    def rust_resolve(rules, consts):
        if kept():
            return py_resolve(rules, consts)
        COUNTS['common:resolve'] += 1
        if shadow:      # `gen()` may return a non-list, and Python's run below reads it again
            rules = list(rules)
        slots = [k for k, c in consts.items() if c is not None]
        raised = []

        def read(k, pred):
            try:
                return _common.const_value(consts[k], pred)
            except BaseException as e:
                raised.append(e)
                raise
        try:
            r = kn.resolve(rules, slots, read)
        except Exception as e:
            if raised and raised[-1] is e:      # the read's own, as on Python
                raise
            COUNTS['fault'] += 1
            raise KnowledgeFault(f'resolve: {e}') from e
        if shadow:
            COUNTS['shadow:common'] += 1
            try:
                theirs = py_resolve(rules, consts)
            except ValueError as e:
                if str(e) != CONTRADICTION:
                    raise
                theirs = None
            _mismatch('resolve', consts, 'rules', r, theirs)
        if r is None:
            COUNTS['common:contradiction'] += 1
            raise ValueError(CONTRADICTION)
        return r

    def rust_pattern(rules, node, nobjs=1):
        if kept():
            return py_pattern(rules, node, nobjs)
        COUNTS['common:pattern'] += 1
        try:
            clauses, used, child_preds, wide = kn.build_pattern(rules, node, _common.MAX_EXPAND)
        except KeyError:        # `cnf_of`'s, an unknown predicate
            raise
        except Exception as e:
            COUNTS['fault'] += 1
            raise KnowledgeFault(f'Pattern: {e}') from e
        p = Pattern.__new__(Pattern)
        p.rules = rules
        p.node = node
        p.nobjs = nobjs
        p.complete = False
        p.clauses = clauses
        p.used = used
        p.child_preds = child_preds
        p.wide = [tuple(rules[i]) for i in wide]
        if PLANT[0] == 'knowledge-pattern-drop' and p.clauses:
            _fired()
            p.clauses = p.clauses[:-1]
        if p.wide:
            COUNTS['common:wide'] += len(p.wide)
        if shadow:
            COUNTS['shadow:common'] += 1
            theirs = py_pattern(rules, node, nobjs)
            for f in FIELDS:
                _mismatch('pattern', node, f, getattr(p, f), getattr(theirs, f))
        return p
    if sa_solver.realroots_limits() != (realroots.MAX_DEGREE, realroots.MAX_BITS):
        raise ValueError('sa_solver.realroots_limits differs from realroots.py')
    saved_roots = {name: getattr(realroots, name) for name in REALROOTS}
    py_roots = _python_realroots()

    def rust_root(name):
        py_f, rs_f = getattr(py_roots, name), getattr(sa_solver, 'realroots_' + name)

        def f(*args):
            q = term_live.current()
            if q is not None and q.kept is not None:
                COUNTS['realroots:kept'] += 1
                return py_f(*args)
            COUNTS['realroots:' + name] += 1
            try:
                r = rs_f(*args)
            except IndexError:                  # Python's `real_root_counts` on a zero polynomial raises this too
                raise
            except Exception as e:
                COUNTS['fault'] += 1
                raise KnowledgeFault(f'realroots.{name}{args!r}: {e}') from e
            if shadow:
                COUNTS['shadow:realroots'] += 1
                _mismatch('realroots:' + name, args, 'result', r, py_f(*args))
            return r
        f.__wrapped__ = py_f
        return f

    _bind_realroots({name: rust_root(name) for name in REALROOTS})

    # `_rows_runtime.py`. `_rows.py` and the offline tools keep Python's: only a query's path goes through `wiring`.
    py_generator, py_constant_value = wiring.generator, wiring.constant_value
    active = [True]

    def rows_kept():
        """Outside the callers' `try`, so an ordinary exception here is made loud, as `term_live._guarded` does."""
        try:
            if not active[0]:
                return True
            if PLANT[0] == 'knowledge-rows-kept-raise':
                _fired()
                raise NameError('planted: rows_kept')
            q = term_live.current()
            if q is not None and q.kept is not None:
                COUNTS['rows:kept'] += 1
                return True
            return False
        except Exception as e:
            COUNTS['fault'] += 1
            raise KnowledgeFault(f'rows_kept: {type(e).__name__}: {e}') from e

    def rust_constant_value(text, c):
        if rows_kept():
            return py_constant_value(text, c)
        COUNTS['rows:constant_value'] += 1
        COUNTS[f'rows:constant_value:{type(c).__name__}:{text}'] += 1
        try:
            r = sa_solver.rows_constant_value(text, c)
        except Exception as e:
            COUNTS['fault'] += 1
            raise KnowledgeFault(f'constant_value({text!r}, {c!r}): {e}') from e
        if r is None:       # not a Rust number: `c` a Float, oo or nan, or the value zoo. Python's, by text and class of `c`.
            COUNTS['rows:constant_value:python'] += 1
            COUNTS[f'rows:constant_value:python:{type(c).__name__}:{text}'] += 1
            return py_constant_value(text, c)
        if shadow:
            _rows_compare('constant_value', (text, c), r, py_constant_value(text, c))
        return r
    rust_constant_value.__wrapped__ = py_constant_value

    def rust_generator(name, arity, terms, specs, module, schemas=()):
        python, rows = [], []

        def py_gen():
            if not python:
                python.append(py_generator(name, arity, terms, specs, module, schemas))
            return python[0]

        def read():
            if not rows:
                COUNTS['rows:generator'] += 1
                try:
                    rows.append(sa_solver.RowsGen(terms, specs, _rows_runtime.from_text, schemas))
                except Exception as e:
                    COUNTS['fault'] += 1
                    raise KnowledgeFault(f'generator({name!r}): {e}') from e
                for v in rows[0].python_values:     # not a Rust number: `I` and `-I`, in Pow's shapes
                    COUNTS[f'rows:value:python:{name}:{v}'] += 1
            return rows[0]

        def gen(R, c):
            if rows_kept():
                return py_gen()(R, c)
            COUNTS['rows:gen'] += 1
            r = read()
            try:
                r(R, c)
            except Exception as e:
                COUNTS['fault'] += 1
                raise KnowledgeFault(f'{name}_rows({c!r}): {e}') from e
        # A family first used by a kept query keeps Python's attributes, with the same values; its later rules are still Rust's.
        if rows_kept():
            COUNTS['rows:generator:kept'] += 1
            source = py_gen()
        else:
            source = read()
        gen.__module__ = module
        gen.__name__ = gen.__qualname__ = f'{name}_rows'
        gen.arity, gen.terms, gen.shifts = arity, source.terms, source.shifts
        gen.specs, gen.plain, gen.schemas = source.specs, source.plain, source.schemas
        if shadow:
            theirs = py_gen()
            for f in ('terms', 'shifts', 'specs', 'plain', 'schemas'):
                _rows_compare('generator:' + f, name, getattr(gen, f), getattr(theirs, f))
        return gen
    rust_generator.__wrapped__ = py_generator
    wiring.generator, wiring.constant_value = rust_generator, rust_constant_value

    rust_resolve.__wrapped__ = py_resolve
    rust_pattern.__wrapped__ = py_pattern
    _common.resolve, _common.Pattern = rust_resolve, rust_pattern

    # `py_constant` calls `atoms.value_units`, which is about to be Rust's: its Python path goes straight to Python's.
    swap = {py_symbol: template(py_symbol, 'symbol', True),
            py_constant: template(py_constant, 'constant', False, lambda e: py_value(e, e))}
    saved_lists = {}
    for cls, ts in registry._by_class.items():
        if any(t in swap for t in ts):
            saved_lists[cls] = list(ts)
            ts[:] = [swap.get(t, t) for t in ts]
    registry._mro_cache.clear()
    registry._clauses_cache.clear()
    _bind_value_units(rust_value_units)

    # Step 6e: core.py's Add family (knowledge_core_live.py).
    undo_core = knowledge_core_live.install(shadow, COUNTS, KnowledgeFault, _mismatch)
    # Step 6f: functions, special, rootof, nodes, physics, stats (knowledge_f6_live.py).
    undo_f6 = knowledge_f6_live.install(shadow, COUNTS, KnowledgeFault, _mismatch)
    undo_term = term_live.install()
    # Step 6g(a): the engine calls Rust's dispatch directly (term/dispatch.rs), not registry.clauses_for.
    undo_dispatch = install_dispatch()
    # Step 6d: `_common`'s per-query rows (knowledge_common_live.py, term/common.rs).
    undo_common = knowledge_common_live.install(kn, COUNTS, KnowledgeFault, CONTRADICTION, PLANT[0], DISPATCH[0])

    def undo():
        _UNDO[0] = None
        active[0] = False
        wiring.generator, wiring.constant_value = py_generator, py_constant_value
        undo_common()
        undo_dispatch()
        undo_term()
        undo_f6()
        undo_core()
        _common.resolve, _common.Pattern = py_resolve, py_pattern
        for cls, ts in saved_lists.items():
            registry._by_class[cls][:] = ts
        registry._mro_cache.clear()
        registry._clauses_cache.clear()
        _bind_value_units(py_value)
        _bind_realroots(saved_roots)
    _UNDO[0] = undo
    return undo
