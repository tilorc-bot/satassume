"""Component 5, step 5a: `VarTable`, `compile_formula` and `Session`'s variable and clause surface run in Rust (`session.rs`,
`compile.rs`). What stays here is the shell: `Session` keeps discovery, `Relations` and the templates, and reaches the core
through the views below, which keep `table` and `base` readable as they were. `SLICE_SESSION=py` keeps it off.

Keys are the session's own node ids, joined as Python's dicts join objects, not the per-query table's ids as the planner's 5a
says. Kept queries have no table. Dev's census of visited nodes (`SESSION_REPORT`): 2,246 input rows, 53 derived rows, 177
`Add` and `Mul` with no row yet, 6 on kept queries, none of another class. Whether to link them is 5b's question.
"""
import os

import sa_solver

from satassume import engine
from satassume.knowledge import compile as C
from satassume.knowledge import rules
from satassume.sat import formula as Fm

#: Test plants: 'var-off' moves every answer of `Session.var` called from Python, 'var-off:PRED' only those for one predicate,
#: and 'var-count' moves none and counts them per predicate in the report; 'guard-drop' compiles `assume_formula`'s formula
#: with no selector, through `compile.rs`.
PLANT = [None]
PLANT_FIRED = [0]
VAR_PREDS = {}
#: Python's `compile_formula` and `formula_literal`, for what Rust won't compile.
PY_COMPILE = [None, None]

#: SESSION_REPORT=FILE: for each visited node, whether the per-query table has a row for it, read with no learning. Written
#: at exit, with the build that loaded and the crossings by kind.
CENSUS = None

_rules = [None]


def _core_rules():
    if _rules[0] is None:
        _rules[0] = sa_solver.SessionRules(
            rules.BASIS, rules.DEF_LITS,
            [Fm.P, Fm.And, Fm.Or, Fm.Not, Fm.Implies, Fm.Equivalent, Fm.Exclusive, Fm.ITE, C._Lit],
            rules.def_implications)
    return _rules[0]


class _Custom:
    """`table.custom`."""
    __slots__ = ('c',)

    def __init__(self, c):
        self.c = c

    def get(self, a, default=None):
        v = self.c.custom_get(a)
        return default if v is None else v

    def __contains__(self, a):
        return self.c.custom_get(a) is not None

    def __getitem__(self, a):
        v = self.c.custom_get(a)
        if v is None:
            raise KeyError(a)
        return v


class _BaseOf:
    """`table.base_of`."""
    __slots__ = ('c',)

    def __init__(self, c):
        self.c = c

    def get(self, n, default=None):
        v = self.c.base_of_get(n)
        return default if v is None else v

    def __contains__(self, n):
        return self.c.base_of_get(n) is not None

    def __getitem__(self, n):
        v = self.c.base_of_get(n)
        if v is None:
            raise KeyError(n)
        return v


class _Base:
    """`Session.base`: the visited nodes."""
    __slots__ = ('c',)

    def __init__(self, c):
        self.c = c

    def get(self, n, default=None):
        v = self.c.base_get(n)
        return default if v is None else v

    def __contains__(self, n):
        return self.c.base_get(n) is not None

    def __getitem__(self, n):
        v = self.c.base_get(n)
        if v is None:
            raise KeyError(n)
        return v

    def __len__(self):
        return self.c.n_base()


class _Slots:
    """`table.slots`: `Relations.sync_transfer` reads it by cursor."""
    __slots__ = ('c',)

    def __init__(self, c):
        self.c = c

    def __len__(self):
        return self.c.n_vars() + 1

    def __getitem__(self, v):
        return self.c.slot(v)


