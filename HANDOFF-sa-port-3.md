# Handoff: sa-port-3 (issue 323)

`rust-spike/PORT-INVENTORY.md` is complete; sections 9 and 10 are final. This file is only for the two censuses it names as not completed (section 8). Neither blocks the port.

`C=~/sa-rust-ids-work/port-census`, environment as in `HANDOFF-sa-port-1.md`.

1. **Suite census:** sa-port-2's run writes `$C/suite2/` when it ends. Summarise `suite-*.json`, not the log. If it died, rerun with the command in `HANDOFF-sa-port-2.md`, item 3.
2. **Derived census over the suite,** after that, not with it, with `-n 6` and the same form: `CENSUS_OUT=DIR LIM_OUT=$C/lim/cap-all PYTHONPATH=$PWD:$HOME/sa-rust-ids-work/sympy:$HOME/sa-rust-ids-work/shim:$C $PY -m pytest -q -n 6 -p derived_plugin -p lim_plugin -p no:cacheprovider tests`. Merge with `derived_merge.py DIR OUT`, view with `derived_show.py OUT`. `lim_plugin` is a suggested addition for replaying all the suite's limit queries with `lim_replay.py`; that pairing hasn't run. Input capture misses some tests' terms (a plain `Symbol` shows as derived), so fix or discount that first.

Tools added: `lim_plugin.py`, `lim_replay.py`, `lim_cmp.py`, `lim_held.py`, `lim_reach.py`, `lim_budget2.py`, `seed328.sh`, `seed_field.py`, `seed_fieldcmp.py`, `seed_list.py`, `derived_merge.py`. Results: `$C/seed328/`, `$C/seed/field-cmp.txt`, `$C/lim/`.
