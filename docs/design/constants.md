# Design note: a bottom-up procedure for constants (#248)

Status: proposal for review (session satassume-design-1). Nothing here is
implemented. Code references are to `main` at `f9291ab`. The companion note
[rules.md](rules.md) (#249) changes how rules are written; this note uses
its compiled form only. Both follow the truth standard of #247 (PR #250,
`docs/spec.md`, "Truth standard"): no step reads SymPy's `doit()`,
automatic evaluation or `is_*` as the truth.

## 1. Problem

A *closed term* is a term with no free symbols, no `AppliedUndef`, and not
built non-commutative (`domain._built_noncommutative`): `pi - 3`,
`E**pi - pi**E`, `log(6) - log(2) - log(3)`. Today:

- **Constant propositions** go to `Engine.is_` (`sympy_api`,
  "Constant propositions: context-free first" in design.md), a SAT session
  over the term's cone. Its clauses link each node to its children in both
  directions.
- **Closed subterms of symbolic queries** are ordinary nodes. Their template
  clauses stay, and `relations.with_closed_units` (#190) adds sign units
  from `closed_sign` on top (`[*compiled, c]`).
- **Atom constants** get their facts from SymPy: `_common.const_value`
  reads `getattr(c, 'is_' + pred)`. The templates carry 30
  `sympy-boundary` marks.
- **Budgets** are per module: `constfield` (`PREC_CAP = 4096`,
  `MAX_DEGREE = 64`, `MAX_TERMS = 512`, `MAX_BITS = 8192`,
  `MAX_WORK = 2**14`), `lra_bounds` (`_IV_PREC = 128`, `_MAX_BITS = 4096`),
  `realroots` (`MAX_DEGREE = 120`, `MAX_BITS = 512`).

The two-way flow is observable. Let `c = log(6) - log(2) - log(3)`, which
is 0. Measured on `main`:

| query | assumptions | `main` | flow |
|---|---|---|---|
| `Q.positive(c)` | `Q.positive(pi*c)` | True | whole -> part |
| `Q.zero(c)` | `Q.zero(pi*c)` | True | whole -> part |
| `Q.zero(pi*c)` | `Q.zero(c)` | True | part -> whole |
| `Q.zero(c)` | none | None, 111 ms | refinement runs to the cap |
| `Q.integer(Pow(4, 1/2, evaluate=False))` | none | None | no exact folding |

The first row derives a false fact about `c` from a (false) assumption
about `pi*c`. That is the direction #248 rules out. The fourth row shows the
cost problem: an enclosure can never prove a value is 0, so refining it
only stops at the cap.

## 2. Design

### 2.1 The procedure

```python
def facts(t, budget: Budget, seeds=()) -> FactVector
```

`FactVector` gives one value in {True, False, None} for each of the 14 basis
predicates (`rules.BASIS`), closed under the rule block. `facts` is a pure
function of `(t, budget, seeds)`. Memo key: the term's structure, as
`_common.const_key` already does (`Float(2.0) == Integer(2)`). With the
default budget and no seeds the memo is global (an LRU), because no SymPy
cache is read (section 4). The steps for a term `t`:

1. **Leaf.** A table written in the spec, never SymPy's `is_*`:
   - `Integer` and `Rational` from `p` and `q`. `prime` and `composite` are
     decided only for `|p| < 2**64`, by Miller-Rabin with the fixed bases
     that are proven deterministic there.
   - `pi`, `E`, `I`, `GoldenRatio`, `EulerGamma`, `Catalan`, `oo`, `-oo`,
     `zoo`, `nan`, each row with its justification. Example: `pi` is
     transcendental (Lindemann). `EulerGamma` has `rational` None (an open
     problem). `nan` has no facts (#189).
   - Floats: keep today's convention (open question 4).
2. **Children.** Compute `facts(child)` for each argument, and for each
   *derived term* the node's rules mention (`x - 1` of `log`, `2*e` of a
   power; rules.md, section 2.3). Derived terms are built unevaluated, so a
   derived term means exactly what the rule says. A term already on the
   recursion stack gets the all-None vector. That is sound and ends any
   cycle.
3. **Local solve.** Take the node's compiled pattern (the same `Pattern`
   the SAT engine instantiates), the rule block on the node, its children
   and its derived terms, and the children's vectors as units. Compute the
   node's backbone: one model, then one entailment check per node literal
   true in that model, at most 14 checks.
   - Facts the solver learns about children are dropped. A child's vector
     comes only from step 2, so information never flows from the whole to a
     part.
   - Memo key: `(pattern key, children's vectors)`. Most nodes then cost a
     lookup.
4. **Evaluation**, only when a basis fact that evaluation can decide is
   still None after step 3. The evaluators are ordered by cost (2.3). They
   return units for the node, and step 3 runs once more with those units.

Integrals, sums and products: `limits.py` never makes the summand a slot,
so their templates read only the limits, which are closed. They need nothing
new. A body as a symbolic sub-query is optional and not planned.

