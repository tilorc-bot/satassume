"""Runtime trap for SymPy reasoning reached from satassume code
(``tests/test_sympy_boundary.py``).

:func:`install` patches SymPy process-wide, so it runs only in the corpus
subprocess (``tests/_sympy_boundary_corpus.py``), before satassume is
imported.  Each event is attributed to the innermost frame in the package
(the *site*) and to the SymPy function the package called there (the
*entry*; None when the site called the trapped function itself):

* ``forbidden``: a call of SymPy's own reasoning or simplification
  (``ask``, ``refine``, ``satask``, ``simplify`` and friends, ``cancel``,
  ``factor``, ``gcd``, ``solve``, the ``Expr.equals``/``.simplify``/
  ``.refine``/... methods, any SymPy class's ``_eval_refine``).  Each is
  wrapped in its defining class or module and rebound in every loaded
  ``sympy.*`` module, so ``from sympy import simplify`` bindings, SymPy's
  local imports and method calls all reach the wrapper.  An event whose
  entry is construction (:data:`CONSTRUCTION`) is allowed: SymPy's
  constructors call such functions themselves (``Mul.flatten`` may call
  ``logcombine``), and with plain symbols they decide nothing about the
  facts.  Any other raises :class:`TrapError`;
* ``symbol_assumption``: an old-assumption property of a symbol declared
  with assumptions returned True or False while package code was on the
  stack (SymPy core or the package used a fact of the symbol, not of the
  Q facts).

Every event is recorded in :data:`EVENTS`, also the raising ones:
:class:`TrapError` is a ``BaseException`` so that no ``except Exception``
of the package can hide it, but the record does not depend on that.
"""
import importlib
import os
import sys
import threading
import types

#: entries that are expression construction: the cached constructors
#: (``Add``, ``Mul``, ``Pow`` and the functions go through ``cacheit``),
#: any ``__new__``, the arithmetic operators (SymPy's decorators) and
#: ``xreplace``
CONSTRUCTION = frozenset({
    "sympy.core.cache.wrapper", "sympy.core.decorators._func",
    "sympy.core.decorators.binary_op_wrapper", "sympy.core.decorators.__sympifyit_wrapper",
    "sympy.core.basic.xreplace"})

FORBIDDEN_FUNCS = [("sympy.simplify.simplify", n) for n in (
    "simplify", "nsimplify", "logcombine", "posify", "separatevars", "signsimp")] + [
    ("sympy.simplify.trigsimp", "trigsimp"), ("sympy.simplify.trigsimp", "futrig"),
    ("sympy.simplify.powsimp", "powsimp"), ("sympy.simplify.powsimp", "powdenest"),
    ("sympy.simplify.radsimp", "radsimp"), ("sympy.simplify.ratsimp", "ratsimp"),
    ("sympy.simplify.sqrtdenest", "sqrtdenest"), ("sympy.simplify.combsimp", "combsimp"),
    ("sympy.simplify.gammasimp", "gammasimp"), ("sympy.simplify.fu", "fu"),
    ("sympy.polys.polytools", "cancel"), ("sympy.polys.polytools", "factor"),
    ("sympy.polys.polytools", "gcd"), ("sympy.polys.rationaltools", "together"),
    ("sympy.polys.numberfields.minpoly", "minimal_polynomial"),
    ("sympy.solvers.solvers", "solve"), ("sympy.solvers.solveset", "solveset"),
    ("sympy.assumptions.ask", "ask"), ("sympy.assumptions.refine", "refine"),
    ("sympy.assumptions.satask", "satask"), ("sympy.assumptions.lra_satask", "lra_satask"),
]
#: methods wrapped on every SymPy class that defines them
FORBIDDEN_METHODS = ("equals", "simplify", "refine", "_eval_refine", "cancel", "factor",
                     "nsimplify", "trigsimp", "radsimp", "powsimp", "ratsimp", "combsimp",
                     "gammasimp")

