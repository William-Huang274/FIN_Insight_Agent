"""User-owned resource packages keep integrity and path isolation after relocation."""
import hashlib
import json

import pytest

from sec_agent.runtime_resource_registry import (
    RuntimeResourceRegistryError, load_runtime_resource_registry,
    read_registered_runtime_json,
)


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode()).hexdigest()


def _package(root):
    root.mkdir()
    value = b'{"unit":"USD","source":"synthetic"}\n'
    (root / "source.json").write_bytes(value)
    rows = [{"resource_id": "application.config.example", "repo_relative_path": "source.json",
        "sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value),
        "classification": "application_runtime_config", "consumer_ids": ["test.reader"],
        "load_phase": "read", "required": True, "source_owner": "test"}]
    payload = {"schema_version": "fin_ia_0_1_3_runtime_resource_registry_v1_0",
        "registry_id": "synthetic-package", "status": "tracked_typed_runtime_resource_authority",
        "policy": {k: True for k in (
            "registry_is_source_of_truth", "static_scanner_is_detector_only",
            "direct_unregistered_runtime_read_fails_closed",
            "missing_unknown_duplicate_or_digest_drift_fails_closed",
            "permutation_or_cross_version_fails_closed",
            "ignored_untracked_codex_runtime_and_git_forbidden",
            "traversal_and_symlink_escape_forbidden")},
        "detector_python_refs": [], "resource_count": 1, "resource_bytes": len(value),
        "resource_canonical_digest": _digest(rows), "resources": rows}
    (root / "runtime-resources.json").write_text(json.dumps(payload), encoding="utf-8")
    return payload


def test_resource_package_reads_from_explicit_external_root(tmp_path, monkeypatch):
    package = tmp_path / "user-data"
    _package(package)
    monkeypatch.setenv("FINSIGHT_RESEARCH_RESOURCES_ROOT", str(package))
    assert read_registered_runtime_json(tmp_path / "checkout", "application.config.example") == {
        "unit": "USD", "source": "synthetic"}
    (package / "source.json").write_text('{"unit":"CNY"}', encoding="utf-8")
    with pytest.raises(RuntimeResourceRegistryError, match="digest|identity"):
        load_runtime_resource_registry(tmp_path / "checkout")


def test_resource_package_cannot_escape_its_directory(tmp_path, monkeypatch):
    package = tmp_path / "user-data"
    payload = _package(package)
    payload["resources"][0]["repo_relative_path"] = "../outside.json"
    payload["resource_canonical_digest"] = _digest(payload["resources"])
    (package / "runtime-resources.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("FINSIGHT_RESEARCH_RESOURCES_ROOT", str(package))
    with pytest.raises(RuntimeResourceRegistryError, match="path_forbidden"):
        load_runtime_resource_registry(tmp_path / "checkout")
