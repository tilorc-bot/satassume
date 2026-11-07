"""Looking for a real answer difference from a stale row. Usage: break_probe.py NAME [--py]; each NAME builds its terms before the patch."""
import json, sys
sys.path.insert(0, '.')
PY = '--py' in sys.argv
if not PY:
    import p_install
    p_install.install()
from sympy import Expr, Mul, Q, S, Symbol, exp, sin, symbols, log
from sympy.core.basic import ordering_of_classes
from satassume import engine as E, sympy_api
if not PY:
    import term_live, lra_live, convert as C
    term_live.install(keys=False, terms=True); lra_live.install()
x, y, z = symbols('x y z', real=True)
LOG = []
def ask(label, p, a=True):
    sympy_api.set_default_engine(E.Engine())
    try:
        r = repr(sympy_api.ask(p, a))
    except Exception as e:
        r = f'{type(e).__name__}: {e}'[:120]
    LOG.append((label, r))
class F(Expr):
    is_commutative = True
    is_real = True
    is_finite = True
    def __new__(cls, a):
        return Expr.__new__(cls, a)
f = F(x)
def sub_patch():
    p, a = Q.eq(f, y), Q.positive(f - y)
    ask('before', p, a)
    F.__sub__ = lambda self, o: S.One
    F.__rsub__ = lambda self, o: S.One
    ask('after', p, a)
def add_patch():
    p, a = Q.eq(y, f), Q.positive(y - f)
    ask('before', p, a)
    F.__neg__ = lambda self: S.One
    F.__mul__ = F.__rmul__ = lambda self, o: S.One
    ask('after', p, a)
def base_exp_patch():
    p, a = Q.eq(y, f), Q.positive(y - f)
    ask('before', p, a)
    F.as_base_exp = lambda self: (x, S(2))
    ask('after', p, a)
def op_priority_patch():
    p, a = Q.eq(f, y), Q.positive(f - y)
    ask('before', p, a)
    class G(Expr):
        _op_priority = 500.0
        is_commutative = True
    F._op_priority = 1000.0
    F.__sub__ = lambda self, o: S.One
    ask('after', p, a)
def rank_patch():
    # Add's arg order comes from Basic.compare's class rank: a derived sum in the old order merges with the input term, in the new one it doesn't.
    u, v = sin(x), exp(x)
    p, a = Q.eq(u, -v), Q.positive(u + v)
    ask('before', p, a)
    i, j = ordering_of_classes.index('sin') if 'sin' in ordering_of_classes else -1, ordering_of_classes.index('exp') if 'exp' in ordering_of_classes else -1
    LOG.append(('ranks', (i, j, str((u+v).args))))
    ordering_of_classes[i], ordering_of_classes[j] = ordering_of_classes[j], ordering_of_classes[i]
    Add_order = (sin(x) + exp(x)).args
    LOG.append(('new order', str(Add_order)))
    ask('after', p, a)
class G(Expr):
    is_commutative = True
    def __new__(cls, a):
        return Expr.__new__(cls, a)
w = Symbol('w')
g, g2 = G(w), G(z)
def ops_links():
    # PLAIN_OPS. Python's a - b and b - a both stop linking; a stale row's Rust still builds the input's difference.
    p, a = Q.eq(g, w), Q.zero(g - w)
    ask('before', p, a)
    G.__sub__ = lambda self, o: S.One
    G.__neg__ = lambda self: S.One
    ask('after', p, a)
def base_links():
    # PLAIN_BASE. -g2 becomes -w**2 in Python: the difference isn't the input's any more.
    p, a = Q.eq(g, g2), Q.zero(g - g2)
    ask('before', p, a)
    G.as_base_exp = lambda self: (w, S(2))
    ask('after', p, a)
def rank_links():
    # rank. Add's order comes from Basic.compare's class rank.
    v, u = Symbol('u'), Symbol('v')
    p, a = Q.eq(v**2, u), Q.zero(v**2 - u)
    ask('before', p, a)
    i, j = ordering_of_classes.index('Pow'), ordering_of_classes.index('Mul')
    ordering_of_classes[i], ordering_of_classes[j] = ordering_of_classes[j], ordering_of_classes[i]
    LOG.append(('order moved', str((v**2 - u).args) + ' was ' + str(a.arguments[0].args if hasattr(a, 'arguments') else '')))
    ask('after', p, a)
def rank_control():
    # The same patch with a new class's row built after it: nothing cached is stale for that class, so this shows only that patching alone isn't the issue.
    ordering_of_classes[ordering_of_classes.index('Pow')], ordering_of_classes[ordering_of_classes.index('Mul')] = 'Mul', 'Pow'
    v, u = Symbol('u'), Symbol('v')
    ask('after, no fill', Q.eq(v**2, u), Q.zero(v**2 - u))
globals()[sys.argv[1]]()
print(json.dumps(dict(case=sys.argv[1], log=LOG, refusals=(term_live.REFUSALS[:6] if not PY else []),
   cache=(C.CACHE_COUNTS['hit'] if not PY else None)), default=repr))
