"""Round 3, item B2a: the ``P`` atoms ``VarTable.node_base`` creates per node.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/2026-09-perf-rounds/scripts/node_atoms.py stream.pkl [PLAIN_SECONDS]

Measures the eager ``VarTable`` of ``895a6c2`` (it replaces ``atom_of``,
which is a read-only property after B2a); run it on the reference clone.

Cold pass with two wrappers (answers checked):

* ``VarTable.node_base``: times every call that allocates a new block and
  counts the blocks (``NPRED`` atoms each);
* ``VarTable.__init__`` swaps ``atom_of`` for a list subclass that records
  every index read (``__getitem__``), so the count of node atoms ever read
  (by ``Session.writeback``, ``VarTable.lit_name`` or anyone else) is exact.

Then the cost of the eager allocation alone, re-timed outside the replay on
the same number of blocks: ``extend`` with 33 fresh ``P`` atoms versus
``extend`` with one shared placeholder repeated 33 times.
"""
import pickle, sys, time

stream = pickle.load(open(sys.argv[1], "rb"))
plain = float(sys.argv[2]) if len(sys.argv) > 2 else None
import satassume.sympy_api as api
from satassume.compile import VarTable
from satassume.formula import P
from satassume.rules import NPRED, PREDICATES

pc = time.perf_counter
stat = {"blocks": 0, "alloc_s": 0.0, "custom_aux": 0}
tables = []


class Rec(list):
    __slots__ = ("read",)

    def __getitem__(self, i):
        self.read.add(i)
        return list.__getitem__(self, i)


orig_init = VarTable.__init__
orig_nb = VarTable.node_base


def init(self):
    orig_init(self)
    r = Rec(self.atom_of); r.read = set()
    self.atom_of = r
    tables.append(self)


def node_base(self, node):
    if node in self.base_of:
        return self.base_of[node]
    t0 = pc()
    b = orig_nb(self, node)
    stat["alloc_s"] += pc() - t0
    stat["blocks"] += 1
    return b


VarTable.__init__ = init
VarTable.node_base = node_base
bad = 0
t0 = pc()
for p, a, r in stream:
    try:
        got = api.ask(p, a)
    except ValueError:
        got = "err"
    if got is not r and got != "err":
        bad += 1
dt = pc() - t0
D = plain or dt
node_atoms = read_node = 0
for t in tables:
    for node, b in t.base_of.items():
        node_atoms += NPRED
        read_node += sum(1 for v in range(b, b + NPRED) if v in t.atom_of.read)
print(f"pass {dt:.3f}s (instrumented), mismatches {bad}; {len(tables)} VarTables")
print(f"node blocks {stat['blocks']}, node atoms created {node_atoms}, "
      f"read by anyone {read_node} ({100 * read_node / node_atoms:.1f}%)")
print(f"eager allocation in the pass (timed calls): {1000 * stat['alloc_s']:.1f} ms "
      f"= {100 * stat['alloc_s'] / D:.2f}% of {D:.3f}s")

nodes = [n for t in tables[:400] for n in t.base_of][:stat["blocks"]]
while len(nodes) < stat["blocks"]:
    nodes += nodes[: stat["blocks"] - len(nodes)]


def eager():
    lst = [None]
    for n in nodes:
        lst.extend(P(p, n) for p in PREDICATES)


def lazy():
    lst = [None]
    for n in nodes:
        lst.extend([(n, len(lst))] * NPRED)


for f in (eager, lazy):
    best = min((lambda: (lambda t0: (f(), pc() - t0)[1])(pc()))() for _ in range(5))
    print(f"  {f.__name__:6s} {len(nodes)} blocks: {1000 * best:.1f} ms = {100 * best / D:.2f}%")
