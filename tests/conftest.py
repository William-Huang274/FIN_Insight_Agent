"""Private source replay is opt-in; current product tests use public fixtures."""
import pytest


def pytest_addoption(parser):
    parser.addoption("--run-private-data", action="store_true", default=False,
                     help="Run tests requiring the original private qualification mounts.")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-private-data"):
        return
    unavailable = pytest.mark.skip(reason="private qualification replay; use --run-private-data with original mounts")
    for item in items:
        if item.get_closest_marker("local_data_integration") or item.get_closest_marker("requires_local_data"):
            item.add_marker(unavailable)
