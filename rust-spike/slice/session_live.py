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


def _rel_fresh(self, inert=False):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_fresh'](self, inert)
    return sa_solver.rel_fresh(self, inert)


def _rel_interpret(self, atom):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_interpret'](self, atom)
    return sa_solver.rel_interpret(self, atom)


def _rel_guard(self, ad, terms):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_guard'](self, ad, terms)
    return sa_solver.rel_guard(self, ad, terms)


def _rel_bound(self, ad, c):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_bound'](self, ad, c)
    return sa_solver.rel_bound(self, ad, c)


def _rel_link(self, e):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_link'](self, e)
    return sa_solver.rel_link(self, e)


def _rel_selectors_of(self, atoms):
    if not isinstance(self.session.table, TableView):
        return PY_REL['selectors_of'](self, atoms)
    return sa_solver.rel_selectors_of(self, atoms)


def _rel_eq_infinity(self, var, atom):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_eq_infinity'](self, var, atom)
    return sa_solver.rel_eq_infinity(self, var, atom)


def _rel_add_role(self, atom, g, kind):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_add_role'](self, atom, g, kind)
    return sa_solver.rel_add_role(self, atom, g, kind)


def _rel_apply_role(self, atom, info, kind, g):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_apply_role'](self, atom, info, kind, g)
    return sa_solver.rel_apply_role(self, atom, info, kind, g)


def _rel_tsource(self, u, k, g):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_tsource'](self, u, k, g)
    return sa_solver.rel_tsource(self, u, k, g)


def _rel_tvar(self, u, k):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_tvar'](self, u, k)
    return sa_solver.rel_tvar(self, u, k)


def _rel_share_guard(self, u):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_share_guard'](self, u)
    return sa_solver.rel_share_guard(self, u)


def _rel_congruent(self, node):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_congruent'](self, node)
    return sa_solver.rel_congruent(self, node)


def _rel_engage_transfer(self):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_engage_transfer'](self)
    return sa_solver.rel_engage_transfer(self)


def _rel_transfer_terms(self):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_transfer_terms'](self)
    return sa_solver.rel_transfer_terms(self)


def _rel_sync_transfer(self):
    if not isinstance(self.session.table, TableView):
        return PY_REL['sync_transfer'](self)
    return sa_solver.rel_sync_transfer(self)


def _rel_xswitch(self, node, t):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_xswitch'](self, node, t)
    return sa_solver.rel_xswitch(self, node, t)


def _rel_congruence_pairs(self):
    if not isinstance(self.session.table, TableView):
        return PY_REL['_congruence_pairs'](self)
    return sa_solver.rel_congruence_pairs(self)


# -- step 5c4: the rest of `Relations` (relations_core.rs, "step 5c4") -------------------------------------------------------
def _rel_init(self, session, specs):
    if not isinstance(session.table, TableView):
        return PY_REL['__init__'](self, session, specs)
    return sa_solver.rel_init(self, session, specs)


def _rel_m(name, rname):
    rf = getattr(sa_solver, rname)

    def f(self, *a):
        if not isinstance(self.session.table, TableView):
            return PY_REL[name](self, *a)
        return rf(self, *a)
    f.__name__ = name
    return f


def _rel_process(self, user_atoms=()):
    if not isinstance(self.session.table, TableView):
        return PY_REL['process'](self, user_atoms)
    return sa_solver.rel_process(self, user_atoms)


