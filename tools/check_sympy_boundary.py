"""SymPy boundary check of the shipped package: what ruff cannot see.

ruff's TID251 (``pyproject.toml``) bans *imports* of SymPy's reasoning and
simplification (``ask``, ``refine``, ``satask``, ``simplify``, ``cancel``,
...).  A method call or an old-assumption read needs no import, so this
check walks the AST of ``satassume/`` and flags

* calls of SymPy methods that rewrite or reason: ``x.simplify()``,
  ``x.cancel()``, ``x.equals(y)``, ``x.refine(a)``, ``x._eval_refine(a)``,
  ``x.evalf()``, ``x.n()``, ``x.is_constant()``, ``x.as_leading_term(t)``,
  ``x._eval_is_<fact>()``, ..., also uncalled (``m = x.cancel``, but not
  ``.n``) and by name (``getattr(x, 'simplify')``);
* reads of SymPy's old-assumption facts: ``x.is_<fact>`` for every fact of
  ``sympy.core.assumptions._assume_defined`` but ``commutative``, and
  ``is_comparable`` (it evaluates numerically); the fact KBs
  (``assumptions0``, ``x._assumptions``, ``default_assumptions``, ...;
  ``self._assumptions`` is the SAT solver's own list);
  ``getattr(x, 'is_...')`` with a literal, ``'is_' + name`` or f-string name.

A call ``x.is_integer()`` is not flagged: SymPy's facts are properties, so a
called ``is_<fact>`` is another type's method (``Fraction.is_integer``).
Structural attributes (``is_Atom``, ``is_Add``, ``is_Rational``,
``is_Symbol``, ``is_commutative``, ``is_number``, ...) are not flagged:
``is_number`` is decided by the class and the arguments, never by a fact.

A site that is legitimate carries ``# sympy-boundary: <reason>`` on a line of
its statement (or of its dict item, in a table of guards), or on a comment
line right above it.  Exit status 1 lists ``file:line``.

    python tools/check_sympy_boundary.py [PATH ...]     (default: satassume/)
"""
from __future__ import annotations

import ast
import io
import sys
import tokenize
from pathlib import Path

METHODS = frozenset({
    "simplify", "cancel", "equals", "refine", "_eval_refine", "trigsimp",
    "nsimplify", "factor", "ratsimp", "powsimp", "radsimp", "combsimp",
    "gammasimp", "together", "evalf", "n", "as_real_imag", "is_constant",
    "as_leading_term"})
# sympy.core.assumptions._assume_defined (SymPy 1.14) without commutative
FACTS = frozenset("""algebraic antihermitian complex composite even extended_negative
    extended_nonnegative extended_nonpositive extended_nonzero extended_positive
    extended_real finite hermitian imaginary infinite integer irrational negative
    noninteger nonnegative nonpositive nonzero odd polar positive prime rational
    real transcendental zero""".split())
FACT_ATTRS = frozenset({"is_" + f for f in FACTS} | {"is_comparable"})
KB_ATTRS = frozenset({"assumptions0", "_assumptions", "_assumptions0", "_assumptions_orig",
                      "default_assumptions"})
MARK = "sympy-boundary:"


def _marks(source: str) -> set:
    """Lines carrying a mark (a mark on a comment line counts for the next)."""
    out = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT and MARK in tok.string \
                and tok.string.split(MARK, 1)[1].strip():
            row, col = tok.start
            out.add(row + 1 if not tok.line[:col].strip() else row)
    return out


def _spans(tree) -> list:
    """``(first, last)`` lines of the simple statements and dict items."""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.stmt) and not hasattr(n, "body"):
            out.append((n.lineno, n.end_lineno))
        elif isinstance(n, ast.Dict):
            out += [((k or v).lineno, v.end_lineno) for k, v in zip(n.keys, n.values)]
    return out


def _dynamic_is(node) -> bool:
    """``'is_' + name`` or ``f'is_{name}'``."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        node = node.left
    elif isinstance(node, ast.JoinedStr) and node.values:
        node = node.values[0]
    return isinstance(node, ast.Constant) and isinstance(node.value, str) \
        and node.value.startswith("is_")


def check_source(source: str, filename: str = "<string>") -> list:
    """``[(line, what)]`` of the unmarked sites in ``source``."""
    tree = ast.parse(source, filename)
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    found = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute):
            # an uncalled reference too (a bound-method alias), but ``.n``
            # is a common attribute name
            if n.attr in METHODS and (id(n) in called or n.attr != "n") \
                    or n.attr.startswith("_eval_is_"):
                found.append((n.lineno, f".{n.attr}() call"))
            elif n.attr in FACT_ATTRS and id(n) not in called or n.attr in KB_ATTRS \
                    and not (n.attr == "_assumptions" and isinstance(n.value, ast.Name)
                             and n.value.id == "self"):
                found.append((n.lineno, f".{n.attr} read"))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id in ("getattr", "hasattr") and len(n.args) >= 2:
            a = n.args[1]
            if _dynamic_is(a) and not (isinstance(a, ast.Constant)
                                       and a.value not in FACT_ATTRS):
                found.append((n.lineno, f"{n.func.id}(x, 'is_...') read"))
            elif isinstance(a, ast.Constant) and a.value in KB_ATTRS:
                found.append((n.lineno, f"{n.func.id}(x, {a.value!r}) read"))
            elif isinstance(a, ast.Constant) and isinstance(a.value, str) \
                    and (a.value in METHODS or a.value.startswith("_eval_is_")):
                found.append((n.lineno, f"{n.func.id}(x, {a.value!r}) method"))
    marks, spans = _marks(source), _spans(tree)

    def covered(line):
        a, b = min((s for s in spans if s[0] <= line <= s[1]),
                   key=lambda s: s[1] - s[0], default=(line, line))
        return any(a <= m <= b for m in marks)
    return sorted({(line, what) for line, what in found if not covered(line)})


def main(argv) -> int:
    paths = [Path(p) for p in argv] or [Path(__file__).resolve().parent.parent / "satassume"]
    files = [f for p in paths for f in (sorted(p.rglob("*.py")) if p.is_dir() else [p])]
    bad = 0
    for f in files:
        for line, what in check_source(f.read_text(), str(f)):
            print(f"{f}:{line}: {what} without '# {MARK} <reason>'")
            bad += 1
    print(f"check_sympy_boundary: {len(files)} files, {bad} unmarked sites")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
