# Handoff: sa-port-34 to the next session on component 1a (issue 323)

**1a isn't landed: nothing is on `rust-slice` and no count against the 32 is claimed. Waiting on the planner for `_forms`, and on `mutbound`. No rsync or rebase yet.** I stopped at the context note.

Read first: my brief `~/.local/state/agent/briefs/sa-port-34-20261107T104305Z.txt`: terms and every ruling still apply, including state transfer and condition 4. **Carry them into any later handoff.** Then `~/dev/architect/briefs/addenda/sa-port-1a-forms-ruling.txt`. Then `HANDOFF-sa-port-26.md` and `HANDOFF-sa-port-21.md`, steps 3 to 7. My reports: bd05455 and the one carrying this file.

## Jobs

- `$O` = `~/sa-rust-ids-work/sa-port-21` on pareto1. At 11:02 UTC `checks/mutlive/done` exists and `checks/mutbound/builds` is being filled. **`$O/checks/done` is the end marker. No rsync or rebase before it.** My waiter dies with this session, so start your own, bounded. It must also notice the job dying: `pgrep -f "[p]1_checks.sh"`.
- orion, detached: `~/sa-rust-ids-work/sa-port-34/hook/fix/dev.done`, `dev.log`: the prototype on dev, recording each new form with a non-canonical object. Read `wc -l dev.log` when done. The log is shown firing (40,110 lines on the enumerator).

## Order from here

1. **Read the planner's answer on `_forms`** (below). Until then, both strict xfails stay and it's listed as a known state difference. It can't land silently.
2. **mutlive is all "no": 15 mutants and base, every cell. Not a result yet.** Builds are distinct, the loaded sha is checked, and state rows have 6,857 / 29,263 searches. But this tool hasn't been seen catching anything here. Run a positive control first: a mutant that has to change answers, through `mutate_live.py --only`, on orion or under the lease. Then report. `$O/checks/mutlive/{table.md,results.jsonl}`.
3. `mutbound/work/table.md` when `checks/done` appears, with a report.
4. Rsync, then the drop alone in its tree: `OUT=$REAL/sa-rust-ids-work/sa-port-34/drop`, `p1_drop.sh`.
5. Rebase on `origin/rust-slice` (ceb6ceb at 10:45). Only `solver_rs/src/lib.rs` conflicts in a trial merge. cc3055c..ceb6ceb has no source change, but fetch again.
6. `p1/p1_landing.sh` under `machine run pareto1 --shared --wait 4h`, detached, after rsyncing again: suite, fresh on all four workloads, forced moves, portmut, history. **Written, syntax-checked, never run.** Suite first, because the suite's numbers are the landing numbers. Then `handler_cmp.py suite`, `handler_cmp.py live`, `suite_report.py` (in `rust-spike/slice`, not in `pr328-check`).
7. The planner's question in three lines to forward-chain-3b. Native path and timing: HANDOFF-sa-port-21 step 6. Push to `rust-slice` without force once held.

## The rule, for the report and for whoever does the rest of LRA

Which object Python keeps when equal, distinct objects land (`satassume/theories/lra/lra.py`):
- **`_key`, `_var_of` keys, model keys (:1174 reads `_key`):** the first object to reach `_term_var` in the session. `_lin` calls it for every term before dropping zeros (:695), so a zero-coefficient or cancelled term counts. Within a payload, the first occurrence (`lin`'s dict key).
- **`_forms` keys (:705-716):** the objects of the first atom whose net form, after dropping zeros, is new; per term, that payload's first occurrence, whatever `_key` holds. A later atom with the same form changes nothing. Iteration is first-registration order.
- **Nothing else holds terms** in these runs: all of Python's fields walked after registration and at session end find only those three.

Run (`identity_rule.py`, `hook/rule.json`, `fix/split.txt`): every ordered 1, 2, 3 of 24 payloads, so both orders of the pair: 14,424 sequences. Each moved right after its registrations, then the same calls on both, then 4 more registrations. **344,304 answers compared, model keys by tag: 0 differ. All state but `_forms`, at every step: 0 differ.** `_forms` objects differ in 7,334. `_forms` order differs in 7,004 (measured with the prototype on, where objects match; the plain run's 9,912 "either" mixes the two). Control: `term:last_object` fires `_key`, `_var_of`, model and answer, 8,630 each, on the run before the 4 later registrations were added.
Limits: payloads have plain Fractions only: no raising `num()`, no constants, no certify path (`_cagg`, `_cert`). Moves only right after registration, level 0, so Rust's `_rows` order after a pivot isn't exercised here. Hook-level, not `ask`.

## The question out to the planner

- **Objects:** can't be `_state` alone, because the object is gone by then. So per the ruling the strict xfail stays. Prototype, not in the tree: `hook/fix/forms_fix.py`, about 20 lines in `_pairs`, `register_atom`, `_state`, no Rust. Costs one `is not` per repeated term, and `core.dump()` on the alias path. Objects differ 7,334 to 0.
- **Order, not in the ruling:** the Rust dump sorts `_forms` deliberately (`lra_py.rs:298-299`, "any defined order will do"), and `state.py:146,157` sorts too. Not hash order. Fixing it needs an insertion sequence in Rust's form map. This is why `order:_forms` isn't caught.
- **Reach:** `port`: 0 recordings. dev pending. fuzz not run.

## Settled

- Hook-level column: 13 Python mutants, loaded and reached: 9 caught; not caught `equality_lost offset_sign forget_skipped last_object`. `last_object` and `always_new` caught by `test_lra_identity.py`. Through `ask` is still 14/18.
- Forced moves were reread by sa-port-26 (d0991f6); rerun on the landing source is in `p1_landing.sh`.

## File:line map (additions)

| Topic | Where |
|---|---|
| The enumerator | `slice/identity_rule.py`; `POOL`, `state`, `calls` |
| Identity tests, 1 pass, 2 strict xfails | `slice/test_lra_identity.py` |
| Hook-level runner, reach counter, sentinel | `~/sa-rust-ids-work/sa-port-34/hook/hook_col.py`, `py.jsonl`, `identity.jsonl` |
| Prototype fix, not in the tree | `~/sa-rust-ids-work/sa-port-34/hook/fix/forms_fix.py` |
| Where the object is lost | `slice/lra_backend.py:231-247`, `_pairs`; `:277`, `_state` |
| Landing driver | `slice/p1/p1_landing.sh`; `p1_portmut.sh` takes `WLS`, `REF` |
