from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    NarrativeQualityPolicy,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _input_pack,
)
from test_fin_0_1_s3_t09_research_lead_v5_compact_scoped_reference_dual_capacity_zero_call_implementation import (
    _CompactV5FullFakeProvider,
    _v5_admission,
)
from test_fin_0_1_s3_t09_specialist_v7_contract_convergence import (
    _semantic_only_mutation,
)


def _layered_narratives() -> list[tuple[str, str]]:
    return [
        ("cross_cell_dependencies", "x" * 571),
        ("cross_cell_dependencies", "x" * 533),
        ("cross_cell_dependencies", "x" * 528),
        *[("conflict_adjudications", "x" * 120) for _ in range(9)],
        ("variant_view", "x" * 120),
        *[("remaining_gaps", "x" * 120) for _ in range(4)],
    ]


def test_profile_v4_preserves_v3_and_reclassifies_character_limits() -> None:
    assert (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3
        .research_lead_narrative_character_limits_terminal
        is True
    )
    assert S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF.endswith(":v4")
    assert (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4
        .research_lead_narrative_character_limits_terminal
        is False
    )
    assert (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4
        .research_lead_narrative_hard_max_characters
        == 512
    )
    assert (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4
        .research_lead_aggregate_narrative_max_characters
        == 3200
    )
    assert (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4
        .research_lead_provider_raw_max_utf8_bytes
        == 8192
    )
    assert (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4
        .research_lead_canonical_alias_max_utf8_bytes
        == 6000
    )


def test_layered_policy_retains_571_533_528_and_aggregate_exceedance() -> None:
    observations, hard = NarrativeQualityPolicy.assess(
        _layered_narratives(),
        target_characters=320,
        hard_max_characters=512,
        length_exceedance_is_terminal=False,
        aggregate_target_characters=3200,
    )

    assert hard == {}
    assert {
        row["quality_code"] for row in observations
    } == {
        "narrative_quality_ceiling_exceeded",
        "narrative_aggregate_quality_ceiling_exceeded",
    }
    field = next(
        row
        for row in observations
        if row["quality_code"] == "narrative_quality_ceiling_exceeded"
    )
    aggregate = next(
        row
        for row in observations
        if row["quality_code"]
        == "narrative_aggregate_quality_ceiling_exceeded"
    )
    assert field["failing_item_count"] == 3
    assert field["maximum_observed_unicode_characters"] == 571
    assert aggregate["maximum_observed_unicode_characters"] == 3312
    assert all(row["terminal"] is False for row in observations)
    assert all(
        row["quality_contract_ref"]
        == NarrativeQualityPolicy.layered_contract_ref
        for row in observations
    )


def test_profile_v4_request_marks_characters_soft_and_bytes_hard() -> None:
    _, by_cell = _shared_local_id_specialists()
    specialists = list(by_cell.values())
    surface = S3ThreeCellBoundedAgentExecutor._derive_scoped_identity_surface(
        specialists
    )
    table = S3ThreeCellBoundedAgentExecutor._compact_scoped_alias_table(
        specialists,
        surface,
    )
    digests = {
        str(row["program_cell_id"]): canonical_digest(row)
        for row in specialists
    }
    heads = DeepSeekS3ThreeCellNodeExecutor._derive_research_lead_cell_heads(
        specialists,
        digests,
        research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4,
    )
    capacity = DeepSeekS3ThreeCellNodeExecutor._research_lead_v5_capacity_envelope(
        alias_table=table,
        cell_heads=heads,
        research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4,
    )
    system, request, _ = DeepSeekS3ThreeCellNodeExecutor._research_lead_v5_request(
        {
            "input_digest": "fixture",
            "lead_contract": {"fixture": True},
            "specialist_outputs": specialists,
            "scoped_identity_surface": surface,
        },
        heads,
        research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4,
        capacity=capacity,
    )

    constraints = request["output_constraints"]
    assert constraints["narrative_hard_maximum_exceedance_is_terminal"] is False
    assert (
        constraints["aggregate_narrative_maximum_exceedance_is_terminal"]
        is False
    )
    assert constraints["ordinary_character_limits_protect_hard_capacity"] is False
    assert constraints["maximum_provider_raw_wire_utf8_bytes"] == 8192
    assert constraints["maximum_canonical_alias_segment_utf8_bytes"] == 6000
    assert "non-terminal quality-ceiling" in system
    assert "byte capacities remain mandatory" in system


class _LayeredLongLeadProvider(_CompactV5FullFakeProvider):
    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        response = dict(super().__call__(**kwargs))
        request = json.loads(kwargs["messages"][1]["content"])
        if request["node_id"] != "research_lead":
            return response
        output = json.loads(str(response["content"]))
        output["cross_cell_dependencies"] = [
            dict(output["cross_cell_dependencies"][0]) for _ in range(3)
        ]
        output["conflict_adjudications"] = [
            dict(output["conflict_adjudications"][0]) for _ in range(3)
        ]
        output["remaining_gaps"] = [
            dict(output["remaining_gaps"][0]) for _ in range(4)
        ]
        for row, length in zip(
            output["cross_cell_dependencies"],
            (571, 533, 528),
            strict=True,
        ):
            row["statement"] = "x" * length
        for row in output["conflict_adjudications"]:
            row["terminal_state_summary"] = "x" * 120
            row["resolution_status"] = "x" * 120
            row["statement"] = "x" * 120
        output["variant_view"]["statement"] = "x" * 120
        for row in output["remaining_gaps"]:
            row["statement"] = "x" * 120
        response["content"] = json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
        )
        return response


def test_profile_v4_full_fake_path_keeps_output_and_builds_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _shared_local_id_specialists()
    input_pack = _input_pack(cells)
    admission = _v5_admission(input_pack).model_copy(
        update={"research_profile_ref": S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF}
    )
    fake = _LayeredLongLeadProvider(
        specialists,
        mutation=_semantic_only_mutation,
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")

    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={"research_run_id": "fixture-v4-layered-quality-run"},
    )

    assert result.terminal_reason == (
        "s3_bounded_agent_three_cell_execution_succeeded"
    )
    assert len(result.artifacts) == 9
    artifacts = {
        artifact.artifact_type: artifact.payload
        for artifact in result.artifacts
    }
    manifest_findings = artifacts[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE][
        "quality_observations"
    ]
    judgment_findings = artifacts[BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE][
        "quality_observations"
    ]
    assert judgment_findings == manifest_findings
    assert {
        row["quality_code"] for row in manifest_findings
    } == {
        "narrative_quality_ceiling_exceeded",
        "narrative_aggregate_quality_ceiling_exceeded",
    }
    assert all(row["node_id"] == "research_lead" for row in manifest_findings)
