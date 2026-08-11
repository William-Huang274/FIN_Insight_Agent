from __future__ import annotations

from datetime import datetime
from typing import Mapping

from .models import StrictModel, canonical_digest
from .pack_registry import PackResolution, PackResolutionRequest, PlanningPackRegistry, PlanningPackRegistryError


class PackSelectionPolicy(StrictModel):
    policy_ref: str
    sector_keywords: dict[str, tuple[str, ...]]
    report_type_keywords: dict[str, tuple[str, ...]]


class PackSelectionIntent(StrictModel):
    query: str
    sector: str | None = None
    report_type: str | None = None
    case_id: str | None = None
    as_of: datetime


class PackSelectionReason(StrictModel):
    code: str
    detail: str


class ExplainedPackSelectionDecision(StrictModel):
    status: str
    selected_sector: str | None = None
    selected_report_type: str | None = None
    resolution: PackResolution | None = None
    reasons: tuple[PackSelectionReason, ...] = ()
    rejections: tuple[PackSelectionReason, ...] = ()
    conflicts: tuple[PackSelectionReason, ...] = ()
    decision_digest: str
    planning_authority: str = "shadow"
    model_call_count: int = 0


class PackSelectionEngine:
    """M2.4 deterministic selection only; a selected pack remains shadow planning input."""

    def __init__(self, registry: PlanningPackRegistry, policy: PackSelectionPolicy):
        self.registry = registry
        self.policy = policy

    def select(self, intent: PackSelectionIntent) -> ExplainedPackSelectionDecision:
        query = intent.query.strip().lower()
        if not query:
            return self._decision(intent, status="rejected", rejections=(PackSelectionReason(code="query_blank", detail="query is required"),))
        sector, sector_conflicts, sector_rejections, sector_reasons = self._resolve_intent_value(
            explicit=intent.sector,
            keyword_map=self.policy.sector_keywords,
            query=query,
            dimension="sector",
        )
        report_type, report_conflicts, report_rejections, report_reasons = self._resolve_intent_value(
            explicit=intent.report_type,
            keyword_map=self.policy.report_type_keywords,
            query=query,
            dimension="report_type",
        )
        conflicts = sector_conflicts + report_conflicts
        rejections = sector_rejections + report_rejections
        reasons = sector_reasons + report_reasons
        if conflicts:
            return self._decision(intent, status="conflict", reasons=reasons, conflicts=conflicts)
        if rejections:
            return self._decision(intent, status="rejected", reasons=reasons, rejections=rejections)
        assert sector is not None and report_type is not None
        try:
            resolution = self.registry.resolve(
                PackResolutionRequest(
                    as_of=intent.as_of,
                    sector=sector,
                    report_type=report_type,
                    case_id=intent.case_id,
                    require_sector_pack=True,
                    require_report_type_pack=True,
                    require_case_delta_pack=bool(intent.case_id),
                )
            )
        except PlanningPackRegistryError as exc:
            return self._decision(
                intent,
                status="rejected",
                selected_sector=sector,
                selected_report_type=report_type,
                reasons=reasons,
                rejections=(PackSelectionReason(code="registry_resolution_failed", detail=str(exc)),),
            )
        return self._decision(
            intent,
            status="selected",
            selected_sector=sector,
            selected_report_type=report_type,
            resolution=resolution,
            reasons=reasons + (PackSelectionReason(code="versioned_pack_resolution_selected", detail=resolution.resolution_digest),),
        )

    def _resolve_intent_value(
        self,
        *,
        explicit: str | None,
        keyword_map: Mapping[str, tuple[str, ...]],
        query: str,
        dimension: str,
    ) -> tuple[str | None, tuple[PackSelectionReason, ...], tuple[PackSelectionReason, ...], tuple[PackSelectionReason, ...]]:
        explicit_value = explicit.strip() if explicit else None
        matches = tuple(sorted(key for key, keywords in keyword_map.items() if any(keyword.lower() in query for keyword in keywords)))
        if explicit_value and explicit_value not in keyword_map:
            return None, (), (PackSelectionReason(code=f"{dimension}_not_allowed", detail=explicit_value),), ()
        if len(matches) > 1:
            return None, (PackSelectionReason(code=f"query_{dimension}_ambiguous", detail=",".join(matches)),), (), ()
        inferred = matches[0] if matches else None
        if explicit_value and inferred and explicit_value != inferred:
            return None, (PackSelectionReason(code=f"explicit_{dimension}_conflicts_query", detail=f"{explicit_value}!={inferred}"),), (), ()
        value = explicit_value or inferred
        if not value:
            return None, (), (PackSelectionReason(code=f"{dimension}_intent_missing", detail="no explicit or query-derived intent"),), ()
        reason_code = f"explicit_{dimension}" if explicit_value else f"query_derived_{dimension}"
        return value, (), (), (PackSelectionReason(code=reason_code, detail=value),)

    @staticmethod
    def _decision(
        intent: PackSelectionIntent,
        *,
        status: str,
        selected_sector: str | None = None,
        selected_report_type: str | None = None,
        resolution: PackResolution | None = None,
        reasons: tuple[PackSelectionReason, ...] = (),
        rejections: tuple[PackSelectionReason, ...] = (),
        conflicts: tuple[PackSelectionReason, ...] = (),
    ) -> ExplainedPackSelectionDecision:
        digest = canonical_digest(
            {
                "intent": intent.model_dump(mode="json"),
                "status": status,
                "selected_sector": selected_sector,
                "selected_report_type": selected_report_type,
                "resolution": resolution.model_dump(mode="json") if resolution else None,
                "reasons": [reason.model_dump(mode="json") for reason in reasons],
                "rejections": [reason.model_dump(mode="json") for reason in rejections],
                "conflicts": [reason.model_dump(mode="json") for reason in conflicts],
            }
        )
        return ExplainedPackSelectionDecision(
            status=status,
            selected_sector=selected_sector,
            selected_report_type=selected_report_type,
            resolution=resolution,
            reasons=reasons,
            rejections=rejections,
            conflicts=conflicts,
            decision_digest=digest,
        )
