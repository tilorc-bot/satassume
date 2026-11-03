"""Prototype of the model-checked lazy escalation, as a monkeypatch (bound only).
usage: lazy_sim.py WORKLOAD {base|lazy} [answers.json]"""
import sys, time, json, gc
from collections import defaultdict, deque
sys.setrecursionlimit(10000)
from evalbench.common import workload, ask_all
from satassume import engine as E, sympy_api
clock = time.perf_counter
wl, mode = sys.argv[1], sys.argv[2]
N = defaultdict(int)
ctx = ['other']

def visit_all(s):
    """Visit every unvisited node of the cone, parking all its clauses."""
    while s.frontier or s.deferred:
        n = s.frontier.popleft() if s.frontier else s.deferred.pop()
        if n not in s.base:
            s.node(n, set()); N[ctx[-1], 'nodes_visited'] += 1
    s.frontier = deque()
    if s.pending:   # parked formulas: compiled as today (none seen on dev)
        while s.pending:
            node, fs = s.pending.popitem(); s._compile(node, fs)
            N[ctx[-1], 'formulas_built'] += len(fs)
        visit_all(s)

def check_and_build(s):
    """Build the parked clauses the last model violates; return how many."""
    solver = s.solver; mv = solver._mvals; fill = solver._fill; nm = len(mv)
    out = []; newpc = {}
    for node, groups in s.pending_c.items():
        keep = []
        for clauses, bases in groups:
            rest = []
            for c in clauses:
                for k, off in c[2]:
                    l = bases[k] + off; v = l >> 1
                    x = mv[v - 1] if v <= nm else None
                    if x is None and v <= nm:
                        x = fill(mv, v)
                    if x is not None and x == (not (l & 1)):
                        rest.append(c); break
                else:
                    out.append([bases[k] + off for k, off in c[2]])
            if rest:
                keep.append((rest, bases))
        if keep:
            newpc[node] = keep
    N[ctx[-1], 'checked'] += 1
    if out:
        s.pending_c.clear(); s.pending_c.update(newpc)
        solver.ensure_vars(len(s.table))
        solver.add_internal(out)
        N[ctx[-1], 'clauses_built'] += len(out)
    return len(out)

def parked(s):
    return sum(len(c) for g in s.pending_c.values() for c, _ in g)

def lazy_sat(s, A):
    while True:
        visit_all(s)
        if s.xfer is not None:
            s.xfer.sync_transfer()
        N[ctx[-1], 'searches'] += 1
        if not s.solver.solve(A):
            return False
        if not check_and_build(s):
            return True

def complete_check(s, lits):
    solver = s.solver
    if s.xfer is not None:
        s.xfer.sync_transfer()
    if not solver.propagate() or solver.implied(lits) is None:
        return E.INCONSISTENT
    N['check', 'calls'] += 1
    if s.incomplete:
        ctx.append('check'); N['check', 'lazy'] += 1
        visit_all(s); N['check', 'parked_at_start'] += parked(s)
        try:
            ok = lazy_sat(s, lits)
        finally:
            ctx.pop()
        if not ok:
            return E.INCONSISTENT
    elif not solver.solve(lits):
        return E.INCONSISTENT
    if E._gave_up(s) or E._exhausted(s) or s.truncated:
        return E.UNKNOWN
    return E.CONSISTENT

def _ask(self, s, lits, proposition, contextual):
    s.solver.release(s.n_hold)
    q = s.prepare_query(proposition)
    lits = s.assumption_lits(proposition)
    r = s.query_literal(q, lits, search=False)
    if r is None and s.incomplete and type(q) is not tuple:
        self.stats["escalations"] += 1
        s.solver.release(s.n_hold)
        ctx.append('ask'); N['ask', 'lazy'] += 1
        try:
            solver = s.solver
            if s.xfer is not None:
                s.xfer.sync_transfer()
            if not solver.propagate():
                raise E.InconsistentAssumptions("rule base or declared facts (templates) are inconsistent")
            solver.mention((q,))
            visit_all(s); N['ask', 'parked_at_start'] += parked(s)
            if not lazy_sat(s, lits + [-q]):
                if not lazy_sat(s, lits + [q]):
                    raise E.InconsistentAssumptions("inconsistent assumptions")
                r = True
            else:
                r = None if lazy_sat(s, lits + [q]) else False
        finally:
            ctx.pop()
    else:
        if r is None and s.incomplete:
            N['ask', 'tuple_fallback'] += 1
            self.stats["escalations"] += 1
            s.solver.release(s.n_hold); s.escalate()
            r = s.query_literal(q, lits, search=False)
        if r is None:
            self.stats["searches"] += 1
            N['ask', 'plain_searches'] += 1
            r = s.query_literal(q, lits, search=True)
    if contextual and E._gave_up(s):
        self.stats["theory_gave_up"] += 1
    self._note_budget(s)
    return r

if mode == 'lazy':
    E.Engine._complete_check = staticmethod(complete_check)
    E.Engine._ask = _ask
elif mode == 'base':  # count today's searches the same way
    orig = E.Session.query_literal
    def ql(self, lit, assumptions=(), search=True):
        if search: N['base', 'searches'] += 1
        return orig(self, lit, assumptions, search)
    E.Session.query_literal = ql

import os
if os.environ.get('LZ_PHASE'):
    TT = defaultdict(float)
    def timed(name, f):
        def w(*a, **k):
            t = clock()
            try: return f(*a, **k)
            finally: TT[name] += clock() - t
        return w
    E.Engine._complete_check = staticmethod(timed('check', E.Engine._complete_check))
    E.Engine._ask = timed('ask', E.Engine._ask)
    _cab = check_and_build
    check_and_build = timed('check_and_build', _cab)
    globals()['check_and_build'] = check_and_build
    _so = E.Session.escalate
    E.Session.escalate = timed('escalate', _so)
    import atexit
    atexit.register(lambda: print(json.dumps({k: round(v, 4) for k, v in TT.items()})))
if wl.startswith('fuzz:'):
    from evalbench.fuzz import queries
    pairs = queries(int(wl[5:]))
else:
    pairs = workload(wl)
gc.collect(); gc.freeze()
t = clock(); per = []
ans = ask_all(sympy_api.ask, pairs, clock, per)
tot = clock() - t
if len(sys.argv) > 3:
    json.dump(ans, open(sys.argv[3], 'w'))
print(json.dumps({'workload': wl, 'mode': mode, 'total_s': round(tot, 4),
  'none_s': round(sum(p for p, a in zip(per, ans) if a is None), 4),
  'N': {f'{a}/{b}': v for (a, b), v in sorted(N.items())}}))
