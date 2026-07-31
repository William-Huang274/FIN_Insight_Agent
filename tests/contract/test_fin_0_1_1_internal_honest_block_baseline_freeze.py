from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASES = ROOT / "configs" / "releases"
MANIFEST = RELEASES / "fin_ia_0_1_1_internal_honest_block_baseline_manifest_v1_0.json"
PROGRAM = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
S4_BACKLOG = RELEASES / "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_freeze_source_bindings_are_content_addressed_and_current() -> None:
    manifest = _load(MANIFEST)
    for binding in manifest["source_bindings"]:
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert _sha256(path) == binding["sha256"]


def test_freeze_preserves_honest_product_truth() -> None:
    manifest = _load(MANIFEST)
    truth = manifest["product_truth"]
    assert truth["NVDA_historical_S3_R2"] is True
    assert truth["NVDA_accepted_artifacts"] == 9
    assert truth["DELL_R2"] is False
    assert truth["MU_R2"] is False
    assert truth["post_transfer_NVDA_exact_product"] is False
    assert truth["NVDA_R3"] is False
    assert truth["S4_pass"] is False
    assert truth["FIN_0_1_release_qualified"] is False
    assert manifest["non_inflation"]["internal_tag_called_release"] is False


def test_freeze_binds_verified_external_recovery_package() -> None:
    recovery = _load(MANIFEST)["external_recovery_package"]
    path = Path(recovery["path"])
    assert _sha256(path / "manifest.json") == recovery["manifest_file_sha256"]
    assert _sha256(path / "verification.json") == recovery["verification_file_sha256"]
    verification = _load(path / "verification.json")
    assert verification["status"] == recovery["verification_status"]
    assert verification["manifest_digest"] == recovery["manifest_semantic_digest"]
    assert verification["manifest_entries_verified"] == recovery["manifest_entries_verified"]


def test_freeze_is_zero_call_local_only_and_hands_off_to_fin_0_1_2_s0() -> None:
    manifest = _load(MANIFEST)
    assert set(manifest["observed_counts"].values()) == {0}
    assert manifest["git_lineage"]["tag_push_authorized"] is False
    assert manifest["git_lineage"]["release_created"] is False
    assert manifest["next_action"] == "FIN-0.1.2-S0-COMMON-RUNTIME-AND-TEST-CONTRACT-REBASELINE"
    assert "FIN_0_1_2_S0" in manifest["open_ownership"]


def test_current_backlogs_project_the_freeze_and_s0_handoff() -> None:
    program = _load(PROGRAM)
    s4 = _load(S4_BACKLOG)
    assert program["version"] == "FIN_0_1_1_INTERNAL_HONEST_BLOCK"
    assert program["current_truth"]["FIN_0_1_1_status"] == "frozen_internal_honest_block"
    assert program["next_action"]["item_id"] == s4["current_next_action"]
    assert program["next_action"]["item_id"] != _load(MANIFEST)["next_action"]
    assert program["active_slice"] == "FIN_0_1_2_S0"
    assert s4["FIN_0_1_1_internal_freeze"]["release_qualified"] is False
