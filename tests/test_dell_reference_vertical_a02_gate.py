from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.agent_runtime.deepseek_structured_agents import (
    load_deepseek_structured_agent_config,
)
from sec_agent.dell_reference_vertical_a02_gate import (
    DELL_REFERENCE_VERTICAL_A02_RUN_SCOPE,
    validate_dell_reference_vertical_a02_paid_start_scope_decision,
)
from sec_agent.project_os_preflight import (
    _validate_fixed_pack_decision,
    build_preflight,
)


ROOT = Path(__file__).resolve().parents[1]
DECISION_REF = (
    "configs/research/evals/"
    "fin_ia_0_1_3_dell_reference_vertical_structured_a02_paid_start_"
    "scope_decision_v1_0.json"
)
DECISION_PATH = ROOT / DECISION_REF
A01_CONFIG_PATH = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_dell_reference_vertical_deepseek_structured_agents_v1_0.json"
)
A02_CONFIG_PATH = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_dell_reference_vertical_deepseek_structured_agents_a02_v1_0.json"
)
LAUNCHER_PATH = (
    ROOT / "scripts/research/run_dell_reference_vertical_structured_a02.ps1"
)


def _decision() -> dict[str, object]:
    return json.loads(DECISION_PATH.read_text(encoding="utf-8"))


def test_a02_successor_config_changes_only_planner_comparable_evidence() -> None:
    predecessor = json.loads(A01_CONFIG_PATH.read_text(encoding="utf-8"))
    successor = json.loads(A02_CONFIG_PATH.read_text(encoding="utf-8"))
    comparable = successor["token_budget_basis"]["planner"][
        "comparable_run_evidence"
    ]
    predecessor["token_budget_basis"]["planner"][
        "comparable_run_evidence"
    ] = comparable

    assert predecessor == successor
    assert "21,465 input tokens" in comparable
    assert "2,076 output tokens" in comparable
    assert "23,541 total tokens" in comparable
    assert "local PydanticToolsParser" in comparable
    assert load_deepseek_structured_agent_config(A02_CONFIG_PATH).max_retries == 0


def test_a02_decision_rejects_any_render_authority_before_paid_start() -> None:
    decision = deepcopy(_decision())
    decision["authority"]["render_authorized"] = True

    with pytest.raises(ValueError, match="dell_a02_authority_invalid"):
        validate_dell_reference_vertical_a02_paid_start_scope_decision(
            root=ROOT,
            decision=decision,
        )


def test_historical_a02_decision_remains_structurally_valid_and_non_resumable() -> None:
    decision = _decision()
    direct = validate_dell_reference_vertical_a02_paid_start_scope_decision(
        root=ROOT,
        decision=decision,
    )

    assert direct == _validate_fixed_pack_decision(root=ROOT, decision=decision)
    assert direct["run_scope_id"] == DELL_REFERENCE_VERTICAL_A02_RUN_SCOPE
    assert direct["evidence_mode"].startswith("reviewed_evidence_plus_")
    assert direct["start_to_hitl_only"] is True
    assert direct["resume_authorized"] is False
    assert direct["render_authorized"] is False
    assert direct["publication_authorized"] is False
    assert direct["formal_qualification_authorized"] is False


def test_consumed_a02_authority_fails_current_project_os_preflight_closed() -> None:
    with pytest.raises(
        ValueError,
        match="project_os_dell_reference_vertical_a02_scope_allowance_missing",
    ):
        build_preflight(
            root=ROOT,
            decision_ref=DECISION_REF,
            environment={},
            check_repository=False,
        )


def test_a02_launcher_binds_decision_and_final_external_pack_without_hash_cycle() -> None:
    text = LAUNCHER_PATH.read_text(encoding="utf-8")

    assert DECISION_REF in text.replace("' +\n    '", "")
    assert "Get-FileHash -Algorithm SHA256" in text
    assert "$projectOsPreflight.decision_sha256" in text
    assert "--project-os-decision-source-path" in text
    assert "--project-os-decision-source-sha256" in text
    assert "dell_external_exact_url_zero_model_20260902_r12\\manifest.json" in text
    assert (
        "db7eae9aaa8108faadbe7ff07404dd25414e0191b7f62af0c7a42b85a0938b94"
        in text
    )
    assert "[switch]$PreflightOnly" in text
    assert "$runArguments += '--preflight-only'" in text
    assert "--run-authority-source" not in text
