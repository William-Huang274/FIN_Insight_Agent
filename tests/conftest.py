"""Local data integration is opt-in; default tests use public fixtures."""
import pytest


def pytest_addoption(parser):
    parser.addoption("--run-private-data", action="store_true", default=False,
                     help="Run integration tests with explicitly configured local resources.")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-private-data"):
        return
    unavailable = pytest.mark.skip(reason="local research resources require --run-private-data")
    for item in items:
        if item.get_closest_marker("local_data_integration") or item.get_closest_marker("requires_local_data"):
            item.add_marker(unavailable)
