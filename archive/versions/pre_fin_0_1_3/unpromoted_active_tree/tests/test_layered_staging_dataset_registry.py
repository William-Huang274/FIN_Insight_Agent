from __future__ import annotations

from pathlib import Path

import yaml


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "configs" / "data_sources" / "layered_staging_datasets_v0_1.yaml"


def test_layered_staging_registry_reserves_non_us_append_shard() -> None:
    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    dataset = registry["datasets"]["tier1_plus_global_primary_disclosure_v0_1"]
    shards = dataset["source_shards"]

    assert registry["promotion_policy"]["allow_incremental_non_us_append"] is True
    assert registry["promotion_policy"]["mainline_index_overwrite_allowed"] is False
    assert shards["sec_tier1_sp500_us_annual_v0_1"]["status"] == "active"
    assert shards["global_public_tier2_annual_v0_1"]["status"] == "reserved"
    assert shards["global_public_tier2_annual_v0_1"]["source_tier"] == "primary_global_public_disclosure"
    assert dataset["gates"]["non_us_shard_append_must_not_force_sec_rechunk"] is True
    assert "merged_outputs" in dataset