#: Python's own methods, for a session with no core: `satassume/ref.py`, the reference, keeps Python's `VarTable` under `Relations`,
#: as `_rust_call` already allows for the compiler.
PY_REL = {}
#: Step 5b's C2a, C2b and C2c: these `Relations` methods run in `relations_core.rs`. SLICE_REL=py keeps them here over the same core.
#: Among themselves they call each other directly in Rust; these are for what's still Python. `_guard`, `_bound` and `_eq_infinity` have
#: no Python caller left under Rust, and stay here so nothing can reach Python's copy by accident.
_REL_METHODS = {
    '_closed_extended_real': _rel_closed_extended_real, '_order_sides': _rel_order_sides,
    '_order_infinite': _rel_order_infinite, '_trichotomy': _rel_trichotomy,
    '_mention_number': _rel_mention_number, '_link_integer': _rel_link_integer,
    '_fresh': _rel_fresh, '_interpret': _rel_interpret, '_guard': _rel_guard, '_bound': _rel_bound, '_link': _rel_link,
    'selectors_of': _rel_selectors_of, '_eq_infinity': _rel_eq_infinity,
    '_add_role': _rel_add_role,
    '_apply_role': _rel_apply_role,
    '_tsource': _rel_tsource,
    '_tvar': _rel_tvar,
    '_share_guard': _rel_share_guard,
    '_congruent': _rel_congruent,
    '_engage_transfer': _rel_engage_transfer,
    '_transfer_terms': _rel_transfer_terms,
    'sync_transfer': _rel_sync_transfer,
    '_xswitch': _rel_xswitch,
    '_congruence_pairs': _rel_congruence_pairs,
    # Step 5c4.
    '__init__': _rel_init, 'enqueue': _rel_m('enqueue', 'rel_enqueue'), 'note_formula': _rel_m('note_formula', 'rel_note_formula'),
    'process': _rel_process, '_link_later': _rel_m('_link_later', 'rel_link_later'),
    'wants_transfer': _rel_m('wants_transfer', 'rel_wants_transfer'), '_share': _rel_m('_share', 'rel_share'),
    # Step 5c5: the five 5c4 left.
    '_adapter': _rel_m('_adapter', 'rel_adapter'), '_atom_selector': _rel_m('_atom_selector', 'rel_atom_selector'),
    '_atom_var': _rel_m('_atom_var', 'rel_atom_var'), '_note_sides': _rel_m('_note_sides', 'rel_note_sides'),
    '_eq_links': _rel_m('_eq_links', 'rel_eq_links'),
}
#: Plants that live in `relations_core.rs`.
_REL_PLANTS = ('link-none', 'drop-order-sides', 'drop-order-infinite', 'drop-trichotomy', 'drop-interpret', 'drop-guard',
               'drop-bound', 'drop-link', 'drop-selector', 'drop-eq-infinity', 'fresh-not-inert', 'fresh-skew', 'skip-trichotomy',
               'drop-add-role', 'drop-apply-role', 'drop-candidacy', 'drop-tsource', 'drop-tvar', 'drop-tvar-mc', 'drop-engage', 'drop-terms',
               'drop-terms-side', 'drop-fixed', 'drop-sync', 'drop-sync-polar', 'drop-xswitch', 'drop-congruence', 'congruent-never',
               'share-guard-one',
               # Step 5c4.
               'drop-init-engage', 'drop-enqueue', 'drop-note-top', 'drop-proc-eq-links', 'drop-link-later', 'wants-never',
               'drop-share', 'skip-share', 'drop-share-tri',
               # Step 5c5.
               'adapter-fresh', 'selector-no-memo', 'atom-var-skew', 'drop-note-sides', 'drop-eq-links-zero',
               # Step 5c5, second part: relations.py's module functions.
               'own-term-false', 'constant-term-never', 'basis-all', 'sympy-atom-swap', 'zero-args-empty', 'under-of-empty',
               'zero-twins-first', 'glue-no-twins', 'guarded-none', 'terms-of-no-order', 'link-objects-bare', 'closed-units-none',
               'with-closed-skip', 'specs-no-euf', 'relname-swap',
               # Adapters step, part A: the specs converted once.
               'spec-row-flip', 'ad-lra-shared', 'ad-euf-node', 'ad-kind-swap', 'ad-euf-shared',
               # Adapters step, part C: the payload classes.
               'pay-neg-twice', 'pay-int-offset', 'pay-eq-flip')

