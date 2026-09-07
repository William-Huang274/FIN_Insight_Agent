from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.canonical_runtime import canonical_digest  # noqa: E402
from sec_agent.research.current_dynamic_writer import (  # noqa: E402
    CURRENT_DYNAMIC_WRITER_RUN_SCOPE,
    CURRENT_DYNAMIC_WRITER_SCOPE_DECISION_SCHEMA_VERSION,
    CURRENT_DYNAMIC_WRITER_SCOPE_DECISION_STATUS,
    CURRENT_DYNAMIC_WRITER_ZERO_CALL_SCHEMA_VERSION,
    CurrentDynamicWriterError,
    compile_r10_protected_writer_messages,
    compile_r10_report_contexts,
    compile_r10_writer_authority,
    compile_r10_writer_evaluation,
    compile_r10_writer_protection_contract,
    expected_current_dynamic_writer_budget,
    project_r10_writer_authority_catalog,
    validate_r10_protected_writer_draft,
)
from sec_agent.research.multi_agent_report_authority import (  # noqa: E402
    MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
    MultiAgentReportAuthorityError,
    protected_report_draft_tool,
    render_protected_report,
)


R10_AUTHORITY_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "content_repair_live_authority_v1_4.json"
)
R10_PUBLIC_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "content_repair_live_result_v1_4.json"
)
R10_PRIVATE_REF = (
    "data/workbench_private/fin_0_1_3_s3_current_dynamic_multi_agent/"
    "dell-current-dynamic-multi-agent-content-reassessment-resume-live-"
    "r10-20260823T194751Z/full_result.json"
)
R10_ASSESSMENT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "content_repair_R10_content_assessment_v1_0.json"
)
R9_PUBLIC_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "content_repair_live_result_v1_3.json"
)
R9_PRIVATE_REF = (
    "data/workbench_private/fin_0_1_3_s3_current_dynamic_multi_agent/"
    "dell-current-dynamic-multi-agent-content-repair-live-r9-"
    "20260823T185102Z/full_result.json"
)
R5_PUBLIC_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "submission_successor_live_result_v1_4.json"
)
R5_PRIVATE_REF = (
    "data/workbench_private/fin_0_1_3_s3_current_dynamic_multi_agent/"
    "dell-current-dynamic-multi-agent-submission-repair-resume-live-r5-"
    "20260823T220000Z/full_result.json"
)
PREDECESSOR_SOURCE_BOUND_REVIEW_REF = (
    "configs/research/fin_ia_0_1_3_s2_dell_multi_agent_source_bound_"
    "numeric_review_v1_0.json"
)
ANALYSIS_PROFILE_REF = (
    "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_agent_profile_v1_1.json"
)
SUBMISSION_PROFILE_REF = (
    "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_report_protected_"
    "remap_non_thinking_profile_v1_1.json"
)

SOURCE_BOUND_REVIEW_REF = (
    "configs/research/fin_ia_0_1_3_s2_dell_current_dynamic_multi_agent_"
    "R10_source_bound_numeric_review_v1_0.json"
)
SOURCE_BOUND_PROGRAM_REF = (
    "configs/research/fin_ia_0_1_3_s2_dell_current_dynamic_multi_agent_"
    "R10_source_bound_numeric_program_v1_0.json"
)
WRITER_AUTHORITY_CATALOG_REF = (
    "configs/research/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_authority_catalog_v1_0.json"
)
WRITER_PROTECTION_REF = (
    "configs/research/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_writer_protection_contract_v1_0.json"
)
ZERO_CALL_RESULT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_zero_call_result_v1_0.json"
)
SCOPE_DECISION_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
    "R10_protected_writer_scope_decision_v1_0.json"
)


def _path(ref: str) -> Path:
    return (ROOT / ref).resolve()


