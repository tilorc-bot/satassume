"""fm_again_split.py OUT.json WL [live.py args]: `fm:again` split by ask (the part 3 follow-up, item 3).

live.py WL rust --check plain, as `fm_rows.py run`, twice over in one process's counters: `formula_track(True)` once at
the start gives every reconversion (`total`, fm_rows.py's `fm:again`); `formula_track(True)` again at each top-level
`sympy_api.ask` also gives the reconversions within that ask. The second is a separate run (OUT's `mode`), since one
TRACK can't hold both: `mode=total` tracks from the start, `mode=ask` resets at each ask. Within an ask must be 0 (one
Hand per ask); across queries (total - within) is information (H2)."""
import atexit
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main(out, wl, mode, rest):
    sys.path.insert(0, HERE)
    import sa_solver
    import p_install
    depth, per = [0], []
    install = p_install.install

    def install_then_wrap(*a, **k):
        # satassume's formula module may only be imported after p_install's install, as live.py does next
        r = install(*a, **k)
        from satassume import sympy_api
        wrap(sympy_api)
        return r
    p_install.install = install_then_wrap

    live = [0, 0]

    def wrap(sympy_api):
        ask = sympy_api.ask

        def wrapped(*a, **k):
            if depth[0] == 0 and mode == 'ask':
                sa_solver.formula_track(True)
            before = dict(sa_solver.session_counts()).get('fm:again', 0)
            depth[0] += 1
            try:
                return ask(*a, **k)
            finally:
                depth[0] -= 1
                if depth[0] == 0:
                    c = dict(sa_solver.session_counts())
                    per.append(c.get('fm:again', 0) - before)
                    # sessions alive at a top-level ask's end (gauge 701; no gc.collect, so a cycle not yet collected counts)
                    live[0] = max(live[0], c.get('sc:ses_live', 0))
                    live[1] += c.get('sc:ses_live', 0) > 0
        sympy_api.ask = wrapped

    def dump():
        c = dict(sa_solver.session_counts())
        json.dump(dict(wl=wl, mode=mode, again=c.get('fm:again', 0), convert=c.get('fm:convert', 0), asks=len(per),
                       asks_with_again=sum(1 for x in per if x), first=[i for i, x in enumerate(per) if x][:10],
                       sc={k: v for k, v in c.items() if k.startswith('sc:')}, ses_live_max_at_ask_end=live[0],
                       asks_ending_with_live_session=live[1]),
                  open(out, 'w'), sort_keys=True)
    atexit.register(dump)
    sa_solver.formula_track(True)
    sys.argv = [os.path.join(HERE, 'live.py'), wl, 'rust', os.path.splitext(out)[0] + '.jsonl', '--check', 'plain'] + rest
    runpy.run_path(sys.argv[0], run_name='__main__')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
