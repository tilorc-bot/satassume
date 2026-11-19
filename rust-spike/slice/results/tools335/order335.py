"""order335.py (sa-port-335): pytest plugin. Keeps only the node ids listed in $ORDER335 (one per line) and runs them
in that order in one process; writes the order it ran to $ORDER335_RAN. For replaying one xdist worker's tests."""
import os


def pytest_collection_modifyitems(config, items):
    want = [l.rstrip('\n') for l in open(os.environ['ORDER335']) if l.strip()]
    pos = {n: i for i, n in enumerate(want)}
    keep = sorted((it for it in items if it.nodeid in pos), key=lambda it: pos[it.nodeid])
    config.hook.pytest_deselected(items=[it for it in items if it.nodeid not in pos])
    items[:] = keep
    with open(os.environ['ORDER335_RAN'], 'w') as f:
        f.write('wanted %d kept %d in_order %s\n' % (len(want), len(keep), [it.nodeid for it in keep] == want))