### 2.2 How it plugs into the engine

- **Constant route.** `sympy_api` calls `facts(t, DEFAULT)` instead of
  `Engine.is_` for an `is_constant_proposition`. The fallback on None
  (answer under the assumptions) stays as it is.
- **Closed nodes become leaves.** `Session.node` gives a closed node the
  units of `facts(t)` (a `_common.units` pattern) and does not visit its
  children. `with_closed_units` and `closed_units` are removed.
- **Pattern-time folding.** `_resolve_lit` decides a literal about a closed
  term (an atom, or a derived term that is closed in this pattern) by
  `facts`, instead of `const_value`. `consts_of` widens from atoms to closed
  terms. This is where the value-dependent rules of rules.md, section 2.4
  get their arithmetic.
- **Seeds.** A top-level conjunct of the assumptions that is a literal about
  a closed term (`Q.zero(c)`) is a *seed*. `facts(t, budget, seeds)` adds the
  seeds as units at the node they name, and they flow upward only. A seed
  that contradicts the computed facts makes the set inconsistent
  (`ValueError`, as today). Other assumptions about closed terms (`Q.zero(c)
  | Q.zero(d)`) apply to the leaves only. With seeds, row 3 of the table
  stays True and rows 1 and 2 become None.

### 2.3 Evaluation and its cost

```python
@dataclass(frozen=True)
class Budget:
    nodes: int = 400            # closed terms visited, derived terms included
    prec_start: int = 64        # bits, intervals and constfield
    prec_cap: int = 4096
    max_bits: int = 4096        # magnitude of any intermediate value
    max_degree: int = 64        # constfield; realroots keeps its own 120 (open question 3)
    max_terms: int = 512
    prime_bits: int = 64
```

A `Meter` passed down the recursion counts against one `Budget`. When the
meter is spent, the remaining facts are None. Nothing raises, and nothing
is measured in time, so an answer is a function of the term alone, not of
the machine's load. The evaluators, cheapest first:

| evaluator | input | can prove | cap |
|---|---|---|---|
| exact rational fold | `+ - * /`, integer powers, `Mod` and rational roots of rationals | every basis fact except `polar` | `max_bits` per intermediate value; roots by integer `iroot` |
| `constfield` | Q(pi, E, radicals, generic constants) | sign; zero only when formally zero | `prec_cap`, `max_degree`, `max_terms` |
| interval pass (`lra_bounds`) | the heads `_interval` supports | strict sign, nonzero, real and finite, noninteger (an enclosure between two consecutive integers) | `prec_cap`; precision doubles at most `log2(prec_cap/prec_start) = 6` times |

- **One pass for the whole term.** The interval pass is one bottom-up walk
  per precision level. It gives an enclosure for every closed subterm at
  once, so the units it gives subterms cost nothing extra.
- **Total cost:** at most `nodes` local solves, each on one template (sizes
  bounded by `tests/test_template_volume.py`), plus at most 7 interval
  passes over at most `nodes` nodes at at most `prec_cap` bits.
- **Never called:** `evalf`, `doit`, `nsimplify`, `minimal_polynomial`,
  factorization, or any SymPy simplifier. `lra_bounds` already uses
  outward-rounded `mpmath.iv` and trusts no `evalf` error estimate.
- **What enclosures cannot prove.** An enclosure never proves `zero`,
  `integer` or `rational`. Those come from exact folding or from rules. So
  `Q.zero(log(6) - log(2) - log(3))` stays None, but it now costs one
  bounded refinement run, not an open-ended one. Stopping as soon as a
  pass proves nothing new is a further option. It needs a measurement
  first.

### 2.4 One rule set, two consumers

Steps 2 and 3 use the compiled patterns of rules.md unchanged. The SAT
engine instantiates them per node; the procedure solves them locally with
the children's facts fixed. Three things are *not* generated from the fact
rules, and the note says so on purpose:

1. **Leaf facts.** A table with a justification per row.
2. **Evaluators.** They need values, not facts. Each one is declared next
   to its head's rules, as code (rules.md, section 2.2).
3. **Matcher primitives.** The shape recognizers, such as a rational
   multiple of `pi`.

## 3. Soundness

Invariant: every literal in `facts(t, budget, seeds)` holds for the value
of `t` under the spec's semantics, assuming the seeds hold. The proof is by
induction on the recursion:

- **Leaves.** The table states facts with written justifications, and the
  facts of a rational follow from `p` and `q`. Miller-Rabin with fixed bases
  is deterministic below `2**64`.
- **All-None vector.** It is trivially sound (the cycle guard, an exhausted
  meter).
- **Local solve.** The template clauses hold for every value of their slots
  (the obligation every template already has). The units are true by
  induction. So every model of the actual values satisfies the local
  problem, and every entailed node literal holds.
  - The solver may derive facts about children. They are also true, but
    they are dropped. Dropping them is not needed for soundness. It gives
    two other things:
    - *Direction.* A part's facts never depend on the whole.
    - *Purity.* `facts(child)` is the same in every context, so the memo is
      safe.
