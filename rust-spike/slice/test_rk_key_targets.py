"""The classes rk_key's isinstance tests name (rk_key step, sa-port-297/298 gates; fidelity, kept without the per-type cache).

relkeys.rs's is_basic and is_joinable call `isinstance(x, T)` on every key, through PyObject_IsInstance, for Basic, Number,
BooleanAtom and Tuple. Their metaclass is `type`, so none is an ABC (`register()`) or has its own `__instancecheck__`, and
`type` being immutable means a class's metaclass can't be reassigned later. These tests keep it so: they assert the targets'
metaclass, that relkeys.rs names exactly these four, and that a key whose `__class__` answers per instance (object_isinstance's
fallback through the type's own `__getattribute__`) is still keyed per instance by RelKeys, as by a Python set.

The read-once cache keyed by (type, tp_version_tag) that relied on this was tried (1b41dce, 1e7a4db, 86845aa) and dropped:
its fuzz gain was within run-to-run spread (results/rk-key-step.md).
"""
import abc
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


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
    body = src[src.index('fn is_basic('):src.index('fn dict<')]
    names = set(re.findall(r'getattr\((?:intern!\(p, )?"([A-Za-z_]+)"\)?\)', body))
    assert names == set(_targets()), names
    assert body.count('is_instance(') == 2, body


def _child():
    from test_relations_core import _rust
    _rust()
    import term_live
    from sympy import Basic, Q, Symbol, pi
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
            for o in objs:
                r._xcand.add(o)
            out[name] = {'r': [len(r._xcand), [o in r._xcand for o in objs], [o in r._xcand for o in objs[:1] * 2]],
                         'py': [len(set(objs)), [o in set(objs) for o in objs]],
                         'basic': [isinstance(o, Basic) for o in objs]}
    finally:
        term_live.stack().pop()
    print(json.dumps(out))


def test_a_key_whose_class_answers_per_instance_is_kept_per_instance():
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    env.pop('SLICE_SESSION_PLANT', None)
    r = subprocess.run([sys.executable, os.path.abspath(__file__), 'child'], env=env, capture_output=True, text=True,
                       timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    got = json.loads(r.stdout.strip().splitlines()[-1])
    assert got['fake']['basic'] == [True, False, True, False], got     # the fixture: the answer differs per instance
    for n in ('fake', 'plain', 'tuple'):
        assert got[n]['r'][:2] == got[n]['py'] == [4, [True] * 4], got
        assert got[n]['r'][2] == [True, True], got


if __name__ == '__main__' and sys.argv[1:] == ['child']:
    _child()