def _load(ref: str) -> dict[str, Any]:
    value = json.loads(_path(ref).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("current_dynamic_writer_json_object_required:" + ref)
    return value


def _sha(ref: str) -> str:
    return hashlib.sha256(_path(ref).read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_new(ref: str, value: Mapping[str, Any]) -> None:
    path = _path(ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _binding(ref: str, *, digest_field: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {"ref": ref, "sha256": _sha(ref)}
    if digest_field:
        payload = _load(ref)
        value = payload.get(digest_field)
        if not isinstance(value, str) or not value:
            raise RuntimeError("current_dynamic_writer_binding_digest_missing:" + ref)
        row.update({"digest_field": digest_field, "digest": value})
    return row


def _source_chain() -> dict[str, dict[str, Any]]:
    authority = _load(R10_AUTHORITY_REF)
    r10_public = _load(R10_PUBLIC_REF)
    r10_private = _load(R10_PRIVATE_REF)
    assessment = _load(R10_ASSESSMENT_REF)
    r9_public = _load(R9_PUBLIC_REF)
    r9_private = _load(R9_PRIVATE_REF)
    r5_public = _load(R5_PUBLIC_REF)
    r5_private = _load(R5_PRIVATE_REF)
    if not (
        r10_public.get("status") == "completed_contract_valid_reassessment_pending"
        and r10_private.get("status")
        == "completed_contract_valid_reassessment_pending"
        and r10_public.get("private_full_result_sha256") == _sha(R10_PRIVATE_REF)
        and r10_public.get("private_full_result_ref") == R10_PRIVATE_REF
        and assessment.get("source_result_sha256") == _sha(R10_PUBLIC_REF)
        and assessment.get("source_result_digest") == r10_public.get("result_digest")
        and assessment.get("private_full_result_sha256") == _sha(R10_PRIVATE_REF)
        and assessment.get("private_full_result_digest")
        == r10_private.get("full_result_digest")
        and assessment.get("authority_sha256") == _sha(R10_AUTHORITY_REF)
        and r10_private.get("authority_sha256") == _sha(R10_AUTHORITY_REF)
        and (r10_private.get("execution") or {}).get("new_provider_calls_attempted")
        == 4
        and (r10_private.get("execution") or {}).get("new_provider_http_200") == 4
        and (r10_private.get("claims") or {}).get("writer_called") is False
        and r10_private.get("R9_private_ref") == R9_PRIVATE_REF
        and r10_private.get("R9_private_full_result_digest")
        == r9_private.get("full_result_digest")
        and r9_public.get("private_full_result_sha256") == _sha(R9_PRIVATE_REF)
        and r9_public.get("result_digest") == r10_private.get("R9_public_result_digest")
        and r5_public.get("private_full_result_sha256") == _sha(R5_PRIVATE_REF)
        and r5_private.get("status") == "completed_contract_valid_assessment_pending"
        and authority.get("status")
        == "signed_exact_once_DELL_current_dynamic_multi_agent_content_reassessment_resume"
    ):
        raise RuntimeError("current_dynamic_writer_source_chain_invalid")
    return {
        "authority": authority,
        "r10_public": r10_public,
        "r10_private": r10_private,
        "assessment": assessment,
        "r9_public": r9_public,
        "r9_private": r9_private,
        "r5_public": r5_public,
        "r5_private": r5_private,
    }


def _claim(catalog: Mapping[str, Any], agent_id: str, index: int) -> dict[str, Any]:
    rows = [
        deepcopy(dict(row))
        for row in catalog.get("claims") or ()
        if row.get("agent_id") == agent_id and row.get("claim_index") == index
    ]
    if len(rows) != 1:
        raise RuntimeError("current_dynamic_writer_fake_claim_missing")
    return rows[0]


def _clause(
    *,
    agent_id: str,
    text: str,
    claim_ref: str = "",
    evidence_ref: str = "",
    authority_refs: tuple[str, ...] = (),
    gap_refs: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "model_text": text,
        "source_workpaper_agent_ids": [agent_id],
        "source_claim_refs": [claim_ref] if claim_ref else [],
        "evidence_refs": [evidence_ref] if evidence_ref else [],
        "authority_refs": list(authority_refs),
        "gap_refs": list(gap_refs),
    }


def _positive_payload(
    catalog: Mapping[str, Any], protection: Mapping[str, Any]
) -> dict[str, Any]:
    demand = _claim(catalog, "AGENT::DEMAND_QUALITY", 0)
    operating = _claim(catalog, "AGENT::OPERATING_PERFORMANCE", 2)
    value = _claim(catalog, "AGENT::VALUE_CAPTURE", 9)
    cash = _claim(catalog, "AGENT::CASH_CONVERSION", 5)
    supply = _claim(catalog, "AGENT::SUPPLY_RELATIONSHIP", 0)
    counter = _claim(catalog, "AGENT::COUNTEREVIDENCE", 3)
    demand_rule = next(
        row
        for row in protection["conditional_rules"]
        if row["rule_id"] == "same_quarter_signals_not_cohort_conversion"
    )
    demand_authority = tuple(demand_rule["trigger_authority_refs_all"])
    sections = [
        {
            "heading": "Demand quality",
            "clauses": [
                _clause(
                    agent_id="AGENT::DEMAND_QUALITY",
                    claim_ref=demand["claim_ref"],
                    evidence_ref="EV::9006E2D4E0F61CCF",
                    authority_refs=demand_authority,
                    gap_refs=("GAP::00730082A5C08C4C",),
                    text=(
                        "Orders and recognized revenue are parallel same-period "
                        "signals; without a cohort bridge they do not prove conversion."
                    ),
                )
            ],
        },
        {
            "heading": "Operating performance",
            "clauses": [
                _clause(
                    agent_id="AGENT::OPERATING_PERFORMANCE",
                    claim_ref=operating["claim_ref"],
                    evidence_ref="EV::7F4D7E6762C21D83",
                    text=(
                        "The signed margin bridge shows opposing gross-margin and "
                        "expense effects, so durability depends on later observations."
                    ),
                )
            ],
        },
        {
            "heading": "Value capture",
            "clauses": [
                _clause(
                    agent_id="AGENT::VALUE_CAPTURE",
                    claim_ref=value["claim_ref"],
                    evidence_ref="EV::5388E016C17032C1",
                    text=(
                        "Company margin direction cannot identify product pricing "
                        "power without direct price, cost, unit, and mix evidence."
                    ),
                )
            ],
        },
        {
            "heading": "Cash conversion",
            "clauses": [
                _clause(
                    agent_id="AGENT::CASH_CONVERSION",
                    claim_ref=cash["claim_ref"],
                    evidence_ref="EV::CAD2B8E9B11D864E",
                    gap_refs=("GAP::EF4839B4BF55ADD0",),
                    text=(
                        "The balance-sheet movement is only a working-capital proxy; "
                        "exact cash use and product attribution remain unresolved."
                    ),
                )
            ],
        },
        {
            "heading": "Supply relationship",
            "clauses": [
                _clause(
                    agent_id="AGENT::SUPPLY_RELATIONSHIP",
                    claim_ref=supply["claim_ref"],
                    evidence_ref="EV::4E05729492683532",
                    text=(
                        "Upstream capacity tension is an ecosystem signal, not proof "
                        "of issuer allocation, delivery timing, or product exposure."
                    ),
                )
            ],
        },
        {
            "heading": "Counterevidence",
            "clauses": [
                _clause(
                    agent_id="AGENT::COUNTEREVIDENCE",
                    claim_ref=counter["claim_ref"],
                    evidence_ref="EV::A74F01276941482E",
                    text=(
                        "Export controls remain an upstream issuer fact and only a "
                        "bounded scenario without a direct exposure mapping."
                    ),
                )
            ],
        },
    ]
    return {
        "schema_version": MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
        "report_topic": (
            "Demand durability, operating leverage, cash conversion, and counterevidence"
        ),
        "executive_thesis": [deepcopy(sections[0]["clauses"][0])],
        "sections": sections,
        "remaining_gaps": [
            _clause(
                agent_id="AGENT::DEMAND_QUALITY",
                gap_refs=("GAP::00730082A5C08C4C",),
                text=(
                    "The scale and timing of possible demand pull-forward remain "
                    "unmeasured in the currently reviewed evidence."
                ),
            ),
            _clause(
                agent_id="AGENT::CASH_CONVERSION",
                gap_refs=("GAP::EF4839B4BF55ADD0",),
                text=(
                    "Product-level working-capital and cash attribution remain "
                    "unavailable under the current evidence authority."
                ),
            ),
        ],
        "what_would_change": [
            _clause(
                agent_id="AGENT::DEMAND_QUALITY",
                claim_ref=demand["claim_ref"],
                gap_refs=("GAP::00730082A5C08C4C",),
                text=(
                    "A direct cohort bridge with delivery timing and cancellation "
                    "evidence would materially change the conversion judgment."
                ),
            ),
            _clause(
                agent_id="AGENT::VALUE_CAPTURE",
                claim_ref=value["claim_ref"],
                text=(
                    "Direct product price, cost, unit, and mix evidence would allow "
                    "a product-economics conclusion that is currently unavailable."
                ),
            ),
        ],
        "confidence": _clause(
            agent_id="AGENT::OPERATING_PERFORMANCE",
            claim_ref=operating["claim_ref"],
            text=(
                "Confidence is moderate because company-level facts are strong "
                "while product attribution and forward durability remain bounded."
            ),
        ),
    }


def build_zero_call_bundle() -> dict[str, Any]:
    chain = _source_chain()
    r10_private = chain["r10_private"]
    contexts, context_receipt = compile_r10_report_contexts(
        r10_private=r10_private,
        r9_private=chain["r9_private"],
        r5_private=chain["r5_private"],
    )
    predecessor_review = _load(PREDECESSOR_SOURCE_BOUND_REVIEW_REF)
    review, program, extended = compile_r10_writer_authority(
        workpapers=r10_private["final_workpapers"],
        specialist_contexts=contexts,
        predecessor_review=predecessor_review,
    )
    protection = compile_r10_writer_protection_contract(
        assessment=chain["assessment"],
        authority_catalog=extended,
        source_bound_program=program,
    )
    catalog = project_r10_writer_authority_catalog(
        authority_catalog=extended,
        protection=protection,
    )
    lead = r10_private["lead_bundle"]["rounds"][0]["decision"]
    writer_gate = compile_r10_writer_evaluation(
        assessment=chain["assessment"],
        lead_decision=lead,
        protection=protection,
    )
    messages = compile_r10_protected_writer_messages(
        workpapers=r10_private["final_workpapers"],
        writer_gate=writer_gate,
        authority_catalog=catalog,
        protection=protection,
    )
    tool = protected_report_draft_tool(authority_catalog=catalog)
    positive = _positive_payload(catalog, protection)
    fake_response = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_R10_protected_writer_zero",
                            "type": "function",
                            "function": {
                                "name": "submit_protected_report_draft",
                                "arguments": json.dumps(
                                    positive,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ),
                            },
                        }
                    ],
                },
            }
        ]
    }
    calls = fake_response["choices"][0]["message"]["tool_calls"]
    parsed = json.loads(calls[0]["function"]["arguments"])
    trusted = validate_r10_protected_writer_draft(
        parsed,
        authority_catalog=catalog,
        protection=protection,
    )
    rendered = render_protected_report(trusted, authority_catalog=catalog)

    def rejected(mutator: Any, expected_prefix: str) -> bool:
        candidate = deepcopy(positive)
        mutator(candidate)
        try:
            validate_r10_protected_writer_draft(
                candidate,
                authority_catalog=catalog,
                protection=protection,
            )
        except (CurrentDynamicWriterError, MultiAgentReportAuthorityError) as exc:
            return str(exc).startswith(expected_prefix)
        return False

    demand_no_boundary = rejected(
        lambda value: value["executive_thesis"][0].update(
            {
                "model_text": (
                    "Orders and recognized revenue support a strong demand "
                    "assessment under the currently reviewed evidence."
                )
            }
        ),
        "current_dynamic_writer_conditional_protection_invalid",
    )
    cash_no_proxy = rejected(
        lambda value: value["sections"][3]["clauses"][0].update(
            {
                "model_text": (
                    "The balance-sheet movement shows working-capital pressure "
                    "while product attribution remains unresolved."
                )
            }
        ),
        "current_dynamic_writer_conditional_protection_invalid",
    )
    arithmetic_necessity = rejected(
        lambda value: value["sections"][1]["clauses"][0].update(
            {
                "model_text": (
                    "Slower growth makes expense leverage narrowing an arithmetic "
                    "necessity under the current operating structure."
                )
            }
        ),
        "current_dynamic_writer_protected_surface_forbidden",
    )
    protected_number = rejected(
        lambda value: value["sections"][1]["clauses"][0].update(
            {"model_text": "Revenue improved by 88 percent in the quarter."}
        ),
        "multi_agent_report_model_text_unprotected_surface",
    )
    spelled_protected_number = rejected(
        lambda value: value["sections"][1]["clauses"][0].update(
            {
                "model_text": (
                    "Revenue improved by eighty-eight percent in the quarter."
                )
            }
        ),
        "current_dynamic_writer_protected_surface_forbidden",
    )
    forbidden_claims = set(protection["forbidden_claim_refs"])
    forbidden_authority = set(protection["forbidden_authority_refs"])
    tool_text = json.dumps(tool, ensure_ascii=False, sort_keys=True)
    checks = {
        "R10_public_private_authority_assessment_chain_bound": True,
        "R9_and_R5_context_lineage_bound": True,
        "six_R10_workpapers_reused_byte_immutable": (
            catalog.get("workpaper_digests")
            == sorted(
                str(row["workpaper_digest"])
                for row in r10_private["final_workpapers"]
            )
        ),
        "supply_report_context_projection_no_authority_change": (
            context_receipt[
                "evidence_numeric_relation_gap_and_case_authority_changed"
            ]
            is False
        ),
        "research_estimates_retained_without_output_authority": (
            (extended.get("coverage_receipt") or {}).get(
                "research_estimates_granted_output_authority"
            )
            is False
        ),
        "source_bound_review_reuses_only_previously_qualified_spans": (
            (review.get("successor_lineage") or {}).get(
                "new_evidence_or_source_span_admitted"
            )
            is False
        ),
        "unnormalized_upstream_inventory_claim_removed": all(
            ref not in tool_text for ref in forbidden_claims
        ),
        "unnormalized_upstream_inventory_authority_removed": all(
            ref not in tool_text for ref in forbidden_authority
        ),
        "R10_protection_contract_model_visible": (
            protection["protection_digest"] in messages[1]["content"]
        ),
        "positive_fake_tool_call_validates": (
            trusted.get("writer_protection_receipt", {}).get(
                "global_forbidden_surface_pass"
            )
            is True
        ),
        "positive_fake_report_renders_deterministically": (
            rendered.get("status") == "multi_agent_protected_report_rendered"
        ),
        "same_quarter_cohort_boundary_mutation_rejected": demand_no_boundary,
        "cash_proxy_boundary_mutation_rejected": cash_no_proxy,
        "arithmetic_necessity_mutation_rejected": arithmetic_necessity,
        "model_owned_protected_number_mutation_rejected": protected_number,
        "spelled_out_protected_number_mutation_rejected": (
            spelled_protected_number
        ),
        "fake_response_exactly_one_expected_tool_call": (
            len(calls) == 1
            and calls[0]["function"]["name"]
            == "submit_protected_report_draft"
            and fake_response["choices"][0]["finish_reason"] == "tool_calls"
        ),
    }
    if not all(checks.values()):
        failed = ",".join(sorted(key for key, passed in checks.items() if not passed))
        raise RuntimeError("current_dynamic_writer_zero_call_check_failed:" + failed)
    zero_body = {
        "schema_version": CURRENT_DYNAMIC_WRITER_ZERO_CALL_SCHEMA_VERSION,
        "status": "R10_bound_protected_writer_zero_call_proven",
        "recorded_at": _now(),
        "case_key": "DELL",
        "run_scope_id": CURRENT_DYNAMIC_WRITER_RUN_SCOPE,
        "source_bindings": {
            "R10_authority": _binding(R10_AUTHORITY_REF),
            "R10_public_result": _binding(R10_PUBLIC_REF, digest_field="result_digest"),
            "R10_private_full_result": _binding(
                R10_PRIVATE_REF, digest_field="full_result_digest"
            ),
            "R10_assessment": _binding(R10_ASSESSMENT_REF),
            "R9_public_result": _binding(R9_PUBLIC_REF, digest_field="result_digest"),
            "R9_private_full_result": _binding(
                R9_PRIVATE_REF, digest_field="full_result_digest"
            ),
            "R5_public_result": _binding(R5_PUBLIC_REF, digest_field="result_digest"),
            "R5_private_full_result": _binding(
                R5_PRIVATE_REF, digest_field="full_result_digest"
            ),
            "predecessor_source_bound_review": _binding(
                PREDECESSOR_SOURCE_BOUND_REVIEW_REF
            ),
        },
        "context_projection_receipt": context_receipt,
        "compiled_artifact_digests": {
            "source_bound_review_digest": review["review_digest"],
            "source_bound_program_digest": program["program_digest"],
            "writer_authority_catalog_digest": catalog["authority_catalog_digest"],
            "writer_protection_digest": protection["protection_digest"],
            "writer_gate_digest": writer_gate["writer_gate_digest"],
            "validated_fake_draft_digest": trusted["draft_digest"],
            "rendered_fake_report_digest": rendered["rendered_report_digest"],
        },
        "first_fresh_provider_frontier": "AGENT::WRITER::R10_PROTECTED_REPORT_ANALYSIS",
        "provider_topology": [
            "AGENT::WRITER::R10_PROTECTED_REPORT_ANALYSIS",
            "AGENT::WRITER::R10_PROTECTED_REPORT_SUBMISSION",
            "AGENT::WRITER::R10_PROTECTED_REPORT_SUBMISSION_CONTRACT_FEEDBACK_IF_REQUIRED",
        ],
        "model_visible_scale": {
            "message_characters": sum(len(row["content"]) for row in messages),
            "tool_schema_characters": len(tool_text),
            "workpaper_count": 6,
            "writer_claim_count": len(catalog["claims"]),
            "presentation_authority_count": len(catalog["presentation_authority"]),
            "gap_authority_count": len(catalog["gap_authority"]),
        },
        "execution_budget": expected_current_dynamic_writer_budget(),
        "execution": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "new_S1_S2_requests": 0,
            "new_retrieval_rounds": 0,
            "candidate_promotions": 0,
            "writer_called": False,
        },
        "checks": checks,
        "known_boundary": (
            "This zero-call proof validates R10 lineage, typed report authority, "
            "protected Writer input and a complete fake seam. It does not authorize "
            "or execute Writer live, accept the final report, pass S3, generalize, "
            "publish, or release."
        ),
    }
    zero = {**zero_body, "result_digest": canonical_digest(zero_body)}
    return {
        "review": review,
        "program": program,
        "catalog": catalog,
        "protection": protection,
        "zero": zero,
    }


