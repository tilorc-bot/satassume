# HANDOFF sa-port-114: 5c4 first version on port/5c4 5509fba, unchecked; re-pointing ruled; bar not run (issue 323)

Clone /home/tilo/dev/sa-port-7, branch port/5c4 (pushed), from rust-slice d14628d (5c3). 5509fba: the 5c4 code; this handoff sits on top.
No jobs running. rust-slice was still d14628d at 00:5xZ (6f, sa-port-113, may land: check `git log origin/rust-slice`).

## What's done (5509fba)
- `relations_core.rs:1550-1880` ("step 5c4"): `rel_init` :1566, `rel_enqueue` :1628, `rel_note_formula` :1639, `rel_link_later` :1681,
  `rel_wants_transfer` :1687, `rel_share` :1700, `rel_process` :1751. Python's relations.py:777-979, 1516-1598, line for line. The instance's
  containers stay Python's; other methods are called by name (patches honoured); `__init__` sets attributes in Python's order.
- Counted callbacks (`rel:cb_*`, session.rs:112-124, NAMES 78-89): `_note_sides`, `_eq_links`, `_atom_selector`, `_atom_var` (5c4's
  "called back" rows), `_constant_term` (5c5's). `_adapter` isn't called by 5c4's code (C2b's `_interpret`/`_link` call it).
  Counters `rel:init` .. `rel:share`. `relations.EqualitySharing`/`transfer_wanted`/`relations_atom`/`PRED_INDEX`/`RELATION_ATOMS`/`Uninterpreted`
  are read from the module at each call (backend.install_transfer makes the first two Rust's).
- `_common` helpers 5c4 needs: **none**. relations.py's only `_common` import is `units` (relations.py:411, in `closed_units`, a 5c5 row).
- Wiring: session_live.py:391-412 (`_rel_init`, `_rel_m`, `_rel_process`), `_REL_METHODS` :438, plants `_REL_PLANTS` :449.
- Plants (relations_core.rs:105-112): drop-init-engage (__init__), drop-enqueue, drop-note-top, drop-proc-eq-links (process),
  drop-link-later, wants-never, drop-share (_share: pairs counted, no interface atom), skip-share (`_share` and `_trichotomy` off,
  :488, for the re-pointed test only, not a bar plant).
- orion: test_relations_core.py + test_query_core.py 73 passed. A 3-query real-EUF probe: all 7 methods and 5 callbacks fire under Rust,
  answers same as SLICE_REL=py ([True, None, True]).

## Re-pointing (ruled: report 609714d, accepted; addenda/sa-port-5c4-ruling.txt end)
Pure Python, test_relations.py:161's query: dummy_specs: none off True, `_share` off True, `_trichotomy` off None, both None. Real specs
(OrderAdapter+EUFAdapter): `_trichotomy` off True, both off None. So sharing matters only on real specs with trichotomy off.
To do: in test_relations_core.py, next to `_share()` (:631) and `test_a_patch_on_a_moved_method_reaches_nothing` (:861), add a mode and test:
(1) the suite test's two assertions unchanged (dummy_specs, `on` True; `off` None), with `off` turned off by
`sa_solver.rel_plant('skip-share')` set between the asks on Rust (`MODE=py`: the suite test's monkeypatches); (2) the real-specs case,
`_trichotomy` off (skip-trichotomy on Rust) answers True, and None once sharing is off too. Show (2) failing under drop-share
on Rust and a `_share` patch on Python. Give test_equality_sharing_is_needed_and_works named needs-internals status where the
named list lives (suite_split_named.py / suite_report.py; rust_plugin.py has no list: say so) with a pointer to the replacement. The real-EUF case for
tests/test_relations.py goes on the owed list as a held-Python-PR candidate, not in the port.

## Next
1. The re-pointed test above. Then PLANTS = the 7 bar plants (not skip-share) in a direct test (each fires and moves a case), as test_query_core.py does.
2. The bar on pareto1: `scp rust-spike/slice/p1/bar.sh pareto1:sp19/bar-NAME.sh`, see its header (bar.sh:2-11). PLANTS = 7, WLS=loop,
   TESTS += test_relations_core.py test_query_core.py, BASE = 5c3's suite rows (`~/sp19/sa-rust-ids-work/sa-port-109/bar-5c3/suite`).
   Output under ~/sa-rust-ids-work/sa-port-<you>/. Count engine.py:1906 catches. Reach per method from `rel:*` counters, dev/fuzz/loop/suite.
3. Plant classification (not on the bar), from port-5c3.md's table: drop-prep-twins, drop-lo-memo, drop-lo-discover, drop-twins-var.
   port-5c3.md says test_query_core.py catches all four (`test_each_plant_fires_and_is_seen`), so a direct test catches drop-twins-var;
   check "redundant" first for it (suite fired 2,381, 0 changed).
4. results/port-5c4.md in port-5c3.md's form; land with `PUSH=1 sh rust-spike/slice/p1/bar.sh land TESTED_SHA`.
relations.py doesn't count whole after 5c4 (5c5 owns its module functions; Session at 5c6, engine.py at 5c10).
