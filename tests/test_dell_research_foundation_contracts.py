from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from sec_agent.research_foundation.contracts import (
    DEFAULT_DELL_REFERENCE_VERTICAL_FOUNDATION_PATH,
    DellReferenceVerticalFoundation,
    DellResearchMethodPackage,
    DellResearchRunScope,
    bind_dell_research_method,
    canonical_sha256,
    load_dell_reference_vertical_foundation,
    project_dell_research_method,
)


def _raw_foundation() -> dict[str, object]:
    return json.loads(
        DEFAULT_DELL_REFERENCE_VERTICAL_FOUNDATION_PATH.read_text(encoding="utf-8")
    )


def test_repository_foundation_loads_with_cross_references() -> None:
    foundation = load_dell_reference_vertical_foundation()

    assert foundation.case_identity.case_id == "DELL_AI_INFRA_REFERENCE_VERTICAL"
    assert len(foundation.question_branches) == 9
    assert len(foundation.source_families) == 11
    assert len(foundation.formulas) == 10
    assert foundation.answer_policy.contains_case_answer is False
    assert foundation.answer_policy.contains_target_company_forecast is False
    assert foundation.answer_policy.contains_hidden_gold is False


def test_loader_rejects_extra_fields(tmp_path: Path) -> None:
    raw = _raw_foundation()
    raw["case_answer"] = "not allowed"
    path = tmp_path / "foundation.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_dell_reference_vertical_foundation(path)


@pytest.mark.parametrize(
    "policy_field",
    [
        "contains_case_answer",
        "contains_target_company_forecast",
        "contains_hidden_gold",
    ],
)
def test_foundation_rejects_answer_forecast_or_hidden_gold(
    policy_field: str,
) -> None:
    raw = _raw_foundation()
    answer_policy = raw["answer_policy"]
    assert isinstance(answer_policy, dict)
    answer_policy[policy_field] = True

    with pytest.raises(ValidationError):
        DellReferenceVerticalFoundation.model_validate_json(
            json.dumps(raw, ensure_ascii=False)
        )


def test_foundation_rejects_dangling_branch_reference() -> None:
    raw = _raw_foundation()
    branches = raw["question_branches"]
    assert isinstance(branches, list)
    assert isinstance(branches[0], dict)
    branches[0]["formula_ids"] = ["F_DOES_NOT_EXIST"]

    with pytest.raises(ValidationError, match="unknown_formula_for_Q1_ISSUER_TRUTH"):
        DellReferenceVerticalFoundation.model_validate_json(
            json.dumps(raw, ensure_ascii=False)
        )


def test_projection_contains_only_selected_method_dependencies() -> None:
    foundation = load_dell_reference_vertical_foundation()

    package = project_dell_research_method(
        foundation,
        ["Q3_UNITS_ASP_PVM", "Q7_EXPORT_CONTROL_CHINA"],
    )

    assert package.method.selected_branch_ids == (
        "Q3_UNITS_ASP_PVM",
        "Q7_EXPORT_CONTROL_CHINA",
    )
    assert {row.source_family_id for row in package.method.source_families} == {
        "F1_SEC_ISSUER_FACTS",
        "F2_DELL_IR_EARNINGS",
        "F3_DELL_PRODUCT_SUPPORT",
        "F5_PUBLIC_PROCUREMENT",
        "F6_COMPUTE_PLATFORM_SUPPLIERS",
        "F10_EXPORT_CONTROL_AND_POLICY",
    }
    assert {row.formula_id for row in package.method.formulas} == {
        "F_PVM_EXACT",
        "F_PVM_SCENARIO",
    }
    projected = package.method.model_dump(mode="json")
    assert "answer_policy" not in projected
    assert "recorded_at" not in projected
    assert "status" not in projected


def test_projection_digest_is_stable_for_same_branch_set() -> None:
    foundation = load_dell_reference_vertical_foundation()

    first = project_dell_research_method(
        foundation,
        ["Q7_EXPORT_CONTROL_CHINA", "Q3_UNITS_ASP_PVM"],
    )
    second = project_dell_research_method(
        foundation,
        [
            "Q3_UNITS_ASP_PVM",
            "Q7_EXPORT_CONTROL_CHINA",
            "Q3_UNITS_ASP_PVM",
        ],
    )

    assert first == second
    assert first.method_sha256 == canonical_sha256(first.method)
    assert len(first.method_sha256) == 64


def test_method_package_rejects_tampered_digest() -> None:
    foundation = load_dell_reference_vertical_foundation()
    package = project_dell_research_method(foundation, ["Q1_ISSUER_TRUTH"])
    raw = package.model_dump(mode="json")
    raw["method_sha256"] = "0" * 64

    with pytest.raises(ValidationError, match="method_sha256_mismatch"):
        DellResearchMethodPackage.model_validate_json(
            json.dumps(raw, ensure_ascii=False)
        )


def test_method_binding_seals_run_scope_and_rejects_tampering() -> None:
    binding = bind_dell_research_method(
        load_dell_reference_vertical_foundation(),
        ["Q1_ISSUER_TRUTH", "Q9_COUNTEREVIDENCE_WWC"],
        research_as_of=datetime(2026, 9, 2, tzinfo=timezone.utc),
        data_snapshot_id="DELL-FOUNDATION-SNAPSHOT-01",
        execution_attempt_id="DELL-CONTRACT-TEST-A01",
    )
    assert binding.run_scope.method_sha256 == binding.method_package.method_sha256
    assert binding.run_scope.selected_branch_ids == (
        "Q1_ISSUER_TRUTH",
        "Q9_COUNTEREVIDENCE_WWC",
    )

    raw = binding.run_scope.model_dump(mode="json")
    raw["data_snapshot_id"] = "TAMPERED"
    with pytest.raises(ValidationError, match="run_scope_digest_mismatch"):
        DellResearchRunScope.model_validate(raw)


@pytest.mark.parametrize("branch_ids", [[], ["Q_DOES_NOT_EXIST"]])
def test_projection_rejects_empty_or_unknown_branch_ids(
    branch_ids: list[str],
) -> None:
    foundation = load_dell_reference_vertical_foundation()

    with pytest.raises(ValueError):
        project_dell_research_method(foundation, branch_ids)
