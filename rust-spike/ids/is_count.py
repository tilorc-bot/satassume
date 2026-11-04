"""is_count.py: AST count of `is` / `is not` in satassume/, split by what the comparison is against."""
import ast
import collections
import os
import sys
root = sys.argv[1]
c = collections.Counter()
by = collections.Counter()
ex = collections.defaultdict(list)
for dp, _, fs in os.walk(root):
    for f in fs:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        for n in ast.walk(ast.parse(open(p).read())):
            if isinstance(n, ast.Compare):
                left = n.left
                for op, r in zip(n.ops, n.comparators):
                    if isinstance(op, (ast.Is, ast.IsNot)):
                        sides = (ast.unparse(left), ast.unparse(r))
                        if any(s in ("None", "NotImplemented") for s in sides):
                            k = "None"
                        elif any(s in ("True", "False") for s in sides):
                            k = "bool"
                        elif any(s.startswith(("S.", "sp.S.", "sympy.S.")) or s in ("true", "false", "nan", "oo", "zoo", "pi", "E", "I") for s in sides):
                            k = "sympy singleton"
                        elif any(s.startswith("type(") or s[:1].isupper() for s in sides):
                            k = "type/constant"
                        else:
                            k = "object identity"
                            if len(ex[k]) < 40:
                                ex[k].append(f"{os.path.relpath(p, root)}:{n.lineno}: {sides[0]} is {sides[1]}")
                        c[k] += 1
                        by[(os.path.relpath(p, root), k)] += 1
                    left = r
print(dict(c), "total", sum(c.values()))
for k in ("sympy singleton",):
    print(k, sorted(((f, n) for (f, kk), n in by.items() if kk == k), key=lambda x: -x[1])[:12])
for e in ex["object identity"]:
    print(e)
