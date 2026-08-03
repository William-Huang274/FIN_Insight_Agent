from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "releases"))

from run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (
    Fin012S3T03SupervisedLiveError,
    _load_later_execution_authority,
    load_admission,
    load_target,
)


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_"
    "execution_authority_decision_r2_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_fresh_exact_admission_r1.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_fresh_exact_"
    "admission_issuance_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_bound_execution_launcher_"
    "parent_supervisor_zero_call_preflight_minimum_implementation_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_28.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_r2_binds_immutable_admission_current_runner_and_launcher() -> None:
    decision = _load(DECISION)
    source = decision["source_authority"]
    target = load_target()
    admission = load_admission(target)

    assert decision["status"] == "authorized_exact_once_execution_not_started"
    assert source["admission_file_sha256"] == _sha256(ADMISSION)
    assert source["issuance_file_sha256"] == _sha256(ISSUANCE)
    assert source["launcher_supervisor_implementation_sha256"] == _sha256(
        IMPLEMENTATION
    )
    assert source["admission_digest"] == target.admission_digest
    assert admission.admission_id == target.admission_id
    for relative, digest in decision["current_code_bindings"].items():
        assert _sha256(ROOT / relative) == digest


def test_r2_is_accepted_by_the_real_launcher_authority_loader() -> None:
    target = load_target()
    authority = _load_later_execution_authority(DECISION, target)

    assert authority["authority"]["future_exact_live_execution_authorized"] is True
    assert authority["authority"][
        "current_turn_admission_consumption_or_execution_authorized"
    ] is False
    assert authority["exact_execution_target"]["execution_identity"] == (
        target.execution_identity
    )


@pytest.mark.parametrize(
    ("mutation", "expected"),
    (
        (("status",), "invalid"),
        (("authority", "future_exact_live_execution_authorized"), "invalid"),
        (("source_authority", "admission_digest"), "invalid"),
        (("exact_execution_target", "execution_identity"), "invalid"),
    ),
)
def test_r2_loader_rejects_authority_or_identity_mutation(
    tmp_path: Path,
    mutation: tuple[str, ...],
    expected: str,
) -> None:
    value = deepcopy(_load(DECISION))
    parent = value
    for key in mutation[:-1]:
        parent = parent[key]
    parent[mutation[-1]] = "mutated"
    path = tmp_path / "mutated-authority.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(Fin012S3T03SupervisedLiveError, match=expected):
        _load_later_execution_authority(path, load_target())


def test_r2_preflight_budget_and_roots_are_fail_closed() -> None:
    decision = _load(DECISION)
    verification = decision["pre_execution_verification"]
    budget = decision["hard_budget"]
    target = decision["exact_execution_target"]

    assert verification["project_os_scope_preflight"] == "pass"
    assert verification["open_full_chain_blocker_count"] == 0
    assert verification["credential_present"] is True
    assert verification["credential_value_read_output_or_persisted"] is False
    assert verification["provider_health_probe_performed"] is False
    assert verification["preflight_provider_callback_calls"] == 0
    assert budget["provider_calls"] == 9
    assert budget["maximum_transport_attempts_per_call"] == 1
    assert budget["retry_budget"] == 0
    assert budget["maximum_total_cost_usd"] == 0.06
    assert not (ROOT / target["runtime_root"]).exists()
    assert not (ROOT / target["supervision_root"]).exists()


def test_r2_stops_before_execution_paired_owner_or_product_claim() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]
    counts = decision["decision_boundary"]
    product = decision["product_boundary"]

    assert authority["new_user_continuation_required_before_execution"] is True
    assert authority[
        "current_turn_admission_consumption_or_execution_authorized"
    ] is False
    assert authority["success_only_paired_assessment_authorized_by_this_decision"] is False
    assert counts["admission_consumptions"] == 0
    assert counts["execution_identity_claims"] == 0
    assert counts["supervisor_exact_live_launches"] == 0
    assert counts["model_calls"] == 0
    assert counts["provider_calls"] == 0
    assert counts["business_artifacts"] == 0
    assert product["external_user_query_or_live_source_product_proof"] is False
    assert product["current_nine_artifact_product_proven"] is False


def test_r2_projection_backlog_and_project_os_are_current() -> None:
    decision = _load(DECISION)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)["next_action"]
    next_action = decision["next_action"]

    assert projection["decision_binding"]["sha256"] == _sha256(DECISION)
    assert projection["current_truth"]["current_next_action"] == next_action
    assert backlog["item_id"] == next_action
    assert backlog["current_projection_sha256"] == _sha256(PROJECTION)
    assert backlog["S3_T03_exact_live_execution_authorized_now"] is True
    assert backlog["S3_T03_fresh_admission_consumed"] is False
    assert backlog["S3_T03_execution_started"] is False
    capabilities = (
        ROOT / "docs/project_os/capability_status_ledger.jsonl"
    ).read_text(encoding="utf-8")
    context = (ROOT / "docs/project_os/current_context_pack.zh-CN.md").read_text(
        encoding="utf-8"
    )
    assert decision["decision_id"] in capabilities
    assert next_action in context