#: Step 5c5, second part: relations.py's module functions that run in `relations_core.rs`, by module attribute -> pyfunction.
#: `_constant_term` has no pyfunction: Rust's callers use its own copy, and Python's few callers keep Python's.
_REL_FUNCS = {
    'zero_args': 'rel_zero_args', 'under_of': 'rel_under_of', 'zero_twins': 'rel_zero_twins', 'glue_atoms': 'rel_glue_atoms',
    'sympy_atom': 'rel_sympy_atom', '_own_term': 'rel_own_term', '_number_basis': 'rel_number_basis',
    '_number_facts': 'rel_number_facts', '_guarded_adapters': 'rel_guarded_adapters', '_terms_of': 'rel_terms_of',
    'link_objects': 'rel_link_objects', 'closed_units': 'rel_closed_units', 'with_closed_units': 'rel_with_closed_units',
    'default_specs': 'rel_default_specs', '_missing': 'rel_missing', 'relational_name': 'rel_relational_name',
}
#: Modules that import some of them by name, and so are patched too. ref.py (the reference engine) is left Python's on purpose;
#: its call-time imports of `closed_units` and `default_specs` (ref.py:299, :544) read the module and so get Rust's.
_REL_FUNC_IMPORTERS = (('satassume.engine', ('zero_args', 'under_of', 'glue_atoms', 'link_objects')),
                       ('satassume.scope', ('glue_atoms',)),
                       ('satassume.sympy_api', ('relational_name',)))
#: Python's module functions, saved at install.
PY_REL_FUNCS = {}


#: Step 5c1: `Session`'s discovery runs in `discovery.rs`. SLICE_DISC=py keeps Python's over the same core. Python's own copies, for a
#: session with no core.
PY_DISC = {}


def _ses_ensure(self, node, demanded=None):
    if not isinstance(self.table, TableView):
        return PY_DISC['ensure'](self, node, demanded)
    return sa_solver.ses_ensure(self, node, demanded)


def _ses_discover(self):
    if not isinstance(self.table, TableView):
        return PY_DISC['discover'](self)
    return sa_solver.ses_discover(self)


def _ses_discover_raw(self, demanded=None):
    if not isinstance(self.table, TableView):
        return PY_DISC['_discover'](self, demanded)
    return sa_solver.ses_discover_raw(self, demanded)


def _ses_incomplete(self):
    if not isinstance(self.table, TableView):
        return PY_DISC['incomplete'].fget(self)
    return sa_solver.ses_incomplete(self)


def _ses_escalate(self, budget=None):
    if not isinstance(self.table, TableView):
        return PY_DISC['escalate'](self, budget)
    return sa_solver.ses_escalate(self, budget)


_DISC_METHODS = {'ensure': _ses_ensure, 'discover': _ses_discover, '_discover': _ses_discover_raw,
                 'incomplete': property(_ses_incomplete), 'escalate': _ses_escalate}
_DISC_PLANTS = ('drop-ensure-demand', 'drop-discover-flush', 'drop-discover-visit', 'drop-esc-pattern', 'drop-esc-compile',
                'drop-esc-deferred', 'truncated-never', 'incomplete-never')


def _install_discovery():
    """Returns the undo."""
    S = engine.Session
    saved = {n: S.__dict__[n] for n in _DISC_METHODS}
    PY_DISC.update(saved)
    for n, f in _DISC_METHODS.items():
        setattr(S, n, f)

    def undo():
        for n, f in saved.items():
            setattr(S, n, f)
    return undo


#: Step 5c2: `Session`'s compile loop runs in `compile_loop.rs`: `_custom`, `_visit`, `_emit_pattern`, `_flush`, `_compile`,
#: `_compile_pending`, `_compile_patterns` and module `_split` and `want_of`; `_link` is the core's (`session.rs` `link`). The core
#: visits a node through Rust's `core_visit` (census and `engine._constructing`, which `session_live._core_visit` did until 5c2), and
#: `_flush` calls Rust's `_custom`. SLICE_LOOP=py puts Python's methods back on the class for direct callers only. Python's own copies, for a session with
#: no core (`_split` and `want_of` read no session, so they're switched for every caller).
PY_LOOP = {}


def _ses_emit_pattern(self, clauses, bases, ment=None):
    if not isinstance(self.table, TableView):
        return PY_LOOP['_emit_pattern'](self, clauses, bases, ment)
    return sa_solver.ses_emit_pattern(self, clauses, bases, ment)


def _ses_flush(self, node=None):
    if not isinstance(self.table, TableView):
        return PY_LOOP['_flush'](self, node)
    return sa_solver.ses_flush(self, node)


