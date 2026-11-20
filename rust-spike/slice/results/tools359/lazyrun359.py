import json, runpy, sys
wl, out = sys.argv[1:3]
sys.argv = ['lazy_reads.py', wl, out] + sys.argv[3:]
import os
if os.environ.get('FROM_ENV'):      # lazy_reads.py never calls convert.from_env(): do it here, so SLICE_CONVERT takes effect
    sys.path.insert(0, os.getcwd())
    import convert
    convert.from_env()
try:
    runpy.run_path('lazy_reads.py', run_name='__main__')
finally:
    import convert, sa_solver
    w = convert.WALK[0]
    print(json.dumps(dict(walk='py' if w is None else ','.join(w.ITEMS), cv={k: v for k, v in sa_solver.walk_counts().items() if v})), file=sys.stderr)
