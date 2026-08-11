from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (
    load_current_fin_0_1_2_s4_t01_case_entry,
)
from apps.workbench.backend.application.fin_0_1_2_s4_retrieval_evidence_readiness import (
    EXPECTED_CASES,
    EXPECTED_CELLS,
    Fin012S4T02ReadinessError,
    compile_fin_0_1_2_s4_t02_case_readiness,
    load_current_fin_0_1_2_s4_t02_readiness,
    load_current_fin_0_1_2_s4_t02_three_case_readiness,
    load_fin_0_1_2_s4_t02_authority_and_resources,
)
from sec_agent.runtime_resource_registry import read_registered_runtime_json


REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_2_s4_t02_runtime_resource_registry_v1_0.json"
)
INDEX_RESOURCE_ID = "fin_0_1_2.s4.t02.index_snapshot.public_source_summary"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _source_and_index(case_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    authority, _ = load_fin_0_1_2_s4_t02_authority_and_resources()
    case = next(row for row in authority["cases"] if row["case_key"] == case_key)
    source = read_registered_runtime_json(
        ROOT,
        case["source_resource_id"],
        registry_ref=REGISTRY_REF,
    )
    index = read_registered_runtime_json(
        ROOT,
        INDEX_RESOURCE_ID,
        registry_ref=REGISTRY_REF,
    )
    return source, index


def _compile(
    case_key: str,
    *,
    authority: Mapping[str, Any] | None = None,
    source: Mapping[str, Any] | None = None,
    index: Mapping[str, Any] | None = None,
):
    current_authority, resources = load_fin_0_1_2_s4_t02_authority_and_resources()
    current_source, current_index = _source_and_index(case_key)
    return compile_fin_0_1_2_s4_t02_case_readiness(
        authority=authority or current_authority,
        resources_by_id=resources,
        case_entry=load_current_fin_0_1_2_s4_t01_case_entry(case_key),
        source_payload=source or current_source,
        index_payload=index or current_index,
    )


def _rebind_authority(authority: dict[str, Any]) -> dict[str, Any]:
    authority["authority_digest"] = _digest(
        {key: value for key, value in authority.items() if key != "authority_digest"}
    )
    return authority


def _all_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        keys.update(str(key) for key in value)
        for child in value.values():
            keys.update(_all_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            keys.update(_all_keys(child))
    return keys


def test_current_runtime_compiles_all_three_cases_without_execution() -> None:
    results = load_current_fin_0_1_2_s4_t02_three_case_readiness()
    assert tuple(row.receipt.case_key for row in results) == EXPECTED_CASES
    assert all(len(row.evidence_requests) == len(EXPECTED_CELLS) for row in results)
    assert all(len(row.route_plans) == len(EXPECTED_CELLS) for row in results)
    assert all(
        plan.planned_external_calls == 0
        and set(plan.invocation_statuses) == {"not_executed"}
        for row in results
        for plan in row.route_plans
    )
    assert all(row.receipt.promoted_evidence_count == 0 for row in results)
    assert all(row.receipt.T03_authorized is False for row in results)
    assert all(set(row.receipt.observed_counts.values()) == {0} for row in results)


def test_historical_dell_mu_are_readiness_only_and_nvda_is_typed_current_gap() -> None:
    dell, mu, nvda = load_current_fin_0_1_2_s4_t02_three_case_readiness()
    assert (
        dell.receipt.accepted_candidate_count,
        dell.receipt.rejected_candidate_count,
        dell.receipt.citation_count,
    ) == (2, 8, 2)
    assert (
        mu.receipt.accepted_candidate_count,
        mu.receipt.rejected_candidate_count,
        mu.receipt.citation_count,
    ) == (13, 1, 13)
    assert (
        nvda.receipt.accepted_candidate_count,
        nvda.receipt.rejected_candidate_count,
        nvda.receipt.citation_count,
    ) == (0, 0, 0)
    assert set(nvda.receipt.typed_gap_codes) == {
        "current_counterevidence_search_required",
        "current_demand_evidence_search_required",
        "current_value_evidence_search_required",
    }
    assert all(
        decision.current_evidence_authorized is False
        for result in (dell, mu, nvda)
        for decision in result.candidate_decisions
    )


def test_output_retains_citation_metadata_but_not_source_content_or_numeric_values() -> None:
    output = load_current_fin_0_1_2_s4_t02_readiness("MU").as_dict()
    keys = _all_keys(output)
    assert not {
        "statement",
        "value",
        "normalized_extract",
        "full_document_sha256",
        "numeric_rows",
        "evidence_rows",
    }.intersection(keys)
    citations = output["CitationProjections"]
    assert citations
    assert all(row["source_url"].startswith("https://") for row in citations)
    assert all(row["locator"] and row["writer_citable"] is False for row in citations)


def test_t01_source_and_index_bindings_are_consumed_exactly() -> None:
    result = load_current_fin_0_1_2_s4_t02_readiness("DELL")
    t01 = load_current_fin_0_1_2_s4_t01_case_entry("DELL")
    assert result.receipt.t01_entry_digest == t01.receipt.entry_digest
    assert result.receipt.source_resource["sha256"] == t01.snapshot_binding.source_snapshot["sha256"]
    assert result.receipt.index_resource["sha256"] == t01.snapshot_binding.index_snapshot["sha256"]
    assert result.receipt.source_freshness_disposition == (
        "historical_exact_as_of_match_not_current_evidence"
    )
    assert result.receipt.index_freshness_disposition == (
        "catalog_reachable_snapshot_stale_for_current_case_evidence"
    )


def test_replay_and_source_collection_permutations_are_digest_stable() -> None:
    first = _compile("MU")
    source, index = _source_and_index("MU")
    permuted = deepcopy(source)
    for key in ("source_snapshots", "route_execution_receipts", "evidence_rows", "typed_gaps"):
        permuted[key] = list(reversed(permuted[key]))
    second = _compile("MU", source=permuted, index=index)
    assert first.receipt.readiness_digest == second.receipt.readiness_digest
    assert [row.as_dict() for row in first.candidate_decisions] == [
        row.as_dict() for row in second.candidate_decisions
    ]


def test_cross_case_source_pack_contamination_fails_closed() -> None:
    source, index = _source_and_index("DELL")
    mutated = deepcopy(source)
    mutated["case_ticker"] = "MU"
    with pytest.raises(
        Fin012S4T02ReadinessError,
        match="s4_t02_source_pack_cross_case_contamination",
    ):
        _compile("DELL", source=mutated, index=index)


def test_row_level_cross_case_contamination_fails_closed() -> None:
    source, index = _source_and_index("MU")
    mutated = deepcopy(source)
    mutated["evidence_rows"][0]["entity_ref"] = "DELL"
    with pytest.raises(
        Fin012S4T02ReadinessError,
        match="s4_t02_source_pack_cross_case_contamination",
    ):
        _compile("MU", source=mutated, index=index)


def test_missing_citation_is_rejected_and_never_promoted() -> None:
    source, index = _source_and_index("MU")
    mutated = deepcopy(source)
    target = mutated["evidence_rows"][0]["evidence_ref"]
    mutated["evidence_rows"][0]["citation"] = ""
    result = _compile("MU", source=mutated, index=index)
    decisions = [row for row in result.candidate_decisions if row.candidate_id == target]
    assert decisions
    assert all(row.decision == "rejected" for row in decisions)
    assert all("citation_locator_missing" in row.decision_codes for row in decisions)
    assert all(row.current_evidence_authorized is False for row in decisions)


def test_unknown_parser_snapshot_is_rejected_with_typed_reason() -> None:
    source, index = _source_and_index("DELL")
    mutated = deepcopy(source)
    target = mutated["evidence_rows"][0]["evidence_ref"]
    mutated["evidence_rows"][0]["parser_lineage"]["source_snapshot_ref"] = "unknown"
    result = _compile("DELL", source=mutated, index=index)
    decisions = [row for row in result.candidate_decisions if row.candidate_id == target]
    assert decisions
    assert all(row.decision == "rejected" for row in decisions)
    assert all(row.decision_codes == ("source_snapshot_unbound",) for row in decisions)


def test_required_public_index_route_absence_fails_closed() -> None:
    source, index = _source_and_index("NVDA")
    mutated = deepcopy(index)
    mutated["successful_sources"].remove("sec_edgar_apis")
    with pytest.raises(
        Fin012S4T02ReadinessError,
        match="s4_t02_index_required_route_unreachable",
    ):
        _compile("NVDA", source=source, index=mutated)


def test_source_pack_as_of_drift_fails_closed() -> None:
    source, index = _source_and_index("DELL")
    mutated = deepcopy(source)
    mutated["as_of"] = "2026-07-25T00:00:00Z"
    with pytest.raises(
        Fin012S4T02ReadinessError,
        match="s4_t02_source_pack_as_of_mismatch",
    ):
        _compile("DELL", source=mutated, index=index)


def test_candidate_ceiling_is_explicit_and_overflow_is_rejected() -> None:
    authority, _ = load_fin_0_1_2_s4_t02_authority_and_resources()
    mutated = deepcopy(authority)
    mutated["candidate_policy"]["per_request_candidate_ceiling"] = 1
    mutated["candidate_policy"]["per_case_candidate_ceiling"] = 3
    _rebind_authority(mutated)
    result = _compile("MU", authority=mutated)
    assert result.receipt.accepted_candidate_count <= 3
    assert any(
        "candidate_ceiling_exceeded_fixture_only" in row.decision_codes
        for row in result.candidate_decisions
    )


def test_route_cell_contract_mutation_fails_closed() -> None:
    authority, _ = load_fin_0_1_2_s4_t02_authority_and_resources()
    mutated = deepcopy(authority)
    mutated["route_profiles"][0]["program_cell_id"] = "unknown_cell"
    _rebind_authority(mutated)
    with pytest.raises(
        Fin012S4T02ReadinessError,
        match="s4_t02_route_cell_set_invalid",
    ):
        _compile("DELL", authority=mutated)


def test_false_promotion_authority_mutation_fails_closed() -> None:
    authority, _ = load_fin_0_1_2_s4_t02_authority_and_resources()
    mutated = deepcopy(authority)
    mutated["nonpromotion_boundary"]["writer_citable"] = True
    _rebind_authority(mutated)
    with pytest.raises(
        Fin012S4T02ReadinessError,
        match="s4_t02_false_promotion_boundary_invalid",
    ):
        _compile("MU", authority=mutated)


def test_unknown_case_fails_closed() -> None:
    with pytest.raises(Fin012S4T02ReadinessError, match="s4_t02_case_unknown"):
        load_current_fin_0_1_2_s4_t02_readiness("AMD")
