"""record.py WORKLOAD OUTDIR [--timers]: replay dev or fuzz 424242 through the real engine and record every
public Solver call with the Python theories' answers, as data the two replays read.

Monkeypatches only (as tools-rust/rc.py does); nothing in the package changes. Theories are recorded per theory
in call order, so a replay that takes a different search path fails at once on an unexpected theory call.

--timers: no recording; outermost timers on the Solver's public methods, minus outermost theory calls, for an
independent estimate of the solver's share of a live pass.
"""
import gc
import hashlib
import inspect
import json
import os
import sys
import time
import weakref
from array import array

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from common_trace import COUNTERS, EXC, MAGIC, OPS, T_ASSERT, T_CHECK, T_DECIDE, T_PROP, crc, norm  # noqa: E402

wl, outdir = sys.argv[1], sys.argv[2]
TIMERS = "--timers" in sys.argv

from evalbench.common import workload  # noqa: E402
from satassume import sympy_api  # noqa: E402
from satassume.sat import solver as solver_mod  # noqa: E402
from satassume.sat.solver import BOTTOM, Solver  # noqa: E402

if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)

pc = time.perf_counter


class S:
    depth = 0           # inside a public Solver call
    tdepth = 0          # inside a theory call made by the solver
    api = array("I")
    res = array("I")
    tapes = []          # per theory id, array('I')
    next_sid = 0
    blocks = {}
    patterns = {}
    keep = []           # blocks and patterns stay alive, so their ids stay unique
    ops = {}
    nested = 0
    owners = 0
    pushes = 0
    pops = 0
    ntheory = {}
    last = {}           # sid -> counters at the last look
    total = [0] * len(COUNTERS)
    t_solver = 0.0
    t_theory = 0.0
    calls = 0


PATCHED = set()


def words(xs):
    S.api.extend(x & 0xFFFFFFFF for x in xs)


def mask(m):
    return [(m >> (32 * i)) & 0xFFFFFFFF for i in range(4)]


def tape_of(theory):
    return S.tapes[theory._rec_tid]


def tput(t, xs):
    t.extend(x & 0xFFFFFFFF for x in xs)


def patch_theory_class(cls):
    if cls in PATCHED:
        return
    PATCHED.add(cls)

    def guard(fn, record, name):
        def w(self, *a):
            if not S.depth or S.tdepth:
                return fn(self, *a)
            S.ntheory[name] = S.ntheory.get(name, 0) + 1
            S.tdepth = 1
            try:
                r = fn(self, *a)
                return record(self, a, r)
            finally:
                S.tdepth = 0
        return w

    def r_assert(self, a, r):
        if r is not None and r[0] is False:
            c = list(r[1])
            tput(tape_of(self), [T_ASSERT, a[0], len(c), *c])
        else:
            tput(tape_of(self), [T_ASSERT, a[0], -1])
        return r

    def r_prop(self, a, r):
        r = [(x, list(why)) for x, why in r]
        out = [T_PROP, len(r)]
        for x, why in r:
            out += [x, len(why), *why]
        tput(tape_of(self), out)
        return r

    def r_check(self, a, r):
        if r is None:
            tput(tape_of(self), [T_CHECK, 0, 0])
        elif r[0] is False:
            c = list(r[1])
            tput(tape_of(self), [T_CHECK, 2, len(c), *c])
        else:
            tput(tape_of(self), [T_CHECK, 1, 0])
        return r

    def r_decide(self, a, r):
        tput(tape_of(self), [T_DECIDE, 0 if r is None else int(r)])
        return r

    def r_push(self, a, r):
        S.pushes += 1
        return r

    def r_pop(self, a, r):
        S.pops += 1
        return r

    for name, rec in (("assert_lit", r_assert), ("propagate", r_prop), ("check", r_check),
                      ("decide", r_decide), ("push_level", r_push), ("pop_level", r_pop)):
        fn = getattr(cls, name, None)
        if fn is not None:
            setattr(cls, name, guard(fn, rec, name))


def table(store, op, obj):
    """The table id of a rule block or pattern, defined in the stream at first sight."""
    i = store.get(id(obj))
    if i is None:
        i = store[id(obj)] = len(store)
        S.keep.append(obj)
        cls = [list(c) for c in obj]
        S.ops[op] = S.ops.get(op, 0) + 1
        out = [op, i, len(cls)]
        for c in cls:
            out += [len(c), *c]
        words(out)
    return i


