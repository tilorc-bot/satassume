# Handoff sa-port-123 (step 6g, issue 323)

Branch port/6g. 6g(a) tested on e5c78e9 (port/6g rebased on rust-slice 2ee0c8c, 5c5's landing) (bar rows pareto1 `~/sp19/sa-rust-ids-work/sa-port-123/`, sum.txt) and landed
on rust-slice (SHAs in results/port-6g.md and the report). 6g(b) and 6g(c) not started.

## Done in 6g(a) (results/port-6g.md)
- sa-port-121's dispatch (HANDOFF-sa-port-121.md) plus, in this session:
  - `knowledge_opaque_wl.py` (`live.py opaque`, live.py:270): queries from `_applied_to_nan`/`_may_be_nan`'s cases.
    registry:opaque 220 there (0 on every other workload); dispatch-opaque-off fires and is caught there.
  - Atoms' no-query path on Rust: knowledge_live.py `rust_compiled` with `term_live.current()` None reads the node as a
    derived one (`<kind>:no-query`, was `py:no-query`). Plant `knowledge-no-query-drop`; direct test
    test_knowledge_value_units.py `test_no_query_plant_is_caught`. With no query on the stack, patterns are fresh objects
    per call (no Python `_CACHE` identity): dispatch_direct.py compares patterns by content.
  - `Dispatch.templates_for` (dispatch.rs, shares `sync_epoch` with `clauses_for`); convert.py's class rows call it
    through `convert.TEMPLATES_FOR[0]` (set and undone by `install_dispatch`), so registry.templates_for runs no Python
    per query (call trace: 0 on core/opaque/f6/value/rootof; was 21k-67k). Left per query in registry.py and
    templates/__init__.py: `_load`/`_covers`/`register` (lazy loading, import-time by ruling) and `_may_be_nan` from
    convert.py:300 (conversion, its only runtime reader now).
  - Trace script: scratch only; re-create from the description in port-6g.md if needed (sys.setprofile over
    `templates/registry.py` and `templates/__init__.py` after 50 warm queries).

## Left
1. 6g(b), the rows families, wiring.py (satassume/knowledge/templates/wiring.py, 683 lines): `power` :223 (template
   :275, ipi_split :292, `_pow_bound_templates` :335), `any_arity` :539, `_wide_of` :558, `rows_block` :565, `rules_for`
   :596, `product` :620, `addition` :650 (half/bound/recip/imag :656-:671), `piecewise_values` :349, `expand` :381,
   `_placements` :417, `_allowed` :440, `_instances` :453, `_clauses` :479, `wide_formulas` :489, `_wide` :511,
   `_declared` :176, `_attributed` :186, `matches` :196. Ownership rows port-ownership.tsv 243-306. Per-node callbacks
   today on the opaque wl (registry:python:<name>): add_rows_templates, mul_rows_templates, pow_templates,
   parts_of_round_templates, symbol_units, idx_units. Rust templates go into dispatch.rs's class entry in place of the
   called-back Python template; keep each callback named and counted until it's gone.
2. 6g(c), the shells: core.py:120 `_half_templates`, :183 `_bound_templates`, :392/:400 `ipi_split`/`pi_split`;
   functions.py:41, :100, :150, :214, :328, :360; special.py:88; nodes.py:30, :37; rootof.py:45; physics.py
   `quantity_units`; stats.py:22 (HANDOFF-sa-port-120.md "The per-node path today").
3. Each part landed at the bar with its own plants, a hidden-gap workload for any moved item at 0, and the module count.