- **Evaluators.** Exact arithmetic is exact. A `constfield` sign is
  semantic: it is either backed by a rigorous enclosure, or it is a formal
  zero, which implies a zero value. Interval results are outward-rounded
  and prove only exclusions.
- **Derived terms.** They are built with `evaluate=False`, so the identity
  "slot = `x - 1`" holds by construction, not because SymPy's constructor
  is right. (#184 was exactly a constructor rewriting `x - 1`.)
- **Seeds.** They are assumptions. Facts derived from them hold whenever
  the assumptions do, which is what entailment asks.
- **Leaves in sessions.** A closed node that carries only its computed
  units removes clauses, and no true unit. It can lose answers, never
  soundness.

On #247: the input object is what SymPy built and is the thing asked about.
Its construction is not an oracle step. The procedure never asks SymPy what
a term evaluates to, and never rebuilds a term with evaluation on.

## 4. Purity

`const_value`'s reads of SymPy's `is_*` are the only SymPy cache the
constant path reads today. The leaf table removes them. After that the
memo is a function of the term, which history independence requires (#97).

## 5. Migration plan

Each step is one PR that keeps the suite green. Each gate names its baseline
(a clean worktree of `origin/main`).

1. **`Budget` object.** A pure refactor: `constfield`, `lra_bounds` and
   `realroots` read one `Budget` with today's values.
   - Gate: every answer identical on gate2 and the refine stream.
2. **Leaf table** in `knowledge/leaves.py`, plus a spec section that
   justifies each row. `const_value` reads the table, not `is_*`.
   - Gate: an answer diff on gate2. Every changed answer is listed with
     the reason the table gives for it.
3. **`facts()` added, unused** (`knowledge/closed.py`), with tests on
   hand-written constants.
   - Oracle (#247): exact rationals, and enclosures from an independent
     `mpmath.iv` run at twice the precision. Not `doit`.
   - A cross-check against today's `Engine.is_` on every closed term of the
     corpora. Differences are candidates, reported, not asserted.
4. **Constant route switched** to `facts()`.
   - Gate: gate2 answers (lost answers listed), the timing of the constant
     queries, and the cost cap shown on the `log(6) - log(2) - log(3)`
     example.
5. **Closed nodes as leaves and pattern-time folding.**
   `with_closed_units` and `closed_units` go, and `_resolve_lit` uses
   `facts()`.
   - Gate: an answer diff on gate2 and the refine stream, and
     `test_template_volume` budgets.
6. **Seeds.**
   - Gate: rows 1 to 3 of the table in section 1 (None, None, True), and an
     inconsistent seed raises.

Steps 1 and 2 are independent of rules.md. Step 5 is needed before the
value-dependent families of rules.md move (rules.md, step 5).

## 6. Optional, not planned

- **Exact algebraic-number arithmetic** (minimal polynomials with a degree
  cap). It would prove `zero`, `integer` and `rational` for algebraic
  constants such as `sqrt(2) + sqrt(3) - sqrt(5 + 2*sqrt(6))`. `realroots` and `constfield`'s
  radicals are the starting point. Degrees grow as `2**n` with nesting, so
  it needs its own cap.
- **Transcendence results** beyond the current rows
  (Lindemann-Weierstrass is already in the `exp`/`sin` rows; Baker,
  Gelfond-Schneider).
- **Early stop of interval refinement** for facts it cannot prove.
- **A symbolic sub-query** for the bodies of closed integrals and sums.

## 7. Risks and open questions for Tilo

1. **Lost answers when closed nodes become leaves (step 5).** Answers that
   needed top-down flow are lost on purpose (rows 1 and 2). Answers that
   needed a constant's subterm next to a symbolic one are lost too, for
   example a closed term that also appears inside a symbolic sum's
   relation glue. Step 5 measures this; is a small loss acceptable?
2. **Seeds.** Do you want them? They keep part-to-whole answers under
   assumptions (row 3) and stay one-directional. Without seeds, any
   assumption about a closed term applies to that leaf only, which is
   simpler.
3. **One `Budget` for `realroots` too?** Its degree cap (120) is higher
   than `constfield`'s (64) for a reason: Sturm sequences of integer
   polynomials are cheap. I propose separate fields in one object.
4. **Floats.** Is `Float(2.0)` the rational 2 (exact binary value), or an
   inexact quantity with no `integer`/`rational` facts? Today SymPy's
   `is_*` decides, and that is the kind of read #247 removes.
5. **Inconsistent constant assumptions.** Should
   `ask(Q.prime(7), Q.composite(7))` keep answering True (design.md,
   "Constant propositions"), or raise now that constant facts are units
   with a single source?
6. **Primality cap.** Should `prime` above `2**64` stay None, or should
   BPSW (no known counterexample, but no proof) count as proof?
