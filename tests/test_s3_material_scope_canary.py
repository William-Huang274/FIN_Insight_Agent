from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from retrieval.contracts import load_evidence_request, load_financial_research_kernel
from sec_agent.providers.chat_completions import (
    ChatCompletionResult,
    ModelGatewayError,
)
from sec_agent.project_os_preflight import build_preflight
from sec_agent.research.material_scope import compile_research_material_scope_messages
from sec_agent.research.material_scope_canary import (
    MATERIAL_SCOPE_CANARY_AUTHORITY_SCHEMA,
    MATERIAL_SCOPE_CANARY_AUTHORITY_STATUS,
    MATERIAL_SCOPE_CANARY_RUN_SCOPE,
    MATERIAL_SCOPE_CONTRACT_REPAIR_AUTHORITY_SCHEMA,
    MATERIAL_SCOPE_CONTRACT_REPAIR_AUTHORITY_STATUS,
    MATERIAL_SCOPE_CONTRACT_REPAIR_RUN_SCOPE,
    MATERIAL_SCOPE_SUCCESSOR_AUTHORITY_SCHEMA,
    MATERIAL_SCOPE_SUCCESSOR_AUTHORITY_STATUS,
    MATERIAL_SCOPE_SUCCESSOR_RUN_SCOPE,
    MaterialScopeCanaryError,
    build_material_scope_canary_input,
    run_material_scope_canary,
    validate_material_scope_canary_authority,
    validate_material_scope_canary_input,
)


ROOT = Path(__file__).resolve().parents[1]


def _json(ref: str) -> dict:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


KERNEL_REF = "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_2.json"
SCOPE_POLICY_REF = "configs/research/fin_ia_0_1_3_s3_material_scope_policy_v1_0.json"
RUNTIME_POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_product_material_evidence_runtime_policy_v1_0.json"
)
ONTOLOGY_REF = "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_2.json"
PROFILE_REF = (
    "configs/providers/"
    "fin_ia_0_1_3_deepseek_v4_pro_ga_material_scope_profile_v1_0.json"
)
SUCCESSOR_PROFILE_REF = (
    "configs/providers/"
    "fin_ia_0_1_3_deepseek_v4_pro_ga_material_scope_"
    "nonthinking_profile_v1_0.json"
)
SUCCESSOR_POLICY_REF = (
    "configs/research/"
    "fin_ia_0_1_3_s3_material_scope_nonthinking_successor_policy_v1_0.json"
)
R1_RESULT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_material_scope_canary_live_result_v1_0.json"
)
R1_ASSESSMENT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_material_scope_canary_failure_assessment_v1_0.json"
)
CONTRACT_REPAIR_POLICY_REF = (
    "configs/research/"
    "fin_ia_0_1_3_s3_material_scope_contract_repair_"
    "successor_policy_v1_0.json"
)
R2_RESULT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_material_scope_canary_live_result_v1_1.json"
)
R2_ASSESSMENT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_material_scope_canary_failure_assessment_v1_1.json"
)
CURRENT_DELL_INPUT_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_material_scope_canary_input_v1_1.json"
)
CURRENT_DELL_AUTHORITY_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_material_scope_canary_authority_v1_0.json"
)
CURRENT_DELL_SUCCESSOR_AUTHORITY_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_material_scope_nonthinking_"
    "successor_authority_v1_0.json"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request_payload() -> dict:
    return {
        "schema_version": "fin_ia_evidence_request_v1_0",
        "request_id": "REQ::DELL-WORKING-CAPITAL-SCOPE",
        "cell_id": "CELL::DELL-MATERIAL-SCOPE",
        "requester_role": "cash_conversion_specialist",
        "evidence_domain": "operating_performance",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "target_entities": ["DELL"],
        "requested_facet_ids": ["working_capital_risk"],
        "metric_intents": ["inventory", "accounts_receivable"],
        "product_intents": ["AI infrastructure working-capital dynamics"],
        "period": {
            "start_date": "2025-02-01",
            "end_date": "2026-08-06",
            "fiscal_years": [2026, 2027],
        },
        "granularity": "quarter_and_fiscal_year",
        "unit": "reported_source_unit",
        "acceptable_sources": ["10-K", "10-Q", "8-K"],
        "acceptable_proxy": False,
        "forbidden_proxy": ["unbound industry demand"],
        "stop_condition": "return candidates, typed facts, or typed gaps",
        "clarification_policy": "return_typed_gap",
    }


