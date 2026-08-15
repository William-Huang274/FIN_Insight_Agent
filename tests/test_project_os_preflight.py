from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from sec_agent.project_os_preflight import (
    FIXED_PACK_SCOPE,
    REQUIRED_PROJECT_OS_REFS,
    build_preflight,
)


ROOT = Path(__file__).resolve().parents[1]
DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_live_decision_v1_0.json"
)


def _copy_ref(target_root: Path, ref: str) -> None:
    source = ROOT / ref
    target = target_root / ref
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _fixture_root(tmp_path: Path) -> Path:
    for ref in REQUIRED_PROJECT_OS_REFS:
        _copy_ref(tmp_path, ref)
    _copy_ref(tmp_path, DECISION_REF)
    decision = json.loads((ROOT / DECISION_REF).read_text(encoding="utf-8"))
    for field in (
        "clean_zero_call_result_ref",
        "immutable_predecessor_result_ref",
        "provider_profile_ref",
        "provider_health_evidence_ref",
    ):
        _copy_ref(tmp_path, decision[field])
    return tmp_path


def test_current_fixed_pack_decision_passes_without_network_or_secret_read() -> None:
    result = build_preflight(
        root=ROOT,
        decision_ref=DECISION_REF,
        environment={"DEEPSEEK_API_KEY": "present-but-never-persisted"},
        check_repository=False,
    )

    assert result["status"] == "pass_current_decision_bound_preflight"
    assert result["run_scope_id"] == FIXED_PACK_SCOPE
    assert result["network_calls"] == 0
    assert result["provider_calls"] == 0
    assert result["credential_value_persisted"] is False
    assert result["checks"]["provider_credential_present_value_unread"] is True
    assert (
        "RC-S3-004-model_visible_judgment_contract_omits_enums_and_conflates_evidence_use"
        in result["scope_projection"]["explicit_allow_issue_ids"]
    )


def test_missing_provider_credential_fails_closed() -> None:
    with pytest.raises(
        ValueError, match="project_os_provider_credential_missing:DEEPSEEK_API_KEY"
    ):
        build_preflight(
            root=ROOT,
            decision_ref=DECISION_REF,
            environment={},
            check_repository=False,
        )


def test_bound_artifact_sha_drift_fails_closed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    decision = json.loads((root / DECISION_REF).read_text(encoding="utf-8"))
    clean_path = root / decision["clean_zero_call_result_ref"]
    clean_path.write_text(clean_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="project_os_artifact_sha_drift"):
        build_preflight(
            root=root,
            decision_ref=DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present"},
            check_repository=False,
        )


def test_new_scope_specific_blocker_fails_closed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    ledger = root / "docs/project_os/root_cause_issue_ledger.jsonl"
    blocker = {
        "schema_version": "fin_insight_root_cause_issue_ledger_v0_1",
        "issue_id": "RC-TEST-CURRENT-SCOPE-BLOCKER",
        "status": "open",
        "full_chain_blocker": True,
        "blocking_run_scopes": [FIXED_PACK_SCOPE],
        "allowed_run_scopes": [],
    }
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(blocker, ensure_ascii=False) + "\n")

    with pytest.raises(
        ValueError,
        match="project_os_scope_blocked:RC-TEST-CURRENT-SCOPE-BLOCKER",
    ):
        build_preflight(
            root=root,
            decision_ref=DECISION_REF,
            environment={"DEEPSEEK_API_KEY": "present"},
            check_repository=False,
        )
