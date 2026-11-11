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

The extension (sa-port-242, the planner's (A)/(B) rulings of 10 Nov), per query in `query_rows` (`rec["moved_q"]`):
- `ses`: per `Session` made in the query, state part 3's seven containers (`frontier`, `deferred` in order; `pending`,
  `pending_c`, `demand`, `literals`, `_groups` items in insertion order, keys and values), on Rust from the core's
  `sc_snapshot`, and under `@ses` its six scalars (`ses_snapshot`); on a build without the exports, the session's own
  attributes (`src`). Under `@xfer`, state part 2 (ii)'s handles: which of the query's `Relations` `Session.xfer` is, and
  whether the session has a solver; each `Relations` row has `@xfer` too (`xfer` and `_xadapter` by class, `xfer_sel`).
- `lra`: lra_live `_memoized`'s per-query slot (state part 1). On Rust every slot entry stored in the query
  (`ad_lra_export`); on Python every distinct `lra_adapter._memoized` call of the query; one short hash per
  (kind, arg, flag, result). Python's memo outlives a query and Rust's slot doesn't, so the rows are the calls, not the
  memo's content, and Rust's paths ask the adapter less often than Python's: livecmp.py requires every entry of Rust's
  slot, key and value, to be among Python's calls of that query (equal sets between two runs of one mode).
- `eng`: the memo and fact-cache rows of every `Engine` built in the query (it is held until the query ends, then let go).
At an engine point, besides the default engine, every tracked `Engine` still alive, under `engine#<n>:`.
`_SPLIT` (the (A) ruling, corrected by sa-port-239's read): its key holds a clause list's address, so the rows are
(clauses, want, now, later) by content; `[distinct rows, order, len, distinct count]`. livecmp.py compares the distinct
rows and takes the copy counts from known_moved.json. `_CACHE` (the pattern cache, not moved) is listed beside it by its
keys, for its known-difference row.
5c9a's native tables have no Python container to compare with (they were never Python's). Each row is checked in the
process against what it caches: a `SPEC_ROWS` row against its spec's own fields, an `ENCLOSURES` row against its
constant's `enclose` cache; a row that differs is listed in `native_bad`, which livecmp.py counts as a difference.

Not read here, and why: the engine's stats and last_budget_limited (5c10d) are already in live.py's rows (`eng`).
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
#: State part 3 (ses_cont.rs SQ_NAMES, SD_NAMES; session.rs SS_NAMES): the session's sequences, dicts and scalars.
SQ = ('frontier', 'deferred')
SD = ('pending', 'pending_c', 'demand', 'literals', '_groups')
SS = ('truncated', '_link_pending', '_neg_shared', 'sel', 'n_hold', 'verdict')
#: The pattern cache's row (knowledge.templates._common._CACHE; not moved): the known-difference row beside `_SPLIT`'s.
CACHE = 'process:_CACHE'
CACHE_FIELDS = ('rules', 'node', 'nobjs', 'clauses', 'used', 'child_preds', 'complete', 'wide')
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


def typed(x):
    """test_lra_slot.py's `_typed`, as text: each node's class and, at the leaves, its repr (a Rust `Element` has no `==`)."""
    if isinstance(x, dict):
        return 'dict{' + ', '.join(typed(k) + ': ' + typed(v) for k, v in x.items()) + '}'
    if isinstance(x, (tuple, list)):
        return type(x).__name__ + '(' + ', '.join(map(typed, x)) + ')'
    if type(x).__name__ == 'Integral' and hasattr(x, '__iter__'):
        return 'Integral(' + ', '.join(map(typed, x)) + ')'
    if type(x).__name__ == 'Element':
        return 'Element ' + repr(x)
    return type(x).__name__ + ' ' + show(x)


def _h(rows):
    return hashlib.blake2b(repr(rows).encode(), digest_size=6).hexdigest()


