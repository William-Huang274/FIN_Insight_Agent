from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
    BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3ScopedIdentityContractError,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
)
from apps.workbench.backend.application.bounded_agent_identity_policies import (
    CellScopedResearchIdentityPolicy,
    S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF,
    ScopedIdentityViolation,
)
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
)
from sec_agent.canonical_runtime.facade import ArtifactValidationError
from test_fin_0_1_s2_t02_bounded_agent_profile import (
    _accepted_case,
    _create_work_unit,
    _t02_admission,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _input_pack,
    _lead_output,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_specialist_transport import (
    _SegmentedOwnerGradeFakeProvider,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_closed_context_authority_repair import (
    _production_surfaces,
)
from test_fin_0_1_s3_t09_specialist_v7_contract_convergence import (
    _semantic_only_mutation,
)


def _shared_local_id_specialists() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    cells, specialists = _production_surfaces()
    for specialist in specialists.values():
        specialist["judgment_layer"][0]["claim_id"] = "claim-local-001"
        specialist["what_would_change"][0]["task_id"] = "wwc-local-001"
        specialist["what_would_change"][0]["claim_id"] = "claim-local-001"
    return cells, specialists


def _v4_admission(input_pack: Any) -> S3ThreeCellBoundedAgentAdmission:
    return S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-s3-t09-cross-cell-scoped-identity-v4",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        execution_enabled=True,
        execution_mode="fixture_only_cross_cell_scoped_identity_v4",
        research_profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
        case_id=input_pack.case_id,
        case_version=input_pack.case_version,
        as_of=input_pack.as_of,
        input_digest=input_pack.input_digest,
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=BOUNDED_DEEPSEEK_BETA_BASE_URL,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        research_lead_transport_ref=S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF,
        memo_writer_transport_ref=S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
        scoped_identity_contract_ref=S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF,
        provider_output_capture_policy_ref=S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        max_semantic_model_calls=12,
        max_provider_calls=12,
        max_network_calls=12,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=4200,
        lead_max_output_tokens=1800,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
    )


def _scoped_ref(kind: str, cell_id: str, local_id: str) -> dict[str, str]:
    return CellScopedResearchIdentityPolicy.ref(kind, cell_id, local_id).to_payload()


class _ScopedV4FullFakeProvider(_SegmentedOwnerGradeFakeProvider):
    @staticmethod
    def _response(output: Mapping[str, Any], call_number: int) -> dict[str, Any]:
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": json.dumps(output, ensure_ascii=False, sort_keys=True),
            "input_tokens": 10,
            "output_tokens": 100,
            "total_tokens": 110,
            "call_id": f"fixture-scoped-v4-{call_number}",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "latency_ms": 1,
            "transport_attempt_count": 1,
            "raw_response": {
                "usage": {
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 10,
                }
            },
        }

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        request = json.loads(kwargs["messages"][1]["content"])
        node_id = str(request["node_id"])
        if node_id == "memo_writer":
            self.calls.append({"kwargs": dict(kwargs), "request": request})
            output = {
                "claim_renderings": [
                    {
                        "claim_ref": deepcopy(claim["claim_ref"]),
                        "analysis_text_zh_cn": "该判断严格保留上游事实和范围边界。",
                    }
                    for claim in request["analysis_input"]["claims"]
                ]
            }
            return self._response(output, len(self.calls))

        response = dict(super().__call__(**kwargs))
        if node_id != "research_lead":
            return response

        specialists = request["analysis_input"]["specialist_outputs"]
        output = _lead_output(list(specialists))
        output.pop("cell_heads")
        claim_refs = [
            _scoped_ref(
                "claim",
                str(specialist["program_cell_id"]),
                str(claim["claim_id"]),
            )
            for specialist in specialists
            for claim in specialist["judgment_layer"]
        ]
        task_refs = [
            _scoped_ref(
                "what_would_change",
                str(specialist["program_cell_id"]),
                str(task["task_id"]),
            )
            for specialist in specialists
            for task in specialist["what_would_change"]
        ]
        output["cross_cell_dependencies"][0]["claim_ids"] = deepcopy(claim_refs)
        output["conflict_adjudications"][0]["involved_claim_ids"] = deepcopy(
            claim_refs
        )
        output["variant_view"]["claim_ids"] = deepcopy(claim_refs)
        output["variant_view"]["what_would_change_task_ids"] = deepcopy(task_refs)
        output["remaining_gaps"][0]["claim_ids"] = deepcopy(claim_refs)
        output["remaining_gaps"][0]["what_would_change_task_ids"] = deepcopy(
            task_refs
        )
        response["content"] = json.dumps(
            output, ensure_ascii=False, sort_keys=True
        )
        return response


