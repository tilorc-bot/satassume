"""rowbit334.py WL OUT.json (sa-port-334; run from rust-spike/slice): run live.py WL rust and digest every row
`term_row` writes, on whichever walker SLICE_CONVERT selects (`_Walk.term_row`, or `_RustWalk.term_row` when Rust's is
on). A row is what the call appends to `out`; its flags byte is the third element from the end (convert.py's
`out += (T_INT, bits, T_INT, nc)`; a skeleton row has 0 there). OUT: rows per walker class, rows with bit 32 set, a
digest of the rows as written (`raw`) and one with bit 32 cleared (`masked`), each in call order (sha256) and as an
order-free sum. For the one line "row bytes differ from ec34788 in bit 32 only": `masked` equal between the two trees,
bit 32 rows N before and 0 after, and after `raw` == `masked`."""
import builtins, collections, hashlib, json, os, runpy, sys
wl, out = sys.argv[1], sys.argv[2]
C = collections.Counter(); H = {k: hashlib.sha256() for k in ('raw', 'masked')}; SUM = collections.Counter(); done = []
BIT = 32


def wrap(cls, name, T_INT):
    f = cls.__dict__.get('term_row')
    if f is None or getattr(f, '_rowbit', False):
        return

    def term_row(self, t, out, _f=f):
        n = len(out)
        r = _f(self, t, out)
        row = list(out[n:])
        C['rows:' + name] += 1
        if len(row) < 4 or row[-4] != T_INT or type(row[-3]) is not int:
            C['shape_bad'] += 1
            return r
        for k in ('raw', 'masked'):
            if k == 'masked' and row[-3] & BIT:
                C['bit32'] += 1
                row[-3] &= ~BIT
            b = repr(row).encode()
            H[k].update(b)
            SUM[k] = (SUM[k] + int.from_bytes(hashlib.sha256(b).digest()[:8], 'big')) % (1 << 64)
        return r
    term_row._rowbit = True
    cls.term_row = term_row


def patch():
    convert = sys.modules['convert']
    wrap(convert._Walk, '_Walk', convert.T_INT)
    for cls in list(convert._RUST.values()):          # classes rust_walk has already made, by items
        if isinstance(cls, type):
            wrap(cls, '_RustWalk', convert.T_INT)
    real = convert.rust_walk

    def rust_walk(*a, **k):          # the class is made inside rust_walk, once per set of items
        cls = real(*a, **k)
        wrap(cls, '_RustWalk', convert.T_INT)
        return cls
    convert.rust_walk = rust_walk
    done.append(convert)


real_import = builtins.__import__


def hook(name, *a, **k):          # as tools327/nancount327.py: patch convert once live.py has it in
    m = real_import(name, *a, **k)
    if not done and getattr(sys.modules.get('convert'), 'from_env', None) is not None:
        patch()
    return m


builtins.__import__ = hook
sys.argv = ['live.py', wl, 'rust', out + '.jsonl', '--check', 'entry']
try:
    runpy.run_path(os.path.join(os.getcwd(), 'live.py'), run_name='__main__')
except SystemExit as e:
    C['exit'] = int(e.code or 0)
finally:
    so = sys.modules.get('sa_solver')
    json.dump(dict(wl=wl, walk=repr(done[0].WALK[0]) if done else 'not patched', convert=os.environ.get('SLICE_CONVERT', 'py'),
                   so=hashlib.sha256(open(so.__file__, 'rb').read()).hexdigest()[:8] if so else None, **C,
                   raw=H['raw'].hexdigest()[:16], masked=H['masked'].hexdigest()[:16], raw_sum=SUM['raw'],
                   masked_sum=SUM['masked']), open(out, 'w'))
    try:
        os.remove(out + '.jsonl')
    except OSError:
        pass
