# Design note: a bottom-up procedure for constants (#248)

Status: proposal for review (session satassume-design-1); nothing is
implemented. Code references are to `main` at `f9291ab`. The companion
note [rules.md](rules.md) (#249) defines the compiled rules used here. Both
notes follow the truth standard of #247 (PR #250, `docs/spec.md`): no step
reads SymPy's `doit()`, automatic evaluation or `is_*` as the truth.
Section 4 lists where the code still does.

## 1. Problem

A *closed term* has no free symbols and no `AppliedUndef`, and is not
built non-commutative (`domain._built_noncommutative`). Examples: `pi - 3`,
`E**pi - pi**E`.

- **Constant propositions** go to `Engine.is_`: a SAT session over the
  term's cone, whose clauses link each node to its children in both
  directions.
- **A closed subterm of a symbolic query** is an ordinary node.
  `relations.with_closed_units` (#190) adds `closed_sign` units on top of
  its template clauses.
- **Atom constants** get their facts from SymPy's `is_*` (`const_value`,
  plus the direct reads listed in section 4).
- **Budgets** are per module:
  - `constfield`: `PREC_CAP = 4096`, `MAX_DEGREE = 64`, `MAX_TERMS = 512`,
    `MAX_BITS = 8192`, `MAX_WORK = 2**14`;
  - `lra_bounds`: `_IV_PREC = 128`, `_MAX_BITS = 4096`;
  - `realroots`: `MAX_DEGREE = 120`, `MAX_BITS = 512`.

Measured on `main`, with `c = log(6) - log(2) - log(3)`, whose value is 0:

| query | assumptions | `main` | flow |
|---|---|---|---|
| `Q.positive(c)` | `Q.positive(pi*c)` | True | whole -> part |
| `Q.zero(c)` | `Q.zero(pi*c)` | True | whole -> part |
| `Q.zero(pi*c)` | `Q.zero(c)` | True | part -> whole |
| `Q.zero(c)` | none | None, 38-111 ms | refinement runs to the cap |
| `Q.integer(Pow(4, S.Half, evaluate=False))` | none | None | no exact folding |

Row 1 derives a false fact about `c` from a false assumption about the
whole, which is the direction #248 rules out. Row 4 is the cost problem:
an enclosure can never prove that a value is 0, so refining stops only at
the cap.

## 2. Design

### 2.1 The procedure

```python
def facts(t, seeds=()) -> FactVector     # under the default Budget (2.3)
```

A `FactVector` gives True, False or None for each of the 14 basis
predicates (`rules.BASIS`), closed under the rule block. For a term `t`:

1. **Leaf.** Facts come from a table written in the spec, never from
   `is_*`.
   - `Integer` and `Rational`: from `p` and `q`. `prime` and `composite`
     are decided only below `2**64`, by deterministic Miller-Rabin.
   - Each named constant (`pi`, `E`, `I`, `GoldenRatio`, `EulerGamma`,
     `Catalan`, `oo`, `-oo`, `zoo`, `nan`) gets one row with its
     justification. For example: `pi` is transcendental (Lindemann);
     `EulerGamma`'s `rational` is None (an open problem); `nan` has no
     facts (#189).
   - Floats: open question 4.
2. **Inputs.**
   - Every argument and every grandchild slot (`POW_SLOTS`' `U`, `S`) gets
     `facts()`. These are proper subterms.
   - Each derived term the node's rules mention (`x - 1` of `log`, `2*e`
     of a power) gets `facts_derived()`. That is the same procedure, but
     it never builds the derived term's own derived terms.
   - A derived term is built from proper subterms and rationals, so the
     recursion is well-founded and needs no cycle guard.
3. **Local solve.** The problem consists of:
   - the node's compiled rules (rules.md, section 2.6);
   - the rule block on each object they mention;
   - the input vectors and the seeds naming `t`, as units.

   Closed compound inputs are *slots* with unit vectors. They are not
   folded at pattern time: folding would drop every rule with an undecided
   premise, and with them the case splits the local solve exists for
   (#248 comment, section 1).

   The procedure computes the node's backbone: one model, then at most 14
   entailment checks. Facts learned about inputs are dropped, so nothing
   flows from the whole to a part.

   If the problem is UNSAT:
   - with seeds, the assumptions are inconsistent and the procedure raises
     `ValueError`;
   - without seeds, a rule or leaf row is unsound: the procedure reports
     it in `stats` and returns the all-None vector.
4. **Evaluation** runs only when a fact an evaluator can decide is still
   None (section 2.3). The evaluators return units for the node, and step 3
   runs once more.

**Memo.** There are two caches, both LRU:

- `facts`: keyed on the term, without seeds;
- the local solve: keyed on (head, shape tag, atom constants, all input
  vectors, the seeds at the node).

Neither key holds a closed compound term, so entries are shared across
terms. An entry stores the meter cost of its computation, and a hit
charges that cost again, so the meter runs the same with or without the
memo. Results computed after the meter ran out are not stored. Every
answer is therefore a function of the query alone (history independence,
#97).

**Integrals, sums, products.** `limits._inner` already runs
`registry.context_free` on the body, with the bound variable replaced by a
`Dummy` that carries assumptions. That direction (body to whole) is
allowed. Two changes are needed:

- the sub-query's cone weight is charged to the meter;
- the body is rebuilt unevaluated (section 4).

### 2.2 How it plugs into the engine

- **Constant route.** For a constant proposition:
  - a unary predicate of a closed term is answered by `facts()`;
  - `And`, `Or` and `Not` combine those answers in Kleene logic;
  - relations between closed terms (`Q.gt(pi, 3)`) keep today's engine and
    LRA path.

  The fallback on None (answer under the assumptions) is unchanged.
- **Closed nodes become leaves.** `Session.node` gives a closed node the
  units of `facts(t)` (a `_common.units` pattern) and does not visit its
  children. `with_closed_units`, `closed_units` and their use in `ref.py`
  go.
- **Pattern-time folding is for parameters only.** Parameters are atom
  constants (as today) and closed derived terms over them: `2*c` and
  `Mod(c, 2)` for a Rational `c` (rules.md, section 2.4). `_resolve_lit`
  decides them with the leaf table and the exact rational fold, on a meter
  of its own and never with seeds. So what lands in `_CACHE` depends on the
  pattern key alone.
- **Seeds.** A top-level conjunct of the assumptions that is a unary
  literal about a closed term (`Q.zero(c)`) is added as a unit at that
  node and flows upward only.
  - Seeded results are stored only in the local-solve cache, whose key
    holds the seeds.
  - Other assumptions about closed terms (`Q.zero(c) | Q.zero(d)`) apply
    to the leaves only.
  - With seeds, rows 1 and 2 of the table become None, and row 3 stays
    True.
- **Relations are out of scope.** LRA still linearizes a closed sum into
  its atoms (`log(6)`, `log(2)`, ...), so relation assumptions can still
  carry facts from a whole to its parts (open question 7).

### 2.3 Evaluation and its cost

```python
@dataclass(frozen=True)
class Budget:
    nodes: int = 400            # distinct closed terms visited, derived terms and sub-queries included
    prec_start: int = 64        # bits, intervals and constfield
    prec_cap: int = 4096
    max_bits: int = 4096        # magnitude of any intermediate value
    max_degree: int = 64        # constfield; realroots keeps 120 (open question 3)
    max_terms: int = 512
    prime_bits: int = 64
```

**The meter.** One `Meter` per top-level call counts against the
`Budget`. When it is spent, the remaining facts are None. Nothing raises
and nothing is timed.

**Walks are memoized on the node.** Every walk over a term, the
closed-term test included, visits each distinct node once. Today
`_interval` walks the tree. `Add(a, a, evaluate=False)` nested 18 times
over `a = pi` (19 distinct nodes) takes 4 s per pass, and
`ask(Q.positive(a))` takes 17 s.

| evaluator | input | can prove | cap |
|---|---|---|---|
| exact rational fold | `+ - * /`, integer powers, `Mod`, `p/q`-th roots of nonnegative rationals | every basis fact except `polar` | `max_bits` per intermediate |
| `constfield` | Q(pi, E, radicals, generic constants) | sign; zero only when formally zero | `prec_cap`, `max_degree`, `max_terms` |
| interval pass (`lra_bounds`) | the heads `_interval` supports | strict sign, nonzero, real and finite, noninteger (enclosure between two consecutive integers) | `prec_cap`; at most 7 levels (64 to 4096 bits) |

- **What the exact fold leaves alone.** It does not fold a negative base
  with a non-integer exponent (`(-8)**(1/3)` is not -2 on the principal
  branch), a division by 0, or `0**-1`. These are left to the rules and
  the spec's special-value conventions.
- **Interval pass.** Each level is one memoized walk that gives an
  enclosure for every closed subterm. Those subterm units are new code:
  `_interval` returns only the top enclosure today.
- **Total cost**, with `n <= nodes` distinct nodes:
  - at most `n` local solves, each bounded by the template volume
    (`tests/test_template_volume.py`);
  - at most 7 interval passes over `n` nodes, at no more than `prec_cap`
    bits;
  - one `constfield` sign;
  - bound-body sub-queries, charged by their cone weight.
- **Never called:** `evalf`, `doit`, `nsimplify`, `minimal_polynomial`,
  factorization, or any SymPy simplifier.
- **Enclosures never prove `zero`, `integer` or `rational`.** Those come
  from exact folding or from rules. So `Q.zero(c)` of the table stays
  None, at a bounded cost.

### 2.4 One rule set, two consumers

Steps 2 and 3 use the compiled rules of rules.md unchanged. The SAT engine
instantiates them per node; the procedure solves them locally with fixed
inputs. Four things are *not* generated from the fact rules:

- the leaf table;
- the per-head evaluators (code, declared next to the head's rows);
- the matcher primitives;
- the LRA glue of relations.

## 3. Soundness

Invariant: every literal of `facts(t, seeds)` holds for the value of `t`
under the spec's semantics, provided the seeds hold. The proof is by
well-founded induction on the recursion of section 2.1, step 2.

- **Leaves.** Each row has a written justification. Rationals follow from
  `p` and `q`. Miller-Rabin with fixed bases is deterministic below
  `2**64`.
- **The all-None vector** (meter spent, internal UNSAT) is trivially
  sound.
- **Local solve.** The compiled rules hold for every value of their slots,
  which is every template's existing obligation. The units are true, by
  induction or as seeds. So the actual values form a model, and every
  entailed node literal holds.
  - Learned input facts would also be true. They are dropped for two other
    reasons:
    - direction: a part's facts never depend on the whole;
    - purity: `facts(child)` is the same in every context.
- **Evaluators.**
  - Exact arithmetic is exact.
  - A `constfield` sign is semantic: a rigorous enclosure excludes 0, or
    the number is a formal zero, which implies the value is 0.
  - Intervals are rounded outward and prove only exclusions.
- **Derived terms** are built with `evaluate=False` (rules.md, step 5). So
  "slot = `x - 1`" holds by construction, not because SymPy's
  constructor is right. #184 was a constructor rewrite.
- **Folding** uses only the leaf table and exact arithmetic. An undecided
  literal drops the rule, which can cost completeness, never soundness.
- **Leaves in sessions.** A closed node that keeps only its units loses
  clauses, but no true unit: again it can cost answers, never soundness.

The input object is what SymPy built, and it is the thing asked about.
Building it is not an oracle step. After section 5, no step asks SymPy
what a term evaluates to.

## 4. Purity and #247: what has to go

| where | what | replaced by |
|---|---|---|
| `_common.const_value` | `getattr(c, 'is_' + pred)` | leaf table (step 2) |
| `core.py` (468, 470, 538, 555-556, 935, 947-953, 1008, 1229), `functions.py` (456, 464, 698) | `is_*` and arithmetic on constants | leaf table, folding (step 2; rules.md step 5) |
| `combinatorial._value_units`, `special.py:269` | `expr.func(c)` evaluates `genocchi(8)` and `multigamma` | exact evaluators per head, or dropped (rules.md step 5) |
| `core._unit_power_units` | `e.as_real_imag()` | exact fold of the exponent (rules.md step 5) |
| `limits._inner` | `xreplace` and `expr.func(f, ...)` rebuild with evaluation | unevaluated rebuild (step 6) |
| `shifted`, `_doubled` | `x + c` and `2*x`, evaluated | `evaluate=False` derived terms (rules.md step 5) |

Purity, and with it the global cache, holds only once all of these are
gone.

## 5. Migration plan

Each step is one PR that keeps the suite green, with its baseline on a
clean worktree of `origin/main`.

1. **`Budget` object and memoized walks.** `constfield`, `lra_bounds` and
   `realroots` read one `Budget`, with today's values.
   - Gate: identical answers on gate2 and the refine stream, and the
     18-level `Add(a, a)` example is fast.
2. **Leaf table** (`knowledge/leaves.py`) and its spec section.
   `const_value` and the leaf-fact reads of section 4 use the table.
   - Gate: an answer diff on gate2, with each change explained by its
     table row.
3. **`facts()` added, unused** (`knowledge/closed.py`).
   - Oracle (#247): exact rationals, and enclosures from an independent
     `mpmath.iv` run at twice the precision.
   - Cross-check against `Engine.is_` on the corpora's closed terms.
     Differences are candidates, not assertions.
   - A test that the meter costs the same with a warm and a cold memo.
4. **Constant route switched** to `facts()`, with Kleene connectives.
   - Gate: gate2 (lost answers listed), the timing of constant queries,
     and the cost of the table's row 4.
5. **Closed nodes as leaves.** `with_closed_units`, `closed_units` and the
   `ref.py` use go, and parameter folding uses the exact fold.
   - Gate: an answer diff on gate2 and the refine stream, and
     `test_template_volume`.
6. **Seeds, and bound bodies under the meter.**
   - Gate: rows 1-3 of the table give None, None, True; an inconsistent
     seed raises; `limits._inner` rebuilds unevaluated.

Steps 1 and 2 do not depend on rules.md. rules.md step 5 needs step 5
here.

## 6. Optional, not planned

- **Exact algebraic-number arithmetic**, with a degree cap. It would prove
  `zero`, `integer` and `rational` for constants like `sqrt(2) + sqrt(3) -
  sqrt(5 + 2*sqrt(6))`. Degrees grow as `2**n` with nesting.
- **More transcendence results.** Lindemann-Weierstrass is already in the
  `exp` and `sin` rows; Baker and Gelfond-Schneider are not.
- **Stopping refinement early** for facts it cannot prove.

## 7. Risks and open questions for Tilo

1. **Lost answers in step 5.** Top-down answers go on purpose (rows 1 and
   2). Answers that needed a constant's subterm inside a symbolic query may
   go too. Step 5 measures this. Is a small loss acceptable?
2. **Seeds: yes or no?** They keep part-to-whole answers under assumptions
   (row 3) and stay one-directional. Without them, assumptions about a
   closed term apply to that leaf only.
3. **One `Budget` for `realroots` too?** Its degree cap is 120, against 64
   in `constfield`, because Sturm sequences are cheap. I propose separate
   fields in one object.
4. **Floats.** Is `Float(2.0)` the rational 2 (its exact binary value), or
   an inexact quantity with no `integer` or `rational` facts? Today
   SymPy's `is_*` decides.
5. **Inconsistent constant assumptions.** `ask(Q.prime(7), Q.composite(7))`
   is True today (design.md). Should it raise, now that a constant's facts
   have a single source?
6. **Primality above `2**64`.** None, or BPSW (no known counterexample, no
   proof)?
7. **Relations about closed terms.** Should LRA keep linearizing closed
   sums, which is a whole-to-part flow through relations? Or should it
   treat a closed term as one opaque constant, bounded by `facts()`?
