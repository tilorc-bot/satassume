#!/usr/bin/env python
"""Old name of ``python -m satrefine.tools.scoreboard battery`` (rows, code lines, battery, fuzz); same options.

Kept for phase 3: ``python -m satrefine.tools.refine_identity_scoreboard [options]``
runs ``scoreboard battery [options]``.
"""
import sys

from satrefine.tools.scoreboard import main

if __name__ == "__main__":
    sys.exit(main(["battery", *sys.argv[1:]]))
