"""The wiring of `knowledge_live` into the default Rust backend (port-wire.md): `from_env()` as `rust_plugin.py` and `live.py`
call it, the second-install guard, and `rows_kept`'s guard with its plant."""
import pytest
from sympy import Integer, Q, Symbol

import knowledge_live as K
import term_live
from satassume import sympy_api
from satassume.knowledge.templates import wiring


@pytest.fixture
def env(monkeypatch):
    """`term_live` as the Rust backend installs it, and whatever `from_env` installs undone afterwards."""
    for v in ('SLICE_KNOWLEDGE', 'SLICE_SESSION_PLANT', 'SESSION_REPORT', 'SLICE_TERM'):
        monkeypatch.delenv(v, raising=False)
    undo_term = term_live.from_env()
    undos = []
    yield monkeypatch, undos
    for u in undos:
        if u is not None:
            u()
    K.PLANT[0] = None
    undo_term()
    K.COUNTS.clear()


def test_default_installs(env):
    mp, undos = env
    undos.append(K.from_env())
    assert K.installed()
    with pytest.raises(RuntimeError):
        K.install()
    x = Symbol('x')
    K.COUNTS.clear()
    assert sympy_api.ask(Q.positive(x**2 + 1), Q.real(x)) is True
    # 6d: Rust's facts/units make the Patterns; their counts reach K.COUNTS only at undo
    import knowledge_common_live
    rust = knowledge_common_live.COMMON[0].counts()
    assert rust.get('common:facts', 0) + rust.get('common:units', 0) > 0, (dict(K.COUNTS), rust)


def test_py_keeps_it_off(env):
    mp, undos = env
    mp.setenv('SLICE_KNOWLEDGE', 'py')
    assert K.from_env() is None and not K.installed()


def test_needs_the_table(monkeypatch):
    """With SLICE_TERM=py there's no table, and `from_env` stays off."""
    monkeypatch.delenv('SLICE_KNOWLEDGE', raising=False)
    assert not term_live.installed()
    assert K.from_env() is None and not K.installed()


def test_undo_uninstalls(env):
    mp, undos = env
    u = K.from_env()
    u()
    assert not K.installed()


def test_rows_kept_plant_is_loud(env):
    mp, undos = env
    mp.setenv('SLICE_SESSION_PLANT', 'knowledge-rows-kept-raise')
    undos.append(K.from_env())
    assert K.PLANT[0] == 'knowledge-rows-kept-raise'
    K.COUNTS.clear()
    with pytest.raises(K.KnowledgeFault, match='rows_kept: NameError'):
        wiring.constant_value('1/2', Integer(1))
    assert K.COUNTS['fault'] == 1 and K.COUNTS['knowledge:plant_fired'] == 1


def test_other_plants_are_not_ours(env):
    mp, undos = env
    mp.setenv('SLICE_SESSION_PLANT', 'var-off')
    undos.append(K.from_env())
    assert K.PLANT[0] is None
