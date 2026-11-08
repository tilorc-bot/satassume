"""pytest plugin (-p ad_swap): the adapter modules' class names become adapters.rs' Rust classes, so tests/test_lra_adapter.py
and tests/test_euf_adapter.py run against them (adapters step, part B). Python's EUFAdapter stays reachable as
`_PyEUFAdapter` for the two calls the Rust class makes into it (`parse`, `interned`)."""


def pytest_configure(config):
    import sa_solver
    from satassume.theories.lra import lra_adapter
    from satassume.theories.euf import euf_adapter
    euf_adapter._PyEUFAdapter = euf_adapter.EUFAdapter
    lra_adapter.LRAAdapter = sa_solver.LRAAdapter
    euf_adapter.EUFAdapter = sa_solver.EUFAdapter
