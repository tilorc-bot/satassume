"""Existing corpora as streams.

* ``load_corpus``: the new-system records of ``queries.jsonl`` (written by
  ``tools/record_queries.py`` from SymPy's own test suite: ``ask`` and
  ``_ask_recursive`` calls);
* ``refine_stream``: the queries SymPy's ``refine`` makes over random
  expressions and assumptions (recorded by wrapping the ``ask`` that
  ``sympy.assumptions.refine`` calls), a natural stream with runs of the
  same assumptions over the subterms of one expression.
"""
from __future__ import annotations

import json
import random
from typing import List, Optional, Sequence

from .checker import Ask, Item
from .sympy_io import from_srepr


def load_corpus(path: str, kinds: Sequence[str] = ("ask", "rec"), limit: Optional[int] = None,
                in_scope_only: bool = False, skip_errors: bool = True) -> List[Ask]:
    from satassume.sympy_api import out_of_scope
    out: List[Ask] = []
    with open(path) as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("kind") not in kinds:
                continue
            try:
                p = from_srepr(rec["prop"])
                a = from_srepr(rec["assum"])
            except Exception:  # noqa: BLE001 - unreplayable record
                if skip_errors:
                    continue
                raise
            if in_scope_only:
                try:
                    if out_of_scope(p, a) is not None:
                        continue
                except Exception:  # noqa: BLE001
                    continue
            out.append(Ask(p, a))
            if limit and len(out) >= limit:
                break
    return out


def old_records(path: str, limit: Optional[int] = None) -> List[Ask]:
    """The old-system records (``expr.is_<fact>``) as context-free queries
    ``ask(Q.<fact>(expr), True)``: the same path ``Engine.is_`` serves."""
    from sympy import Q
    from satassume.rules import PRED_INDEX
    out: List[Ask] = []
    with open(path) as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("kind") != "old" or rec["fact"] not in PRED_INDEX:
                continue
            try:
                e = from_srepr(rec["expr"])
                out.append(Ask(getattr(Q, rec["fact"])(e), True))
            except Exception:  # noqa: BLE001
                continue
            if limit and len(out) >= limit:
                break
    return out


def refine_stream(seed: int, n_exprs: int = 30, **opts) -> List[Item]:
    """Queries made by ``sympy.refine`` on ``n_exprs`` random expressions
    under random assumptions (SymPy's own ``ask`` answers them while
    recording; only the queries are kept)."""
    import importlib
    R = importlib.import_module("sympy.assumptions.refine")   # the module, not the function
    from sympy import Abs, I, arg, atan2, exp, im, pi, re, sign, sqrt
    from .generators import GenOptions, QueryGen, RandomDraw
    rng = random.Random(seed)
    gen = QueryGen(RandomDraw(rng), GenOptions(**opts))
    recorded: List[Ask] = []
    orig = R.ask

    def rec_ask(prop, assumptions=True, context=None):
        recorded.append(Ask(prop, assumptions))
        try:
            return orig(prop, assumptions) if context is None else orig(prop, assumptions, context)
        except Exception:  # noqa: BLE001
            return None

    heads = [lambda t: Abs(t), lambda t: sqrt(t ** 2), lambda t: (t ** 2) ** rng.choice((S_half(), 1)),
             lambda t: re(t), lambda t: im(t), lambda t: sign(t), lambda t: arg(t),
             lambda t: exp(I * pi * t), lambda t: (-1) ** t, lambda t: t ** rng.choice((2, 3, -1)),
             lambda t: atan2(t, gen.term(1)), lambda t: Abs(t) * t, lambda t: sqrt(t ** 2) + re(t)]
    R.ask = rec_ask
    try:
        for _ in range(n_exprs):
            t = gen.term(2)
            try:
                e = rng.choice(heads)(t)
            except Exception:  # noqa: BLE001
                continue
            a = gen.assumptions()
            if a is True:
                a = gen.assumptions()
            try:
                R.refine(e, a)
            except Exception:  # noqa: BLE001
                pass
    finally:
        R.ask = orig
    return list(recorded)


def S_half():
    from sympy import S
    return S.Half
