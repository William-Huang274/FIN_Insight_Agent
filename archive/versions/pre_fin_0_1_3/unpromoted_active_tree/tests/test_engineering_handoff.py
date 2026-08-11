from __future__ import annotations

from pathlib import Path

from sec_agent.engineering_handoff import (
    build_handoff_summary,
    classify_test_nodeid,
    load_json,
    validate_canonical_registry,
    validate_legacy_mapping,
    validate_test_profile_registry,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = ROOT / "configs" / "engineering_handoff"


def _payloads():
    return (
        load_json(CONFIG_ROOT / "canonical_object_registry_v0_1.json"),
        load_json(CONFIG_ROOT / "legacy_object_mapping_matrix_v0_1.json"),
        load_json(CONFIG_ROOT / "test_profile_registry_v0_1.json"),
    )


def test_handoff_registries_are_cross_validated_and_not_cut_over() -> None:
    canonical, mapping, profiles = _payloads()

    assert validate_canonical_registry(canonical) == []
    assert validate_legacy_mapping(mapping, canonical, repo_root=ROOT) == []
    assert validate_test_profile_registry(profiles) == []
    assert all(item["runtime_write_status"] == "not_cut_over" for item in canonical["objects"])
    assert all(item["adapter_direction"] == "legacy_to_canonical" for item in mapping["mappings"])


def test_handoff_summary_proves_registry_coverage_without_runtime_claim() -> None:
    canonical, mapping, profiles = _payloads()

    summary = build_handoff_summary(ROOT, canonical, mapping, profiles)

    assert summary["status"] == "pass"
    assert summary["canonical_object_count"] >= 28
    assert summary["legacy_mapping_count"] >= summary["canonical_object_count"]
    assert summary["runtime_cutover_count"] == 0
    assert summary["boundaries"]["prd_or_tech_requirement_added"] is False
    assert summary["boundaries"]["runtime_write_path_changed"] is False


def test_test_profile_rules_isolate_known_non_hermetic_and_explicit_profiles() -> None:
    profiles = load_json(CONFIG_ROOT / "test_profile_registry_v0_1.json")

    local = classify_test_nodeid(
        "tests/test_multi_agent_specialist_llm.py::test_specialist_request_preserves_public_web_entity_binding_metadata",
        profiles,
    )
    full_chain = classify_test_nodeid(
        "tests/test_multi_agent_chain_performance_eval.py::test_multi_agent_chain_performance_fixture_schema",
        profiles,
    )
    ordinary = classify_test_nodeid("tests/test_engineering_handoff.py::test_example", profiles)

    assert local["profile"] == "local_data_integration"
    assert local["requirements"] == ["requires_local_data"]
    assert full_chain["profile"] == "full_chain"
    assert ordinary["profile"] == "fast_contract"
