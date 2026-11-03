import json,sys,collections
a=[json.loads(l) for l in open(sys.argv[1])]; b=[json.loads(l) for l in open(sys.argv[2])]
assert len(a)==len(b)
C=collections.Counter()
for x,y in zip(a,b):
    assert x[:2]==y[:2]
    if x[2]!=y[2]:
        C["more definite" if x[2] is None and y[2] in (True,False) else "less definite" if y[2] is None and x[2] in (True,False) else f"other {x[2]}->{y[2]}"]+=1
print(sys.argv[2].split("/")[-1], len(a), dict(C) or "identical")
