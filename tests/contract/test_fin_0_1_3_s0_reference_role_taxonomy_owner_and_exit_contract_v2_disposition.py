from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DECISION_REF = (
    "configs/releases/fin_ia_0_1_3_s0_t03_terminal_honest_block_"
    "reference_role_taxonomy_owner_and_exit_contract_v2_disposition_v1_0.json"
)
CURRENT_PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_4.json"
)
FROZEN_T03_PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_3.json"
)
PROGRAM_BACKLOG_REF = (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG_REF = (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
NEXT_ACTION = (
    "FIN-0.1.3-S0-REFERENCE-ROLE-TAXONOMY-REGISTRY-AND-COLLECT-ALL-"
    "COMPILER-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
DECISION_SHA256 = (
    "2c040ff28f499b03e36cc5d3b5b31df7827fe27d8a1448958d6dd965f368fcba"
)
EXPECTED_ROLES = [
    "repository_resource",
    "package_relative_audit",
    "external_content",
    "restricted_runtime_audit",
    "model_run_report",
    "semantic_followup",
]


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(ref: str) -> dict[str, Any]:
    return json.loads(
        (ROOT / ref).read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )


def _load_jsonl(ref: str) -> list[dict[str, Any]]:
    return [
        json.loads(line, object_pairs_hook=_reject_duplicate_keys)
        for line in (ROOT / ref).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(ref: str) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def test_disposition_binds_sources_and_preserves_terminal_T03() -> None:
    decision = _load(DECISION_REF)
    assert _sha256(DECISION_REF) == DECISION_SHA256
    assert decision["status"] == (
        "pass_FIN_0_1_3_kept_as_single_current_mainline_S0_exit_contract_"
        "v2_selected_implementation_pending"
    )
    for binding in decision["source_bindings"]:
        assert (ROOT / binding["ref"]).is_file()
        if binding["binding_mode"] == "immutable_source":
            assert binding["sha256"] == _sha256(binding["ref"])
        else:
            assert binding["binding_mode"] == (
                "recorded_projection_snapshot_not_future_immutability"
            )
            assert len(binding["sha256"]) == 64
    terminal = decision["terminal_T03_truth"]
    assert terminal["engineering_proof_runs"] == [1, 1]
    assert terminal["old_T03_rerun_authorized"] is False
    assert terminal["old_T04_authorized"] is False
    assert terminal["historical_result_reinterpreted"] is False
    assert (ROOT / FROZEN_T03_PROJECTION_REF).is_file()


def test_exit_contract_v2_is_bounded_typed_and_not_a_product_pass() -> None:
    decision = _load(DECISION_REF)
    contract = decision["exit_contract_v2"]
    assert contract["contract_id"] == "fin_0_1_3.S0.exit_contract:v2"
    assert contract["required_reference_roles"] == EXPECTED_ROLES
    assert contract["fixed_budget"] == {
        "maximum_zero_call_implementation_bundles": 1,
        "maximum_host_engineering_proof_runs": 1,
        "maximum_formal_two_disposable_proof_packages": 1,
        "automatic_retries": 0,
        "automatic_replacement_families": 0,
        "automatic_version_bumps": 0,
    }
    assert decision["options"]["automatically_create_FIN_0_1_4"] is False
    assert decision["product_truth"]["taxonomy_implemented"] is False
    assert decision["product_truth"]["FIN_0_1_release_qualified"] is False
    assert decision["next_action"] == NEXT_ACTION


def test_current_projection_and_backlogs_have_one_current_next_owner() -> None:
    projection = _load(CURRENT_PROJECTION_REF)
    assert projection["decision_binding"] == {
        "ref": DECISION_REF,
        "sha256": DECISION_SHA256,
    }
    assert projection["expectations"]["current_next_action"] == NEXT_ACTION
    assert projection["expectations"]["required_reference_roles"] == EXPECTED_ROLES
    program = _load(PROGRAM_BACKLOG_REF)
    s4 = _load(S4_BACKLOG_REF)
    assert program["active_slice"] == projection["expectations"]["active_slice"]
    assert program["next_action"]["item_id"] == NEXT_ACTION
    assert program["next_action"]["FIN_0_1_3_current_projection_ref"] == (
        CURRENT_PROJECTION_REF
    )
    assert s4["current_next_action"] == NEXT_ACTION
    assert s4["FIN_0_1_3_S0_hermetic_runtime_dependency_and_semantic_parity"][
        "current_projection_ref"
    ] == CURRENT_PROJECTION_REF


def test_project_os_tracks_the_selected_plan_without_closing_blockers() -> None:
    projection = _load(CURRENT_PROJECTION_REF)
    sources = projection["source_paths"]
    context = (ROOT / sources["context_pack"]).read_text(encoding="utf-8")
    assert f"current next=`{NEXT_ACTION}`" in context
    capability = next(
        row
        for row in reversed(_load_jsonl(sources["capability_ledger"]))
        if row.get("capability_id")
        == projection["expectations"]["capability_id"]
    )
    assert capability["current_next"] == NEXT_ACTION
    assert capability["stage_acceptance"] == projection["expectations"][
        "capability_stage_acceptance"
    ]
    root_rows = _load_jsonl(sources["root_cause_ledger"])
    for issue_id in projection["expectations"]["open_issue_ids"]:
        row = next(
            item
            for item in reversed(root_rows)
            if item.get("issue_id") == issue_id
        )
        assert row["status"] == "open"
        assert row["full_chain_blocker"] is True
        assert NEXT_ACTION in row["allowed_run_scopes"]
    pattern = next(
        row
        for row in reversed(_load_jsonl(sources["external_pattern_ledger"]))
        if row.get("pattern_id") == projection["expectations"]["pattern_id"]
    )
    assert pattern["status"] == projection["expectations"]["pattern_status"]


def test_product_plan_restores_one_complete_S0_to_S5_axis() -> None:
    decision = _load(DECISION_REF)
    product_ref = next(
        binding["ref"]
        for binding in decision["source_bindings"]
        if binding["role"] == "canonical_product_stage_owner"
    )
    text = (ROOT / product_ref).read_text(encoding="utf-8")
    for stage in ("S0 可信基础", "S1 确定性三案", "S2 模型边界", "S3 单案例产品锚点", "S4 跨案例迁移与工作台价值", "S5 发布判定"):
        assert stage in text
    assert "FIN-0.1.3-S0-REFERENCE-ROLE-TAXONOMY" in text
