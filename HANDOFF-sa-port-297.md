# HANDOFF sa-port-297 (rk_key step, issue 323): gate check done, S1 r3 and the bar running detached

Branch port/rk-key, head = the commit adding this file (Rust source as at 86845aa). Worktree ~/sa-rust-ids-work/sa-port-296/wt
(in ~/dev/sa-port-7). Base origin/rust-slice 63d5632. Env: `. ~/sa-rust-ids-work/sa-port-296/env296.sh`. Scratch ~/sa-rust-ids-work/sa-port-297/.

## DONE
- Planner's 297 check (isinstance cache): rk_key's isinstance targets are Basic, Number, BooleanAtom, Tuple (relkeys.rs is_basic
  :42, is_joinable :55). All metaclass `type` (checked once per process in plain(); `type` is immutable so a metaclass can't be
  reassigned), so no ABC and no own __instancecheck__. Kept test test_rk_key_targets.py (metaclass + not ABC + reassignment
  refused; relkeys.rs names exactly these four). Extra hole closed: object_isinstance's fallback reads `x.__class__` through
  tp_getattro, so plain() also needs the generic tp_getattro (relkeys.rs:279). Plant 669 `rk-getattr-cached` (:113, session.rs:761,
  session_live.py:1104) caught by the per-instance row (Fake type: 8 reads for 4 keys added+looked up; plain class 1; tuples 1).
  - 1e7a4db first did this by an MRO lookup of `__getattribute__`, which made every TUPLE key uncached (tuple's dict holds a slot
    wrapper): fuzz rk:type_read 267,128. 86845aa reads the slot: 27,256; rk:top_read 2,860, rk:term 217,752, rk:dict:hit 584,041,
    answers_sha 173502b6ef285ad6 unchanged (orion, ~/sa-rust-ids-work/sa-port-297/cnt/fuzz{,2}.session.json). Tuple row kept.
  - Neighbour suites on 86845aa (orion): 349 passed (neigh-86845aa.log).
- (c) S1: r1 VOID (my own --shared bar started inside my quiet lease: `machine` lets the same holder in; load 4-6; gd/aborted-r1).
  r2 (on 1e7a4db, clean, load ~1) gd/aborted-r2-1e7a4db/med-r2.md: dev 146 0.751 / 63d5632(=1d22f9a slice source) 0.760 / 1e7a4db
  0.760; fuzz 6.699 / 6.401 / 6.359 (head -0.7% vs 63d5632, -5.1% vs 146). Fuzz inclusive s/run (r2): rk_key 0.281 -> 0.265,
  rd_get 0.171 -> 0.158, rd_set 0.119 -> 0.093, rs_contains 0.037 -> 0.033, relkeys module 0.400 -> 0.381; rk_key Group D 0.120 ->
  0.108 (+term_of D 0.027 -> 0.011). That was WITH the tuple regression; r3 times 86845aa.
- (d) numbers (r2, fuzz, ThreadCheckerImpl::ensure inclusive s/run): 146 0.046, 63d5632 0.109, head 0.108; thread::current self
  0.055. Owners (prof297.py `tc`): RDict::get_item 0.009, add_clause 0.004, term_in 0.004, Ses::d_get 0.004, compile_loop::flush
  0.004, RDict::set_item 0.004, MembersView/RepView __getitem__ ~0.003 each, d_contains, LraCore.propagate, solver_of, q_truthy.
  Proposed fix (write-up only, no code): (1) borrow once per entry: pass PyRef/&T down instead of re-borrowing (term_in's two
  table.try_borrow, rk_key's l.table.try_borrow, solver_of, flush): ~0.02 s, no unsafe; (2) drop `unsendable` from the hot classes
  (relkeys.rs:443/704/958, session.rs:584/676, ses_cont.rs:509/645, PyTermTable, PySolver lib.rs:246, euf_py.rs:398/443,
  lra_py.rs:39) with a GIL-token cell (`unsafe impl Send+Sync` under cfg(not(Py_GIL_DISABLED)), borrow takes Python<'_>):
  up to the whole ~0.06 s growth; needs the planner's yes (adds unsafe).

## RUNNING (detached on orion: ~/sa-rust-ids-work/sa-port-297/gd/go297c.sh, end marker gd/go-end.txt)
.so built on pareto1 for 86845aa (bench sa-cy-build; bar .so 82440e6e copied to pareto0 ~/sp19/dev/sa-port-297). Then S1 r3 on
pareto0 (one quiet lease: 7 rounds 1401d1f/1d22f9a/86845aa + pysample runs), then it launches the bar (~3.3 h)
`machine run pareto0 --shared -- bash ~/sp19/bar297.sh` (bar.sh = rust-spike/slice/p1/bar.sh as ~/sp19/bar-sa-port-297.sh; PLANTS
+= rk-top-once rk-type-once rk-getattr-cached; BASE sa-port-294/bar/suite) -> pareto0 ~/sp19/sa-rust-ids-work/sa-port-297/bar,
end marker bar-end.txt there (launcher end: orion sa-port-297/bar/bar-launch-end.txt). Then go297c post-processes S1 into
gd/med-r3.md and gd/prof-{dev,fuzz}-SHA.json (prof297.py adds `dentry` rk_key's direct C calls and `tc` thread-check owners).
Read r3 with `python3 ~/sa-rust-ids-work/sa-port-297/fn297.py fuzz 1401d1f 1d22f9a 86845aa` in gd/ (and dev).

## NEXT
1. Read gd/med-r3.md + fn297.py (dev, fuzz) -> the S1 table (three arms, same lease). Target "most of rk_key's 0.127 s" is
   likely NOT met (r2: ~0.03 s of rk_key+term_of Group D); remaining rk_key D is PyDict_GetItemWithError ~0.03 (the dict path:
   584k hits) and a PyObject_IsSubclass-symbolised ~0.02 (likely a static libpython neighbour; check against r3's dentry).
2. Read the bar (bar_sum in bar.log / sum), items per the formula rulings; plants 621/668/669 via kept tests (669 and 621 are
   kept-test catches: no workload has a fake-__class__ type / the path plant changes no answer). Known failures per SIBLINGS.
3. bar.sh land 86845aa-or-HEAD (results-only commits pass the guard), PUSH=1; probe pc294.sh -> pc297.sh against 21/32
   (pareto0 ~/sp19/sa-rust-ids-work/pc294.sh; base sa-port-294/pc); knowledge_live per workload.
4. Tell the architect: `machine` lets a holder's own --shared lease start inside its quiet lease (cost S1 r1).
