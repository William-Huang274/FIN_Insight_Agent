from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .models import StrictModel, canonical_digest
from .planning_service import CompilerInputContract, DecisionCellSeed, EvidenceSlotSeed, PackSelectionDecision


class LegacyObjectiveAdapterError(ValueError):
    pass


_DEFAULT_FORBIDDEN_SUBSTITUTIONS_BY_EVIDENCE_ROLE: dict[str, tuple[str, ...]] = {
    "issuer_metric": ("relationship_graph_only",),
    "relationship_signal": ("issuer_metric_substitute",),
    "commercial_tracker_metric": ("public_proxy_as_exact",),
}


def _forbidden_substitutions_for_required_item(item: Mapping[str, Any], *, evidence_role: str) -> tuple[str, ...]:
    """Resolve the minimum explicit substitution boundary for an adapted slot.

    Legacy objectives predate the compiler's required substitution contract.
    An explicit legacy value remains authoritative; otherwise only the three
    canonical evidence-role defaults may be supplied.  Unknown roles stop
    rather than silently creating an unbounded evidence slot.
    """

    if "forbidden_substitutions" in item:
        value = item["forbidden_substitutions"]
        if not isinstance(value, (list, tuple)) or not value or any(not str(entry).strip() for entry in value):
            raise LegacyObjectiveAdapterError("legacy_required_item_forbidden_substitutions_invalid")
        return tuple(str(entry) for entry in value)
    resolved = _DEFAULT_FORBIDDEN_SUBSTITUTIONS_BY_EVIDENCE_ROLE.get(evidence_role)
    if not resolved:
        raise LegacyObjectiveAdapterError("legacy_required_item_forbidden_substitutions_unresolved")
    return resolved


class LegacySemanticMappingPolicy(StrictModel):
    policy_ref: str
    allowed_actions: tuple[str, ...] = ("merge", "split", "downgrade")
    require_information_loss_tags: bool = True


class LegacySemanticMapping(StrictModel):
    legacy_required_item_id: str
    action: str
    target_cell_keys: tuple[str, ...] = ()
    information_loss_tags: tuple[str, ...] = ()
    downgrade_reason: str | None = None


class LegacyInformationLossEntry(StrictModel):
    legacy_required_item_id: str
    action: str
    target_cell_keys: tuple[str, ...]
    information_loss_tags: tuple[str, ...]
    downgrade_reason: str | None = None


class LegacyMigrationPlan(StrictModel):
    policy_ref: str
    legacy_input_digest: str
    legacy_required_item_ids: tuple[str, ...]
    mappings: tuple[LegacySemanticMapping, ...]
    information_loss_review: tuple[LegacyInformationLossEntry, ...]
    legacy_identity_preserved: bool = True
    one_to_one_equivalence_count: int = 0
    planning_authority: str = "legacy"
    model_call_count: int = 0
    external_call_count: int = 0


def adapt_legacy_research_objective(
    legacy_payload: Mapping[str, Any],
    *,
    tenant_id: str,
    project_id: str,
    case_id: str,
    compiler_policy_ref: str,
) -> CompilerInputContract:
    """Pure adapter: normalize a frozen legacy objective without reading or mutating legacy state."""
    query = str(legacy_payload.get("query") or legacy_payload.get("user_query") or "").strip()
    as_of = legacy_payload.get("as_of")
    universe = tuple(str(value) for value in legacy_payload.get("universe") or legacy_payload.get("tickers") or ())
    required_items = tuple(legacy_payload.get("required_items") or ())
    if not query or not as_of or not universe or not required_items:
        raise LegacyObjectiveAdapterError("legacy_objective_missing_required_fields")
    if not isinstance(as_of, datetime):
        as_of = datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        raise LegacyObjectiveAdapterError("legacy_objective_as_of_must_be_timezone_aware")
    cells = []
    for index, item in enumerate(required_items, 1):
        if not isinstance(item, Mapping):
            raise LegacyObjectiveAdapterError("legacy_required_item_must_be_mapping")
        question = str(item.get("question") or item.get("must_answer") or "").strip()
        if not question:
            raise LegacyObjectiveAdapterError("legacy_required_item_question_missing")
        role = str(item.get("owner_role") or "research_lead")
        evidence_role = str(item.get("evidence_role") or "required_item_support")
        cells.append(
            DecisionCellSeed(
                cell_key=str(item.get("required_item_id") or f"legacy_item_{index}"),
                decision_question=question,
                origin_type="legacy_adapter",
                owner_role=role,
                materiality=str(item.get("materiality") or "high"),
                stop_rule=str(item.get("stop_rule") or "one accepted evidence route plus typed gap"),
                evidence_slots=(
                    EvidenceSlotSeed(
                        evidence_role=evidence_role,
                        entity_scope=tuple(str(value) for value in item.get("entity_scope") or universe),
                        period_scope=str(item.get("period_scope") or "as_of"),
                        source_policy_ref=str(item.get("source_policy_ref") or "legacy_route_policy"),
                        forbidden_substitutions=_forbidden_substitutions_for_required_item(item, evidence_role=evidence_role),
                        acceptance_role="primary_or_bounded_context",
                        required=True,
                    ),
                ),
            )
        )
    return CompilerInputContract(
        tenant_id=tenant_id,
        project_id=project_id,
        case_id=case_id,
        query=query,
        as_of=as_of,
        universe=universe,
        language=str(legacy_payload.get("language") or "zh-CN"),
        compiler_policy_ref=compiler_policy_ref,
        pack_selection=PackSelectionDecision(),
        required_cells=tuple(cells),
    )


