"""Stage 0 of the fact-lattice plan: what the rule block writes, who reads it,
how many distinct asserted sets there are, and which search answers rest on
a rule-block case split.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy:agent-reports/scripts \\
        python agent-reports/scripts/facts_census.py stream.pkl [out.json]

Replays the refine stream through ``satassume.sympy_api.ask`` (answers are
checked against the recording) with the solver and the engine instrumented
from the outside by wrapping methods; nothing under ``satassume/`` changes.

Rule writes.  A *rule write* is a literal the rule block assigns: a trail
entry appended by ``Solver._propagate`` whose reason is an int (a block
implication), or a root unit ``Solver._rb_settle`` adds when a block is
registered over assigned variables.

Mentions.  Every clause the engine adds is tagged with the engine step that
added it (a stack of tags set by wrappers on the engine methods; innermost
wins): ``cache`` (cached facts imported as units, ``Session._add_clauses``),
``template`` (``_emit_pattern``, ``_compile``), ``custom`` (``_custom``),
``assumption`` (``assume_formula``), ``queryf`` (``literal_of``: Tseitin of a
compound proposition), ``link`` / ``guard`` (``Relations._link`` /
``_interpret``), ``other`` (``Engine.ask``'s cone memo clause and anything
untagged); plus ``theory`` (``Solver.register_atom``), ``query`` (the
literal of ``Session.query_literal``) and ``learnt`` (``Solver._analyze``'s
learnt clause).  A variable is *mentioned* by a tag if some clause with that
tag contains it, at any time in the session's life.  Section 2.3 of the plan
allocates a predicate variable iff it is mentioned by something other than
the rule block, the cache (imported into the theory instead) and learnt
clauses (derived from rule reasons; under the design they would be built
from theory explanations over existing variables).

Reads (dynamic, a lower bound on use): a rule write is *read* if, while it
stands, it is an antecedent of a non-rule clause's propagation (a false
literal of the reason clause of a later trail entry), is in a conflict
clause returned by ``_propagate``, is the query variable, or its variable is
a theory atom (the theory is told).  Antecedents of other rule implications
do not count (they stay inside the rule base).

Asserted sets.  After every ``_propagate`` call, for each node block with a
new trail entry not implied by the rule block, the set of that block's
literals assigned for another reason (decision, assumption, clause, root
unit, theory) and the set of all its assigned literals.  Distinct sets bound
the size of the closure memo of section 2.1.

Case splits.  For every ``Solver.entails`` that searched (unit propagation
did not settle the literal) and returned True/False, the design's
propagation is simulated on the session's non-rule, non-learnt clauses: unit
propagation over the clauses plus the *exact* closure of each block
(``facts_closure.closure``), to a fixpoint.  If that decides the literal,
the search was only needed for a case split inside the rule base; if not,
the answer needs search in the design too (a template or theory case
split).  The same simulator with unit propagation over the rule block
instead of the exact closure is the control: it must not decide these
literals (today's propagation did not), except through theory reasoning it
does not model.
"""
import gc, json, pickle, sys, time, weakref
from collections import Counter

import facts_closure
from satassume import sympy_api
from satassume.engine import Engine, Session
from satassume.relations import Relations
from satassume.rules import NPRED, PREDICATES, RULE_INSTANTIATED, unit_propagate
from satassume.solver import Solver

TAGS = ["cache", "template", "custom", "assumption", "queryf", "link", "guard",
        "other", "theory", "query", "learnt"]
BIT = {t: 1 << i for i, t in enumerate(TAGS)}
DESIGN_MASK = sum(BIT[t] for t in TAGS if t not in ("cache", "learnt"))

R_CLAUSE, R_CONFL, R_QUERY, R_THEORY = 1, 2, 4, 8

_stack = ["other"]


def tagged(cls, name, tag):
    orig = getattr(cls, name)

    def wrapper(*a, **k):
        _stack.append(tag)
        try:
            return orig(*a, **k)
        finally:
            _stack.pop()
    wrapper.__name__ = name
    setattr(cls, name, wrapper)


