"""order338.py (sa-port-338): a pytest plugin that puts the collected tests in the order ORDER338 names and writes what
ran where, for showing that seven ids of tests/test_witness.py no longer depend on the two tests that used to leave a
template on the default registry.

ORDER338 = file         the order collected (the default)
           first        the two leaking tests, then everything else
           last         everything else, then the two
           interleaved  the test_templates one right before the first of the seven, the test_p4_review one before
                        the third of the five cases; the last of the seven runs after both
           seed:N       every collected test shuffled by random.Random(N)
ORDER338_OUT = a file: one line per leaking test and per one of the seven, "position outcome id", then the totals.
With LEAKCHECK338=1 a last line says whether a user's template is on the default registry when the session ends.
"""
import os
import random

LEAK = ('tests/test_templates.py::test_template_key_error_is_not_read_as_inconsistent',
        'tests/test_p4_review.py::test_reregistered_template_key_does_not_reuse_compiled_pattern')
W = 'tests/test_witness.py::'
FIVE = W + 'test_a_users_knowledge_falls_through_and_the_engines_answer_is_used['
SEVEN = (W + 'test_registered_knowledge_falls_through', FIVE, W + 'test_on_skips_the_session_and_counts_the_query')

_order, _outcome = [], {}


def _seven(nodeid):
    return nodeid.startswith(SEVEN[1]) or nodeid in (SEVEN[0], SEVEN[2])


def pytest_collection_modifyitems(session, config, items):
    mode = os.environ.get('ORDER338', 'file')
    leak = [i for i in items if i.nodeid in LEAK]
    rest = [i for i in items if i.nodeid not in LEAK]
    if mode == 'first':
        items[:] = leak + rest
    elif mode == 'last':
        items[:] = rest + leak
    elif mode == 'interleaved':
        by = {i.nodeid: i for i in leak}
        out, five = [], 0
        for i in rest:
            if i.nodeid == SEVEN[0] and LEAK[0] in by:
                out.append(by.pop(LEAK[0]))
            if i.nodeid.startswith(FIVE):
                five += 1
                if five == 3 and LEAK[1] in by:
                    out.append(by.pop(LEAK[1]))
            out.append(i)
        assert not by, 'interleaved needs the two leaking tests and tests/test_witness.py'
        items[:] = out
    elif mode.startswith('seed:'):
        random.Random(int(mode[5:])).shuffle(items)
    elif mode != 'file':
        raise ValueError(mode)
    _order[:] = [i.nodeid for i in items]


def pytest_runtest_logreport(report):
    if report.when == 'call' or report.outcome != 'passed':
        if _outcome.get(report.nodeid, 'passed') == 'passed':
            _outcome[report.nodeid] = report.outcome if report.when == 'call' else report.when + '-' + report.outcome


def pytest_sessionfinish(session):
    out = os.environ.get('ORDER338_OUT')
    if not out or hasattr(session.config, 'workerinput'):
        return
    lines = ['%5d %-8s %s' % (n, _outcome.get(i, 'not-run'), i) for n, i in enumerate(_order) if i in LEAK or _seven(i)]
    tally = {}
    for o in _outcome.values():
        tally[o] = tally.get(o, 0) + 1
    seven = [i for i in _order if _seven(i)]
    lines.append('mode %s tests %d seven_passed %d/%d all %s' % (
        os.environ.get('ORDER338', 'file'), len(_order), sum(_outcome.get(i) == 'passed' for i in seven), len(seven),
        ' '.join('%s=%d' % kv for kv in sorted(tally.items()))))
    lines += ['NOT-PASSED %s %s' % (o, i) for i, o in sorted(_outcome.items()) if o not in ('passed', 'skipped')]
    if os.environ.get('LEAKCHECK338') == '1':
        from satassume.knowledge.templates import registry
        own = 'satassume.knowledge.templates.'
        users = sorted('%s.%s' % (getattr(t, '__module__', '?'), getattr(t, '__name__', '?'))
                       for ts in registry._by_class.values() for t in ts
                       if not str(getattr(t, '__module__', '')).startswith(own))
        lines.append('users_templates_at_end %d %s' % (len(users), ' '.join(users)))
    with open(out, 'w') as f:
        f.write('\n'.join(lines) + '\n')
