from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
DECISION_REF = (
    "configs/releases/fin_ia_0_1_3_s0_exit_contract_v3_eligibility_authority_"
    "transition_structural_blocker_terminal_decision_v1_0.json"
)
PROJECTION_REF = "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_10.json"
PRE_AUTHORITY_PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_9.json"
)
RUNNER_REF = "scripts/engineering/run_fin_0_1_3_s0_v3_proof_control_plane.py"
PROGRAM_BACKLOG_REF = "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
S4_BACKLOG_REF = "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
CAPABILITY_LEDGER_REF = "docs/project_os/capability_status_ledger.jsonl"
ROOT_CAUSE_LEDGER_REF = "docs/project_os/root_cause_issue_ledger.jsonl"
PATTERN_LEDGER_REF = "docs/project_os/external_pattern_registry.jsonl"
CANONICAL_PLAN_REF = (
    "docs/product/FIN_0_1_3_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_"
    "20260801.zh-CN.md"
)
NEXT = (
    "FIN-0.1.3-S0-EXIT-CONTRACT-V3-TERMINAL-HONEST-BLOCK-AND-"
    "VERSION-SCOPE-DISPOSITION-DECISION"
)
ISSUE = (
    "RC-P36-096-fin-0-1-3-v3-eligibility-authority-transition-projection-"
    "status-hard-coded-pre-authority-state"
)
POST_AUTHORITY_STATUS = (
    "current_FIN_0_1_3_S0_exit_contract_v3_eligibility_authorized_not_executed"
)


def _load_json(ref: str) -> dict[str, Any]:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _sha256(ref: str) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def _last_jsonl(ref: str) -> dict[str, Any]:
    lines = (ROOT / ref).read_text(encoding="utf-8").splitlines()
    return json.loads(lines[-1])


def _load_runner(module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, ROOT / RUNNER_REF)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    return runner


def test_terminal_decision_is_digest_bound_and_does_not_authorize_execution() -> None:
    decision = _load_json(DECISION_REF)
    authority = decision["authority"]

    for binding in decision["source_bindings"]:
        assert _sha256(binding["ref"]) == binding["sha256"]

    assert _sha256(RUNNER_REF) == (
        "f38b2e0157f1f870c05b9af64716b23e8a2c3774c91f1154aa7266b9a77a0e94"
    )
    assert authority["eligibility_attestation_authorized"] is False
    assert authority["eligibility_attestation_executed"] is False
    assert authority["host_or_formal_proof_authorized"] is False
    assert authority["execution_manifest_created"] is False
    assert authority[
        "automatic_retry_replacement_exit_contract_v4_or_FIN_0_1_4_authorized"
    ] is False
    assert decision["budget_truth"][
        "v3_implementation_eligibility_host_formal_observed"
    ] == [1, 0, 0, 0]
    assert decision["budget_truth"]["eligibility_attestation_consumed"] == 0
    assert decision["first_credible_failure"]["error_code"] == (
        "current_v3_projection_status_invalid"
    )
    assert decision["next_action"] == NEXT


def test_frozen_runner_rejects_truthful_post_authority_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner("fin_v3_authority_transition_terminal_test")
    original_load = runner.LEGACY_LOAD_JSON
    projection_path = (ROOT / PRE_AUTHORITY_PROJECTION_REF).resolve()

    def post_authority_load(path: Path) -> dict[str, Any]:
        value = deepcopy(original_load(path))
        if path.resolve() == projection_path:
            value["status"] = POST_AUTHORITY_STATUS
        return value

    monkeypatch.setattr(runner, "LEGACY_LOAD_JSON", post_authority_load)
    with pytest.raises(
        runner.HERMETIC.HermeticTestRunnerError,
        match="current_v3_projection_status_invalid",
    ):
        runner._validate_current_projection_v3(ROOT, PRE_AUTHORITY_PROJECTION_REF)


def test_current_projection_backlogs_and_project_os_share_terminal_truth() -> None:
    projection = _load_json(PROJECTION_REF)
    program = _load_json(PROGRAM_BACKLOG_REF)
    s4 = _load_json(S4_BACKLOG_REF)
    capability = _last_jsonl(CAPABILITY_LEDGER_REF)
    root_cause = _last_jsonl(ROOT_CAUSE_LEDGER_REF)
    pattern = _last_jsonl(PATTERN_LEDGER_REF)
    expected = projection["expectations"]

    assert projection["decision_binding"] == {
        "ref": DECISION_REF,
        "sha256": _sha256(DECISION_REF),
    }
    assert expected["current_next_action"] == NEXT
    assert expected["capability_id"] == capability["capability_id"]
    assert expected["capability_stage_acceptance"] == capability["stage_acceptance"]
    assert expected["v3_implementation_eligibility_host_formal_observed"] == [
        1,
        0,
        0,
        0,
    ]
    assert expected["eligibility_authorized"] is False
    assert expected["eligibility_host_or_formal_executed"] == [False, False, False]
    assert expected["exit_contract_v4_authorized"] is False
    assert expected["FIN_0_1_4_created_or_implied"] is False
    assert expected["FIN_0_1_3_S1_entry_authorized"] is False
    assert expected["FIN_0_1_release_qualified"] is False

    assert program["active_slice"] == expected["active_slice"]
    assert program["next_action"]["item_id"] == NEXT
    assert program["next_action"]["FIN_0_1_3_current_projection_ref"] == PROJECTION_REF
    assert program["next_action"]["FIN_0_1_3_current_projection_sha256"] == _sha256(
        PROJECTION_REF
    )
    assert s4["current_next_action"] == NEXT
    s0 = s4["FIN_0_1_3_S0_hermetic_runtime_dependency_and_semantic_parity"]
    assert s0["current_projection_ref"] == PROJECTION_REF
    assert s0["current_projection_sha256"] == _sha256(PROJECTION_REF)
    assert s0["exit_contract_v3_observed"] == [1, 0, 0, 0]
    assert s0["exit_contract_v3_eligibility_authorized"] is False
    assert s0["exit_contract_v4_authorized"] is False
    assert s0["open_issue_ids"] == expected["open_issue_ids"]

    assert root_cause["issue_id"] == ISSUE
    assert root_cause["status"] == "open"
    assert NEXT in root_cause["allowed_run_scopes"]
    assert pattern["pattern_id"] == expected["pattern_id"]
    assert pattern["status"] == expected["pattern_status"]


def test_documents_preserve_product_non_inflation_and_next_disposition() -> None:
    canonical = (ROOT / CANONICAL_PLAN_REF).read_text(encoding="utf-8")
    context = (ROOT / "docs/project_os/current_context_pack.zh-CN.md").read_text(
        encoding="utf-8"
    )
    lineage = (
        ROOT
        / "docs/product/FIN_0_1_1_0_1_2_VERSION_LINEAGE_AND_RELEASE_CADENCE_"
        "DECISION_20260731.zh-CN.md"
    ).read_text(encoding="utf-8")

    for text in (canonical, context, lineage):
        assert NEXT in text
        assert "FIN 0.2" in text or "FIN0.2" in text
    assert ISSUE in context
    assert "eligibility budget 未消费" in lineage
    assert "FIN 0.1.4 未自动创建" in canonical
