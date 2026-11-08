# HANDOFF sa-port-149: adapters B+C1 landed (4dd2ed9, report f92a360); C2 waits on the planner's ruling (issue 323)

## State (8 Nov, ~07:00 UTC)
- rust-slice = port/adapters = this handoff's commit over **f92a360** (docs) over **4dd2ed9** (B+C1 landed; tested d676f36,
  bar BC2 clean). Architect told at landing. 6g(b) (sa-port-145) and 5c7 (sa-port-148) rebase on it.
- Reports done: port-adapters.md "parts B and C1" section; port-ownership.md header line + rows :97-111 and the TSV
  (`~/sa-rust-ids-work/sa-port-149/own_edit.py`, then `_inherits_from_basic` as "not port (conversion, ownership ruling)").
- Two departures from the brief, both stated in the report and to the architect: (1) **module count 12 of 32**, not 8
  (6g(a) and 6d already brought 11); (2) lra_adapter's module `terms`/`to_constraint` (and `constant_enclosure`) have no Rust
  caller (adapters.rs:178-186 go through `_memoized(interpret)`), so they stay Python; only `constant_bounds` and
  `_memoized` are "called back".
- pay-neg-twice caught by test_adapters_core on 4dd2ed9: `~/sa-rust-ids-work/sa-port-149/negcheck/` (plain 2 passed;
  plant: inner 2 failed / 296 passed). No bars running. No jobs of mine running.

## C2 (not started; question sent to the planner via the architect)
Map: HANDOFF-sa-port-138.md "Next 5" (constfield.py sites and Rust callers); measurement: HANDOFF-sa-port-140.md "C2
measurement" and `~/sa-rust-ids-work/sa-port-140/c2/NOTES.txt` (+ cf_trace.py). Ownership rows: port-ownership.md :104
(the 6 Python rows), :101 and :103 (constfield callbacks, owned 1b/D partial), :131 (partials row naming adapters).
Key facts: the 6 rows don't run per query on Rust (`Element.__repr__` harness-only, the rest 0). Per-query callbacks:
`Element._new` (dev 703 / fuzz 1,552: lra_live.py's `_rust` sites :126-179 return Python Elements from the Rust term table
through `_memoized`, lra_backend.py `check`, harness `_state`), `pi_laurent` (dev 121 / fuzz 200, lra_cert.rs:82-90),
`Constant.enclose` (R9, permanent). constfield.rs:1998 builds `Element._new(n, d)`. The constant registry
(`_CONSTANTS`, constfield.py :731) is process-global and shared with Python's Element.
Question asked: (a) class the 6 rows as output/display conversion (not port), `Constant` kept as the registry and R9
receiver; (b) `Element._new` at the boundary: port (Rust Element pyclass with Python's eq/hash/repr, or `interpret`'s memo
moved off Python) vs. classed as output conversion; (c) `pi_laurent` into Rust. Port only after the answer.

## Next
1. Read the planner's C2 ruling (the architect relays it). Port per the ruling over session-local ids, as 5c1-5c5: callbacks
   named and counted, one plant per moved item, counters (next free numbers after 110 / 154: check relations_core.rs and
   session.rs, since 6g(b)/5c7 may land first and take numbers).
2. Local check (core tests, dev/fuzz MATCH, plant caught), then the full bar: bar.sh as in HANDOFF-sa-port-133.md, env as
   HANDOFF-sa-port-140.md "State" with PLANTS = the C2 plants + controls, BASE = BC2's suite rows
   (`sa-port-140/bar-BC2/suite`), KEPT_BASE = `sa-port-140/bar-BC2`. Output under ~/sa-rust-ids-work/<NAME>/.
3. Land with `PUSH=1 bar.sh land TESTED`, report C2 in port-adapters.md, ownership rows :101, :103, :104, :131.
