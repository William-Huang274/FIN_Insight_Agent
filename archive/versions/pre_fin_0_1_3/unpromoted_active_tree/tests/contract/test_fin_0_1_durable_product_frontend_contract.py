from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "apps" / "workbench" / "frontend" / "vite" / "src"


def _source(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def test_product_shell_exposes_real_research_and_exact_human_baseline_routes() -> None:
    shell = _source("app/AppShell.tsx")
    chrome = _source("app/AnalystWorkspaceChrome.tsx")
    task_center = _source("features/task-center/TaskCenter.tsx")

    assert 'kind: "humanBaseline"' in shell
    assert '/baseline' in shell
    assert 'copy("基线评测", "Baseline")' in chrome
    assert "getLocalResearchPreview(selectedCaseId)" in task_center
    assert "getLocalAnalysisPreview(selectedCaseId)" in task_center
    assert "task-center-board" in task_center


def test_human_baseline_ui_keeps_drafts_and_requires_exact_senior_confirmation() -> None:
    baseline = _source("features/human-baseline/HumanBaseline.tsx")
    api = _source("api/humanBaseline.ts")

    assert "localStorage.setItem" in baseline
    assert "exact_digest_confirmed" in baseline
    assert "Record exact human senior review" in baseline
    assert "baseline:review" in api
    assert "human-baseline/sessions" in api


def test_workpaper_and_writer_join_existing_research_without_changing_writer_authority() -> None:
    preview = _source("shared/LocalAnalysisPreview.tsx")

    assert "getLocalAnalysisPreview" in preview
    assert "getLocalResearchPreview" in preview
    assert 'copy("证据基础", "Evidence basis")' in preview
    assert 'copy("什么会改变判断", "What would change")' in preview
    assert 'copy("执行摘要", "Executive summary")' in preview
    assert 'copy("结论边界", "Conclusion boundary")' in preview
    assert 'copy("待验证", "To verify")' in preview
    assert "source_access_calls" in preview
    assert "api.getLocal" in preview
    assert "api.create" not in preview
    assert "api.update" not in preview
