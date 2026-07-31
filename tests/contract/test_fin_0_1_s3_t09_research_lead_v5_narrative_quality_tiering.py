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
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
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


def test_profile_v3_preserves_old_profiles_and_separates_target_from_hard_max() -> None:
    assert S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2.profile_ref.endswith(":v2")
    assert S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2.research_lead_narrative_target_characters == 320
    assert S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2.research_lead_narrative_hard_max_characters == 320
    assert S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF.endswith(":v3")
    assert S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3.research_lead_narrative_target_characters == 320
    assert S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3.research_lead_narrative_hard_max_characters == 512
    assert S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3.maximum_narrative_characters == 320
    assert S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3.research_lead_aggregate_narrative_max_characters == 3200


def test_failed_live_lengths_become_three_closed_non_terminal_findings_under_v3() -> None:
    fields = [
        ("cross_cell_dependencies", "x" * 388),
        ("cross_cell_dependencies", "x" * 343),
        ("variant_view", "x" * 423),
    ]
    observations, hard = NarrativeQualityPolicy.assess(
        fields,
        target_characters=320,
        hard_max_characters=512,
    )

    assert hard == {}
    assert sum(row["failing_item_count"] for row in observations) == 3
    assert {row["field_id"] for row in observations} == {
        "cross_cell_dependencies",
        "variant_view",
    }
    assert all(row["terminal"] is False for row in observations)
    assert all(row["raw_text_persisted"] is False for row in observations)


def test_legacy_profile_replay_counts_all_three_and_v3_still_fails_over_512() -> None:
    fields = [
        ("cross_cell_dependencies", "x" * 388),
        ("cross_cell_dependencies", "x" * 343),
        ("variant_view", "x" * 423),
    ]
    _, legacy_hard = NarrativeQualityPolicy.assess(
        fields,
        target_characters=320,
        hard_max_characters=320,
    )
    _, v3_hard = NarrativeQualityPolicy.assess(
        [("variant_view", "x" * 513)],
        target_characters=320,
        hard_max_characters=512,
    )

    assert sum(legacy_hard["item_over_max_unicode_characters"].values()) == 3
    assert v3_hard == {
        "item_over_max_unicode_characters": {"variant_view": 1}
    }


def test_v5_request_is_profile_driven_without_new_transport_version() -> None:
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
        research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3,
    )
    capacity = DeepSeekS3ThreeCellNodeExecutor._research_lead_v5_capacity_envelope(
        alias_table=table,
        cell_heads=heads,
        research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3,
    )
    _, request, binding = DeepSeekS3ThreeCellNodeExecutor._research_lead_v5_request(
        {
            "input_digest": "fixture",
            "lead_contract": {"fixture": True},
            "specialist_outputs": specialists,
            "scoped_identity_surface": surface,
        },
        heads,
        research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3,
        capacity=capacity,
    )

    constraints = request["output_constraints"]
    assert request["research_lead_transport_ref"].endswith(":v5")
    assert constraints["narrative_field_quality_target_unicode_characters"] == 320
    assert constraints["maximum_narrative_field_unicode_characters"] == 512
    assert constraints["narrative_target_exceedance_is_terminal"] is False
    assert constraints["narrative_hard_maximum_exceedance_is_terminal"] is True
    assert binding["research_lead_transport_ref"].endswith(":v5")


class _LongButSafeLeadProvider(_CompactV5FullFakeProvider):
    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        response = dict(super().__call__(**kwargs))
        request = json.loads(kwargs["messages"][1]["content"])
        if request["node_id"] != "research_lead":
            return response
        output = json.loads(str(response["content"]))
        output["cross_cell_dependencies"][0]["statement"] = "x" * 388
        output["remaining_gaps"][0]["statement"] = "x" * 343
        output["variant_view"]["statement"] = "x" * 423
        response["content"] = json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
        )
        return response


def test_full_fake_path_persists_quality_observations_without_blocking_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _shared_local_id_specialists()
    input_pack = _input_pack(cells)
    admission = _v5_admission(input_pack).model_copy(
        update={
            "research_profile_ref": (
                S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF
            )
        }
    )
    fake = _LongButSafeLeadProvider(
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
        run_identity={"research_run_id": "fixture-v3-quality-run"},
    )

    assert len(result.artifacts) == 9
    artifacts = {artifact.artifact_type: artifact.payload for artifact in result.artifacts}
    manifest_findings = artifacts[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE][
        "quality_observations"
    ]
    judgment_findings = artifacts[BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE][
        "quality_observations"
    ]
    assert sum(row["failing_item_count"] for row in manifest_findings) == 3
    assert judgment_findings == manifest_findings
    assert all(row["node_id"] == "research_lead" for row in manifest_findings)
