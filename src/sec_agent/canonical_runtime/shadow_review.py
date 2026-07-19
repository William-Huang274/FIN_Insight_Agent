"""Read-model and append-only action contracts for M3 shadow comparison review."""

from __future__ import annotations

from typing import Literal

from .models import StrictModel, canonical_digest
from .shadow_calibration import CandidateAdjudicationReport
from .shadow_comparison import CellCoverageAuditReport, LegacyRequiredItemComparisonReport, ShadowCell, ShadowComparisonError


class ReviewTraceRow(StrictModel):
    trace_id: str
    query_ref: str
    contract_version_id: str
    cell_key: str
    evidence_roles: tuple[str, ...]
    source_policy_refs: tuple[str, ...]
    mapping_status: str
    audit_status: str


class ReviewerAction(StrictModel):
    action_id: str
    action: Literal["accept", "reject", "needs_source", "needs_parser", "supersede"]
    actor_type: Literal["fixture_reviewer", "human"]
    reason: str
    affected_cell_keys: tuple[str, ...]
    supersedes_action_id: str | None = None


class ShadowReviewSurface(StrictModel):
    case_id: str
    contract_version_id: str
    status: Literal["pass", "fail"]
    traces: tuple[ReviewTraceRow, ...]
    actions: tuple[ReviewerAction, ...]
    unresolved_action_ids: tuple[str, ...]
    surface_digest: str
    planning_authority: str = "legacy"
    canonical_lane: str = "shadow_only"
    model_call_count: int = 0
    external_call_count: int = 0


class ShadowComparisonReviewService:
    """Build reviewer traces without granting a reviewer authority to cut over a lane."""

    def build_surface(
        self,
        *,
        case_id: str,
        query_ref: str,
        contract_version_id: str,
        cells: tuple[ShadowCell, ...],
        comparison: LegacyRequiredItemComparisonReport,
        audit: CellCoverageAuditReport,
        adjudication: CandidateAdjudicationReport,
        actions: tuple[ReviewerAction, ...],
    ) -> ShadowReviewSurface:
        if not all((case_id.strip(), query_ref.strip(), contract_version_id.strip())):
            raise ShadowComparisonError("review_surface_required_scope_missing")
        if comparison.case_id != case_id or audit.case_id != case_id:
            raise ShadowComparisonError("review_surface_case_scope_mismatch")
        cell_by_key = {cell.cell_key: cell for cell in cells}
        if len(cell_by_key) != len(cells):
            raise ShadowComparisonError("review_surface_duplicate_cell_keys")
        comparisons = {row.legacy_required_item_id: row.status for row in comparison.rows}
        traces = tuple(
            ReviewTraceRow(
                trace_id=f"trace_{canonical_digest((case_id, contract_version_id, cell.cell_key))[:20]}",
                query_ref=query_ref,
                contract_version_id=contract_version_id,
                cell_key=cell.cell_key,
                evidence_roles=cell.evidence_roles,
                source_policy_refs=cell.source_policy_refs,
                mapping_status="covered" if cell.cell_key not in comparison.extra_shadow_cell_keys else "canonical_only_cell",
                audit_status=audit.status,
            )
            for cell in sorted(cells, key=lambda row: row.cell_key)
        )
        action_ids = {action.action_id for action in actions}
        if len(action_ids) != len(actions):
            raise ShadowComparisonError("review_action_ids_must_be_unique")
        unresolved: list[str] = []
        errors: list[str] = []
        seen_action_ids: set[str] = set()
        for action in actions:
            if not action.reason.strip() or not action.affected_cell_keys or set(action.affected_cell_keys) - set(cell_by_key):
                errors.append(f"invalid_action:{action.action_id}")
            if action.action == "supersede":
                if not action.supersedes_action_id or action.supersedes_action_id not in seen_action_ids:
                    errors.append(f"invalid_supersession:{action.action_id}")
            elif action.supersedes_action_id:
                errors.append(f"unexpected_supersession:{action.action_id}")
            if action.action in {"reject", "needs_source", "needs_parser"}:
                unresolved.append(action.action_id)
            if action.action == "supersede" and action.supersedes_action_id in unresolved:
                unresolved.remove(action.supersedes_action_id)
            seen_action_ids.add(action.action_id)
        if comparison.status != "pass":
            errors.append("legacy_semantic_comparison_failed")
        if audit.status != "pass":
            errors.append("cell_audit_failed")
        if adjudication.status != "pass":
            errors.append("candidate_adjudication_failed")
        digest = canonical_digest(
            {
                "case_id": case_id,
                "query_ref": query_ref,
                "contract_version_id": contract_version_id,
                "trace_ids": [trace.trace_id for trace in traces],
                "actions": [action.model_dump(mode="json") for action in actions],
                "comparison_digest": comparison.mapping_digest,
                "audit_digest": audit.audit_digest,
                "adjudication_digest": adjudication.adjudication_digest,
            }
        )
        return ShadowReviewSurface(
            case_id=case_id,
            contract_version_id=contract_version_id,
            status="pass" if not errors else "fail",
            traces=traces,
            actions=actions,
            unresolved_action_ids=tuple(sorted(unresolved)),
            surface_digest=digest,
        )
