"""split_probe.py: what `_SPLIT`, `_WANT`, `_CLOSED`, `_SYMPY_ATOMS` hold, by content, for results/split-order-cause.md (issue 323).

Test-only, read-only. `SPLIT_PROBE=PATH` makes live.py's moved digest (moved_digest.engine_rows) append one JSON line per
engine point: for each of the four containers its rows in the order `memos.PROCESS` lists them. A `_SPLIT` row is
`[clauses, want, owner, n_now, n_later]`: the clause list by content (`show`), `want` sorted or None, and who else holds
the list (`pattern` with the pattern's node and clause count, `later` for an earlier result's `later`, else the referrers'
type names), so that two entries with equal clause lists can be told apart by where their lists come from. `_CACHE` (the pattern cache,
`knowledge.templates._common`, not moved) is listed beside them as `[key, id(pattern.clauses), n]`: a `_SPLIT` row's list is a
cached pattern's when its address (the row's last field) is in that column.
"""
import gc
import json
import os

NAMES = ('_WANT', '_SPLIT', '_CLOSED', '_SYMPY_ATOMS')
#: SPLIT_PLANT (test-only, split_order.py): on Rust's read, 450 `split-row-drop` leaves out every `_SPLIT` row of one
#: (clauses, want) and 453 `closed-row-drop` the last `_CLOSED` row; on Python, 451 `atoms-uncached` makes atoms.py's unit
#: templates build their pattern on every call, as Rust's do (the key is taken out of `_CACHE` before `units` reads it).
STATE = {'rust': False, 'fired': 0}


def arm(rust):
    STATE['rust'] = rust
    if os.environ.get('SPLIT_PLANT') == 'atoms-uncached' and not rust:
        from satassume.knowledge.templates import _common, atoms
        real = atoms.units

        def units(key, gen, obj):
            STATE['fired'] += 1
            _common._CACHE.pop(key, None)
            return real(key, gen, obj)
        atoms.units = units
        # Python also keeps each node's template result (registry._clauses_cache), so on twin it calls an atom template once
        # where Rust calls it in each query: emptied before each ask, so the template runs again as it does on Rust.
        from satassume import sympy_api
        from satassume.knowledge.templates import registry
        ask = sympy_api.ask

        def asked(*a, **k):
            getattr(registry, "registry", registry)._clauses_cache.clear()
            return ask(*a, **k)
        sympy_api.ask = asked


def _owner(clauses, laters):
    if id(clauses) in laters:
        return 'later'
    out = []
    for r in gc.get_referrers(clauses):
        t = type(r).__name__
        if t == 'Pattern' or hasattr(r, 'child_preds'):
            out.append('pattern@%x node=%s' % (id(r), getattr(r, 'node', '?')))
        elif t not in ('tuple', 'frame', 'list', 'dict', 'cell'):
            out.append(t)
    return ';'.join(sorted(out)) or 'none'


def rows(show):
    from satassume.state import memos
    out = {}
    for name, key, c in memos.PROCESS.items():
        short = name.rsplit('.', 1)[-1]
        if short not in NAMES:
            continue
        items = list(c.items())
        if short == '_SPLIT':
            laters = {id(r[2]) for _, r in items if r[2] is not None}
            out[short] = [[show(r[0]), None if k[1] is None else sorted(k[1]), _owner(r[0], laters), len(r[1]),
                           None if r[2] is None else len(r[2]), '%x' % k[0]] for k, r in items]
        else:
            out[short] = [[show(a), show(b)] for a, b in items]
    plant = os.environ.get('SPLIT_PLANT') if STATE['rust'] else None
    if plant == 'split-row-drop' and out['_SPLIT']:
        gone = out['_SPLIT'][0][:2]
        out['_SPLIT'] = [r for r in out['_SPLIT'] if r[:2] != gone]
        STATE['fired'] += 1
    if plant == 'closed-row-drop' and out['_CLOSED']:
        out['_CLOSED'].pop()
        STATE['fired'] += 1
    from satassume.knowledge.templates import _common
    out['_CACHE'] = [[show(k), '%x' % id(v.clauses), len(v.clauses)] for k, v in list(_common._CACHE.items())]
    return out


def dump(show, at):
    path = os.environ.get('SPLIT_PROBE')
    if path:
        with open(path, 'a') as f:
            r = rows(show)
            f.write(json.dumps({'at': at, 'rows': r, 'plant_fired': STATE['fired']}) + '\n')
