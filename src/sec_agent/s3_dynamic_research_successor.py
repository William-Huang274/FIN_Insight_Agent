from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.evidence_request import (
    EvidenceRequest,
    EvidenceRequestCompiler,
    EvidenceRequestCompileOverrides,
    EvidenceRequestPolicy,
    EvidenceRequestRoleRule,
)
from sec_agent.canonical_runtime.models import (
    DecisionSurfaceCellVersion,
    DecisionSurfaceContractVersion,
    EvidenceSlotVersion,
    canonical_digest,
)


POLICY_SCHEMA = (
    "fin_ia_0_1_3_s3_dynamic_research_planner_evidence_request_and_"
    "content_quality_entry_policy_v1_0"
)
PROGRAM_SCHEMA = "fin_ia_0_1_3_s3_dynamic_research_successor_program_v1_0"
CONTRACT_REF = (
    "fin_0_1_3.S3.dynamic_research_evidence_repair_and_content_quality_successor:v1"
)
RUN_SCOPE = (
    "FIN_0_1_3_S3_DYNAMIC_RESEARCH_PLANNER_EVIDENCE_REQUEST_"
    "AND_CONTENT_QUALITY_ZERO_CALL"
)
CASES = ("DELL", "MU", "NVDA")
CORE_CELLS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)
ELIGIBLE_GAP_CLASSES = {
    "needs_source",
    "needs_parser",
    "needs_numeric_recompute",
    "needs_relationship_resolution",
    "needs_counterevidence",
}
TERMINAL_OBSERVATION_OUTCOMES = {"accepted", "rejected", "typed_gap"}
READJUDICATION_STATES = {
    "supported",
    "supported_with_limits",
    "mixed",
    "cannot_infer",
    "not_supported",
}
STATIC_TIME = datetime(2026, 8, 11, tzinfo=timezone.utc)
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])\d[\d,.]*(?:%|x|倍)?(?![A-Za-z0-9_])")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]+|[\u4e00-\u9fff]")
_BOUNDARY_RE = re.compile(
    r"cannot infer|cannot establish|not enough|insufficient|未披露|不足以|"
    r"不能推断|无法判断|边界|缺口",
    re.IGNORECASE,
)
_DECISION_RE = re.compile(
    r"supports?|weakens?|strengthens?|overturns?|implies?|because|therefore|"
    r"支持|削弱|加强|推翻|意味着|因为|因此|传导|导致|取决于",
    re.IGNORECASE,
)


class S3DynamicResearchSuccessorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_s3_dynamic_research_successor_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    digest_body = {key: value for key, value in policy.items() if key != "result_digest"}
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("result_digest") != canonical_digest(digest_body)
    ):
        raise S3DynamicResearchSuccessorError("s3_successor_policy_identity_invalid")
    loop = policy.get("evidence_request_loop") or {}
    if set(loop.get("eligible_gap_classes") or ()) != ELIGIBLE_GAP_CLASSES:
        raise S3DynamicResearchSuccessorError("s3_successor_gap_classes_invalid")
    if policy.get("zero_call_authority", {}).get("fresh_authority_required_before_any_live") is not True:
        raise S3DynamicResearchSuccessorError("s3_successor_live_boundary_invalid")
    return policy


