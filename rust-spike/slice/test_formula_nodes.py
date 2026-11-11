"""Formula step: formula.rs's one-pass conversion of a Python Formula into Rust nodes, against Python's own reading of the
same object: `atoms_of` (the same objects, in the same order), the tree (class by class, in `to_f`'s isinstance order), and
each atom occurrence's own object. Each plant 601-606 must fire and move one of those comparisons, and none moves without
one. Plant 600 (`rows-product-verdict-flip`) is the control of `scaffold:core:kept_product:mismatch` on the core workload.
Not here, because it isn't wired yet: the session reading nodes (after state part 2 (iii))."""
import random

import pytest

import sa_solver
from satassume.knowledge import compile as C
from satassume.sat import formula as Fm
from satassume.sat.formula import And, Equivalent, Exclusive, Formula, Implies, ITE, Not, Or, atoms_of

#: The atom class in use: Python's `P`, or sa_solver.P where p_install has swapped it in. Python's `atoms_of` knows only
#: this one (its `isinstance(g, P)` reads the module global), so the cases are built from it alone.
ATOM = Fm.P
CLASSES = [Fm.P, And, Or, Not, Implies, Equivalent, Exclusive, ITE, C._Lit]
TAGS = [(And, 'and'), (Or, 'or'), (Not, 'not'), (Implies, 'implies'), (Equivalent, 'equivalent'), (Exclusive, 'exclusive'),
        (ITE, 'ite')]


def is_atom(f):
    return isinstance(f, (sa_solver.P, Fm.P))


def shape(f):
    """What `to_f` (session.rs) makes of `f`, as nested tuples."""
    if isinstance(f, bool):
        return f
    if is_atom(f):
        return ('atom', f.pred, f.expr)
    for cls, tag in TAGS:
        if isinstance(f, cls):
            return (tag,) + tuple(shape(a) for a in f.args)
    if isinstance(f, C._Lit):
        return ('lit', f.lit)
    return ('bad', f)


def occurrences(f):
    """Each atom occurrence, depth first, left to right."""
    if is_atom(f):
        return [f]
    if isinstance(f, Formula) and not isinstance(f, C._Lit):
        return [o for a in f.args for o in occurrences(a)]
    return []


class Expr:
    """An opaque hashable expr: `==` by name, so two objects can be one atom."""

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return type(other) is Expr and other.name == self.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return self.name


def rand_formula(r, depth, atom):
    k = r.random()
    if depth == 0 or k < 0.3:
        j = r.random()
        if j < 0.08:
            return r.choice([True, False])
        if j < 0.12:
            return C._Lit(r.randint(-5, 5) or 1)
        if j < 0.15:
            return r.choice([None, 5, 'x', Expr('loose')])
        # a new object each time: equal atoms that aren't one object
        return atom(r.choice(['positive', 'integer', 'zero', 'custom']), Expr(r.choice('abcd')))
    sub = lambda: rand_formula(r, depth - 1, atom)
    c = r.choice(['and', 'or', 'not', 'implies', 'equivalent', 'exclusive', 'ite'])
    if c == 'not':
        return Not(sub())
    if c == 'implies':
        return Implies(sub(), sub())
    if c == 'ite':
        return ITE(sub(), sub(), sub())
    return {'and': And, 'or': Or, 'equivalent': Equivalent, 'exclusive': Exclusive}[c](*[sub() for _ in range(r.randint(0, 4))])


def cases(n=400, seed=231):
    r = random.Random(seed)
    out = [rand_formula(r, r.randint(0, 5), ATOM) for _ in range(n)]
    a, b = ATOM('positive', Expr('a')), ATOM('positive', Expr('a'))
    out += [a, And(a, b), And(b, a, Not(a)), Implies(a, b), ITE(a, b, Not(b)), Or(Not(Not(a)), b), True, False, And(), Or()]
    return out


