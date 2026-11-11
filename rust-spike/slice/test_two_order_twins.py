"""Item 4e: the twin harness and the two-order harness (sa-port-250, results/before-pr-reads.md) as kept tests, Python and
Rust, each order in its own process (two_order.py). Fail on base 9151316 (wiring.py compared two arguments of one term by
identity: 34 of the harness's 560 queries flip, all on terms with two equal arguments); pass with 17241af's `==`."""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def run(mode, order):
    env = dict(os.environ)
    for k in ('SLICE_TERM_PLANT', 'SLICE_SESSION_PLANT', 'SLICE_KNOWLEDGE_PLANT', 'SLICE_PLANT'):
        env.pop(k, None)
    out = subprocess.run([sys.executable, os.path.join(HERE, 'two_order.py'), mode, order], env=env, cwd=HERE,
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])['answers']


def split(d, side):
    return {k.rsplit(':', 1)[0]: v for k, v in d.items() if k.endswith(':' + side)}


@pytest.mark.parametrize('mode', ['py', 'rust'])
def test_twin_answers_its_original(mode):
    """The twin harness: originals in one process, twins in another, a new Engine per ask."""
    orig, tw = split(run(mode, 'orig'), 'orig'), split(run(mode, 'twin'), 'twin')
    assert len(orig) == 160 and not any(v.startswith('EXC') for v in orig.values())
    assert sum(v == 'True' for v in orig.values()) > 20          # the rule the identity compare lost decides these
    assert {k for k in orig if orig[k] != tw[k]} == set()


@pytest.mark.parametrize('mode', ['py', 'rust'])
def test_two_orders_give_one_answer(mode):
    """The two-order harness: each original and its twin asked twin first and original first, each order in its own
    process; neither side's answer depends on the order."""
    a, b = run(mode, 'orig-first'), run(mode, 'twin-first')
    assert len(a) == len(b) == 320
    assert {k for k in a if a[k] != b[k]} == set()
    assert {k for k in split(a, 'orig') if split(a, 'orig')[k] != split(a, 'twin')[k]} == set()


def test_rust_answers_python():
    assert run('rust', 'orig-first') == run('py', 'orig-first')
