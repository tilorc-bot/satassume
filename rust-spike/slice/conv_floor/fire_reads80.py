"""read:rest, read:facts and read_raised each fire on the lazy tree: `row` forces them, `shape` doesn't."""
import sys
sys.path.insert(0, '.')
import p_install
p_install.install()
import sa_solver
from sympy import Expr, Q, symbols
from satassume import engine as E
import convert as C
x = symbols('x', real=True)
class Raises(Expr):
    is_commutative = True
    def __new__(cls, a): return Expr.__new__(cls, a)
    @property
    def free_symbols(self): raise ValueError('planted')
def table(p):
    c = C.convert(p, True, E.Engine())
    return c, sa_solver.TermTable(c.tables)
c, t = table(Q.positive(x + 1))
i = c.ids[x + 1]
t.shape(i); print('shape', c.counts['read:facts'], c.counts['read:rest'])
r = t.row(i); print('row', c.counts['read:facts'], c.counts['read:rest'], 'bits', r[4], 'free', r[3])
print('number', t.is_number_term(c.ids[x]), c.counts['read:facts'])
c, t = table(Q.positive(Raises(x)))
try:
    print(t.is_number_term(c.ids[Raises(x)]))
except sa_solver.TermRefuse as e:
    print('refused:', e, 'read_raised', c.counts['read_raised'], c.raised)
# The check mode's counter fires on a row made wrong by hand.
from sympy import Symbol
e = C._record_row(Symbol)
C._check_row(Symbol, ([*e[0][:7], e[0][7] + 1, *e[0][8:]], e[1]))
print('check_differ', C.CACHE_COUNTS['check_differ'], C.CACHE_DIFFERS[0][0])
