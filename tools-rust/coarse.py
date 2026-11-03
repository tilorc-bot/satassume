"""fn mode of rc.py: exclusive outermost timers on the satassume functions behind the
boundary that read or build SymPy objects. Each group is what would stay in Python if the
function stayed whole. A nested Engine entry (an inner session, _number_basis) pauses the
timer: the inner session's own groups count, its search does not."""
import functools
import importlib
import sys
import time

pc = time.perf_counter
LRA = "satassume.theories.lra.lra_adapter"
EUF = "satassume.theories.euf.euf_adapter"
REL = "satassume.relations"
ENG = "satassume.engine"
GROUPS = {
    "templates": [("satassume.knowledge.templates.registry", "TemplateRegistry.clauses_for"),
                  (REL, "closed_units")],
    "lra_read": [(LRA, n) for n in ("relation", "_lin", "_closed", "closed_sign", "constant_bounds",
                                    "constant_enclosure", "_linear", "to_constraint", "_constraint",
                                    "interpret", "terms", "_side", "order_sides", "integer_form",
                                    "_memoized")]
                + [("satassume.theories.lra.constfield", n) for n in ("from_sympy", "_from_sympy")],
    "euf_read": [(EUF, "structural")]
                + [(EUF, "EUFAdapter." + n) for n in ("parse", "interprets", "term", "node_term",
                                                     "_intern", "interned", "term_of")],
    "relation_read": [(REL, n) for n in ("_key", "_affine_strip", "sympy_atom", "_is_number", "_under_apps",
                                         "zero_args", "under_of", "zero_twin", "zero_twins", "glue_atoms",
                                         "_termwise", "_constant_term", "_number_basis", "_number_facts",
                                         "_own_term", "_structural_subterms", "link_objects", "glue_objects",
                                         "relation_atom", "Relations._congruent", "Relations._transfer_terms",
                                         "Relations._closed_extended_real")],
    "struct": [(ENG, n) for n in ("Engine._struct", "Engine._cone_info", "Engine._query_cone",
                                  "Engine._union", "Engine._within_budget", "_noncommutative_atoms",
                                  "_noncommutative", "_construction_level")]
              + [("satassume.scope", "theory_scope"),
                 ("satassume.theories.transfer", "transfer_wanted")],
}
NAMES = list(GROUPS)


class St:
    cur = None
    t0 = 0.0
    calls = [0] * len(NAMES)
    perq = None
    snaps = None
    prepare = 0.0
    prepare_depth = 0
    custom = 0
    facts_for = 0
    node_facts = 0


def _replace_everywhere(orig, new):
    for m in list(sys.modules.values()):
        name = getattr(m, "__name__", "")
        if name.startswith("satassume") and "templates._" not in name:
            d = getattr(m, "__dict__", {})
            for k, v in list(d.items()):
                if v is orig:
                    d[k] = new


def _patch(modname, qual, make):
    m = importlib.import_module(modname)
    if "." in qual:
        cname, fname = qual.split(".")
        c = getattr(m, cname)
        orig = c.__dict__[fname]
        if isinstance(orig, staticmethod):
            setattr(c, fname, staticmethod(make(orig.__func__)))
        elif isinstance(orig, classmethod):
            setattr(c, fname, classmethod(make(orig.__func__)))
        else:
            setattr(c, fname, make(orig))
    else:
        orig = getattr(m, qual)
        new = make(orig)
        _replace_everywhere(orig, new)


def install(B, snaps, n):
    St.perq = [[0.0] * len(NAMES) for _ in range(n)]
    St.snaps = snaps

    def timed(g):
        def make(orig):
            @functools.wraps(orig)
            def w(*a, **k):
                if St.cur is not None or not B.depth:
                    return orig(*a, **k)
                St.cur = g
                St.calls[g] += 1
                St.t0 = pc()
                try:
                    return orig(*a, **k)
                finally:
                    St.perq[len(snaps) // 2][g] += pc() - St.t0
                    St.cur = None
            return w
        return make

    for g, name in enumerate(NAMES):
        for modname, qual in GROUPS[name]:
            _patch(modname, qual, timed(g))

    from satassume.engine import Engine, Session
    for entry in ("ask", "is_", "is_many", "verdict"):
        orig = getattr(Engine, entry)

        def pause(self, *a, _orig=orig, **k):
            g = St.cur
            if g is None:
                return _orig(self, *a, **k)
            St.perq[len(snaps) // 2][g] += pc() - St.t0
            St.cur = None
            try:
                return _orig(self, *a, **k)
            finally:
                St.cur = g
                St.t0 = pc()
        setattr(Engine, entry, pause)

    # all-in time of prepare_query (the issue's "query preparation"): it is session work
    pq = Session.prepare_query

    def prepare(self, proposition):
        t = pc()
        try:
            return pq(self, proposition)
        finally:
            St.prepare += pc() - t
    Session.prepare_query = prepare

    # Session._custom takes custom-predicate atoms AND relation atoms, so its count is not
    # a callback count. The calls into registered user code are Extensions.facts_for and
    # Extensions.node_facts; count those, and how many handlers each actually ran.
    cu = Session._custom

    def custom(self, atom):
        St.custom += 1
        return cu(self, atom)
    Session._custom = custom

    from satassume.knowledge.extensions import Extensions
    ff, nf = Extensions.facts_for, Extensions.node_facts

    def facts_for(self, atom):
        St.facts_for += 1
        return ff(self, atom)

    def node_facts(self, node):
        St.node_facts += 1
        return nf(self, node)
    Extensions.facts_for = facts_for
    Extensions.node_facts = node_facts


def report(ans):
    out = {"calls": dict(zip(NAMES, St.calls)), "prepare_query_all_in_s": round(St.prepare, 5),
           "session_custom_atoms": St.custom,   # custom and relation atoms: NOT callbacks
           "ext_facts_for": St.facts_for, "ext_node_facts": St.node_facts}
    for g, name in enumerate(NAMES):
        none = sum(q[g] for q, r in zip(St.perq, ans) if r is None)
        defi = sum(q[g] for q, r in zip(St.perq, ans) if r is not None)
        out[name] = {"none": round(none, 5), "def": round(defi, 5)}
    return out