def _scope_payload() -> dict:
    return {
        "schema_version": "fin_ia_research_material_scope_atoms_v1_0",
        "research_plan_digest": "PLAN::CANARY",
        "request_scopes": [
            {
                "request_id": "REQ::DELL-WORKING-CAPITAL-SCOPE",
                "product_intent_dispositions": [
                    {
                        "product_intent_index": 0,
                        "disposition": "contextual_retrieval_only",
                    }
                ],
                "requirement_atoms": [
                    {
                        "facet_id": "working_capital_risk",
                        "role": "bridge",
                        "metric_intent_indices": [0, 1],
                        "product_intent_indices": [],
                        "period_mode": "any",
                        "coverage_mode": "collective_axes",
                    },
                    {
                        "facet_id": "working_capital_risk",
                        "role": "counter",
                        "metric_intent_indices": [],
                        "product_intent_indices": [],
                        "period_mode": "any",
                        "coverage_mode": "collective_axes",
                    },
                ],
            }
        ],
    }


def _input_payload() -> dict:
    kernel = load_financial_research_kernel(_json(KERNEL_REF))
    request = load_evidence_request(_request_payload(), kernel)
    messages = compile_research_material_scope_messages(
        research_plan_digest="PLAN::CANARY",
        requests=[request],
        required_request_ids=[request.request_id],
        policy=_json(SCOPE_POLICY_REF),
        material_runtime_policy=_json(RUNTIME_POLICY_REF),
        intent_ontology=_json(ONTOLOGY_REF),
    )
    projection = {
        "projection_digest": "projection-digest",
        "compiled_plan": {
            "plan_digest": "PLAN::CANARY",
            "evidence_requests": [_request_payload()],
        },
        "material_scope": {
            "mode": "explicit_scope_required",
            "required_request_ids": [request.request_id],
        },
        "summary": {
            "proposed_atom_count": 1,
            "selected_atom_count": 1,
            "deferred_atom_count": 0,
            "evidence_request_count": 1,
            "nonempty_lane_count": 1,
            "typed_fact_request_count": 2,
            "typed_fact_resolved_count": 1,
            "typed_fact_gap_count": 1,
            "numeric_fact_count": 2,
            "hybrid_selected_candidate_count": 8,
            "material_scope_required_request_count": 1,
            "material_scope_ready_request_count": 0,
            "local_embedding_inference_batches": 1,
            "network_calls": 0,
            "model_calls": 0,
        },
        "request_results": [
            {
                "request": {"request_id": request.request_id},
                "hybrid_object_retrieval": {
                    "summary": {
                        "selected_count": 8,
                        "material_scope_ready": False,
                        "material_set_complete": False,
                        "reserved_material_candidate_count": 1,
                        "material_review_order_candidate_count": 5,
                    }
                },
            }
        ],
    }
    return build_material_scope_canary_input(
        case_key="DELL",
        product_projection=projection,
        model_visible_messages=messages,
        source_bindings={
            "fixture": {"ref": "fixture.json", "sha256": "0" * 64}
        },
        prepared_from_commit="a" * 40,
    )


def test_canary_input_is_candidate_blind_and_digest_bound() -> None:
    payload = _input_payload()
    validate_material_scope_canary_input(payload)
    visible = json.loads(payload["model_visible_messages"][1]["content"])
    serialized = json.dumps(visible, ensure_ascii=False).casefold()
    assert "candidate_id" not in serialized
    assert "object_id" not in serialized
    assert "source_url" not in serialized
    assert payload["authority"]["candidate_or_reference_inputs_read"] is False
    assert payload["product_diagnostic"]["request_diagnostics"][0][
        "request_id"
    ] == "REQ::DELL-WORKING-CAPITAL-SCOPE"


def test_current_dell_input_is_clean_commit_bound_and_fully_traceable() -> None:
    payload = _json(CURRENT_DELL_INPUT_REF)
    validate_material_scope_canary_input(payload)
    diagnostic = payload["product_diagnostic"]
    assert payload["prepared_from_commit"] == (
        "20ca2768eab3d8e70785d85b3a956416736289e3"
    )
    assert len(payload["required_request_ids"]) == 8
    assert [
        row["request_id"] for row in diagnostic["request_diagnostics"]
    ] == payload["required_request_ids"]
    assert diagnostic["proposed_atom_count"] == 10
    assert diagnostic["selected_atom_count"] == 8
    assert diagnostic["deferred_atom_count"] == 2
    assert diagnostic["material_scope_required_request_count"] == 8
    assert diagnostic["material_scope_ready_request_count"] == 0
    assert diagnostic["hybrid_selected_candidate_count"] == 128
    assert diagnostic["numeric_fact_count"] == 58
    assert diagnostic["network_calls"] == 0
    assert diagnostic["model_calls"] == 0