class TableView:
    """`VarTable`'s surface. The core comes when `Session.__init__` assigns this to `self.table`, by then with its solver."""

    def bind(self, session):
        import weakref
        self.core = sa_solver.SessionCore(_core_rules(), weakref.ref(session))
        c = self.core
        self.custom, self.base_of, self.slots = _Custom(c), _BaseOf(c), _Slots(c)
        self.var, self.aux, self.node_base = c.table_var_py, c.aux, c.node_base
        self.atom = c.atom
        self.base_view = _Base(c)

    @property
    def new_nodes(self):
        return self.core.new_nodes()

    @new_nodes.setter
    def new_nodes(self, value):
        assert not value
        self.core.clear_new_nodes()

    @property
    def new_custom(self):
        return self.core.new_custom()

    @new_custom.setter
    def new_custom(self, value):
        assert not value
        self.core.clear_new_custom()

    @property
    def atom_of(self):
        return [None] + [self.atom(v) for v in range(1, len(self) + 1)]

    @property
    def naux(self):
        return self.core.naux()

    @property
    def true_var(self):
        return self.core.true_var()

    @true_var.setter
    def true_var(self, v):
        self.core.set_true_var(v)

    def __len__(self):
        return self.core.n_vars()

    def lit_name(self, lit):
        a = self.atom(abs(lit))
        s = repr(a) if a is not None else f"aux{abs(lit)}"
        return ("~" if lit < 0 else "") + s


def _table_get(self):
    return self.__dict__['_table_view']


def _table_set(self, view):
    view.bind(self)
    self.__dict__['_table_view'] = view


def _base_get(self):
    return self.__dict__['_table_view'].base_view


def _base_set(self, value):
    assert not value    # `Session.__init__`'s `{}`


def _node(self, node, demanded=None):
    c = self.table.core
    b = c.base_get(node)
    if b is not None:
        if demanded is not None and (node in self.pending or node in self.pending_c):
            self._compile_pending(node, demanded)
        return b
    return c.visit(node, demanded)


def _census(node):
    import term_live
    q = term_live.current()
    if q is None:
        k = 'no-query'
    elif q.kept is not None:
        k = 'kept-query'
    elif q.ids.get(node) is not None:
        k = 'input-row'
    elif q.derived.get(node) is not None:
        k = 'derived-row'
    else:
        k = 'no-row:' + type(node).__name__
    CENSUS[k] = CENSUS.get(k, 0) + 1


def _core_visit(self, node, b, demanded):
    if CENSUS is not None:
        _census(node)
    constructing = self.engine._constructing
    constructing.add(node)
    try:
        self._visit(node, b, demanded)
    finally:
        constructing.discard(node)


def _var(self, pred, node):
    v = self.table.core.var(pred, node)
    if PLANT[0] is not None and v > 1:
        if PLANT[0] == 'var-count':
            VAR_PREDS[str(pred)] = VAR_PREDS.get(str(pred), 0) + 1
        elif PLANT[0] == 'var-off' or PLANT[0] == f'var-off:{pred}':
            PLANT_FIRED[0] += 1
            return v - 1
    return v


def _dvar_public(self, dn, need='both'):
    return self.table.core.dvar(dn, need)


def _dvar_raw(self, d, node, need, link=False):
    return self.table.core.dvar_raw_py(d, node, need, link)


def _fault(site, text):
    """`relations_core.rs`'s own failure: counted, and past every `except Exception` on the engine's path."""
    import term_live
    term_live.COUNTS['fault'] += 1
    return term_live.TermFault(f'{site}: {text}')


def _rel_closed_extended_real(self, e):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_closed_extended_real'](self, e)
    return sa_solver.rel_closed_extended_real(self, e)


def _rel_order_sides(self, var, atom):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_order_sides'](self, var, atom)
    return sa_solver.rel_order_sides(self, var, atom)


def _rel_order_infinite(self, var, sides):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_order_infinite'](self, var, sides)
    return sa_solver.rel_order_infinite(self, var, sides)


def _rel_trichotomy(self, var, atom):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_trichotomy'](self, var, atom)
    return sa_solver.rel_trichotomy(self, var, atom)


def _rel_mention_number(self, e):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_mention_number'](self, e)
    return sa_solver.rel_mention_number(self, e)


def _rel_link_integer(self, ad, e, g):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_link_integer'](self, ad, e, g)
    return sa_solver.rel_link_integer(self, ad, e, g)


