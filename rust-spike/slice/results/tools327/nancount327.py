"""nancount327.py WL OUT.json (sa-port-327): run live.py WL rust with Python's walker (the default) and count what
`_may_be_nan` returns at its one per-query call site, convert.py:304 (`_Walk.term_row`): top-level calls, how many
return True, and for the True ones the term's class. convert.py holds the name by `from ... import`, so the rebind is on
the convert module, once live.py has imported it (run from rust-spike/slice); the inner recursion stays the original. Says whether any workload term has the bit set,
which is what plants 746-748 need in order to show on a workload."""
import collections, json, os, runpy, sys
wl, out = sys.argv[1], sys.argv[2]
import builtins
C = collections.Counter(); K = collections.Counter(); EX = []
real_import = builtins.__import__; done = []
def patch():
    convert = sys.modules['convert']; real = convert._may_be_nan
    def counted(a):
        r = real(a)
        C['calls'] += 1
        if r:
            C['true'] += 1; K[type(a).__name__] += 1
            if len(EX) < 5: EX.append(repr(a)[:120])
        return r
    convert._may_be_nan = counted; done.append(convert)
def hook(name, *a, **k):          # live.py installs its own plugin before satassume loads, so patch convert once it is in
    m = real_import(name, *a, **k)
    if not done and getattr(sys.modules.get('convert'), 'from_env', None) is not None:
        patch()
    return m
builtins.__import__ = hook
HERE = os.path.dirname(os.path.abspath(__file__)) if False else os.getcwd()
sys.argv = ['live.py', wl, 'rust', out + '.jsonl', '--check', 'entry']
try:
    runpy.run_path(os.path.join(HERE, 'live.py'), run_name='__main__')
except SystemExit as e:
    C['exit'] = int(e.code or 0)
finally:
    json.dump(dict(wl=wl, walk=repr(done[0].WALK[0]) if done else 'not patched', **C, true_by_class=dict(K), examples=EX), open(out, 'w'))
    try: os.remove(out + '.jsonl')
    except OSError: pass
