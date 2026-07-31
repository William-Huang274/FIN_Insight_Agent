from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    S3_FOUR_LAYER_VERIFIER_LAYERS,
    S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
    S3_THREE_CELL_PROGRAM_CELL_IDS,
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.case_service import CasePrincipal, CaseService
from apps.workbench.backend.application.evidence_service import EvidenceService
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
)
from apps.workbench.backend.application.local_research_service import (
    P36LocalResearchService,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s3_three_cell_bounded_agent_exact_input,
)
from sec_agent.canonical_runtime.models import canonical_digest


TENANT_ID = "tenant-fin01-s3-t09-preflight"
PROJECT_ID = "project-fin01-s3-t09-preflight"
ACTOR_ID = "analyst-fin01-s3-t09-preflight"
EXECUTION_IDENTITY = "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
RESULT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_deepseek_transport_exact_input_preflight_repair_v1_0.json"
)
BACKLOG = ROOT / "configs" / "releases" / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"
PERMISSIONS = frozenset(
    {
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "execution:write",
        "execution:read",
        "activity:read",
        "evidence:read",
    }
)


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": ",".join(sorted(PERMISSIONS)),
    }


def _principal() -> CasePrincipal:
    return CasePrincipal(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        actor_id=ACTOR_ID,
        permissions=PERMISSIONS,
    )


def _create_accepted_case(
    tmp_path: Path,
) -> tuple[CaseService, P36LocalResearchService, EvidenceService, dict[str, Any], dict[str, Any]]:
    case_service = CaseService.for_fixture_root(
        tmp_path / "canonical-runtime", repo_root=ROOT
    )
    local_service = P36LocalResearchService.from_case_service(
        case_service, repo_root=ROOT
    )
    evidence_service = EvidenceService.from_case_service(case_service, repo_root=ROOT)
    app = create_app(
        tmp_path / "setup-workbench.sqlite",
        p02_case_service=case_service,
        p03_evidence_service=evidence_service,
        p36_local_research_service=local_service,
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/cases",
            headers=_headers(),
            json={
                "query": "Execute the FIN 0.1 NVDA S3 T09 exact three-cell preflight fixture",
                "as_of": "2026-07-21T00:00:00Z",
                "language": "en",
                "source_policy_ref": "fixture:internal-only",
                "idempotency_key": "t09-preflight-case",
            },
        )
        assert created.status_code == 202, created.text
        case = created.json()
        compiled = client.post(
            f"/api/v1/cases/{case['case_id']}/planning/compile",
            headers=_headers(),
            json={
                "expected_case_version": case["case_version"],
                "expected_summary_version": case["summary_version"],
                "compiler_policy_ref": "fixture:p36-three-cell-v1",
                "pack_selection_ref": "fixture:p36-ai-infrastructure-v1",
                "actor_ref": ACTOR_ID,
                "idempotency_key": "t09-preflight-compile",
            },
        )
        assert compiled.status_code == 202, compiled.text
        accepted = client.post(
            f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
            headers=_headers(),
            json={
                "decision": "accept",
                "expected_case_version": case["case_version"],
                "expected_decision_surface_contract_version": compiled.json()[
                    "contract_version"
                ],
                "expected_checkpoint_version": compiled.json()["checkpoint_version"],
                "actor_ref": ACTOR_ID,
                "idempotency_key": "t09-preflight-accept",
            },
        )
        assert accepted.status_code == 202, accepted.text
    return case_service, local_service, evidence_service, case, accepted.json()


def _prepare(
    local_service: P36LocalResearchService,
    evidence_service: EvidenceService,
    case: Mapping[str, Any],
    accepted: Mapping[str, Any],
):
    return prepare_s3_three_cell_bounded_agent_exact_input(
        local_service,
        evidence_service,
        str(case["case_id"]),
        _principal(),
        decision_surface_contract_ref=str(accepted["contract_version_id"]),
        execution_identity=EXECUTION_IDENTITY,
    )


