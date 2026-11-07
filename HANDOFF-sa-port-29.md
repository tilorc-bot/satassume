# Handoff: sa-port-29 to the next session (issue 323), lazy reads

Read the brief first: `~/.local/state/agent/briefs/sa-port-29-20261107T101506Z.txt`. Its terms, rulings and "held to" list all still apply. Clone `~/dev/sa-port-5`, branch `port/lazy`, from origin/rust-slice cc3055c. Also binding: the suite-reporting ruling, `~/dev/architect/briefs/addenda/sa-port-suite-reporting-ruling.txt`.

**State: the survey is done and reported (report e780e4f). No conversion or Rust code has changed. Nothing below is built or tested unless it says so; the design is a plan.** The only code on the branch is `rust-spike/slice/lazy_probe.py`. Modules of the 32: 0.

## What's left, in order

1. Build the design below. `sh rust-spike/slice/build_solver.sh`.
2. Measure "a key holds a term `.args` doesn't reach" (design, point 3).
3. The count test and its plant (the ruling's item 2).
4. Everything in the brief's HELD TO, then section 9, `TERMS-INTERFACE.md`, rebase, push to `rust-slice` without force, and report.

None of the HELD TO runs has started: no dev or fuzz match, no history, no handler firing, no suite, no ruling 6 rerun.

## Survey result (table is in report e780e4f)

Output: `~/sa-rust-ids-work/sa-port-29/probe/d10.tsv`, `d10-extra.tsv`. 19 reads on 60 terms, one fork per pair. Both runs finished. `d10.invalid-str-in-window.tsv` is invalid: my `str(v)` was inside the counted window.

**Goes lazy:** `complex(t)` `convert.py:291`; `default_sort_key` `:252`; `is_finite` `:289`; `decompose_power` `:308` (new: `Pow(y**(1+r),3/2)` 4.35 s, 19 root refinements); `is_commutative` `:277` (new, on a user class only).

**Stays in conversion:** `is_number`, `_may_be_nan`, the three `has`, `atoms`, `free_symbols`, `constructed_noncommutative`, `args`, `hash`, `_hashable_content`, `as_base_exp`, `_is_scalar`, `relation_parts`. Zero evaluations on all 60 terms.

Limits of that survey, some of which e780e4f doesn't state, so **put them in the final report**:

- **`is_commutative` rests on one planted class.** `Costly(Expr)` with its own `_eval_evalf` gave 2 calls; script copied to `probe/commutative_fallthrough.py`. No stock class has been shown to evaluate through it. e780e4f says "RootSum gave 0", but that test is weak: my `RootSum` had `is_number` False, and `_eval_is_extended_positive_negative` only evaluates when `is_number` holds. The "59 fall through, 4 with own `_eval_evalf`" list also overstates: `Pow` is on it, yet `Pow.__new__` fills the slot on the instance. `Lambda` and `IdentityFunction` are the other two. Only 40 shuffle orders were planned for this and that loop never ran, so one order was run per term.
- **Counts include cheap evaluations.** `f(r)` shows 3 `complex()` in 0.0008 s. I read those as the polynomial's integer coefficients and didn't trace them. They count toward "zero `complex()` calls", so the test must see zero with these included.
- `Max(y,r)` and `Lt(r,y)` didn't build (this root isn't real), so they're absent. d=30 not run; d=10 only. Times are from a loaded orion.
- A class overriding a structural read could evaluate. Not ruled out; just not seen.
- **Printing evaluates.** `str(y+r)` goes through `as_ordered_terms` and `complex()`. Any log or error text printing an input term breaks the count test. `term_shadow.py` calls `str()` on terms in its refusal and `bad` paths, so count `complex()` with the shadow's checks off.

## Design (plan, unbuilt)

