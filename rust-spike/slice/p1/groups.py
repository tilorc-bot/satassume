import json,sys,collections
for path in sys.argv[1:]:
    rows=[json.loads(l) for l in open(path)]
    rows=[r for r in rows if 'q' in r]
    g=collections.Counter(); caught=collections.Counter(); qc=0; sess=0
    for r in rows:
        if r.get('caught'):
            qc+=1
            for c in r['caught']: caught[(c[0],c[1])]+=1
        for s in r.get('sessions',[]):
            sess+=1
            g[json.dumps(s.get('group'))]+=1
    print(path.split('/')[-1],'rows',len(rows),'sessions',sess,'queries_with_catch',qc)
    print(' groups',g.most_common(30))
    print(' caught',caught.most_common(20))
    print(' answers',collections.Counter(str(r['ans'])[:30] for r in rows).most_common(6))
