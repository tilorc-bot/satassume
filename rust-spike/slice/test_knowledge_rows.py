"""`_rows_runtime.py` on Rust: by hand, for what a SymPy-side comparison can't say. `rows_cmp.py` is the comparison against Python."""
import pytest
import sa_solver
from fractions import Fraction
from sympy import E, Float, I, Integer, Rational, S, exp, pi

from satassume.knowledge.templates import _rows_runtime as RT, wiring
from satassume.knowledge.templates._compiled_rows import FAMILIES
from satassume.theories.lra import constfield


def same(a, b):
    return type(a) is type(b) and a == b and repr(a) == repr(b)


@pytest.mark.parametrize('text,value', [
    ('1/2', S.Half), ('-1/2', Rational(-1, 2)), (1, S.One), (-3, Integer(-3)), ('E', E), ('exp(-1)', exp(-1)), ('-1/E', -exp(-1)),
    ('pi', pi), ('2**-1', S.Half), ('-2**2', Integer(-4)), ('2**3**2', Integer(512)), ('sqrt(4/9)', Rational(2, 3)), ('Abs(-E)', E)])
def test_read(text, value):
    assert same(sa_solver.rows_from_text(text), value)


@pytest.mark.parametrize('text', ['I', '-I', 'I*I', 'sqrt(2)', 'E+1', '1/0', '0**-1', 'exp(1/2)', '1.5', '007', '+1', ' 1', '1//2', 'x', '',
                                  '(' * 80 + '1' + ')' * 80, '9' * 5000])
def test_declined(text):
    assert sa_solver.rows_from_text(text) is None


@pytest.mark.parametrize('text,c,value', [
    ('Abs(number) - 1', Integer(-3), Integer(2)), ('1/number', Rational(2, 3), Rational(3, 2)), ('2*coefficient', S.Half, S.One),
    ('number/2', Integer(3), Rational(3, 2)), ('number - 2', Integer(10)**30, Integer(10)**30 - 2)])
def test_constant_value(text, c, value):
    assert same(sa_solver.rows_constant_value(text, c), value)


@pytest.mark.parametrize('text,c', [('1/number', S.Zero), ('number/2', Float(2.0)), ('number - 2', S.Infinity), ('2*number', S.NaN),
                                    ('Abs(number) - 1', S.NegativeInfinity)])
def test_constant_value_declined(text, c):
    assert sa_solver.rows_constant_value(text, c) is None
    RT.constant_value(text, c)      # and Python answers it


def test_only_I_stays_on_python():
    """The rows' values that Rust can't read, and that its numbers are the constant field's."""
    python, numbers = [], {}
    for _, fns in FAMILIES:
        for fn_name, _, terms, specs, *schemas in fns:
            g = sa_solver.RowsGen(terms, specs, RT.from_text, *schemas)
            python += [(fn_name, v) for v in g.python_values]
            numbers.update(g.numbers())
    assert sorted(python) == [('Pow', '-I'), ('Pow', 'I')]
    assert numbers['-1/2'] == Fraction(-1, 2)
    assert numbers['E'] == constfield.E
    assert numbers['exp(-1)'] == 1 / constfield.E


def test_I_read_by_python():
    g = sa_solver.RowsGen((), ((2, ((((0, 'zero', True),), ((3, 'zero', True),), (('value', 'I'), None)),)),), RT.from_text)
    assert g.specs[2][0][2][0] == ('value', I)


@pytest.fixture
def live(request):
    """The install, shadow or not by the parameter, with the counters cleared and everything put back."""
    import knowledge_live as K
    undo = K.install(shadow=getattr(request, 'param', False))
    K.COUNTS.clear()
    del K.MISMATCHES[:]
    yield K
    undo()
    K.COUNTS.clear()
    del K.MISMATCHES[:]


class _Kept:
    kept = 'a kept query'


class _Log:
    def __init__(self):
        self.rules = []

    def rule(self, prem, concl):
        self.rules.append((prem, concl))


def kept_query(K):
    K._stack().append(_Kept())


