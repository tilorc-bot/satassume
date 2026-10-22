# Design note: rules written as declarative math (#249)

Status: proposal for review (session satassume-design-1). Nothing here is
implemented. Code references are to satassume `main` at `f9291ab` and
satsimp `main` at `3832f94`. The companion note
[constants.md](constants.md) (#248) uses the compiled form designed here.
Both follow the truth standard of #247 (`docs/spec.md`, "Truth standard",
PR #250).

## 1. Problem

`satassume/knowledge/templates/` is 5,105 lines with 254 function
definitions (#249 comment). Its rules are written in three notations:

| notation | where | size |
|---|---|---|
| private tuple tables, `(('algebraic', ('zero', False)), 'transcendental')` | `functions.py`, `special.py`, `combinatorial.py`, `cfunctions.py` | 184 rows (103, 61, 12, 8) |
| `table.py` `Row`/`Section` with slot names and guard strings | `core.py` (`Mul`, `POW_TABLE`) | 111 `Row(` |
| hand-written `R.rule`/`R.equiv` calls | everywhere | about 350 call sites |

The call-site count comes from an AST count, a prototype kept out of this
PR. About 270 of those call sites are in generators that never look at the
constant argument. 22 are in generators that do arithmetic on it. About 60
are in `core.py`'s `Add` rules and its shape splits.

Two things make the code long and error-prone:

- **Bookkeeping around the rules:** slot indices, key building and shape
  recognition (`pi_split`, `_half_split`, `_bound_split`).
- **Mathematics done in Python while a template is built.** For example,
  `_pi_trig_rules` computes `r = c % 2` and branches on `r.q == 2` before it
  emits a rule. There are 30 `sympy-boundary` marks, mostly reads of
  `is_*` on constants.

The procedural layer is also where recent soundness bugs were: #184
(`shifted` and the `x - 1` slot), #161 (`kept_product`), and #225/#238
(levels).

## 2. Design

### 2.1 Notation

The new notation follows satsimp's `rules/trig.py`:

- Rows are SymPy booleans over plain symbols.
- Hypotheses are stated per block.
- A compile step at import time turns rows into the slot specs the engine
  already uses (`_common.Rule`, `Pattern`).

The engine, the cache and the clause shapes do not change.

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

Python binds `>>` tighter than `&` and `|`, so a compound premise or
conclusion needs parentheses. A forgotten pair cannot slip through: `a & b
>> c` builds `And(a, Implies(b, c))`, and the compiler rejects a row whose
top is not an implication (section 2.3).

Forms:

- **`prem >> concl`** is one clause-shaped rule: a conjunction of literals
  implies a disjunction of literals.
  - A disjunction in a premise splits into several rules. This replaces the
    `'int>=2'` pseudo-predicate.
  - A conjunction in a conclusion splits too.
  - `cond >> Equivalent(a, b)` replaces `Rules.equiv`.
- **Predicate iteration** is a Python comprehension. No `preds=`/`'$p'`
  mini-language, and `SIGN_FLIP` stays a dict.
- **Groups.** `Args` stands for the arguments of an n-ary node. Its parts
  are `one`, `other`, `pair` and `choose(m)`. In a premise,
  `every(P, group)` means P holds for each member. In a conclusion,
  `some(P, group)` means P holds for at least one. These replace
  `Section('each' | 'pairs' | 'negsets')`.
- **Arity conditions that are mathematics** (`n >= 2`) wrap a row in
  `when`. **Arity limits that are cost policy** (`MAX_ONEOUT`, `MAX_PAIRS`)
  are `limit=` metadata.
- **Blocks.** `assuming(H, rows)` adds the hypothesis `H` to each row that
  mentions all of `H`'s symbols. This is satsimp's `add_rules`/`ASSUMED`.
- **`head(F, rows)` with an undefined `F`** is a generic row. It is
  registered for every head of its arity, as in satsimp's `ZERO`.

### 2.2 Head declarations

A module declares a head once, with the rules and, optionally, the head's
value semantics for the constant procedure:

```python
declare(sin, SIN, SIN_PI, interval=iv.sin)    # interval: used by constants.md, section 2.3
```

The evaluators are code, not rules. They are the one part of a head that
is not generated from its rows (constants.md, section 2.4).

### 2.3 Compiler

`rulelang.compile(rows) -> {shape key: spec generator}` runs once per
module at import. A spec generator returns the same `(premises,
conclusion)` index specs that `Rules` collects today. So `resolve`,
`Pattern`, `Compiled`, the template cache and `test_template_volume` stay
as they are. Per row the compiler:

1. **Finds the terms.**
   - The *node*: the application of the declared head.
   - The *argument symbols*.
   - *Derived terms*: any other term built from them, such as `x - 1` or
     `2*e`.
   - *Group terms.*
2. **Assigns slots** in the order the old template used: arguments, the
   node, then derived terms. This lets step 1 of the migration compare
   specs one to one.
3. **Builds derived terms per node with `evaluate=False`.** This replaces
   `slots=`, `_minus_one` and `shifted`. A derived term then means exactly
   what the row says. It is never a rewrite by SymPy's constructor (the
   #184 bug).
4. **Validates the row and fails at import time** if any of these hold:
   - a literal's predicate is not in `VOCAB`;
   - the row does not mention the node;
   - a symbol carries assumptions;
   - a written term lost its head. SymPy rewrote the pattern itself, for
     example `cos(x + pi/2)` built as `-sin(x)`. Rows are therefore built
     under `with evaluate(False)`, and the check catches what that does not
     cover;
   - the row is not an implication at the top. This catches a missing
     pair of parentheses, and a row that SymPy's logic constructors
     collapsed to `True`.

The compiler has no runtime cost: templates are still built once per
pattern key.

### 2.4 Value-dependent rules: the arithmetic leaves the rules

A row states a theorem about its parameters. The arithmetic moves to
*pattern-time folding* (constants.md, section 2.2):

- In a pattern where `c` is a Rational atom, `Q.integer(2*c)` and
  `fold(Mod(c, 2))` are closed terms. `_resolve_lit` decides them through
  the constant procedure when the pattern is compiled, as it decides
  `positive(2)` today. A decided premise is dropped, a violated one kills
  the row, and an undecided one drops the row.
- `fold(t)` is a cost marker. The derived term is used only where it is
  closed. Elsewhere the row is dropped, so a symbolic `s` never adds a `Mod`
  node to a session. Dropping a row loses completeness, never soundness.

With `c = 3/2`, the second row folds away (`integer(3/2)` is False) and
the third compiles to "`even(s)` -> `zero(N)`". That is the clause
`_pi_trig_rules` emits today, without its `r.q == 2` branch.

This works for `_pi_trig_rules`, `_cosh_shift_rules`, `_exp`'s `I*pi`
case, `_mod`, `POW_TABLE`'s constant bases and the bound and reciprocal
splits. Each family's step checks the claim against its clause diff.

### 2.5 Matcher

The rows of a head are grouped by the shape of the node's pattern. The
shapes are:

- plain `head(x, ...)`;
- `head(pi*c*s)`, with `c` a Rational and `s` the rest;
- `head(I*pi*c*s)`;
- `Add` with half-integer coefficients;
- `Add` with an integer constant term.

Today each shape has its own split function. They become a few *matcher
primitives*, and each primitive gets one written soundness argument. The
obligation for a primitive: a binding `σ` it returns makes the node's
argument multiset **structurally** equal to the pattern's parts under `σ`.
The check compares parts. It never rebuilds a term with evaluation on, and
it never asks SymPy whether two terms are equal (the lesson of #161 and
#184). Matches are memoized on the existing pattern key (class, arity,
positions and values of constants, shape tag).

### 2.6 One rule set for the SAT encoding and for constants

Both consumers read the compiled specs of section 2.3:

- the SAT engine instantiates them per node, as today;
- the constant procedure (constants.md, section 2.1, step 3) solves one
  node's specs with the children's facts fixed.

So the answer to "can both be generated from one declarative rule set" is
**yes for the fact rules**. Three things stay outside the rule set:

- the leaf table (the facts of `pi`, of a rational, of `oo`);
- the per-head evaluators;
- the matcher primitives.

None of them is a fact rule: they give values, base facts or bindings. They
are declared next to the rows, so a head is still described in one place.

## 3. Soundness

- **The rows.** A row is sound when it holds for all values of its symbols.
  That is the obligation templates already have, and the spec stays the
  judge. Stating rows as formulas makes the obligation readable: the
  review of a row is the review of one formula, not of a generator's
  branches.
- **The compiler.** Its output for a row is the row's clausal form over
  slots. Bugs move from per-template code to one compiler, which is
  tested once:
  - spec identity during the migration (section 5);
  - the existing point oracle at ordinary values, which is a candidate
    generator under #247;
  - a mutation test: a flipped literal must change the specs.
- **Derived terms** are built unevaluated, so slot identities hold by
  construction.
- **Folding** is the constant procedure, which is sound by constants.md,
  section 3. An undecided folded literal drops the row.
- **Matcher primitives** each carry the structural-equality obligation of
  section 2.5.

## 4. Sharing machinery with satsimp

**Dependency direction.** satsimp pins satassume. Shared code therefore
lives in satassume, as `satassume.rulelang`, which has no satsimp imports.

**Shareable now** (the authoring layer):

- plain symbols;
- `assuming` (= satsimp's `add_rules` and `ASSUMED`);
- head wildcards;
- the import-time row validation;
- the `evaluate(False)` row building.

satsimp could import these with one pin bump. That is an optional
follow-up PR in satsimp, not part of this plan.

**Shareable later:**

- **The matcher primitives.** satsimp's `n*unit + r` and `part(...)` are
  the same shapes as `pi_split` and `_half_split`. satsimp's matcher would
  have to meet the structural-equality obligation of section 2.5 first,
  since satassume matches unevaluated input.
- **Identity tables as facts** (optional, not planned). For example,
  `cos(n*pi/2 + x) = (-1)**((n + 1)/2)*sin(x)` for odd `n` gives every
  predicate of the left side, with the sign flipped. Preconditions:
  - **The special-value conventions.** satsimp maps `sin(oo)` to
    `AccumBounds`, and its `ZERO` row takes its meaning from SymPy's value
    at 0 (`cot(0)` is `zoo`). Under #247 both must become conventions
    written in a spec, not SymPy's output.
  - **A cost measurement** of the transfer through `theories/transfer.py`.

## 5. Migration plan

Each step is one PR that keeps the suite green.

**The gate for steps 1 to 4.** `tools/rule_equiv.py` collects the template
pattern keys of every node visited by the suite, gate2 and the refine
stream. For each key it compiles the old and the new specs. They must be
identical: same rules, same order. So answers cannot change.

1. **`satassume/rulelang/` and the unary tables.**
   - The notation, the compiler (with the validations of section 2.3,
     step 4) and `head`/`declare`.
   - Convert the 103 tuple rows of `functions.py` and the unary
     generators that never look at the constant.
   - Settle the exact spelling here: the group API, `when`, `fold`.
   - Gate: spec identity.
2. **`special.py`, `combinatorial.py`, `cfunctions.py`.** This includes the
   nary-by-arity generators (`_zeta`, `_lowergamma`): their `n` is the
   arity, not a value. Gate: spec identity.
3. **`Mul` and `POW_TABLE`'s symbolic rows.** Translate `Row`/`Section`
   and delete `table.py`'s private notation (`tools/totality.py` reads
   row names: keep names as row labels). Gate: spec identity.
4. **`Add`** (`_add_rules`, `_wide_one`). Gate: spec identity, and
   `test_template_volume`.
5. **Value-dependent families** (section 2.4). This needs constants.md,
   step 5 (pattern-time folding).
   - The clauses may change: folding can decide more than the old
     branches did.
   - Gate: an answer diff on gate2 and the refine stream (every change
     listed with its mathematical reason), and `test_template_volume`.
6. **Remove the old generators and helpers.** This includes `Rules`'s
   public use, `_minus_one`, `shifted` and the split functions that became
   primitives. Expected size: the template modules shrink to the rows plus
   the declarations. Measure it in this step; do not promise a number now.

Steps 1 to 4 do not depend on constants.md. They can run in parallel with
its steps 1 to 4.

## 6. Risks and open questions for Tilo

1. **Spec identity holds only if the compiler reproduces the old rule
   order.** If an order change turns out to be harmless and simpler, should
   the gate be "same answers and same clause set" instead of "same specs"?
2. **SymPy as notation.** Rows built from SymPy objects depend on its
   constructors even under `evaluate(False)`. Some constructors ignore the
   flag. The import-time head check catches it, but authors may then hit a
   pattern they cannot write. Also, `evaluate(False)` leaves numbers
   unnormalized: `pi/2` stays `Mul(Pow(2, -1), pi)`, so the compiler has to
   normalize the numeric parts of a row itself (measured, SymPy 1.14). The alternative is a small term language of
   our own, which is more robust but less like math. I propose SymPy, with
   the check.
3. **Where the evaluators live** (section 2.2). Should they sit next to
   the rows, or stay in `lra_bounds` with a registry?
4. **satsimp.** Is a shared authoring layer enough for now, with the
   matcher and the identity tables left for later? Or do you want the
   matcher shared from the start? That would make satsimp's matcher meet
   satassume's soundness obligation first.
5. **Row names.** `tools/totality.py` reports non-total blocks by row
   name. Should rows carry explicit names, or labels derived from the
   formula text?
