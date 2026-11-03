"""Instrumentation only: break Session.escalate down by step kind and caller."""
import sys, time, json, gc
from collections import defaultdict
sys.setrecursionlimit(10000)
from evalbench.common import workload, ask_all
from satassume import engine as E, sympy_api
from collections import deque
clock = time.perf_counter
ctx = ['other']
T = defaultdict(float); N = defaultdict(int)

def wrapctx(name, f):
    def w(*a, **k):
        ctx.append(name)
        try: return f(*a, **k)
        finally: ctx.pop()
    return w
E.Engine._complete_check = staticmethod(wrapctx('check', E.Engine._complete_check))
E.Engine._ask = wrapctx('ask', E.Engine._ask)
E.Engine._decide = wrapctx('decide', E.Engine._decide)

def escalate(self, budget=None):
    c = ctx[-1]
    N[c, 'calls'] += 1
    nb0 = len(self.base); nv0 = len(self.table)
    t0 = clock()
    while self.pending or self.pending_c or self.deferred or self.frontier:
        t = clock()
        if self.pending_c:
            node, pend = self.pending_c.popitem()
            for clauses, bases in pend:
                self._emit_pattern(clauses, bases)
                N[c, 'pc_groups'] += 1; N[c, 'pc_clauses'] += len(clauses)
            k = 'pending_c'
        elif self.pending:
            node, formulas = self.pending.popitem()
            self._compile(node, formulas)
            N[c, 'pf'] += len(formulas)
            k = 'pending'
        elif self.frontier:
            n = self.frontier.popleft(); k = 'frontier'
            if n not in self.base:
                self.node(n, None); N[c, 'frontier_nodes'] += 1
        else:
            n = self.deferred.pop(); k = 'deferred'
            if n not in self.base:
                self.node(n, None); N[c, 'deferred_nodes'] += 1
        T[c, k] += clock() - t
    T[c, 'total'] += clock() - t0
    N[c, 'nodes'] += len(self.base) - nb0
    N[c, 'vars'] += len(self.table) - nv0
    self.frontier = deque()
E.Session.escalate = escalate

wl = sys.argv[1] if len(sys.argv) > 1 else 'dev'
if wl.startswith('fuzz:'):
    from evalbench.fuzz import queries
    pairs = queries(int(wl[5:]))
else:
    pairs = workload(wl)
gc.collect(); gc.freeze()
t = clock(); per = []
ans = ask_all(sympy_api.ask, pairs, clock, per)
tot = clock() - t
print(json.dumps({'workload': wl, 'n': len(pairs), 'total_s': round(tot, 4),
  'none_s': round(sum(p for p, a in zip(per, ans) if a is None), 4),
  'T': {f'{a}/{b}': round(v, 4) for (a, b), v in sorted(T.items())},
  'N': {f'{a}/{b}': v for (a, b), v in sorted(N.items())}}, indent=1))
