"""A counter that has fired: a raise planted at `_build_context`'s complete check in rust mode reaches handler_count, on the lazy and cached tree."""
import json, sys
sys.path.insert(0, '.')
import p_install
p_install.install()
from sympy import Q, symbols
from satassume import engine as E, sympy_api
import handler_count, term_live, lra_live, convert as C
term_live.install(keys=False, terms=True); lra_live.install()
x = symbols('x', real=True)
out = sys.argv[1]; handler_count.install(out)
real = E.Session.check if hasattr(E.Session, 'check') else None
names = [n for n in dir(E.Engine) if 'complete' in n.lower()] + [n for n in dir(E.Session) if 'complete' in n.lower()]
print('hooks', names[:6])
def boom(*a, **k): raise ValueError('planted')
target = next(c for c in (E.Session, E.Engine) if any('complete' in n.lower() for n in dir(c)))
n = next(n for n in dir(target) if 'complete' in n.lower())
setattr(target, n, boom)
sympy_api.set_default_engine(E.Engine())
print('answer', repr(sympy_api.ask(Q.positive(x + 1), Q.positive(x))), 'lazy', C._LAZY, 'cache', C._CACHE)
handler_count._out.flush()
print('fired', sum(1 for _ in open(out)), open(out).read()[:200])