def differences(fs):
    """How many of `fs` differ from Python's reading, per comparison."""
    d = dict(atoms=0, identity=0, shape=0, occurrences=0, refused=0)
    for f in fs:
        n = sa_solver.formula_convert(f, CLASSES)
        if n is None:
            d['refused'] += 1
            continue
        want = atoms_of(f)
        got = n.atoms
        if len(got) != len(want) or any(x != y for x, y in zip(got, want)):
            d['atoms'] += 1
        elif any(x is not y for x, y in zip(got, want)):
            d['identity'] += 1
        if repr(n.shape()) != repr(shape(f)) or n.shape() != shape(f):
            d['shape'] += 1
        occ = n.occurrences()
        ref = occurrences(f)
        if len(occ) != len(ref) or any(o is not x or i >= len(got) or got[i] != x for (o, i), x in zip(occ, ref)):
            d['occurrences'] += 1
    return d


@pytest.fixture(autouse=True)
def unplanted():
    sa_solver.formula_plant(None)
    yield
    sa_solver.formula_plant(None)


def test_nodes_match_pythons_reading():
    fs = cases()
    c0 = sa_solver.formula_counts()
    d = differences(fs)
    c1 = sa_solver.formula_counts()
    assert d == dict(atoms=0, identity=0, shape=0, occurrences=0, refused=0)
    assert c1['fm:convert'] - c0['fm:convert'] == len(fs)
    assert c1['fm:atoms'] - c0['fm:atoms'] >= len(fs)
    assert c1['fm:atom_occ'] - c0['fm:atom_occ'] == sum(len(occurrences(f)) for f in fs)
    assert c1['fm:bad'] > c0['fm:bad'] and c1['fm:atom_intern'] > c0['fm:atom_intern']
    assert c1['fm:plant_fired'] == c0['fm:plant_fired']
    assert all(c1[k] == c0[k] for k in c1 if k.startswith('fm:refuse'))


def test_source_is_the_object_and_is_never_read_again():
    """After conversion the node answers without the object: emptying its `args` changes nothing."""
    a, b = ATOM('positive', Expr('a')), ATOM('zero', Expr('b'))
    f = And(a, Or(b, Not(a)))
    n = sa_solver.formula_convert(f, CLASSES)
    want_atoms, want_shape = atoms_of(f), shape(f)
    f.args = ()
    assert n.source is f
    assert n.atoms == want_atoms and all(x is y for x, y in zip(n.atoms, want_atoms))
    assert n.shape() == want_shape
    assert n.nodes == 6


# 660, 661: test_cbm_noid.py; 607, 608 (`fm-hand-*`, an entry's nodes): test_convert_once.py
@pytest.mark.parametrize('plant', [n for n in sa_solver.formula_plants() if n.startswith('fm-') and not n.startswith('fm-hand-')])
def test_each_plant_fires_and_is_caught(plant):
    fs = cases()
    c0 = sa_solver.formula_counts()['fm:plant_fired']
    sa_solver.formula_plant(plant)
    d = differences(fs)
    sa_solver.formula_plant(None)
    assert sa_solver.formula_counts()['fm:plant_fired'] > c0, plant
    caught = {'fm-atoms-drop-last': 'atoms', 'fm-atoms-no-dedupe': 'atoms'}.get(plant, 'shape')
    assert d[caught] > 0, (plant, d)
    assert differences(fs) == dict(atoms=0, identity=0, shape=0, occurrences=0, refused=0)


def test_unknown_plant_is_refused():
    with pytest.raises(ValueError):
        sa_solver.formula_plant('fm-no-such')


def refusal(f, key):
    c0 = sa_solver.formula_counts()
    n = sa_solver.formula_convert(f, CLASSES)
    c1 = sa_solver.formula_counts()
    return n, {k: c1[k] - c0[k] for k in c1 if k.startswith('fm:refuse') and c1[k] != c0[k]} == {key: 1}