def compile_s3_dynamic_research_successor_program(
    *,
    policy: Mapping[str, Any],
    surface_decision: Mapping[str, Any],
    claim_decision: Mapping[str, Any],
    synthesis_decision: Mapping[str, Any],
    writer_decision: Mapping[str, Any],
    quality_decision: Mapping[str, Any],
    dell_business_assessment: Mapping[str, Any],
    report_pair: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Connect the existing S3 assets without executing a model or source tool.

    ``report_pair`` may contain already-captured ``direct_baseline`` and
    ``final_writer`` report objects.  It is inspected in memory; the returned
    program contains only fingerprints, counts, typed findings and source
    digests, never raw report prose.
    """

    _assert_inputs(
        policy=policy,
        surface_decision=surface_decision,
        claim_decision=claim_decision,
        synthesis_decision=synthesis_decision,
        writer_decision=writer_decision,
        quality_decision=quality_decision,
        dell_business_assessment=dell_business_assessment,
    )
    surfaces = surface_decision["dynamic_decision_surface_program"]["surfaces"]
    cards = claim_decision["claim_quality_program"]["core_claim_cards"]
    syntheses = synthesis_decision["cross_cell_synthesis_program"]["case_syntheses"]
    planner_states = _compile_planner_states(surfaces=surfaces, cards=cards, syntheses=syntheses)
    request_policy = _compile_request_policy(surfaces)
    repair_requests = _compile_repair_requests(
        surfaces=surfaces,
        cards=cards,
        syntheses=syntheses,
        request_policy=request_policy,
        policy=policy,
    )
    mechanism_program = _compile_mechanism_and_wwc(cards=cards, syntheses=syntheses)
    information_economy = _compile_information_economy_pair(
        report_pair=report_pair,
        assessment=dell_business_assessment,
    )
    quality_packet = _compile_dell_quality_packet(
        assessment=dell_business_assessment,
        information_economy=information_economy,
        quality_decision=quality_decision,
    )
    observed = {
        "cases": len(planner_states),
        "decision_cells": sum(len(row["cells"]) for row in planner_states),
        "current_pack_adjudicated_cells": sum(
            cell["state"] == "adjudicated_current_pack"
            for row in planner_states
            for cell in row["cells"]
        ),
        "planned_cells_without_current_judgment": sum(
            cell["state"] == "planned_evidence_needed"
            for row in planner_states
            for cell in row["cells"]
        ),
        "compiled_repair_requests": len(repair_requests),
        "mechanism_chains": len(mechanism_program["mechanism_chains"]),
        "wwc_conditions": len(mechanism_program["what_would_change"]),
        "numeric_wwc_without_authority": sum(
            row["operationalization_status"]
            == "cannot_operationalize_numeric_threshold_with_current_evidence"
            for row in mechanism_program["what_would_change"]
        ),
        "formal_quality_scores": 0,
        "paired_assessments": 0,
        "qualified_human_acceptances": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "business_artifact_promotions": 0,
    }
    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "policy_digest": policy["result_digest"],
        "upstream_digests": {
            "S3_01": surface_decision["record_digest"],
            "S3_02": claim_decision["record_digest"],
            "S3_03": synthesis_decision["record_digest"],
            "S3_04": writer_decision["record_digest"],
            "S3_05": quality_decision["record_digest"],
            "DELL_business_assessment": dell_business_assessment["assessment_digest"],
        },
        "planner_states": planner_states,
        "evidence_request_policy_digest": canonical_digest(
            request_policy.model_dump(mode="json")
        ),
        "repair_requests": repair_requests,
        "repair_observations": [],
        "readjudication_receipts": [],
        "loop_revision": 1,
        "mechanism_and_wwc": mechanism_program,
        "information_economy": information_economy,
        "dell_fixed_pack_quality_packet": quality_packet,
        "observed_counts": observed,
        "stage_boundary": {
            "zero_call_successor": "engineering_candidate_compiled",
            "canonical_evidence_requests": "compiled_not_admitted",
            "saved_report_pair_inspection": information_economy["source_mode"],
            "historical_dell_candidate_relabelled": False,
            "formal_agentic_research": False,
            "post_repair_final_delivery": False,
            "formal_eight_dimension_score": False,
            "paired_assessment": False,
            "qualified_human_content_acceptance": False,
            "owner_acceptance": False,
            "release": False,
        },
    }
    program = {**body, "program_digest": canonical_digest(body)}
    validate_s3_dynamic_research_successor_program(program, policy=policy)
    return program


def validate_s3_dynamic_research_successor_program(
    program: Mapping[str, Any], *, policy: Mapping[str, Any]
) -> None:
    body = {key: deepcopy(value) for key, value in program.items() if key != "program_digest"}
    if (
        program.get("schema_version") != PROGRAM_SCHEMA
        or program.get("contract_ref") != CONTRACT_REF
        or program.get("run_scope") != RUN_SCOPE
        or program.get("policy_digest") != policy.get("result_digest")
        or program.get("program_digest") != canonical_digest(body)
    ):
        raise S3DynamicResearchSuccessorError("s3_successor_program_binding_invalid")
    states = program.get("planner_states") or []
    if [row.get("case_key") for row in states] != list(CASES):
        raise S3DynamicResearchSuccessorError("s3_successor_case_surface_invalid")
    for state in states:
        _validate_planner_state(state)
    request_ids: set[str] = set()
    for row in program.get("repair_requests") or []:
        request = row.get("canonical_request") or {}
        try:
            EvidenceRequest.model_validate(request)
        except Exception as exc:
            raise S3DynamicResearchSuccessorError(
                "s3_successor_canonical_request_invalid"
            ) from exc
        request_id = str(request.get("request_id") or "")
        if not request_id or request_id in request_ids:
            raise S3DynamicResearchSuccessorError("s3_successor_request_identity_invalid")
        request_ids.add(request_id)
        if (
            row.get("repair_request_digest")
            != canonical_digest(
                {key: value for key, value in row.items() if key != "repair_request_digest"}
            )
            or
            row.get("gap_class") not in ELIGIBLE_GAP_CLASSES
            or row.get("status")
            not in {"compiled_not_admitted", "observation_accepted_pending_readjudication", "re_adjudicated", "rejected", "typed_gap"}
            or request.get("execution_admission") != "not_admitted"
            or request.get("planning_authority") != "shadow"
            or request.get("budget", {}).get("tool_call_limit") != 1
        ):
            raise S3DynamicResearchSuccessorError("s3_successor_request_boundary_invalid")
    pending = {
        row["canonical_request"]["request_id"]
        for row in program.get("repair_requests") or []
        if row["status"] == "observation_accepted_pending_readjudication"
    }
    receipts = {row.get("request_id") for row in program.get("readjudication_receipts") or []}
    if pending & receipts:
        raise S3DynamicResearchSuccessorError("s3_successor_readjudication_state_invalid")
    if program.get("observed_counts", {}).get("formal_quality_scores") != 0:
        raise S3DynamicResearchSuccessorError("s3_successor_formal_score_forbidden")
    mechanism = program.get("mechanism_and_wwc") or {}
    if mechanism.get("program_digest") != canonical_digest(
        {key: value for key, value in mechanism.items() if key != "program_digest"}
    ):
        raise S3DynamicResearchSuccessorError("s3_successor_mechanism_program_digest_invalid")
    information_economy = program.get("information_economy") or {}
    if information_economy.get("information_economy_digest") != canonical_digest(
        {
            key: value
            for key, value in information_economy.items()
            if key != "information_economy_digest"
        }
    ):
        raise S3DynamicResearchSuccessorError("s3_successor_information_economy_digest_invalid")
    packet = program.get("dell_fixed_pack_quality_packet") or {}
    if packet.get("quality_packet_digest") != canonical_digest(
        {key: value for key, value in packet.items() if key != "quality_packet_digest"}
    ):
        raise S3DynamicResearchSuccessorError("s3_successor_quality_packet_digest_invalid")
    for receipt in program.get("readjudication_receipts") or []:
        if receipt.get("readjudication_digest") != canonical_digest(
            {key: value for key, value in receipt.items() if key != "readjudication_digest"}
        ):
            raise S3DynamicResearchSuccessorError("s3_successor_readjudication_digest_invalid")
    for field in (
        "provider_calls",
        "model_calls",
        "network_calls",
        "source_calls",
        "retries",
        "fallbacks",
        "business_artifact_promotions",
    ):
        if program.get("observed_counts", {}).get(field) != 0:
            raise S3DynamicResearchSuccessorError("s3_successor_zero_call_boundary_invalid")
    boundary = program.get("stage_boundary") or {}
    if any(
        boundary.get(field) is not False
        for field in (
            "historical_dell_candidate_relabelled",
            "formal_agentic_research",
            "post_repair_final_delivery",
            "formal_eight_dimension_score",
            "paired_assessment",
            "qualified_human_content_acceptance",
            "owner_acceptance",
            "release",
        )
    ):
        raise S3DynamicResearchSuccessorError("s3_successor_promotion_boundary_invalid")


def apply_repair_observation(
    program: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    request_id: str,
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Record a captured fake/replay observation without changing a judgment."""

    validate_s3_dynamic_research_successor_program(program, policy=policy)
    revised = deepcopy(dict(program))
    revised.pop("program_digest", None)
    request = _request_by_id(revised, request_id)
    if request["status"] != "compiled_not_admitted":
        raise S3DynamicResearchSuccessorError("s3_successor_request_not_observable")
    outcome = str(observation.get("outcome") or "")
    if outcome not in TERMINAL_OBSERVATION_OUTCOMES:
        raise S3DynamicResearchSuccessorError("s3_successor_observation_outcome_invalid")
    if not observation.get("capture_ref") or not _digest_like(observation.get("capture_digest")):
        raise S3DynamicResearchSuccessorError("s3_successor_capture_binding_invalid")
    evidence_ref = observation.get("evidence_ref")
    if outcome == "accepted":
        if observation.get("evidence_gate_status") != "accepted" or not evidence_ref:
            raise S3DynamicResearchSuccessorError("s3_successor_accepted_evidence_binding_invalid")
        affected = _affected_cells(revised, request["case_key"], request["cell_id"])
        for cell in _case_state(revised, request["case_key"])["cells"]:
            if cell["cell_id"] in affected:
                cell["state"] = "needs_readjudication"
                cell["pending_observation_request_ids"] = sorted(
                    set(cell.get("pending_observation_request_ids") or ()) | {request_id}
                )
        request["status"] = "observation_accepted_pending_readjudication"
        request["affected_cell_ids"] = affected
    else:
        if evidence_ref is not None or not str(observation.get("reason_code") or ""):
            raise S3DynamicResearchSuccessorError("s3_successor_nonaccepted_observation_invalid")
        request["status"] = outcome
        request["affected_cell_ids"] = []
        target = _cell_by_id(revised, request["case_key"], request["cell_id"])
        target["state"] = "repair_terminal_gap_retained"
    observation_body = {
        "request_id": request_id,
        "case_key": request["case_key"],
        "cell_id": request["cell_id"],
        "outcome": outcome,
        "capture_ref": observation["capture_ref"],
        "capture_digest": observation["capture_digest"],
        "evidence_gate_status": observation.get("evidence_gate_status"),
        "evidence_ref": evidence_ref,
        "reason_code": observation.get("reason_code"),
        "simulation_or_saved_replay_only": True,
    }
    revised["repair_observations"].append(
        {**observation_body, "observation_digest": canonical_digest(observation_body)}
    )
    _reseal_request(request)
    _reseal_planner_state(_case_state(revised, request["case_key"]))
    revised["loop_revision"] = int(revised["loop_revision"]) + 1
    revised["program_digest"] = canonical_digest(revised)
    validate_s3_dynamic_research_successor_program(revised, policy=policy)
    return revised


def record_affected_cell_readjudication(
    program: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    request_id: str,
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Seal re-adjudication only when every affected Cell is explicitly reviewed."""

    validate_s3_dynamic_research_successor_program(program, policy=policy)
    revised = deepcopy(dict(program))
    revised.pop("program_digest", None)
    request = _request_by_id(revised, request_id)
    if request["status"] != "observation_accepted_pending_readjudication":
        raise S3DynamicResearchSuccessorError("s3_successor_readjudication_not_pending")
    observation = next(
        row for row in revised["repair_observations"] if row["request_id"] == request_id
    )
    expected = set(request["affected_cell_ids"])
    observed = {str(row.get("cell_id") or "") for row in decisions}
    if observed != expected or len(decisions) != len(expected):
        raise S3DynamicResearchSuccessorError("s3_successor_readjudication_coverage_invalid")
    receipts = []
    for decision in sorted(decisions, key=lambda row: str(row["cell_id"])):
        cell_id = str(decision["cell_id"])
        if decision.get("judgment_state") not in READJUDICATION_STATES:
            raise S3DynamicResearchSuccessorError("s3_successor_readjudication_state_invalid")
        refs = list(decision.get("support_refs") or ()) + list(
            decision.get("counterevidence_refs") or ()
        )
        if not refs or not str(decision.get("mechanism") or "").strip() or not str(
            decision.get("boundary") or ""
        ).strip():
            raise S3DynamicResearchSuccessorError("s3_successor_readjudication_content_invalid")
        if decision.get("judgment_changed") is True and observation["evidence_ref"] not in refs:
            raise S3DynamicResearchSuccessorError("s3_successor_changed_judgment_new_evidence_missing")
        if decision.get("observation_digest") != observation["observation_digest"]:
            raise S3DynamicResearchSuccessorError("s3_successor_readjudication_observation_mismatch")
        body = {
            "request_id": request_id,
            "case_key": request["case_key"],
            "cell_id": cell_id,
            "judgment_state": decision["judgment_state"],
            "judgment_changed": bool(decision.get("judgment_changed")),
            "support_refs": sorted(str(value) for value in decision.get("support_refs") or ()),
            "counterevidence_refs": sorted(
                str(value) for value in decision.get("counterevidence_refs") or ()
            ),
            "mechanism": str(decision["mechanism"]),
            "boundary": str(decision["boundary"]),
            "wwc_ref": str(decision.get("wwc_ref") or ""),
            "observation_digest": observation["observation_digest"],
        }
        receipt = {**body, "readjudication_digest": canonical_digest(body)}
        receipts.append(receipt)
        cell = _cell_by_id(revised, request["case_key"], cell_id)
        cell["state"] = "adjudicated_after_repair"
        cell["current_judgment_ref"] = receipt["readjudication_digest"]
        cell["pending_observation_request_ids"] = []
    request["status"] = "re_adjudicated"
    revised["readjudication_receipts"].extend(receipts)
    _reseal_request(request)
    _reseal_planner_state(_case_state(revised, request["case_key"]))
    revised["loop_revision"] = int(revised["loop_revision"]) + 1
    revised["program_digest"] = canonical_digest(revised)
    validate_s3_dynamic_research_successor_program(revised, policy=policy)
    return revised


def compile_wwc_authority(
    condition: Mapping[str, Any], *, allowed_numeric_authority_refs: Sequence[str] = ()
) -> dict[str, Any]:
    threshold = str(condition.get("threshold") or "").strip()
    if not threshold:
        raise S3DynamicResearchSuccessorError("s3_successor_wwc_threshold_missing")
    proposed_ref = str(condition.get("threshold_authority_ref") or "")
    numeric = bool(_NUMBER_RE.search(threshold))
    if numeric and proposed_ref not in set(allowed_numeric_authority_refs):
        return {
            "threshold_surface_digest": canonical_digest({"threshold": threshold}),
            "threshold_kind": "numeric_or_numeric_like",
            "threshold_authority_ref": None,
            "operationalization_status": (
                "cannot_operationalize_numeric_threshold_with_current_evidence"
            ),
        }
    return {
        "threshold_surface_digest": canonical_digest({"threshold": threshold}),
        "threshold_kind": "numeric_authority_bound" if numeric else "qualitative_observable_condition",
        "threshold_authority_ref": (
            proposed_ref if numeric else "policy:qualitative_observable_condition"
        ),
        "operationalization_status": "operationalizable",
    }


def evaluate_information_economy(
    report: Mapping[str, Any],
    *,
    terminal_l1_codes: Sequence[str] = (),
    writer_source_access_count: int = 0,
) -> dict[str, Any]:
    """Return a prose-free decision-density and repetition projection."""

    sections = list(report.get("sections") or ())
    if not sections:
        raise S3DynamicResearchSuccessorError("s3_successor_report_sections_missing")
    points: list[dict[str, Any]] = []
    section_rows: list[dict[str, Any]] = []
    for section in sections:
        section_id = str(section.get("section_id") or "")
        if not section_id:
            raise S3DynamicResearchSuccessorError("s3_successor_report_section_id_missing")
        section_points = list(section.get("points") or ())
        section_refs: set[str] = set()
        for index, point in enumerate(section_points, start=1):
            text = str(point.get("text") or "").strip()
            if not text:
                raise S3DynamicResearchSuccessorError("s3_successor_report_point_text_missing")
            evidence_refs = sorted(str(value) for value in point.get("evidence_aliases") or ())
            numeric_refs = sorted(str(value) for value in point.get("numeric_refs") or ())
            gap_refs = sorted(str(value) for value in point.get("gap_aliases") or ())
            refs = sorted(set(evidence_refs + numeric_refs + gap_refs))
            section_refs.update(refs)
            normalized = _normalize_text(text)
            points.append(
                {
                    "point_ref": f"{section_id}:{index}",
                    "section_id": section_id,
                    "text_fingerprint": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                    "semantic_tokens": _semantic_tokens(normalized),
                    "char_count": len(text),
                    "evidence_refs": evidence_refs,
                    "numeric_refs": numeric_refs,
                    "gap_refs": gap_refs,
                    "all_refs": refs,
                    "boundary_markers": len(_BOUNDARY_RE.findall(text)),
                    "decision_markers": len(_DECISION_RE.findall(text)),
                    "epistemic_status": str(point.get("epistemic_status") or ""),
                }
            )
        section_rows.append(
            {
                "section_id": section_id,
                "point_count": len(section_points),
                "unique_ref_count": len(section_refs),
                "section_digest": canonical_digest(
                    {
                        "section_id": section_id,
                        "point_fingerprints": [row["text_fingerprint"] for row in points if row["section_id"] == section_id],
                        "refs": sorted(section_refs),
                    }
                ),
            }
        )
    duplicates = []
    for index, left in enumerate(points):
        for right in points[index + 1 :]:
            if left["section_id"] == right["section_id"]:
                continue
            similarity = _jaccard(left["semantic_tokens"], right["semantic_tokens"])
            ref_overlap = _jaccard(left["all_refs"], right["all_refs"])
            if left["text_fingerprint"] == right["text_fingerprint"] or (
                similarity >= 0.45 and ref_overlap >= 0.50
            ):
                duplicates.append(
                    {
                        "left_ref": left["point_ref"],
                        "right_ref": right["point_ref"],
                        "semantic_similarity": round(similarity, 4),
                        "evidence_ref_overlap": round(ref_overlap, 4),
                    }
                )
    unsupported = [
        row["point_ref"]
        for row in points
        if not row["all_refs"]
        and row["epistemic_status"] not in {"cannot_infer", "explicit_gap", "gap"}
    ]
    executive_overload = [
        row["point_ref"]
        for row in points
        if row["section_id"] == "executive_thesis"
        and (row["char_count"] > 260 or len(row["all_refs"]) > 8)
    ]
    boundary_points = sum(row["boundary_markers"] > 0 for row in points)
    decision_points = sum(row["decision_markers"] > 0 for row in points)
    section_ids = {row["section_id"] for row in section_rows}
    hard = []
    if unsupported:
        hard.append({"code": "unsupported_material_claim", "point_refs": unsupported})
    if terminal_l1_codes:
        hard.append(
            {
                "code": "numeric_or_identity_authority_violation",
                "source_codes": sorted(set(terminal_l1_codes)),
            }
        )
    if writer_source_access_count:
        hard.append({"code": "writer_source_bypass", "observed_count": writer_source_access_count})
    if "counter_thesis_risks_and_gaps" not in section_ids:
        hard.append({"code": "missing_strongest_counterthesis"})
    if "what_would_change" not in section_ids or not any(
        row["section_id"] == "what_would_change" for row in points
    ):
        hard.append({"code": "missing_what_would_change_section"})
    quality = []
    if duplicates:
        quality.append({"code": "cross_section_repetition", "pair_count": len(duplicates)})
    if executive_overload:
        quality.append({"code": "overloaded_executive_point", "point_refs": executive_overload})
    novelty = (len(points) - len({row["right_ref"] for row in duplicates})) / max(len(points), 1)
    if novelty < 0.85:
        quality.append({"code": "low_claim_novelty", "novelty_ratio": round(novelty, 4)})
    decision_density = decision_points / max(len(points), 1)
    if decision_density < 0.50:
        quality.append({"code": "weak_decision_density", "decision_marker_point_ratio": round(decision_density, 4)})
    boundary_ratio = boundary_points / max(len(points), 1)
    if boundary_ratio > 0.35:
        quality.append({"code": "excess_boundary_language", "boundary_point_ratio": round(boundary_ratio, 4)})
    projection = {
        "section_count": len(section_rows),
        "point_count": len(points),
        "sections": section_rows,
        "cross_section_duplicate_pairs": duplicates,
        "claim_novelty_ratio": round(novelty, 4),
        "decision_marker_point_ratio": round(decision_density, 4),
        "boundary_point_ratio": round(boundary_ratio, 4),
        "hard_failures": hard,
        "quality_findings": quality,
        "raw_prose_persisted": False,
    }
    return {**projection, "projection_digest": canonical_digest(projection)}


def _compile_planner_states(
    *,
    surfaces: Sequence[Mapping[str, Any]],
    cards: Sequence[Mapping[str, Any]],
    syntheses: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    card_map = {(str(row["case_key"]), str(row["program_cell_id"])): row for row in cards}
    gap_claim_ids = {
        str(gap["source_claim_id"])
        for synthesis in syntheses
        for gap in synthesis.get("gaps") or ()
    }
    states = []
    for surface in surfaces:
        case_key = str(surface["case_key"])
        cells = []
        for cell in surface["cells"]:
            cell_id = str(cell["cell_key"])
            card = card_map.get((case_key, cell_id))
            state = "adjudicated_current_pack" if card else "planned_evidence_needed"
            if card and card["claim_card_id"] in gap_claim_ids:
                state = "repair_eligible"
            body = {
                "cell_id": cell_id,
                "business_decision_role": _business_role(cell),
                "why_material": _why_material(cell),
                "owner_role": cell["owner_role"],
                "materiality": cell["materiality"],
                "dependency_cell_ids": list(cell.get("dependency_cell_keys") or ()),
                "evidence_slot_count": len(cell.get("evidence_slots") or ()),
                "evidence_binding_status": cell["evidence_binding"]["binding_status"],
                "current_judgment_ref": card["claim_card_id"] if card else None,
                "state": state,
                "pending_observation_request_ids": [],
                "stop_condition": cell["stop_rule"],
                "downstream_decision": _downstream_decision(cell),
            }
            cells.append(body)
        state_body = {
            "case_key": case_key,
            "case_id": surface["case_id"],
            "company_name": surface["company_name"],
            "surface_digest": surface["surface_digest"],
            "cell_count": len(cells),
            "fixed_call_count": None,
            "cells": cells,
        }
        states.append({**state_body, "planner_state_digest": canonical_digest(state_body)})
    return states


def _compile_request_policy(surfaces: Sequence[Mapping[str, Any]]) -> EvidenceRequestPolicy:
    observed: dict[str, dict[str, set[str]]] = {}
    for surface in surfaces:
        for cell in surface["cells"]:
            for slot in cell.get("evidence_slots") or ():
                role = str(slot["evidence_role"])
                row = observed.setdefault(role, {"source": set(), "acceptance": set()})
                row["source"].add(str(slot["source_policy_ref"]))
                row["acceptance"].add(str(slot["acceptance_role"]))
    rules = {
        role: EvidenceRequestRoleRule(
            accepted_evidence_role=role,
            evidence_domain=role,
            allowed_source_policy_refs=tuple(sorted(values["source"])),
            allowed_acceptance_roles=tuple(sorted(values["acceptance"])),
            required_forbidden_substitutions=(),
            metadata_binding_requirements=(
                "canonical_identity",
                "publication_or_observation_time",
                "source_authority",
                "capture_lineage",
            ),
            numeric_binding_requirements=(),
            acceptable_proxy=(),
            preferred_routes=("shared_evidence_orchestrator",),
            fallback_routes=(),
            top_k=5,
            candidate_limit=10,
            tool_call_limit=1,
            elapsed_seconds_limit=120,
        )
        for role, values in sorted(observed.items())
    }
    return EvidenceRequestPolicy(
        policy_ref="fin_0_1_3.S3.dynamic_research.canonical_evidence_request:v1",
        role_rules=rules,
    )


def _compile_repair_requests(
    *,
    surfaces: Sequence[Mapping[str, Any]],
    cards: Sequence[Mapping[str, Any]],
    syntheses: Sequence[Mapping[str, Any]],
    request_policy: EvidenceRequestPolicy,
    policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    surface_map = {str(row["case_key"]): row for row in surfaces}
    cards_by_id = {str(row["claim_card_id"]): row for row in cards}
    requests = []
    compiler = EvidenceRequestCompiler(request_policy)
    for synthesis in syntheses:
        case_key = str(synthesis["case_key"])
        surface = surface_map[case_key]
        cells = {str(row["cell_key"]): row for row in surface["cells"]}
        contract = _contract_version(surface, policy)
        for gap in synthesis.get("gaps") or ():
            card = cards_by_id[str(gap["source_claim_id"])]
            cell_id = str(card["program_cell_id"])
            cell = cells[cell_id]
            slot_index, slot = _select_slot(cell, gap)
            cell_version = _cell_version(surface, cell, contract, policy)
            slot_version = _slot_version(
                surface, cell, slot, slot_index, cell_version, policy
            )
            compiled = compiler.compile(
                contract=contract,
                cell=cell_version,
                slot=slot_version,
                overrides=EvidenceRequestCompileOverrides(
                    requester_role=cell["owner_role"],
                    product_intent=(f"resolve:{gap['gap_id']}",),
                    granularity="cell_slot",
                ),
            )
            source_basis = gap.get("source_basis") or {}
            previous = []
            if source_basis.get("gap_code"):
                previous.append(str(source_basis["gap_code"]))
            body = {
                "gap_id": gap["gap_id"],
                "gap_class": _gap_class(gap, card),
                "case_key": case_key,
                "cell_id": cell_id,
                "materiality": gap["priority"],
                "impact": gap["impact"],
                "previous_rejections": previous,
                "next_evidence_route": gap["next_evidence_route"],
                "return_contract": ["accepted", "rejected", "typed_gap", "needs_repair"],
                "canonical_request": compiled.request.model_dump(mode="json"),
                "input_lineage_digest": compiled.input_lineage_digest,
                "status": "compiled_not_admitted",
                "affected_cell_ids": [],
            }
            requests.append({**body, "repair_request_digest": canonical_digest(body)})
    return sorted(requests, key=lambda row: (row["case_key"], row["gap_id"]))


def _compile_mechanism_and_wwc(
    *, cards: Sequence[Mapping[str, Any]], syntheses: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    dependency_by_claim: dict[str, set[str]] = {}
    for synthesis in syntheses:
        for dependency in synthesis.get("dependencies") or ():
            left = str(dependency["from_claim_id"])
            right = str(dependency["to_claim_id"])
            dependency_by_claim.setdefault(left, set()).add(right)
            dependency_by_claim.setdefault(right, set()).add(left)
    chains = []
    conditions = []
    for card in cards:
        claim_id = str(card["claim_card_id"])
        evidence_refs = sorted(str(value) for value in card.get("support_candidate_ids") or ())
        counter_refs = sorted(
            str(value) for value in card.get("counterevidence_candidate_ids") or ()
        )
        body = {
            "case_key": card["case_key"],
            "claim_card_id": claim_id,
            "observed_fact_or_signal_refs": evidence_refs,
            "economic_transmission_hypothesis": card["mechanism_atom"],
            "supporting_and_counterevidence_refs": {
                "support": evidence_refs,
                "counterevidence": counter_refs,
            },
            "affected_decision_cells": [card["program_cell_id"]],
            "cross_cell_claim_refs": sorted(dependency_by_claim.get(claim_id, set())),
            "financial_or_operating_implication": {
                "answer_direction": card["answer_direction"],
                "epistemic_state": card["epistemic_state"],
            },
            "confidence_and_cannot_infer_boundary": {
                "confidence": card["confidence"],
                "evidence_boundary": list(card.get("evidence_boundary") or ()),
                "typed_gaps": deepcopy(card.get("typed_gaps") or ()),
            },
        }
        chains.append({**body, "mechanism_chain_digest": canonical_digest(body)})
        numeric_refs = {
            f"numeric:{fact['candidate_id']}" for fact in card.get("numeric_facts") or ()
        }
        for condition in card.get("what_would_change") or ():
            authority = compile_wwc_authority(
                condition, allowed_numeric_authority_refs=tuple(sorted(numeric_refs))
            )
            condition_body = {
                "case_key": card["case_key"],
                "claim_card_id": claim_id,
                "alias": condition["alias"],
                "current_judgment": card["answer_direction"],
                "decisive_variable": condition["metric_or_event"],
                "observable_measure": condition["metric_or_event"],
                "direction": condition["direction"],
                "time_window": condition["time_window"],
                "next_disclosure_or_observation_route": condition["next_evidence_route"],
                "re_adjudication_owner": _owner_for_card(card),
                **authority,
            }
            conditions.append(
                {**condition_body, "wwc_condition_digest": canonical_digest(condition_body)}
            )
    body = {
        "mechanism_chains": chains,
        "what_would_change": conditions,
        "model_created_financial_facts": 0,
        "unbound_numeric_thresholds_promoted": 0,
    }
    return {**body, "program_digest": canonical_digest(body)}


def _compile_information_economy_pair(
    *, report_pair: Mapping[str, Any] | None, assessment: Mapping[str, Any]
) -> dict[str, Any]:
    if report_pair is None:
        content = assessment["content_shape"]
        quality = [
            {
                "code": "weak_decision_density",
                "basis": "business_assessment:decision_density",
            },
            {
                "code": "cross_section_repetition",
                "basis": "business_assessment:decision_density.remaining_gap",
            },
            {
                "code": "overloaded_executive_point",
                "basis": "business_assessment:decision_density.remaining_gap",
            },
        ]
        body = {
            "source_mode": "public_business_assessment_projection_no_raw_report",
            "same_input_pair": assessment["internal_direct_and_agent_same_input"]
            if "internal_direct_and_agent_same_input" in assessment
            else assessment["layered_control_observation"]["verdict"].startswith("agent_chain"),
            "baseline": deepcopy(content["current_direct_baseline"]),
            "agent": deepcopy(content["current_agent"]),
            "agent_hard_failures": [
                {
                    "code": "numeric_or_identity_authority_violation",
                    "count": assessment["layered_control_observation"]["agent_final_L1_findings"],
                }
            ],
            "agent_quality_findings": quality,
            "raw_prose_persisted": False,
        }
        return {**body, "information_economy_digest": canonical_digest(body)}
    baseline = evaluate_information_economy(report_pair["direct_baseline"])
    agent = evaluate_information_economy(
        report_pair["final_writer"],
        terminal_l1_codes=tuple(
            str(value) for value in report_pair.get("terminal_l1_codes") or ()
        ),
        writer_source_access_count=int(report_pair.get("writer_source_access_count", 0)),
    )
    body = {
        "source_mode": "immutable_private_capture_in_memory_prose_free_projection",
        "source_terminal_digest": report_pair.get("source_terminal_digest"),
        "source_terminal_sha256": report_pair.get("source_terminal_sha256"),
        "same_input_pair": True,
        "baseline": baseline,
        "agent": agent,
        "raw_prose_persisted": False,
    }
    return {**body, "information_economy_digest": canonical_digest(body)}


def _compile_dell_quality_packet(
    *,
    assessment: Mapping[str, Any],
    information_economy: Mapping[str, Any],
    quality_decision: Mapping[str, Any],
) -> dict[str, Any]:
    assessment_dimensions = {
        str(row["dimension"]): row for row in assessment["dimensions"]
    }
    reason_map = {
        "Q1": "demand_authenticity_and_sustainability",
        "Q2": "evidence_utilization",
        "Q3": "profit_transmission_and_cash",
        "Q4": "supply_capacity_and_execution",
        "Q5": "decision_density",
        "Q6": "counterevidence_and_risk",
        "Q7": "what_would_change",
        "Q8": "decision_density",
    }
    dimensions = []
    for dimension_id, source_key in reason_map.items():
        source = assessment_dimensions[source_key]
        dimensions.append(
            {
                "dimension_id": dimension_id,
                "status": "evidence_compiled_not_formally_scored",
                "source_assessment_dimension": source_key,
                "source_verdict": source["verdict"],
                "reason_digest": canonical_digest(
                    {
                        "business_observation": source["business_observation"],
                        "remaining_gap": source["remaining_gap"],
                    }
                ),
                "score": None,
            }
        )
    body = {
        "case_key": "DELL",
        "source_run_id": assessment["exact_live"]["run_id"],
        "source_agent_result_digest": assessment["comparison_basis"][
            "current_agent_result_digest"
        ],
        "source_pack_digest": assessment["comparison_basis"]["current_source_pack_digest"],
        "source_assessment_digest": assessment["assessment_digest"],
        "L1_status": "fail_immutable_historical_candidate",
        "L1_finding_count": assessment["layered_control_observation"][
            "agent_final_L1_findings"
        ],
        "L2_status": "pass_on_recorded_assessment",
        "formal_scoreability": "blocked_before_L3_scoring",
        "dimensions": dimensions,
        "total_score": None,
        "formal_pass": False,
        "information_economy_digest": information_economy[
            "information_economy_digest"
        ],
        "paired_contract": {
            "same_input_direct_and_agent": assessment["comparison_basis"][
                "current_agent_result_digest"
            ]
            is not None
            and assessment["layered_control_observation"]["verdict"].startswith(
                "agent_chain"
            ),
            "formal_paired_assessment": False,
            "reason": "candidate_L1_failed_and_no_post_successor_final_delivery",
        },
        "reference_isolation": {
            "codex_reference_required": True,
            "reference_hidden_from_model_and_runner": True,
            "reference_content_present_in_packet": False,
        },
        "qualified_human_content_acceptance": {
            "required": quality_decision["research_quality_gate_program"][
                "stage_boundary"
            ]["qualified_human_content_acceptance"]
            is False,
            "status": "pending",
            "automation_may_sign": False,
        },
        "repair_targets": [
            "executable_what_would_change",
            "evidence_to_economic_mechanism_bridge",
            "cross_section_information_economy",
            "senior_decision_density",
        ],
        "non_S3_boundaries_preserved": [
            "external_candidate_coverage_RC_P36_157",
            "valuation_and_issuer_specific_supply_semantics_RC_P36_165",
        ],
        "historical_candidate_relabelled_or_promoted": False,
    }
    return {**body, "quality_packet_digest": canonical_digest(body)}


def _contract_version(
    surface: Mapping[str, Any], policy: Mapping[str, Any]
) -> DecisionSurfaceContractVersion:
    case_key = str(surface["case_key"])
    return DecisionSurfaceContractVersion(
        tenant_id="fin013-internal",
        project_id="fin013-repair-closeout",
        case_id=surface["case_id"],
        created_at=STATIC_TIME,
        recorded_at=STATIC_TIME,
        actor_snapshot_ref="actor:deterministic_research_lead",
        permission_snapshot_ref="permission:s3_zero_call_only",
        policy_config_refs=(policy["result_digest"],),
        correlation_id=f"fin013-s3-successor-{case_key.lower()}",
        content_digest=surface["surface_digest"],
        current_status="accepted_input_projection",
        contract_id=f"fin013-s3-surface-{case_key.lower()}",
        contract_version_id=f"fin013-s3-surface-{case_key.lower()}:v1",
        contract_version=1,
        query=f"Dynamic research for {surface['company_name']}",
        as_of=STATIC_TIME,
        universe=(case_key,),
        language="zh-CN",
        universal_pack_refs=("universal-core:v1",),
        sector_pack_refs=("sector-ai-infrastructure:v2",),
        report_type_pack_refs=("deep-research-workpaper:v1",),
        compiler_policy_ref="fin013:dynamic_research_successor:v1",
        required_cell_ids=tuple(str(row["cell_key"]) for row in surface["cells"]),
    )


def _cell_version(
    surface: Mapping[str, Any],
    cell: Mapping[str, Any],
    contract: DecisionSurfaceContractVersion,
    policy: Mapping[str, Any],
) -> DecisionSurfaceCellVersion:
    cell_id = str(cell["cell_key"])
    return DecisionSurfaceCellVersion(
        tenant_id=contract.tenant_id,
        project_id=contract.project_id,
        case_id=contract.case_id,
        created_at=STATIC_TIME,
        recorded_at=STATIC_TIME,
        actor_snapshot_ref="actor:deterministic_research_lead",
        permission_snapshot_ref="permission:s3_zero_call_only",
        policy_config_refs=(policy["result_digest"],),
        correlation_id=contract.correlation_id,
        content_digest=canonical_digest(cell),
        current_status="accepted_input_projection",
        contract_version_id=contract.contract_version_id,
        cell_id=cell_id,
        cell_version_id=f"{contract.contract_version_id}:{cell_id}:v1",
        cell_version=1,
        decision_question=cell["decision_question"],
        origin_type=cell["origin_type"],
        owner_role=cell["owner_role"],
        materiality=cell["materiality"],
        dependency_cell_ids=tuple(cell.get("dependency_cell_keys") or ()),
        stop_rule=cell["stop_rule"],
        what_would_change="; ".join(cell.get("what_would_change") or ()),
    )


def _slot_version(
    surface: Mapping[str, Any],
    cell: Mapping[str, Any],
    slot: Mapping[str, Any],
    index: int,
    cell_version: DecisionSurfaceCellVersion,
    policy: Mapping[str, Any],
) -> EvidenceSlotVersion:
    slot_id = f"{cell['cell_key']}::{slot['evidence_role']}::{index}"
    return EvidenceSlotVersion(
        tenant_id=cell_version.tenant_id,
        project_id=cell_version.project_id,
        case_id=surface["case_id"],
        created_at=STATIC_TIME,
        recorded_at=STATIC_TIME,
        actor_snapshot_ref="actor:deterministic_research_lead",
        permission_snapshot_ref="permission:s3_zero_call_only",
        policy_config_refs=(policy["result_digest"],),
        correlation_id=cell_version.correlation_id,
        content_digest=canonical_digest(slot),
        current_status="accepted_input_projection",
        cell_version_id=cell_version.cell_version_id,
        evidence_slot_id=slot_id,
        slot_version_id=f"{cell_version.cell_version_id}:{slot_id}:v1",
        slot_version=1,
        evidence_role=slot["evidence_role"],
        entity_scope=tuple(slot["entity_scope"]),
        period_scope=slot["period_scope"],
        metric_scope=tuple(slot.get("metric_scope") or ()),
        source_policy_ref=slot["source_policy_ref"],
        forbidden_substitutions=tuple(slot.get("forbidden_substitutions") or ()),
        acceptance_role=slot["acceptance_role"],
        required=bool(slot.get("required", True)),
    )


def _select_slot(
    cell: Mapping[str, Any], gap: Mapping[str, Any]
) -> tuple[int, Mapping[str, Any]]:
    slots = list(cell.get("evidence_slots") or ())
    if not slots:
        raise S3DynamicResearchSuccessorError("s3_successor_gap_cell_slot_missing")
    route = str(gap.get("next_evidence_route") or "").casefold()
    scored = []
    for index, slot in enumerate(slots, start=1):
        score = sum(
            str(metric).replace("_", " ").casefold() in route
            for metric in slot.get("metric_scope") or ()
        )
        scored.append((score, -index, index, slot))
    _, _, index, slot = max(scored, key=lambda row: (row[0], row[1]))
    return index, slot


def _gap_class(gap: Mapping[str, Any], card: Mapping[str, Any]) -> str:
    text = json.dumps(
        {
            "gap": gap,
            "typed": card.get("typed_gaps") or (),
        },
        ensure_ascii=False,
    ).casefold()
    if "counter" in text or "反" in text or "risk" in text:
        return "needs_counterevidence"
    if "relationship" in text or "allocation" in text or "named" in text:
        return "needs_relationship_resolution"
    if "reproducible" in text or "recompute" in text:
        return "needs_numeric_recompute"
    if "parser" in text or "table" in text:
        return "needs_parser"
    return "needs_source"


def _affected_cells(program: Mapping[str, Any], case_key: str, cell_id: str) -> list[str]:
    state = _case_state(program, case_key)
    dependents: dict[str, set[str]] = {}
    for cell in state["cells"]:
        for dependency in cell.get("dependency_cell_ids") or ():
            dependents.setdefault(str(dependency), set()).add(str(cell["cell_id"]))
    affected = {cell_id}
    frontier = [cell_id]
    while frontier:
        current = frontier.pop()
        for dependent in dependents.get(current, set()):
            if dependent not in affected:
                affected.add(dependent)
                frontier.append(dependent)
    return sorted(affected)


def _case_state(program: Mapping[str, Any], case_key: str) -> dict[str, Any]:
    try:
        return next(row for row in program["planner_states"] if row["case_key"] == case_key)
    except StopIteration as exc:
        raise S3DynamicResearchSuccessorError("s3_successor_case_missing") from exc


def _cell_by_id(program: Mapping[str, Any], case_key: str, cell_id: str) -> dict[str, Any]:
    try:
        return next(
            row for row in _case_state(program, case_key)["cells"] if row["cell_id"] == cell_id
        )
    except StopIteration as exc:
        raise S3DynamicResearchSuccessorError("s3_successor_cell_missing") from exc


def _request_by_id(program: Mapping[str, Any], request_id: str) -> dict[str, Any]:
    try:
        return next(
            row
            for row in program["repair_requests"]
            if row["canonical_request"]["request_id"] == request_id
        )
    except StopIteration as exc:
        raise S3DynamicResearchSuccessorError("s3_successor_request_missing") from exc


def _validate_planner_state(state: Mapping[str, Any]) -> None:
    cells = state.get("cells") or []
    if (
        state.get("case_key") not in CASES
        or state.get("cell_count") != len(cells)
        or not 10 <= len(cells) <= 20
        or state.get("fixed_call_count") is not None
        or state.get("planner_state_digest")
        != canonical_digest(
            {key: value for key, value in state.items() if key != "planner_state_digest"}
        )
    ):
        raise S3DynamicResearchSuccessorError("s3_successor_planner_shape_invalid")
    ids = [str(row.get("cell_id") or "") for row in cells]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise S3DynamicResearchSuccessorError("s3_successor_planner_cell_identity_invalid")
    for cell in cells:
        if (
            not cell.get("business_decision_role")
            or not cell.get("why_material")
            or not cell.get("owner_role")
            or not cell.get("stop_condition")
            or not cell.get("downstream_decision")
            or set(cell.get("dependency_cell_ids") or ()) - set(ids)
        ):
            raise S3DynamicResearchSuccessorError("s3_successor_planner_cell_incomplete")


def _reseal_request(request: dict[str, Any]) -> None:
    request["repair_request_digest"] = canonical_digest(
        {key: value for key, value in request.items() if key != "repair_request_digest"}
    )


def _reseal_planner_state(state: dict[str, Any]) -> None:
    state["planner_state_digest"] = canonical_digest(
        {key: value for key, value in state.items() if key != "planner_state_digest"}
    )


def _business_role(cell: Mapping[str, Any]) -> str:
    families = set(cell.get("family_ids") or ())
    if any("counterthesis" in value for value in families):
        return "test_thesis_break_and_monitor_change"
    if any("revenue_margin_cash" in value or "value_capture" in value for value in families):
        return "trace_revenue_to_profit_and_cash"
    if any("capacity" in value or "supply" in value for value in families):
        return "test_supply_constraint_and_rent_capture"
    return "test_demand_quality_and_company_specific_exposure"


def _why_material(cell: Mapping[str, Any]) -> str:
    return (
        f"{cell['decision_question']} This Cell is material because its answer can alter "
        f"{_downstream_decision(cell)}."
    )


def _downstream_decision(cell: Mapping[str, Any]) -> str:
    role = _business_role(cell)
    return {
        "test_thesis_break_and_monitor_change": "confidence, risk boundary and next review trigger",
        "trace_revenue_to_profit_and_cash": "earnings quality, cash conversion and valuation readiness",
        "test_supply_constraint_and_rent_capture": "delivery timing, margin capture and bottleneck ownership",
        "test_demand_quality_and_company_specific_exposure": "demand durability and company-specific thesis strength",
    }[role]


def _owner_for_card(card: Mapping[str, Any]) -> str:
    return {
        "demand_authenticity_and_sustainability": "industry_analyst",
        "value_and_profit_capture": "financial_analyst",
        "bottleneck_counterevidence_and_what_would_change": "risk_reviewer",
    }[str(card["program_cell_id"])]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _semantic_tokens(text: str) -> list[str]:
    raw = _WORD_RE.findall(text)
    tokens = [value.casefold() for value in raw]
    chinese = "".join(value for value in raw if "\u4e00" <= value <= "\u9fff")
    tokens.extend(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
    return sorted(set(tokens))


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    first, second = set(left), set(right)
    if not first and not second:
        return 1.0
    return len(first & second) / max(len(first | second), 1)


def _digest_like(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _record_digest_ok(record: Mapping[str, Any]) -> bool:
    return record.get("record_digest") == canonical_digest(
        {key: deepcopy(value) for key, value in record.items() if key != "record_digest"}
    )


def _assessment_digest_ok(record: Mapping[str, Any]) -> bool:
    return record.get("assessment_digest") == canonical_digest(
        {key: deepcopy(value) for key, value in record.items() if key != "assessment_digest"}
    )


def _assert_inputs(**inputs: Mapping[str, Any]) -> None:
    policy = inputs["policy"]
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("run_scope") != RUN_SCOPE
    ):
        raise S3DynamicResearchSuccessorError("s3_successor_policy_binding_invalid")
    for key in (
        "surface_decision",
        "claim_decision",
        "synthesis_decision",
        "writer_decision",
        "quality_decision",
    ):
        if not _record_digest_ok(inputs[key]):
            raise S3DynamicResearchSuccessorError(f"s3_successor_upstream_digest_invalid:{key}")
    if not _assessment_digest_ok(inputs["dell_business_assessment"]):
        raise S3DynamicResearchSuccessorError("s3_successor_assessment_digest_invalid")
    expected = {
        "surface_decision": ("S3_01", "engineering_pass"),
        "claim_decision": ("S3_02", "engineering_pass"),
        "synthesis_decision": ("S3_03", "engineering_pass"),
        "writer_decision": ("S3_04", "engineering_pass"),
        "quality_decision": ("S3_05_deterministic_gate", "engineering_pass"),
    }
    for key, (field, value) in expected.items():
        if inputs[key].get("acceptance", {}).get(field) != value:
            raise S3DynamicResearchSuccessorError(f"s3_successor_upstream_status_invalid:{key}")
    assessment = inputs["dell_business_assessment"]
    if (
        assessment.get("case_key") != "DELL"
        or assessment.get("business_artifact_promoted") is not False
        or assessment.get("product_disposition", {}).get("delivery_gate") != "failed_L1"
    ):
        raise S3DynamicResearchSuccessorError("s3_successor_historical_candidate_boundary_invalid")
