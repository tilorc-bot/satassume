# Handoff: sa-port-56, `knowledge/realroots.py` port (issue 323)

**State:** ported whole and tested at 5cd0319 on `port/realroots`, not on `rust-slice`. Results: `rust-spike/slice/results/port-realroots.md`. All that's left is to land after 1b: rebase, rerun if the incoming diff needs it, update the report, push.

**Why it stopped:** the brief says 1b lands first. sa-port-51 handed off with 1b's landing job running (journal 0279697, `~/dev/architect/briefs/NEXT-port-1b.txt`). Landing ahead would change `knowledge_live.py` and the crate under that job. The planner's rule says 1b's successor does its landing runs on top of what they overlap with, so this could restart them.

## Map

| What | Where |
|---|---|
| Rust module, one fn per Python function, same order | `rust-spike/slice/solver_rs/src/realroots.rs` |
| `root_facts` | `realroots.rs:185` |
| Input reader, what's refused | `realroots.rs:223` |
| Python bindings | `realroots.rs:246` on |
| Registered | `solver_rs/src/lib.rs`: `mod realroots`, `realroots::register` |
| Public names, the caller by name | `knowledge_live.py:48`, `:50` |
| Private Python copy, why | `knowledge_live.py:142` |
| Bind to module and `rootof` | `knowledge_live.py:152` |
| Limits check, wrapper, swap, undo | `knowledge_live.py:284`, `:289`, `:312`, `:365` |
| Real caller | `satassume/knowledge/templates/rootof.py:17`, `:28`, `:47` |
| Direct comparison | `rust-spike/slice/realroots_cmp.py` |
| Fresh workload | `rust-spike/slice/knowledge_rootof_wl.py`, `knowledge_fresh.py` (`rootof`) |
| Plants, `rootof` column | `mutate_knowledge.py:61-65`, `:155`, `:173` |
| Unit tests | `rust-spike/slice/test_knowledge_realroots.py` |

## On pareto1

- `~/sp56/env56.sh`, `~/sp56/land56.sh SHA TAG`, `~/sp56/read56.py LAND BASE_ROWS`. The clone is `~/sp56/dev/sa-port-56`; the SHA must be pushed first, since it fetches from origin.
- One landing run took 16 minutes, with the suite at about 3.
- Output: `~/sa-rust-ids-work/sa-port-56/land1/`. Set `B` in `env56.sh` to your own name.
- `suite_report.py` needs `. ~/sp56/env56.sh` and `PYTHONPATH=$PYTHONPATH:$S`. pareto1 has no `rg`.

## Traps I hit

- **`pkill -f` matches its own shell** if the pattern's text appears anywhere in the same command, even with a bracket in the pattern, when the literal path is further down. It killed my shell twice (exit 144). Stop jobs in a command of their own.
- **`git push` with no refspec is unsafe here:** this branch's upstream is `origin/rust-slice`. Always name the refspec.
- **Under `install()`, the module's original functions aren't pure Python,** since their globals are swapped. Use `R.root_facts.__wrapped__`, the private copy.
- `knowledge_quiet.py`'s output prints `fault: 719` on dev. It's identical on the base, and ordinary dev runs have none.
