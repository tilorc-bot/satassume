"""Layer 0 of :mod:`satassume`: process-wide state.

The registry epoch (:mod:`.epoch`) and the memo tables keyed on it
(:mod:`.memos`).  Hides how cached results are invalidated: every cache
of the engine is either keyed on the epoch (or on a version counter) and
registered here, or owned by an engine; clearing and inventory go
through one place.  Owners register their own tables; nothing here names
a module above it.

Imports nothing from :mod:`satassume`, and no SymPy.
"""
