"""Offline: satrefine's tools (scoreboard, differential, fuzz, oracle, ablation, generation, gates).

Run as ``python -m satrefine.tools.<name>``; refine never imports this package.
What the tools share is in :mod:`satrefine.tools.lib`.
"""
from satrefine.tools.lib.select import rerun_with  # noqa: F401  (kept for callers of the old place)