def raises(*a, **k):
    raise ValueError('planted')


# FALSE ZEROS: each counter a landing report quotes as 0 has to be seen to fire.
def test_fault_fires_on_constant_value(live, monkeypatch):
    monkeypatch.setattr(live.sa_solver, 'rows_constant_value', raises)
    with pytest.raises(live.KnowledgeFault):
        wiring.constant_value('number/2', Integer(3))
    assert live.COUNTS['fault'] == 1


def test_fault_fires_on_generator(live, monkeypatch):
    monkeypatch.setattr(live.sa_solver, 'RowsGen', raises)
    with pytest.raises(live.KnowledgeFault):
        wiring.generator('f', 1, (), (), __name__)
    assert live.COUNTS['fault'] == 1


def test_fault_is_not_an_exception(live):
    """So neither of the two quiet `except Exception` handlers can turn it into an answer."""
    assert not issubclass(live.KnowledgeFault, Exception)


@pytest.mark.parametrize('live', [True], indirect=True)
def test_mismatch_fires_on_constant_value(live, monkeypatch):
    monkeypatch.setattr(live.sa_solver, 'rows_constant_value', lambda text, c: Integer(99))
    assert wiring.constant_value('number/2', Integer(4)) == 99
    assert live.COUNTS['shadow:rows'] == 1
    assert live.COUNTS['shadow:mismatch'] == 1


@pytest.mark.parametrize('live', [True], indirect=True)
def test_no_mismatch_on_the_real_function(live):
    assert wiring.constant_value('number/2', Integer(4)) == 2
    assert live.COUNTS['shadow:rows'] == 1
    assert live.COUNTS['shadow:mismatch'] == 0


def test_fallback_counted(live):
    assert same(wiring.constant_value('number/2', Float(2.0)), RT.constant_value('number/2', Float(2.0)))
    assert live.COUNTS['rows:constant_value:python'] == 1
    assert live.COUNTS['rows:constant_value:python:Float:number/2'] == 1


# The kept path: `gen` and `constant_value` go to Python in a kept query, and a family first used by one keeps Python's attributes.
def _family():
    (_, fns), = [f for f in FAMILIES if any(fn[0] == 'Pow' for fn in f[1])]
    fn_name, arity, terms, specs, *schemas = next(fn for fn in fns if fn[0] == 'Pow')
    return fn_name, arity, terms, specs, 'somewhere', *schemas


def test_constant_value_kept(live, monkeypatch):
    monkeypatch.setattr(live.sa_solver, 'rows_constant_value', raises)
    kept_query(live)
    try:
        assert wiring.constant_value('number/2', Integer(4)) == 2
    finally:
        live._stack().pop()
    assert live.COUNTS['rows:kept'] == 1 and live.COUNTS['fault'] == 0


def test_family_first_used_by_kept_query(live, monkeypatch):
    """Python's attributes and Python's `gen` in the query, Rust's `gen` after it, and Rust's reader built only then."""
    built, real = [], live.sa_solver.RowsGen

    def counted(*a, **k):
        built.append(a)
        return real(*a, **k)
    monkeypatch.setattr(live.sa_solver, 'RowsGen', counted)
    kept_query(live)
    try:
        gen = wiring.generator(*_family())
        python = RT.generator(*_family())
        for f in ('terms', 'shifts', 'specs', 'plain', 'schemas'):
            assert live._same_objects(getattr(gen, f), getattr(python, f)), f
        assert live.COUNTS['rows:generator:kept'] == 1 and not built
    finally:
        live._stack().pop()
    assert gen.__name__ == 'Pow_rows' and gen.__module__ == 'somewhere'
    assert not built
    key = next(iter(python.specs))

    def rules(g):
        log = _Log()
        g(log, key)
        return log.rules
    kept_query(live)
    try:
        assert rules(gen) == rules(python) and not built      # still Python's inside a kept query
    finally:
        live._stack().pop()
    assert rules(gen) == rules(python) and len(built) == 1     # Rust's after it
    assert live.COUNTS['rows:gen'] == 1
