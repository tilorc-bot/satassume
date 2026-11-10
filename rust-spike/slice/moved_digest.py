"""moved_digest.py: test-only. One digest of every container the port has moved to Rust so far, keys and values, sets, dicts
and lists, for `live.py`'s rows and `livecmp.py`'s comparison against Python (issue 323, the planner's ruling of 10 Nov:
"State MATCH" read only the solver, EUF, LRA and the engine's stats, and none of the moved containers).

Nothing here is called by satassume, the backend or the crate. `live.py` installs it after every backend install, on both
modes, unless SLICE_MOVED=0.

Per query, per `Relations` made in it (`session_rows`), when the query ends:
- the nine sets (step (iii)(b) rest): members, sorted (no set is iterated);
- the fifteen dicts: items in insertion order, keys and values (`_xheads` and `top` are iterated);
- the four work lists: items at the end, and under `@lists` a running hash of every non-empty list at each `_interpret`
  and `_link` call (they're drained by the end of a query; test_rl_core.py's sampling);
- the seven scalar cursors ((iii)(b) first move), under `@cur`.
On Python each is `rel.__dict__[name]`; on Rust the core's test-only exports (`rs_snapshot`, `rd_snapshot`, `rl_snapshot`,
`relc_snapshot`), or Python's own attribute where the build has no such export (an older build, SLICE_REL=py), counted in `src`.
A row holds one short hash per non-empty container, by name, so a difference names its container.

Every SLICE_MOVED_EVERY queries (default 25) and after the last (`engine_rows`), for the default engine and the process:
- 5c9b's process memos in `memos.PROCESS` (`PROC`: `_WANT`, `_SPLIT`, `_NEIGH`, `_CLOSED`, `_SYMPY_ATOMS`): keys and
  values through `items()`; a memo with no `items()` gives its length and says so in `unread`. The registry's other
  memos weren't moved (Rust's paths don't fill Python's caches), so they're left out.
  5c9a's native tables (SPEC_ROWS, ENCLOSURES) are NOT compared: Rust registers them under its own names and Python's
  registry has no such row, so only their sizes are kept (`native_only` in the totals);
- the engine memos (5c9c `_kids`, `_qcones`, `_glue_adapters`, `_xbasis`, `splits`; 5c10b `_failed`, `_verdict`,
  `_context_sessions`; 5c10c `_cones`, `_constructing`) and the fact caches' stores (5c10a), by memo_check.py's rows;
The registry's size rows (memo_check.registry_rows) are left out: they count Python caches the port's later steps no
longer fill on Rust, so they differ on a clean build (seen on twin and transfer:7:60 at ba1ca22).
Each gives [content, order, len]: `content` is the rows sorted, `order` the rows as inserted. livecmp.py compares `order`
only when both runs name the same PYTHONHASHSEED.

Not read here, and why: lra_live's per-query `_memoized` slot (state part 1) dies with its query, so it can't be read at
the end (test_lra_slot.py reads it inside the query); the session core's solver and transfer handles (state part 2 (ii))
are single objects, not containers (test_xfer_core.py); the engine's stats and last_budget_limited (5c10d) are already
in live.py's rows (`eng`).
"""
import hashlib
import os
import sys
import re

RS = ('linked', '_bounded', '_user_eq', '_xpairs', '_aux_eq', '_link_eq', '_xpart', '_xcounted', '_xcand')
RD = ('adapters', 'status', '_guards', '_link_lt', 'top', 'link_sel', 'atom_sel', 'num_sel', '_roles', '_info', '_link_of',
      '_tv', '_tsrc', '_xside', '_xheads')
RL = ('queue', '_pending_links', '_xextra', '_xpend')
RC = ('_xtcur', '_xhn', '_xhseen', '_xslot', '_xterm', '_xnsides', '_xsides_n')
#: Step 5c9b's process memos (procmemo.rs), by the last part of their registry names.
PROC = ('_WANT', '_SPLIT', '_NEIGH', '_CLOSED', '_SYMPY_ATOMS')
GROUPS = (('rs_snapshot', RS), ('rd_snapshot', RD), ('rl_snapshot', RL), ('relc_snapshot', RC))

_ADDR = re.compile(r' at 0x[0-9a-f]+')
# Default specs hold the Rust adapters (the RelKeys ruling, (3)): an adapter compares by its class's own name.
_CLS = re.compile(r'<[\w.]*\.(\w+Adapter) object>')


def show(x):
    """A text that doesn't depend on set order, addresses or the backend's adapter class: sets sorted, containers by member."""
    k = type(x)
    if k in (set, frozenset):
        return '{' + ', '.join(sorted(map(show, x))) + '}'
    if k is tuple:
        return '(' + ', '.join(map(show, x)) + ')'
    if k is list:
        return '[' + ', '.join(map(show, x)) + ']'
    if k is dict:
        return '{' + ', '.join(show(a) + ': ' + show(b) for a, b in x.items()) + '}'
    if k is object:        # a bare sentinel: its repr is an address
        return '<object>'
    return _CLS.sub(r'<\1>', _ADDR.sub('', repr(x)))


def _h(rows):
    return hashlib.blake2b(repr(rows).encode(), digest_size=6).hexdigest()