class Moved:
    """The `Relations` made since the last `session_rows`, with each one's core (the session goes with its query)."""

    def __init__(self, rust):
        from satassume.relations import Relations
        self.rust, self.made, self.mid = rust, [], {}
        self.tot = dict(relations=0, mid_samples=0, engine_points=0, filled={}, src={}, names_differ=[], unread=[], native_only={},
                        sessions=0, engines=0, lra_entries=0, native_bad=[], native_checked={})
        self.sessions, self.new_engs, self.engs, self.rels, self.lra = [], [], [], [], {}
        init = Relations.__init__
        me = self

        def tracked(self, *a, **k):
            r = init(self, *a, **k)
            me.made.append((self, getattr(getattr(a[0], 'table', None), 'core', None) if me.rust else None))
            return r
        self._more()
        Relations.__init__ = tracked
        self._observe(Relations)

    def _observe(self, Relations):
        """The mid-query samples, taken on entry to `_interpret` and `_link` without replacing either (item 4g, RULINGS 14:
        instrumentation must not change which path runs). Replacing them made Rust call them by name (`sb:fwd_named`).
        Rust's own copies call `sa_solver.rel_observe`'s observer on entry, on every path that reaches them; Python's own
        (the Python backend, and Rust's PY_REL copies for a session with no core) are watched by `sys.monitoring`'s PY_START
        on their code objects. The two never both see one call: Rust's copies run no Python code of these methods."""
        import sys
        me = self
        if self.rust:
            import sa_solver
            import session_live
            sa_solver.rel_observe(lambda rel, at: me.sample(rel, at))
            codes = {session_live.PY_REL[n].__code__: n[1:] for n in ('_interpret', '_link') if n in session_live.PY_REL}
        else:
            codes = {Relations._interpret.__code__: 'interpret', Relations._link.__code__: 'link'}
        M = sys.monitoring
        tool = next(t for t in range(M.PROFILER_ID + 1, 6) if M.get_tool(t) is None)
        M.use_tool_id(tool, 'moved_digest')

        def start(code, _offset):
            at = codes.get(code)
            if at is None:
                return M.DISABLE
            me.sample(sys._getframe(1).f_locals['self'], at)
        M.register_callback(tool, M.events.PY_START, start)
        for code in codes:
            M.set_local_events(tool, code, M.events.PY_START)
        self.observing = (tool, sorted(codes.values()))

    def _more(self):
        """The extension's hooks: every `Session` and `Engine` made, and the LRA slot's entries."""
        import weakref
        from satassume import engine as E
        me = self
        s_init, e_init = E.Session.__init__, E.Engine.__init__

        def s_tracked(self, *a, **k):
            r = s_init(self, *a, **k)
            me.sessions.append(self)
            return r

        def e_tracked(self, *a, **k):
            r = e_init(self, *a, **k)
            me.new_engs.append(self)
            try:
                me.engs.append(weakref.ref(self))
            except TypeError:
                me._src('engine:no-weakref')
            return r
        E.Session.__init__, E.Engine.__init__ = s_tracked, e_tracked
        if self.rust:
            import sa_solver
            self._lra_take = getattr(sa_solver, 'ad_lra_export', None)
            if self._lra_take is not None:
                self._lra_take(True)
            return
        self._lra_take = None
        from satassume.theories.lra import lra_adapter as L
        real = L._memoized

        def memoized(key, read, arg):
            r = real(key, read, arg)
            kind = (1 if key[0] == 'sides' else 2) if type(key) is tuple else 0
            try:
                me.lra.setdefault((kind, L.GENERIC_CONSTANTS, key), (arg, r))
            except TypeError:       # unhashable: read every time, on Rust too
                me.lra[(kind, L.GENERIC_CONSTANTS, len(me.lra), id(arg))] = (arg, r)
            return r
        L._memoized = memoized

    def _lra_rows(self):
        if self._lra_take is not None:
            got = [(k, arg, flag, r) for _, k, arg, flag, r in self._lra_take(False)]
            self._lra_take(True)
        else:
            got = [(k[0], arg, k[1], r) for k, (arg, r) in self.lra.items()]
            self.lra.clear()
        return sorted({(k, show(arg), bool(flag), typed(r)) for k, arg, flag, r in got})

    def _engine(self, engine):
        import memo_check
        out = {}
        for name, rows in memo_check.engmemo_rows(engine) + memo_check.factcache_rows(engine):
            rows = [tuple(map(show, r)) for r in rows]
            out[name] = [_h(sorted(rows)), _h(rows), len(rows)]
        return out

    def run_mark(self):
        """What the record holds as a term_live run starts (live.py `_discarded_runs`)."""
        return len(self.made), len(self.sessions), len(self.new_engs)

    def run_discard(self, mark):
        """A refused run was rolled back and is run again: its relations, sessions and engines leave the record with it."""
        a, b, c = mark
        for rel, _ in self.made[a:]:
            self.mid.pop(id(rel), None)
        n = len(self.sessions) - b
        del self.made[a:], self.sessions[b:], self.new_engs[c:]
        return n

    def query_rows(self):
        """The extension's per-query row: `ses`, `lra`, `eng` (the module docstring). Call after `session_rows`."""
        out, rels = {}, self.rels
        ses = []
        for s in self.sessions:
            row = {}
            core = getattr(getattr(s, 'table', None), 'core', None) if self.rust else None
            snap = getattr(core, 'sc_snapshot', None)
            if snap is not None:
                cont = snap()
                self._src('sc_snapshot')
                if tuple(sorted(cont)) != tuple(sorted(SQ + SD)) and 'sc_snapshot:names' not in self.tot['names_differ']:
                    self.tot['names_differ'].append('sc_snapshot:names')
            else:
                cont = {n: getattr(s, n) for n in SQ + SD}
                self._src('py:sc')
            for n in SQ:
                if len(cont[n]):
                    row[n] = _h([show(x) for x in cont[n]])
            for n in SD:
                if len(cont[n]):
                    row[n] = _h([(show(k), show(v)) for k, v in list(cont[n].items())])
            for n in row:
                self._fill('ses.' + n)
            snap = getattr(core, 'ses_snapshot', None)
            sc = snap() if snap is not None else {n: getattr(s, n, None) for n in SS}
            self._src('ses_snapshot' if snap is not None else 'py:ss')
            row['@ses'] = [show(sc.get(n)) for n in SS]
            x = getattr(s, 'xfer', None)
            row['@xfer'] = [next((i for i, r in enumerate(rels) if r is x), None if x is None else -1),
                            getattr(s, 'solver', None) is not None]
            if x is not None:
                self._fill('@xfer')
            ses.append(row)
        self.tot['sessions'] += len(ses)
        if ses:
            out['ses'] = ses
        lra = self._lra_rows()
        if lra:
            out['lra'] = sorted(hashlib.blake2b(repr(r).encode(), digest_size=4).hexdigest() for r in lra)
            self.tot['lra_entries'] += len(lra)
            self._fill('@lra')
        eng = [self._engine(e) for e in self.new_engs]
        if eng:
            out['eng'] = eng
            self.tot['engines'] += len(eng)
            for e in eng:
                for k, v in e.items():
                    if v[2]:
                        self._fill('engq:' + k)
        del self.sessions[:], self.new_engs[:], self.rels[:]
        return out

    def _native(self, k, c):
        """A 5c9a native table's rows against what they cache; the rows that differ go to `native_bad`."""
        bad = 0
        for a, b in list(c.items()):
            if k.endswith('SPEC_ROWS:pure') or '.SPEC_ROWS:' in k:
                ok = len(b) == 3 and a[0] is b[0] and a[1] is b[1] and bool(a[2]) is b[2]
            else:
                from satassume.theories.lra import constfield
                i, prec = a
                ok = i < len(constfield._CONSTANTS) and constfield._CONSTANTS[i]._cache.get(prec) == b
            bad += not ok
        self.tot['native_checked'][k] = self.tot['native_checked'].get(k, 0) + len(c)
        if bad and k not in self.tot['native_bad']:
            self.tot['native_bad'].append(k)
        if len(c):
            self._fill('native:' + k.split(':')[1])

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
            try:        # state part 2 (ii)'s handles, through the views a reader has
                xf, ad = getattr(rel, 'xfer', None), getattr(rel, '_xadapter', None)
                row['@xfer'] = [None if xf is None else show(type(xf).__name__), show(getattr(rel, 'xfer_sel', None)),
                                None if ad is None else _CLS.sub(r'<\1>', '<x.%s object>' % type(ad).__name__)]
            except Exception as e:
                row['@xfer'] = ['unread ' + type(e).__name__]
            self.rels.append(rel)
            self.tot['relations'] += 1
            out.append(row)
        del self.made[:]
        self.mid.clear()
        return out

    def engine_rows(self, engine):
        from satassume.state import memos
        out = {}
        plant = os.environ.get('SPLIT_PLANT') if self.rust else None        # split_probe.py's 450 and 453, on the digest's read
        for name, key, c in memos.PROCESS.items():
            k = 'process:%s:%s' % (name, key)
            if getattr(c, 'native', False) and not getattr(c, 'moved', False):
                # 5c9a's native tables (SPEC_ROWS, ENCLOSURES): Rust's own, with no Python container of that name, so each
                # row is checked against what it caches and the sizes go in the totals.
                self.tot['native_only'][k] = len(c)
                try:
                    self._native(k, c)
                except Exception as e:
                    if k not in self.tot['unread']:
                        self.tot['unread'].append(k + ' ' + type(e).__name__)
                continue
            if name.rsplit('.', 1)[-1] not in PROC:
                continue        # a memo the port didn't move: Rust's paths don't fill Python's cache, so its rows aren't comparable
            short = name.rsplit('.', 1)[-1]
            try:
                if short == '_SPLIT':       # the key is (id(clauses), want): by content, as split_probe.py reads it
                    rows = [(show(r[0]), 'None' if a[1] is None else show(sorted(a[1])), show(r[1]), show(r[2]))
                            for a, r in list(c.items())]
                    if plant == 'split-row-drop' and rows:       # plant 450
                        rows = [r for r in rows if r != rows[0]]
                else:
                    rows = [(show(a), show(b)) for a, b in list(c.items())]
                    if plant == 'closed-row-drop' and short == '_CLOSED' and rows:       # plant 453
                        rows.pop()
            except Exception as e:
                if k not in self.tot['unread']:
                    self.tot['unread'].append(k + ' ' + type(e).__name__)
                out[k] = ['unread', 'unread', len(c)]
                continue
            out[k] = [_h(sorted(rows)), _h(rows), len(rows)]
            if short == '_SPLIT':
                out[k] = [_h(sorted(set(rows))), _h(rows), len(rows), len(set(rows))]
        from satassume.knowledge.templates import _common
        # keys and values (the `_CACHE` fix, issue 323: both backends fill one table under Python's keys, so the patterns
        # are compared too, field by field)
        rows = [(show(a), show(tuple(getattr(p, f, '<unset>') for f in CACHE_FIELDS))) for a, p in list(_common._CACHE.items())]
        # [content, order, count, keys]: content hashes key and pattern together; the fourth is the keys alone (4i), so a
        # comparison tells a changed pattern under the same keys from a changed key set
        out[CACHE] = [_h(sorted(rows)), _h(rows), len(rows), _h(sorted(r[0] for r in rows))]
        for name, v in self._engine(engine).items():
            out['engine:' + name] = v
        n = 0
        for w in self.engs:
            e = w()
            if e is None or e is engine:
                continue
            n += 1
            for name, v in self._engine(e).items():
                out['engine#%d:%s' % (n, name)] = v
        self.engs = [w for w in self.engs if w() is not None]
        for k, v in out.items():
            if v[2]:
                self._fill(k.rsplit(':', 1)[0] if k.startswith('process:') and k != CACHE else k)
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