def test_current_dell_R1_authority_remains_bound_but_scope_is_consumed() -> None:
    authority = _json(CURRENT_DELL_AUTHORITY_REF)
    bound = validate_material_scope_canary_authority(authority, root=ROOT)
    assert bound["input"]["result_digest"] == (
        "f19148cba25125fa7668d3aec8846d27e4a9d4ed22db6a1f143a4b0cbe562ed9"
    )
    with pytest.raises(
        ValueError,
        match="project_os_material_scope_canary_scope_allowance_missing",
    ):
        build_preflight(
            root=ROOT,
            decision_ref=CURRENT_DELL_AUTHORITY_REF,
            environment={"DEEPSEEK_API_KEY": "present"},
            check_repository=False,
        )


def test_current_dell_R2_successor_authority_remains_bound_but_is_consumed() -> None:
    authority = _json(CURRENT_DELL_SUCCESSOR_AUTHORITY_REF)
    bound = validate_material_scope_canary_authority(authority, root=ROOT)
    assert bound["successor"] is True
    assert bound["profile"].request_defaults["thinking"] == {
        "type": "disabled"
    }
    with pytest.raises(
        ValueError,
        match="project_os_material_scope_canary_scope_allowance_missing",
    ):
        build_preflight(
            root=ROOT,
            decision_ref=CURRENT_DELL_SUCCESSOR_AUTHORITY_REF,
            environment={"DEEPSEEK_API_KEY": "present"},
            check_repository=False,
        )


def _copy(root: Path, ref: str) -> None:
    target = root / ref
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / ref, target)