tagged(Session, "_add_clauses", "cache")
tagged(Session, "_emit_pattern", "template")
tagged(Session, "_compile", "template")
tagged(Session, "_custom", "custom")
tagged(Session, "assume_formula", "assumption")
tagged(Session, "literal_of", "queryf")
tagged(Relations, "_link", "link")
tagged(Relations, "_interpret", "guard")
tagged(Engine, "ask", "other")

# ---------------------------------------------------------------- totals
T = Counter()               # global counters
WRITE_BY_TAGS = Counter()   # rule writes by the mention mask of their variable (as tag tuple)
BLOCK_MENTIONS = Counter()  # predicates mentioned per block (design mask) -> blocks
BLOCK_MENTIONS_ALL = Counter()
ASSERTED = Counter()        # (pos, neg) masks of asserted sets -> occurrences
CLOSED = Counter()
PRED_MENTION = Counter()    # predicate -> blocks where the design mentions it
PRED_WRITES = Counter()     # predicate -> rule writes
PRED_WRITES_UNMENTIONED = Counter()
SEARCH = []                 # per search-definite entails: classification


class Rec:
    __slots__ = ("mention", "wvar", "wread", "wroot", "cur", "clauses", "table",
                 "tvars", "qvars")

    def __init__(self):
        self.mention = {}       # var -> tag mask
        self.wvar = []          # rule writes: variable
        self.wread = []         # rule writes: read mask
        self.wroot = []         # rule writes: at root
        self.cur = {}           # var -> index of its standing rule write
        self.clauses = []       # non-rule, non-learnt clauses (external lits)
        self.table = None
        self.tvars = set()
        self.qvars = set()


def rec_of(s):
    r = s.__dict__.get("_census")
    if r is None:
        r = s.__dict__["_census"] = Rec()
        FINALIZERS.append(weakref.finalize(s, finish, r))
    return r


FINALIZERS = []


def mention(r, vars_, tag):
    b = BIT[tag]
    m = r.mention
    for v in vars_:
        m[v] = m.get(v, 0) | b


# ---------------------------------------------------------------- solver hooks
_orig_add_clause = Solver.add_clause
_orig_add_clauses = Solver.add_clauses
_orig_add_internal = Solver.add_internal
_orig_register_atom = Solver.register_atom
_orig_analyze = Solver._analyze
_orig_propagate = Solver._propagate
_orig_settle = Solver._rb_settle
_orig_entails = Solver.entails
_orig_solve = Solver._solve


def add_clause(self, lits):
    lits = list(lits)
    r = rec_of(self)
    mention(r, [abs(l) for l in lits], _stack[-1])
    r.clauses.append(lits)
    return _orig_add_clause(self, lits)


def add_clauses(self, clauses):
    clauses = [list(c) for c in clauses]
    r = rec_of(self)
    tag = _stack[-1]
    for c in clauses:
        mention(r, [abs(l) for l in c], tag)
        r.clauses.append(c)
    return _orig_add_clauses(self, clauses)


def add_internal(self, clauses):
    clauses = [list(c) for c in clauses]
    r = rec_of(self)
    tag = _stack[-1]
    for c in clauses:
        mention(r, [l >> 1 for l in c], tag)
        r.clauses.append([-(l >> 1) if l & 1 else (l >> 1) for l in c])
    return _orig_add_internal(self, clauses)


def register_atom(self, theory, var, payload):
    r = rec_of(self)
    mention(r, [int(var)], "theory")
    r.tvars.add(int(var))
    return _orig_register_atom(self, theory, var, payload)


def _analyze(self, confl):
    learnt, bt = _orig_analyze(self, confl)
    mention(rec_of(self), [l >> 1 for l in learnt], "learnt")
    return learnt, bt