EVENTS = []
PKG = None          # the package directory, with a trailing separator
_HERE = os.path.abspath(__file__)
_guard = threading.local()


class TrapError(BaseException):
    pass


def _site(start):
    """``(site, entry)`` of the innermost package frame above ``start``."""
    f = sys._getframe(start)
    below = None
    while f is not None:
        fn = f.f_code.co_filename
        if fn.startswith(PKG):
            entry = below and f"{below.f_globals.get('__name__', '?')}.{below.f_code.co_name}"
            return f"{fn[len(PKG):]}:{f.f_lineno} {f.f_code.co_name}", entry
        if fn != _HERE:
            below = f
        f = f.f_back
    return None, None


def _wrap(name, fn):
    def wrapper(*a, **k):
        if getattr(_guard, "busy", False):
            return fn(*a, **k)      # nested in a call already recorded
        site, entry = _site(2)
        if site is None:
            return fn(*a, **k)
        allowed = entry in CONSTRUCTION or bool(entry) and entry.endswith(".__new__")
        EVENTS.append({"kind": "forbidden", "name": name, "site": site, "entry": entry,
                       "allowed": allowed})
        if not allowed:
            raise TrapError(f"{name} reached from {site} (entry {entry})")
        _guard.busy = True
        try:
            return fn(*a, **k)
        finally:
            _guard.busy = False
    wrapper.__wrapped__ = fn
    wrapper.__name__ = getattr(fn, "__name__", name)
    wrapper.__doc__ = getattr(fn, "__doc__", None)
    return wrapper


def _subclasses(c):
    out, todo = {c}, [c]
    while todo:
        for s in todo.pop().__subclasses__():
            if s not in out:
                out.add(s)
                todo.append(s)
    return out


def install(pkg_dir):
    global PKG
    PKG = os.path.join(os.path.abspath(pkg_dir), "")
    # the wrappers add frames: keep the package's own RecursionError guards
    # from firing earlier than they would untrapped
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4000))
    import sympy
    from sympy.core.assumptions import _assume_defined, as_property
    from sympy.core.basic import Basic
    from sympy.core.symbol import Symbol

    wrapped = {}
    for mod, attr in FORBIDDEN_FUNCS:
        m = importlib.import_module(mod)
        fn = getattr(m, attr)
        wrapped[id(fn)] = w = _wrap(f"{mod.rsplit('.', 1)[-1]}.{attr}", fn)
        setattr(m, attr, w)
    for name, m in list(sys.modules.items()):
        if name.startswith("sympy") and m is not None:
            for k, v in list(vars(m).items()):
                if id(v) in wrapped:
                    setattr(m, k, wrapped[id(v)])
    for c in _subclasses(Basic):
        if c.__module__.startswith("sympy"):
            for meth in FORBIDDEN_METHODS:
                fn = c.__dict__.get(meth)
                if isinstance(fn, types.FunctionType):
                    setattr(c, meth, _wrap(f"{c.__name__}.{meth}", fn))

    def wrap_prop(pname, prop):
        fget = prop.fget

        def getit(self):
            v = fget(self)
            if v is not None and isinstance(self, Symbol) and not getattr(_guard, "busy", False) \
                    and set(self.assumptions0) != {"commutative"}:
                site, entry = _site(2)
                if site is not None:
                    EVENTS.append({"kind": "symbol_assumption", "name": pname, "site": site,
                                   "entry": entry, "allowed": False})
            return v
        return property(getit, prop.fset, prop.fdel)

    facts = {as_property(k) for k in _assume_defined} - {"is_commutative"}
    for c in _subclasses(Symbol) | set(Symbol.__mro__):
        for pname in facts:
            p = c.__dict__.get(pname)
            if isinstance(p, property):
                setattr(c, pname, wrap_prop(pname, p))
    sympy.core.cache.clear_cache()
