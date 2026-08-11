from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentInputPack,
    compile_s4_case_runtime_mandatory_safety_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _ScopedV4FullFakeProvider,
)


MU_FIXTURE = ROOT / (
    "tests/fixtures/fin_0_1_2/mu_realistic_three_cell_exact_input_v1.json"
)
MU_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_fresh_exact_admission_r1.json"
)
EXPECTED_SCHEMA = (
    "fin_ia_0_1_2_mu_realistic_three_cell_exact_input_fixture_v1_0"
)
EXPECTED_FIXTURE_ID = (
    "FIN-0.1.2-PRE-S2-MU-REALISTIC-THREE-CELL-EXACT-INPUT-V1"
)
EXPECTED_SOURCE_OBJECT_SHA256 = (
    "290e82aec53d6d3078eb0c8bac94e022bde7cc17a77b72d2315af118ced4958e"
)
EXPECTED_SOURCE_INPUT_DIGEST = (
    "7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1"
)
_EXPECTED_TOP_LEVEL = {
    "schema_version",
    "fixture_id",
    "source_object_sha256",
    "source_input_digest",
    "source_case_id_and_version",
    "input_pack",
    "content_digest",
    "provenance_and_nonpromotion_boundary",
}


class RealisticFixtureContractError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _provider_response(
    output: Mapping[str, Any],
    call_number: int,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "finish_reason": "stop",
        "content": json.dumps(output, ensure_ascii=False, sort_keys=True),
        "input_tokens": 10,
        "output_tokens": 100,
        "total_tokens": 110,
        "call_id": f"fixture-mu-source-grounded-v7-{call_number}",
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


class MuSourceGroundedV7FullFakeProvider(_ScopedV4FullFakeProvider):
    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        request = json.loads(kwargs["messages"][1]["content"])
        node_id = str(request["node_id"])
        if node_id.startswith("domain_specialist:"):
            self.calls.append({"kwargs": dict(kwargs), "request": request})
            cell_id = node_id.split(":", 1)[1]
            segment_id = str(request["segment_id"])
            if segment_id == "facts_explanation_and_terminal":
                allowed = request["fact_support_authority_contract"][
                    "allowed_refs_by_support_type"
                ]
                support_type = (
                    "Evidence" if allowed["Evidence"] else "Numeric"
                )
                output = {
                    "program_cell_id": cell_id,
                    "fact_layer": [
                        {
                            "fact_id": "fact-local-001",
                            "statement": "Official issuer evidence is present.",
                            "support_type": support_type,
                            "support_refs": [allowed[support_type][0]],
                            "boundary": (
                                "The evidence supports only a bounded judgment."
                            ),
                        }
                    ],
                    "explanation_layer": [
                        "The admitted source supports a bounded conclusion."
                    ],
                    "remaining_gaps": [
                        "Future durability remains unproven."
                    ],
                    "terminal_class": "bounded_inference",
                }
            elif segment_id == "owner_grade_claim_cards":
                fact_alias = request["claim_fact_link_contract"][
                    "allowed_facts"
                ][0]["fact_alias"]
                output = {
                    "program_cell_id": cell_id,
                    "judgment_layer": [
                        {
                            "claim_id": "claim-local-001",
                            "statement": (
                                "Issuer evidence supports a bounded outlook."
                            ),
                            "epistemic_status": "bounded_inference",
                            "scope": {
                                "metric_or_mechanism": (
                                    "HBM demand and value capture"
                                )
                            },
                            "context_refs": [],
                            "support_fact_aliases": [fact_alias],
                            "qualification": (
                                "The conclusion is bounded by disclosed evidence."
                            ),
                            "cannot_support": [
                                "It does not prove a future financial outcome."
                            ],
                        }
                    ],
                }
            else:
                allowed = request["what_would_change_authority_contract"][
                    "allowed_refs_by_authority_class"
                ]
                authority_ref = next(
                    ref
                    for authority_class in (
                        "Evidence",
                        "Numeric",
                        "Graph",
                        "Candidate",
                    )
                    for ref in allowed[authority_class]
                )
                output = {
                    "program_cell_id": cell_id,
                    "what_would_change": [
                        {
                            "task_id": "wwc-local-001",
                            "claim_id": "claim-local-001",
                            "metric_or_observation": (
                                "An updated issuer disclosure"
                            ),
                            "source_target": {
                                "source_type": "issuer filing",
                                "entity_or_owner": "MU",
                                "document_event_or_dataset": (
                                    "next earnings disclosure"
                                ),
                            },
                            "decision_rule": {
                                "rule_type": "directional_update",
                                "comparator_or_condition": (
                                    "new evidence changes the bounded outlook"
                                ),
                                "threshold_or_observation": (
                                    "issuer-bound evidence is observed"
                                ),
                            },
                            "expected_claim_transition": (
                                "Reassess the claim's epistemic status."
                            ),
                            "time_window": {
                                "as_of": "2026-07-26",
                                "start_or_trigger": "next issuer disclosure",
                                "deadline_or_review_date": (
                                    "next scheduled review"
                                ),
                            },
                            "fallback_stop_condition": (
                                "Stop if no issuer-bound update is available."
                            ),
                            "authority_refs": [authority_ref],
                        }
                    ],
                }
            return _provider_response(output, len(self.calls))
        if node_id == "research_lead":
            self.calls.append({"kwargs": dict(kwargs), "request": request})
            rows = request["analysis_input"][
                "compact_scoped_reference_alias_table"
            ]["rows"]
            claims = [
                row["alias"]
                for row in rows
                if row["identity_kind"] == "claim"
            ]
            tasks = [
                row["alias"]
                for row in rows
                if row["identity_kind"] == "what_would_change"
            ]
            output = {
                "cross_cell_dependencies": [
                    {
                        "statement": (
                            "Demand durability constrains value capture."
                        ),
                        "claim_ids": claims,
                    }
                ],
                "conflict_adjudications": [
                    {
                        "involved_claim_ids": claims,
                        "terminal_state_summary": (
                            "All three cells remain bounded."
                        ),
                        "resolution_status": "bounded_not_resolved",
                        "statement": (
                            "The evidence supports a bounded joint view."
                        ),
                    }
                ],
                "variant_view": {
                    "statement": (
                        "The outlook varies with demand conversion."
                    ),
                    "claim_ids": claims,
                    "what_would_change_task_ids": tasks,
                },
                "remaining_gaps": [
                    {
                        "statement": (
                            "Future HBM financial durability remains unproven."
                        ),
                        "claim_ids": claims,
                        "what_would_change_task_ids": tasks,
                    }
                ],
            }
            return _provider_response(output, len(self.calls))
        return super().__call__(**kwargs)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RealisticFixtureContractError(
                f"realistic_fixture_duplicate_json_key:{key}"
            )
        result[key] = value
    return result


def load_mu_realistic_fixture_document(
    path: Path = MU_FIXTURE,
) -> dict[str, Any]:
    document = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
    )
    if not isinstance(document, dict) or set(document) != _EXPECTED_TOP_LEVEL:
        raise RealisticFixtureContractError(
            "realistic_fixture_top_level_contract_invalid"
        )
    if document["schema_version"] != EXPECTED_SCHEMA:
        raise RealisticFixtureContractError("realistic_fixture_schema_invalid")
    if document["fixture_id"] != EXPECTED_FIXTURE_ID:
        raise RealisticFixtureContractError("realistic_fixture_id_invalid")
    if document["source_object_sha256"] != EXPECTED_SOURCE_OBJECT_SHA256:
        raise RealisticFixtureContractError(
            "realistic_fixture_source_object_digest_invalid"
        )
    if document["source_input_digest"] != EXPECTED_SOURCE_INPUT_DIGEST:
        raise RealisticFixtureContractError(
            "realistic_fixture_source_input_digest_invalid"
        )
    digest_payload = {
        key: value
        for key, value in document.items()
        if key != "content_digest"
    }
    if canonical_digest(digest_payload) != document["content_digest"]:
        raise RealisticFixtureContractError(
            "realistic_fixture_content_digest_invalid"
        )
    boundary = document["provenance_and_nonpromotion_boundary"]
    if not isinstance(boundary, dict) or any(
        boundary.get(key) is not False
        for key in (
            "credentials_or_authorization_headers_included",
            "provider_output_or_private_reasoning_included",
            "mutable_work_unit_attempt_or_run_state_included",
            "business_acceptance_or_release_claim_included",
            "failed_output_business_promotable",
        )
    ):
        raise RealisticFixtureContractError(
            "realistic_fixture_nonpromotion_boundary_invalid"
        )
    return document


def load_mu_realistic_input_and_admission() -> tuple[
    S3ThreeCellBoundedAgentInputPack,
    S3ThreeCellBoundedAgentAdmission,
]:
    fixture = load_mu_realistic_fixture_document()
    input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(
        fixture["input_pack"]
    )
    identity = fixture["source_case_id_and_version"]
    if (
        input_pack.company != "MU"
        or input_pack.case_id != identity.get("case_id")
        or input_pack.case_version != identity.get("case_version")
        or input_pack.input_digest != fixture["source_input_digest"]
    ):
        raise RealisticFixtureContractError(
            "realistic_fixture_input_pack_identity_invalid"
        )
    admission = compile_s4_case_runtime_mandatory_safety_admission(
        S3ThreeCellBoundedAgentAdmission.model_validate(
            json.loads(MU_ADMISSION.read_text(encoding="utf-8"))
        ),
        updates={
            "admission_id": "fixture-s4-t06-mu-source-grounded-v7",
            "execution_mode": "fixture_only_mu_source_grounded_v7",
            "research_lead_transport_ref": (
                S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
            ),
        },
    )
    return input_pack, admission