def _scan(self, r, start, confl):
    trail = self._trail
    reason = self._reason
    level = self._level
    cur = r.cur
    wread = r.wread
    rb_base = self._rb_base
    touched = set()
    for k in range(start, len(trail)):
        l = trail[k]
        v = l >> 1
        rs = reason[v]
        if type(rs) is int:
            cur[v] = len(r.wvar)
            r.wvar.append(v)
            r.wread.append(0)
            r.wroot.append(level[v] == 0)
        else:
            if rs is not None:
                for m in rs:
                    u = m >> 1
                    if u != v:
                        w = cur.get(u)
                        if w is not None and type(reason[u]) is int:
                            wread[w] |= R_CLAUSE
            b = rb_base[v]
            if b:
                touched.add(b)
    if confl is not None and type(confl) is not int:
        for m in confl:
            u = m >> 1
            w = cur.get(u)
            if w is not None and type(reason[u]) is int and self._val[m] is False:
                wread[w] |= R_CONFL
    if touched:
        val = self._val
        for b in touched:
            pos = neg = cpos = cneg = 0
            for i in range(NPRED):
                v = b + i
                x = val[2 * v]
                if x is None:
                    continue
                bit = 1 << i
                if x:
                    cpos |= bit
                else:
                    cneg |= bit
                if type(reason[v]) is not int:
                    if x:
                        pos |= bit
                    else:
                        neg |= bit
            ASSERTED[(pos, neg)] += 1
            CLOSED[(cpos, cneg)] += 1


def _propagate(self):
    # from the queue head, not the trail's end: entries queued before this
    # call (decisions, units, learnt asserting literals, theory
    # implications) are processed by it and must be scanned too
    start = self._qhead
    confl = _orig_propagate(self)
    _scan(self, rec_of(self), start, confl)
    return confl


def _rb_settle(self, base):
    trail = self._trail
    start = len(trail)
    reason = self._reason
    r = rec_of(self)
    n0 = len(r.wvar)
    ok = _orig_settle(self, base)
    # root units of the block itself: reason None, level 0, appended before
    # the nested _propagate (which records its own entries)
    seen = set(r.wvar[n0:])
    for k in range(start, len(trail)):
        v = trail[k] >> 1
        if reason[v] is None and v not in seen and base <= v < base + NPRED:
            r.cur[v] = len(r.wvar)
            r.wvar.append(v)
            r.wread.append(0)
            r.wroot.append(True)
            T["settle_writes"] += 1
    return ok


# ---------------------------------------------------------------- case splits
def _solve(self, lits, keep):
    self.__dict__["_census_solves"] = self.__dict__.get("_census_solves", 0) + 1
    return _orig_solve(self, lits, keep)


def entails(self, lit, assumptions=()):
    assumptions = list(assumptions)
    self.__dict__["_census_solves"] = 0
    trail = self._assume(assumptions)
    decided_up = trail is not None and (
        (2 * abs(lit) + (lit < 0)) in trail or (2 * abs(lit) + (lit > 0)) in trail)
    res = _orig_entails(self, lit, assumptions)
    if res is not None and not decided_up:
        T["search_definite"] += 1
        r = rec_of(self)
        SEARCH.append(simulate(self, r, lit, assumptions, res))
    elif not decided_up:
        T["search_none"] += 1
    return res


def slots_of(r):
    return r.table.slots if r.table is not None else None


def simulate(solver, r, lit, assumptions, res):
    """The design's propagation (unit propagation over the non-rule clauses
    plus the exact closure per block) and the control (rule-block UP)."""
    slots = slots_of(r)
    blocks = {}
    if slots is not None:
        for v in range(1, len(slots)):
            e = slots[v]
            if type(e) is tuple:
                blocks[v] = e[1]
    out = {"answer": res, "theories": bool(solver._theories),
           "nclauses": len(r.clauses), "nvars": solver._nvars}
    for mode in ("exact", "up"):
        out[mode] = _sim(r.clauses, blocks, assumptions, lit, mode)
    return out


