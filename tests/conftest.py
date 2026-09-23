"""Shared pytest configuration."""


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: long-running test, skipped unless enabled by an environment variable")
