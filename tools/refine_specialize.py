#!/usr/bin/env python
"""Moved to ``satrefine/tools/refine_specialize.py``: run ``python -m satrefine.tools.refine_specialize``.

This shim (kept for phase 3) runs that file as a script with the same arguments."""
import os
import runpy
import sys

sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository root, not tools/
runpy.run_path(os.path.join(sys.path[0], "satrefine", "tools", "refine_specialize.py"), run_name="__main__")
