"""Every way code outside ``core`` plugs into ``core``: plain module attributes.

Core reads them at call time (``hooks.name``), so whoever sets one does so once,
at load, by assignment or in place.  Nothing in ``core`` names a specific SymPy
function; what the engine needs to know about particular heads is a role here.

Set by :mod:`..compat.sympy_fixes`:

:data:`rebuild`
    ``rebuild(func, args, assumptions)`` rebuilds a node from its refined
    children (the driver); the ``acot``/``acoth`` guard (B8).
:data:`eval_refine`
    SymPy ``_eval_refine`` method -> the copy the driver calls instead (a
    subclass overriding the method keeps its own).

Set by :mod:`..compat.matrix_match`:

:data:`match`
    matchers for pattern kinds the generic matcher does not know:
    ``hook(pattern, target, assumptions, binding, top)`` returns ``None`` when
    ``pattern`` is not of its kind (matching goes on with the generic forms),
    else an iterator of bindings (the only ones).
:data:`non_scalar`
    sum and product heads that are not scalar sums and products (``MatAdd``,
    ``MatMul``): the rest-symbol and sub-product forms skip them.
:data:`commutative`
    heads matched in every argument order (small arities).

Set by :func:`..rules._simple.install`:

:data:`fallback`
    key -> handler tried by the driver after the key's handler declines.
:data:`own_args`
    keys whose handler refines the node's arguments itself (``Piecewise``).
:data:`opaque`
    the default opaque heads of identity rows (``floor``, ``im``, ``arg``):
    a candidate still holding one is not accepted (:func:`.rewrite.identity_handler`,
    :func:`.split.case_split` with ``opaque=None``).
:data:`conditional`
    the head of a conditional expression (``Piecewise``): a candidate with a
    new one is an undecided definition, not a rewrite.
:data:`modulus`
    the modulus head (``Abs``): canonical in :func:`.measure.default_measure`,
    what :func:`.split.case_split` generalizes its cases by.
:data:`step`
    the step head (``floor``) the endpoint split (:func:`.split.endpoint_split`) resolves.
:data:`two_valued`
    ``two_valued(node, assumptions)``: ``(value, u, endpoint, alternative)`` when
    the step node is ``value`` except at one closed endpoint ``u = endpoint``
    (:func:`..rules._simple.floor_two_valued`), else ``None``.

Pushed by offline code (:mod:`satrefine.build`) through :func:`.driver.observing`:

:data:`observer`
    a stack of :class:`Observer`; the innermost one is consulted.  Its
    ``on_fire(kind, row)`` is called on each table-row firing (``kind``
    ``"rule"`` or ``"identity"``), and its ``tables(key)``, when set, gives the
    generated table the driver uses for ``key`` (``None``: none), whatever the mode.
"""
from __future__ import annotations

from typing import Any, Callable, NamedTuple

from sympy.core import Add, Mul
from sympy.core.operations import LatticeOp


def rebuild(func: Any, args: Any, assumptions: Any) -> Any:
    """The default: ``func(*args)``."""
    return func(*args)


eval_refine: dict = {}

match: list = []
non_scalar: tuple = ()
commutative: tuple = (Add, Mul, LatticeOp)

fallback: dict = {}
own_args: set = set()

opaque: tuple = ()
conditional: Any = None
modulus: Any = None
step: Any = None


def two_valued(node: Any, assumptions: Any) -> tuple | None:
    """The default: no step node is two-valued."""
    return None


class Observer(NamedTuple):
    """One entry of :data:`observer` (see :func:`.driver.observing`)."""
    on_fire: Callable | None
    tables: Callable | None


observer: list[Observer] = []
