from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from pydantic import Field

from .models import StrictModel, canonical_digest


CASE_DELTA_NO_OVERRIDE_PAYLOAD_SCHEMA = "finsight_point01_case_delta_no_override_payload_v1_0"
_CASE_DELTA_PAYLOAD_KEYS = frozenset(
    {
        "schema_version",
        "case_id",
        "pack_version_id",
        "freshness",
        "promotion_status",
        "source_authority_policy_refs",
        "base_pack_refs",
        "decision_source_ref",
        "override_mode",
        "additions",
        "removals",
        "overrides",
        "payload_digest",
    }
)
_CASE_DELTA_BASE_REF_KEYS = frozenset({"universal_pack_refs", "sector_pack_refs", "report_type_pack_refs"})


class PlanningPackRegistryError(ValueError):
    """Typed fail-closed error for M2.3 planning-pack lifecycle and resolution."""


class PlanningPackRegistryPolicy(StrictModel):
    policy_ref: str
    allowed_scope_kinds: tuple[str, ...]
    allowed_promotion_statuses: tuple[str, ...]
    require_fresh_until: bool = True


class PlanningPackVersion(StrictModel):
    pack_id: str
    pack_version: int = Field(ge=1)
    pack_version_id: str
    scope_kind: str
    sector: str | None = None
    report_type: str | None = None
    case_id: str | None = None
    promotion_status: str
    effective_from: datetime
    fresh_until: datetime | None = None
    source_authority_policy_refs: tuple[str, ...]
    payload_digest: str
    case_delta_payload: Mapping[str, Any] | None = None
    published_at: datetime
    supersedes_pack_version_id: str | None = None


class PackFreshnessReport(StrictModel):
    pack_version_id: str
    status: str
    as_of: datetime
    effective_from: datetime
    fresh_until: datetime | None = None


class PackLifecycleEvent(StrictModel):
    sequence: int = Field(ge=1)
    event_type: str
    pack_version_id: str
    superseded_pack_version_id: str | None = None
    recorded_at: datetime


class PackResolutionRequest(StrictModel):
    as_of: datetime
    sector: str | None = None
    report_type: str | None = None
    case_id: str | None = None
    require_universal_pack: bool = True
    require_sector_pack: bool = False
    require_report_type_pack: bool = False
    require_case_delta_pack: bool = False


class PackResolution(StrictModel):
    as_of: datetime
    universal_pack_refs: tuple[str, ...] = ()
    sector_pack_refs: tuple[str, ...] = ()
    report_type_pack_refs: tuple[str, ...] = ()
    case_delta_pack_refs: tuple[str, ...] = ()
    resolved_source_authority_policy_refs: tuple[str, ...] = ()
    resolution_digest: str


