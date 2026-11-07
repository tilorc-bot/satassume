"""pytest plugin, 5b's first item: one row per `join`, the two objects' classes and args, by test id.

`-p join_log` with SLICE_SUITE_OUT set writes joins.PID.jsonl there. A join is a second object `==` to a node's first with
another class, `SessionCore::known` in session.rs. The hook only reads; it swallows nothing, so a raise here reaches the
session, and each row's text is cut short. `join_summary.py` reads the rows.
"""
import json
import os

import sa_solver

_out = []


def _text(x):
    return repr(x)[:200]


def _cls(x):
    t = type(x)
    return dict(name=t.__name__, module=t.__module__, id=id(t), meta=type(t).__name__,
                kwargs=_text(getattr(t, '_kwargs', None)), func=_text(getattr(x, 'func', None)))


def _hook(session, nid, first, second):
    a, b = _cls(first), _cls(second)
    _out.append(dict(
        test=os.environ.get('PYTEST_CURRENT_TEST', '').split(' ')[0],
        worker=os.environ.get('PYTEST_XDIST_WORKER', ''),
        session=session, nid=nid, first=a, second=b,
        first_text=_text(first), second_text=_text(second),
        args_first=_text(getattr(first, 'args', None)), args_second=_text(getattr(second, 'args', None)),
        same_text=_text(first) == _text(second),
        hash_eq=hash(first) == hash(second),
    ))


def pytest_configure(config):
    if os.environ.get('SLICE_SUITE_OUT'):
        sa_solver.set_join_hook(_hook)


def pytest_runtest_logfinish(nodeid, location):
    if _out:
        with open(os.path.join(os.environ['SLICE_SUITE_OUT'], f'joins.{os.getpid()}.jsonl'), 'a') as f:
            for r in _out:
                f.write(json.dumps(r) + '\n')
        _out.clear()
