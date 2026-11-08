"""Adapters step, part B: the suite's adapter tests, run against adapters.rs' classes (ad_swap.py), must all pass, the same
count as against Python's."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FILES = [os.path.join(ROOT, "tests", f) for f in ("test_lra_adapter.py", "test_euf_adapter.py")]


def _run(*plugin):
    r = subprocess.run([sys.executable, "-m", "pytest", *plugin, "-q", "-p", "no:cacheprovider", "-p", "no:xdist", *FILES],
                       cwd=HERE, capture_output=True, text=True)
    return r.returncode, r.stdout.strip().splitlines()[-1]


def test_rust_adapters_pass_the_adapter_tests():
    import sa_solver
    rc, tail = _run("-p", "ad_swap")
    assert rc == 0, tail
    assert _run()[1].split(" in ")[0] == tail.split(" in ")[0]
    assert sa_solver.LRAAdapter.__module__ == "sa_solver"
