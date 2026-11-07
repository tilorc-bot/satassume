"""The atoms family of runtime knowledge (component 6, issue 323), wired into the real engine.

`install()` makes two changes, from outside satassume, and returns a function that undoes them. Pure Python stays the
default: nothing here runs unless a caller installs it.

1. `sympy_api._ask`, which runs exactly on an answer-memo miss, converts the query first (`convert.py`) and holds the
   table for the query's length. Nothing outlives the query: ids mean nothing outside it.
2. `symbol_units` and `constant_units` in the real registry read Rust's closed pattern for an input atom. The registry's
   dispatch, the engine and everything else stay Python and take the pattern as they take Python's.
3. `value_units`, as `functions._value_units` and `special.py` call it, gets its pattern the same way. Those callers stay
   Python, so the value they pass was built there: it usually isn't an input term, and takes the derived path below.

Stays on Python, counted by reason in `COUNTS`: a query conversion keeps (`kept:<reason>`), and a template reached with no
query on the stack, by a caller using `Engine` directly (`py:no-query`). A node that isn't an input term (`derived`, such
as a Zero the engine built): Python reads its facts, and Rust closes them. That read is the "`is_` by callback" of
section 10's row, and it goes when 4 and 5 stop building those nodes in Python.

A fault from Rust raises `KnowledgeFault`, a BaseException, so `engine.py:1906` and `sympy_api.py:1107` can't turn it into
a quiet "unknown". There is no discarded run in this family: conversion finishes before the engine starts, and a template
never refuses mid-run.
"""
import collections
import os
import sys
import threading

import sa_solver
import sympy

import satassume
from satassume import sympy_api
from satassume.knowledge.templates import atoms, registry
from satassume.knowledge.templates._common import Compiled, Pattern, VOCAB, const_value

import convert

HERE = os.path.dirname(os.path.abspath(__file__))
#: Modules that take `atoms.value_units` by name at import. Both load lazily, so naming them here must not import them.
VALUE_UNITS_CALLERS = ('satassume.knowledge.templates.functions', 'satassume.knowledge.templates.special')
COUNTS = collections.Counter()
#: With `shadow=True`: (kind, repr of the term, field, Rust's, Python's), the first few of each run's differences.
MISMATCHES = []
MAX_MISMATCHES = 50
#: (kind, id, exception type) of the first few reads that raised, across queries.
RAISED = []


class KnowledgeFault(BaseException):
    """Rust failed where it has no reason to. Not an `Exception`, so no quiet handler reads it as "unknown"."""


class _Query:
    __slots__ = ('table', 'ids', 'objects', 'kept', 'counts', 'raised')

    def __init__(self, c):
        if isinstance(c, convert.Kept):
            self.kept, self.table, self.ids, self.objects, self.counts, self.raised = c.reason, None, None, None, {}, ()
        else:
            self.kept = None
            self.table = sa_solver.TermTable(c.tables)
            self.ids, self.objects, self.counts = c.ids, c.objects, c.counts
            self.raised = c.raised


_local = threading.local()


def _stack():
    try:
        return _local.stack
    except AttributeError:
        _local.stack = []
        return _local.stack


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


def _compare(kind, expr, ours, theirs):
    COUNTS['shadow:compared'] += 1
    for f in FIELDS:
        a, b = getattr(ours, f), getattr(theirs, f)
        if a != b or type(a) is not type(b):
            COUNTS['shadow:mismatch'] += 1
            if len(MISMATCHES) < MAX_MISMATCHES:
                MISMATCHES.append((kind, repr(expr), f, repr(a)[:300], repr(b)[:300]))


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


def install(shadow=False, data=None):
    """`shadow`: also run Python's template on each call and compare every field. Rust's result is still the one used."""
    py_symbol, py_constant, py_value = atoms.symbol_units, atoms.constant_units, atoms.value_units
    offline = sa_solver.OfflineData(data or os.path.join(HERE, 'offline_data.json'),
                                    os.path.dirname(os.path.dirname(os.path.abspath(satassume.__file__))), sympy.__version__)
    kn = sa_solver.Knowledge(offline)
    if kn.const_basis() != list(atoms._CONST_BASIS):
        raise ValueError('offline _CONST_BASIS differs from atoms.py')

    def rust_compiled(py, kind, is_symbol, value, obj):
        """`py()`'s `Compiled`, with Rust's pattern for the facts of `value`, as facts of `obj`."""
        stack = _stack()
        q = stack[-1] if stack else None
        if q is None:
            COUNTS['py:no-query'] += 1
            return py()
        if q.kept is not None:
            COUNTS['py:kept'] += 1
            return py()
        i = q.ids.get(value)
        try:
            # `==` can join classes (const_key's Float against Integer), so a row counts only for its own class.
            if i is not None and type(q.objects[i]) is type(value):
                COUNTS[kind + ':input'] += 1
                r = kn.symbol_units(q.table, i) if is_symbol else kn.constant_units(q.table, i)
            else:
                COUNTS[kind + ':derived'] += 1
                r = kn.units(_derived_facts(kn, value, is_symbol))
        except Exception as e:
            COUNTS['fault'] += 1
            raise KnowledgeFault(f'{kind} {value!r}: {e}') from e
        pat = _wrap(r)
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

    py_ask = sympy_api._ask

    def _ask(proposition, assumptions, eng):
        # This can sit inside a quiet handler when a query nests, so a failure here must not be an Exception.
        try:
            q = _Query(convert.convert(proposition, assumptions, eng))
        except Exception as e:
            COUNTS['fault'] += 1
            raise KnowledgeFault(f'conversion: {e}') from e
        if q.kept is not None:
            COUNTS['kept:' + q.kept] += 1
        else:
            COUNTS['converted'] += 1
        stack = _stack()
        stack.append(q)
        try:
            return py_ask(proposition, assumptions, eng)
        finally:
            stack.pop()
            # The reads this query really asked for, so `read_raised` here is never a forced read.
            for name, n in q.counts.items():
                if n and (name.startswith('read:') or name in ('read_raised', 'read_term_missing')):
                    COUNTS[name] += n
            RAISED[len(RAISED):] = list(q.raised)[:max(0, MAX_MISMATCHES - len(RAISED))]

    sympy_api._ask = _ask

    def undo():
        sympy_api._ask = py_ask
        for cls, ts in saved_lists.items():
            registry._by_class[cls][:] = ts
        registry._mro_cache.clear()
        registry._clauses_cache.clear()
        _bind_value_units(py_value)
    return undo