def test_scoped_identity_allows_same_local_ids_in_different_cells() -> None:
    _, specialists = _shared_local_id_specialists()
    surface = CellScopedResearchIdentityPolicy.derive_surface(
        list(specialists.values())
    )
    assert isinstance(surface, dict)
    indexes = CellScopedResearchIdentityPolicy.index_surface(surface)
    assert isinstance(indexes, dict)
    assert len(indexes["claim"]) == 3
    assert len(indexes["what_would_change"]) == 3
    assert surface["raw_local_id_cross_cell_ambiguity_counts"] == {
        "claim": 1,
        "what_would_change": 1,
    }


def test_scoped_identity_is_entity_period_and_fact_authority_agnostic() -> None:
    specialists = [
        {
            "program_cell_id": "amd-demand",
            "fact_layer": [
                {
                    "fact_id": "fact-evidence",
                    "support_type": "Evidence",
                    "support_refs": ["evidence:amd-10q"],
                }
            ],
            "judgment_layer": [{"claim_id": "claim-001"}],
            "what_would_change": [
                {"task_id": "task-001", "claim_id": "claim-001"}
            ],
            "scope_fixture": {
                "entity_ref": "AMD",
                "period": "2026-Q1",
            },
        },
        {
            "program_cell_id": "amd-supply",
            "fact_layer": [
                {
                    "fact_id": "fact-numeric",
                    "support_type": "Numeric",
                    "support_refs": ["numeric:amd-2026-q1"],
                }
            ],
            "judgment_layer": [{"claim_id": "claim-001"}],
            "what_would_change": [
                {"task_id": "task-001", "claim_id": "claim-001"}
            ],
            "scope_fixture": {
                "entity_ref": "AMD",
                "period": "2026-Q1",
            },
        },
    ]
    surface = CellScopedResearchIdentityPolicy.derive_surface(specialists)
    assert isinstance(surface, dict)
    assert CellScopedResearchIdentityPolicy.index_surface(surface)
    assert surface["raw_local_id_cross_cell_ambiguity_counts"] == {
        "claim": 1,
        "what_would_change": 1,
    }
    assert {
        row["fact_layer"][0]["support_type"] for row in specialists
    } == {"Evidence", "Numeric"}


def test_scoped_identity_rejects_wrong_identity_kind() -> None:
    violation = CellScopedResearchIdentityPolicy.parse(
        {
            "identity_kind": "what_would_change",
            "program_cell_id": "cell-a",
            "local_id": "claim-001",
        },
        expected_kind="claim",
    )
    assert violation == ScopedIdentityViolation(
        identity_kind="claim",
        failure_subtype="scoped_ref_mismatch",
        failing_item_count=1,
    )


@pytest.mark.parametrize(
    ("field", "kind"),
    (("judgment_layer", "claim"), ("what_would_change", "what_would_change")),
)
def test_scoped_identity_rejects_same_cell_duplicate(
    field: str,
    kind: str,
) -> None:
    _, specialists = _shared_local_id_specialists()
    first = next(iter(specialists.values()))
    first[field].append(deepcopy(first[field][0]))
    violation = CellScopedResearchIdentityPolicy.derive_surface(
        list(specialists.values())
    )
    assert violation == ScopedIdentityViolation(
        identity_kind=kind,
        failure_subtype="duplicate_local_id_same_cell",
        failing_item_count=1,
    )


def test_v4_lead_rejects_raw_local_id_and_unknown_scoped_ref() -> None:
    _, specialists_by_cell = _shared_local_id_specialists()
    specialists = list(specialists_by_cell.values())
    surface = S3ThreeCellBoundedAgentExecutor._derive_scoped_identity_surface(
        specialists
    )
    digests = {
        str(row["program_cell_id"]): "0" * 64 for row in specialists
    }
    raw = _lead_output(specialists)
    raw["cell_heads"] = [
        {
            **head,
            "specialist_output_digest": digests[str(head["program_cell_id"])],
        }
        for head in raw["cell_heads"]
    ]
    with pytest.raises(
        S3ScopedIdentityContractError,
        match="raw_local_id_cross_cell_ambiguous",
    ):
        S3ThreeCellBoundedAgentExecutor._validate_lead_output(
            raw,
            digests,
            specialist_outputs=specialists,
            scoped_identity_surface=surface,
            output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        )

    typed = deepcopy(raw)
    bad_ref = _scoped_ref("claim", "unknown-cell", "claim-local-001")
    for dependency in typed["cross_cell_dependencies"]:
        dependency["claim_ids"] = [bad_ref]
    with pytest.raises(S3ScopedIdentityContractError, match="unknown_scoped_ref"):
        S3ThreeCellBoundedAgentExecutor._validate_lead_output(
            typed,
            digests,
            specialist_outputs=specialists,
            scoped_identity_surface=surface,
            output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        )