def _build_scope_decision() -> dict[str, Any]:
    zero = _load(ZERO_CALL_RESULT_REF)
    scale = zero["model_visible_scale"]
    body = {
        "schema_version": CURRENT_DYNAMIC_WRITER_SCOPE_DECISION_SCHEMA_VERSION,
        "status": CURRENT_DYNAMIC_WRITER_SCOPE_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "MULTI_AGENT::DELL::R10_PROTECTED_WRITER",
        "run_scope_id": CURRENT_DYNAMIC_WRITER_RUN_SCOPE,
        "evidence_mode": "immutable_R10_workpapers_typed_authority_zero_new_evidence",
        "next_authorized_scope": CURRENT_DYNAMIC_WRITER_RUN_SCOPE,
        "replacement_is_new_logical_node_not_retry": True,
        "credential_presence_required": True,
        "R10_authority_public_private_assessment_required": True,
        "R10_workpapers_and_Lead_reuse_required": True,
        "protected_report_contract_required": True,
        "source_bound_numeric_authority_required": True,
        "material_and_L3_writer_protections_required": True,
        "deterministic_renderer_required": True,
        "writer_live_authorized_after_full_gate_clean_preflight_and_fresh_authority": True,
        "new_S1_S2_authorized": False,
        "new_retrieval_authorized": False,
        "external_source_network_authorized": False,
        "upstream_agent_rerun_authorized": False,
        "candidate_promotion_authorized": False,
        "S3_acceptance_authorized": False,
        "heterogeneous_generalization_authorized": False,
        "product_publication_authorized": False,
        "release_authorized": False,
        "bound_inputs": {
            "R10_authority": _binding(R10_AUTHORITY_REF),
            "R10_public_result": _binding(R10_PUBLIC_REF, digest_field="result_digest"),
            "R10_private_full_result": _binding(
                R10_PRIVATE_REF, digest_field="full_result_digest"
            ),
            "R10_assessment": _binding(R10_ASSESSMENT_REF),
            "R9_private_full_result": _binding(
                R9_PRIVATE_REF, digest_field="full_result_digest"
            ),
            "R5_private_full_result": _binding(
                R5_PRIVATE_REF, digest_field="full_result_digest"
            ),
            "source_bound_review": _binding(
                SOURCE_BOUND_REVIEW_REF, digest_field="review_digest"
            ),
            "source_bound_program": _binding(
                SOURCE_BOUND_PROGRAM_REF, digest_field="program_digest"
            ),
            "writer_authority_catalog": _binding(
                WRITER_AUTHORITY_CATALOG_REF,
                digest_field="authority_catalog_digest",
            ),
            "writer_protection_contract": _binding(
                WRITER_PROTECTION_REF, digest_field="protection_digest"
            ),
            "zero_call_result": _binding(
                ZERO_CALL_RESULT_REF, digest_field="result_digest"
            ),
            "analysis_profile": _binding(ANALYSIS_PROFILE_REF),
            "submission_profile": _binding(SUBMISSION_PROFILE_REF),
        },
        "implementation_bindings": [
            _binding("src/sec_agent/research/current_dynamic_writer.py"),
            _binding("src/sec_agent/research/multi_agent_report_authority.py"),
            _binding("src/sec_agent/research/source_bound_numeric_authority.py"),
            _binding("src/sec_agent/project_os_preflight.py"),
            _binding("scripts/research/run_s3_current_dynamic_writer_zero_call.py"),
            _binding("scripts/research/run_s3_current_dynamic_writer_live.py"),
        ],
        "execution_budget": expected_current_dynamic_writer_budget(),
        "token_budget_basis": {
            "writer_analysis": {
                "node_purpose": (
                    "Synthesize six R10 workpapers into a protected report plan "
                    "while preserving all material and L3 boundaries."
                ),
                "input_scale": (
                    f"{scale['message_characters']} model-visible characters, six "
                    f"workpapers, {scale['writer_claim_count']} claims, "
                    f"{scale['presentation_authority_count']} typed presentations."
                ),
                "required_outputs": [
                    "thesis_and_section_plan",
                    "claim_evidence_authority_map",
                    "material_boundary_checklist",
                    "counterthesis_gap_and_what_would_change_plan",
                ],
                "schema_burden": (
                    "Analysis prepares a nested protected report but does not submit "
                    "the final tool contract."
                ),
                "materiality_quality_risk": (
                    "High: synthesis can reintroduce cohort, cash, source-owner, "
                    "product-attribution, pull-forward, or leverage overstatement."
                ),
                "comparable_run_evidence": (
                    "R10 Demand and Lead analysis completed within the max-reasoning "
                    "profile; prior Writer synthesis required explicit boundary review."
                ),
                "reasoning_profile": "deepseek-v4-pro thinking enabled max",
                "maximum_completion_tokens": 16000,
                "maximum_calls": 1,
                "stop_and_truncation_behavior": (
                    "A length or empty-content finish is terminal for this authority; "
                    "no silent continuation or submission is permitted."
                ),
            },
            "writer_submission": {
                "node_purpose": (
                    "Submit one complete protected report draft using only the typed "
                    "R10 Writer authority projection."
                ),
                "input_scale": (
                    f"At least {scale['message_characters']} source characters plus "
                    "the completed analysis and a nested protected tool schema of "
                    f"{scale['tool_schema_characters']} characters."
                ),
                "required_outputs": [
                    "report_topic",
                    "executive_thesis",
                    "four_to_ten_sections",
                    "remaining_gaps",
                    "what_would_change",
                    "confidence",
                    "claim_evidence_authority_and_gap_refs",
                ],
                "schema_burden": (
                    "Nested numeric-free clauses with claim-scoped Evidence, typed "
                    "presentation authority, gaps, and deterministic render receipts."
                ),
                "materiality_quality_risk": (
                    "High: a structurally fluent report is invalid if any R10 "
                    "protection or reference scope is violated."
                ),
                "comparable_run_evidence": (
                    "Prior protected remap completed around six thousand output "
                    "tokens; twelve thousand prevents truncating required sections."
                ),
                "reasoning_profile": "deepseek-v4-pro thinking disabled strict tool",
                "maximum_completion_tokens": 12000,
                "maximum_calls": 2,
                "stop_and_truncation_behavior": (
                    "Stop after the first valid contract. One precise all-finding "
                    "feedback attempt is allowed; a second rejection or length finish "
                    "is terminal and preserves the failed run."
                ),
            },
        },
        "authority_statement": (
            "After the full repository gate, clean synced commit, repository-aware "
            "preflight, and a fresh exact-run authority, permit one Writer analysis "
            "and at most two strict submission attempts. Reuse every upstream R10 "
            "artifact; permit no research, retrieval, source, promotion, product "
            "acceptance, publication, or release action."
        ),
    }
    return {**body, "decision_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    bundle = build_zero_call_bundle()
    if not args.write:
        print(json.dumps(bundle["zero"], ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    for ref, key in (
        (SOURCE_BOUND_REVIEW_REF, "review"),
        (SOURCE_BOUND_PROGRAM_REF, "program"),
        (WRITER_AUTHORITY_CATALOG_REF, "catalog"),
        (WRITER_PROTECTION_REF, "protection"),
        (ZERO_CALL_RESULT_REF, "zero"),
    ):
        _write_new(ref, bundle[key])
    decision = _build_scope_decision()
    _write_new(SCOPE_DECISION_REF, decision)
    print(
        json.dumps(
            {
                "status": "written",
                "zero_call_result_ref": ZERO_CALL_RESULT_REF,
                "zero_call_result_digest": bundle["zero"]["result_digest"],
                "scope_decision_ref": SCOPE_DECISION_REF,
                "decision_digest": decision["decision_digest"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