def _authority_root(tmp_path: Path) -> tuple[Path, dict, Path]:
    for ref in (
        KERNEL_REF,
        SCOPE_POLICY_REF,
        RUNTIME_POLICY_REF,
        ONTOLOGY_REF,
        PROFILE_REF,
    ):
        _copy(tmp_path, ref)
    runner_ref = "scripts/research/run_s3_material_scope_canary.py"
    implementation_ref = "src/sec_agent/research/material_scope_canary.py"
    for ref in (runner_ref, implementation_ref):
        _copy(tmp_path, ref)
    input_ref = "configs/research/evals/test_material_scope_input.json"
    input_path = tmp_path / input_ref
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_payload = _input_payload()
    input_path.write_text(
        json.dumps(input_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    def binding(ref: str) -> tuple[str, str]:
        return ref, _sha(tmp_path / ref)

    authority = {
        "schema_version": MATERIAL_SCOPE_CANARY_AUTHORITY_SCHEMA,
        "authority_id": "TEST-MATERIAL-SCOPE-CANARY",
        "status": MATERIAL_SCOPE_CANARY_AUTHORITY_STATUS,
        "issued_at": "2026-08-18T00:00:00+08:00",
        "implementation_commit": "a" * 40,
        "case_key": "DELL",
        "cell_id": "MATERIAL_SCOPE",
        "run_scope_id": MATERIAL_SCOPE_CANARY_RUN_SCOPE,
        "evidence_mode": "request_visible_scope_only_no_candidates_no_evidence",
        "credential_presence_required": True,
        "chat_live_authorized": True,
        "responses_live_authorized": False,
        "anthropic_live_authorized": False,
        "external_network_authorized": False,
        "candidate_or_reference_visibility_authorized": False,
        "candidate_promotion_authorized": False,
        "numeric_authority_authorized": False,
        "product_publication_authorized": False,
        "s1_acceptance_authorized": False,
        "bound_inputs": {
            "input_result_ref": input_ref,
            "input_result_sha256": _sha(input_path),
            "input_result_digest": input_payload["result_digest"],
            "material_scope_policy_ref": binding(SCOPE_POLICY_REF)[0],
            "material_scope_policy_sha256": binding(SCOPE_POLICY_REF)[1],
            "material_runtime_policy_ref": binding(RUNTIME_POLICY_REF)[0],
            "material_runtime_policy_sha256": binding(RUNTIME_POLICY_REF)[1],
            "intent_ontology_ref": binding(ONTOLOGY_REF)[0],
            "intent_ontology_sha256": binding(ONTOLOGY_REF)[1],
            "kernel_ref": binding(KERNEL_REF)[0],
            "kernel_sha256": binding(KERNEL_REF)[1],
            "provider_profile_ref": binding(PROFILE_REF)[0],
            "provider_profile_sha256": binding(PROFILE_REF)[1],
            "runner_ref": binding(runner_ref)[0],
            "runner_sha256": binding(runner_ref)[1],
            "implementation_ref": binding(implementation_ref)[0],
            "implementation_sha256": binding(implementation_ref)[1],
            "model_visible_messages_digest": input_payload[
                "model_visible_messages_digest"
            ],
        },
        "execution_budget": {
            "maximum_model_calls": 1,
            "maximum_transport_attempts": 1,
            "retries": 0,
            "fallbacks": 0,
            "protocol_switches": 0,
            "external_source_network_calls": 0,
            "retrieval_calls": 0,
            "embedding_calls": 0,
            "candidate_reads": 0,
            "qrel_reference_or_hidden_reads": 0,
            "product_pointer_mutations": 0,
        },
        "output_contract": {
            "capture_root_ref": ".codex_runtime/test_material_scope",
            "private_result_ref": "data/workbench_private/test_material_scope/full.json",
            "public_result_ref": "configs/research/evals/test_material_scope_result.json",
            "run_id": "TEST-MATERIAL-SCOPE",
            "attempt_id": "R1",
            "product_publication": "forbidden",
        },
        "known_boundary": "test candidate-blind scope only",
    }
    authority_ref = "configs/research/evals/test_material_scope_authority.json"
    authority_path = tmp_path / authority_ref
    authority_path.write_text(
        json.dumps(authority, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return tmp_path, authority, authority_path


def _successor_authority_root(tmp_path: Path) -> tuple[Path, dict, Path]:
    root, authority, _ = _authority_root(tmp_path)
    for ref in (
        SUCCESSOR_PROFILE_REF,
        SUCCESSOR_POLICY_REF,
        R1_RESULT_REF,
        R1_ASSESSMENT_REF,
    ):
        _copy(root, ref)
    authority["schema_version"] = MATERIAL_SCOPE_SUCCESSOR_AUTHORITY_SCHEMA
    authority["authority_id"] = "TEST-MATERIAL-SCOPE-SUCCESSOR"
    authority["status"] = MATERIAL_SCOPE_SUCCESSOR_AUTHORITY_STATUS
    authority["run_scope_id"] = MATERIAL_SCOPE_SUCCESSOR_RUN_SCOPE
    authority["immutable_predecessor"] = {
        "failure_result_ref": R1_RESULT_REF,
        "failure_result_sha256": _sha(root / R1_RESULT_REF),
        "failure_result_digest": _json(R1_RESULT_REF)["result_digest"],
        "failure_assessment_ref": R1_ASSESSMENT_REF,
        "failure_assessment_sha256": _sha(root / R1_ASSESSMENT_REF),
    }
    authority["bound_inputs"]["provider_profile_ref"] = SUCCESSOR_PROFILE_REF
    authority["bound_inputs"]["provider_profile_sha256"] = _sha(
        root / SUCCESSOR_PROFILE_REF
    )
    authority["bound_inputs"]["successor_policy_ref"] = SUCCESSOR_POLICY_REF
    authority["bound_inputs"]["successor_policy_sha256"] = _sha(
        root / SUCCESSOR_POLICY_REF
    )
    authority["output_contract"] = {
        "capture_root_ref": ".codex_runtime/test_material_scope_successor",
        "private_result_ref": (
            "data/workbench_private/test_material_scope_successor/full.json"
        ),
        "public_result_ref": (
            "configs/research/evals/test_material_scope_successor_result.json"
        ),
        "run_id": "TEST-MATERIAL-SCOPE-SUCCESSOR",
        "attempt_id": "R2",
        "product_publication": "forbidden",
    }
    authority_ref = (
        "configs/research/evals/test_material_scope_successor_authority.json"
    )
    authority_path = root / authority_ref
    authority_path.write_text(
        json.dumps(authority, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return root, authority, authority_path


def _contract_repair_authority_root(
    tmp_path: Path,
) -> tuple[Path, dict, Path]:
    root, authority, _ = _authority_root(tmp_path)
    for ref in (
        SUCCESSOR_PROFILE_REF,
        CONTRACT_REPAIR_POLICY_REF,
        R2_RESULT_REF,
        R2_ASSESSMENT_REF,
    ):
        _copy(root, ref)
    authority["schema_version"] = MATERIAL_SCOPE_CONTRACT_REPAIR_AUTHORITY_SCHEMA
    authority["authority_id"] = "TEST-MATERIAL-SCOPE-CONTRACT-REPAIR"
    authority["status"] = MATERIAL_SCOPE_CONTRACT_REPAIR_AUTHORITY_STATUS
    authority["run_scope_id"] = MATERIAL_SCOPE_CONTRACT_REPAIR_RUN_SCOPE
    authority["immutable_predecessor"] = {
        "failure_result_ref": R2_RESULT_REF,
        "failure_result_sha256": _sha(root / R2_RESULT_REF),
        "failure_result_digest": _json(R2_RESULT_REF)["result_digest"],
        "failure_assessment_ref": R2_ASSESSMENT_REF,
        "failure_assessment_sha256": _sha(root / R2_ASSESSMENT_REF),
    }
    authority["bound_inputs"]["provider_profile_ref"] = SUCCESSOR_PROFILE_REF
    authority["bound_inputs"]["provider_profile_sha256"] = _sha(
        root / SUCCESSOR_PROFILE_REF
    )
    authority["bound_inputs"][
        "contract_repair_policy_ref"
    ] = CONTRACT_REPAIR_POLICY_REF
    authority["bound_inputs"]["contract_repair_policy_sha256"] = _sha(
        root / CONTRACT_REPAIR_POLICY_REF
    )
    authority["output_contract"] = {
        "capture_root_ref": ".codex_runtime/test_material_scope_contract_repair",
        "private_result_ref": (
            "data/workbench_private/test_material_scope_contract_repair/full.json"
        ),
        "public_result_ref": (
            "configs/research/evals/test_material_scope_contract_repair_result.json"
        ),
        "run_id": "TEST-MATERIAL-SCOPE-CONTRACT-REPAIR",
        "attempt_id": "R3",
        "product_publication": "forbidden",
    }
    authority_ref = (
        "configs/research/evals/test_material_scope_contract_repair_authority.json"
    )
    authority_path = root / authority_ref
    authority_path.write_text(
        json.dumps(authority, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return root, authority, authority_path


def test_authority_binds_one_call_profile_and_input(tmp_path: Path) -> None:
    root, authority, _ = _authority_root(tmp_path)
    bound = validate_material_scope_canary_authority(authority, root=root)
    assert bound["input"]["result_digest"] == authority["bound_inputs"][
        "input_result_digest"
    ]
    assert bound["profile"].model == "deepseek-v4-pro"
    assert bound["profile"].request_defaults["max_tokens"] == 12000


def test_successor_authority_preserves_R1_and_uses_nonthinking_profile(
    tmp_path: Path,
) -> None:
    root, authority, _ = _successor_authority_root(tmp_path)
    bound = validate_material_scope_canary_authority(authority, root=root)
    defaults = bound["profile"].request_defaults
    assert bound["successor"] is True
    assert bound["predecessor"]["failure"]["status"] == (
        "terminal_failed_no_retry"
    )
    assert defaults["max_tokens"] == 8000
    assert defaults["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in defaults


def test_successor_predecessor_drift_fails_closed(tmp_path: Path) -> None:
    root, authority, _ = _successor_authority_root(tmp_path)
    authority["immutable_predecessor"]["failure_result_digest"] = "f" * 64
    with pytest.raises(
        MaterialScopeCanaryError,
        match="material_scope_successor_predecessor_invalid",
    ):
        validate_material_scope_canary_authority(authority, root=root)


def test_contract_repair_authority_binds_R2_and_same_nonthinking_profile(
    tmp_path: Path,
) -> None:
    root, authority, _ = _contract_repair_authority_root(tmp_path)
    bound = validate_material_scope_canary_authority(authority, root=root)
    assert bound["contract_repair_successor"] is True
    assert bound["nonthinking_successor"] is False
    assert bound["predecessor"]["failure"]["failure_code"] == (
        "research_material_scope_output_fields_invalid"
    )
    assert bound["profile"].request_defaults["thinking"] == {
        "type": "disabled"
    }
    assert bound["contract_repair_policy"]["contract_repair"][
        "local_model_output_rewrite"
    ] is False


def test_contract_repair_predecessor_drift_fails_closed(tmp_path: Path) -> None:
    root, authority, _ = _contract_repair_authority_root(tmp_path)
    authority["immutable_predecessor"]["failure_result_digest"] = "e" * 64
    with pytest.raises(
        MaterialScopeCanaryError,
        match="material_scope_contract_repair_predecessor_invalid",
    ):
        validate_material_scope_canary_authority(authority, root=root)


def test_exact_once_canary_compiles_scope_and_materializes_terminal_result(
    tmp_path: Path,
) -> None:
    root, _, authority_path = _authority_root(tmp_path)
    calls: list[dict] = []

    def executor(**kwargs):
        calls.append(kwargs)
        return ChatCompletionResult(
            status="completed_exact_once",
            provider_id="deepseek",
            model="deepseek-v4-pro",
            content=json.dumps(_scope_payload()),
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 200},
            request_capture_ref=(root / ".codex_runtime/request.json").as_posix(),
            response_capture_ref=(root / ".codex_runtime/response.json").as_posix(),
            request_digest="1" * 64,
            response_digest="2" * 64,
            private_reasoning_fields_redacted=1,
        )

    result = run_material_scope_canary(
        authority_path, root=root, executor=executor
    )

    assert len(calls) == 1
    assert result["status"] == "completed_contract_valid"
    assert result["scope_summary"]["required_request_count"] == 1
    assert result["scope_summary"]["candidate_or_reference_inputs_read"] is False
    assert (root / result["full_result_ref"]).is_file()
    assert (root / "configs/research/evals/test_material_scope_result.json").is_file()


def test_successor_exact_once_keeps_same_contract_and_compiles_scope(
    tmp_path: Path,
) -> None:
    root, _, authority_path = _successor_authority_root(tmp_path)
    calls: list[dict] = []

    def executor(**kwargs):
        calls.append(kwargs)
        return ChatCompletionResult(
            status="completed_exact_once",
            provider_id="deepseek",
            model="deepseek-v4-pro",
            content=json.dumps(_scope_payload()),
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 200},
            request_capture_ref=(root / ".codex_runtime/request-r2.json").as_posix(),
            response_capture_ref=(root / ".codex_runtime/response-r2.json").as_posix(),
            request_digest="3" * 64,
            response_digest="4" * 64,
            private_reasoning_fields_redacted=0,
        )

    result = run_material_scope_canary(
        authority_path, root=root, executor=executor
    )

    assert len(calls) == 1
    assert calls[0]["profile"].request_defaults["thinking"] == {
        "type": "disabled"
    }
    assert result["status"] == "completed_contract_valid"
    assert result["scope_summary"]["required_request_count"] == 1
    assert result["execution"]["retries"] == 0


def test_failed_gateway_projects_capture_metadata_without_response_content(
    tmp_path: Path,
) -> None:
    root, _, authority_path = _successor_authority_root(tmp_path)

    def executor(**kwargs):
        capture_dir = (
            Path(kwargs["capture_root"])
            / kwargs["run_id"]
            / kwargs["attempt_id"]
        )
        capture_dir.mkdir(parents=True, exist_ok=True)
        request_path = capture_dir / "model_visible_request.json"
        response_path = capture_dir / "provider_response.json"
        request_path.write_text(
            json.dumps({"request_digest": "1" * 64}), encoding="utf-8"
        )
        response_path.write_text(
            json.dumps(
                {
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "response_digest": "2" * 64,
                    "private_reasoning_fields_redacted": 1,
                    "response_body": {
                        "choices": [
                            {
                                "finish_reason": "length",
                                "message": {"content": ""},
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 2781,
                            "completion_tokens": 8000,
                            "completion_tokens_details": {
                                "reasoning_tokens": 8000
                            },
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        raise ModelGatewayError(
            "model_gateway_reasoning_budget_exhausted",
            capture_ref=response_path.as_posix(),
        )

    result = run_material_scope_canary(
        authority_path, root=root, executor=executor
    )

    assert result["status"] == "terminal_failed_no_retry"
    assert result["provider"]["finish_reason"] == "length"
    assert result["provider"]["usage"]["prompt_tokens"] == 2781
    assert result["provider"]["request_digest"] == "1" * 64
    assert result["provider"]["response_digest"] == "2" * 64
    assert result["provider"]["private_reasoning_fields_redacted"] == 1
    assert "response_body" not in result["provider"]


def test_authority_profile_drift_fails_closed(tmp_path: Path) -> None:
    root, authority, _ = _authority_root(tmp_path)
    drift = deepcopy(authority)
    drift["bound_inputs"]["provider_profile_sha256"] = "f" * 64
    with pytest.raises(
        MaterialScopeCanaryError,
        match="material_scope_canary_bound_sha_drift:provider_profile_ref",
    ):
        validate_material_scope_canary_authority(drift, root=root)
