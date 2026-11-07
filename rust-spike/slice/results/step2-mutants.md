# S step 2: mutant scores and known differences (issue 323)

Run on orion: `mutate_slice.py WORK --sessions 1500 --step1 300 --seed 1 --jobs 4 --timeout 600 --triage 120 --shrink 60`, 01:42 to 01:45 UTC, 7 Nov. Sweep code at faad621; the crate last changed at 1b84ef9.

**Columns.** digest: answers only, step 1's corpus (325 sessions, 24,288 calls). state: state compare, same corpus. fuzz answers: answers only, fuzz sessions (1506 sessions, 178,613 calls on the unmutated build). fuzz state: state compare, fuzz sessions. A cell names the first difference, the session, and the calls left after shrinking. Hand-written sessions run first, so "fixed N" doesn't show that random sessions would miss it; the second table tests that for the 5 missed.

**The "digest" column is API answers, not the plan's engine digests.** Those need the theory callbacks of step 3, so that column of the plan can't be scored yet.

| # | mutant | missed by replays | digest | state | fuzz answers | fuzz state |
|---|---|---|---|---|---|---|
| base | unmutated |  | no | no | no | no |
| 0 | level sort: ascending then reversed (ties flip) |  | no | no | caught: result, session 240, 13 calls | caught: state learnts, session 22, 60 calls |
| 1 | explain: last best wins, not first |  | no | caught: state heap, session 226, 5 calls | caught: result, session 124, 47 calls | caught: state level, session 124, 20 calls |
| 2 | _mention: pending blocks in reverse order | yes | no | no | no | caught: state heap, session 385, 7 calls |
| 3 | _learn: no var_inc decay |  | no | caught: state var_inc, session 6, 7 calls | caught: result, session fixed 0, 29 calls | caught: state trail, session fixed 0, 744 calls (not fully shrunk) |
| 4 | watch: blocker-style keep |  | no | caught: state reason, session 8, 82 calls | caught: result, session fixed 0, 119 calls | caught: state level, session fixed 0, 554 calls (not fully shrunk) |
| 5 | ring: None counts as false in a clause | yes | no | no | caught: result, session fixed 5, 11 calls | caught: theory calls, session fixed 5, 10 calls |
| 6 | _fill: no growth past the model's end | yes | no | no | caught: result, session 535, 6 calls | caught: state ring, session 170, 7 calls |
| 7 | _learn: bump after joining learnts | yes | no | no | no | caught: state reason, session 15, 24 calls |
| 8 | _pick_branch: decisions not counted on -1 |  | no | caught: state counters, session 0, 1 calls | caught: result, session fixed 0, 2 calls | caught: state counters, session fixed 0, 1 calls |
| 9 | theory unit reason stored as learnt | yes | no | no | no | caught: state reason, session fixed 3, 4 calls |

**Load proof.** All 11 builds have different hashes. Each check's process reports the hash of the file it loaded, and the sweep stops if that isn't the mutant's. On a fixed pigeonhole script, `_var_inc` is `0x1.6c12995717974p+10` on the unmutated build and `0x1.0000000000000p+0` on mutant 3.

**Hangs: none.** No check of any mutant hit the 600 s limit, and none crashed, so no cell is a hang. sa-rust-14's 590 s overrun was the unbounded shrink, not a mutant: with the limit removed, shrinking mutant 3's catch alone was still at 767 calls when killed at 500 s. Mutants 3 and 4 still hit the 60 s limit here, hence "not fully shrunk".

## The 5 the replays missed, on random sessions alone

`--no-fixed`, state compare, 1500 sessions per seed.

| # | mutant | seed 1 | seed 1000 | What the catch depends on |
|---|---|---|---|---|
| 2 | `_mention` order | caught, session 385, 7 calls | caught, session 1365, 7 calls | |
| 5 | ring None | **no** | **no** | **Only hand-written `fixed 5` catches it**, which keeps a solver after `push_level` raised |
| 6 | `_fill` growth | caught, session 170, 7 calls | caught, session 1006, 7 calls | |
| 7 | `_learn` bump order | caught, session 15, 24 calls | caught, session 1000, 14 calls | `_cla_inc` set by hand near the rescale limit, in both |
| 9 | theory unit reason | caught, session 63, 7 calls | caught, session 1018, 4 calls | |