def lits_(xs):
    return [len(xs), *xs]


def hold_(h):
    if h is not None and h < 0:
        raise ValueError("negative hold")
    return -1 if h is None else h


def enc_add_internal(sid, a):
    clauses, mentions = a["clauses"], a["mentions"]
    out = [sid, 0 if mentions is None else 1]
    if mentions is None:
        out.append(0)
    else:
        out.append(len(mentions))
        for b, m in mentions:
            out += [b, *mask(m)]
    out.append(len(clauses))
    for c in clauses:
        out += [len(c), *c]
    return out


def enc_mention_blocks(sid, a):
    pairs_ = a["pairs"]
    out = [sid, len(pairs_)]
    for b, m in pairs_:
        out += [b, *mask(m)]
    return out


def enc_add_clauses(sid, a):
    out = [sid, len(a["clauses"])]
    for c in a["clauses"]:
        out += [len(c), *c]
    return out


def enc_atom(sid, a):
    return [sid, a["theory"]._rec_tid, a["var"], 1 if a["mention"] else 0]


def enc_attach(sid, a):
    th = a["theory"]
    tid = len(S.tapes)
    S.tapes.append(array("I"))
    th._rec_tid = tid
    patch_theory_class(type(th))
    return [sid, tid, 1 if hasattr(th, "propagate") else 0, 1 if hasattr(th, "decide") else 0]


ENC = {
    "attach_theory": enc_attach,
    "register_atom": enc_atom,
    "ensure_vars": lambda s, a: [s, a["v"]],
    "new_var": lambda s, a: [s],
    "add_clause": lambda s, a: [s, *lits_(a["lits"])],
    "add_clauses": enc_add_clauses,
    "add_internal": enc_add_internal,
    "add_pattern": lambda s, a: [s, table(S.patterns, OPS["PATTERN"], a["pattern"]), a["base"], a["nvars"]],
    "set_rule_block": lambda s, a: [s, table(S.blocks, OPS["BLOCK"], a["block"]),
                                    -1 if a["nvars"] is None else a["nvars"]],
    "register_block": lambda s, a: [s, a["base"], *mask(a["mentions"])],
    "mention_blocks": enc_mention_blocks,
    "mention": lambda s, a: [s, *lits_(a["lits"])],
    "propagate": lambda s, a: [s],
    "value": lambda s, a: [s, a["lit"]],
    "root_trail": lambda s, a: [s],
    "implied": lambda s, a: [s, hold_(a["hold"]), *lits_(a["assumptions"])],
    "release": lambda s, a: [s, a["k"]],
    "set_inert": lambda s, a: [s, a["v"]],
    "solve": lambda s, a: [s, *lits_(a["assumptions"])],
    "consistent": lambda s, a: [s, hold_(a["hold"]), *lits_(a["assumptions"])],
    "entails": lambda s, a: [s, a["lit"], hold_(a["hold"]), *lits_(a["assumptions"])],
    "entails_all": lambda s, a: [s, hold_(a["hold"]), *lits_(a["lits"]), *lits_(a["assumptions"])],
    "theories": lambda s, a: [s],
    "nvars": lambda s, a: [s],
    "stats": lambda s, a: [s],
    "model": lambda s, a: [s],
    "conflict": lambda s, a: [s],
    "theory_models": lambda s, a: [s],
}
MATERIALIZE = ("lits", "assumptions", "clauses", "mentions", "pairs")


def account(self):
    prev = S.last[self._rec_sid]
    tot = S.total
    for i, name in enumerate(COUNTERS):
        x = getattr(self, name)
        tot[i] += x - prev[i]
        prev[i] = x


def wrap_record(name, fn):
    sig = inspect.signature(fn)
    enc = ENC.get(name)
    op = OPS.get(name)

    def w(self, *a, **k):
        if S.depth:
            if S.tdepth:
                S.nested += 1       # a theory calling back into the solver: the replay would miss it
            return fn(self, *a, **k)
        if enc is None:
            raise RuntimeError(f"Solver.{name} is not in the trace format")
        if self.track_owners or self.owner is not BOTTOM:
            S.owners += 1
        b = sig.bind(self, *a, **k)
        b.apply_defaults()
        args = b.arguments
        for key in MATERIALIZE:
            v = args.get(key)
            if v is not None and not isinstance(v, (list, tuple, int)):
                args[key] = list(v)
        out = enc(self._rec_sid, args)
        S.depth = 1
        try:
            r = fn(*b.args, **b.kwargs)
            h = crc(norm(r))
        except ValueError:
            r = None
            h = crc(EXC)
            S.depth = 0
            words([op, *out])
            S.res.append(h)
            S.ops[name] = S.ops.get(name, 0) + 1
            account(self)
            raise
        S.depth = 0
        words([op, *out])
        S.res.append(h)
        S.ops[name] = S.ops.get(name, 0) + 1
        account(self)
        return r
    return w


