"""A lazy facts read that raises, and rows with no row `.args` reaches. What's counted, and that the query still answers as Python."""
import sys
sys.path.insert(0, '.')
import p_install
p_install.install()
from sympy import Expr, Q, Symbol, symbols, sin
from satassume import engine as E, sympy_api
import term_live, lra_live, convert as C
term_live.install(keys=False, terms=True); lra_live.install()
x, y = symbols('x y', real=True); h = Symbol('hidden', real=True)
class Raises(Expr):
    is_commutative = True
    def __new__(cls, a): return Expr.__new__(cls, a)
    @property
    def free_symbols(self): raise ValueError('planted')
class Hidden(Expr):
    is_commutative = True
    def __new__(cls, a): return Expr.__new__(cls, a)
    @property
    def free_symbols(self): return {h}
for label, p, a in (('raises', Q.eq(Raises(x), y), Q.zero(Raises(x) - y)), ('hidden', Q.eq(Hidden(x), y), Q.zero(Hidden(x) - y))):
    sympy_api.set_default_engine(E.Engine())
    try: r = repr(sympy_api.ask(p, a))
    except Exception as e: r = f'{type(e).__name__}: {str(e)[:100]}'
    print(label, 'lazy' if C._LAZY else 'eager', r, {k: v for k, v in term_live.counts().items() if k in ('read:facts', 'read_raised', 'read_term_missing')}, term_live.REFUSALS[-1:])
