from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "apps" / "workbench" / "frontend" / "vite" / "src"


def _source(relative_path: str) -> str:
    return (FRONTEND / relative_path).read_text(encoding="utf-8")


def test_vt2_frontend_routes_numeric_and_workpaper_without_local_fallback() -> None:
    shell = _source("app/AppShell.tsx")
    integrity = _source("api/integrity.ts")

    assert 'kind: "numbers"' in shell
    assert 'kind: "workpaper"' in shell
    assert "/numbers" in shell
    assert "/workpaper" in shell
    assert "NumericWorkbench" in shell
    assert "WorkpaperReview" in shell
    assert 'integrity/numeric' in integrity
    assert 'workpaperPath(caseId)' in integrity
    assert "localStorage" not in shell + integrity


def test_vt2_evidence_exposes_exact_bounded_repair_action_and_outcome() -> None:
    api = _source("api/evidence.ts")
    view = _source("features/evidence-workbench/EvidenceWorkbench.tsx")

    for field in (
        "expected_workspace_version",
        "actor_ref",
        "idempotency_key",
        "repair_outcomes",
        "repair_completed_count",
        "outcome_boundary",
    ):
        assert field in api
    assert "execute-repair" in api
    assert "Run bounded source repair" in view
    assert "Source-repaired candidate" in view
    assert "Open numeric analysis" in view
    assert "keyForAttempt" in view and "mapIdempotencyKey" in view


def test_vt2_numeric_wire_preserves_exact_parser_fact_trace_and_promotion_fields() -> None:
    api = _source("api/integrity.ts")
    view = _source("features/numeric-workbench/NumericWorkbench.tsx")

    for top_level in (
        "case_id",
        "numeric_workspace_id",
        "numeric_workspace_version",
        "evidence_workspace_id",
        "evidence_workspace_version",
        "status",
        "facts",
        "counts",
        "hard_boundaries",
    ):
        assert top_level in api
    for fact_field in (
        "cell_id",
        "evidence_slot_id",
        "candidate_id",
        "parser_candidate_id",
        "normalized_fact_id",
        "numeric_trace_id",
        "promotion_decision_id",
        "entity_ref",
        "period",
        "row_label",
        "normalized_value",
        "output_value",
        "unit",
        "scale_multiplier",
        "source_coordinate",
        "metric_definition_ref",
        "program_steps",
        "promotion_decision",
        "promotion_scope",
        "writer_citable",
        "boundary",
    ):
        assert fact_field in api
    assert "Compile numeric fixture" in view
    assert "Internal fixture only" in view
    assert "Not writer-citable" in view
    assert "Normalized fact table" in view
    assert "Program steps" in view


def test_vt2_workpaper_wire_and_lead_review_bind_exact_content() -> None:
    api = _source("api/integrity.ts")
    view = _source("features/workpaper-review/WorkpaperReview.tsx")

    for top_level in (
        "workpaper_id",
        "workpaper_version",
        "content_digest",
        "evidence_workspace_id",
        "numeric_workspace_id",
        "judgments",
        "lead_review",
        "writer_admission",
        "hard_boundaries",
    ):
        assert top_level in api
    for judgment_field in (
        "judgment_id",
        "cell_id",
        "owner_role",
        "judgment_status",
        "confidence",
        "judgment",
        "evidence_refs",
        "numeric_refs",
        "repair_outcome_refs",
        "counter_thesis",
        "what_would_change",
        "remaining_gaps",
    ):
        assert judgment_field in api
    for command_field in (
        "expected_workpaper_version",
        "expected_content_digest",
        "decision",
        "reason",
        "actor_ref",
        "idempotency_key",
    ):
        assert command_field in api
    assert "admit_fixture_writer_preview" in api + view
    assert "return_for_repair" in api + view
    assert "Fixture-only writer admission" in view
    assert "No writer execution" in view


def test_vt2_frontend_covers_remote_states_and_stable_mutation_retry() -> None:
    sources = "\n".join(
        _source(path)
        for path in (
            "features/evidence-workbench/EvidenceWorkbench.tsx",
            "features/numeric-workbench/NumericWorkbench.tsx",
            "features/workpaper-review/WorkpaperReview.tsx",
        )
    )

    for state in ("loading", "empty", "offline", "permission", "conflict", "stale", "error"):
        assert f'"{state}"' in sources
    assert "crypto.randomUUID()" in sources
    assert "fingerprint" in sources
    assert "localStorage" not in sources


def test_vt2_css_is_dense_and_has_mobile_constraints() -> None:
    css = _source("app/p02-shell.css")

    assert ".vt2-split-layout" in css
    assert ".vt2-workpaper-layout" in css
    assert ".vt2-fact-table" in css
    assert ".vt2-judgment-list" in css
    assert "@media (max-width: 420px)" in css
    assert "overflow-x: auto" in css
