"""rdcmp335.py A.rows B.rows (sa-port-335): two rowdump335.py row files of one workload, line by line. Prints the rows
that differ, the element positions that differ, and the set of (b - a) offsets over the differing integer elements. One
offset over every differing element, with values in SymPy's Dummy index range (symbol.py:507, randint(10**6, 9*10**6)
plus a count), means the rows differ only by the process's random `Dummy._base_dummy_index`."""
import ast, sys, collections
a, b = sys.argv[1], sys.argv[2]
n = diff = shape = 0; offs = collections.Counter(); lo = hi = None; nonint = 0
for x, y in zip(open(a), open(b)):
    n += 1
    if x == y:
        continue
    diff += 1
    X, Y = ast.literal_eval(x), ast.literal_eval(y)
    if len(X) != len(Y):
        shape += 1; continue
    for p, q in zip(X, Y):
        if p != q:
            if type(p) is int and type(q) is int:
                offs[q - p] += 1
                lo = min(p, q) if lo is None else min(lo, p, q); hi = max(p, q) if hi is None else max(hi, p, q)
            else:
                nonint += 1
la = sum(1 for _ in open(a)); lb = sum(1 for _ in open(b))
print(f'{a} {la} rows | {b} {lb} rows | compared {n} | rows differing {diff} | length differs {shape} | non-int element differs {nonint}')
print(f'   offsets (b - a) over differing int elements: {dict(offs.most_common(4))} distinct {len(offs)} | values between {lo} and {hi}')
