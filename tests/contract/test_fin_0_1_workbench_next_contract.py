from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "apps" / "workbench" / "frontend" / "vite" / "src"


def _source(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def test_next_workbench_is_isolated_behind_versioned_routes() -> None:
    shell = _source("app/AppShell.tsx")
    next_ui = _source("app/WorkbenchNext.tsx")

    assert "isWorkbenchNextPath" in shell
    assert '<WorkbenchNext online={online}' in shell
    assert 'pathname === "/next"' in next_ui
    assert '"/next/tasks"' in next_ui
    for surface in ("run", "evidence", "workpaper", "review", "report", "inspect"):
        assert f'"{surface}"' in next_ui


def test_next_workbench_composes_existing_typed_read_models() -> None:
    next_ui = _source("app/WorkbenchNext.tsx")

    expected_reads = (
        "caseApi.getCase(caseId)",
        "planningApi.getDecisionSurface(caseId)",
        "executionApi.listWorkUnits(caseId)",
        "executionApi.getActivityTrace(caseId)",
        "evidenceApi.getLocalResearchPreview(caseId)",
        "evidenceApi.getLocalAnalysisPreview(caseId)",
        "evidenceApi.getEvidenceWorkbench(caseId)",
        "integrityApi.getNumericWorkbench(caseId)",
        "integrityApi.getWorkpaper(caseId)",
        "deliverablesApi.getDeliverableHead(caseId)",
        "deliverablesApi.getCaseTrace(caseId)",
        "baselineApi.list(caseId)",
    )
    for expected in expected_reads:
        assert expected in next_ui


def test_next_run_surface_does_not_fake_model_or_operational_execution() -> None:
    next_ui = _source("app/WorkbenchNext.tsx")

    assert 'copy("运行请求未准入", "Run request not admitted")' in next_ui
    assert 'model_calls' in next_ui
    assert 'case_mutation_calls' in next_ui
    assert "compileDecisionSurface(" not in next_ui
    assert "compileNumericFixture(" not in next_ui
    assert "compileWorkpaperFixture(" not in next_ui
    assert "compileDeliverablePreviewFixture(" not in next_ui


def test_exact_human_review_writes_only_after_explicit_form_actions() -> None:
    next_ui = _source("app/WorkbenchNext.tsx")

    assert "async function startReview()" in next_ui
    assert 'baselineApi.start(caseId, "human_senior_internal"' in next_ui
    assert "baselineApi.submitAnalyst" in next_ui
    assert "baselineApi.submitSenior" in next_ui
    assert "exact_digest_confirmed: checks.digest" in next_ui
    assert "disabled={saving || !checks.digest}" in next_ui


def test_next_workbench_has_an_independent_responsive_visual_system() -> None:
    next_ui = _source("app/WorkbenchNext.tsx")
    css = _source("app/workbench-next.css")

    assert 'import "./workbench-next.css"' in next_ui
    assert ".next-run-layout" in css
    assert ".next-evidence-grid" in css
    assert ".next-workpaper-document" in css
    assert ".next-report-document" in css
    assert "@media (max-width: 900px)" in css
