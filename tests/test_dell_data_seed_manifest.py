from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import pytest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    ROOT
    / "configs"
    / "research"
    / "fin_ia_0_1_3_dell_reference_vertical_data_seed_v1_0.json"
)


def _load_manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_data_seed_keeps_event_and_authority_boundaries() -> None:
    manifest = _load_manifest()
    event = manifest["event_boundary"]
    routes = manifest["foundation_routes"]
    non_goals = set(manifest["non_goals"])

    assert isinstance(event, dict)
    assert datetime.fromisoformat(str(manifest["research_cutoff"])) >= (
        datetime.fromisoformat(str(event["scheduled_call_time"]))
    )
    assert event["state_at_seed"] == (
        "official_8k_and_earnings_exhibit_captured_call_window_reached"
    )
    assert event["public_complete_demo_requires"] == (
        "E0_event_seal; E1_remains_required_only_for_current_quarter_"
        "structured_numeric_completeness"
    )
    assert isinstance(routes, dict)
    assert routes["legacy_s2_sqlite"].startswith("read_only_numeric_fact_port")
    assert "infer_missing_company_units_or_ASP" in non_goals
    assert "implement_a_custom_general_crawler" in non_goals


@pytest.mark.requires_local_data
def test_verified_local_seed_matches_frozen_files_and_counts() -> None:
    manifest = _load_manifest()
    assets = {
        row["asset_role"]: row for row in manifest["verified_local_assets"]
    }
    narrative = assets["current_narrative_candidate_store"]
    facts = assets["current_company_financial_fact_mart"]
    narrative_path = ROOT / narrative["ref"]
    fact_path = ROOT / facts["ref"]
    if not narrative_path.is_file() or not fact_path.is_file():
        pytest.skip("current local DELL data mounts are unavailable")

    assert _sha256(narrative_path) == narrative["sha256"]
    assert _sha256(fact_path) == facts["sha256"]

    owner_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()
    record_count = 0
    with narrative_path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            record_count += 1
            owner_counts[str(row.get("ticker"))] += 1
            source_type_counts[str(row.get("source_type"))] += 1
    assert record_count == narrative["record_count"] == 1888
    assert owner_counts["DELL"] == 687
    assert source_type_counts == Counter(
        manifest["local_candidate_inventory"]["records_by_source_type"]
    )

    with sqlite3.connect(fact_path) as connection:
        dell_count = connection.execute(
            "SELECT count(*) FROM company_fact_observations WHERE ticker = ?",
            ("DELL",),
        ).fetchone()[0]
        all_count = connection.execute(
            "SELECT count(*) FROM company_fact_observations"
        ).fetchone()[0]
        latest_period_end, latest_filed_at = connection.execute(
            """
            SELECT max(period_end), max(filed_at)
            FROM company_fact_observations
            WHERE ticker = ?
            """,
            ("DELL",),
        ).fetchone()
    numeric = manifest["local_numeric_inventory"]
    assert all_count == facts["observation_count"] == 1319
    assert dell_count == numeric["dell_observation_count"] == 390
    assert latest_period_end == numeric["dell_latest_period_end"]
    assert latest_filed_at == numeric["dell_latest_filed_at"]
