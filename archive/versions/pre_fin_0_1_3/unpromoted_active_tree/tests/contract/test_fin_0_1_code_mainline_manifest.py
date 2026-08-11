from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPO_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_code_mainline_manifest_v1_0.json"
)


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_mainline_manifest_has_required_groups_and_existing_paths() -> None:
    manifest = _manifest()
    assert manifest["schema_version"] == "fin_ia_0_1_code_mainline_manifest_v1_0"
    groups = manifest["path_groups"]
    required_groups = {
        "current_product_runtime",
        "reusable_foundation",
        "legacy_compatibility_and_rollback",
        "historical_agent_engine_reuse_candidates",
        "release_reproducibility",
        "durable_release_evidence",
        "historical_point01_proof_support",
        "design_reference",
        "generated_local_excluded",
    }
    assert required_groups <= set(groups)

    for entries in groups.values():
        for entry in entries:
            if entry.get("required_exists"):
                assert (REPO_ROOT / entry["path"]).exists(), entry["path"]


def test_generated_local_paths_are_not_classified_as_product_runtime() -> None:
    manifest = _manifest()
    groups = manifest["path_groups"]
    active_paths = {
        entry["path"]
        for group_name in ("current_product_runtime", "reusable_foundation")
        for entry in groups[group_name]
    }
    generated_paths = {entry["path"] for entry in groups["generated_local_excluded"]}
    assert active_paths.isdisjoint(generated_paths)

    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/.codex_runtime/" in gitignore
    assert "/output/" in gitignore


def test_release_contract_families_have_one_active_authority() -> None:
    manifest = _manifest()
    for family in manifest["release_contract_versions"]:
        active = family["active"]
        active_paths = active if isinstance(active, list) else [active]
        assert active_paths
        for path in active_paths:
            assert (REPO_ROOT / path).is_file(), path


def test_disconnected_slices_are_explicitly_retained_or_integrated_later() -> None:
    manifest = _manifest()
    slices = manifest["disconnected_slices"]
    assert len(slices) >= 6
    assert len({item["slice_id"] for item in slices}) == len(slices)
    for item in slices:
        assert item["producer_paths"]
        assert item["not_connected_to"]
        assert item["reason"]
        assert item["effect"]
        assert item["decision"]
