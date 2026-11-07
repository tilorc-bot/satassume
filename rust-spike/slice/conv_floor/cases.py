"""The class-row cache's history argument, case by case. Each case runs in its own process (`cases.py NAME`), with SLICE_CONV_CACHE=1,
against the same steps with the cache off (`SLICE_CONV_CACHE=`) and on plain Python (`--py`). It prints JSON: the answers, the cache's
counts and how the query ran. The steps change something mid-process after a first query has filled the cache."""
import json, sys

sys.path.insert(0, '.')
PY = '--py' in sys.argv
if not PY:
    import p_install
    p_install.install()
from sympy import Abs, Expr, Function, Q, S, Symbol, cos, sin, symbols
from sympy.core.basic import ordering_of_classes
from satassume import engine as E, sympy_api
from satassume.knowledge import templates
from satassume.knowledge.templates import registry
from satassume.state import epoch

if not PY:
    import term_live, lra_live, convert as C
    term_live.install(keys=False, terms=True)
    lra_live.install()
x, y, z = symbols('x y z', real=True)
LOG = []


def ask(label, p, a=True, eng=None):
    sympy_api.set_default_engine(eng or E.Engine())
    try:
        r = repr(sympy_api.ask(p, a))
    except Exception as e:
        r = f'{type(e).__name__}: {e}'[:160]
    rec = dict(label=label, answer=r, epoch=epoch.EPOCH[0])
    if not PY:
        rec.update(cache=dict(C.CACHE_COUNTS), size=len(C._ROW_CACHE))
    LOG.append(rec)
    return r


class MyExpr(Expr):
    """Kept positive and commutative: the plainest class of one's own."""
    is_commutative = True
    is_positive = True
    is_real = True

    def __new__(cls, a):
        return Expr.__new__(cls, a)


class Sub(MyExpr):
    pass


def default_engine_nondefault_registry():
    """An engine with its own `templates`: Kept before any row."""
    ask('fill', Q.positive(x**2 + 1), Q.real(x))
    other = E.Engine(templates=lambda node: ())
    ask('non-default', Q.positive(sin(x)**2 + 1), Q.real(x), other)
    ask('back', Q.positive(sin(x)**2 + 1), Q.real(x))


def template_from_other_module():
    """A template from outside satassume: bump, row rebuilt, Kept for that class only."""
    f = MyExpr(x)
    ask('before', Q.positive(f + 1))

    def tmpl(*a, **k):
        return []
    tmpl.__module__ = 'someone.elses'
    registry.register(MyExpr)(tmpl)
    ask('after', Q.positive(f + 1))
    ask('other class', Q.positive(x**2 + 1))


def class_registered_midway():
    """A template on a base, with the subclass's row already cached."""
    f = Sub(x)
    ask('before', Q.positive(f))

    def tmpl(*a, **k):
        return []
    tmpl.__module__ = 'satassume.planted_here'
    registry.register(MyExpr)(tmpl)
    ask('after', Q.positive(f))


def new_class_after_fill():
    ask('fill', Q.positive(x + 1), Q.positive(x))

    class Late(MyExpr):
        pass
    ask('late', Q.positive(Late(x)))


def extensions_register():
    from satassume.knowledge import extensions as X
    ask('before', Q.prime(MyExpr(x)))

    def f(*a, **k):
        return True
    X.register(Q.prime, MyExpr)(f)
    ask('registered', Q.prime(MyExpr(x)))
    X.unregister(Q.prime)
    ask('unregistered', Q.prime(MyExpr(x)))


def undefined_function_equal_classes():
    """Function('f') twice makes two classes that compare equal; different assumptions make classes that don't."""
    f1, f2 = Function('f'), Function('f')
    g = Function('f', real=True)
    LOG.append(dict(label='classes', equal=f1 == f2, same=f1 is f2, hash_equal=hash(f1) == hash(f2), real_equal=f1 == g))
    ask('f1', Q.positive(f1(x)), Q.positive(f1(x)))
    ask('f2', Q.positive(f2(x)), Q.positive(f2(x)))
    ask('real', Q.real(g(x)))
    ask('plain', Q.real(f1(x)))


def sympy_handlers():
    """`Q.x.register` and `_eval_is_*`: the row doesn't read them."""
    f = MyExpr(x)
    ask('before', Q.prime(f))
    Q.prime.register(MyExpr)(lambda e, assumptions: True)
    ask('registered', Q.prime(f))
    MyExpr._eval_is_prime = lambda self: True
    ask('eval set', Q.prime(f))


def patched(attr, value, query):
    """What's asked before and after setting `attr` on the class, with no epoch bump."""
    ask('before', query)
    setattr(MyExpr, attr, value)
    ask('after', query)


def patch_as_base_exp():
    f = MyExpr(x)
    patched('as_base_exp', lambda self: (x, S(2)), Q.positive(f * x**2))


def patch_op_priority():
    patched('_op_priority', 1000.0, Q.positive(MyExpr(x) + 1))


def patch_add():
    patched('__add__', lambda self, o: S.Zero, Q.zero(MyExpr(x) + y))


def patch_atoms():
    patched('atoms', lambda self, *t: set(), Q.positive(MyExpr(x) + 1))


def patch_class_key():
    # Reorders the sides of a comparison, so the eq atom's order and the keys move.
    ask('before', Q.eq(MyExpr(x), sin(x)))
    MyExpr.class_key = classmethod(lambda c: (10, 0, 'Zzz'))
    ask('after', Q.eq(MyExpr(x), sin(x)))


def patch_hashable_content():
    patched('_hashable_content', lambda self: (1,) + self.args, Q.positive(MyExpr(x) + 1))


def patch_ordering_of_classes():
    ask('before', Q.eq(sin(x), cos(x)))
    ordering_of_classes.insert(0, ordering_of_classes.pop(ordering_of_classes.index('cos')))
    ask('after', Q.eq(sin(x), cos(x)))


def patch_is_number_class_flag():
    """`FLAGS`' `is_*` class attributes."""
    patched('is_Number', True, Q.positive(MyExpr(x) + 1))


if __name__ == '__main__':
    name = sys.argv[1]
    globals()[name]()
    out = dict(case=name, cache=(C._CACHE if not PY else 'py'), log=LOG)
    if not PY:
        out['refusals'] = term_live.REFUSALS[:10]
        out['term'] = {k: v for k, v in term_live.counts().items() if k.startswith(('converted', 'kept:', 'refus'))}
    print(json.dumps(out, default=repr))
