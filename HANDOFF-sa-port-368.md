# HANDOFF sa-port-368: why full instrumentation moved the Rust path's answers (issue 323), diagnosis only

Done. Branch diag/instrumented (clone /home/tilo/dev/sa-port-7, worktree ~/sa-rust-ids-work/sa-port-368/wt), from
rust-slice 966268c, .so 4d8921d9c510e99f. No source change to satassume or the slice. Committed: tools367 (from
audit/reads b832e5f) with the fix to cnt367.py, results/tools368/, results/instrumented-diag.md.

## Bisection state: closed, nothing left

Class (a). Three wraps each move a digest alone: `EUFTheory.rep`, `EUFTheory.members` (dev and fuzz, AttributeError
out of `ask`), `EUFTheory.on_merge` (fuzz only, 3 answers True -> None, silent). Cause: cnt367's Field on
backend.EUFTheory in front of getset descriptors inherited from sa_solver.EUFTheory. Fixed in the instrument; all
twelve full-instrumentation cells (dev, fuzz, budget, wiring x rust-nat, py-ref, default) are at the reference.
The trail, the first moved queries with their three answers and the digests: results/instrumented-diag.md.

## file:line map

- tools367/cnt367.py:341 `install_fields`; :362 the own-dict lookup; :369-378 the fix (lookup on the bases, "inherited
  TYPE" skipped); :379 own-dict objects with `__get__` skipped; :172 `Field.__get__` (:181 dict read, :184 the
  AttributeError); :212 `Field.__set__` (:216 dict write).
- backend.py:84 `class EUFTheory(sa_solver.EUFTheory)`; :88-94 `install_euf` replaces euf.EUFTheory.
- euf_py.rs:154/:159 on_merge getter/setter, :172 rep, :178 members, :108 the listener read.
- transfer_py.rs:60, :62 (`initial_multi` reads rep, members; also :41, :47); :133 `_attach` sets on_merge.
- session_live.py:598 `sa_solver.rel_init`, :887 `sa_solver.ses_init` (the Python frames above the failing read).
- tools368: bis368.py (cnt367 with knobs), cell368.sh (one cell), diff368.py (moved queries), probe_tb368.py
  (traceback), probe_catch368.py (quiet catches, with a planted raise), filelist.txt (the 208 files of "full").
- Run output: orion ~/sa-rust-ids-work/sa-port-368/ s0..s7 (s7/end.txt is the last job's end marker, s7/job.sh last line).

## Not done

- Budget and wiring were not bisected (they were at the reference before and after).
- sa-port-367's tables were not regenerated: its rust-nat cells did not instrument euf.py or transfer.py.
