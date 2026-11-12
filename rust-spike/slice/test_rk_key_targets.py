"""The classes rk_key's isinstance tests name, and why its per-type result is exact (rk_key step, sa-port-297 gate).

relkeys.rs keeps `isinstance(x, T)` per (type(x), tp_version_tag) for the query. That is exact only when no target can answer
differently for the same type: an ABC (`register()`), or a metaclass with its own `__instancecheck__`, could. The targets are
Basic, Number, BooleanAtom and Tuple; their metaclass is `type`, so none of that applies, and `type` being immutable means a
class's metaclass can't be reassigned later. These tests keep it so: they assert the targets' metaclass, and that relkeys.rs's
isinstance calls name exactly these four.

The one per-instance answer left is `x.__class__` read through a type's own `__getattribute__` (object_isinstance's fallback
when type(x) isn't a subclass), which relkeys.rs guards by the type's tp_getattro slot. Such a type is never cached: one isinstance read per key (plant 669 `rk-getattr-cached`
caches it by type, caught by the per-instance row: 4 keys added and looked up give 8 reads).
"""
import abc
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ('rk:type_read', 'rk:top_read', 'rel:plant_fired')


def _targets():
    from sympy import Basic, Number, Tuple
    from sympy.logic.boolalg import BooleanAtom
    return {'Basic': Basic, 'Number': Number, 'BooleanAtom': BooleanAtom, 'Tuple': Tuple}


def test_the_targets_metaclass_is_type_so_none_is_an_abc_or_has_its_own_instancecheck():
    for name, t in _targets().items():
        assert type(t) is type, name
        assert not isinstance(t, abc.ABCMeta) and not hasattr(t, '_abc_impl'), name
        assert type(t).__instancecheck__ is type.__instancecheck__, name
        try:
            t.__class__ = abc.ABCMeta
        except TypeError:
            pass
        else:
            raise AssertionError(f'{name}: metaclass reassigned')


def test_relkeys_isinstance_targets_are_exactly_these():
    src = open(os.path.join(HERE, 'solver_rs', 'src', 'relkeys.rs')).read()
    body = src[src.index('fn is_basic('):src.index('fn dict<')] + src[src.index('fn plain('):src.index('pub(crate) fn rk_key(')]
    names = set(re.findall(r'getattr\((?:intern!\(p, )?"([A-Za-z_]+)"\)?\)', body))
    assert names == set(_targets()), names


def _child():
    from test_relations_core import _rust
    _rust()
    import sa_solver
    import term_live
    from sympy import Q, Symbol, pi
    from satassume.engine import Engine, Session
    from satassume.relations import Relations

    class Fake:
        """Answers `__class__` per instance: Symbol when `fake`, so isinstance(x, Basic) differs between instances."""
        def __init__(self, fake, v):
            self.fake, self.v = fake, v

        def __getattribute__(self, n):
            if n == '__class__' and object.__getattribute__(self, 'fake'):
                return Symbol
            return object.__getattribute__(self, n)

    class Plain:
        def __init__(self, v):
            self.v = v

    eng = Engine()
    x, y = Symbol('x'), Symbol('y')
    out = {}
    q1 = term_live._convert(Q.positive(x + y + pi), True, eng)
    term_live.stack().append(q1)
    try:
        for name, objs in (('fake', [Fake(i % 2 == 0, i) for i in range(4)]), ('plain', [Plain(i) for i in range(4)]),
                           ('tuple', [(i, x) for i in range(4)])):
            s = Session(eng)
            r = Relations(s, eng._relation_specs)
            b = dict(sa_solver.session_counts())
            for o in objs:
                r._xcand.add(o)
            got = [len(r._xcand), [o in r._xcand for o in objs]]
            a = dict(sa_solver.session_counts())
            out[name] = {'d': {k: a[k] - b[k] for k in KEYS}, 'r': got,
                         'basic': [isinstance(o, __import__('sympy').Basic) for o in objs]}
    finally:
        term_live.stack().pop()
    print(json.dumps(out))


def _run(plant=None):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    env.pop('SLICE_SESSION_PLANT', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    r = subprocess.run([sys.executable, os.path.abspath(__file__), 'child'], env=env, capture_output=True, text=True,
                       timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_a_type_with_its_own_getattribute_is_read_per_key_and_a_plain_type_once():
    got = _run()
    assert got['fake']['basic'] == [True, False, True, False], got     # the fixture: the answer differs per instance
    # tuples, most keys, are cached too (tuple's own dict holds a `__getattribute__` wrapper of the generic slot)
    assert [got[n]['d']['rk:type_read'] for n in ('fake', 'plain', 'tuple')] == [8, 1, 1], got
    assert all(got[n]['r'] == [4, [True] * 4] for n in ('fake', 'plain', 'tuple')), got
    assert got['fake']['d']['rel:plant_fired'] == 0 and got['plain']['d']['rel:plant_fired'] == 0, got


def test_rk_getattr_cached_plant_is_caught():
    got = _run('rk-getattr-cached')
    assert got['fake']['d']['rel:plant_fired'] > 0, got     # the control: it ran
    assert got['fake']['d']['rk:type_read'] != 8, got


if __name__ == '__main__' and sys.argv[1:] == ['child']:
    _child()
