# HANDOFF sa-port-283 (A, part 3 follow-up, issue 323)

Branch `port/part3-followup` on origin, from rust-slice 50f1421 (= landed 172d690 + results). rust-slice had not moved at
handoff. Nothing landed yet: items (1) and (2) are committed and pushed, unbarred. Handed off between items (2) and (3) at
~140k context, because item 3's code, its runs and the landing bar won't fit in what's left.

## Done

- (1) 0144584, F1: `SessionCore::known` gives the join hook `self.serial`, not the address. Plant 614 `sb-join-address`.
  Kept tests in test_rs_core.py force the address reuse (asserted). 614 is a kept-test catch only: no workload sets the join
  hook (only join_log.py does).
- (2) 5232cd3, SesDict: an identity memo per dict (`seen`: a strong ref, the hash, the entry plus its generation). Plant 615
  `sc-key-id-stale`, kept test test_ses_keys.py (dict vs `Session.demand`, every result equal). Counter `sc:key_id` (label
  700, NAMES index 571). sc:key_hash fuzz 478,541 -> 48,913 (159.5 -> 16.3 per query), dev 28,951 -> 5,238. livecmp
  before vs after MATCH on fuzz and dev, answers_sha equal. Runs are in ~/sa-rust-ids-work/sa-port-283/kh-before and
  kh-after3 (rust --check raw, SESSION_REPORT).
  **Deviation for the planner:** not keyed by the query's term id. A term id is reached through `term_of` ->
  `node_quiet` (a Python dict lookup on the session's `nids`, counted `link:cross_hash`), so keying by term id would move
  each hash() from one counter to another, not remove it. The memo keeps Python-dict semantics (first key object held,
  per dict, per session, emptied by clear()) and assumes what a dict assumes: a key's hash and `==` don't change.
- Tests on 5232cd3: test_rs_core.py + test_session_boundary.py + test_ses_keys.py, 46 passed. The suite has not been run.

## Item (3), measured, not started in code

`fm_again_split.py` (committed with this handoff) runs live.py as `fm_rows.py run` does. Mode `ask` resets
`formula_track` at each top-level `sympy_api.ask` (wrapped after `p_install.install`). Mode `total` tracks from the start.
Before the fix, on 5232cd3:

| wl | asks | within an ask (must be 0) | total | across queries (information) |
|---|---|---|---|---|
| dev | 1985 | 30 (30 asks, first 190, 193, 371, 398, 572, ...) | 1134 | 1104 |
| fuzz | 3000 | 0 | 1388 | 1388 |

Repro: `fm_again_split.py OUT dev ask --only 185,186,187,188,189,190` gives 1 (190 alone gives 0: it needs earlier state).
A `sys.setprofile` trace (scratch script, not committed) puts the reconversion inside the Rust entry behind `eng.ask`
(session_live.py:1109 `_ent` -> `rf`), before it calls back into term_live.py:692 `affine_pair`. That object was converted
by an earlier top-level entry of the same ask, whose `Hand` ended with it (ENTRIES back to 0, SEEN cleared, so it's
`fm:again`, not `fm:twice`).

Proposed fix, one Hand per ask, touching formula.rs (sibling B's file: keep it minimal, tell sa-port-284, name it in the report):
- An ask-level `Hand` opened once per top-level ask. `Hand::enter()` inside an ask shares its node map; a thread-local
  `ASK: Option<Rc<..>>` holds it. Split `Hand` into a shared inner (the node map, with HELD/KEPT accounting in its Drop, so
  plant 608 `HAND_KEPT` still works across asks) and the per-entry part (ENTRIES and SEEN, as now).
- The ask boundary must NOT raise ENTRIES, or `enter_inner` (formula.rs:621) ticks `fm:nosession` for every scope/cone call
  from Python inside an ask (the bar needs fm:nosession 0).
- Where to open it: a single Rust call at the ask entry, which overlaps item (4) (sympy_api entry frames as single Rust
  calls). term_live.py:1062 `_ask` (-> :1079/:1101 `py_ask`) is today's outermost slice frame. term_live.py is not one of
  A's files, so a session_live.py install over it is the likely place.
- Check a discarded run (R5): a shared ask Hand keeps nodes over a discard inside the ask. Nodes are conversions, but read
  term_discard.py / `formula_seen_restore` before assuming that's fine.
- Done when: `fm_again_split.py` within-ask is 0 on dev and fuzz (and the bar's workloads), across is reported, fm rows
  (results/fm_rows.json: fm:twice 0, fm:nosession 0) are unchanged or explained, and there's a kept test plus a plant (616
  is free).

## Item (4): not started

session_live converted calls (fuzz 1.09M at fd0fabb, results/port-state-part3.md:241) per function with an owner, and the
sympy_api entry frames reduced to single Rust calls.

## FILE:LINE MAP (on 5232cd3)

- rust-spike/slice/solver_rs/src/formula.rs:129 ENTRIES, :139 TRACK, :545 `tick(AGAIN)` (in convert_or), :602 `Hand`,
  :614 `enter`, :621 `enter_inner` (NOSESSION), :665 `give`, :707 `Drop for Hand` (KEPT/HELD, SEEN cleared at ENTRIES 0).
- Hand callers: entry.rs:616/:621/:743/:767, context.rs:159/:243/:322/:329, relevance.rs:791/:822/:827 (`enter`);
  budget.rs:297/:306/:439/:537/:577, scope_core.rs:273/:319 (`enter_inner`).
- rust-spike/slice/session_live.py:1106 `_ent` (Engine methods over Rust entries), :1095 `_SB_PLANTS` (614, 615 added),
  :1473 SLICE_SESSION_PLANT routing.
- rust-spike/slice/term_live.py:1062 `_ask` (outermost slice frame of an ask).
- rust-spike/slice/solver_rs/src/ses_cont.rs:56 plant 615, :67 `Seen`, :112 `sd_find` (memo), :148 `sd_remember`,
  :157 `sd_find_hash`.
- rust-spike/slice/solver_rs/src/session.rs:536 `SC_KEY_ID`, :730 `A_PLANTS` (614, 615; from 614 via `sb_plant`), :1224
  `known` -> `log_join(self.serial)`.
- Tests: rust-spike/slice/test_rs_core.py (`joinkey` child, two F1 tests), test_ses_keys.py.
- Ranges: plants 614-621 + 668 (614, 615 used), counters 700-719 (700 used).

## Not done (landing)

Bar (rust-spike/slice/p1/bar.sh, PLANTS must include sb-join-address and sc-key-id-stale), suite, rebase, landing, and
the module-wide probe count on the landed SHA against 21/32 with relations.py/session_live/ses_cont stated. Files outside
A's four that A's commits touch: ses_cont.rs (item 2's subject, part 3 state), test_rs_core.py, the new test_ses_keys.py
and fm_again_split.py. QUIET FAILURES: engine.py's `except Exception` catches were not counted in these runs (--check raw
without --handlers); the bar counts them.
