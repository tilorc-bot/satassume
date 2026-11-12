"""Both walkers over a run's own inputs (issue 323, the convert step, item 6): the differential test.

`diff(a, b)` says what differs between two outcomes of `convert.convert` on the same input objects; test_convert_walk.py
uses it on its own inputs. `install(out)` (SLICE_CONVERT_DIFF=DIR, through `convert.from_env`) wraps `convert.convert`
for a whole run, a workload or the suite: each query is converted twice, by Python's `_Walk` and by Rust's walker
with every item on, and those two are compared, every lazy read of every term included (SLICE_CONVERT_DIFF_READS=N:
of the first N terms only). Then the query is converted as the run asked, and the run goes on with that conversion,
untouched. `DIR/diff.PID.json` gets the number of inputs, of differences, of each kind of outcome, and the first
examples: written at every difference, every WRITE_EVERY inputs and at exit, so a worker that is killed loses no
difference. `python convert_diff.py DIR...` adds the files up and exits 1 on any difference or on no inputs at all.

The lazy reads are made in fresh state (`fresh`): each walker's reads run in their own forked child of the state the
two conversions left, so both walkers are the first to ask, of the same objects in the same state (SymPy's caches,
each object's `_assumptions`, the assumptions shuffle), and neither's asking reaches the other or the run. A read can
evaluate, and SymPy's answer to the second asker isn't always its answer to the first (finite_history_repro.py:
`is_finite` of `x*ComplexRootOf._new(...)` raises or answers True by the shuffle and by who asked before), so reads
made one after the other in one process compare the askers' order, not the walkers. What is compared is every read's
value, the counts and what raised. Python's own second ask, in its child after the first, is recorded too: an input
where it answers differently counts under `reread` (history dependence in pure Python, reported with its inputs; not
a difference between the walkers, and nothing here hides one: both walkers' first asks are still compared).

A read gets READ_SECONDS of the child's CPU time (SLICE_CONVERT_DIFF_READ_SECONDS); past it the child is killed, and
the reads it had answered are still compared, each having been sent as it was made. When both children stop at the
same read, the input counts under `slow` (listed, not a difference: the reads after that one weren't compared); when
they stop at different reads, or only one stops, that is a difference. `reads` is the number of reads compared.
"""
import collections
import glob
import json
import io
import os
import pickle
import signal
import sys
import warnings

import convert

MAX_EXAMPLES = 20
MAX_REREAD = 400            # every `reread` and `slow` input is listed, up to this many of each per process
WRITE_EVERY = 50
READ_SECONDS = float(os.environ.get('SLICE_CONVERT_DIFF_READ_SECONDS', 30))     # CPU time one read gets in its child
CHILD_SECONDS = 1800        # wall time a child gets in all
COUNTS = collections.Counter()
EXAMPLES = []
REREAD = []
SLOW = []


def typed(v):
    return [(type(a), a) for a in v] if isinstance(v, list) else v


def fresh(*fns):
    """Each `fn(emit)` in its own forked child, all forked before any is waited for: for each, the list of what it gave
    `emit`, in order, then ('raised', type, message) if it raised. A child that is killed leaves what it had emitted.
    A child starts from this process's state as it is now, the same for all of them, and takes its own changes with it."""
    started = [_fork(fn) for fn in fns]
    return [_collect(pid, rd) for pid, rd in started]


def _fork(fn):
    rd, wr = os.pipe()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)      # 3.12 warns of fork under xdist's threads
        pid = os.fork()
    if pid == 0:
        try:
            os.close(rd)
            signal.signal(signal.SIGALRM, signal.SIG_DFL)
            signal.signal(signal.SIGVTALRM, signal.SIG_DFL)
            signal.alarm(CHILD_SECONDS)
            with os.fdopen(wr, 'wb') as f:
                def emit(v):
                    pickle.dump(v, f)
                    f.flush()
                try:
                    fn(emit)
                except BaseException as e:
                    emit(('raised', type(e).__name__, str(e)))
        finally:
            os._exit(0)
    os.close(wr)
    return pid, rd


def _collect(pid, rd):
    with os.fdopen(rd, 'rb') as f:
        got = io.BytesIO(f.read())
    os.waitpid(pid, 0)
    out = []
    try:
        while True:
            out.append(pickle.load(got))
    except Exception:           # the end, or a last one cut short by the kill
        return out


def reads(c, n, emit, again=False):
    """In a child: every lazy read of the first `n` terms of a `Converted`, kind by kind, each emitted as ('v', value)
    and each with READ_SECONDS of CPU time before the kill; then ('end', its counts, what raised, and with `again` the
    names of the reads that answer differently when asked a second time, here, after all of those)."""
    ask = c.tables['reads']
    order = [(kind, i) for kind in range(len(convert.READS)) for i in range(n)]
    values = []
    for kind, i in order:
        signal.setitimer(signal.ITIMER_VIRTUAL, READ_SECONDS)
        values.append(ask(kind, i))
        emit(('v', values[-1]))
    signal.setitimer(signal.ITIMER_VIRTUAL, 0)
    counts, raised = dict(c.counts), list(c.raised)
    second = [f'{convert.READS[kind]} {i}' for (kind, i), v in zip(order, values) if ask(kind, i) != v] if again else []
    emit(('end', counts, raised, second))


