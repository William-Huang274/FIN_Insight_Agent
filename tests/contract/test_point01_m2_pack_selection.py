from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.pack_registry import PlanningPackRegistry, PlanningPackRegistryPolicy, PlanningPackVersion
from sec_agent.canonical_runtime.pack_selection import PackSelectionEngine, PackSelectionIntent, PackSelectionPolicy


pytestmark = pytest.mark.fast_contract


def _registry_policy() -> PlanningPackRegistryPolicy:
    root = Path(__file__).resolve().parents[2]
    raw = json.loads((root / "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json").read_text(encoding="utf-8"))
    return PlanningPackRegistryPolicy.model_validate({key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}})


def _selection_policy() -> PackSelectionPolicy:
    root = Path(__file__).resolve().parents[2]
    raw = json.loads((root / "configs/engineering_handoff/point01_m2_4_pack_selection_policy_v1_0.json").read_text(encoding="utf-8"))
    return PackSelectionPolicy.model_validate({key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}})


def _pack(pack_id: str, scope_kind: str, *, sector: str | None = None, report_type: str | None = None, case_id: str | None = None) -> PlanningPackVersion:
    payload = {"pack_id": pack_id, "scope_kind": scope_kind, "sector": sector, "report_type": report_type, "case_id": case_id}
    return PlanningPackVersion(
        pack_id=pack_id,
        pack_version=1,
        pack_version_id=f"{pack_id}:v1",
        scope_kind=scope_kind,
        sector=sector,
        report_type=report_type,
        case_id=case_id,
        promotion_status="provisional_case_delta" if scope_kind == "case_delta" else "reviewed_runtime_candidate",
        effective_from=datetime(2026, 7, 1, tzinfo=timezone.utc),
        fresh_until=datetime(2026, 12, 31, tzinfo=timezone.utc),
        source_authority_policy_refs=("official_first",),
        payload_digest=canonical_digest(payload),
        published_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def _engine() -> PackSelectionEngine:
    registry = PlanningPackRegistry(_registry_policy())
    registry.publish(_pack("universal", "universal"))
    registry.publish(_pack("sector-ai", "sector", sector="ai_semis"))
    registry.publish(_pack("report-init", "report_type", report_type="initiation"))
    registry.publish(_pack("case-ai", "case_delta", case_id="case-ai"))
    return PackSelectionEngine(registry, _selection_policy())


def test_selection_records_reasoned_versioned_resolution() -> None:
    decision = _engine().select(
        PackSelectionIntent(query="Semiconductor accelerator initiation", sector="ai_semis", report_type="initiation", as_of=datetime(2026, 7, 12, tzinfo=timezone.utc))
    )
    assert decision.status == "selected"
    assert decision.resolution and decision.resolution.sector_pack_refs == ("sector-ai:v1",)
    assert {reason.code for reason in decision.reasons} >= {"explicit_sector", "explicit_report_type", "versioned_pack_resolution_selected"}
    assert decision.model_call_count == 0


def test_selection_infers_intent_and_requires_case_delta_when_case_is_supplied() -> None:
    engine = _engine()
    inferred = engine.select(PackSelectionIntent(query="Semiconductor accelerator initiation", as_of=datetime(2026, 7, 12, tzinfo=timezone.utc)))
    assert inferred.status == "selected"
    case = engine.select(PackSelectionIntent(query="Semiconductor accelerator initiation", case_id="case-ai", as_of=datetime(2026, 7, 12, tzinfo=timezone.utc)))
    assert case.status == "selected"
    assert case.resolution and case.resolution.case_delta_pack_refs == ("case-ai:v1",)


def test_selection_records_conflicts_and_rejections_fail_closed() -> None:
    engine = _engine()
    conflict = engine.select(PackSelectionIntent(query="bank software initiation", sector="saas", report_type="initiation", as_of=datetime(2026, 7, 12, tzinfo=timezone.utc)))
    assert conflict.status == "conflict"
    assert conflict.conflicts[0].code == "query_sector_ambiguous"
    rejected = engine.select(PackSelectionIntent(query="unclassified initiation", report_type="initiation", as_of=datetime(2026, 7, 12, tzinfo=timezone.utc)))
    assert rejected.status == "rejected"
    assert rejected.rejections[0].code == "sector_intent_missing"


def test_m2_4_machine_fixture_is_multi_sector_and_model_free(tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "m2_4_selection_fixture.json"
    completed = subprocess.run([sys.executable, str(root / "scripts/engineering/run_point01_m2_4_pack_selection_fixture.py"), "--output", str(output)], cwd=root, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["multi_sector_report_type_grid"] is True
    assert result["checks"]["conflict_recorded"] is True