def adapt_legacy_objective_semantically(
    legacy_payload: Mapping[str, Any],
    *,
    target_cells: tuple[DecisionCellSeed, ...],
    mappings: tuple[LegacySemanticMapping, ...],
    policy: LegacySemanticMappingPolicy,
) -> LegacyMigrationPlan:
    """Create an auditable M2.7 migration plan without equating legacy facts to DecisionCells."""
    required_items = tuple(legacy_payload.get("required_items") or ())
    legacy_ids = []
    for item in required_items:
        if not isinstance(item, Mapping):
            raise LegacyObjectiveAdapterError("legacy_required_item_must_be_mapping")
        item_id = str(item.get("required_item_id") or "").strip()
        if not item_id:
            raise LegacyObjectiveAdapterError("legacy_required_item_id_missing")
        legacy_ids.append(item_id)
    if not legacy_ids or len(set(legacy_ids)) != len(legacy_ids):
        raise LegacyObjectiveAdapterError("legacy_required_item_ids_invalid")
    mapping_by_id = {mapping.legacy_required_item_id: mapping for mapping in mappings}
    if set(mapping_by_id) != set(legacy_ids) or len(mapping_by_id) != len(mappings):
        raise LegacyObjectiveAdapterError("legacy_mapping_coverage_invalid")
    target_cell_keys = {cell.cell_key for cell in target_cells}
    merge_targets: dict[str, int] = {}
    loss_review: list[LegacyInformationLossEntry] = []
    for mapping in mappings:
        if mapping.action not in policy.allowed_actions:
            raise LegacyObjectiveAdapterError("legacy_mapping_action_not_allowed")
        if policy.require_information_loss_tags and not mapping.information_loss_tags:
            raise LegacyObjectiveAdapterError("legacy_information_loss_tags_required")
        if mapping.action == "split" and len(mapping.target_cell_keys) < 2:
            raise LegacyObjectiveAdapterError("legacy_split_requires_multiple_target_cells")
        if mapping.action == "merge":
            if len(mapping.target_cell_keys) != 1:
                raise LegacyObjectiveAdapterError("legacy_merge_requires_one_target_cell")
            merge_targets[mapping.target_cell_keys[0]] = merge_targets.get(mapping.target_cell_keys[0], 0) + 1
        if mapping.action == "downgrade":
            if mapping.target_cell_keys or not (mapping.downgrade_reason or "").strip():
                raise LegacyObjectiveAdapterError("legacy_downgrade_requires_reason_without_target_cell")
        if set(mapping.target_cell_keys) - target_cell_keys:
            raise LegacyObjectiveAdapterError("legacy_mapping_target_cell_not_found")
        loss_review.append(
            LegacyInformationLossEntry(
                legacy_required_item_id=mapping.legacy_required_item_id,
                action=mapping.action,
                target_cell_keys=mapping.target_cell_keys,
                information_loss_tags=mapping.information_loss_tags,
                downgrade_reason=mapping.downgrade_reason,
            )
        )
    if any(count < 2 for count in merge_targets.values()):
        raise LegacyObjectiveAdapterError("legacy_merge_requires_multiple_legacy_items")
    digest = canonical_digest(
        {
            "legacy_payload": legacy_payload,
            "target_cell_keys": sorted(target_cell_keys),
            "mappings": [mapping.model_dump(mode="json") for mapping in mappings],
            "policy_ref": policy.policy_ref,
        }
    )
    return LegacyMigrationPlan(
        policy_ref=policy.policy_ref,
        legacy_input_digest=digest,
        legacy_required_item_ids=tuple(legacy_ids),
        mappings=mappings,
        information_loss_review=tuple(loss_review),
    )