## Mutants not caught

Every mutant is caught by at least one check, so none is argued equivalent. Cells marked "no" are stated as not caught by that check, with no claim of equivalence:
- **digest:** not caught for any of the 10.
- **state on step 1's corpus:** caught 1, 3, 4, 8. Not caught 0, 2, 5, 6, 7, 9.
- **fuzz answers:** caught 0, 1, 3, 4, 5, 6, 8. Not caught 2, 7, 9: in these runs they change state but no answer.

## Known differences, each with its smallest script

`fuzz.py --known` runs B to E and the exemption's self-test. Exempted calls are counted and the session goes on being compared. On the unmutated build, seeds 1, 1000 and 2000 are clean apart from these. B, C and D counts per seed: 1131, 8, 6; 802, 2, 12; 639, 3, 14.

| | Difference | Python | Rust | State after | Smallest script | Handling |
|---|---|---|---|---|---|---|
| A | Solver call inside a hook | runs it | RuntimeError "Already borrowed" or "Already mutably borrowed" | not compared | theory whose `assert_lit` calls `solver.nvars()`, then `solve([1])` on a registered atom | 42 of 42 hook x method pairs. Not exempted, because the fuzzer's stubs make no such call. Step 4's to trace, per the planner |
| B | Backtrack after `pop_level` raised | IndexError at `k = self._rb_ulim[lvl]` | PanicException | same | theory `{'raise_at': {'pop': 29}, 'decide': [31], 'conflicts': [(-31,), (-31, 31)], 'finals': [(-31, 31)], 'model': True}`; `attach_theory T0; register_atom T0 31 'a31' False; entails 24 [] 0; add_clause [-13, -18]` | Exempted, exact site |
| C | `mention_blocks` base past the last variable | IndexError at `b0 = rb_base[base]` | PanicException | same | `set_rule_block(WIDE, 10); mention_blocks([(44, 3)])` | Exempted, exact site. **New: the old rule hid it** |
| D | `mention_blocks` range past the last variable | IndexError at `if not ment[v]:` | PanicException | same | `ensure_vars(12); set_rule_block(BLOCK, 4); mention_blocks([(11, 255)])` | Exempted, exact site. **New: the old rule hid it** |
| E | `add_pattern` with a one-literal clause | stores the clause, then IndexError at `out[1]` | PanicException before storing it | **differs** (`clauses`) | `add_pattern([[1], [0, 2]], 29, 2)` | Not exempted. The generator makes no unit patterns, so the fuzzer can't see it |

C, D and E break documented contracts ("variables must exist", "no unit clauses"). B needs a caller who keeps a solver after a hook raised. A PanicException is a BaseException, so it passes through `except Exception`. Within satassume, `add_pattern` and `mention_blocks` have no callers outside `solver.py`.

**The exemption.** It went from "any IndexError against any out-of-bounds panic, then end the session" to a table of three sites (`KNOWN_SITES`, `fuzz.py:268`). All of these must hold: the exact source line in Python; Rust's message with the same list length and index; and the site's own cause (`pop_level` raised on both solvers and the level lists out of step, or a variable past `nvars()`). `--known` self-tests that it refuses another line, length or index, or a hook that didn't raise on one side. Sessions also now continue after an exempted call, where they used to stop: 1506 of 1506 finish, against 1483 of 1503 before.

**Not fixed:** B to E need a change in `solver.rs`, not the wrapper, so they are listed for later steps. B, C and D are single bounds checks.

## Limits of this result

- Mutant 5 is caught only by a script written for it, in a state only a caller who keeps a solver after a hook raised can reach. Random sessions reach "ring hit on a model with None" but never tell the mutant apart.
- Mutant 7 needs `_cla_inc` set by hand. Whether a natural rescale reaches it wasn't measured.
- Mutants 2, 7 and 9 are seen only by state compare, never by an answer.
- No state compare runs inside a hook, because of difference A.
- The first table is one seed; the 5 missed were re-run on a second. `check_step1.py` on the current crate: same results, 3025 scripts, 220,653 calls, exit 0.
