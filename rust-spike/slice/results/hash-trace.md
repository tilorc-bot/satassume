# Hash trace: where C2b's and C2c's `__hash__` callbacks come from (issue 323)

**The rise is scaffolding. All of it comes from the eight `rel_*` functions C2b and C2c moved into Rust. They read and write `Relations`' Python dicts and sets, which are keyed by SymPy objects, and Python's `Relations.process`, `_share` and `Session` call them with SymPy objects. 5c moves `Relations.__init__`, `process`, `_share` and `Session` onto per-query ids, so every one of these sites goes away by design.** The few sites that stay after 5c are in the EUF and LRA adapters and in `scope.py`. They were there at bfac870 and haven't changed since: 46,140 `Basic` and 26,603 `Integer` on fuzz.

This is a count, not a timing. No speed was measured or claimed.

## How it was counted
- **Counter:** `rust-spike/slice/hash_trace.py` is sa-port-86's `qt86.py` (639abd6) with its `count` kind and the same install sequence. It adds one key: each Rust-to-Python callback is also keyed by the Rust callable on top of the stack and the Python line that called it. The `rust2py` totals are qt86's numbers by construction, and the per-site rows sum exactly to them (the `TOTAL site` row equals `TOTAL rust2py` in every column).
- **Runs:** pareto1, under a shared lease, by `rust-spike/slice/p1/hash_trace_job.sh`, `PYTHONHASHSEED=0`. Each tree is my own clone with a `.so` built in the job: base bfac870 (`.so` db2e4182…), C2b a62bd61 (492b80de…), C2c 5a8740b = de8bd3a plus the counter only (a348bf35…, the same sha as sa-port-91's C2c build). Each run imported `satassume` from its own tree. Rows are on pareto1 under `~/sp19/sa-rust-ids-work/sa-port-94/trace1`, with a copy on orion under `~/sa-rust-ids-work/sa-port-94/trace1`.
- **Reproduces every number in the brief exactly:** fuzz 708,603 / 207,017 → 1,563,962 / 615,456, and dev 43,401 / 8,137 → 73,784 / 22,856. Answer digests are as pinned on every run: dev 31cd0945c07f02a6, fuzz 173502b6ef285ad6. The C2c dev count was also run on orion (aarch64) and gave the same numbers.
- **Only callbacks made directly from Rust are counted, as in qt86.** A hash that Python code or a C slot makes isn't counted, and a `__hash__` that Python code calls during the walk isn't counted either.

## Per call site, by Rust callable: `Basic.__hash__` / `Integer.__hash__`

"5c" says whether 5c's plan removes the site by design. The plan is the order ruling's step 3 ("the rest of `Session` and then `Engine`: discovery, escalation, `_relevant`, `_Split`, the budget, memos under per-query ids"), together with `port-c2c.md`'s list of what `relations.py` keeps. I didn't use sa-port-93's split. Where it matters, the assumption is stated.

| Rust callable ← Python caller | dev base | dev C2b | dev C2c | fuzz base | fuzz C2b | fuzz C2c | 5c | why |
|---|--:|--:|--:|--:|--:|--:|---|---|
| `rel_interpret` ← `Relations.process` | 0 / 0 | 16,618 / 7,163 | 22,570 / 10,536 | 0 / 0 | 486,883 / 190,525 | 666,322 / 283,367 | goes | hashes atoms into `_info`, `_roles`, `_link_lt`, `_aux_eq` and `_link_eq` (`relations_core.rs:635`). These are Python dicts and sets made by `Relations.__init__`, which stays Python until 5c. C2c's rise here is probably methods it calls that are now Rust: a Rust-to-Rust call isn't a new stack entry, so their hashes land here. Not checked. |
| `rel_link` ← `Relations.process` | 0 / 0 | 5,866 / 2,994 | 9,435 / 6,394 | 0 / 0 | 139,686 / 75,164 | 226,901 / 160,168 | goes | `_link_lt`, `link_sel`, `link_of` and `_aux_eq` set by SymPy key. Also includes the 5b link's own hashes, at most `link:cross_hash`'s count. |
| `rel_sync_transfer` ← `process`, `_complete_check`, `query_literal` | 0 / 0 | 0 / 0 | 1,245 / 0 | 0 / 0 | 0 / 0 | 87,512 / 18,572 | goes | new in C2c. Same kind of state, and the callers are 5c's. |
| `rel_selectors_of` ← `Session._set_glue`, `assumption_lits`, `_group_sel` | 0 / 0 | 2,090 / 348 | 2,090 / 348 | 0 / 0 | 38,328 / 10,174 | 38,328 / 10,174 | goes | `link_sel` and `num_sel` looked up by term. Called by `Session`. |
| `rel_share_guard` ← `Relations._share` | 0 / 0 | 0 / 0 | 1,236 / 0 | 0 / 0 | 0 / 0 | 24,140 / 0 | goes | new in C2c. `_share` is on the kept list. |
| `rel_transfer_terms` ← `process` | 0 / 0 | 0 / 0 | 225 / 107 | 0 / 0 | 0 / 0 | 21,654 / 6,040 | goes | new in C2c |
| `rel_add_role` ← `_share`, `process` | 0 / 0 | 0 / 0 | 1,038 / 72 | 0 / 0 | 0 / 0 | 19,736 / 208 | goes | new in C2c. Writes `_roles`. |
| `rel_mention_number` ← `process` | 0 / 0 | 261 / 0 | 522 / 0 | 0 / 0 | 966 / 22 | 1,932 / 22 | goes | `num_sel` |
| `SessionCore.base_get` ← `_Base`/`_node` ← `Session.ensure`, `_discover`, `query_lit`, `escalate` | 12,038 / 130 | 12,038 / 130 | 11,970 / 130 | 161,191 / 149 | 161,191 / 149 | 154,549 / 149 | goes | 5a's views: Python's `Session` reads Rust state by object, which means a `nids` dict lookup (`session.rs:307`). Discovery and escalation are in 5c. |
| `SessionCore.table_var_py` ← `Relations._atom_var` | 3,301 / 2,521 | same | same | 79,149 / 64,431 | same | same | goes | `_atom_var` is on the kept list |
| `SessionCore.custom_get` ← `_Custom` ← `_share`, `process` | 4,330 / 2,758 | 1,033 / 415 | 332 / 20 | 99,690 / 70,180 | 22,635 / 9,579 | 6,572 / 68 | goes | falls as C2b and C2c move its callers |
| `SessionCore.var` ← `_var` | 4,032 / 0 | 120 / 0 | 120 / 0 | 134,774 / 0 | 3,368 / 0 | 3,368 / 0 | goes | fell in C2b. What's left comes from `term_live._run_plan`. |
| `SessionCore.base_of_get` ← `_BaseOf` ← `_compile_patterns` | 4,126 / 27 | same | same | 33,351 / 27 | same | same | goes | `Session` |
| `SessionCore.visit` ← `_node` ← `_discover`, `escalate` | 3,972 / 54 | same | same | 26,030 / 54 | same | same | goes | discovery and escalation |
| `SessionCore.compile` ← `Session.assume_formula` | 2,660 / 258 | same | same | 20,865 / 7,954 | same | same | goes | `Session` |
| `SessionCore.node_base` ← `Session._compile_patterns` | 1,762 / 0 | same | same | 13,912 / 0 | same | same | goes | `Session` |
| `SessionCore.literal` ← `Session.literal_of` | 141 / 63 | same | same | 12,247 / 482 | same | same | goes | `Session` |
| `SessionCore.dvar` ← `knowledge/compile.py _literal` | 33 / 9 | same | same | 220 / 44 | same | same | assumed goes | the knowledge caller isn't named in 5c |
| `EqualitySharing.update` ← `Relations._share` | 2,608 / 997 | same | same | 62,884 / 28,215 | same | same | goes, assumed | `_share` is on the kept list. This assumes 5c passes ids to the ported `EqualitySharing` and not objects. |
| `transfer_wanted` ← `Relations.wants_transfer` | 1,620 / 344 | same | same | 18,150 / 8,878 | same | same | goes | `wants_transfer` is on the kept list |
| `transfer_wanted` ← `scope.py:174 scope_of_atoms` | 1,648 / 352 | same | same | 22,188 / 8,709 | same | same | **stays**, assumed | `scope.py` isn't named in 5c's plan |
| `LraCore.check` ← `lra_backend.py:125 LRATheory.check` | 610 / 0 | same | same | 13,040 / 0 | same | same | **stays** | LRA glue, not in 5c |
| `EUFTheory.value`, `.term` ← `euf_adapter.py:203,213 _intern` | 520 / 624 | same | same | 10,912 / 17,894 | same | same | **stays** | EUF adapter, not in 5c |
| **total** | 43,401 / 8,137 | 61,027 / 16,299 | 73,784 / 22,856 | 708,603 / 207,017 | 1,166,005 / 422,301 | 1,563,962 / 615,456 | | |

## Reconciliation, bfac870 to C2c
- **fuzz `Basic`, +855,359:** the eight `rel_*` sites add 1,086,525. Sites whose callers moved fall: `SessionCore.var` −131,406, `custom_get` −93,118, `base_get` −6,642. 1,086,525 − 231,166 = 855,359. C2b accounts for +457,402 of it and C2c for +397,957.
- **fuzz `Integer`, +408,439:** `rel_*` +478,551, `custom_get` −70,112.
- **dev `Basic`, +30,383:** `rel_*` +38,361, `custom_get` −3,998, `var` −3,912, `base_get` −68. **dev `Integer`, +14,719:** `rel_*` +17,457, `custom_get` −2,738.
- **Every other site is identical across the three trees.**
- **The link:** its hashes land inside `rel_link` and `rel_interpret`, and this counter can't separate them. The bound from `port-c2c.md` stands: at most one per `link:cross_hash`, which is 81,134 on fuzz. `Cx::structural`'s share is part of that bound and isn't split out here.

**After 5c, by design:** at C2c, everything but the three "stays" rows goes. That's 1,517,822 of 1,563,962 `Basic` and 588,853 of 615,456 `Integer` on fuzz, and 71,006 of 73,784 and 21,880 of 22,856 on dev. It assumes three things: `EqualitySharing` gets ids, `scope.py` stays outside 5c, and the knowledge caller of `dvar` goes. Whatever converting the input to ids costs at the query entry remains: once per term per query, not once per crossing. Per the ruling, that cost gets reported when the engine port lands.

## Not done
- No timing.
- No seed other than 0.
- sa-port-93's split wasn't read. The assumptions are listed above.
- The suite wasn't run: this branch adds counting scripts only and changes no source the suite runs.
- No planted check of the counter is needed for a zero here. Every row reported as moving has nonzero counts on at least one tree, and the zeros are sites that don't exist in that tree.
