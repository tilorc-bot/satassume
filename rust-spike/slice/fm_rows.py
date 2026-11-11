"""fm_rows.py: formula's conversion counters for one workload, as an exact row the bar fails on (the planner's ruling (2)
on sa-port-268's report: a plant is caught only by a check that is not its own counter).

    fm_rows.py run OUT.json WL [live.py args]   live.py WL rust --check plain with `sa_solver.formula_track(True)`,
                                                then the row into OUT.json
    fm_rows.py check DIR [ROWS.json]            every DIR/*.row.json against results/fm_rows.json: exit 1 on any
                                                difference, on a workload with no row, and on a row with no run

A row is `fm:again` (an input object converted again in a later query: intended under H2, and what a `Hand` kept across
queries, plant 608, takes away), `fm:convert`, `fm:twice`, `fm:twice:patched` and `fm:nosession`. `fm:plant_fired` is
written beside the row and is never compared: it is the plant's own counter. A plant comes in by SLICE_SESSION_PLANT, as
in bar.sh."""
import atexit
import glob
import json
import os
import runpy
import sys

ROW = ('fm:again', 'fm:convert', 'fm:twice', 'fm:twice:patched', 'fm:nosession')
HERE = os.path.dirname(os.path.abspath(__file__))
KNOWN = os.path.join(HERE, 'results', 'fm_rows.json')


def name(wl):
    return wl.replace(':', '')


def run(out, wl, rest):
    sys.path.insert(0, HERE)
    import sa_solver

    def dump():
        c = dict(sa_solver.session_counts())
        row = {k: c.get(k, 0) for k in ROW}
        json.dump(dict(wl=wl, row=row, plant_fired=c.get('fm:plant_fired', 0), plant=os.environ.get('SLICE_SESSION_PLANT')),
                  open(out, 'w'), sort_keys=True)
    atexit.register(dump)
    sa_solver.formula_track(True)
    sys.argv = [os.path.join(HERE, 'live.py'), wl, 'rust', os.path.splitext(out)[0] + '.jsonl', '--check', 'plain'] + rest
    runpy.run_path(sys.argv[0], run_name='__main__')


def check(d, known=KNOWN):
    want = json.load(open(known))
    got = {}
    for f in sorted(glob.glob(os.path.join(d, '*.row.json'))):
        j = json.load(open(f))
        got[name(j['wl'])] = j['row']
    bad = []
    for wl in sorted(set(want) | set(got)):
        if wl not in got:
            bad.append('%s: no run' % wl)
        elif wl not in want:
            bad.append('%s: no known row; got %s' % (wl, json.dumps(got[wl], sort_keys=True)))
        elif got[wl] != want[wl]:
            diff = {k: (want[wl].get(k), got[wl].get(k)) for k in ROW if want[wl].get(k) != got[wl].get(k)}
            bad.append('%s: %s' % (wl, ', '.join('%s %s, known %s' % (k, g, w) for k, (w, g) in sorted(diff.items()))))
    for b in bad:
        print('DIFFER', b)
    print('fm rows: %d workloads, %d differ' % (len(set(want) | set(got)), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif sys.argv[1] == 'check':
        sys.exit(check(*sys.argv[2:4]))
    else:
        sys.exit(__doc__)
