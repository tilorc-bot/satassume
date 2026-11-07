# Handoff: sa-port-4 (issue 323)

Item 1 of the brief (`~/.local/state/agent/briefs/sa-port-4-20261107T062601Z.txt`) is pushed and reported, a5ef6ae, report 6e3d523: `rust-spike/slice/results/pr328-check.md`. What's left is its fuzz history result and item 2. Same scope and rules as the brief. The clone is yours alone; sa-port-3 has stopped.

`C=~/sa-rust-ids-work/port-census`, `R=$C/pr328-check`. Check `ps` before starting anything: two detached jobs may still be running, all on source 2d00bea, and they stop by themselves.

## Left, in order

1. **Fuzz history.** `$R/hist/finished.txt` appears when it ends (28 lines in `done.txt`). Then `. ~/sa-rust-ids-work/env.sh; $PY rust-spike/slice/historycmp.py $R/hist`. Replace the "Fuzz: still running" line in the results file. A fuzz row is a result only if it reads `total rows: yes`; partial rows show 0 differences that mean nothing. Report the smallest case if any differs; don't reclassify it.
2. **Suite census rerun: also timed out, so it is a floor too.** `$C/suite3.exit` is exit=124 at 7,000 s. By test id, 5,562 of 6,125 finished (`done-main.txt` is the controller's copy of the workers' lists, so don't add it in); 563 didn't, led by `test_zero_glue` 109, `test_wide_derived` 72, `test_euf_adapter` 71, `test_euf` 59. `gw0` finished 92 and wrote no JSON, under the 200-test dump, as in `suite2`, where `gw0` was also the one lost. Whether one test holds `gw0` is unknown: look before rerunning. Options: read `suite3` as a floor, or run the missing ids alone with `census_plugin2`. Don't report "not reached" until those 563 ran. `$PY $C/suite_summary.py $C/suite3 $C/census-dev.json $C/census-fuzz.json`; it also reads `suite-main.json`, which is empty. Tried only on `suite2`; read low counts as floors. Section 8 item 1 and line 25's numbers are sa-port-3's `suite2-summary.txt`, not this tool.
3. **Derived census.** Running from about 09:13 UTC (`$R/derived.sh`, limit 7,000 s); restarted to add a dump every 200 tests and `done-*.txt`, since it may time out as the census did. Check coverage by id the same way. `$C/derived-suite.exit`, then `$PY $C/derived_merge.py $C/derived-suite $C/derived-suite.json; $PY $C/derived_show.py $C/derived-suite.json 40`. Memos stay on, so counts are floors. `calls` has `capture|preorder-stopped-at-top` and `|outside-query`; report both.
4. **Sections 7, 8 and 10,** only where results change them: reach of `special`, `stats`, `rootof`, `physics`; which shapes reach a sort key (section 3's option 1). Section 8's "if the suite shows more shapes, the plan doesn't change" stands unless the results say otherwise.
5. **Optional:** rerun `test_performance_smoke_300_vars` through pytest on `$R/pre` and this tree when orion is quiet. The cause is likely load, not shown.
6. Commit, push, `agent report`, send the line it prints. Say the census ran on 2d00bea while the older `suite2` ran without PR 328.

## Traps

- **`suite2` is a floor:** 5 of 6 workers, killed at 3,000 s. Never report "not reached" from it.
- **The derived capture was fixed in `$C/derived_plugin.py`** (`.orig` is the old one): `preorder_traversal` stopped at the top of some `And`s and `Or`s, so plain `Symbol`s and more showed as derived. **The cause in SymPy wasn't found,** only worked around with an `.args` walk. On `tests/test_history.py`: 60 shapes before, 19 after. Don't read the old `derived-probe.json`.
- **Check `ans_cmp.py` output shows real answers.** My first version read the wrong field and passed vacuously. The current one reads `ans` and raises if absent.
- **Other `slice/` scripts** (`run5_harness.sh`, `run-audit.sh`, `run6_counts.sh`) still use `~/dev/sa-rust`.
- **Lines:** PR 328 moved lines in the files it changes; the census keys hold `file|function|line` at 2d00bea, while the inventory's are at c230ee0.

## File:line map

- `rust-spike/PORT-INVENTORY.md`: status `:3`, suite reach `:25`, reached sites `:86`, section 5 `:155`, section 7 `:265`, section 8 `:300`, section 10 `:369`. Approximate: rg the headings.
- `rust-spike/slice/results/pr328-check.md`: the "History runs" part.
- `$R`: `live/summary.txt`, `seed/{before,after}/`, `suite-report.md`, `suite-lists.md`, `hist/`, and the job scripts `phase1.sh`, `phase2.sh`, `phase3.sh`, `hist.sh`.
- `$C`: `census_plugin2.py`, `suite_summary.py`, `ans_cmp.py`, `derived_plugin.py`.
