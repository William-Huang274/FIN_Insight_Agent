from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.releases.prepare_fin_ia_0_1_2_s2_t04_identity_sealed_blind_assessment_packet import (
    BlindPacketError,
    CAPTURES,
    PACKET_ID,
    assert_no_identity_leak,
    build_packet,
)


pytestmark = pytest.mark.fast_contract


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_builds_six_output_three_family_packet_and_sealed_mapping(tmp_path: Path):
    output_root = tmp_path / "blind-packet"
    manifest = build_packet(
        ROOT, output_root, mapping_bit=0, nonce_hex="11" * 32
    )
    packet = _load(output_root / "assessor-packet.json")
    assert packet["packet_id"] == PACKET_ID
    assert len(packet["families"]) == 3
    assert [len(row["candidate_outputs"]) for row in packet["families"]] == [
        2,
        2,
        2,
    ]
    assert all(
        [row["label"] for row in family["candidate_outputs"]]
        == ["candidate_A", "candidate_B"]
        for family in packet["families"]
    )
    assert manifest["selected_capture_count"] == 6
    assert manifest["identity_leak_preflight"] == "pass"
    assert manifest["model_provider_network_calls"] == [0, 0, 0]
    mapping_ref = Path(manifest["restricted_mapping_ref"])
    mapping = _load(mapping_ref)
    assert mapping["label_to_candidate"] == {
        "candidate_A": "flash_stable",
        "candidate_B": "pro_preview",
    }
    assert hashlib.sha256(mapping_ref.read_bytes()).hexdigest() in packet[
        "mapping_commitment"
    ]
    assert "nonce_hex" not in packet


def test_random_mapping_direction_changes_labels_not_content_or_context(tmp_path: Path):
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    build_packet(ROOT, left_root, mapping_bit=0, nonce_hex="22" * 32)
    build_packet(ROOT, right_root, mapping_bit=1, nonce_hex="33" * 32)
    left = _load(left_root / "assessor-packet.json")
    right = _load(right_root / "assessor-packet.json")
    visibly_swapped_family_count = 0
    for left_family, right_family in zip(
        left["families"], right["families"], strict=True
    ):
        assert left_family["family_id"] == right_family["family_id"]
        assert left_family["evaluation_context"] == right_family["evaluation_context"]
        left_outputs = {
            json.dumps(row["output"], sort_keys=True)
            for row in left_family["candidate_outputs"]
        }
        right_outputs = {
            json.dumps(row["output"], sort_keys=True)
            for row in right_family["candidate_outputs"]
        }
        assert left_outputs == right_outputs
        if left_family["candidate_outputs"] != right_family["candidate_outputs"]:
            visibly_swapped_family_count += 1
    assert visibly_swapped_family_count >= 1


def test_packet_excludes_identity_operational_digests_and_paths(tmp_path: Path):
    output_root = tmp_path / "blind-packet"
    build_packet(ROOT, output_root, mapping_bit=1, nonce_hex="44" * 32)
    packet = _load(output_root / "assessor-packet.json")
    assert_no_identity_leak(packet)
    text = json.dumps(packet, ensure_ascii=False, sort_keys=True).lower()
    for spec in CAPTURES:
        assert spec["sha256"] not in text
        assert spec["candidate_id"] not in text
        assert spec["ref"].replace("\\", "/").lower() not in text
    for forbidden in (
        "deepseek",
        "latency_ms",
        '"usage"',
        '"call_id"',
        '"model_ref"',
        '"provider"',
    ):
        assert forbidden not in text


def test_mapping_commitment_nonce_prevents_two_choice_enumeration(tmp_path: Path):
    first = build_packet(
        ROOT, tmp_path / "first", mapping_bit=0, nonce_hex="55" * 32
    )
    second = build_packet(
        ROOT, tmp_path / "second", mapping_bit=0, nonce_hex="66" * 32
    )
    assert first["mapping_commitment"] != second["mapping_commitment"]


def test_same_packet_identity_cannot_be_materialized_twice(tmp_path: Path):
    output_root = tmp_path / "blind-packet"
    build_packet(ROOT, output_root, mapping_bit=0, nonce_hex="77" * 32)
    with pytest.raises(BlindPacketError, match="identity_already_claimed"):
        build_packet(ROOT, output_root, mapping_bit=0, nonce_hex="77" * 32)
