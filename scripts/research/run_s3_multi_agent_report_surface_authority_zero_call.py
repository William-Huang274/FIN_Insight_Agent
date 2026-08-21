from __future__ import annotations

from copy import deepcopy
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.research.multi_agent_report_authority import (  # noqa: E402
    MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
    MultiAgentReportAuthorityError,
    audit_legacy_report_protected_surfaces,
    compile_multi_agent_report_authority_catalog,
    extend_multi_agent_report_authority_catalog,
    protected_report_draft_tool,
    render_protected_report,
    validate_protected_report_draft,
)
from sec_agent.research.source_bound_numeric_authority import (  # noqa: E402
    SourceBoundNumericAuthorityError,
    compile_source_bound_numeric_authority_program,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest  # noqa: E402
from sec_agent.research.multi_agent_report_remap import (  # noqa: E402
    REPORT_REMAP_REPLACEMENT_RUN_SCOPE,
    REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_SCHEMA_VERSION,
    REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_STATUS,
    REPORT_REMAP_RUN_SCOPE,
    REPORT_REMAP_SCOPE_DECISION_SCHEMA_VERSION,
    REPORT_REMAP_SCOPE_DECISION_STATUS,
)


PRIVATE_RESULT_REF = (
    "data/workbench_private/model_runs/"
    "fin_0_1_3_s3_dell_multi_agent_preview_writer_terminal_submission_"
    "successor_20260821/full_result.json"
)
PUBLIC_RESULT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "writer_terminal_submission_successor_live_result_v1_0.json"
)
ASSESSMENT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "writer_terminal_submission_successor_content_assessment_v1_0.json"
)
SOURCE_BOUND_REVIEW_REF = (
    "configs/research/fin_ia_0_1_3_s2_dell_multi_agent_source_bound_"
    "numeric_review_v1_0.json"
)
RESULT_SCHEMA_VERSION = (
    "fin_ia_s3_multi_agent_report_surface_authority_zero_call_result_v1_1"
)
AUTHORITY_CATALOG_REF = (
    "configs/research/fin_ia_0_1_3_s3_dell_multi_agent_report_"
    "authority_catalog_v1_1.json"
)
PREDECESSOR_AUTHORITY_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_"
    "writer_terminal_submission_successor_live_authority_v1_0.json"
)
ZERO_CALL_RESULT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_multi_agent_report_"
    "surface_authority_zero_call_result_v1_1.json"
)
WRITER_REMAP_PROFILE_REF = (
    "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_report_"
    "protected_remap_non_thinking_profile_v1_0.json"
)
REPORT_REMAP_SCOPE_DECISION_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_scope_decision_v1_0.json"
)
FAILED_REMAP_AUTHORITY_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_live_authority_v1_0.json"
)
FAILED_REMAP_PUBLIC_RESULT_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_live_result_v1_0.json"
)
FAILED_REMAP_PRIVATE_RESULT_REF = (
    "data/workbench_private/model_runs/fin_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_20260821/terminal_failure.json"
)
WRITER_REMAP_REPLACEMENT_PROFILE_REF = (
    "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_report_"
    "protected_remap_non_thinking_profile_v1_1.json"
)
REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_REF = (
    "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_"
    "protected_report_remap_scope_decision_v1_1.json"
)


