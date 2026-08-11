from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_workbench_polling_is_scoped_to_current_research_execution() -> None:
    source = (
        REPO_ROOT
        / "apps"
        / "workbench"
        / "frontend"
        / "vite"
        / "src"
        / "app"
        / "WorkbenchNext.tsx"
    ).read_text(encoding="utf-8")

    assert "const [executionPolling, setExecutionPolling] = useState(false)" in source
    assert "onExecutionQueued={startExecutionPolling}" in source
    assert "onExecutionQueued();" in source
    assert "const activeRun = bundle.data.runProjection?.runs.some" in source
    assert "executionPolling && activeWorkUnit" in source
    assert (
        'const active = bundle.data.workUnits?.work_units.some((unit) => '
        '/pending|running/.test(unit.state))'
    ) not in source
