# Handoff, sa-port-91: component 5, step 5b, C2c. Tests written, landing runs started; not landed

Head: `port/c2c` 2caa559 plus this file, on `rust-slice` 8d6cff7. **Not landed.** Handed off at the context note before a wait of over an hour, no blocker. Read `HANDOFF-sa-port-90.md` too: its "Also say", traps and map still hold, except where this file settles them. Its line numbers for `relations_core.rs` are off by one past `register`, which gained `REL_KINDS`.

## Running now, detached: don't restart it
`machine run pareto1 --shared` under lease b5885005, wrapper pid 458672 on orion, log `~/sa-rust-ids-work/sa-port-91/machine-run.log`. Started 7 Nov about 21:01 UTC, at source 2caa559. Recipe: pareto1 `~/sp19/job91.sh`, `~/sp19/land91.sh`, `~/sp19/plant91.sh`. **Don't run `job91.sh` again while this runs: it checks out `origin/port/c2c` in that tree.**

Output, all on pareto1 under `~/sp19/sa-rust-ids-work/sa-port-91/`:
| file | what |
|---|---|
| `source.txt`, `build.txt` | tested source, so hash |
| `rel-tests.txt`, `session-limits.txt`, `relations-direct.txt` | direct tests |
| `suite/` | suite, `exit.txt`, handler rows, `tree.txt` |
| `live/` | fresh dev and fuzz from `run_live.sh`; `plant-WL-PLANT.{cmp,session.json}` for all 29 plants; `seedx-WL.cmp` at seed 1 |
| `fast-done.txt` | written when everything above is finished |
| `suite-link-none/` | `link-none` on the suite, by id |
| `suite-plants.txt`, `suite-PLANT/` | each C2c plant that fired 0 on both dev and fuzz, on the suite |
| `done.txt` | end marker for the whole job |

Wait on the marker from a background shell, not by polling. Nothing has been read yet except that `source.txt` says 2caa559. **Check `suite/tree.txt` and `build.txt` first.**

## Done
**Tests, `test_relations_core.py`, 59 passed on orion, aarch64, at 2caa559** (`~/sa-rust-ids-work/sa-port-91/rel-tests-1.txt`, with the crate's source otherwise as sa-port-90 left it):
- `_queries` gained 13 cases: congruence, chains, rationals, a Float, sharing and twins.
- `_run`'s stream now records atoms registered with the transfer theory, so `sync_transfer` and `_xswitch` are compared, not just clauses.
- `_direct_c2c`, Python against Rust on forged state, with `_rel_state` comparing the maps in insertion order: `_add_role`, `_apply_role` (each kind by each atom shape, twins and terms on and off, two KeyError cases), `_tsource`, `_tvar` (each kind, MC before, between and after SD and EN), `_share_guard`, `_congruent` (16 exits), `_congruence_pairs` (9), `_engage_transfer` (3), and `_transfer_terms`, `sync_transfer`, `_xswitch` over a really engaged session, with `set_fixed` and `switch` recorded.
- **Written answers where a method answers,** because Python against Rust can't see both taking the wrong exit. `test_c2c_answers_are_the_ones_written_down` and `test_c2c_direct_reaches_what_it_says`.
- All 16 new plants fire and are seen on **both** the corpus (`test_dropped_clause_is_seen`) and the direct comparison (`test_direct_sees_its_plants`). So no moved method is left with no evidence, even if a plant fires 0 on a workload.
- `test_rust_kinds_are_pythons`, through the new `sa_solver.REL_KINDS`.

**Code against Python, by reading each moved method line by line: no difference found.** That is a reading, and the direct tests agree; no workload has compared it until the job's rows are read. `base_contains_direct` agrees with the `base` view's `base_get`. `block_direct` matches `type(e) is tuple and e[1] == i` by reading.

## Settled: set iteration in moved code (report this)
**Nothing in moved code iterates a set, and no order Rust chooses reaches it.**
- `_xcand`, `_xpart`, `_xpairs`, `_xcounted`: added to and asked `in` only.
- `_xheads.values()`, `grown`, `_xside`: dicts in insertion order. `grown` is a real Python dict in Rust.
- `specs`, `_tsrc` values, `_xheads` values, `_roles` values, `_xpend`, `lterms`, `eterms`, `twins`: lists. `atom.expr`, `args`: tuples. `_number_basis`: a tuple sorted from a set.
- **The two items sa-port-90 hadn't read:** `th.switch` on Rust, `transfer.rs:116`, returns a `Vec` in the fixed order full then polar, as `transfer.py:166` does. `ad.terms_since` is Python's own in both: `install_euf` replaces only `EUFTheory`, not `EUFAdapter`, so it's `list(islice(dict))`.
- So the go's condition for a seed run isn't met. The job ran dev and fuzz at seed 1 anyway, because `_link`'s set does differ there and it came with C2b's recipe. Report it as extra, one seed, not the seed rerun.

## Not done, in order
1. When `fast-done.txt` appears, read by summary, never whole: `suite/exit.txt`, by id against pareto1 `~/sp19/sa-rust-ids-work/sa-port-89/suite` (orion `~/sa-rust-ids-work/sa-port-89/rows`), handler rows against the base's 39 rows in 2 tests, `TermFault`, plain dev and fuzz MATCH, and each plant's fired count and `.cmp`. Any new id, changed outcome or firing other than the named ones is a finding.
2. **Hash counts,** `Basic.__hash__` and `Integer.__hash__` on dev and fuzz, as 639abd6: `~/sa-rust-ids-work/sa-port-86/tools/qt86.py` kind `count`, called as `tools/run.sh:50`, `python $Q $wl rust count`. Short: a timeout of 240 s each there. On a lease on pareto1 and with no timing claim. Compare fuzz 708,603 and 207,017, dev 43,401 and 8,137. Don't trace; if they rise, say so. Report `link:calls` beside them. `Cx::structural` going through the link is the unmeasured suspect.
3. **What's still Python in `relations.py`, with lengths,** from the source with `ast`, minus `_REL_METHODS`.
4. Report `rust-spike/slice/results/port-c2c.md`, in `port-c2b.md`'s form, with everything in the brief's "ALSO SAY". Check `py:table` and `custom:own` fell and that no digest reads them. Check `term_discard.py`'s sites against the moved methods.
5. Rebase on `origin/rust-slice`, apply the rebase rule, land without force, `agent report`, SendMessage.

## Module count
Same as sa-port-90's expectation, still to restate after step 3: none newly counts whole.

## Map at 2caa559, under `rust-spike/slice/`
`test_relations_core.py`: `_queries` :28, `_run` :88, `_direct` :165, `_rel_state`, `_direct_c2c` right after `_direct`, `_kinds` near the end. `relations_core.rs`: as sa-port-90's map, `register` at the end. `session_live.py`: as sa-port-90's map.