def _load(ref: str | Path) -> dict[str, Any]:
    path = Path(ref)
    if not path.is_absolute():
        path = ROOT / path
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(ref: str | Path) -> str:
    path = Path(ref)
    if not path.is_absolute():
        path = ROOT / path
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _binding(ref: str, *, digest_field: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {"ref": ref, "sha256": _sha(ref)}
    if digest_field:
        payload = _load(ref)
        digest = payload.get(digest_field)
        if not isinstance(digest, str) or not digest:
            raise RuntimeError("report_remap_scope_binding_digest_missing:" + ref)
        row.update({"digest_field": digest_field, "digest": digest})
    return row


def build_report_remap_scope_decision() -> dict[str, Any]:
    full = _load(PRIVATE_RESULT_REF)
    source_report_chars = len(
        json.dumps(
            full["report"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    authority_catalog = _load(AUTHORITY_CATALOG_REF)
    authority_catalog_chars = len(
        json.dumps(
            authority_catalog,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    body = {
        "schema_version": REPORT_REMAP_SCOPE_DECISION_SCHEMA_VERSION,
        "status": REPORT_REMAP_SCOPE_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "ALL",
        "run_scope_id": REPORT_REMAP_RUN_SCOPE,
        "evidence_mode": (
            "immutable_completed_report_plus_typed_authority_no_new_research"
        ),
        "next_authorized_scope": "one_writer_terminal_protected_contract_remap",
        "replacement_is_new_logical_node_not_retry": True,
        "chat_live_authorized": True,
        "credential_presence_required": True,
        "immutable_source_report_required": True,
        "protected_surface_contract_required": True,
        "deterministic_renderer_required": True,
        "separate_logical_node_and_contract_attempt_counts_required": True,
        "upstream_agent_rerun_authorized": False,
        "writer_research_analysis_authorized": False,
        "new_evidence_or_numeric_fact_authorized": False,
        "external_source_network_authorized": False,
        "candidate_promotion_authorized": False,
        "responses_live_authorized": False,
        "anthropic_live_authorized": False,
        "S1_acceptance_authorized": False,
        "S3_acceptance_authorized": False,
        "generalization_claim_authorized": False,
        "qualified_human_acceptance_authorized": False,
        "product_publication_authorized": False,
        "release_authorized": False,
        "bound_inputs": {
            "predecessor_live_authority": _binding(PREDECESSOR_AUTHORITY_REF),
            "predecessor_public_result": _binding(
                PUBLIC_RESULT_REF, digest_field="result_digest"
            ),
            "predecessor_content_assessment": _binding(ASSESSMENT_REF),
            "predecessor_private_full_result": _binding(
                PRIVATE_RESULT_REF, digest_field="full_result_digest"
            ),
            "report_surface_zero_call_proof": _binding(
                ZERO_CALL_RESULT_REF, digest_field="result_digest"
            ),
            "report_authority_catalog": _binding(
                AUTHORITY_CATALOG_REF, digest_field="authority_catalog_digest"
            ),
            "source_bound_numeric_review": _binding(SOURCE_BOUND_REVIEW_REF),
            "writer_submission_profile": _binding(WRITER_REMAP_PROFILE_REF),
        },
        "implementation_bindings": [
            _binding("src/sec_agent/research/multi_agent_report_authority.py"),
            _binding("src/sec_agent/research/multi_agent_report_remap.py"),
            _binding("src/sec_agent/project_os_preflight.py"),
            _binding("scripts/research/run_s3_multi_agent_report_remap_live.py"),
        ],
        "execution_limits": {
            "reused_specialist_plan_count": 6,
            "reused_lead_plan_count": 1,
            "reused_workpaper_count": 6,
            "reused_lead_coordination_count": 1,
            "reused_completed_challenge_repair_count": 3,
            "reused_role_evaluation_count": 6,
            "reused_cross_role_evaluation_count": 1,
            "reused_legacy_report_count": 1,
            "maximum_new_logical_model_nodes": 1,
            "maximum_contract_attempts": 2,
            "maximum_new_analysis_calls": 0,
            "maximum_new_writer_continuations": 0,
            "external_source_network_calls": 0,
            "candidate_promotions": 0,
        },
        "token_budget_basis": {
            "node_id": "AGENT::WRITER::PROTECTED_REPORT_REMAP",
            "purpose": "terminal_contract_remap_without_new_research",
            "source_report_characters": source_report_chars,
            "authority_catalog_characters": authority_catalog_chars,
            "required_section_count": len(full["report"]["sections"]),
            "required_gap_count": len(full["report"]["remaining_gaps"]),
            "required_wwc_count": len(full["report"]["what_would_change"]),
            "schema_burden": (
                "nested_six_section_protected_tool_with_claim_scoped_refs"
            ),
            "materiality_quality_risk": "high",
            "comparable_run_evidence": (
                "prior_writer_report_required_two_bounded_contract_attempts"
            ),
            "reasoning_profile": "thinking_disabled",
            "maximum_output_tokens": 7000,
            "maximum_contract_attempts": 2,
            "cost_and_latency_are_secondary_constraints": True,
            "stop_behavior": (
                "stop_after_first_valid_contract_or_terminal_after_second_rejection"
            ),
        },
        "authority_statement": (
            "Authorize one fresh Writer-only terminal remapping logical node and "
            "at most two bounded contract attempts. Preserve all upstream research "
            "and the immutable failed report. Permit no new analysis, continuation, "
            "Evidence, NumericFact, network, Candidate promotion or product acceptance."
        ),
    }
    return {**body, "decision_digest": canonical_digest(body)}


def build_report_remap_replacement_scope_decision() -> dict[str, Any]:
    initial = build_report_remap_scope_decision()
    body = {key: deepcopy(value) for key, value in initial.items() if key != "decision_digest"}
    body.update(
        {
            "schema_version": REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_SCHEMA_VERSION,
            "status": REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_STATUS,
            "run_scope_id": REPORT_REMAP_REPLACEMENT_RUN_SCOPE,
            "next_authorized_scope": (
                "one_writer_terminal_protected_contract_remap_replacement"
            ),
            "authority_statement": (
                "Preserve the first natural remap as a one-attempt output-length "
                "failure. Authorize one new Writer-only replacement logical node "
                "with at most two bounded contract attempts, twelve thousand "
                "output tokens per attempt, and zero analysis, continuation, "
                "upstream Agent, Evidence, network or Candidate-promotion calls."
            ),
        }
    )
    body["bound_inputs"]["writer_submission_profile"] = _binding(
        WRITER_REMAP_REPLACEMENT_PROFILE_REF
    )
    body["bound_inputs"].update(
        {
            "failed_remap_live_authority": _binding(
                FAILED_REMAP_AUTHORITY_REF, digest_field="authority_digest"
            ),
            "failed_remap_public_result": _binding(
                FAILED_REMAP_PUBLIC_RESULT_REF, digest_field="result_digest"
            ),
            "failed_remap_private_terminal_result": _binding(
                FAILED_REMAP_PRIVATE_RESULT_REF, digest_field="full_result_digest"
            ),
        }
    )
    body["token_budget_basis"].update(
        {
            "comparable_run_evidence": (
                "first_natural_remap_truncated_at_7000_after_six_sections_six_"
                "gaps_and_partial_second_wwc"
            ),
            "maximum_output_tokens": 12000,
        }
    )
    return {**body, "decision_digest": canonical_digest(body)}


def _nested_contexts_from_request(path: Path) -> list[dict[str, Any]]:
    try:
        capture = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    output: list[dict[str, Any]] = []
    messages = (capture.get("request_body") or {}).get("messages") or []
    for message in messages:
        content = message.get("content")
        if message.get("role") != "user" or not isinstance(content, str):
            continue
        try:
            outer = json.loads(content)
        except json.JSONDecodeError:
            continue
        for item in outer.get("task_context") or ():
            if not isinstance(item, Mapping) or not isinstance(item.get("content"), str):
                continue
            try:
                context = json.loads(str(item["content"]))
            except json.JSONDecodeError:
                continue
            if isinstance(context, dict) and "cell_analysis_view" in context:
                output.append(context)
    return output


def _load_final_contexts(full_result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    targets = {
        str(row["context_digest"]): str(row["agent_id"])
        for row in full_result["final_workpapers"]
    }
    found: dict[str, dict[str, Any]] = {}
    capture_root = ROOT / "data" / "captures"
    for path in capture_root.rglob("model_visible_request.json"):
        for context in _nested_contexts_from_request(path):
            digest = str(context.get("context_digest") or "")
            if digest in targets:
                found[targets[digest]] = context
    if set(found) != set(targets.values()):
        missing = sorted(set(targets.values()) - set(found))
        raise RuntimeError("final_specialist_context_capture_missing:" + ",".join(missing))
    return found


def _clause(
    *,
    agent_id: str,
    model_text: str,
    claim_ref: str = "",
    evidence_ref: str = "",
    authority_ref: str = "",
    gap_ref: str = "",
) -> dict[str, Any]:
    return {
        "model_text": model_text,
        "source_workpaper_agent_ids": [agent_id],
        "source_claim_refs": [claim_ref] if claim_ref else [],
        "evidence_refs": [evidence_ref] if evidence_ref else [],
        "authority_refs": [authority_ref] if authority_ref else [],
        "gap_refs": [gap_ref] if gap_ref else [],
    }


def _positive_payload(catalog: Mapping[str, Any]) -> dict[str, Any]:
    claims = list(catalog["claims"])
    first_claim_by_agent: dict[str, Mapping[str, Any]] = {}
    for claim in claims:
        first_claim_by_agent.setdefault(str(claim["agent_id"]), claim)
    agents = sorted(first_claim_by_agent)
    authority_claim = next(row for row in claims if row["authority_refs"])
    executive = _clause(
        agent_id=str(authority_claim["agent_id"]),
        claim_ref=str(authority_claim["claim_ref"]),
        evidence_ref=str(authority_claim["evidence_refs"][0]),
        authority_ref=str(authority_claim["authority_refs"][0]),
        model_text=(
            "The company level operating evidence is strong while product level "
            "attribution remains bounded by the available bridge."
        ),
    )
    sections = []
    for agent_id in agents:
        claim = first_claim_by_agent[agent_id]
        label = agent_id.split("::")[-1].replace("_", " ").title()
        sections.append(
            {
                "heading": label + " perspective",
                "clauses": [
                    _clause(
                        agent_id=agent_id,
                        claim_ref=str(claim["claim_ref"]),
                        evidence_ref=str(claim["evidence_refs"][0]),
                        model_text=(
                            "The reviewed evidence supports a bounded conclusion "
                            "while preserving the strongest alternative explanation."
                        ),
                    )
                ],
            }
        )
    first_gap_binding = next(
        row for row in catalog["workpaper_gap_bindings"] if row["gap_refs"]
    )
    gap_agent = str(first_gap_binding["agent_id"])
    gap_ref = str(first_gap_binding["gap_refs"][0])
    first_claim = first_claim_by_agent[gap_agent]
    return {
        "schema_version": MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
        "report_topic": "Demand durability, value capture and cash conversion",
        "executive_thesis": [executive],
        "sections": sections,
        "remaining_gaps": [
            _clause(
                agent_id=gap_agent,
                gap_ref=gap_ref,
                model_text=(
                    "Direct disclosure remains unavailable after the currently "
                    "authorized research routes."
                ),
            )
        ],
        "what_would_change": [
            _clause(
                agent_id=gap_agent,
                claim_ref=str(first_claim["claim_ref"]),
                gap_ref=gap_ref,
                model_text=(
                    "A direct issuer disclosure would materially narrow the "
                    "remaining uncertainty."
                ),
            ),
            _clause(
                agent_id=str(authority_claim["agent_id"]),
                claim_ref=str(authority_claim["claim_ref"]),
                model_text=(
                    "A verified reversal in the operating mechanism would change "
                    "the current judgment."
                ),
            ),
        ],
        "confidence": _clause(
            agent_id=str(authority_claim["agent_id"]),
            claim_ref=str(authority_claim["claim_ref"]),
            model_text=(
                "Confidence is moderate because typed company facts are available "
                "but product attribution remains incomplete."
            ),
        ),
    }


def _expect_failure(
    operation: Callable[[], object],
    *,
    code: str,
) -> bool:
    try:
        operation()
    except MultiAgentReportAuthorityError as exc:
        return exc.code == code
    return False


def _expect_source_failure(
    operation: Callable[[], object],
    *,
    code: str,
) -> bool:
    try:
        operation()
    except SourceBoundNumericAuthorityError as exc:
        return exc.code == code
    return False


def _material_surface_value(surface: str) -> tuple[str, Decimal]:
    number = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", surface)
    if number is None:
        raise ValueError("material_surface_numeric_value_missing")
    value = Decimal(number.group(0).replace(",", ""))
    upper = surface.upper()
    if upper.endswith("B"):
        value *= Decimal("1000000000")
    elif upper.endswith("M"):
        value *= Decimal("1000000")
    elif upper.endswith("K"):
        value *= Decimal("1000")
    unit = "USD" if "$" in surface else ("percent" if "%" in surface else "count")
    return unit, value


def _material_untyped_surface_status(
    *,
    report: Mapping[str, Any],
    catalog: Mapping[str, Any],
    source_bound_program: Mapping[str, Any],
) -> dict[str, Any]:
    report_text = json.dumps(report, ensure_ascii=False)
    authorized_values = {
        (str(row.get("unit") or ""), Decimal(str(row["value_decimal"])))
        for row in source_bound_program.get("numeric_fact_additions") or ()
    }
    authorized_values.update(
        (str(row.get("unit") or ""), Decimal(str(value)))
        for row in source_bound_program.get("bounded_presentation_additions") or ()
        for value in row.get("normalized_values") or ()
    )
    material_surfaces = [
        "$16.1B",
        "$24.4B",
        "$51.3B",
        "5,000",
        "$60B",
        "$25,854M",
        "$17,585M",
        "$15,052M",
        "$10,437M",
        "$11,578M",
        "$11,528M",
        "$8,237M",
        "$8,458M",
        "$5,713M",
        "$5,822M",
        "$44.0B",
    ]
    observed = [value for value in material_surfaces if value in report_text]
    typed_exact_surface = [
        value for value in observed if _material_surface_value(value) in authorized_values
    ]
    requires_s2 = [value for value in observed if value not in typed_exact_surface]
    return {
        "audited_material_surface_count": len(observed),
        "already_exactly_renderable_surface_count": len(typed_exact_surface),
        "already_exactly_renderable_surfaces": typed_exact_surface,
        "requires_typed_compilation_or_omission_count": len(requires_s2),
        "requires_typed_compilation_or_omission_surfaces": requires_s2,
        "source_visibility_treated_as_output_authority": False,
    }


def build_authority_catalog() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    full = _load(PRIVATE_RESULT_REF)
    contexts = _load_final_contexts(full)
    workpapers = [deepcopy(dict(row)) for row in full["final_workpapers"]]
    base_catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    review = _load(SOURCE_BOUND_REVIEW_REF)
    source_bound_program = compile_source_bound_numeric_authority_program(
        authority_catalog=base_catalog,
        specialist_contexts=contexts,
        review=review,
    )
    catalog = extend_multi_agent_report_authority_catalog(
        authority_catalog=base_catalog,
        source_bound_program=source_bound_program,
    )
    return full, source_bound_program, catalog


def build_result() -> dict[str, Any]:
    full, source_bound_program, catalog = build_authority_catalog()
    legacy_audit = audit_legacy_report_protected_surfaces(full["report"])
    payload = _positive_payload(catalog)
    trusted = validate_protected_report_draft(
        payload,
        authority_catalog=catalog,
    )
    rendered = render_protected_report(trusted, authority_catalog=catalog)

    raw_numeric = deepcopy(payload)
    raw_numeric["executive_thesis"][0]["model_text"] += " Revenue was $43.842B."
    authority_claim = next(row for row in catalog["claims"] if row["authority_refs"])
    other_claim = next(
        row
        for row in catalog["claims"]
        if row["agent_id"] != authority_claim["agent_id"]
        and authority_claim["authority_refs"][0] not in row["authority_refs"]
    )
    cross_claim = deepcopy(payload)
    cross_claim["executive_thesis"][0] = _clause(
        agent_id=str(other_claim["agent_id"]),
        claim_ref=str(other_claim["claim_ref"]),
        evidence_ref=str(other_claim["evidence_refs"][0]),
        authority_ref=str(authority_claim["authority_refs"][0]),
        model_text=(
            "The reviewed evidence supports a bounded conclusion while preserving "
            "the strongest alternative explanation."
        ),
    )
    identity_drift_contexts = deepcopy(contexts)
    first_agent = sorted(identity_drift_contexts)[0]
    identity_drift_contexts[first_agent]["cell_analysis_view"]["case_identity"][
        "case_key"
    ] = "MU"
    permutation_base_catalog = compile_multi_agent_report_authority_catalog(
        workpapers=list(reversed(workpapers)),
        specialist_contexts=dict(reversed(list(contexts.items()))),
    )
    permutation_program = compile_source_bound_numeric_authority_program(
        authority_catalog=permutation_base_catalog,
        specialist_contexts=dict(reversed(list(contexts.items()))),
        review=deepcopy(review),
    )
    permutation_catalog = extend_multi_agent_report_authority_catalog(
        authority_catalog=permutation_base_catalog,
        source_bound_program=permutation_program,
    )
    tool = protected_report_draft_tool(authority_catalog=catalog)
    tool_text = json.dumps(tool, ensure_ascii=False, sort_keys=True)
    source_visible_numeric_excerpt_count = sum(
        1
        for context in contexts.values()
        for row in context["cell_analysis_view"].get("evidence_fact_catalog") or ()
        if any(character.isdigit() for character in str(row.get("source_visible_fact_excerpt") or ""))
    )

    typed_status = _material_untyped_surface_status(
        report=full["report"],
        catalog=catalog,
        source_bound_program=source_bound_program,
    )
    source_value_mismatch_review = deepcopy(review)
    source_value_mismatch_review["decisions"][3]["normalized_values"] = [
        "2440000000"
    ]
    mutations = {
        "raw_numeric_surface_in_model_prose_fail_closed": _expect_failure(
            lambda: validate_protected_report_draft(
                raw_numeric, authority_catalog=catalog
            ),
            code="multi_agent_report_model_text_unprotected_surface",
        ),
        "cross_claim_authority_borrowing_fail_closed": _expect_failure(
            lambda: validate_protected_report_draft(
                cross_claim, authority_catalog=catalog
            ),
            code="multi_agent_report_clause_reference_scope_invalid",
        ),
        "cross_case_identity_drift_fail_closed": _expect_failure(
            lambda: compile_multi_agent_report_authority_catalog(
                workpapers=workpapers,
                specialist_contexts=identity_drift_contexts,
            ),
            code="multi_agent_report_case_identity_drift",
        ),
        "input_permutation_is_digest_stable": (
            permutation_catalog["authority_catalog_digest"]
            == catalog["authority_catalog_digest"]
            and permutation_program["program_digest"]
            == source_bound_program["program_digest"]
        ),
        "raw_evidence_numeric_excerpt_absent_from_tool_contract": (
            "booked $24.4 billion in AI orders" not in tool_text
            and "recognized $16.1 billion of AI server revenue" not in tool_text
            and "record $51.3 billion of AI backlog" not in tool_text
        ),
        "source_surface_normalization_mismatch_fails_closed": _expect_source_failure(
            lambda: compile_source_bound_numeric_authority_program(
                authority_catalog=base_catalog,
                specialist_contexts=contexts,
                review=source_value_mismatch_review,
            ),
            code="source_bound_admission_surface_value_mismatch",
        ),
        "source_metadata_date_not_automatically_promoted": (
            source_bound_program["coverage_receipt"]["temporal_authority_count"]
            == 1
            and all(
                row["date"] == "2025-10-31"
                for row in source_bound_program["temporal_authority_additions"]
            )
        ),
    }
    structure_pass = all(mutations.values()) and legacy_audit["status"] == "hard_fail"
    remap_ready = (
        structure_pass
        and typed_status["requires_typed_compilation_or_omission_count"] == 0
    )
    body = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": (
            "zero_call_structure_pass_s2_source_visible_numeric_compilation_pending"
            if structure_pass and not remap_ready
            else (
                "zero_call_structure_pass_terminal_remap_eligible"
                if remap_ready
                else "zero_call_structure_fail"
            )
        ),
        "recorded_at": _now(),
        "bound_inputs": {
            "private_full_result": {
                "ref": PRIVATE_RESULT_REF,
                "sha256": _sha(PRIVATE_RESULT_REF),
                "full_result_digest": full["full_result_digest"],
            },
            "public_result": {
                "ref": PUBLIC_RESULT_REF,
                "sha256": _sha(PUBLIC_RESULT_REF),
                "result_digest": _load(PUBLIC_RESULT_REF)["result_digest"],
            },
            "content_assessment": {
                "ref": ASSESSMENT_REF,
                "sha256": _sha(ASSESSMENT_REF),
            },
            "source_bound_numeric_review": {
                "ref": SOURCE_BOUND_REVIEW_REF,
                "sha256": _sha(SOURCE_BOUND_REVIEW_REF),
            },
        },
        "actual_dell_replay": {
            "base_authority_catalog_digest": base_catalog[
                "authority_catalog_digest"
            ],
            "source_bound_program_digest": source_bound_program["program_digest"],
            "authority_catalog_digest": catalog["authority_catalog_digest"],
            "coverage_receipt": catalog["coverage_receipt"],
            "source_bound_coverage_receipt": source_bound_program[
                "coverage_receipt"
            ],
            "source_visible_numeric_excerpt_count": source_visible_numeric_excerpt_count,
            "typed_presentation_count": len(catalog["presentation_authority"]),
            "legacy_report_audit": legacy_audit,
            "material_surface_disposition": typed_status,
            "positive_protected_contract_replay": {
                "draft_digest": trusted["draft_digest"],
                "rendered_report_digest": rendered["rendered_report_digest"],
                "rendered_section_count": len(rendered["sections"]),
                "model_owned_prose_numeric_free": True,
                "protected_surfaces_harness_rendered": True,
            },
        },
        "mutation_results": mutations,
        "case_neutral_test_matrix": {
            "test_refs": [
                "tests/test_s2_source_bound_numeric_authority.py",
                "tests/test_s3_multi_agent_report_authority.py"
            ],
            "cases": ["DELL", "MU", "NVDA", "ORCL"],
            "required_command": (
                "pytest -q tests/test_s2_source_bound_numeric_authority.py "
                "tests/test_s3_multi_agent_report_authority.py"
            ),
            "purpose": (
                "Prove that the compiler, validator and renderer do not contain "
                "DELL-specific business branches."
            ),
        },
        "execution": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "candidate_promotions": 0,
            "upstream_agent_reruns": 0,
            "legacy_result_mutated": False,
        },
        "decision": {
            "report_surface_contract_engineering_pass": structure_pass,
            "current_legacy_report_financial_truth_L1_pass": False,
            "terminal_writer_remapping_live_ready": remap_ready,
            "earliest_remaining_owner": (
                "S3_writer_terminal_remapping"
                if remap_ready
                else "S2_numeric_authority_compilation"
            ),
            "required_next_action": (
                "If the full repository gate remains green, issue a fresh exact-once "
                "Writer-only authority and remap the immutable report analysis into "
                "the protected contract. Do not rerun Specialists or retrieval."
                if remap_ready
                else (
                    "Compile or omit every remaining material source-visible surface "
                    "before authorizing any Writer-only remapping call."
                )
            ),
            "forbidden_next_actions": [
                "rerun_six_specialists",
                "rerun_retrieval_without_a_new_evidence_need",
                "raise_free_prose_character_or_numeric_tolerance",
                "treat_source_visibility_as_output_authority",
                "declare_S3_or_release_pass",
            ],
        },
        "boundary": (
            "This zero-call result proves a provider-neutral protected report "
            "surface contract and a qualified S2 source-bound authority extension. "
            "It does not accept the legacy DELL report, prove the remapped report's "
            "content quality, qualify generalization, authorize a paid call, or pass "
            "S1, S3, S4 or S5."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--write-authority-catalog", action="store_true")
    actions.add_argument("--write-remap-scope-decision", action="store_true")
    actions.add_argument(
        "--write-remap-replacement-scope-decision", action="store_true"
    )
    args = parser.parse_args()
    if args.write_remap_replacement_scope_decision:
        decision = build_report_remap_replacement_scope_decision()
        path = ROOT / REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_REF
        path.write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "report_remap_replacement_scope_decision_materialized",
                    "ref": REPORT_REMAP_REPLACEMENT_SCOPE_DECISION_REF,
                    "decision_digest": decision["decision_digest"],
                },
                ensure_ascii=False,
            )
        )
    elif args.write_remap_scope_decision:
        decision = build_report_remap_scope_decision()
        path = ROOT / REPORT_REMAP_SCOPE_DECISION_REF
        path.write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "report_remap_scope_decision_materialized",
                    "ref": REPORT_REMAP_SCOPE_DECISION_REF,
                    "decision_digest": decision["decision_digest"],
                },
                ensure_ascii=False,
            )
        )
    elif args.write_authority_catalog:
        _, _, catalog = build_authority_catalog()
        path = ROOT / AUTHORITY_CATALOG_REF
        path.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "authority_catalog_materialized",
                    "ref": AUTHORITY_CATALOG_REF,
                    "authority_catalog_digest": catalog[
                        "authority_catalog_digest"
                    ],
                },
                ensure_ascii=False,
            )
        )
    else:
        print(json.dumps(build_result(), ensure_ascii=False, indent=2))
