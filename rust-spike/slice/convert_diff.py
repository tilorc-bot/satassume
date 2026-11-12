"""Both walkers over a run's own inputs (issue 323, the convert step, item 6): the differential test.

`diff(a, b)` says what differs between two outcomes of `convert.convert` on the same input objects; test_convert_walk.py
uses it on its own inputs. `install(out)` (SLICE_CONVERT_DIFF=DIR, through `convert.from_env`) wraps `convert.convert`
for a whole run, a workload or the suite: each query is converted twice, by Python's `_Walk` and by Rust's walker
with every item on, and those two are compared, every lazy read of every term included (SLICE_CONVERT_DIFF_READS=N:
of the first N terms only). Then the query is converted as the run asked, and the run goes on with that conversion,
untouched. `DIR/diff.PID.json` gets the number of inputs, of differences, of each kind of outcome, and the first
examples: written at every difference, every WRITE_EVERY inputs and at exit, so a worker that is killed loses no
difference. `python convert_diff.py DIR...` adds the files up and exits 1 on any difference or on no inputs at all.
"""
import collections
import glob
import json
import os
import sys

import convert

MAX_EXAMPLES = 20
WRITE_EVERY = 50
COUNTS = collections.Counter()
EXAMPLES = []


def typed(v):
    return [(type(a), a) for a in v] if isinstance(v, list) else v


def diff(a, b, read_terms=None):
    """What differs between two outcomes (a `Converted`, a `Kept`, or the exception raised), as names. Empty: the same.
    The same: the reason and detail of a `Kept`; an exception's type and message; tables equal token for token and type
    for type; `ids` with the same objects under the same ids in the same order; `objects` and `classes` the same objects;
    then each lazy read of each term (of the first `read_terms`, if given) answering alike, and the counts after."""
    if type(a) is not type(b):
        return [f'outcome {type(a).__name__} {type(b).__name__}']
    if isinstance(a, BaseException):
        return [] if str(a) == str(b) else [f'message {a} | {b}']
    if isinstance(a, convert.Kept):
        return [] if (a.reason, a.detail) == (b.reason, b.detail) else [f'kept {a.reason} {a.detail} | {b.reason} {b.detail}']
    out = []
    ta, tb = a.tables, b.tables
    if list(ta) != list(tb):
        out.append('table names')
    for k in ta:
        if k != 'reads' and typed(ta[k]) != typed(tb.get(k)):
            out.append('table ' + k)
    ia, ib = list(a.ids.items()), list(b.ids.items())
    if len(ia) != len(ib) or any(s is not t or i != j or type(i) is not type(j) for (s, i), (t, j) in zip(ia, ib)):
        out.append('ids')
    if len(a.objects) != len(b.objects) or any(s is not t for s, t in zip(a.objects, b.objects)):
        out.append('objects')
    if [(id(c), i) for c, i in a.classes.items()] != [(id(c), i) for c, i in b.classes.items()]:
        out.append('classes')
    if out:
        return out
    n = len(a.objects) if read_terms is None else min(read_terms, len(a.objects))
    for kind in range(len(convert.READS)):
        for i in range(n):
            if ta['reads'](kind, i) != tb['reads'](kind, i):
                out.append(f'read {convert.READS[kind]} {i}')
    if a.counts != b.counts or a.raised != b.raised:
        out.append('counts')
    return out


def outcome(walk, proposition, assumptions, eng, real=None):
    """`convert.convert` under one walker class (None: Python's `_Walk`), or what it raised."""
    was = convert.WALK[0]
    convert.WALK[0] = walk
    try:
        return (real or convert.convert)(proposition, assumptions, eng)
    except Exception as e:
        return e
    finally:
        convert.WALK[0] = was


def install(out, read_terms=None, control=False):
    """Wrap `convert.convert` (once per process) so that every input is also compared under both walkers."""
    import atexit
    if getattr(convert.convert, 'differential', False):
        return
    real = convert.convert
    rust = convert.rust_walk(() if control else convert.RUST_ITEMS)   # control: Python's walker against itself

    def both(proposition, assumptions, eng):
        a = outcome(None, proposition, assumptions, eng, real)
        b = outcome(rust, proposition, assumptions, eng, real)
        d = diff(a, b, read_terms)
        COUNTS['inputs'] += 1
        COUNTS['outcome:' + (a.reason if isinstance(a, convert.Kept) else type(a).__name__)] += 1
        if isinstance(a, convert.Converted):
            COUNTS['terms'] += len(a.objects)
        if d:
            COUNTS['differences'] += 1
            if len(EXAMPLES) < MAX_EXAMPLES:
                EXAMPLES.append([d[:6], repr(proposition)[:200], repr(assumptions)[:200]])
        if d or COUNTS['inputs'] % WRITE_EVERY == 0:
            write()
        return real(proposition, assumptions, eng)

    def write():
        os.makedirs(out, exist_ok=True)
        p = os.path.join(out, f'diff.{os.getpid()}.json')
        with open(p + '.tmp', 'w') as f:
            json.dump(dict(counts=COUNTS, examples=EXAMPLES, items=list(rust.ITEMS), walk=getattr(convert.WALK[0], 'ITEMS', 'py'),
                           read_terms=read_terms), f)
        os.replace(p + '.tmp', p)

    os.register_at_fork(after_in_child=lambda: (COUNTS.clear(), EXAMPLES.clear()))       # a forked child counts its own
    both.differential = True
    convert.convert = both
    atexit.register(write)


def total(dirs):
    c, ex, files = collections.Counter(), [], 0
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(d, 'diff.*.json'))):
            r = json.load(open(p))
            c.update(r['counts'])
            ex += r['examples']
            files += 1
    return files, c, ex


if __name__ == '__main__':
    files, c, ex = total(sys.argv[1:])
    print(json.dumps(dict(files=files, inputs=c['inputs'], differences=c['differences'], terms=c['terms'],
                          outcomes={k[8:]: v for k, v in sorted(c.items()) if k.startswith('outcome:')})))
    for e in ex[:10]:
        print('DIFF', e)
    raise SystemExit(1 if c['differences'] or not c['inputs'] else 0)