def test_v4_admission_is_exactly_bound_and_historical_payload_is_unchanged() -> None:
    cells, _ = _shared_local_id_specialists()
    input_pack = _input_pack(cells)
    admission = _v4_admission(input_pack)
    admission.assert_profile_admissible()
    assert admission.digest_payload()["scoped_identity_contract_ref"] == (
        S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
    )
    with pytest.raises(
        ValueError,
        match="output_v4_scoped_identity_binding_required",
    ):
        admission.model_copy(
            update={"scoped_identity_contract_ref": None}
        ).assert_profile_admissible()

    historical = S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-historical-digest-shape",
        execution_enabled=False,
        execution_mode="fixture_historical_digest_shape",
    )
    assert "scoped_identity_contract_ref" not in historical.digest_payload()


def test_v4_full_fake_provider_preserves_scoped_refs_across_six_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _shared_local_id_specialists()
    input_pack = _input_pack(cells)
    admission = _v4_admission(input_pack)
    fake = _ScopedV4FullFakeProvider(
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
        run_identity={
            "research_run_id": "fixture-run-scoped-identity-v4",
            "attempt_id": "fixture-attempt-scoped-identity-v4",
        },
    )

    assert result.terminal_reason == "s3_bounded_agent_three_cell_execution_succeeded"
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    judgment = next(
        row.payload
        for row in result.artifacts
        if row.artifact_type == BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE
    )
    assert judgment["scoped_identity_surface"][
        "raw_local_id_cross_cell_ambiguity_counts"
    ] == {"claim": 1, "what_would_change": 1}
    lead_refs = judgment["cross_cell_lead"]["variant_view"]["claim_ids"]
    assert len({tuple(ref.values()) for ref in lead_refs}) == 3
    assert all(set(ref) == {"identity_kind", "program_cell_id", "local_id"} for ref in lead_refs)
    report = next(
        row.payload["report"]
        for row in result.artifacts
        if row.artifact_type == BOUNDED_AGENT_REPORT_ARTIFACT_TYPE
    )
    assert len({tuple(ref.values()) for ref in report["exact_claim_refs"]}) == 3


class _ScopedTelemetryFailureProbe:
    def __init__(self, *, unsafe: bool = False) -> None:
        self.unsafe = unsafe

    def execute(
        self,
        input_pack: Any,
        admission: Any,
        *,
        run_identity: Mapping[str, str],
    ) -> Any:
        telemetry: dict[str, Any] = {
            "identity_kind": "claim",
            "failure_subtype": "unknown_scoped_ref",
            "failing_item_count": 1,
        }
        if self.unsafe:
            telemetry["raw_local_id"] = "secret-local-id"
        raise BoundedAgentExecutionError(
            "research_lead",
            usage_receipts=[],
            estimated_cost_usd=0.0,
            failure_codes=(
                "s3_bounded_cross_cell_scoped_identity_unknown_scoped_ref",
            ),
            scoped_identity_contract=telemetry,
        )


def test_scoped_identity_telemetry_persists_content_free(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "scoped-telemetry-runtime", repo_root=ROOT
    )
    app = create_app(
        tmp_path / "scoped-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_ScopedTelemetryFailureProbe(),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="scoped-telemetry")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="scoped-telemetry-bounded",
            work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        )
    assert response.status_code == 202
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    assert failed_event["payload"]["failure_observation"][
        "failure_telemetry"
    ] == {
        "scoped_identity_contract": {
            "identity_kind": "claim",
            "failure_subtype": "unknown_scoped_ref",
            "failing_item_count": 1,
        }
    }


def test_scoped_identity_telemetry_rejects_raw_local_id(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "unsafe-scoped-telemetry-runtime", repo_root=ROOT
    )
    app = create_app(
        tmp_path / "unsafe-scoped-telemetry.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_t02_admission(),
        bounded_agent_executor=_ScopedTelemetryFailureProbe(unsafe=True),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="unsafe-scoped-telemetry")
        with pytest.raises(
            ArtifactValidationError,
            match="research_run_failure_observation_not_secret_safe",
        ):
            _create_work_unit(
                client,
                case,
                plan,
                key="unsafe-scoped-telemetry-bounded",
                work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
            )


def test_zero_call_result_and_next_authority_are_frozen() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"].startswith(
        "pass_zero_call_cross_cell_scoped_identity"
    )
    assert set(result["observed_counts"].values()) == {0}
    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-CROSS-CELL-SCOPED-IDENTITY-"
        "FRESH-AGENT-PROOF-DECISION"
    )