def validate_case_delta_payload(
    pack: PlanningPackVersion,
    *,
    expected_case_id: str | None = None,
    expected_base_pack_refs: Mapping[str, tuple[str, ...]] | None = None,
) -> None:
    """Validate a real case-instance ``no_override`` payload on a pack version.

    This is deliberately a payload contract on ``PlanningPackVersion`` rather
    than a parallel CaseInstancePack model.  A case delta that changes no
    cells is still a versioned decision: it records the case, exact inherited
    base packs, decision source and an immutable digest.
    """

    if pack.scope_kind != "case_delta":
        raise PlanningPackRegistryError("case_delta_payload_scope_invalid")
    raw = pack.case_delta_payload
    if not isinstance(raw, Mapping):
        raise PlanningPackRegistryError("case_delta_payload_missing")
    payload = dict(raw)
    if set(payload) != _CASE_DELTA_PAYLOAD_KEYS:
        raise PlanningPackRegistryError("case_delta_payload_shape_invalid")
    if payload.get("schema_version") != CASE_DELTA_NO_OVERRIDE_PAYLOAD_SCHEMA:
        raise PlanningPackRegistryError("case_delta_payload_schema_invalid")
    if payload.get("case_id") != pack.case_id or (expected_case_id is not None and payload.get("case_id") != expected_case_id):
        raise PlanningPackRegistryError("case_delta_payload_case_id_mismatch")
    if payload.get("pack_version_id") != pack.pack_version_id:
        raise PlanningPackRegistryError("case_delta_payload_pack_version_mismatch")
    freshness = payload.get("freshness")
    if not isinstance(freshness, Mapping):
        raise PlanningPackRegistryError("case_delta_payload_freshness_missing")
    expected_freshness = {
        "effective_from": pack.effective_from.isoformat().replace("+00:00", "Z"),
        "fresh_until": pack.fresh_until.isoformat().replace("+00:00", "Z") if pack.fresh_until is not None else None,
    }
    if dict(freshness) != expected_freshness:
        raise PlanningPackRegistryError("case_delta_payload_freshness_mismatch")
    if payload.get("promotion_status") != pack.promotion_status:
        raise PlanningPackRegistryError("case_delta_payload_promotion_status_mismatch")
    if tuple(payload.get("source_authority_policy_refs") or ()) != pack.source_authority_policy_refs:
        raise PlanningPackRegistryError("case_delta_payload_source_policy_mismatch")
    base_refs = payload.get("base_pack_refs")
    if not isinstance(base_refs, Mapping) or set(base_refs) != _CASE_DELTA_BASE_REF_KEYS:
        raise PlanningPackRegistryError("case_delta_payload_base_pack_refs_invalid")
    normalized_base_refs: dict[str, tuple[str, ...]] = {}
    for key in sorted(_CASE_DELTA_BASE_REF_KEYS):
        refs = base_refs.get(key)
        if not isinstance(refs, (list, tuple)) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
            raise PlanningPackRegistryError("case_delta_payload_base_pack_refs_invalid")
        normalized_base_refs[key] = tuple(refs)
    if expected_base_pack_refs is not None and normalized_base_refs != dict(expected_base_pack_refs):
        raise PlanningPackRegistryError("case_delta_payload_base_pack_refs_mismatch")
    decision_source_ref = payload.get("decision_source_ref")
    if not isinstance(decision_source_ref, str) or not decision_source_ref.strip():
        raise PlanningPackRegistryError("case_delta_payload_decision_source_missing")
    if payload.get("override_mode") != "no_override":
        raise PlanningPackRegistryError("case_delta_payload_override_mode_invalid")
    if any(payload.get(key) != [] for key in ("additions", "removals", "overrides")):
        raise PlanningPackRegistryError("case_delta_payload_no_override_not_empty")
    claimed_digest = payload.get("payload_digest")
    if not isinstance(claimed_digest, str) or claimed_digest != canonical_digest({key: value for key, value in payload.items() if key != "payload_digest"}):
        raise PlanningPackRegistryError("case_delta_payload_digest_mismatch")
    if pack.payload_digest != claimed_digest:
        raise PlanningPackRegistryError("case_delta_pack_payload_digest_mismatch")