1. **One callback, carried in the tables.** `tables['reads'] = callable(kind, i) -> (tokens, strings)`, so `sa_solver.TermTable(c.tables)` keeps its signature and sa-port-27's calls don't change. Kinds: key, finite, complex, power, commutative. The callable keeps the `_Walk` alive for the query and counts by kind in `c.counts`. It catches `Exception` and returns None, as `:253` and `:292` do today. `is_finite` and `decompose_power` aren't guarded today, so this is a change: name it.
2. **Rust memo.** Replace `TermRow.key/closed/power` (`table.rs:107-113`) with a per-table `Mutex<HashMap<(kind, TermId), V>>`, so it dies with the table. Release the lock before calling Python. pyo3 0.30 pyclasses need `Sync`, which is why not `RefCell`; `OnceLock` plus Python risks a GIL deadlock. A trait object in `table.rs` keeps pyo3 out of the table, implemented in `py.rs`.
3. **A lazy key can't add a term.** Rust's derived ids follow `n_input` (`table.rs:123`), so there's no id to give it. In read mode `enc` must use `ids.get`, not `self.term` (`convert.py:134`, `:162`); a miss refuses through "Refused during a run". By my read of `Expr.sort_key`, a key's terms are reached by `.args`, and a `Float` is its own arg, but **that isn't measured. Count eager key growth on dev, fuzz and corpus first; the loop at `convert()` says "grows if a key..."**. Report the count either way.
4. **Strings.** Lazy keys hold new text (`str(self)` in `Atom.sort_key`), and `V::Str` indexes a table that's read as `&self`. Add `V::Text(Arc<str>)`: parse the callback's tokens against its local strings, then map. Add arms at `table.rs:401` (Str/Text in all pairings) and `py.rs:34`.
5. **BaseException.** `Refuse` is `&'static str`. Store the `PyErr` in a thread-local, return a named `Refuse`, and have `refuse()` (`py.rs:14`) raise it only for that reason. `refuse`'s signature doesn't change, so sibling code doesn't either.
6. **Which terms get a read.**
   - Key: check `bits & READ` in Rust first, since a skeleton refuses as it does today (`algebra.rs:530`, same text, "key: not supplied").
   - Power: the `powers` table becomes a list of ids that have a read, chosen by `power_rows`' existing test (`convert.py:304-305`, none of it evaluates). `_count` (`:416`) and `n_powers` change with it. Exponent stays `T_INT` only (`table.rs` "power exponent"); make that a refusal at read.
   - Closed: `F_NUMBER` plus Expr, checked in the read; non-Expr returns None, which refuses as today (`algebra.rs:645`).
   - Commutative: read at `algebra.rs:67` and `:637`, input terms only. Derived terms keep the bit (`:80`, `:125`).
7. **`table.row(i)`:** keep the 8-tuple and make it show what's been read so far, forcing nothing. Add explicit `table.sort_key(i)` (exists, `py.rs:176`), `closed(i)`, `power(i)`, `commutative(i)`. Note the change in `TERMS-INTERFACE.md`.

**Shadow changes this forces:**

- `check_table` (`term_shadow.py:105-150`) unpacks key, closed and power from `row`, and needs the explicit reads. It reads everything, so it's the test of the values and not of laziness.
- `check_order` `:186` tests `row(i)[2] is None` and would count every unread key as `key-compare-no-key`.
- `:634` uses `counts['pow_base_not_input']`: ruling 3's "queries holding such a Pow" can't come from conversion now. Compute it in the shadow as its own check.
- `F_COMMUTATIVE` is part of `want` at `:131`; take it out for the explicit read.
- Laziness numbers come from `term_counts.py`, with checks off. `term_history.py:72` hashes `row(i)[:5]`, which now holds read-so-far: check that against a read-everything run.

**Other bodies:** `Kept('too-deep')` can shift, since a `RecursionError` in a read becomes a refusal, not a Kept. Report it. sa-port-27's `knowledge.rs` didn't match `COMMUTATIVE` or `.bits` by rg on `~/dev/sa-port-24`; it reads `.key`/`.closed`/`.power` only in `py.rs`, and has `complex-unbounded` at `convert.py:43,310,423` on its branch, which it drops when it rebases. Don't commit to its branch.

## Handlers (brief's item)

The shadow catches `TermRefuse` itself (`term_shadow.py:~660`), so **a shadow-only run can't raise through `engine.py:1906` or `sympy_api.py:1107`: a zero there covers almost nothing, and the report must say so.** To show firing: follow `quiet_fire.py` (`~/dev/sa-port-17/rust-spike/slice/`, mode `port2 PATH` takes `handler_count.py`) with a plant that makes `table.sort_key` on an unreadable term raise from inside each `try`. Copy both to this clone.

## Traps

- **`ps | rg PATTERN` then `kill`, in one command that contains the pattern, kills your own shell. It did, this session** (`[l]azy_probe` matched the text of the command itself). Kill by a PID you've looked at.
- `import sympy.core.assumptions as Z` gets a function. Use `sys.modules`.
- Env: `. ~/sa-rust-ids-work/env.sh; export PYTHONPATH=$PWD:$W/sympy:$W/shim`. `lazy_probe.py` is run the same way; output under `~/sa-rust-ids-work/sa-port-29/`.

## Map

`HANDOFF-sa-port-18.md`'s map holds. Ruling 6's old numbers and its still-owed items (largest single `complex(t)`, by-site split of conversion) are in that file; `~/sa-port-18/` on pareto1 has its `p1-*.sh`, and the brief's recipe is `~/sp19/p1_job.sh`. Scripts from sa-port-18: `~/sa-rust-ids-work/sa-port-18/` (`runs.sh`, `timing_summary.py`, `handler.sh`, `tools/`).

| Topic | Where |
|---|---|
| Key reader in Rust | `algebra.rs:524` `sort_key`, `:543` `mul_key`, `:588` `add_key`, closed `:642`, power `:652` |
| Table parse | `table.rs:204` `from_tokens`, closed `:254`, powers `:288`; `V` `:18` |
| Python face | `py.rs:14` `refuse`, `:48` `new`, `:95` `row`, `:176` `sort_key` |
| Conversion | `convert.py:237` `term_row`, `:285` `closed`, `:298` `power_rows`, `:378` `convert` |
| Shadow | `term_shadow.py:105` check, `:186` order, `:602` table, `:650` used keys |
