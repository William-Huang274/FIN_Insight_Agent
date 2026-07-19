from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.pack_registry import (
    PackResolutionRequest,
    PlanningPackRegistry,
    PlanningPackRegistryError,
    PlanningPackRegistryPolicy,
    PlanningPackVersion,
)


pytestmark = pytest.mark.fast_contract


def _policy() -> PlanningPackRegistryPolicy:
    root = Path(__file__).resolve().parents[2]
    raw = json.loads((root / "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json").read_text(encoding="utf-8"))
    return PlanningPackRegistryPolicy.model_validate(
        {key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}}
    )


def _pack(
    pack_id: str,
    version: int,
    scope_kind: str,
    *,
    sector: str | None = None,
    report_type: str | None = None,
    case_id: str | None = None,
    supersedes: str | None = None,
    fresh_until: datetime | None = None,
    promotion_status: str = "reviewed_runtime_candidate",
) -> PlanningPackVersion:
    payload = {"pack_id": pack_id, "version": version, "scope_kind": scope_kind, "sector": sector, "report_type": report_type, "case_id": case_id}
    return PlanningPackVersion(
        pack_id=pack_id,
        pack_version=version,
        pack_version_id=f"{pack_id}:v{version}",
        scope_kind=scope_kind,
        sector=sector,
        report_type=report_type,
        case_id=case_id,
        promotion_status=promotion_status,
        effective_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
        fresh_until=fresh_until or datetime(2026, 12, 31, tzinfo=timezone.utc),
        source_authority_policy_refs=("official_first",),
        payload_digest=canonical_digest(payload),
        published_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        supersedes_pack_version_id=supersedes,
    )


def test_registry_resolves_all_four_pack_scopes_with_authority_policy_refs() -> None:
    registry = PlanningPackRegistry(_policy())
    registry.publish(_pack("universal", 1, "universal"))
    registry.publish(_pack("sector-ai", 1, "sector", sector="ai_semis"))
    registry.publish(_pack("report-init", 1, "report_type", report_type="initiation"))
    registry.publish(_pack("case-ai", 1, "case_delta", case_id="case-ai", promotion_status="provisional_case_delta"))
    result = registry.resolve(
        PackResolutionRequest(
            as_of=datetime(2026, 7, 12, tzinfo=timezone.utc),
            sector="ai_semis",
            report_type="initiation",
            case_id="case-ai",
            require_sector_pack=True,
            require_report_type_pack=True,
            require_case_delta_pack=True,
        )
    )
    assert result.universal_pack_refs == ("universal:v1",)
    assert result.sector_pack_refs == ("sector-ai:v1",)
    assert result.report_type_pack_refs == ("report-init:v1",)
    assert result.case_delta_pack_refs == ("case-ai:v1",)
    assert result.resolved_source_authority_policy_refs == ("official_first",)


def test_registry_rejects_superseded_stale_and_document_only_versions() -> None:
    registry = PlanningPackRegistry(_policy())
    registry.publish(_pack("sector-ai", 1, "sector", sector="ai_semis"))
    registry.publish(_pack("sector-ai", 2, "sector", sector="ai_semis", supersedes="sector-ai:v1"))
    with pytest.raises(PlanningPackRegistryError, match="superseded_pack_version"):
        registry.read_exact("sector-ai:v1", as_of=datetime(2026, 7, 12, tzinfo=timezone.utc))
    assert registry.read_exact("sector-ai:v2", as_of=datetime(2026, 7, 12, tzinfo=timezone.utc)).pack_version == 2
    registry.publish(_pack("stale", 1, "sector", sector="stale", fresh_until=datetime(2026, 7, 2, tzinfo=timezone.utc)))
    with pytest.raises(PlanningPackRegistryError, match="pack_not_fresh:stale"):
        registry.read_exact("stale:v1", as_of=datetime(2026, 7, 12, tzinfo=timezone.utc))
    with pytest.raises(PlanningPackRegistryError, match="pack_promotion_status_not_allowed"):
        registry.publish(_pack("document-only", 1, "universal", promotion_status="document_only"))


def test_registry_snapshot_replays_immutable_version_history() -> None:
    registry = PlanningPackRegistry(_policy())
    registry.publish(_pack("universal", 1, "universal"))
    registry.publish(_pack("sector-saas", 1, "sector", sector="saas"))
    registry.publish(_pack("sector-saas", 2, "sector", sector="saas", supersedes="sector-saas:v1"))
    snapshot = registry.snapshot()
    replay = PlanningPackRegistry.from_snapshot(snapshot)
    assert replay.snapshot() == snapshot
    resolution = replay.resolve(PackResolutionRequest(as_of=datetime(2026, 7, 12, tzinfo=timezone.utc), sector="saas", require_sector_pack=True))
    assert resolution.sector_pack_refs == ("sector-saas:v2",)


def test_m2_3_machine_fixture_covers_four_sectors_and_is_model_free(tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "m2_3_registry_fixture.json"
    completed = subprocess.run(
        [sys.executable, str(root / "scripts/engineering/run_point01_m2_3_pack_registry_fixture.py"), "--output", str(output)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["four_sector_coverage"] is True
    assert result["authority_boundary"]["model_call_count"] == 0
