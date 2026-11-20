"""current360.py WL... (sa-port-360; the planner's check on 359's base row: the last query's _Query stays referenced
until the next conversion). At every call of sympy_api._engine_ask, what term_live.current() is: this ask's own _Query
(made by term_live._convert inside this top-level ask; with a table, or kept with its reason), a _Refused (the second
run of a discarded query), None, or STALE (a _Query some earlier top-level ask made). Also: current() after each
top-level ask returns, and at a direct call of _engine_ask outside any ask right after a converted query."""
import collections, os, sys, warnings
warnings.simplefilter('ignore')
S = os.environ["SLICE_DIR"]; sys.path.insert(0, S)
import p_install; p_install.install()
from satassume import sympy_api
import sa_solver, backend
backend.install_euf()
import term_live; term_live.from_env()
import lra_live; lra_live.from_env()
import session_live; session_live.from_env()
import knowledge_live; knowledge_live.from_env()
backend.install()
import convert, live, witness_live
seen = collections.Counter()
made, earlier, depth = [], [], [0]
real_convert, real_engine_ask, real_ask = term_live._convert, sympy_api._engine_ask, sympy_api._ask
def _convert(*a, **k):
    q = real_convert(*a, **k); made.append(q); return q
def _engine_ask(p, a, eng):
    c = term_live.current()
    if c is None: k = 'none'
    elif isinstance(c, term_live._Refused): k = 'refused-second-run'
    elif any(c is q for q in made): k = 'own:' + ('table' if c.kept is None else 'kept:' + str(c.kept))
    elif any(c is q for q in earlier): k = 'STALE'
    else: k = 'OTHER'
    seen[('in-ask ' if depth[0] else 'direct ') + k] += 1
    return real_engine_ask(p, a, eng)
def _ask(p, a, eng):
    top = depth[0] == 0
    if top:
        earlier[:] = (earlier + made)[-3:]; del made[:]      # the three queries before this one, held: a stale one would be one of them
    depth[0] += 1
    try: return real_ask(p, a, eng)
    finally:
        depth[0] -= 1
        if top: seen['after-ask ' + ('none' if term_live.current() is None else 'NOT-NONE')] += 1
term_live._convert, sympy_api._engine_ask, sympy_api._ask = _convert, _engine_ask, _ask
for wl in sys.argv[1:]:
    seen.clear(); n = raised = 0
    pairs = live.load(wl)
    for p, a in pairs:
        n += 1
        try: sympy_api.ask(p, a)
        except Exception: raised += 1
    # a direct call outside any ask, right after the workload's last query (its _Query is 359's base row: still referenced)
    from sympy import Q, Symbol
    x = Symbol('x'); eng = sympy_api.default_engine()
    w0 = dict(witness_live.COUNTS).get('wn:fallback:off', 0)
    try: r = sympy_api._engine_ask(Q.positive(x), Q.positive(x), eng)
    except Exception as e: r = type(e).__name__
    print(wl, 'queries', n, 'raised', raised, 'walker', getattr(convert.WALK[0], 'ITEMS', 'py'), dict(sorted(seen.items())),
          '| direct call answer', r, 'wn:fallback:off +', dict(witness_live.COUNTS).get('wn:fallback:off', 0) - w0, flush=True)
