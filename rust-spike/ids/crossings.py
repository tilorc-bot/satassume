"""crossings.py: AST list of satassume functions that hand a container to SymPy or read one from it (xreplace, subs, match, free_symbols,
atoms, as_coefficients_dict, as_powers_dict): the sites where a dict or set meets SymPy's real hash. Prints file.py:qualname lines."""
import ast
import os
import sys
NAMES = {"xreplace", "subs", "replace", "match", "free_symbols", "atoms", "as_coefficients_dict", "as_powers_dict", "has_free", "find", "as_independent"}
root = sys.argv[1]
out = {}
for dp, _, fs in os.walk(root):
    for f in fs:
        if not f.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(dp, f)).read())

        def walk(n, q):
            for c in ast.iter_child_nodes(n):
                if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    nq = q + [c.name] + (["<locals>"] if not isinstance(c, ast.ClassDef) else [])
                    walk(c, nq)
                else:
                    if isinstance(c, ast.Attribute) and c.attr in NAMES and q and not (c.attr == "replace" and isinstance(c.value, ast.Constant)):
                        k = f"{f}:{'.'.join(q).removesuffix('.<locals>')}"
                        out.setdefault(k, set()).add(f"{c.attr}:{c.lineno}")
                    walk(c, q)
        walk(tree, [])
for k, v in sorted(out.items()):
    print(f"{k}  # {' '.join(sorted(v))}")
