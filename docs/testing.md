# Testing and gates

How to check a change to satassume: the unit tests, the answer gates that
compare a candidate with a baseline, the fuzzers, and the asv benchmarks.
How to run the suite and record the corpus is in the
[README](../README.md#running); refine testing is documented on the
`refine-identities` branch.

Which checks a change needs:

| Change | Run |
|---|---|
| any change | the suite; `tools/gate2.py`; the stream answers (`tools/stream_answers.py` on base and candidate) |
| rules, templates, `sympy_api.py` | the above, plus `tools/compare.py --in-scope-only` and `--relations-only` |
| `solver.py` (anything kept between public calls) | the above, plus a long run of `tests/test_solver_incremental.py` in each mode |
| theories, relations, transfer | the above, plus the theory fuzzers at more seeds (`TRANSFER_FUZZ_SEEDS`, `EUF_FUZZ_EXAMPLES`, `REAL_THEORY_SEEDS`, `VERIFY_SLOW=1`) |
| relevance (`Engine(relevance=...)`) | `tools/relevance_fuzz.py` over a few thousand seeds |
| a claim about speed | `tools/ab.py` or `bench-container`, interleaved rounds; see below |

## The test suite

`tests/` holds unit tests per module (`test_solver.py`, `test_lra.py`,
`test_euf.py`, `test_constfield.py`, `test_templates.py`, ...), end-to-end
tests through `sympy_api.ask` (`test_sympy_api.py`, `test_relations.py`,
`test_noncommutative.py`, ...), and fuzzers written as tests (below).
`tests/test_layering.py` checks the package structure: the layers, where
SymPy may be imported, and that no in-repo code uses the transitional
old module names (docs/design.md, "Package layers").
Tests that need SymPy call `pytest.importorskip("sympy")`.
`tests/theory_harness.py` (`Recorder`, `check_protocol`, `ForbidTheory`)
and `tests/real_theory_fuzz.py` are helpers, not test files.

`tests/test_known_gaps.py` pins the README's "Known gaps" as strict
xfails; closing one fails with XPASS: move the case and update the README.

Environment variables that size the fuzz tests (`slow` tests are skipped
unless one enables them):

| Variable | Default | Test |
|---|---|---|
| `SOLVER_FUZZ_SEEDS`, `SOLVER_FUZZ_SEED0` | 500, 0 | `test_solver_incremental.py` |
| `REAL_THEORY_SEEDS` | 150 per mode | `test_solver_real_theories.py` |
| `TRANSFER_FUZZ_SEEDS`, `TRANSFER_FUZZ_SEED0` | 80, 0 | `test_transfer_fuzz.py` |
| `EUF_FUZZ_EXAMPLES` | 150 | `test_euf_fuzz.py` |
| `VERIFY_FUZZ_EXAMPLES`, `VERIFY_SLOW=1` | 60; slow test off | `test_verify_soundness.py` (the slow test draws 2000 examples) |

`SATASSUME_LRA_*` variables select other implementations for the theory
tests; leave them unset. The full suite (about 3,000 tests) takes about 5
minutes, less under pytest-xdist (`-n 4`, same results). Use
`PYTHONHASHSEED=0` when comparing checkouts; CI does not.

Known failures:

* `test_shared_facts.py::test_cached_sympy_fact_does_not_make_assumptions_inconsistent`
  (both parameters) fails with SymPy 1.15.0.dev at `ddbb536d7e`; it passes
  with released 1.14.0 (as in CI) and with the pin `6379c4da69`.
* `test_verify_soundness.py::test_fuzz_old_style_symbols` is flaky: when
  Hypothesis draws `ask(Q.positive(x), ~Q.positive(i) & (x >= i + x))`
  (`i` imaginary), satassume answers False and the test fails, on `main`
  too. A red run on this example is not caused by the change.

## CI

`.github/workflows/test.yml` runs on every push and pull request: Python
3.11 and 3.12, `pip install pytest hypothesis sympy mpmath z3-solver`
(released SymPy), then `python -m pytest -q tests`. z3 is a second oracle
in `test_constfield.py` and `test_lra_constant_coefficients.py` (skipped
without it). CI runs none of the answer gates: their data is not in the
repository.

## Test data outside the repository

The gates read two files that are not committed (issue #62). The
durable copies are in `/home/tilo/provable/data/`:

| File | sha256 prefix | What |
|---|---|---|
| `gate2-frozen.jsonl` | `d53ed3db2f3a` | frozen answers of `tools/gate2.py`, 2,863 records |
| `stream.pkl` | `94db857d9d5d` | the refine stream: 16,232 `(prop, assumptions, answer)` triples |

The tools default to `~/.cache/satassume/` for both; point them at the
copies with `SATASSUME_GATE2` and `SATASSUME_STREAM` (or `--frozen`,
`--stream`). SymPy is `$SATASSUME_SYMPY` or `/home/tilo/sympy`; the pin
the gates use is `/home/tilo/orion/sympy` (`6379c4da69`). The corpus
`queries.jsonl` is gitignored and recorded as the README describes.

## The answer gates

Every gate compares answers four-valued: True, False, None, and
`ValueError` (inconsistent assumptions). "More definite" is None becoming
True or False; "less definite" is the reverse. More definite answers are
listed and checked by hand; a contradiction (True against False), a lost
answer or a new error must be explained in the PR.

### compare.py: the corpus against SymPy

`tools/compare.py queries.jsonl` replays the corpus that
`tools/record_queries.py` records from SymPy's own tests against SymPy's
recorded answers (categories as in its docstring) and exits 1 only on a
`wrong` in-scope record.

* `--in-scope-only`: the headline numbers of the README. Any `wrong` is a
  bug; a change in `extra` or `none` needs a line in the PR.
* `--relations-only`: the relation records, answered by the theories.
* `--time-sympy` times `sympy.ask` on the same records; see `--help` for
  the rest. One engine replays the whole file, in recording order.

### gate2

`tools/gate2.py CHECKOUT` replays the `ask` and `_ask_recursive` calls of
SymPy's assumption tests (`sympy/assumptions/tests`) against frozen
satassume answers, not SymPy's, so it catches any change of answer,
improvements included, in every scope group (the in-scope count is printed
separately). CHECKOUT runs in a subprocess with `PYTHONPATH` set to it and
the SymPy pin, so any checkout can be gated. About 2 s:

    PYTHONHASHSEED=0 python tools/gate2.py . --frozen /home/tilo/provable/data/gate2-frozen.jsonl \
        --sympy /home/tilo/orion/sympy [--allow-more-definite] [--show K]

It exits 1 on any change. With `--allow-more-definite` a None-to-definite
change is listed and does not fail; a contradiction, a less definite
answer and any change to or from `error:ValueError` still fail. On `main`
at 7399535 it reports 2,863 records (2,588 in scope), 0 changed, without
the flag.

How the frozen file is made:

1. Record, from a SymPy checkout (read-only, `PYTHONDONTWRITEBYTECODE=1`),
   one pytest run per file of `sympy/assumptions/tests`, each under
   `timeout`, then concatenate the outputs in file-name order:

       RECORD_OUT=rec/$b.jsonl PYTHONHASHSEED=0 PYTHONPATH=/path/to/satassume/tools:. \
         python -m pytest -q -p record_queries -p no:cacheprovider sympy/assumptions/tests/$b.py

   The last recording had 3,642 records (772 `old`, not gated).
2. Freeze: `python tools/gate2.py CHECKOUT --freeze RECORDED.jsonl --frozen OUT`.
   Each line holds `prop` and `assum` (as `srepr`), SymPy's recorded
   answer, the scope group and CHECKOUT's answer. Records that cannot be
   rebuilt are left out (7).

Do not sort or deduplicate the file: one engine replays it in order. An
intended change of answer means re-freezing and saying so in the commit.
On an overloaded machine a rebuild can hit its 2 s alarm and show up as a
changed answer.

### The stream answers

The refine stream (`stream.pkl`) is every `ask` call satrefine makes over
its battery, recorded by `tools/refine_record.py` on `refine-identities`.
It is the workload of the timing tools and the widest answer check. Its
recorded answers are satassume's at recording time and are now stale: on
`main` at 7399535, 961 answers are more definite than the recording, 3
less definite and 42 raise. So compare a candidate with a baseline run,
not with the recording:

    PYTHONHASHSEED=0 PYTHONPATH=BASE:/path/to/sympy python tools/stream_answers.py STREAM base.json default
    PYTHONHASHSEED=0 PYTHONPATH=CAND:/path/to/sympy python tools/stream_answers.py STREAM cand.json default
    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python tools/stream_answers_compare.py STREAM base.json cand.json out.json [--verify S]

`tools/stream_answers.py` replays every query in order on one engine
(`MODE` `default` is `Engine()`, `free` is `Engine(uninterpreted="free")`,
issue #64) and writes the answers and the wall time, about 3.6 s.
`tools/stream_answers_compare.py` classifies each query (same, more
definite, new error, lost error, less definite, flipped; the output calls
the two files `default` and `free` whatever they hold), prints a census of
the relation atoms no theory reads, and with `--verify S` asks SymPy's
`ask` each distinct changed query. `tools/gate2_stream.py [FROZEN] OUT.pkl`
turns gate2's frozen queries into a stream file for the same two tools.

### ab.py: interleaved A/B timing

`tools/ab.py REF CAND [--rounds N]` replays the stream in a fresh process
per run, alternating reference and candidate, each a cold pass, with the
same embedded loop for both, and prints every run, the best of each side
and the change. It also checks every answer against the recording and
exits 1 on a mismatch; with the current `stream.pkl` that verdict is
"ANSWER MISMATCH" on both sides alike, so use it for the timing, check
that the per-side counts (`error`, `less`, `more`) are equal, and take
answers from the stream diff above.

`--allow-more-definite`: None in the recording and True or False now is
listed (`--show K`, `--more-definite-out PATH`), not a failure; a
contradiction, a less definite answer or a `ValueError` still fails. A
more definite answer on the reference must then be the same on the
candidate, and each side's must be the same in every round.

On the shared host, timings that decide something run under
`~/bin/bench-container` (pinned cores), interleaved, and report the median
of per-round ratios. One cold stream pass is about 3.2 to 3.6 s at 7399535.

### Per-query log

`tools/refine_replay.py STREAM --log PATH [--log-models]` replays the
stream once with wrappers from `tools/query_log.py` installed on the
engine classes and writes one JSON line per query: the stages taken
(`memo`, `propagation`, `escalation`, `cone`, `search`), the outcome, why
a session was built (`session_new`, `evict_reason`, `session_error`), and
every `Solver._solve` call with its decisions, conflicts and optionally
the model (format in the module docstring). It shows where the time goes
before an optimisation is attempted. The logged pass is a few percent
slower and is not a benchmark number. The wrappers mirror control flow in
`Engine.ask` and `Solver.entails`; after a change to either, check the
log's totals against `Engine.stats`. The analysis scripts that read the
log are in the `agent-reports-2026-09` tag
(`agent-reports/2026-09-perf-rounds/scripts/`).

## Fuzzers

Every checker should count what it could not check and print that count
next to the pass count; "0 unsound" means nothing without "N unchecked".

* `tests/test_solver_incremental.py`: one long-lived `Solver` per seed
  through a weighted random mix (clause insertion in every form, including
  while assumption levels are held; `implied`, `entails`, `solve`,
  `propagate`, `root_trail`, `value`), each answer checked against a fresh
  solver of the same code built from the same clauses. Coverage tests
  assert the incremental paths were hit; mutation tests (a dropped clause,
  a weak propagator, a stale witness) assert the harness catches them. A
  bug shared with the from-scratch path is invisible here;
  `test_solver.py` checks that path against brute force. Seeds change
  meaning when the op mix is edited; a failure prints its seed and
  operation log. By hand: `python tests/test_solver_incremental.py 0 2000
  [block|theory]`, split by seed range to keep each run under 2 minutes.
* `tools/solver_diff_fuzz.py NEW/satassume/sat/solver.py REF/satassume/sat/solver.py SEED0 N`:
  the original form of the above, for comparing two versions of the
  solver (a checkout before the package move has it at
  `satassume/solver.py`).
* `tests/real_theory_fuzz.py SEED0 N [lra|euf|both]`: the long-lived
  solver with the real LRA and EUF theories against fresh solvers
  (`test_solver_real_theories.py` runs it). It also collects steps where
  `implied` is weaker than fresh (a lost implication, not a wrong answer).
* `tools/relevance_fuzz.py SEED0 N [--sets K] [--queries Q] [--relational whole|rationals]`:
  `Engine(relevance=True)` against `Engine(relevance=False)` on the same
  queries. Exit 1 on a contradiction or on a one-sided error that
  reproduces in fresh engines; a None on one side only is allowed. It
  exercises the component split on under 5% of queries (its generator is
  about 40% relations).
* `harness/reffuzz.py`: differential fuzz of `ask` against the
  specification, `satassume.ref.ask_ref`. Each random query is answered
  on a fresh `Engine`, twice on an engine reused across a stream of 20
  queries, and by `ask_ref`. A finding is True vs False, a value vs
  `ValueError`, an engine answer where `ask_ref` says None, the fresh and
  reused engines disagreeing, an error or a timeout. `ask_ref` definite
  where the engine says None is counted (`lost`), not reported (the
  discovery budget and the relevance split allow it). Two generators:
  `general` (every predicate including `polar`, Add/Mul up to 12 terms,
  Pow/Abs/exp/log/trig/re/im, wide And/Or/Not, relations, `oo`/`-oo`/`zoo`/`I`)
  and `inconsistent` (`--inconsistent`: edge values inside Add/Mul with
  finite/infinite and extended-sign facts, so about half of the sets raise
  in `ask_ref`). `KNOWN` in the module lists the accepted differences with
  their reasons (7, all from the relevance split, the same on ca49991); a
  finding whose outcomes match an entry exactly is counted as `known`.
  - CI slice: `tests/test_ref_fuzz.py`, seeds 0-1 x 150 queries per
    generator (about 4 s), plus `test_known_differences`, which pins each
    `KNOWN` entry; a change that makes one agree with `ask_ref` must drop
    it. `REFFUZZ_SEEDS=0-9 REFFUZZ_N=3000` widens the slice.
  - Longer runs: `PYTHONHASHSEED=0 python -m harness.reffuzz --seeds 0-9 -n 3000
    [--inconsistent] [--out F.jsonl]`, about 30 s per 3000-query seed; run seeds
    as parallel processes. Exit 1 on any finding, each printed with its query.
    `--diff A.jsonl B.jsonl` compares two versions' `--out` files over the same
    seeds (flips, lost and gained answers per column).
* Hypothesis: `test_verify_soundness.py` (`ask` against concrete points
  including `I`, `oo`, `zoo`, `nan`), `test_lra_fuzz.py` (Fourier-Motzkin
  oracle), `test_euf_fuzz.py` (naive congruence closure) and others.
* `tools/ask_fuzz.py` (on `refine-identities`) checks numerically the
  `ask` answers satrefine takes from SymPy; it is a refine tool.

## History independence and totality

* `harness/` (#55) checks that answers do not depend on query history:
  a long-lived engine against fresh ones over several stream orders and
  engine presets, shrinking, attribution, a cache audit and pinned repros.
  `tests/test_history.py` runs its fast part on every push (the known
  cases are strict xfails; a fix moves its repro to `harness/repros/fixed/`)
  and its slow part with `HISTORY_SLOW=1`;
  `.github/workflows/history-fuzz.yml` runs the nightly campaign. Every
  mode is in `harness/README.md`.
* #58, not merged: `tools/totality.py` checks statically that every
  node's template block is satisfiable for every allowed assignment of its
  children; `tests/test_totality.py` runs it with an empty allowlist.

## Benchmarks (asv)

`asv.conf.json` runs `benchmarks/` per commit of `main` in a virtualenv
(Python 3.13, mpmath 1.3.0, `PYTHONHASHSEED=0`); results are in `.asv/`
(gitignored). SymPy comes from `$SATASSUME_SYMPY`, the stream from
`$SATASSUME_STREAM`, as for `tools/ab.py`.

`benchmarks/counters.py` has exact `track_` counts per workload (the
stream and small query families: sessions, nodes, clauses, propagations,
decisions, searches, ...; a count going up is a question, not a failure)
and `StreamTime`; `benchmarks/correlation.py` has time and every count in
one benchmark; `benchmarks/memory.py` has peak RSS and `tracemalloc` peak
and retained; `benchmarks/compare.html` reads asv's published JSON.

Run and serve:

    pip install asv virtualenv
    SATASSUME_SYMPY=/home/tilo/orion/sympy SATASSUME_STREAM=/home/tilo/provable/data/stream.pkl \
      asv run HASHFILE:<(git rev-list --first-parent -n 20 main)
    asv publish
    mkdir -p .asv/site && ln -sfn ../../benchmarks/compare.html .asv/site/index.html \
      && ln -sfn ../html .asv/site/asv
    git log --format='%H%x09%s' main | python -c 'import sys, json; \
      print(json.dumps(dict(l.rstrip("\n").split("\t", 1) for l in sys.stdin)))' > .asv/site/commits.json
    python -m http.server -d .asv/site      # asv preview serves asv's pages only

asv 0.6.6 limitations and the workarounds in the suite:

| Limitation | Workaround |
|---|---|
| one y-axis per graph | `compare.html` draws time on the left axis and any count or memory metric on the right |
| different benchmarks cannot be overlaid | `Correlation` puts time and the counts in one benchmark, with a `metric` parameter |
| no per-line normalisation (the reference button divides every line by one value) | the "Indexed" option of `compare.html` (each line as % of its first commit); on asv's own graph, log scale |
| no change-versus-change view | the "Change per commit" scatter of `compare.html` (per-commit % change of a count against % change of time) |
| commit subjects are not in the published data | `.asv/site/commits.json`, generated from `git log` (stale as commits land) |
| `asv publish` deletes `html_dir` | serve `.asv/site/` with the two symlinks above |
| timing statistics only for `time_` benchmarks | `Correlation` returns `{"samples": [...], "number": 1}` for `metric="time"`, which asv's result parser treats as a timing. Undocumented: pin asv or re-check on upgrade |
| a benchmark whose source changes hides its past results (results are keyed by a hash of the source) | new metrics go in a new file (memory is in `memory.py`, joined in `compare.html`) |
| `peakmem_` is the whole process (interpreter, SymPy and the loaded stream are about 56 of 68 MB) | `StreamPythonMemory` with `tracemalloc` |

Reading the graphs:

* Timings on a shared machine vary by 3 to 5% across the history (commits
  that change no code spread from -6% to +9%); counts and `tracemalloc`
  numbers are exact under `PYTHONHASHSEED=0`.
* `clauses` is not comparable across `747fb0e`, which moved the unary
  rules into the rule block; `clauses_with_rule_block` is.
* The stream file is not part of the benchmark source: another recording
  changes every stream number without asv noticing. The docstrings quote
  the older 13,877-query stream; the current one has 16,232.

If asv is forked or changes are sent upstream, most useful first: a
second y-axis; per-line normalisation; overlaying selected benchmarks; the
change-versus-change scatter; documented timing samples from `track_`
benchmarks.
