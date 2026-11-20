# HANDOFF sa-port-364 (port/domain, from rust-slice 966268c): no port; the per-term level is unread

Read rust-spike/slice/results/domain-reads.md first (the counts, the readers, the shares, the ruling's (a)-(d)).

## Done
- Worktree ~/sa-rust-ids-work/sa-port-364/wt in clone ~/dev/sa-port-7, branch port/domain. No source change.
- results/tools364 (cnt364.py, gocnt364.sh, tab364.py, tab-orion.txt) and results/domain-reads.md.
- Orion .so 4d8921d9c510e99f (966268c, build_solver.sh). Count rows: ~/sa-rust-ids-work/sa-port-364/cnt4.
- Not run: gate, S1, bar, probe count (no source change; 21/32 stands from 362).

## Open (the planner's): remove the per-term level, no port of the rest
If the removal is ruled GO, it is 363's shape and touches 363's files, so start from rust-slice after 365 has landed.

## File:line map for the removal (at 966268c; 363's landing moves convert.py, walk.rs, table.rs, py.rs, term_shadow.py)
- convert.py:27 the import; :270 `T_TUPLE, 6` (the row's arity); :279 the skeleton row's `T_INT, 0, T_INT, 0` (bits, level);
  :305 `out += (T_INT, bits, T_INT, constructed_noncommutative(t))`.
- solver_rs/src/term/walk.rs:165 the field `constructed_nc`, :271 its lookup, :826 the skeleton row's tokens, :865-869 the call
  and the two tokens; the row's arity token is written near the top of `term_row` (before :835).
- solver_rs/src/term/table.rs:143 `pub level: u8`, :338 `level: int(&f[5])? as u8` (the row is read as six fields);
  algebra.rs:102, :123, :158 the three `level: 0` of derived rows.
- solver_rs/src/term/py.rs:334 the doc of `row`, :349 `r.level` (the 8-tuple becomes 7: closed and power move from 6, 7 to 5, 6).
- `row`'s callers: term_live.py:490 scaffold (row[0], row[1]: unchanged), term_history.py:78, :83 (row[4], row[:5]: unchanged),
  term_shadow.py:128 (the destructuring), :167-168 (the level check, goes), :27 (the import, goes if unused), and
  :243, :311, :316, :322, :324, :369-374, :428 (indexes 0 to 4: unchanged).
- lazy_probe.py:25, :79 holds `constructed_noncommutative` by name (a tool; check what it does with it).
- Stays: engine.py:165 `_construction_level` and entry.rs:579 (the on-demand level, already computed on its read);
  domain.py itself (the default path and the tests use it); PORT-INVENTORY.md:43 and TERMS-INTERFACE.md:54 name the level
  as a per-node fact and need a line.
- Side effects to show before removing (363's step 2): `constructed_noncommutative` on a term can raise only through a
  class's own `__mro__`/`args`/slot read; show per query that refusals, counts and raised are unchanged under both walkers.
- Plants: none sits on the level (walk.rs:118 PLANT_TERM_ROW is the is_number bit). The shadow check loses its level row;
  say which check then covers `engine._construction_level` (tests/test_noncommutative.py:632 on, by the suite).

## Traps met
- `pkill -f PATTERN` and `pgrep -f` in a command whose own text holds the pattern kill or match the shell (exit 144).
- convert.py:412 builds the WalkCtx when term_live.from_env() runs, so a wrapper on a convert.py global must be in before it.
- sys.monitoring's CALL gives a method call as the unbound descriptor plus arg0; a test on `__self__` alone never fires.
