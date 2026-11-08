"""Step 6d: `knowledge/templates/_common.py`'s per-query rows on Rust (term/common.rs `Common`).

`install(...)` binds Rust's `facts`, `units`, `Rules` (a factory: Rust's `Rules`, or Python's on a kept query),
`lits`, `ge2_alternatives`, `consts_of`, `pattern_key` and `const_key` in `_common` and in every runtime module that
imported them by name, and hands Rust's `wide_formulas` to the dispatch. Not rebound, by ruling: `limits.py` (kept on
Python), `table.py` (offline, and `core.ipi_rules`' kept path) and the offline tools.

Python still runs, named and counted in COUNTS: the template's `gen()` (`common:python:gen`), `const_value`
(`common:python:const_value`, a SymPy read of a numeric constant), and, on a kept query, Python's own function
(`common:kept:<name>`). The cache is `_common._CACHE` itself, so `state.memos` and `register` empty the one table.
"""
import sys

import knowledge_core_live
import sa_solver
import term_live
from satassume.knowledge.templates import _common
from satassume.sat.formula import And, Implies, Not, Or, P

NAMES = ('facts', 'units', 'Rules', 'lits', 'ge2_alternatives', 'consts_of', 'pattern_key', 'const_key')
#: Runtime modules that take `_common`'s names at import. `limits` and `table` keep Python's (module docstring).
MODULES = tuple('satassume.knowledge.templates.' + m for m in (
    'wiring', 'functions', 'core', 'nodes', 'special', 'atoms', 'rootof', 'stats', 'physics', '_rows_runtime'))
PLANTS = ('common-facts-drop', 'common-units-drop', 'common-max-cache-off', 'common-key-shape-off',
          'common-compiled-swap', 'common-wide-drop', 'common-rule-drop', 'common-equiv-one', 'common-lits-flip',
          'common-ge2-drop', 'common-consts-of-skip', 'common-pattern-key-type', 'common-const-key-type')
#: 6g(b): wiring's rows families on Rust (term/rows_tpl.rs `PLANTS`), set on `Common`, which the rows templates read.
PLANTS += ('rows-block-key-n', 'rows-rules-for-shape', 'rows-of-constant-skip', 'rows-matches-constant',
           'rows-expand-drop-last', 'rows-placements-first', 'rows-matches-coefficient', 'rows-instances-others',
           'rows-count-flip', 'rows-clauses-concl-only', 'rows-wide-drop', 'rows-piecewise-last', 'rows-mul-sets-first',
           'rows-add-bound-skip', 'rows-pow-key-same', 'rows-pow-times-skip', 'rows-pow-head-any',
           'rows-pow-irrational-skip', 'rows-pow-ipi-skip', 'rows-pow-unit-drop', 'rows-pow-of-constant-skip')
#: 6g(c): the direct core splits in rows_tpl.rs.
PLANTS += ('rows-half-parity', 'rows-bound-coeff-one', 'rows-imag-drop-last')
COMMON = [None]


def install(kn, counts, fault, contradiction, plant=None, dispatch=None):
    py_fns = {n: getattr(_common, n) for n in NAMES}
    rust_fns = dict(py_fns)
    if knowledge_core_live.SHADOW_SPLIT[0] is not None:        # 6g(c): the shadow of rows_tpl.rs's direct splits
        rust_fns['_shadow_split'] = knowledge_core_live.SHADOW_SPLIT[0]
    c = sa_solver.Common(kn, _common._CACHE, _common.MAX_CACHE, _common.MAX_EXPAND, _common.Pattern
                         if isinstance(_common.Pattern, type) else _common.Pattern.__wrapped__, _common.Compiled,
                         _common.TemplateKeyError, fault, contradiction, _common.const_value, term_live._local,
                         rust_fns, (P, Not, Or, Implies, And))
    if plant in PLANTS:
        c.set_plant(plant)
    COMMON[0] = c
    rust = {'facts': c.facts, 'units': c.units, 'Rules': c.make_rules, 'lits': c.lits,
            'ge2_alternatives': c.ge2_alternatives, 'consts_of': c.consts_of, 'pattern_key': c.pattern_key,
            'const_key': c.const_key}
    saved = []
    for m in [_common] + [sys.modules[n] for n in MODULES if n in sys.modules]:
        for n, f in py_fns.items():
            if m.__dict__.get(n) is f:
                saved.append((m, n, f))
                setattr(m, n, rust[n])
    if dispatch is not None:
        dispatch.set_common(c)

    def flush():
        for k, v in c.counts().items():
            counts[k] += v
            if k == 'plant:fired':
                s = sys.modules.get('session_live')
                if s is not None:
                    s.PLANT_FIRED[0] += v
        c.clear_counts()
    import atexit
    atexit.register(flush)

    def undo():
        flush()
        atexit.unregister(flush)
        for m, n, f in saved:
            setattr(m, n, f)
        # a module imported after install (lazy registration) took Rust's names from `_common`
        for name in MODULES:
            m = sys.modules.get(name)
            for n, f in rust.items():
                if m is not None and m.__dict__.get(n) is f:
                    setattr(m, n, py_fns[n])
        if dispatch is not None:
            dispatch.set_common(None)
        COMMON[0] = None
    return undo
