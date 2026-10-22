# Design note: rules written as declarative math (#249)

Status: proposal for review (session satassume-design-1); nothing is
implemented. Code references: satassume `main` `f9291ab`, satsimp `main`
`3832f94`. The companion note [constants.md](constants.md) (#248) consumes
the compiled rules designed here. Both notes follow the truth standard of
#247 (PR #250, `docs/spec.md`).

## 1. Problem

`satassume/knowledge/templates/` is 5,105 lines, with 254 function
definitions (#249 comment). Its rules are written in three notations:

| notation | where | size |
|---|---|---|
| private tuple tables `(('algebraic', ('zero', False)), 'transcendental')` | `functions.py`, `special.py`, `combinatorial.py`, `cfunctions.py` | 184 rows (103, 61, 12, 8) |
| `table.py` `Row`/`Section`, with slot names and guard strings | `core.py` (`Mul`, `POW_TABLE`) | 111 `Row(` |
| hand-written `R.rule`/`R.equiv` calls | everywhere | about 350 call sites |

The call-site counts are approximate, from an AST count (a prototype, not
in this PR):

- about 270 are in generators that never look at the constant argument;
- 22 are in generators that do arithmetic on it;
- about 60 are in other helpers: `core.py`'s `Add` and its shape splits,
  `limits.py`, `selection.py`.

The length comes from two things:

- **Bookkeeping around the rules:** slot indices, key building, and shape
  recognition (`pi_split`, `_half_split`, `_bound_split`).
- **Mathematics done in Python while a template is built.**
  `_pi_trig_rules`, for example, computes `r = c % 2` and branches on
  `r.q == 2`.

There are 30 `sympy-boundary` marks, mostly `is_*` reads on constants.
This procedural layer is also where recent soundness bugs were: #184
(`shifted`, the `x - 1` slot), #161 (`kept_product`), #225 and #238.

## 2. Design

### 2.1 Notation

The notation follows satsimp's `rules/trig.py`: rows are SymPy booleans
over plain symbols, and hypotheses are stated per block. At import time, a
compile step turns the rows into the slot specs the engine uses today
(`_common.Rule`, `Pattern`). The engine, the template cache and the clause
shapes do not change.

```python
from satassume.rulelang import Q, Args, assuming, every, fold, head, node, rational, some, when
x, b, e, s = symbols('x b e s')   # plain: facts are stated, never implied by a name

SIN = head(sin, [
    *(P(x) >> P(sin(x)) for P in (Q.real, Q.complex, Q.finite, Q.zero, Q.imaginary)),
    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(sin(x)),        # Lindemann
])

LOG = head(log, [
    Q.extended_positive(x) >> Q.extended_real(log(x)),
    Q.zero(x) >> (Q.infinite(log(x)) & ~Q.extended_real(log(x))),
    Q.positive(x - 1) >> Q.positive(log(x)),          # x - 1: a derived term
])

xs = Args('xs'); k = xs.one; rest = xs.other          # n-ary: one argument and the others
M = node(Mul, xs)
MUL = head(Mul, [
    (Q.zero(k) & every(Q.finite, rest)) >> Q.zero(M),
    (Q.extended_negative(k) & every(Q.extended_positive, rest)) >> Q.extended_negative(M),
    when(xs.n >= 2, every(Q.prime, xs) >> Q.composite(M)),
], limit={'one': MAX_ONEOUT})                         # cost policy, kept apart from the math

c = rational('c')                                     # matcher primitive: a Rational coefficient
SIN_PI = head(sin, [
    Q.rational(s) >> Q.algebraic(sin(pi*c*s)),
    (Q.integer(c) & Q.integer(s)) >> Q.zero(sin(pi*c*s)),
    (Q.integer(2*c) & ~Q.integer(c) & Q.even(s)) >> Q.zero(sin(pi*c*s)),
    (Q.positive(fold(Mod(c, 2))) & Q.negative(fold(Mod(c, 2) - 1))) >> Q.positive(sin(pi*c)),
])
```

Python binds `>>` tighter than `&` and `|`, so compound sides need
parentheses. A forgotten pair cannot slip through: `a & b >> c` builds
`And(a, Implies(b, c))`, which the compiler rejects (section 2.3).

- **`prem >> concl`** is a conjunction of literals implying a disjunction.
  - A disjunction in the premise splits into several rules, which replaces
    `'int>=2'`. A conjunction in the conclusion splits too.
  - `cond >> Equivalent(a, b)` replaces `Rules.equiv`.
- **Predicate iteration** is a Python comprehension, not `preds=`/`'$p'`.
- **Groups.** `Args` stands for the arguments of an n-ary node, with the
  parts `one`, `other`, `pair` and `choose(m)`.
  - `every(P, g)` in a premise means P holds for each member of `g`.
  - `some(P, g)` in a conclusion means P holds for at least one.
  - Together they replace `Section('each' | 'pairs' | 'negsets')`.
- **Arity.** An arity condition that is mathematics (`n >= 2`) is
  `when(...)`. An arity limit that is cost policy (`MAX_ONEOUT`,
  `MAX_PAIRS`) is `limit=` metadata.
- **Blocks.** `assuming(H, rows)` adds `H` to every row that mentions all
  of `H`'s symbols, like satsimp's `add_rules`/`ASSUMED`.
- **Generic rows.** A `head(F, rows)` with an undefined `F` is registered
  for every head of its arity, like satsimp's `ZERO`.

### 2.2 Head declarations

```python
declare(sin, SIN, SIN_PI, interval=iv.sin)    # interval: constants.md, section 2.3
```

A head is declared once, with its rows and, optionally, its value
semantics for the constant procedure. The evaluators are code, not rules.

### 2.3 Compiler

`rulelang.compile(rows) -> {shape key: spec generator}` runs at import. A
spec generator returns the `(premises, conclusion)` index specs `Rules`
collects today. So `resolve`, `Pattern`, `Compiled`, the template cache
and `test_template_volume` stay as they are, and the compiler adds no cost
per query. For each row, the compiler:

1. **Finds the terms.** These are:
   - the *node*, the application of the declared head;
   - the argument symbols;
   - *derived terms*, any other term built from them (`x - 1`, `2*e`);
   - group terms.
2. **Assigns slots** in the old order: arguments, the node, then derived
   terms.
3. **Builds the derived terms per node.**
   - In migration steps 1 to 4 it calls today's builders (`shifted`,
     `_doubled`), so the slot objects do not change.
   - From step 5 on it builds them with `evaluate=False`. A derived term
     then means what the row says, never a constructor's rewrite (#184).
   - The switch changes pattern keys: `shifted(3, -1)` is the atom `2`,
     but the unevaluated `Add(3, -1)` is decided by the exact fold. So it
     is gated on its own.
4. **Rejects the row at import time** if:
   - a predicate is not in `VOCAB`;
   - the row does not mention the node;
   - a symbol carries assumptions;
   - a written term lost its head (`cos(x + pi/2)` is built as
     `-sin(x)`). Rows are built under `with evaluate(False)`, and this
     check catches what that misses;
   - the top of the row is not an implication. This catches a missing pair
     of parentheses, and a row that SymPy's logic collapsed to `True`.

### 2.4 Value-dependent rules: the arithmetic leaves the rules

A row states a theorem about its parameters. The arithmetic moves to
*pattern-time folding* (constants.md, section 2.2).

- **Folding.** Where `c` is a Rational atom, `Q.integer(2*c)` and
  `fold(Mod(c, 2))` are closed. `_resolve_lit` decides them when the
  pattern is compiled, with the leaf table and the exact rational fold,
  the same way it decides `positive(2)` today. Then:
  - a satisfied premise is dropped;
  - a violated premise kills the row;
  - an undecided literal drops the row.
- **`fold(t)` is a cost marker.** The term is used only where it is
  closed, and elsewhere the row is dropped. So a symbolic `s` never adds a
  `Mod` node to a session. Dropping a row costs completeness, never
  soundness.

For example, with `c = 3/2` the second `SIN_PI` row folds away
(`integer(3/2)` is False). The third compiles to `even(s) -> zero(N)`,
which is the clause `_pi_trig_rules` emits today, without its `r.q == 2`
branch.

The same applies to `_cosh_shift_rules`, `_exp`'s `I*pi` case, `_mod`,
`POW_TABLE`'s constant bases, and the bound and reciprocal splits. Each
family's step checks this against its clause diff.

### 2.5 Matcher

A head's rows are grouped by node shape:

- plain `head(x, ...)`;
- `head(pi*c*s)` with a Rational `c`, and `head(I*pi*c*s)`;
- `Add` with half-integer coefficients;
- `Add` with an integer constant term.

The split function of each shape becomes one of a few *matcher
primitives*, each with one written soundness argument. The obligation: a
binding `σ` makes the node's argument multiset **structurally** equal to
the pattern's parts under `σ`. A primitive never rebuilds a term with
evaluation on, and never asks SymPy whether two terms are equal (#161,
#184). Matches are memoized on the existing pattern key (class, arity,
constants, shape tag).

### 2.6 One rule set for the SAT encoding and for constants

Both consumers read the compiled output of section 2.3: the `Pattern`
clauses, the plain formulas (`registry._split`), the wide formulas
(`Pattern.wide_formulas()`) and the head's extension facts.

- The SAT engine instantiates them per node, as today.
- The constant procedure (constants.md, section 2.1, step 3) solves one
  node's rules with its inputs' facts fixed. Grandchild slots
  (`POW_SLOTS`' `U`, `S`) count as inputs.

So the answer to "can both be generated from one declarative rule set" is
**yes, for the fact rules**. Four things stay outside the rule set:

- the leaf table;
- the per-head evaluators;
- the matcher primitives;
- the LRA glue of relations.

They give values, base facts, bindings or a theory, not facts. All but the
LRA glue are declared next to the rows, so a head is described in one
place.

## 3. Soundness

- **Rows.** A row is sound when it holds for all values of its symbols.
  That is the obligation templates already have, and the spec judges it.
  Reviewing a row becomes reviewing one formula, not a generator's
  branches.
- **Compiler.** It emits a row's clausal form over slots. Bugs move from
  per-template code into one compiler, tested by:
  - the clause-set gate of section 5;
  - the point oracle at ordinary values, a candidate generator under #247;
  - a mutation test: a flipped literal must change the clauses.
- **Derived terms** are unevaluated from step 5 on, so slot identities hold
  by construction.
- **Folding** uses the leaf table and exact arithmetic (constants.md,
  section 3). An undecided literal drops the row.
- **Matcher primitives** each discharge the obligation of section 2.5.

## 4. Sharing machinery with satsimp

**Location.** satsimp pins satassume, so shared code lives in satassume,
as `satassume.rulelang`, with no satsimp imports.

**Shareable now: the authoring layer.**
- plain symbols;
- `assuming` (satsimp's `add_rules`/`ASSUMED`);
- head wildcards;
- import-time validation;
- `evaluate(False)` row building.

satsimp could adopt it after a pin bump. That is an optional satsimp PR,
not part of this plan.

**Shareable later.**
- **The matcher primitives.** satsimp's `n*unit + r` and `part(...)` are
  the shapes of `pi_split` and `_half_split`. satsimp's matcher would
  first have to meet the structural obligation of section 2.5.
- **Identity tables as facts** (optional, not planned). For example,
  `cos(n*pi/2 + x) = (-1)**((n + 1)/2)*sin(x)` for odd `n` gives every
  predicate of the left side, with the sign flipped. Preconditions:
  - satsimp's `sin(oo) -> AccumBounds` and its `ZERO` row become written
    conventions, not SymPy's values (`cot(0)` is `zoo`), per #247;
  - the cost of the transfer through `theories/transfer.py` is measured.

## 5. Migration plan

Each step is one PR that keeps the suite green.

**The gate for steps 1 to 4.** `tools/rule_equiv.py` collects the pattern
key of every node that the suite, gate2 and the refine stream visit. For
each key it requires:

- **Equal clause multisets after `resolve`.** Rule order cannot be
  reproduced, since SymPy's `And` and `Equivalent` sort their arguments.
- **Identical slot objects** for each node.
- **Identical answers** on gate2 and the refine stream, with timings
  within noise. Literal order can steer the search, but entailment answers
  do not depend on it.

1. **`satassume/rulelang/` and the unary tables.**
   - The notation, the compiler with its checks, and `head`/`declare`.
   - Convert the 103 tuple rows of `functions.py` and the unary generators
     that never read the constant.
   - The spelling of groups, `when` and `fold` is settled in this step.
2. **`special.py`, `combinatorial.py`, `cfunctions.py`.** This includes the
   generators that dispatch on arity (`_zeta`, `_lowergamma`), whose `n` is
   the arity, not a value.
3. **`Mul` and `POW_TABLE`'s symbolic rows.** `table.py`'s private notation
   goes. `tools/totality.py` reads row names, so rows keep their names as
   labels.
4. **`Add`** (`_add_rules`, `_wide_one`), plus `test_template_volume`.
5. **Value-dependent families** (section 2.4) and `evaluate=False` derived
   terms.
   - Needs constants.md step 5.
   - Also replaces the evaluations listed in constants.md, section 4:
     `combinatorial._value_units`, the `multigamma` value,
     `core._unit_power_units` (`as_real_imag`), `shifted` and `_doubled`.
     Each moves to an exact evaluator or is dropped.
   - Clauses may change. Gate: an answer diff on gate2 and the refine
     stream, each change listed with its mathematical reason, plus
     `test_template_volume`.
6. **Remove the old generators and helpers.** That is `Rules` as a public
   API, `_minus_one`, `shifted`, and the split functions that became
   primitives. The resulting size is measured here and not promised now.

Steps 1 to 4 do not depend on constants.md and can run alongside its steps
1 to 4.

## 6. Risks and open questions for Tilo

1. **The gate compares clause sets, not rule order.** Is "same answers,
   timings within noise" enough? Or should the old order be kept, carried
   outside SymPy's booleans?
2. **SymPy as notation.** Rows depend on SymPy's constructors, and some
   ignore `evaluate(False)`. The head check catches that, but an author may
   then hit a pattern they cannot write. `evaluate(False)` also leaves
   numbers unnormalized (`pi/2` stays `Mul(Pow(2, -1), pi)`, SymPy 1.14),
   so the compiler must normalize numeric parts itself.
   - The alternative is a small term language of our own: more robust,
     less like math. I propose SymPy, with the check.
3. **Where do the evaluators live?** Next to the rows (section 2.2), or in
   `lra_bounds` behind a registry?
4. **satsimp.** Is the shared authoring layer enough for now? Or should the
   matcher be shared from the start, which first requires satsimp's
   matcher to meet satassume's obligation?
5. **Row names** for `tools/totality.py`: explicit names, or labels derived
   from the formula?