def _ses_compile(self, node, items):
    if not isinstance(self.table, TableView):
        return PY_LOOP['_compile'](self, node, items)
    return sa_solver.ses_compile(self, node, items)


def _ses_compile_patterns(self, node, compiled, demanded):
    if not isinstance(self.table, TableView):
        return PY_LOOP['_compile_patterns'](self, node, compiled, demanded)
    return sa_solver.ses_compile_patterns(self, node, compiled, demanded)


def _ses_compile_pending(self, node, demanded):
    if not isinstance(self.table, TableView):
        return PY_LOOP['_compile_pending'](self, node, demanded)
    return sa_solver.ses_compile_pending(self, node, demanded)


def _ses_custom(self, atom):
    if not isinstance(self.table, TableView):
        return PY_LOOP['_custom'](self, atom)
    return sa_solver.ses_custom(self, atom)


def _ses_visit(self, node, b, demanded):
    if not isinstance(self.table, TableView):
        return PY_LOOP['_visit'](self, node, b, demanded)
    return sa_solver.ses_visit(self, node, b, demanded)


def _ses_link(self, d, node, v):
    if not isinstance(self.table, TableView):
        return PY_LOOP['_link'](self, d, node, v)
    return self.table.core.link_py(d, node, v)


_LOOP_METHODS = {'_custom': _ses_custom, '_visit': _ses_visit, '_link': _ses_link, '_emit_pattern': _ses_emit_pattern, '_flush': _ses_flush, '_compile': _ses_compile,
                 '_compile_pending': _ses_compile_pending, '_compile_patterns': _ses_compile_patterns}
_LOOP_FUNCS = {'_split': 'ses_split', 'want_of': 'ses_want_of'}
_LOOP_PLANTS = ('drop-split-later', 'drop-emit-ment', 'drop-flush-custom', 'drop-compile-demand', 'drop-pend-compile', 'want-empty',
                'drop-pat-demand', 'drop-custom-rel', 'drop-custom-facts', 'drop-visit-items', 'drop-dv-link')


def _install_compile_loop():
    """Returns the undo."""
    S = engine.Session
    saved = {n: S.__dict__[n] for n in _LOOP_METHODS}
    saved_f = {n: getattr(engine, n) for n in _LOOP_FUNCS}
    PY_LOOP.update(saved)
    PY_LOOP.update(saved_f)
    for n, f in _LOOP_METHODS.items():
        setattr(S, n, f)
    for n, r in _LOOP_FUNCS.items():
        setattr(engine, n, getattr(sa_solver, r))

    def undo():
        for n, f in saved.items():
            setattr(S, n, f)
        for n, f in saved_f.items():
            setattr(engine, n, f)
    return undo


# -- step 5c3: the queries (query.rs) --------------------------------------------------------------------------------------
PY_QUERY = {}


def _q(name, rname):
    rf = getattr(sa_solver, rname)

    def f(self, *a):
        if not isinstance(self.table, TableView):
            return PY_QUERY[name](self, *a)
        return rf(self, *a)
    f.__name__ = name
    return f


def _ses_query_literal(self, lit, assumptions=(), search=True):
    if not isinstance(self.table, TableView):
        return PY_QUERY['query_literal'](self, lit, assumptions, search)
    return sa_solver.ses_query_literal(self, lit, assumptions, search)


_QUERY_METHODS = {'query_lit': _q('query_lit', 'ses_query_lit'), 'prepare_query': _q('prepare_query', 'ses_prepare_query'),
                  'emit': _q('emit', 'ses_emit'), 'query_literal': _ses_query_literal,
                  '_query_all': _q('_query_all', 'ses_query_all'), 'literal_of': _q('literal_of', 'ses_literal_of'),
                  '_relations': _q('_relations', 'ses_relations'), '_ensure_atoms': _q('_ensure_atoms', 'ses_ensure_atoms'),
                  '_ensure_twins': _q('_ensure_twins', 'ses_ensure_twins')}
_QUERY_PLANTS = ('drop-prep-twins', 'drop-prep-rel', 'query-lit-tuple', 'drop-ql-mention', 'ql-skip-consistent', 'drop-qa-mention',
                 'drop-lo-memo', 'drop-lo-discover', 'drop-rel-process', 'drop-ea-ensure', 'drop-twins-var', 'drop-emit')


