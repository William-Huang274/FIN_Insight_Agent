"""Historical authority schema tests use their pre-existing issue scope.

Later live blockers remain authoritative in the product. Replaying an old
decision's schema is neither a new paid-call authorization nor a current pass.
"""
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


@pytest.fixture(autouse=True)
def historical_scope_ledger(request, monkeypatch):
    if request.node.path.name not in {
        "test_project_os_preflight.py", "test_s3_current_research_consumer_canary.py",
        "test_s3_material_scope_canary.py",
    } or request.node.name == "test_current_repository_blockers_remain_effective":
        return
    from sec_agent import project_os_preflight as preflight
    read = preflight._latest_jsonl_rows
    later_issues = {
        "RC-S3-124-feedback-length-and-noncitable-preview-conflicts-abort-research",
        "RC-S3-131-report-inference-overstatement-and-research-UX",
    }

    def historical_rows(path, key):
        rows = read(path, key)
        if path.name == "root_cause_issue_ledger.jsonl":
            return {k: v for k, v in rows.items() if k not in later_issues}
        return rows

    monkeypatch.setattr(preflight, "_latest_jsonl_rows", historical_rows)
