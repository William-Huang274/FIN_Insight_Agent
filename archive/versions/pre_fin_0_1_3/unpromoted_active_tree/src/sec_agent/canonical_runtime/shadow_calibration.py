"""Deterministic M3 calibration, negative-control, and provenance contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import StrictModel, canonical_digest
from .shadow_comparison import CellCoverageAuditReport, ShadowCell, ShadowComparisonError


class FiveChainDefinition(StrictModel):
    chain_id: str
    required_cell_keys: tuple[str, ...]
    required_evidence_roles: tuple[str, ...]


class FiveChainPolicy(StrictModel):
    policy_ref: str
    require_what_would_change: bool = True
    require_counterevidence_owner: bool = True


class FiveChainFinding(StrictModel):
    chain_id: str
    status: Literal["pass", "fail"]
    missing_cell_keys: tuple[str, ...] = ()
    missing_evidence_roles: tuple[str, ...] = ()
    missing_wwc_cell_keys: tuple[str, ...] = ()
    missing_counterevidence_cell_keys: tuple[str, ...] = ()
    failure_attribution: tuple[str, ...] = ()


class FiveChainCalibrationReport(StrictModel):
    case_id: str
    policy_ref: str
    status: Literal["pass", "fail"]
    findings: tuple[FiveChainFinding, ...]
    material_omission_ids: tuple[str, ...] = ()
    evaluation_digest: str
    planning_authority: str = "legacy"
    canonical_lane: str = "shadow_only"
    model_call_count: int = 0
    external_call_count: int = 0


class P36FiveChainEvaluator:
    """Evaluate the frozen P36 five-chain rubric without treating supplements as runtime evidence."""

    def __init__(self, policy: FiveChainPolicy):
        self.policy = policy

    def evaluate(
        self,
        *,
        case_id: str,
        chains: tuple[FiveChainDefinition, ...],
        cells: tuple[ShadowCell, ...],
        audit: CellCoverageAuditReport,
        material_omission_ids: tuple[str, ...] = (),
    ) -> FiveChainCalibrationReport:
        if not case_id.strip() or not chains or audit.case_id != case_id:
            raise ShadowComparisonError("five_chain_required_input_missing_or_case_mismatch")
        cell_by_key = {cell.cell_key: cell for cell in cells}
        if len(cell_by_key) != len(cells):
            raise ShadowComparisonError("five_chain_duplicate_cell_keys")
        findings: list[FiveChainFinding] = []
        for chain in chains:
            chain_cells = [cell_by_key[key] for key in chain.required_cell_keys if key in cell_by_key]
            missing_cells = tuple(sorted(set(chain.required_cell_keys) - set(cell_by_key)))
            present_roles = {role for cell in chain_cells for role in cell.evidence_roles}
            missing_roles = tuple(sorted(set(chain.required_evidence_roles) - present_roles))
            missing_wwc = tuple(sorted(cell.cell_key for cell in chain_cells if not cell.what_would_change)) if self.policy.require_what_would_change else ()
            missing_counter = (
                tuple(sorted(cell.cell_key for cell in chain_cells if not (cell.counterevidence_owner_role or "").strip()))
                if self.policy.require_counterevidence_owner
                else ()
            )
            attribution = []
            if missing_cells:
                attribution.append("cell_coverage")
            if missing_roles:
                attribution.append("evidence_slot_coverage")
            if missing_wwc:
                attribution.append("what_would_change_coverage")
            if missing_counter:
                attribution.append("counterevidence_ownership")
            findings.append(
                FiveChainFinding(
                    chain_id=chain.chain_id,
                    status="pass" if not attribution else "fail",
                    missing_cell_keys=missing_cells,
                    missing_evidence_roles=missing_roles,
                    missing_wwc_cell_keys=missing_wwc,
                    missing_counterevidence_cell_keys=missing_counter,
                    failure_attribution=tuple(attribution),
                )
            )
        passing = audit.status == "pass" and not material_omission_ids and all(row.status == "pass" for row in findings)
        digest = canonical_digest(
            {
                "case_id": case_id,
                "policy": self.policy.model_dump(mode="json"),
                "chains": [chain.model_dump(mode="json") for chain in chains],
                "audit_digest": audit.audit_digest,
                "material_omission_ids": material_omission_ids,
            }
        )
        return FiveChainCalibrationReport(
            case_id=case_id,
            policy_ref=self.policy.policy_ref,
            status="pass" if passing else "fail",
            findings=tuple(findings),
            material_omission_ids=tuple(sorted(material_omission_ids)),
            evaluation_digest=digest,
        )


class SectorCalibrationCase(StrictModel):
    case_id: str
    sector: Literal["ai_semis", "saas", "healthcare", "banks"]
    report_type: Literal["initiation", "event_update", "valuation_price_in"]
    expected_mechanism_keys: tuple[str, ...]
    observed_mechanism_keys: tuple[str, ...]
    ontology_ref: str
    source_policy_delta_refs: tuple[str, ...]
    status: Literal["pass", "fail"]


class MultiSectorCalibrationPolicy(StrictModel):
    policy_ref: str
    required_sectors: tuple[str, ...] = ("ai_semis", "saas", "healthcare", "banks")
    minimum_mechanism_coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    require_source_policy_delta: bool = True


class SectorCalibrationFinding(StrictModel):
    case_id: str
    sector: str
    report_type: str
    status: Literal["pass", "fail"]
    mechanism_coverage: float
    failures: tuple[str, ...] = ()


class MultiSectorCalibrationReport(StrictModel):
    policy_ref: str
    status: Literal["pass", "fail"]
    findings: tuple[SectorCalibrationFinding, ...]
    missing_sectors: tuple[str, ...]
    calibration_digest: str
    planning_authority: str = "legacy"
    canonical_lane: str = "shadow_only"
    model_call_count: int = 0
    external_call_count: int = 0


class MultiSectorCalibrationMatrix:
    def __init__(self, policy: MultiSectorCalibrationPolicy):
        self.policy = policy

    def evaluate(self, *, cases: tuple[SectorCalibrationCase, ...]) -> MultiSectorCalibrationReport:
        if not cases or len({case.case_id for case in cases}) != len(cases):
            raise ShadowComparisonError("multi_sector_cases_missing_or_duplicate")
        findings: list[SectorCalibrationFinding] = []
        for case in cases:
            expected = set(case.expected_mechanism_keys)
            coverage = len(expected & set(case.observed_mechanism_keys)) / len(expected) if expected else 0.0
            failures = []
            if case.status != "pass":
                failures.append("upstream_case_calibration_failed")
            if coverage < self.policy.minimum_mechanism_coverage:
                failures.append("sector_mechanism_coverage_below_threshold")
            if not case.ontology_ref.strip():
                failures.append("sector_ontology_missing")
            if self.policy.require_source_policy_delta and not case.source_policy_delta_refs:
                failures.append("source_policy_delta_missing")
            findings.append(
                SectorCalibrationFinding(
                    case_id=case.case_id,
                    sector=case.sector,
                    report_type=case.report_type,
                    status="pass" if not failures else "fail",
                    mechanism_coverage=coverage,
                    failures=tuple(failures),
                )
            )
        present = {case.sector for case in cases}
        missing_sectors = tuple(sorted(set(self.policy.required_sectors) - present))
        status = "pass" if not missing_sectors and all(row.status == "pass" for row in findings) else "fail"
        return MultiSectorCalibrationReport(
            policy_ref=self.policy.policy_ref,
            status=status,
            findings=tuple(findings),
            missing_sectors=missing_sectors,
            calibration_digest=canonical_digest(
                {"policy": self.policy.model_dump(mode="json"), "cases": [case.model_dump(mode="json") for case in cases]}
            ),
        )


class NegativeControl(StrictModel):
    control_id: str
    family: Literal["relationship", "parser", "commercial"]
    attempted_promotion: str
    typed_gap_type: str
    actual_status: Literal["rejected", "accepted"]
    actual_reason: str


class NegativeControlFinding(StrictModel):
    control_id: str
    status: Literal["pass", "fail"]
    escape_detected: bool
    failures: tuple[str, ...] = ()


class NegativeControlReport(StrictModel):
    status: Literal["pass", "fail"]
    findings: tuple[NegativeControlFinding, ...]
    material_escape_count: int
    control_digest: str
    planning_authority: str = "legacy"
    canonical_lane: str = "shadow_only"
    model_call_count: int = 0
    external_call_count: int = 0


class NegativeControlVerifier:
    expected_gap_types = {
        "relationship": "relationship_scope_only",
        "parser": "parser_gap",
        "commercial": "commercial_data_gap",
    }

    def verify(self, *, controls: tuple[NegativeControl, ...]) -> NegativeControlReport:
        expected_families = set(self.expected_gap_types)
        if {control.family for control in controls} != expected_families or len(controls) != len(expected_families):
            raise ShadowComparisonError("negative_control_families_must_be_exactly_relationship_parser_commercial")
        findings: list[NegativeControlFinding] = []
        for control in controls:
            failures = []
            if control.actual_status != "rejected":
                failures.append("material_escape_detected")
            if control.typed_gap_type != self.expected_gap_types[control.family]:
                failures.append("typed_gap_misclassified")
            if not control.actual_reason.strip():
                failures.append("rejection_reason_missing")
            findings.append(
                NegativeControlFinding(
                    control_id=control.control_id,
                    status="pass" if not failures else "fail",
                    escape_detected="material_escape_detected" in failures,
                    failures=tuple(failures),
                )
            )
        escapes = sum(1 for row in findings if row.escape_detected)
        return NegativeControlReport(
            status="pass" if not escapes and all(row.status == "pass" for row in findings) else "fail",
            findings=tuple(findings),
            material_escape_count=escapes,
            control_digest=canonical_digest([control.model_dump(mode="json") for control in controls]),
        )


ProvenanceKind = Literal["prompt_required", "independently_observed", "reviewer_inferred"]
CandidateDisposition = Literal[
    "universal_candidate",
    "sector_candidate",
    "report_type_candidate",
    "case_only",
    "evidence_slot_candidate",
    "reject",
]


class PatternCandidate(StrictModel):
    candidate_id: str
    source_case_id: str
    source_family: str
    provenance: ProvenanceKind
    proposed_disposition: CandidateDisposition
    candidate_summary: str
    evidence_refs: tuple[str, ...]
    independent_corroboration_refs: tuple[str, ...] = ()
    reviewer_action: Literal["accept", "reject"]


class CandidateAdjudication(StrictModel):
    candidate_id: str
    status: Literal["promotable", "rejected"]
    final_disposition: CandidateDisposition
    reason: str
    promotion_scope: Literal["reviewed_runtime_candidate", "none"]


class CandidateAdjudicationReport(StrictModel):
    status: Literal["pass", "fail"]
    adjudications: tuple[CandidateAdjudication, ...]
    promotable_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...]
    adjudication_digest: str
    direct_workbuddy_pack_promotion_count: int = 0
    planning_authority: str = "legacy"
    canonical_lane: str = "shadow_only"
    model_call_count: int = 0
    external_call_count: int = 0


class PatternCandidateAdjudicator:
    """Apply M3 provenance rules before a candidate can reach the pack registry."""

    def adjudicate(self, *, candidates: tuple[PatternCandidate, ...]) -> CandidateAdjudicationReport:
        if not candidates or len({candidate.candidate_id for candidate in candidates}) != len(candidates):
            raise ShadowComparisonError("pattern_candidates_missing_or_duplicate")
        adjudications: list[CandidateAdjudication] = []
        for candidate in candidates:
            status = "promotable"
            disposition = candidate.proposed_disposition
            scope: Literal["reviewed_runtime_candidate", "none"] = "reviewed_runtime_candidate"
            reason = "reviewer_confirmed_independently_observed_candidate"
            if candidate.provenance == "prompt_required":
                status, disposition, scope, reason = "rejected", "reject", "none", "prompt_required_structure_is_not_independent_discovery"
            elif candidate.provenance == "reviewer_inferred":
                status, disposition, scope, reason = "rejected", "reject", "none", "reviewer_inference_requires_independent_observation"
            elif candidate.source_family == "workbuddy" and not candidate.independent_corroboration_refs:
                status, disposition, scope, reason = "rejected", "reject", "none", "workbuddy_candidate_missing_independent_corroboration"
            elif candidate.reviewer_action != "accept":
                status, disposition, scope, reason = "rejected", "reject", "none", "reviewer_rejected_candidate"
            elif not candidate.evidence_refs or not candidate.candidate_summary.strip():
                status, disposition, scope, reason = "rejected", "reject", "none", "candidate_evidence_or_summary_missing"
            adjudications.append(
                CandidateAdjudication(
                    candidate_id=candidate.candidate_id,
                    status=status,
                    final_disposition=disposition,
                    reason=reason,
                    promotion_scope=scope,
                )
            )
        promoted = tuple(sorted(row.candidate_id for row in adjudications if row.status == "promotable"))
        rejected = tuple(sorted(row.candidate_id for row in adjudications if row.status == "rejected"))
        direct_promotions = sum(
            1
            for candidate, adjudication in zip(candidates, adjudications, strict=True)
            if candidate.source_family == "workbuddy" and adjudication.status == "promotable" and not candidate.independent_corroboration_refs
        )
        return CandidateAdjudicationReport(
            status="pass" if direct_promotions == 0 else "fail",
            adjudications=tuple(adjudications),
            promotable_candidate_ids=promoted,
            rejected_candidate_ids=rejected,
            adjudication_digest=canonical_digest([candidate.model_dump(mode="json") for candidate in candidates]),
            direct_workbuddy_pack_promotion_count=direct_promotions,
        )