def _install_queries():
    """Returns the undo."""
    S = engine.Session
    saved = {n: S.__dict__[n] for n in _QUERY_METHODS}
    PY_QUERY.update(saved)
    for n, f in _QUERY_METHODS.items():
        setattr(S, n, f)

    def undo():
        for n, f in saved.items():
            setattr(S, n, f)
    return undo


#: Step 5c6: the rest of `Session` runs in `session_glue.rs`: `__init__`, `assume_formula`, `link_set`, `assumption_lits`, `_set_glue`,
#: `_group_sel`, `_glue_of`. `query.rs` calls `_glue_of` directly, and these call each other directly. SLICE_GLUE=py puts Python's
#: methods back. Python's own copies, for a session with no core (`__init__`: when `engine.VarTable` isn't `TableView`).
PY_GLUE = {}


def _ses_init(self, engine_, scope):
    if engine.VarTable is not TableView:
        return PY_GLUE['__init__'](self, engine_, scope)
    return sa_solver.ses_init(self, engine_, scope)


def _ses_assumption_lits(self, prop=None):
    if not isinstance(self.table, TableView):
        return PY_GLUE['assumption_lits'](self, prop)
    return sa_solver.ses_assumption_lits(self, prop)


def _g(name, rname):
    rf = getattr(sa_solver, rname)

    def f(self, *a):
        if not isinstance(self.table, TableView):
            return PY_GLUE[name](self, *a)
        return rf(self, *a)
    f.__name__ = name
    return f


_GLUE_METHODS = {'__init__': _ses_init, 'assume_formula': _g('assume_formula', 'ses_assume_formula'),
                 'link_set': _g('link_set', 'ses_link_set'), 'assumption_lits': _ses_assumption_lits,
                 '_set_glue': _g('_set_glue', 'ses_set_glue'), '_group_sel': _g('_group_sel', 'ses_group_sel'),
                 '_glue_of': _g('_glue_of', 'ses_glue_of')}
_GLUE_PLANTS = ('init-no-relations', 'af-drop-relations', 'link-set-skip', 'al-drop-delta', 'set-glue-no-emit', 'group-sel-no-impl',
                'glue-of-plain')


def _install_glue():
    """Returns the undo. `__init__`'s `scope=EMPTY` default is the one `_install_scope` left on Python's."""
    S = engine.Session
    saved = {n: S.__dict__[n] for n in _GLUE_METHODS}
    PY_GLUE.update(saved)
    _ses_init.__defaults__ = saved['__init__'].__defaults__
    for n, f in _GLUE_METHODS.items():
        setattr(S, n, f)

    def undo():
        for n, f in saved.items():
            setattr(S, n, f)
    return undo


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
    import importlib
    mods = [(relations, tuple(_REL_FUNCS))] + [(importlib.import_module(m), ns) for m, ns in _REL_FUNC_IMPORTERS]
    saved_f = [(m, n, getattr(m, n)) for m, ns in mods for n in ns]
    PY_REL_FUNCS.update({n: getattr(relations, n) for n in _REL_FUNCS})
    for m, ns in mods:
        for n in ns:
            setattr(m, n, getattr(sa_solver, _REL_FUNCS[n]))

    def undo():
        for n, f in saved.items():
            setattr(R, n, f)
        for m, n, f in saved_f:
            setattr(m, n, f)
    return undo


#: Step scope: scope.py's six port rows that run in `scope_core.rs`, by module attribute -> sa_solver name (`affine_pair` is C1's,
#: term_live's wrapper over `PyTermTable.affine_pair`, and Rust calls it back). `EMPTY` is the Rust `Scope` that `scope_install` makes.
_SCOPE_FUNCS = {
    'Scope': 'Scope', 'linked_terms': 'scope_linked_terms', 'scope_of_atoms': 'scope_scope_of_atoms',
    'theory_scope': 'scope_theory_scope', '_custom_pred': 'scope_custom_pred', 'extension_atoms': 'scope_extension_atoms',
}
#: Modules that import some of them by name, as (module, ((its name, scope's name), ...)). ref.py (the reference engine) is left
#: Python's on purpose, as for `_REL_FUNCS`.
_SCOPE_IMPORTERS = (('satassume.engine', (('Scope', 'Scope'), ('_EMPTY_SCOPE', 'EMPTY'), ('scope_of_atoms', 'scope_of_atoms'),
                                          ('theory_scope', 'theory_scope'))),
                    ('satassume.sympy_api', (('_theory_scope', 'theory_scope'),)))
