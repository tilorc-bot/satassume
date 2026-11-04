"""rc_ids.py MODE WL: tools-rust/rc.py (same counters as the ceiling report) with the ids table installed first."""
import os
import runpy
import sys
here = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, here)
import ids_core  # noqa: E402
ids_core.install("live")
sys.argv = [os.path.join(here, "..", "..", "tools-rust", "rc.py")] + sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
