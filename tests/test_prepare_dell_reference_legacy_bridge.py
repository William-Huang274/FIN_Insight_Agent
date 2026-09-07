from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path

import pytest

import scripts.data_retrieval.prepare_dell_reference_legacy_bridge as bridge


ROOT = Path(__file__).resolve().parents[1]
FROZEN_INPUT = (
    ROOT
    / "data"
    / "workbench_private"
    / "fin_0_1_3_s1b_current_financial_object_store"
    / "v5"
    / "records.jsonl"
)
EXPECTED_SOURCE_TYPES = {
    "10-K": 1334,
    "10-Q": 414,
    "6-K": 2,
    "8-K": 52,
    "EARNINGS_CALL_TRANSCRIPT": 36,
    "MARKET_SNAPSHOT": 3,
    "PUBLIC_PDF": 9,
    "PUBLIC_WEB": 38,
}
pytestmark = pytest.mark.local_data_integration
if not FROZEN_INPUT.is_file():
    pytest.skip("current DELL local data mount is unavailable", allow_module_level=True)


def _load_plan(path: Path) -> tuple[dict, list[dict]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return rows[0], rows[1:]


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _all_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _all_keys(item)}
    return set()


def _mapping_receipt_payload(mapping: dict) -> dict:
    keys = {
        "schema_version",
        "mapping_id",
        "legacy_namespace",
        "legacy_snapshot_id",
        "legacy_snapshot_digest",
        "legacy_object_id",
        "target_kind",
        "target_locator_id",
        "source_locator_digest",
        "authority",
        "metadata",
    }
    return {key: mapping[key] for key in keys}


def test_dell_filter_is_stable_and_preserves_full_source_inventory(tmp_path: Path) -> None:
    first = tmp_path / "dell-bridge-1.jsonl"
    second = tmp_path / "dell-bridge-2.jsonl"

    first_summary = bridge.prepare_bridge_plan(
        input_path=FROZEN_INPUT,
        output_path=first,
        issuer="dell",
    )
    second_summary = bridge.prepare_bridge_plan(
        input_path=FROZEN_INPUT,
        output_path=second,
        issuer="DELL",
    )

    assert first.read_bytes() == second.read_bytes()
    assert first_summary["output_sha256"] == second_summary["output_sha256"]
    assert first_summary["output_sha256"] == sha256(first.read_bytes()).hexdigest()
    assert first_summary["selected_mapping_count"] == 687
    assert first_summary["output_line_count"] == 688

    inventory, rows = _load_plan(first)
    assert inventory["record_type"] == "source_inventory_receipt"
    assert inventory["legacy_snapshot_sha256"] == bridge.LEGACY_SNAPSHOT_SHA256
    assert inventory["legacy_snapshot_record_count"] == 1888
    assert inventory["unique_legacy_object_count"] == 1888
    assert inventory["records_by_issuer"]["DELL"] == 687
    assert inventory["records_by_source_type"] == EXPECTED_SOURCE_TYPES
    assert inventory["source_url_present_count"] == 1885
    assert inventory["source_url_absent_count"] == 3
    assert inventory["issuer_filter"] == "DELL"
    assert inventory["selected_mapping_count"] == 687
    claimed_inventory_digest = inventory.pop("inventory_receipt_digest")
    assert bridge.canonical_sha256(inventory) == claimed_inventory_digest

    assert len(rows) == 687
    assert [row["legacy_mapping"]["legacy_object_id"] for row in rows] == sorted(
        row["legacy_mapping"]["legacy_object_id"] for row in rows
    )
    assert len({row["legacy_mapping"]["mapping_id"] for row in rows}) == 687
    assert len({row["source_locator"]["locator_id"] for row in rows}) < 687

    locators_by_uri: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        locator = row["source_locator"]
        mapping = row["legacy_mapping"]
        locators_by_uri[locator["canonical_uri"]].add(locator["locator_id"])
        assert locator["issuer_id"] == "DELL"
        assert locator["document_date"]
        assert locator["source_type"]
        assert locator["source_family"] == "LEGACY_S1_V5"
        assert locator["source_published_at"] is None
        assert bridge.canonical_sha256(locator) == row["source_locator_digest"]
        assert mapping["target_kind"] == "source_locator"
        assert mapping["target_locator_id"] == locator["locator_id"]
        assert mapping["source_locator_digest"] == row["source_locator_digest"]
        assert bridge.canonical_sha256(_mapping_receipt_payload(mapping)) == mapping[
            "mapping_receipt_digest"
        ]
        for metadata in (locator["metadata"], mapping["metadata"]):
            assert metadata["migration_authority"] is False
            assert metadata["evidence_authority"] is False
            assert metadata["numeric_fact_authority"] is False

    assert all(len(locator_ids) == 1 for locator_ids in locators_by_uri.values())


