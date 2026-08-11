from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sec_agent.financial_research_held_out_profile_registry import (
    HeldOutProfileRegistryError,
    execute_held_out_profile_selection,
    load_held_out_profile_selection_policy,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_three_held_out_profile_selection_policy_v1_0.json"
)


def _payload() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def test_three_unseen_profiles_compile_without_core_change() -> None:
    policy, base, extended = load_held_out_profile_selection_policy(
        POLICY,
        repo_root=ROOT,
    )
    result = execute_held_out_profile_selection(
        policy=policy,
        base_contract=base,
        extended_contract=extended,
        repo_root=ROOT,
    )
    assert result["status"] == "held_out_identity_and_profile_freeze_pass"
    assert [row["case_key"] for row in result["case_selections"]] == [
        "ORCL",
        "ASML",
        "ANET",
    ]
    assert {
        row["compiled_core_fingerprint"] for row in result["case_selections"]
    } == {policy.expected_core_fingerprint}
    assert all(
        row["required_slot_count"] == 8
        and row["optional_slot_count"] == 1
        and row["candidate_or_gold_inspection_count"] == 0
        for row in result["case_selections"]
    )
    assert result["locked_artifacts_before"] == result["locked_artifacts_after"]
    assert set(result["observed_calls"].values()) == {0}
    second = execute_held_out_profile_selection(
        policy=policy,
        base_contract=base,
        extended_contract=extended,
        repo_root=ROOT,
    )
    assert result == second


def test_previously_seen_relationship_identity_is_not_a_valid_held_out_case(
    tmp_path: Path,
) -> None:
    payload = _payload()
    payload["selections"][0]["profile"]["case_key"] = "MSFT"
    payload["selections"][0]["profile"]["subject_entity_key"] = "MICROSOFT"
    payload["selections"][0]["profile"]["subject_aliases"] = [
        "Microsoft",
        "MSFT",
    ]
    with pytest.raises(HeldOutProfileRegistryError) as exc:
        load_held_out_profile_selection_policy(
            _write(tmp_path, payload),
            repo_root=ROOT,
        )
    assert exc.value.code == "held_out_identity_seen_in_base_contract"


def test_gold_url_leakage_is_rejected(tmp_path: Path) -> None:
    payload = _payload()
    payload["selections"][0]["research_questions_zh"][0] += (
        " https://example.invalid/gold"
    )
    with pytest.raises(HeldOutProfileRegistryError) as exc:
        load_held_out_profile_selection_policy(
            _write(tmp_path, payload),
            repo_root=ROOT,
        )
    assert exc.value.code == "held_out_gold_or_locator_leakage"


def test_industry_pack_cannot_relax_kernel_authority(tmp_path: Path) -> None:
    payload = _payload()
    payload["industry_pack_overlays"][0][
        "may_relax_identity_period_lineage_or_authority"
    ] = True
    with pytest.raises(HeldOutProfileRegistryError) as exc:
        load_held_out_profile_selection_policy(
            _write(tmp_path, payload),
            repo_root=ROOT,
        )
    assert exc.value.code == "held_out_industry_pack_contract_invalid"


def test_profile_cannot_select_unknown_pack(tmp_path: Path) -> None:
    payload = _payload()
    payload["selections"][0]["profile"]["industry_pack_ref"] = "unknown:v1"
    with pytest.raises(HeldOutProfileRegistryError) as exc:
        load_held_out_profile_selection_policy(
            _write(tmp_path, payload),
            repo_root=ROOT,
        )
    assert exc.value.code == "held_out_profile_pack_not_in_overlay"


def test_selection_order_and_identity_are_frozen(tmp_path: Path) -> None:
    payload = _payload()
    payload["selections"] = list(reversed(payload["selections"]))
    with pytest.raises(HeldOutProfileRegistryError) as exc:
        load_held_out_profile_selection_policy(
            _write(tmp_path, payload),
            repo_root=ROOT,
        )
    assert exc.value.code == "held_out_archetype_order_or_identity_invalid"


def test_candidate_inspection_before_freeze_is_rejected(tmp_path: Path) -> None:
    payload = _payload()
    payload["pre_freeze_observation_boundary"]["candidate_results_inspected"] = True
    with pytest.raises(HeldOutProfileRegistryError) as exc:
        load_held_out_profile_selection_policy(
            _write(tmp_path, payload),
            repo_root=ROOT,
        )
    assert exc.value.code == "held_out_pre_freeze_observation_boundary_invalid"


def test_locked_core_digest_drift_is_rejected(tmp_path: Path) -> None:
    payload = copy.deepcopy(_payload())
    payload["locked_artifacts"][0]["normalized_sha256"] = "0" * 64
    with pytest.raises(HeldOutProfileRegistryError) as exc:
        load_held_out_profile_selection_policy(
            _write(tmp_path, payload),
            repo_root=ROOT,
        )
    assert exc.value.code == "held_out_locked_artifact_digest_mismatch"
