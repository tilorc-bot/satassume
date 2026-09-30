"""History-dependence testing for satassume.

The property under test: the answer of ``satassume.sympy_api.ask(prop,
assumptions, engine)`` must be a function of ``prop``, ``assumptions``,
the engine's declared configuration and the registered extensions and
theory adapters only.  It must not depend on what was asked before in the
same process or engine, on what is cached or evicted, on which sessions
exist or were reused, or on ``PYTHONHASHSEED``.

Modules
-------
``state``       inventory of the state that outlives a query, engine
                configurations (including presets that stress every bounded
                cache and reuse threshold), ``reset_module_state()``
``outcomes``    the four-valued answer (True / False / None / ValueError)
``checker``     the differential checker: a stream of queries in one
                long-lived engine against a clean reference, several stream
                orders, ddmin shrinking, attribution to the carrying state
                and a family tag, the cache audit, repro scripts,
                subprocess and hash-seed confirmation
``generators``  seeded random and Hypothesis generators over the engine's
                whole feature surface
``profiles``    stream shapes aimed at the engine's state (shared conjuncts,
                long sessions, registrations, trigger/observer pairs)
``lazy``        triggers and observers of the capabilities a session
                switches on lazily (relation glue, predicate transfer)
``registry``    the custom-predicate registrations a stream can switch
``corpus``      replay of ``queries.jsonl`` (``tools/record_queries.py``)
                and of refine-driven query streams
``sympy_io``    srepr round trips
``selfcheck``   optional runtime self-check (``selfcheck.install()``)
``__main__``    the command line: ``python -m harness --help``

See ``harness/README.md``.
"""