#: Python's own methods, for a session with no core: `satassume/ref.py`, the reference, keeps Python's `VarTable` under `Relations`,
#: as `_rust_call` already allows for the compiler.
PY_REL = {}
#: Step 5b's C2a: these `Relations` methods run in `relations_core.rs`. SLICE_REL=py keeps them here over the same core.
_REL_METHODS = {
    '_closed_extended_real': _rel_closed_extended_real, '_order_sides': _rel_order_sides,
    '_order_infinite': _rel_order_infinite, '_trichotomy': _rel_trichotomy,
    '_mention_number': _rel_mention_number, '_link_integer': _rel_link_integer,
}
#: Plants that live in `relations_core.rs`.
_REL_PLANTS = ('link-none', 'drop-order-sides', 'drop-order-infinite', 'drop-trichotomy')


def _install_relations():
    """Returns the undo."""
    import term_live
    from satassume import relations
    from satassume.theories.euf import euf_adapter
    R = relations.Relations
    saved = {n: R.__dict__[n] for n in _REL_METHODS}
    PY_REL.update(saved)
    sa_solver.rel_install(term_live, relations, euf_adapter, _fault)
    for n, f in _REL_METHODS.items():
        setattr(R, n, f)

    def undo():
        for n, f in saved.items():
            setattr(R, n, f)
    return undo


def _rust_call(table, emit, dv):
    """Whether Rust can make this call, and the `emit` it has to call back: `None` means `Session.emit` itself, which Rust does
    directly. `assume_formula` passes its own `emit`, which adds the selector; Rust calls that one, so it never has to know."""
    if not isinstance(table, TableView):
        return False, None
    if dv is not None and not (getattr(dv, '__func__', None) is _dvar_public and dv.__self__.table is table):
        return False, None
    if getattr(emit, '__func__', None) is engine.Session.emit and emit.__self__.table is table:
        return True, None
    return True, emit


def _compile_formula(f, table, emit, dv=None):
    ok, via = _rust_call(table, emit, dv)
    if PLANT[0] == 'guard-drop':
        PLANT_FIRED[0] += via is not None
        via = None
    # False, also when `ok`: too deep or unreadable, before anything is emitted. Python's compiler over this same table.
    if not (ok and table.core.compile(f, via, dv is not None)):
        PY_COMPILE[0](f, table, emit, dv)


def _formula_literal(f, table, emit, dv=None):
    ok, via = _rust_call(table, emit, dv)
    lit = table.core.literal(f, via, dv is not None) if ok else None
    return PY_COMPILE[1](f, table, emit, dv) if lit is None else lit


def install():
    """Returns the undo."""
    S = engine.Session
    saved = {n: S.__dict__.get(n) for n in ('table', 'base', 'node', 'var', 'dvar', '_dvar', '_core_visit')}
    g = (engine.VarTable, engine.compile_formula, engine.formula_literal)
    PY_COMPILE[:] = g[1:]
    S.table = property(_table_get, _table_set)
    S.base = property(_base_get, _base_set)
    S.node, S.var, S.dvar, S._dvar, S._core_visit = _node, _var, _dvar_public, _dvar_raw, _core_visit
    engine.VarTable, engine.compile_formula, engine.formula_literal = TableView, _compile_formula, _formula_literal
    undo_rel = _install_relations() if os.environ.get('SLICE_REL', 'rust') == 'rust' else None

    def undo():
        if undo_rel is not None:
            undo_rel()
        for n, v in saved.items():
            if v is None:
                delattr(S, n)
            else:
                setattr(S, n, v)
        engine.VarTable, engine.compile_formula, engine.formula_literal = g
    return undo


def _write_report(path):
    import json
    json.dump(dict(so=sa_solver.__file__, counts=counts(), nodes=CENSUS, plant_fired=PLANT_FIRED[0], var_preds=VAR_PREDS), open(path, 'w'), sort_keys=True)


def from_env():
    global CENSUS
    if os.environ.get('SLICE_SESSION', 'rust') == 'rust':
        if os.environ.get('SESSION_REPORT'):
            import atexit
            CENSUS = {}
            atexit.register(_write_report, os.environ['SESSION_REPORT'])
        if os.environ.get('SLICE_SESSION_PLANT'):
            PLANT[0] = os.environ['SLICE_SESSION_PLANT']
            if PLANT[0] in _REL_PLANTS:
                sa_solver.rel_plant(PLANT[0])
        return install()
    return None


def counts():
    return dict(sa_solver.session_counts())
