from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "apps" / "workbench" / "frontend" / "vite" / "src"


def _source(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def test_workbench_defaults_to_chinese_and_keeps_an_explicit_english_switch() -> None:
    locale = _source("i18n/WorkbenchLocale.tsx")
    shell = _source("app/AnalystWorkspaceChrome.tsx")

    assert 'return saved === "en" || saved === "zh-CN" ? saved : "zh-CN"' in locale
    assert 'setLocale("zh-CN")' in shell
    assert 'setLocale("en")' in shell
    assert 'FinSight Workbench' in shell
    assert 'copy("演示数据已连接", "Demo data connected")' in shell


def test_primary_vertical_surfaces_consume_the_shared_locale_contract() -> None:
    paths = (
        "features/task-center/TaskCenter.tsx",
        "features/case-overview/CaseOverview.tsx",
        "features/decision-surface/DecisionSurface.tsx",
        "features/evidence-workbench/EvidenceWorkbench.tsx",
        "features/numeric-workbench/NumericWorkbench.tsx",
        "features/workpaper-review/WorkpaperReview.tsx",
        "features/deliverable-review/DeliverableReview.tsx",
        "features/activity-trace/ActivityTrace.tsx",
        "shared/RemoteStatus.tsx",
    )
    for path in paths:
        assert "useWorkbenchLocale" in _source(path), path


def test_research_question_and_analyst_workflow_are_primary_ui_concepts() -> None:
    shell = _source("app/AppShell.tsx")
    chrome = _source("app/AnalystWorkspaceChrome.tsx")
    cases = _source("features/task-center/TaskCenter.tsx")
    overview = _source("features/case-overview/CaseOverview.tsx")
    css = _source("app/p02-shell.css")

    for label in ("Overview", "Research questions", "Evidence", "Numbers", "Workpaper", "Deliverable", "Trace"):
        assert label in chrome
    assert "item.query" in cases
    assert "localizeFixtureText(workspace.query)" in overview
    assert ".analyst-workspace-shell.has-case" in css
    assert ".analyst-task-rail" in css
    assert ".analyst-context-drawer" in css
    assert "@media (max-width: 620px)" in css


def test_canonical_analyst_shell_keeps_routes_and_reads_side_panels_without_mutating_them() -> None:
    shell = _source("app/AppShell.tsx")
    chrome = _source("app/AnalystWorkspaceChrome.tsx")

    assert 'if (pathname === "/legacy")' in shell
    assert 'if (route.kind === "legacy")' in shell
    assert 'EvidenceApiClient' in chrome
    assert 'DeliverablesApiClient' in chrome
    assert 'getEvidenceWorkbench(caseId)' in chrome
    assert 'getDeliverableHead(caseId)' in chrome
    assert 'compileEvidenceFixture' not in chrome
    assert 'compileDeliverablePreviewFixture' not in chrome
    assert 'window.matchMedia("(min-width: 901px)").matches' in chrome
    assert "open={railOpen}" in chrome
    assert "open={drawerOpen}" in chrome


def test_missing_case_state_is_explained_without_exposing_raw_case_not_found_as_the_product_copy() -> None:
    activity = _source("features/activity-trace/ActivityTrace.tsx")
    evidence = _source("features/evidence-workbench/EvidenceWorkbench.tsx")

    for source in (activity, evidence):
        assert 'error.code === "case_not_found"' in source
        assert "找不到此研究案例" in source
    assert "Return to research cases" in activity


def test_real_candidate_analysis_is_visible_across_numeric_workpaper_and_writer_surfaces() -> None:
    api = _source("api/evidence.ts")
    preview = _source("shared/LocalAnalysisPreview.tsx")

    assert "getLocalAnalysisPreview" in api
    assert "local-analysis-preview" in api
    assert "deterministic_no_source_internal_composer" in api
    assert "受限真实研究链" in preview
    assert "source_access_calls" in preview
    assert 'view="numeric"' in _source("features/numeric-workbench/NumericWorkbench.tsx")
    assert 'view="workpaper"' in _source("features/workpaper-review/WorkpaperReview.tsx")
    assert 'view="writer"' in _source("features/deliverable-review/DeliverableReview.tsx")