def test_depth_refuses_where_to_f_does():
    a = ATOM('positive', Expr('a'))
    f = a
    for _ in range(64):
        f = Not(f)
    assert sa_solver.formula_convert(f, CLASSES) is not None        # the atom at depth 64
    n, only = refusal(Not(f), 'fm:refuse:depth')
    assert n is None and only


def test_a_formula_class_to_f_doesnt_know_refuses():
    class Mine(Formula):
        pass

    a = ATOM('positive', Expr('a'))
    n, only = refusal(And(a, Mine(a)), 'fm:refuse:class')
    assert n is None and only
    assert atoms_of(And(a, Mine(a))) == (a,)                        # Python walks it: why a `Bad` node would be wrong


def test_wrong_arity_refuses():
    a = ATOM('positive', Expr('a'))
    for f, args in ((Not(a), (a, a)), (Implies(a, a), (a,)), (ITE(a, a, a), (a, a))):
        f.args = args
        n, only = refusal(f, 'fm:refuse:class')
        assert n is None and only


def test_a_read_that_raises_refuses_and_a_baseexception_goes_up():
    a = ATOM('positive', Expr('a'))
    f = And(a)
    f.args = [a]                                                    # not a tuple
    n, only = refusal(f, 'fm:refuse:read')
    assert n is None and only
    n, only = refusal(And(a, ATOM('positive', [])), 'fm:refuse:read')      # unhashable in `seen`
    assert n is None and only
    bare = ATOM('positive', [])
    assert sa_solver.formula_convert(bare, CLASSES).atoms == (bare,)        # atoms_of(P) hashes nothing

    class Stop(BaseException):
        pass

    class Boom(And):
        @property
        def args(self):
            raise Stop()

    with pytest.raises(Stop):
        sa_solver.formula_convert(Boom.__new__(Boom), CLASSES)


def test_nine_classes_or_an_error():
    with pytest.raises(ValueError):
        sa_solver.formula_convert(True, CLASSES[:8])


def _core_counts(plant=None):
    import knowledge_common_live as KC
    import knowledge_live as K
    from harness.state import reset_module_state
    from live import load
    from satassume import engine as E_, sympy_api

    def counts():
        c = KC.COMMON[0]
        return dict(c.counts()) if c is not None else {}

    def ask(p, a):
        try:
            return sympy_api.ask(p, a)
        except Exception as e:      # core's workload has queries that raise on both backends
            return type(e).__name__

    pairs = load('core')
    old = K.PLANT[0]
    try:
        reset_module_state()
        sympy_api.set_default_engine(E_.Engine())
        plain = [ask(p, a) for p, a in pairs]
        K.PLANT[0] = plant
        undo = K.install()
        try:
            c0 = counts()
            reset_module_state()
            sympy_api.set_default_engine(E_.Engine())
            got = [ask(p, a) for p, a in pairs]
            c1 = counts()
        finally:
            undo()
    finally:
        K.PLANT[0] = old
    return plain, got, {k: c1.get(k, 0) - c0.get(k, 0) for k in c1}


def test_kept_product_mismatch_counter_is_zero_on_core_and_fires_on_its_plant():
    """KEPT_PRODUCT ruling: Python's answer is used and Rust's own verdict is compared with it. The counter reads 0 on
    core, where the scaffold fires, and plant 600 (Rust's verdict flipped) makes it fire once per checked product without
    moving an answer."""
    plain, got, d = _core_counts()
    assert got == plain
    n = d.get('scaffold:core:kept_product', 0)
    assert n > 0
    assert d.get('scaffold:core:kept_product:mismatch', 0) == 0, d.get('scaffold:core:kept_product:mismatch')
    plain, got, p = _core_counts('rows-product-verdict-flip')
    assert got == plain
    checked = p.get('scaffold:core:kept_product', 0) - p.get('scaffold:core:kept_product:unchecked', 0)
    assert p.get('plant:fired', 0) == checked > 0
    assert p.get('scaffold:core:kept_product:mismatch', 0) == checked