def _sim(clauses, blocks, assumptions, lit, mode):
    """'true'/'false' if the fixpoint decides lit, 'refute' if it only
    refutes the opposite by a conflict, 'conflict' if the assumptions alone
    conflict, else 'open'."""
    def fix(start):
        a = set(start)
        if any(-x in a for x in a):
            return None
        bases = {}
        for v, b in blocks.items():
            bases.setdefault(b, None)
        while True:
            n0 = len(a)
            if not facts_closure._up(clauses, a):
                return None
            by_block = {}
            for x in a:
                b = blocks.get(abs(x))
                if b is not None:
                    by_block.setdefault(b, []).append(x)
            for b, xs in by_block.items():
                rel = [(abs(x) - b + 1) * (1 if x > 0 else -1) for x in xs]
                c = facts_closure.closure(rel) if mode == "exact" else \
                    (lambda s: None if s is None else frozenset(s))(unit_propagate(RULE_INSTANTIATED, rel))
                if c is None:
                    return None
                for y in c:
                    z = (abs(y) - 1 + b) * (1 if y > 0 else -1)
                    if -z in a:
                        return None
                    a.add(z)
            if len(a) == n0:
                return a
    base = fix(assumptions)
    if base is None:
        return "conflict"
    if lit in base:
        return "true"
    if -lit in base:
        return "false"
    if fix(list(assumptions) + [-lit]) is None:
        return "refute-true"
    if fix(list(assumptions) + [lit]) is None:
        return "refute-false"
    return "open"


# ---------------------------------------------------------------- finish
def finish(r):
    """Aggregate one solver's record (called when the solver dies, or at the
    end of the run)."""
    m = r.mention
    wread = r.wread
    for k, v in enumerate(r.wvar):
        mask = m.get(v, 0)
        if v in r.tvars:
            wread[k] |= R_THEORY
        if mask & BIT["query"]:
            wread[k] |= R_QUERY
        T["writes"] += 1
        if r.wroot[k]:
            T["writes_root"] += 1
        design = bool(mask & DESIGN_MASK)
        T["writes_mentioned_design"] += design
        T["writes_mentioned_any"] += bool(mask)
        T["writes_mentioned_with_cache"] += bool(mask & (DESIGN_MASK | BIT["cache"]))
        T["writes_read"] += bool(wread[k])
        T["writes_read_clause"] += bool(wread[k] & R_CLAUSE)
        T["writes_read_confl"] += bool(wread[k] & R_CONFL)
        T["writes_read_query"] += bool(wread[k] & R_QUERY)
        T["writes_read_theory"] += bool(wread[k] & R_THEORY)
        T["writes_read_and_unmentioned"] += bool(wread[k]) and not design
        WRITE_BY_TAGS[tuple(t for t in TAGS if mask & BIT[t])] += 1
        slots = slots_of(r)
        if slots is not None and v < len(slots) and type(slots[v]) is tuple:
            p = PREDICATES[v - slots[v][1]]
            PRED_WRITES[p] += 1
            if not design:
                PRED_WRITES_UNMENTIONED[p] += 1
    slots = slots_of(r)
    if slots is not None:
        bases = sorted({e[1] for e in slots if type(e) is tuple})
        for b in bases:
            nd = na = 0
            for i in range(NPRED):
                mask = m.get(b + i, 0)
                if mask & DESIGN_MASK:
                    nd += 1
                    PRED_MENTION[PREDICATES[i]] += 1
                if mask:
                    na += 1
            BLOCK_MENTIONS[nd] += 1
            BLOCK_MENTIONS_ALL[na] += 1
        T["blocks"] += len(bases)
    T["solvers"] += 1
    r.wvar = r.wread = r.wroot = r.clauses = None
    r.cur = r.mention = None


