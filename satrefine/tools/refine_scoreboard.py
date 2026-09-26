#!/usr/bin/env python
"""Old name of ``python -m satrefine.tools.scoreboard suite`` (a test suite under each ask backend); same options.

Kept for phase 3: ``python -m satrefine.tools.refine_scoreboard [options]``
runs ``scoreboard suite [options]``.
"""
import sys

from satrefine.tools.scoreboard import main

if __name__ == "__main__":
    sys.exit(main(["suite", *sys.argv[1:]]))