_SCOPE_PLANTS = ('scope-linked-empty', 'linked-no-rel', 'scope-no-affine', 'theory-no-assume', 'custom-never', 'ext-shallow')
#: Python's, saved at install (with 'EMPTY').
PY_SCOPE_FUNCS = {}


def _install_scope():
    """Returns the undo. Needs `_install_relations` (relations_core's hooks)."""
    import importlib
    from satassume import scope
    empty = sa_solver.scope_install(scope)
    rs = {n: getattr(sa_solver, v) for n, v in _SCOPE_FUNCS.items()}
    rs['EMPTY'] = empty
    PY_SCOPE_FUNCS.update({n: getattr(scope, n) for n in rs})
    py_empty = PY_SCOPE_FUNCS['EMPTY']
    sets = [(scope, n, n) for n in rs] + [(importlib.import_module(m), mine, theirs) for m, ns in _SCOPE_IMPORTERS for mine, theirs in ns]
    saved = [(m, mine, getattr(m, mine)) for m, mine, _ in sets]
    for m, mine, theirs in sets:
        setattr(m, mine, rs[theirs])
    # Default arguments bound at def time: `Session.__init__(engine, scope=EMPTY)` and `Engine._fresh_session(scope=EMPTY)`.
    fns = [f for f in (engine.Session.__init__, engine.Engine._fresh_session) if py_empty in (f.__defaults__ or ())]
    saved_d = [(f, f.__defaults__) for f in fns]
    for f in fns:
        f.__defaults__ = tuple(empty if d is py_empty else d for d in f.__defaults__)

    def undo():
        for m, n, v in saved:
            setattr(m, n, v)
        for f, d in saved_d:
            f.__defaults__ = d
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
    saved = {n: S.__dict__.get(n) for n in ('table', 'base', 'node', 'var', 'dvar', '_dvar')}
    g = (engine.VarTable, engine.compile_formula, engine.formula_literal)
    PY_COMPILE[:] = g[1:]
    S.table = property(_table_get, _table_set)
    S.base = property(_base_get, _base_set)
    S.node, S.var, S.dvar, S._dvar = _node, _var, _dvar_public, _dvar_raw
    engine.VarTable, engine.compile_formula, engine.formula_literal = TableView, _compile_formula, _formula_literal
    undo_rel = _install_relations() if os.environ.get('SLICE_REL', 'rust') == 'rust' else None
    undo_scope = _install_scope() if undo_rel is not None and os.environ.get('SLICE_SCOPE', 'rust') == 'rust' else None
    undo_disc = _install_discovery() if os.environ.get('SLICE_DISC', 'rust') == 'rust' else None
    undo_loop = _install_compile_loop() if os.environ.get('SLICE_LOOP', 'rust') == 'rust' else None
    undo_query = _install_queries() if os.environ.get('SLICE_QUERY', 'rust') == 'rust' else None
    undo_glue = _install_glue() if os.environ.get('SLICE_GLUE', 'rust') == 'rust' else None

    def undo():
        if undo_glue is not None:
            undo_glue()
        if undo_query is not None:
            undo_query()
        if undo_loop is not None:
            undo_loop()
        if undo_disc is not None:
            undo_disc()
        if undo_scope is not None:
            undo_scope()
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
            if PLANT[0] in _REL_PLANTS or PLANT[0] in _DISC_PLANTS or PLANT[0] in _LOOP_PLANTS or PLANT[0] in _QUERY_PLANTS \
                    or PLANT[0] in _SCOPE_PLANTS or PLANT[0] in _GLUE_PLANTS:
                sa_solver.rel_plant(PLANT[0])
        return install()
    return None


def counts():
    return dict(sa_solver.session_counts())