Solver.add_clause = add_clause
Solver.add_clauses = add_clauses
Solver.add_internal = add_internal
Solver.register_atom = register_atom
Solver._analyze = _analyze
Solver._propagate = _propagate
Solver._rb_settle = _rb_settle
Solver._solve = _solve
Solver.entails = entails

_orig_session_init = Session.__init__


def session_init(self, engine):
    _orig_session_init(self, engine)
    rec_of(self.solver).table = self.table


Session.__init__ = session_init

_orig_query_literal = Session.query_literal


def query_literal(self, lit, assumptions=(), search=True):
    mention(rec_of(self.solver), [abs(lit)], "query")
    return _orig_query_literal(self, lit, assumptions, search)


Session.query_literal = query_literal


def main():
    stream = pickle.load(open(sys.argv[1], "rb"))
    out_path = sys.argv[2] if len(sys.argv) > 2 else None
    t0 = time.perf_counter()
    bad = 0
    for i, (p, a, rec) in enumerate(stream):
        got = sympy_api.ask(p, a)
        if got is not rec:
            bad += 1
    dt = time.perf_counter() - t0
    sympy_api.set_default_engine(Engine())
    gc.collect()
    for f in FINALIZERS:
        f()
    w = T["writes"]
    print(f"replay {dt:.1f}s instrumented; answers differing from the recording: {bad}")
    print(f"solvers {T['solvers']}, node blocks {T['blocks']}")
    print(f"rule writes {w} (root {T['writes_root']}, from _rb_settle {T['settle_writes']})")
    for k in ("writes_mentioned_design", "writes_mentioned_with_cache", "writes_mentioned_any",
              "writes_read", "writes_read_clause", "writes_read_confl", "writes_read_query",
              "writes_read_theory", "writes_read_and_unmentioned"):
        print(f"  {k:32s} {T[k]:8d}  {100 * T[k] / max(w, 1):5.1f}%")
    print("predicates mentioned per block (design: excl. cache and learnt):")
    nb = sum(BLOCK_MENTIONS.values())
    mean = sum(k * c for k, c in BLOCK_MENTIONS.items()) / max(nb, 1)
    meana = sum(k * c for k, c in BLOCK_MENTIONS_ALL.items()) / max(nb, 1)
    print(f"  mean {mean:.2f} (with cache and learnt: {meana:.2f}) of {NPRED}")
    print("  histogram:", sorted(BLOCK_MENTIONS.items()))
    print("top predicates by blocks mentioning them:", PRED_MENTION.most_common(12))
    print("rule writes by the mention tags of their variable (top 15):")
    for k, c in WRITE_BY_TAGS.most_common(15):
        print(f"  {c:8d} {100 * c / max(w, 1):5.1f}%  {'+'.join(k) or '(none)'}")
    print(f"asserted sets: {sum(ASSERTED.values())} observations, {len(ASSERTED)} distinct; "
          f"closed sets: {len(CLOSED)} distinct")
    cls = Counter((s["exact"], s["up"], s["theories"]) for s in SEARCH)
    print(f"search-definite entails: {T['search_definite']} (search None: {T['search_none']})")
    for k, c in cls.most_common():
        print(f"  {c:5d}  design={k[0]:12s} control={k[1]:12s} theories={k[2]}")
    print(f"closure memo entries: {facts_closure.memo_size()}")
    if out_path:
        json.dump({"totals": T, "block_mentions": sorted(BLOCK_MENTIONS.items()),
                   "block_mentions_all": sorted(BLOCK_MENTIONS_ALL.items()),
                   "pred_mention": PRED_MENTION, "pred_writes": PRED_WRITES,
                   "pred_writes_unmentioned": PRED_WRITES_UNMENTIONED,
                   "writes_by_tags": [["+".join(k), c] for k, c in WRITE_BY_TAGS.most_common()],
                   "asserted_distinct": len(ASSERTED), "asserted_obs": sum(ASSERTED.values()),
                   "closed_distinct": len(CLOSED), "search": SEARCH},
                  open(out_path, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