def wrap_timer(name, fn):
    def w(self, *a, **k):
        if S.depth:
            return fn(self, *a, **k)
        S.depth = 1
        S.calls += 1
        t = pc()
        try:
            return fn(self, *a, **k)
        finally:
            S.t_solver += pc() - t
            S.depth = 0
    return w


def timer_theory(cls):
    if cls in PATCHED:
        return
    PATCHED.add(cls)
    for name in ("assert_lit", "propagate", "check", "decide", "push_level", "pop_level", "register_atom"):
        fn = getattr(cls, name, None)
        if fn is None:
            continue

        def w(self, *a, _fn=fn):
            if not S.depth or S.tdepth:
                return _fn(self, *a)
            S.tdepth = 1
            t = pc()
            try:
                return _fn(self, *a)
            finally:
                S.t_theory += pc() - t
                S.tdepth = 0
        setattr(cls, name, w)


PUBLIC = [n for n, f in vars(Solver).items() if inspect.isfunction(f) and not n.startswith("_")]
for n in PUBLIC:
    f = getattr(Solver, n)
    setattr(Solver, n, (wrap_timer if TIMERS else wrap_record)(n, f))

orig_init = Solver.__init__
if TIMERS:
    orig_attach = Solver.attach_theory

    def attach(self, theory):
        timer_theory(type(theory))
        return orig_attach(self, theory)
    Solver.attach_theory = attach
else:
    def init(self):
        orig_init(self)
        sid = self._rec_sid = S.next_sid
        S.next_sid += 1
        S.last[sid] = [0] * len(COUNTERS)
        words([OPS["NEW"], sid])
        weakref.finalize(self, lambda s=sid: words([OPS["DROP"], s]))
    Solver.__init__ = init

gc.collect()
gc.freeze()

ans = []
perq = []
t0 = pc()
for q, (p, a) in enumerate(pairs):
    if not TIMERS:
        words([OPS["QUERY"], q])
    try:
        r = sympy_api.ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:  # noqa: BLE001
        r = "raise " + type(e).__name__
        if os.environ.get("REC_DEBUG"):
            raise
    ans.append(r)
    if not TIMERS:
        perq.append([*S.total, S.pushes, S.pops, len(S.res)])
T = pc() - t0
digest = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]

if TIMERS:
    print(json.dumps(dict(mode="timers", wl=wl, T=T, t_solver=S.t_solver, t_theory=S.t_theory, calls=S.calls,
                          digest=digest)), flush=True)
    sys.exit(0)

os.makedirs(outdir, exist_ok=True)
with open(os.path.join(outdir, f"{wl}.trace"), "wb") as f:
    head = array("I", [MAGIC, len(S.api), len(S.tapes)])
    head.tofile(f)
    S.api.tofile(f)
    for t in S.tapes:
        array("I", [len(t)]).tofile(f)
        t.tofile(f)
with open(os.path.join(outdir, f"{wl}.res"), "wb") as f:
    S.res.tofile(f)
with open(os.path.join(outdir, f"{wl}.meta.json"), "w") as f:
    json.dump(dict(wl=wl, digest=digest, answers=ans, perq=perq, ops=S.ops, ntheory=S.ntheory,
                   nested=S.nested, owners=S.owners, solvers=S.next_sid, theories=len(S.tapes),
                   record_s=T, counters=COUNTERS, api_words=len(S.api), tape_words=sum(map(len, S.tapes))), f)
print(json.dumps(dict(wl=wl, digest=digest, ops=S.ops, ntheory=S.ntheory, nested=S.nested, owners=S.owners,
                      solvers=S.next_sid, theories=len(S.tapes), record_s=round(T, 2),
                      api_words=len(S.api), tape_words=sum(map(len, S.tapes)),
                      total=dict(zip(COUNTERS, S.total)), pushes=S.pushes, pops=S.pops)), flush=True)