def test_full_plan_has_only_locator_targets_and_content_addressed_missing_urls(
    tmp_path: Path,
) -> None:
    output = tmp_path / "full-bridge.jsonl"
    summary = bridge.prepare_bridge_plan(
        input_path=FROZEN_INPUT,
        output_path=output,
    )
    inventory, rows = _load_plan(output)

    assert summary["selected_mapping_count"] == 1888
    assert summary["output_line_count"] == 1889
    assert inventory["issuer_filter"] is None
    assert inventory["selected_mapping_count"] == 1888
    assert len(rows) == 1888
    assert sum(
        row["source_locator"]["canonical_uri"].startswith(
            "urn:fin-insight:legacy-source:v5:"
        )
        for row in rows
    ) == 3

    forbidden_keys = {
        "source_capture",
        "capture_id",
        "target_capture_id",
        "knowledge_chunk",
        "chunk_id",
        "target_chunk_id",
        "reviewed_evidence",
        "numeric_fact",
        "embedding",
        "text",
    }
    for row in rows:
        assert row["record_type"] == "legacy_source_locator_mapping"
        assert not (_all_keys(row) & forbidden_keys)
        assert row["legacy_mapping"]["authority"] == {
            "migration_authority": False,
            "evidence_authority": False,
            "numeric_fact_authority": False,
        }


def test_frozen_digest_and_record_count_drift_fail_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    digest_drift = tmp_path / "digest-drift.jsonl"
    digest_drift.write_bytes(FROZEN_INPUT.read_bytes() + b" ")
    digest_output = tmp_path / "digest-output.jsonl"
    with pytest.raises(bridge.BridgePreparationError, match="sha256_mismatch"):
        bridge.prepare_bridge_plan(
            input_path=digest_drift,
            output_path=digest_output,
        )
    assert not digest_output.exists()

    count_drift = tmp_path / "count-drift.jsonl"
    lines = FROZEN_INPUT.read_bytes().splitlines(keepends=True)
    count_drift.write_bytes(b"".join(lines[:-1]))
    monkeypatch.setattr(
        bridge,
        "LEGACY_SNAPSHOT_SHA256",
        bridge.file_sha256(count_drift),
    )
    count_output = tmp_path / "count-output.jsonl"
    with pytest.raises(bridge.BridgePreparationError, match="record_count_mismatch"):
        bridge.prepare_bridge_plan(
            input_path=count_drift,
            output_path=count_output,
        )
    assert not count_output.exists()


def test_existing_output_is_never_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "existing.jsonl"
    output.write_bytes(b"owner-data\n")
    with pytest.raises(bridge.BridgePreparationError, match="output_exists"):
        bridge.prepare_bridge_plan(
            input_path=FROZEN_INPUT,
            output_path=output,
            issuer="DELL",
        )
    assert output.read_bytes() == b"owner-data\n"


def test_cli_requires_input_and_output() -> None:
    with pytest.raises(SystemExit) as exc_info:
        bridge.main([])
    assert exc_info.value.code == 2


def test_cli_writes_the_same_bounded_dell_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "cli-dell.jsonl"
    assert (
        bridge.main(
            [
                "--input",
                str(FROZEN_INPUT),
                "--output",
                str(output),
                "--issuer",
                "DELL",
            ]
        )
        == 0
    )
    terminal = json.loads(capsys.readouterr().out)
    assert terminal["status"] == "locator_only_bridge_plan_written"
    assert terminal["selected_mapping_count"] == 687
    assert terminal["output_line_count"] == 688
    assert terminal["output_sha256"] == sha256(output.read_bytes()).hexdigest()
