"""Does a discarded run leave anything in Python? (Section 9's limit on "Rust holds no state", component 4 slice A.)

`fresh.py ... --discard` runs each query three ways, memos cleared before each: once to count the calls at each site, once
with `TermRefuse` raised at one of those calls, and that run's second run on Python is the answer and digests written, so
`cmp` against a plain `fresh.py` says whether the discard moved anything. Sites and depths cycle by query index.

At the rollback, `check()` compares all of Python's state against a copy taken as the run started, and counts each name that
differs. `raised` against `refused` says nothing swallowed a refusal on the way up. A site the query never reaches isn't
planted, so each row's `reached` says what was really shown.

SITES holds what a refusal has to pass: each `except Exception` on the engine's path, a nested session, and the term sites
that will use Rust's key in slice B.
"""
import collections

import sa_solver
from sympy import Dummy

from harness import state as HS
from satassume import engine as E, relations as R, sympy_api as A
from satassume.state import memos
from satassume.theories.lra import constfield, lra_adapter as L

import term_live

SITES = (
    ('engine.py:1906 _complete_check', E.Engine, '_complete_check'),
    ('sympy_api.py:1107 _formula', A, '_formula'),
    ('sympy_api.py:1107 verdict', E.Engine, 'verdict'),
    ('relations.py:1989 _guarded_adapters', R, '_guarded_adapters'),
    ('relations.py:2018 _terms_of', R, '_terms_of'),
    ('nested Engine.is_', E.Engine, 'is_'),
    ('Session.prepare_query', E.Session, 'prepare_query'),
    ('Session.query_literal', E.Session, 'query_literal'),
    ('Session._visit', E.Session, '_visit'),
    ('relations._key', R, '_key'),
    ('lra_adapter.default_sort_key', L, 'default_sort_key'),
    ('relations.relation_atom', R, 'relation_atom'),
)
COUNTS = collections.Counter()
LEFT = collections.Counter()
EXAMPLES = {}
_calls = collections.Counter()
_arm = [None, 0]     # site name and the call to raise at


class Planted:
    @staticmethod
    def wrap(name, real):
        def f(*a, **k):
            _calls[name] += 1
            if _arm[0] == name and _calls[name] == _arm[1] and term_live.current() is not None:
                _arm[0] = None
                COUNTS['raised'] += 1
                COUNTS['raised:' + name] += 1
                raise sa_solver.TermRefuse('planted: ' + name)
            return real(*a, **k)
        f.__wrapped__ = real
        return f


def install():
    for name, owner, attr in SITES:
        setattr(owner, attr, Planted.wrap(name, getattr(owner, attr)))
    term_live.BEFORE_RUN[0] = _before
    term_live.AFTER_ROLLBACK[0] = check


def _copy(v):
    if isinstance(v, dict):
        return {k: _one(x) for k, x in v.items()}
    return _one(v)


def _one(v):
    return dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else set(v) if isinstance(v, set) else v


def state(eng):
    out = {}
    for n, _, t in memos.PROCESS.items():
        out['process:' + n] = _copy(t)
        out['stamp:' + n] = getattr(t, 'stamp', None)
    for n, _, t in eng.memos.items():
        out['engine:' + n] = _copy(t)
    for mod, name, _ in HS.inventory():
        out[f'module:{mod}.{name}'] = _copy(_module_value(mod, name))
    out['stats'] = dict(eng.stats)
    out['budget'] = eng.last_budget_limited
    out['constructing'] = set(eng._constructing)
    out['context_sessions'] = len(eng._context_sessions)
    out['constants'] = list(constfield._CONSTANTS)
    out['by_key'] = dict(constfield._BY_KEY)
    out['epoch'] = eng._epoch
    return out


def _module_value(mod, name):
    import sys
    return getattr(sys.modules[mod], name)


_before_state = [None, None, 0]


def _before(eng):
    _before_state[:] = [eng, state(eng), Dummy._count]


def check():
    """After the rollback: what's different from when the run started."""
    eng, before, dummies = _before_state
    after = state(eng)
    COUNTS['checked'] += 1
    clean = True
    for k in before.keys() | after.keys():
        a, b = before.get(k), after.get(k)
        try:
            same = a == b
        except Exception as e:      # a value that can't compare is not a pass
            same = False
            COUNTS['uncomparable'] += 1
            EXAMPLES.setdefault('uncomparable:' + k, repr(e)[:200])
        if not same:
            clean = False
            LEFT[k] += 1
            if k not in EXAMPLES and isinstance(a, dict) and isinstance(b, dict):
                extra = [x for x in b if x not in a][:2]
                EXAMPLES[k] = repr(dict(added=extra, n_before=len(a), n_after=len(b)))[:300]
    if Dummy._count != dummies:
        COUNTS['dummy-count-moved'] += 1
    COUNTS['clean' if clean else 'left-something'] += 1


def count_pass():
    _calls.clear()
    _arm[0] = None


def arm(i):
    """Picks this query's plant from the count pass: a reached site by index, then first, middle or last call."""
    reached = [n for n, _, _ in SITES if _calls[n]]
    if not reached:
        COUNTS['no-site-reached'] += 1
        _calls.clear()
        return None
    name = reached[i % len(reached)]
    n = _calls[name]
    nth = (1, (n + 1) // 2, n)[(i // len(reached)) % 3]
    _calls.clear()
    _arm[:] = [name, nth]
    COUNTS['armed'] += 1
    COUNTS['reached:' + name] += 1
    return name, nth


def report():
    import json
    return json.dumps(dict(counts=COUNTS, left=LEFT, examples=EXAMPLES, term=term_live.counts(), refusals=term_live.REFUSALS[:20]),
                      indent=0, sort_keys=True)