class PlanningPackRegistry:
    """In-memory, immutable-version registry with deterministic snapshot/replay semantics.

    It is a shadow planning registry: it never writes legacy TaskRun or promotes document-only
    material to runtime authority. Persistence and production tenancy are deliberately later milestones.
    """

    def __init__(self, policy: PlanningPackRegistryPolicy):
        self.policy = policy
        self._versions: dict[str, PlanningPackVersion] = {}
        self._superseded_by: dict[str, str] = {}
        self._events: list[PackLifecycleEvent] = []

    def publish(self, pack: PlanningPackVersion) -> tuple[PackLifecycleEvent, ...]:
        self._validate_pack(pack)
        if pack.pack_version_id in self._versions:
            raise PlanningPackRegistryError("pack_version_already_exists")
        active_same_pack = [
            version_id
            for version_id, version in self._versions.items()
            if version.pack_id == pack.pack_id and version_id not in self._superseded_by
        ]
        superseded_id = pack.supersedes_pack_version_id
        if superseded_id:
            predecessor = self._versions.get(superseded_id)
            if predecessor is None:
                raise PlanningPackRegistryError("supersedes_pack_version_not_found")
            if predecessor.pack_id != pack.pack_id:
                raise PlanningPackRegistryError("supersedes_pack_id_mismatch")
            if superseded_id in self._superseded_by:
                raise PlanningPackRegistryError("supersedes_pack_version_not_current")
            if pack.pack_version <= predecessor.pack_version:
                raise PlanningPackRegistryError("superseding_version_must_increase")
            if set(active_same_pack) != {superseded_id}:
                raise PlanningPackRegistryError("active_pack_version_conflict")
        elif active_same_pack:
            raise PlanningPackRegistryError("active_pack_version_already_exists")

        self._versions[pack.pack_version_id] = pack
        events = [self._append_event("published", pack.pack_version_id, pack.published_at)]
        if superseded_id:
            self._superseded_by[superseded_id] = pack.pack_version_id
            events.append(self._append_event("superseded", pack.pack_version_id, pack.published_at, superseded_id))
        return tuple(events)

    def read_exact(self, pack_version_id: str, *, as_of: datetime, include_superseded_history: bool = False) -> PlanningPackVersion:
        pack = self._versions.get(pack_version_id)
        if pack is None:
            raise PlanningPackRegistryError("pack_version_not_found")
        if not include_superseded_history and pack_version_id in self._superseded_by:
            raise PlanningPackRegistryError("superseded_pack_version")
        freshness = self.get_freshness_report(pack_version_id, as_of=as_of)
        if freshness.status != "fresh":
            raise PlanningPackRegistryError(f"pack_not_fresh:{freshness.status}")
        return pack

    def get_freshness_report(self, pack_version_id: str, *, as_of: datetime) -> PackFreshnessReport:
        pack = self._versions.get(pack_version_id)
        if pack is None:
            raise PlanningPackRegistryError("pack_version_not_found")
        if as_of < pack.effective_from:
            status = "not_yet_effective"
        elif pack.fresh_until is not None and as_of > pack.fresh_until:
            status = "stale"
        else:
            status = "fresh"
        return PackFreshnessReport(
            pack_version_id=pack_version_id,
            status=status,
            as_of=as_of,
            effective_from=pack.effective_from,
            fresh_until=pack.fresh_until,
        )

    def resolve(self, request: PackResolutionRequest) -> PackResolution:
        universal = self._resolve_scope("universal", request, required=request.require_universal_pack)
        sector = self._resolve_scope("sector", request, required=request.require_sector_pack)
        report_type = self._resolve_scope("report_type", request, required=request.require_report_type_pack)
        case_delta = self._resolve_scope("case_delta", request, required=request.require_case_delta_pack)
        selected = universal + sector + report_type + case_delta
        refs = tuple(sorted({policy_ref for pack in selected for policy_ref in pack.source_authority_policy_refs}))
        digest = canonical_digest(
            {
                "request": request.model_dump(mode="json"),
                "selected_pack_version_ids": [pack.pack_version_id for pack in selected],
                "source_authority_policy_refs": refs,
            }
        )
        return PackResolution(
            as_of=request.as_of,
            universal_pack_refs=tuple(pack.pack_version_id for pack in universal),
            sector_pack_refs=tuple(pack.pack_version_id for pack in sector),
            report_type_pack_refs=tuple(pack.pack_version_id for pack in report_type),
            case_delta_pack_refs=tuple(pack.pack_version_id for pack in case_delta),
            resolved_source_authority_policy_refs=refs,
            resolution_digest=digest,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "policy": self.policy.model_dump(mode="json"),
            "versions": [self._versions[key].model_dump(mode="json") for key in sorted(self._versions)],
            "superseded_by": dict(sorted(self._superseded_by.items())),
            "events": [event.model_dump(mode="json") for event in self._events],
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "PlanningPackRegistry":
        registry = cls(PlanningPackRegistryPolicy.model_validate(snapshot["policy"]))
        versions = {
            row.pack_version_id: row
            for row in (PlanningPackVersion.model_validate(value) for value in snapshot.get("versions", ()))
        }
        published_order = [
            str(event["pack_version_id"])
            for event in snapshot.get("events", ())
            if isinstance(event, Mapping) and event.get("event_type") == "published"
        ]
        if set(published_order) != set(versions) or len(published_order) != len(versions):
            raise PlanningPackRegistryError("snapshot_publish_history_invalid")
        for pack_version_id in published_order:
            registry.publish(versions[pack_version_id])
        if registry.snapshot()["superseded_by"] != dict(sorted(dict(snapshot.get("superseded_by") or {}).items())):
            raise PlanningPackRegistryError("snapshot_supersession_mismatch")
        return registry

    @property
    def lifecycle_events(self) -> tuple[PackLifecycleEvent, ...]:
        return tuple(self._events)

    def _resolve_scope(self, scope_kind: str, request: PackResolutionRequest, *, required: bool) -> tuple[PlanningPackVersion, ...]:
        matches = []
        for pack in self._versions.values():
            if pack.scope_kind != scope_kind or pack.pack_version_id in self._superseded_by:
                continue
            if scope_kind == "sector" and pack.sector != request.sector:
                continue
            if scope_kind == "report_type" and pack.report_type != request.report_type:
                continue
            if scope_kind == "case_delta" and pack.case_id != request.case_id:
                continue
            if self.get_freshness_report(pack.pack_version_id, as_of=request.as_of).status != "fresh":
                continue
            matches.append(pack)
        if required and not matches:
            raise PlanningPackRegistryError(f"required_pack_scope_missing:{scope_kind}")
        return tuple(sorted(matches, key=lambda pack: (pack.pack_id, pack.pack_version)))

    def _validate_pack(self, pack: PlanningPackVersion) -> None:
        if pack.scope_kind not in self.policy.allowed_scope_kinds:
            raise PlanningPackRegistryError("pack_scope_kind_not_allowed")
        if pack.promotion_status not in self.policy.allowed_promotion_statuses:
            raise PlanningPackRegistryError("pack_promotion_status_not_allowed")
        if pack.pack_version_id != f"{pack.pack_id}:v{pack.pack_version}":
            raise PlanningPackRegistryError("pack_version_id_invalid")
        if self.policy.require_fresh_until and pack.fresh_until is None:
            raise PlanningPackRegistryError("pack_fresh_until_required")
        if pack.fresh_until is not None and pack.fresh_until <= pack.effective_from:
            raise PlanningPackRegistryError("pack_freshness_window_invalid")
        if not pack.source_authority_policy_refs:
            raise PlanningPackRegistryError("pack_source_authority_policy_required")
        if pack.scope_kind == "universal" and any((pack.sector, pack.report_type, pack.case_id)):
            raise PlanningPackRegistryError("universal_pack_scope_invalid")
        if pack.scope_kind == "sector" and (not pack.sector or pack.report_type or pack.case_id):
            raise PlanningPackRegistryError("sector_pack_scope_invalid")
        if pack.scope_kind == "report_type" and (not pack.report_type or pack.sector or pack.case_id):
            raise PlanningPackRegistryError("report_type_pack_scope_invalid")
        if pack.scope_kind == "case_delta" and not pack.case_id:
            raise PlanningPackRegistryError("case_delta_pack_scope_invalid")
        if pack.scope_kind == "case_delta" and pack.case_delta_payload is not None:
            validate_case_delta_payload(pack)

    def _append_event(
        self,
        event_type: str,
        pack_version_id: str,
        recorded_at: datetime,
        superseded_pack_version_id: str | None = None,
    ) -> PackLifecycleEvent:
        event = PackLifecycleEvent(
            sequence=len(self._events) + 1,
            event_type=event_type,
            pack_version_id=pack_version_id,
            superseded_pack_version_id=superseded_pack_version_id,
            recorded_at=recorded_at,
        )
        self._events.append(event)
        return event
