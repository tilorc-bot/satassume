"""set_iter.py: static floor on iteration over sets in satassume/. An iterable counts when it is, in the same function,
visibly a set: a set/frozenset call or literal or comprehension, a name assigned or annotated as one, an attribute annotated or assigned
as one on self, or `.free_symbols` / `.atoms(...)`. Wrapped in sorted(...) does not count (order fixed). It misses sets passed in
as arguments or stored in another object, so it is a floor. Prints each site."""
import ast, os, sys
ROOT = sys.argv[1]
def is_set_expr(n, names):
    if isinstance(n, (ast.Set, ast.SetComp)): return True
    if isinstance(n, ast.Call):
        f = n.func
        if isinstance(f, ast.Name) and f.id in ("set", "frozenset"): return True
        if isinstance(f, ast.Attribute) and f.attr in ("atoms", "union", "intersection", "difference"): return True
    if isinstance(n, ast.Attribute):
        if n.attr == "free_symbols": return True
        if isinstance(n.value, ast.Name) and f"{n.value.id}.{n.attr}" in names: return True
    if isinstance(n, ast.Name) and n.id in names: return True
    if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.BitOr, ast.BitAnd, ast.Sub)):
        return is_set_expr(n.left, names) or is_set_expr(n.right, names)
    return False
def ann_set(a):
    s = ast.unparse(a) if a is not None else ""
    return s.startswith(("set", "Set", "frozenset", "FrozenSet", "typing.Set"))
def key(t):
    if isinstance(t, ast.Name): return t.id
    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name): return f"{t.value.id}.{t.attr}"
tot = 0
for dp, _, fs in os.walk(ROOT):
    for f in fs:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        tree = ast.parse(open(p).read())
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))] + [tree]
        seen = set()
        for fn in funcs:
            names = set()
            for n in ast.walk(fn):
                if isinstance(n, ast.Assign) and is_set_expr(n.value, names):
                    for t in n.targets:
                        k = key(t)
                        if k: names.add(k)
                if isinstance(n, ast.AnnAssign) and ann_set(n.annotation):
                    k = key(n.target)
                    if k: names.add(k)
            if not isinstance(fn, ast.Module):
                for a in fn.args.args + fn.args.kwonlyargs:
                    if ann_set(a.annotation): names.add(a.arg)
            for n in ast.walk(fn):
                its = []
                if isinstance(n, (ast.For, ast.AsyncFor)): its = [n.iter]
                elif isinstance(n, ast.comprehension): its = [n.iter]
                elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("list", "tuple", "next", "iter", "enumerate") and n.args: its = [n.args[0]]
                for it in its:
                    if is_set_expr(it, names) and (p, it.lineno) not in seen:
                        seen.add((p, it.lineno))
                        print(f"{os.path.relpath(p, ROOT)}:{it.lineno}: {ast.unparse(it)[:70]}")
                        tot += 1
print("total", tot)