class Moved:
    """The `Relations` made since the last `session_rows`, with each one's core (the session goes with its query)."""

    def __init__(self, rust):
        from satassume.relations import Relations
        self.rust, self.made, self.mid = rust, [], {}
        self.tot = dict(relations=0, mid_samples=0, engine_points=0, filled={}, src={}, names_differ=[], unread=[], native_only={})
        init, interp, link = Relations.__init__, Relations._interpret, Relations._link
        me = self

        def tracked(self, *a, **k):
            r = init(self, *a, **k)
            me.made.append((self, getattr(getattr(a[0], 'table', None), 'core', None) if me.rust else None))
            return r

        def t_interp(self, atom):
            me.sample(self, 'interpret')
            return interp(self, atom)

        def t_link(self, e):
            me.sample(self, 'link')
            return link(self, e)
        Relations.__init__, Relations._interpret, Relations._link = tracked, t_interp, t_link

    def _read(self, rel, core, export, names):
        """{name: container} from the core's export when the build has it, else Python's own attributes."""
        snap = getattr(core, export, None)
        if snap is not None:
            got = [d for r, d in snap() if r is rel]
            if got:
                if tuple(got[0]) != names and export + ':names' not in self.tot['names_differ']:
                    self.tot['names_differ'].append(export + ':names')      # the core moved a container this file doesn't list
                self._src(export)
                return got[0]
        if all(n in rel.__dict__ for n in names):
            self._src('py:' + export[:2])
            return {n: rel.__dict__[n] for n in names}
        self._src('none:' + export[:2])
        return None

    def _src(self, k):
        self.tot['src'][k] = self.tot['src'].get(k, 0) + 1

    def sample(self, rel, at):
        """The work lists at a point where Python can read them (they're empty again when the query ends)."""
        try:
            core = getattr(rel.session.table, 'core', None) if self.rust else None
            ls = self._read(rel, core, 'rl_snapshot', RL)
        except Exception:      # the session went with its query
            ls = None
        if ls is None:
            return
        rows = [(n, [show(x) for x in ls[n]]) for n in RL if len(ls[n])]
        if rows:
            h, n = self.mid.get(id(rel), ('', 0))
            self.mid[id(rel)] = (_h((h, at, rows)), n + 1)
            self.tot['mid_samples'] += 1
            for name, _ in rows:
                self._fill('@' + name)

    def _fill(self, name):
        self.tot['filled'][name] = self.tot['filled'].get(name, 0) + 1

    def session_rows(self):
        out = []
        for rel, core in self.made:
            row = {}
            sets = self._read(rel, core, 'rs_snapshot', RS)
            dicts = self._read(rel, core, 'rd_snapshot', RD)
            lists = self._read(rel, core, 'rl_snapshot', RL)
            cur = self._read(rel, core, 'relc_snapshot', RC)
            for n in RS if sets is not None else ():
                if len(sets[n]):
                    row[n] = _h(sorted(show(x) for x in sets[n]))
            for n in RD if dicts is not None else ():
                items = dicts[n] if type(dicts[n]) is list else list(dicts[n].items())
                if items:
                    row[n] = _h([(show(k), show(v)) for k, v in items])
            for n in RL if lists is not None else ():
                if len(lists[n]):
                    row[n] = _h([show(x) for x in lists[n]])
            for n in row:
                self._fill(n)
            if id(rel) in self.mid:
                row['@lists'] = '%s:%d' % self.mid[id(rel)]
            if cur is not None:
                row['@cur'] = [cur[n] for n in RC]
            self.tot['relations'] += 1
            out.append(row)
        del self.made[:]
        self.mid.clear()
        return out

    def engine_rows(self, engine):
        import memo_check
        from satassume.state import memos
        out = {}
        for name, key, c in memos.PROCESS.items():
            k = 'process:%s:%s' % (name, key)
            if name.rsplit('.', 1)[-1] not in PROC:
                continue        # a memo the port didn't move: Rust's paths don't fill Python's cache, so its rows aren't comparable
            if getattr(c, 'native', False) and not getattr(c, 'moved', False):
                # 5c9a's native tables (SPEC_ROWS, ENCLOSURES) are under Rust's own names, with no row of that name in
                # Python's registry (memo_check.registry_rows skips them too): their sizes go in the totals, uncompared.
                self.tot['native_only'][k] = len(c)
                continue
            try:
                rows = [(show(a), show(b)) for a, b in list(c.items())]
            except Exception as e:
                if k not in self.tot['unread']:
                    self.tot['unread'].append(k + ' ' + type(e).__name__)
                out[k] = ['unread', 'unread', len(c)]
                continue
            out[k] = [_h(sorted(rows)), _h(rows), len(rows)]
        for name, rows in memo_check.engmemo_rows(engine) + memo_check.factcache_rows(engine):
            rows = [tuple(map(show, r)) for r in rows]
            out['engine:' + name] = [_h(sorted(rows)), _h(rows), len(rows)]
        for k, v in out.items():
            if v[2]:
                self._fill(k.rsplit(':', 1)[0] if k.startswith('process:') else k)
        self.tot['engine_points'] += 1
        if os.environ.get('SPLIT_PROBE'):       # split_probe.py: the four process memos by content (issue 323)
            import split_probe
            split_probe.dump(show, self.tot['engine_points'])
        return out


def every():
    return int(os.environ.get('SLICE_MOVED_EVERY', '25'))


def install(rust):
    """None under SLICE_MOVED=0."""
    if os.environ.get('SPLIT_PLANT'):       # split_probe.py's test-only plants 450, 451, 453 (issue 323)
        import split_probe
        split_probe.arm(rust)
    else:
        sys.modules.get('split_probe') and sys.modules['split_probe'].STATE.update(rust=rust)
    return None if os.environ.get('SLICE_MOVED', '1') == '0' else Moved(rust)
