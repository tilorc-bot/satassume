# HANDOFF sa-lzr-2 -> sa-lzr-3 (lazy relation links, step 1 PROTOTYPE, unfinished)

Branch `lazy-proto` (from `lazy-links` 91896ec). Prototype code in the package, NOT
readable yet; `SA_LAZY=0` env falls back to the eager path (same code tree).

## What is built (prototype)
- `relations.py`: `LAZY`, `LSTATS` (counters), `Relations.unbuilt`; `process()` calls
  `_defer(e)` instead of `_link(e)`: ensures e's node (pos/neg/zero) and allocates
  `link_sel[e]` eagerly (so selectors_of/_set_glue/_group_sel are unchanged; an
  active unbuilt link = its selector true in the model). `_link` reuses that selector.
  `build(es)` = `_link` + `process()`.
- `unbuilt_disagree()`: for each active unbuilt link: (1) an existing link atom
  (user atom == link atom) must match M; (2) LRA: if all form terms real in M, e's
  value in LRA's model (an unregistered term is chosen to fit) vs M's pos/neg/zero and
  integer; on failure a SCRATCH LRATheory replays every LRA registration
  (`LRAAdapter.registered`, new) with M's polarities plus all active links'
  sign/integrality constraints: feasible -> no LRA disagreement; (3) EUF: virtual
  interning of e over EUF's model rep (`_virtual`/`_vclass`: signature table from
  `th._app`): a new term congruent to an existing or another new term -> build;
  e existing: class-of-0 == Z; (4) transfer engaged and Z: polar(e) == polar(0).
  NOT implemented: interface equalities (pairs of newly shared LRA/EUF terms). The
  exactness argument must cover them (dev answers matched without).
- `engine.py` Session: `_lazy(lits,k,a)` loop (solve; check; release(0); build;
  re-escalate if the session had escalated; sync_transfer), used by `_consistent`,
  `_entails`, `_entails_all`, `solve_lazy` (`_complete_check`). query_literal/_query_all
  call these.
- Tests: full suite was 2 failures before the EUF fix: `test_history::module_state_inventory`
  (new module state LSTATS/LAZY: expected for a prototype) and the I2 stream test
  (fixed by the virtual congruence check: `ask(Q.real(g(n)+2), Q.zero(n) & Q.integer(g(0)+2))`
  was None, now True). Suite NOT re-run after the scratch-LRA change.

## Measured (dev, orion, tools-lzr/protocount.py; counts deterministic)
Answer digest lazy == eager (`31cd0945c07f02a6`, both modes of this tree; confirm vs
9bafaa5 with `~/dev/sa-eval/evalbench/dev.py`). Links built (sim was 0 / 27% / ~0):
| | sessions | links | built (cheap check only) | built (+scratch LRA) |
|---|---:|---:|---:|---:|
| None queries | 96 | 186 | 72 | 28 |
| definite | 99 | 185 | 62 | 41 |
| set checks | 164 | 227 pending | 110 | 108 |
Reasons (+scratch, all): lra_sign 107, atom 47, lra_int 11, euf 7, polar 5.
Solves 611 total, of which re-solves 148.
OPEN: set checks still build ~half their links (lra_sign 64 with scratch_ok only 1/65,
atom 40): find why (likely the set's own glue: user relation atoms whose sides are the
linked terms, so "atom" fires; and LRA scratch infeasible for a reason to inspect,
e.g. M's integer(e) for a term the check never constrained). Fix that before timing.
Fuzz 424242 not run; pinned pareto1 timing not run.

## Next command
cd ~/dev/sa-eval/.shim && SA_LAZY=1 PYTHONHASHSEED=0 PYTHONPATH=$HOME/dev/sa-lzr:$HOME/dev/sa-eval/ext/sympy:$HOME/dev/sa-eval/.shim ~/dev/sa-eval/.venv/bin/python ~/dev/sa-lzr/tools-lzr/protocount.py dev   (or: fuzz 424242)
Then: pytest -n 8 tests; dev.py vs base-9bafaa5; pinned A/B (machine run pareto1 --quiet).
