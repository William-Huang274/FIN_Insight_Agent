from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "configs/releases/fin_ia_0_1_release_contract_v1_2.json"
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_detailed_execution_backlog_v1_1.json"
DECISION = ROOT / "configs/releases/point01_foundation_alpha_scope_closeout_decision_v1_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_digest(payload: dict[str, object], *, omit: str | None = None) -> str:
    material = {key: value for key, value in payload.items() if key != omit}
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_scope_closeout_is_narrow_and_defers_operational_qualification() -> None:
    decision = _load(DECISION)
    assert decision["decision"] == "POINT01_FOUNDATION_ALPHA_CONTRACT_RUNTIME_PROOF_COMPLETE"
    assert decision["supersedes"]["forbidden_prior_terminal"] == "POINT01_FOUNDATION_ALPHA_COMPLETE"
    axes = decision["state_axes"]
    assert axes["operational_qualification"] == "not_qualified_deferred_to_REL_PROD_001_RG1"
    assert axes["production_readiness"] == "not_admitted"
    assert axes["legacy_global_authority"] == "retained"
    assert decision["p01_gate_disposition"]["P01-G2"] == "failed_single_operational_attempt_consumed_and_deferred_to_REL_PROD_001_RG1"


def test_active_release_contract_and_backlog_bind_the_same_rg1_debt() -> None:
    decision = _load(DECISION)
    release = _load(RELEASE)
    backlog = _load(BACKLOG)
    assert release["schema_version"] == "fin_release_contract_v1_2"
    assert release["supersedes"]["schema_version"] == "fin_release_contract_v1_1"
    assert release["unchanged_v1_1_contract_inheritance"]["file_sha256"] == "93ea4fd19a20819452d0f3eb61fa2728bbc9747bfb23a169e3fa7100df98fb4d"
    assert release["entry_gate"]["development_admission"] == "fixture_shadow_internal_development_only"
    assert release["release_admission"]["issuer"] == "P07.5_only"
    assert "RG1_vertical_path_entry_to_clean_child_identity_invariant" in release["release_admission"]["hard_blockers"]
    assert backlog["schema_version"] == "fin_ia_0_1_detailed_execution_backlog_v1_1"
    assert backlog["point_overrides"]["P02.0"]["status"] == "development_admitted_fixture_shadow_internal_only"
    assert backlog["point_overrides"]["P07.5"]["status"] == "release_decision_blocked_until_RG1_vertical_path_debt_closed"
    assert backlog["test_profile_contract"]["operational"] == "not_qualified_deferred_to_REL_PROD_001_RG1"
    assert decision["active_contract_bindings"]["release_contract"]["canonical_digest"] == _canonical_digest(release)
    assert decision["active_contract_bindings"]["detailed_execution_backlog"]["canonical_digest"] == _canonical_digest(backlog)
    assert decision["manifest_digest"] == _canonical_digest(decision, omit="manifest_digest")


def test_failed_attempt_is_recorded_without_turning_it_into_a_pass_or_retry() -> None:
    decision = _load(DECISION)
    evidence = decision["failed_operational_evidence"]
    assert evidence["terminal_digest"] == "728d9ebd2e5c215f0c782f258c22e154658f316286e3c058ce43c379b99f0342"
    assert evidence["receipt_lifecycle"] == "consumed_permanently_nonreplayable_nonrenewable_nonreplaceable"
    blocker = decision["release_hard_blocker"]
    assert blocker["gate"] == "RG1_vertical_path"
    assert blocker["bypass_forbidden"] is True
    assert decision["test_profile_contract"]["operational"] == "not_qualified_deferred_to_REL_PROD_001_RG1"
    assert "operational_retry_or_replay" in decision["development_admission"]["forbidden"]