def _admission(prepared: Any, *, input_digest: str | None = None):
    return S3ThreeCellBoundedAgentAdmission(
        admission_id="fin01-s3-t09-deepseek-segmented-v1-preflight-fixture",
        execution_mode="exact_live_three_cell",
        execution_enabled=True,
        case_id=prepared.case_id,
        case_version=prepared.case_version,
        as_of=prepared.input_pack.as_of,
        input_digest=input_digest or prepared.input_pack.input_digest,
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=BOUNDED_DEEPSEEK_BETA_BASE_URL,
        max_semantic_model_calls=6,
        max_provider_calls=6,
        max_network_calls=6,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=1400,
        lead_max_output_tokens=1200,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
    )


class _ExactFakeDeepSeek:
    def __init__(self, *, first_content: str | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.first_content = first_content

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(dict(kwargs))
        node_id = str(kwargs["role"])
        request = json.loads(kwargs["messages"][1]["content"])
        payload = dict(request["analysis_input"])
        if len(self.calls) == 1 and self.first_content is not None:
            content = self.first_content
        else:
            content = json.dumps(
                self._output(node_id, payload),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": content,
            "input_tokens": 10,
            "output_tokens": 10,
            "total_tokens": 20,
            "call_id": f"fake-deepseek-{len(self.calls)}",
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

    @staticmethod
    def _output(node_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if node_id.startswith("domain_specialist:"):
            cell_id = str(payload["cell_input"]["program_cell_id"])
            return {
                "program_cell_id": cell_id,
                "fact_layer": [],
                "explanation_layer": ["Only admitted inputs were evaluated."],
                "judgment_layer": ["The current evidence boundary remains binding."],
                "remaining_gaps": ["Independent exact evidence remains required."],
                "what_would_change": ["Admit exact evidence through its owner."],
                "terminal_class": "typed_cannot_infer",
            }
        if node_id == "research_lead":
            digests = dict(payload["specialist_output_digests"])
            return {
                "cell_heads": [
                    {
                        "program_cell_id": cell_id,
                        "specialist_output_digest": digests[cell_id],
                    }
                    for cell_id in S3_THREE_CELL_PROGRAM_CELL_IDS
                ],
                "cross_cell_dependencies": [
                    "All three cell boundaries constrain the combined conclusion."
                ],
                "conflict_adjudications": [],
                "variant_view": "No Alpha conclusion is supported beyond admitted authority.",
                "remaining_gaps": ["Consensus and independent evidence are not admitted."],
            }
        if node_id == "memo_writer":
            return {
                "title_zh_cn": "NVDA 三单元内部研究草稿",
                "executive_summary_zh_cn": "现有输入仍不足以形成越界结论。",
                "sections": [
                    {
                        "program_cell_id": cell_id,
                        "content_zh_cn": "仅保留已裁决信息及 cannot-infer 边界。",
                    }
                    for cell_id in S3_THREE_CELL_PROGRAM_CELL_IDS
                ],
                "limitations_zh_cn": ["不得把 Candidate 或 Graph context 当作事实。"],
                "consumed_lead_digest": str(payload["cross_cell_lead_digest"]),
                "source_calls": 0,
                "tool_calls": 0,
            }
        if node_id == "verifier":
            return {
                "findings": [
                    {"layer": layer, "status": "pass", "issues": []}
                    for layer in S3_FOUR_LAYER_VERIFIER_LAYERS
                ],
                "bound_lead_digest": str(payload["cross_cell_lead_digest"]),
                "bound_writer_digest": str(payload["writer_digest"]),
                "decision": "accept_for_internal_review",
            }
        raise AssertionError(node_id)


def _counts(case_service: CaseService, case_id: str) -> dict[str, int]:
    return {
        table: len(case_service._facade.store.list_latest(table, case_id=case_id))
        for table in (
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
            "canonical_artifact_versions",
        )
    }


def test_repair_result_closes_only_preissuance_owned_blockers() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    latest = {
        row["issue_id"]: row
        for row in (
            json.loads(line)
            for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    assert result["status"] == (
        "pass_zero_call_preissuance_repair_exact_admission_not_issued"
    )
    assert set(result["observed_counts"].values()) == {0}
    assert result["exact_input_preflight_repair"]["input_digest"] == (
        "ec562442781bae817fdba072cc953e86373ef3b64e78e8a9dcca8312bb5802b8"
    )
    assert result["deterministic_fixture_proof"]["simulated_model_provider_network_calls"] == [
        6,
        6,
        6,
    ]
    assert result["next_action"] == (
        "S3-T09-EXACT-THREE-CELL-DEEPSEEK-ADMISSION-ISSUANCE-DECISION"
    )
    assert backlog["next_action"]["S3_T09_preissuance_repair_ref"] == (
        "configs/releases/"
        "fin_ia_0_1_s3_t09_deepseek_transport_exact_input_preflight_repair_v1_0.json"
    )
    assert backlog["next_action"]["S3_T09_preissuance_repair_authorized"] is True
    for issue_id in (
        "RC-P36-032-s3-three-cell-six-node-provider-adapter-missing",
        "RC-P36-033-s3-exact-input-run-before-prepare-cycle",
    ):
        row = latest[issue_id]
        assert row["status"].startswith("closed_root_cause_repaired_zero_call")
        assert row["full_chain_blocker"] is False


def test_exact_input_prepare_is_repeatable_and_creates_no_execution_state(
    tmp_path: Path,
) -> None:
    case_service, local_service, evidence_service, case, accepted = (
        _create_accepted_case(tmp_path)
    )
    before = _counts(case_service, case["case_id"])
    first = _prepare(local_service, evidence_service, case, accepted)
    middle = _counts(case_service, case["case_id"])
    second = _prepare(local_service, evidence_service, case, accepted)
    after = _counts(case_service, case["case_id"])

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert before == middle == after == {
        "canonical_work_units": 0,
        "canonical_attempts": 0,
        "canonical_research_run_versions": 0,
        "canonical_artifact_versions": 0,
    }
    assert first.observed_counts == {
        "canonical_writes": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
    }
    assert first.input_pack.decision_surface_contract_ref == accepted["contract_version_id"]
    assert first.input_pack.input_digest
    assert first.preparation_digest

    v2_admission = _admission(first).model_copy(
        update={
            "output_contract_ref": S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
            "specialist_max_output_tokens": 2200,
        }
    )
    for cell_input in first.input_pack.cell_inputs:
        payload = {
            "input_contract_ref": first.input_pack.input_contract_ref,
            "input_digest": first.input_pack.input_digest,
            "cell_input": cell_input,
            "required_output_layers": [
                "fact_layer",
                "explanation_layer",
                "judgment_layer",
                "remaining_gaps",
                "what_would_change",
            ],
        }
        _, request, binding = DeepSeekS3ThreeCellNodeExecutor._node_request(
            f"domain_specialist:{cell_input['program_cell_id']}",
            payload,
            v2_admission,
        )
        view = request["analysis_input"]["cell_input"]
        assert request["analysis_input"]["model_view_contract_ref"] == (
            S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF
        )
        assert binding["model_view_digest"] == canonical_digest(view)
        assert view["decision_contract"]["decision_question"] == (
            cell_input["runtime_branch"]["decision_question"]
        )
        assert view["authority_refs"] == cell_input["authority_refs"]
        assert {
            row["financial_row_id"]
            for row in view["numeric_view"]["selected_financial_rows"]
        } == {
            row["financial_row_id"]
            for row in cell_input["numeric_input"]["selected_financial_rows"]
        }
        assert {
            row["derived_metric_id"]
            for row in view["numeric_view"]["derived_metrics"]
        } == {
            row["derived_metric_id"]
            for row in cell_input["numeric_input"]["derived_metrics"]
        }
        serialized = json.dumps(request, ensure_ascii=False, sort_keys=True)
        assert "tool_selection_plan" not in serialized
        assert "tool_gateway_preflights" not in serialized
        assert "candidate_snapshot" not in serialized
        assert "decision_cells" not in serialized
        assert len(serialized.encode("utf-8")) < 0.5 * len(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        )


def test_fake_provider_full_runtime_preserves_prepared_identity_and_six_call_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_service, local_service, evidence_service, case, accepted = (
        _create_accepted_case(tmp_path)
    )
    prepared = _prepare(local_service, evidence_service, case, accepted)
    admission = _admission(prepared)
    fake = _ExactFakeDeepSeek()
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-not-a-real-key")
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=fake
    )
    app = create_app(
        tmp_path / "execution-workbench.sqlite",
        p02_case_service=case_service,
        p03_evidence_service=evidence_service,
        p36_local_research_service=local_service,
        s3_three_cell_bounded_agent_admission=admission,
        s3_three_cell_bounded_agent_executor=executor,
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/cases/{case['case_id']}/work-units",
            headers=_headers(),
            json={
                "work_unit_type": BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
                "expected_case_version": case["case_version"],
                "input_head_digest": canonical_digest(
                    (accepted["contract_version_id"],)
                ),
                "actor_ref": ACTOR_ID,
                "idempotency_key": EXECUTION_IDENTITY,
            },
        )
        assert response.status_code == 202, response.text

    store = case_service._facade.store
    work_unit = store.get_latest("canonical_work_units", prepared.work_unit_id)
    attempt = store.get_latest("canonical_attempts", prepared.attempt_id)
    run = store.get_latest("canonical_research_run_versions", prepared.research_run_id)
    artifacts = store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    )
    assert work_unit is not None and work_unit["state"] == "succeeded"
    assert attempt is not None and attempt["state"] == "succeeded"
    assert run is not None and run["state"] == "succeeded"
    assert len(artifacts) == len(BOUNDED_AGENT_ARTIFACT_TYPES)
    assert len(fake.calls) == 6
    assert [row["role"] for row in fake.calls] == [
        *(f"domain_specialist:{cell_id}" for cell_id in S3_THREE_CELL_PROGRAM_CELL_IDS),
        "research_lead",
        "memo_writer",
        "verifier",
    ]
    assert all(row["tools"] is None and row["tool_choice"] is None for row in fake.calls)
    assert all(row["response_format"] == {"type": "json_object"} for row in fake.calls)
    assert all(row["enable_thinking"] is False for row in fake.calls)
    manifest_row = next(
        row for row in artifacts if row["artifact_type"] == "bounded_agent_manifest"
    )
    manifest = case_service._facade.object_store.get_json(
        manifest_row["object_key"], expected_digest=manifest_row["object_digest"]
    )
    assert manifest["input_digest"] == prepared.input_pack.input_digest
    assert manifest["observed_counts"] == {
        "model_calls": 6,
        "provider_calls": 6,
        "network_calls": 6,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_case_head_writes": 0,
        "evaluation_evidence_promotions": 0,
    }


def test_exact_input_mismatch_stops_before_fake_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, local_service, evidence_service, case, accepted = _create_accepted_case(tmp_path)
    prepared = _prepare(local_service, evidence_service, case, accepted)
    admission = _admission(prepared, input_digest="wrong-input-digest")
    fake = _ExactFakeDeepSeek()
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-not-a-real-key")
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=fake
    )
    with pytest.raises(ValueError, match="s3_bounded_admission_exact_input_mismatch"):
        executor.execute(
            prepared.input_pack,
            admission,
            run_identity={
                "case_id": prepared.case_id,
                "work_unit_id": prepared.work_unit_id,
                "attempt_id": prepared.attempt_id,
                "research_run_id": prepared.research_run_id,
            },
        )
    assert fake.calls == []


def test_non_native_or_duplicate_json_fails_closed_after_one_transport_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, local_service, evidence_service, case, accepted = _create_accepted_case(tmp_path)
    prepared = _prepare(local_service, evidence_service, case, accepted)
    admission = _admission(prepared)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-not-a-real-key")

    for content, expected in (
        ('{"program_cell_id":"a","program_cell_id":"b"}', "duplicate_json_key"),
        ("```json\n{}\n```", "native_json_required"),
    ):
        fake = _ExactFakeDeepSeek(first_content=content)
        executor = build_s3_three_cell_bounded_agent_executor_for_admission(
            admission, chat_completion_fn=fake
        )
        with pytest.raises(BoundedAgentExecutionError) as caught:
            executor.execute(
                prepared.input_pack,
                admission,
                run_identity={
                    "case_id": prepared.case_id,
                    "work_unit_id": prepared.work_unit_id,
                    "attempt_id": prepared.attempt_id,
                    "research_run_id": prepared.research_run_id,
                },
            )
        observation = caught.value.failure_observation
        assert len(fake.calls) == 1
        assert expected in observation["failure_codes"][0]
        assert observation["observed_counts"] == {
            "model_calls": 1,
            "provider_calls": 1,
            "network_calls": 1,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        }
        assert observation["raw_provider_response_persisted"] is False