def diff(a, b, read_terms=None, seen=None):
    """What differs between two outcomes (a `Converted`, a `Kept`, or the exception raised), as names. Empty: the same.
    The same: the reason and detail of a `Kept`; an exception's type and message; tables equal token for token and type
    for type; `ids` with the same objects under the same ids in the same order; `objects` and `classes` the same objects;
    then each lazy read of each term (of the first `read_terms`, if given) answering alike, and the counts after, each
    outcome's reads in its own forked child (`fresh`). `seen`, a dict, gets `reads`, the number of reads compared;
    `reread`, the names of `a`'s reads that answered differently when asked a second time in `a`'s child; and `slow`,
    the read both children stopped at, if they did."""
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
    fa, fb = fresh(lambda emit: reads(a, n, emit, seen is not None), lambda emit: reads(b, n, emit))
    va, vb = [f[1] for f in fa if f[0] == 'v'], [f[1] for f in fb if f[0] == 'v']
    ea, eb = fa[len(va):], fb[len(vb):]           # the end, or what it raised, or nothing: killed
    k = min(len(va), len(vb))
    name = lambda j: f'{convert.READS[j // n]} {j % n}'
    out += ['read ' + name(j) for j in range(k) if va[j] != vb[j]]
    ended = bool(ea) and bool(eb) and ea[0][0] == eb[0][0] == 'end'
    if ended:
        if ea[0][1:3] != eb[0][1:3]:
            out.append('counts')
    elif len(va) != len(vb) or [e[:2] for e in ea] != [e[:2] for e in eb]:
        out.append(f'reads stopped {len(va)} {[e[:2] for e in ea]} | {len(vb)} {[e[:2] for e in eb]}')
    if seen is not None:
        seen.update(reads=k, reread=ea[0][3] if ended else [],
                    slow=None if ended else (name(k) if k < len(convert.READS) * n else 'after the reads') + f' {[e[:2] for e in ea]}')
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
        seen = dict(reads=0, reread=[], slow=None)
        d = diff(a, b, read_terms, seen)
        again = seen['reread']
        COUNTS['reads'] += seen['reads']
        if seen['slow']:
            COUNTS['slow'] += 1
            if len(SLOW) < MAX_REREAD:
                SLOW.append([seen['slow'], repr(proposition)[:300], repr(assumptions)[:200]])
        COUNTS['inputs'] += 1
        COUNTS['outcome:' + (a.reason if isinstance(a, convert.Kept) else type(a).__name__)] += 1
        if isinstance(a, convert.Converted):
            COUNTS['terms'] += len(a.objects)
        if d:
            COUNTS['differences'] += 1
            if len(EXAMPLES) < MAX_EXAMPLES:
                EXAMPLES.append([d[:6], repr(proposition)[:200], repr(assumptions)[:200]])
        if again:
            COUNTS['reread'] += 1
            if len(REREAD) < MAX_REREAD:
                REREAD.append([again[:6], repr(proposition)[:200], repr(assumptions)[:200]])
        if d or again or seen['slow'] or COUNTS['inputs'] % WRITE_EVERY == 0:
            write()
        return real(proposition, assumptions, eng)

    def write():
        os.makedirs(out, exist_ok=True)
        p = os.path.join(out, f'diff.{os.getpid()}.json')
        with open(p + '.tmp', 'w') as f:
            json.dump(dict(counts=COUNTS, examples=EXAMPLES, reread=REREAD, slow=SLOW, items=list(rust.ITEMS),
                           walk=getattr(convert.WALK[0], 'ITEMS', 'py'), read_terms=read_terms), f)
        os.replace(p + '.tmp', p)

    os.register_at_fork(after_in_child=lambda: (COUNTS.clear(), EXAMPLES.clear(), REREAD.clear(), SLOW.clear()))   # a forked child counts its own
    both.differential = True
    convert.convert = both
    atexit.register(write)


def total(dirs):
    c, ex, re, slow, files = collections.Counter(), [], [], [], 0
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(d, 'diff.*.json'))):
            r = json.load(open(p))
            c.update(r['counts'])
            ex += r['examples']
            re += [[os.path.basename(d)] + e for e in r.get('reread', [])]
            slow += [[os.path.basename(d)] + e for e in r.get('slow', [])]
            files += 1
    return files, c, ex, re, slow


if __name__ == '__main__':
    files, c, ex, re, slow = total(sys.argv[1:])
    print(json.dumps(dict(files=files, inputs=c['inputs'], differences=c['differences'], terms=c['terms'], reads=c['reads'], slow=c['slow'], reread=c['reread'],
                          reread_by_dir=dict(collections.Counter(e[0] for e in re)),
                          outcomes={k[8:]: v for k, v in sorted(c.items()) if k.startswith('outcome:')})))
    for e in ex[:10]:
        print('DIFF', e)
    for e in slow:
        print('SLOW', e)
    for e in re:
        print('REREAD', e)
    raise SystemExit(1 if c['differences'] or not c['inputs'] else 0)
