import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_sub2api_park_and_deepseek_mainline_rebaseline_decision_v1_0.json"
)
HANDOFF = ROOT / "docs" / "project_os" / "STRICT_SCHEMA_TRANSPORT_API_HANDOFF.zh-CN.md"
S4_BACKLOG = (
    ROOT / "configs" / "releases" / "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs" / "releases" / "fin_ia_0_1_program_release_backlog_v2_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_rebaseline_selects_existing_deepseek_pro_mainline_without_provider_call() -> None:
    decision = _load(DECISION)
    binding = decision["DeepSeek_mainline_binding"]
    assert binding == {
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "model_tier": "pro_not_flash",
        "model_ref": "deepseek:deepseek-v4-pro",
        "base_url": "https://api.deepseek.com/beta",
        "credential_env": "DEEPSEEK_API_KEY",
        "credential_presence_checked": True,
        "credential_present": True,
        "credential_value_read_or_printed": False,
        "transport_family": "existing_segmented_typed_atom_and_local_validation_path",
        "server_side_strict_schema_required_for_T06_entry": False,
        "local_fail_closed_validation_required": True,
        "provider_hopping_allowed": False,
    }
    counts = decision["observed_counts"]
    assert counts["model_calls"] == 0
    assert counts["provider_calls"] == 0
    assert counts["network_calls"] == 0
    assert counts["credential_value_reads"] == 0
    assert counts["admissions_issued"] == 0


def test_strict_schema_track_is_parked_but_recoverable_and_does_not_weaken_l1() -> None:
    decision = _load(DECISION)
    disposition = decision["program_disposition"]
    assert disposition["Sub2API_track"].startswith("parked_external_dependency")
    assert disposition["strict_schema_transport"].endswith(
        "not_a_DeepSeek_MU_T06_entry_blocker"
    )
    assert decision["integrity_contract"]["hard_fail_retained_for"] == [
        "source_and_identity_integrity",
        "numeric_authority_and_correspondence",
        "typed_structure_required_for_canonical_materialization",
        "secret_safety",
        "atomic_terminal_truth",
    ]
    handoff = HANDOFF.read_text(encoding="utf-8")
    assert "已停放，不阻断 DeepSeek 主线" in handoff
    assert "standalone raw HTTP/curl" in handoff
    assert "完整 HTTPS base URL" in handoff
    assert "真实密钥不要写进仓库文档或普通聊天" in handoff


def test_stage_non_inflation_and_next_action_are_explicit() -> None:
    decision = _load(DECISION)
    assert decision["stage_disposition"]["S4_T05"].startswith(
        "honestly_blocked_after_R11_no_R12"
    )
    assert decision["stage_disposition"]["S4_T06"] == (
        "entered_zero_call_MU_preparation_only"
    )
    assert decision["stage_disposition"]["MU_R2"] == "not_started"
    assert not decision["non_inflation"]["transport_schema_capability_claimed"]
    assert not decision["non_inflation"]["MU_exact_execution_started"]
    assert not decision["non_inflation"]["S4_passed"]
    expected = (
        "S4-T06-MU-DEEPSEEK-MAINLINE-FRESH-EXACT-ADMISSION-"
        "PREPARATION-AND-ZERO-CALL-PROOF"
    )
    progressed = (
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    assert decision["current_next"] == expected
    assert _load(S4_BACKLOG)["current_next_action"] == progressed
    assert _load(PROGRAM_BACKLOG)["next_action"]["item_id"] == progressed
