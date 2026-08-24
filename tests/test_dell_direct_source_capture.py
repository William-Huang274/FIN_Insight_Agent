from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.direct_source_capture import (  # noqa: E402
    DELL_DIRECT_SOURCE_CAPTURE_PLAN_SCHEMA_VERSION,
    DELL_DIRECT_SOURCE_CAPTURE_SUCCESSOR_PLAN_SCHEMA_VERSION,
    DELL_DIRECT_SOURCE_SHORTLIST_SCHEMA_VERSION,
    DirectSourceCaptureError,
    compile_dell_direct_source_capture_successor,
    compile_dell_direct_source_shortlist,
    validate_dell_direct_source_capture_plan,
    validate_dell_direct_source_capture_successor_plan,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from scripts.data_retrieval.run_dell_external_source_ladder import (  # noqa: E402
    _compile_original_capture_plan,
)
from scripts.data_retrieval.replay_dell_direct_source_compilation import (  # noqa: E402
    validate_replay_plan,
)


PLAN = (
    ROOT
    / "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_direct_source_capture_plan_v1_0.json"
)
SUCCESSOR_PLAN = (
    ROOT
    / "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_direct_source_capture_successor_plan_v1_0.json"
)
REPLAY_PLAN = (
    ROOT
    / "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_direct_source_compilation_replay_plan_v1_1.json"
)


def _plan() -> dict[str, object]:
    return json.loads(PLAN.read_text(encoding="utf-8"))


def _redigest(value: dict[str, object]) -> dict[str, object]:
    body = deepcopy(value)
    body.pop("plan_digest", None)
    body["plan_digest"] = canonical_digest(body)
    return body


def _successor_plan() -> dict[str, object]:
    return json.loads(SUCCESSOR_PLAN.read_text(encoding="utf-8"))


def _predecessor_terminal(plan: dict[str, object]) -> dict[str, object]:
    shortlist = compile_dell_direct_source_shortlist(plan)
    failed = next(
        row
        for row in shortlist["selected"]
        if row["direct_source_id"]
        == "DELL-DIRECT-DELL-NVIDIA-NEWSROOM-2025"
    )
    body = {
        "attempt_id": "fixture-r1",
        "plan_binding": {"plan_digest": plan["plan_digest"]},
        "fetch_shortlist": shortlist,
        "original_compilation_result": {
            "route_receipts": [
                {
                    "canonical_url": failed["canonical_url"],
                    "capture_failure_code": "official_source_http_403",
                }
            ]
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


def test_direct_plan_compiles_five_zero_provider_original_routes() -> None:
    plan = validate_dell_direct_source_capture_plan(_plan())
    shortlist = compile_dell_direct_source_shortlist(plan)
    original_plan = _compile_original_capture_plan(
        plan=plan,
        shortlist=shortlist,
    )

    assert plan["schema_version"] == (
        DELL_DIRECT_SOURCE_CAPTURE_PLAN_SCHEMA_VERSION
    )
    assert plan["execution_budget"]["provider_call_ceiling"] == 0
    assert shortlist["schema_version"] == (
        DELL_DIRECT_SOURCE_SHORTLIST_SCHEMA_VERSION
    )
    assert shortlist["summary"] == {
        "reviewed_direct_locator_count": 5,
        "selected_original_fetch_count": 5,
        "provider_call_count": 0,
        "provider_result_count": 0,
        "candidate_evidence_promotions": 0,
    }
    assert len(original_plan["sources"]) == 5
    assert len(
        {row["canonical_url"] for row in shortlist["selected"]}
    ) == 5
    assert all(
        row["provider_result_is_locator_only"] is True
        and row["candidate_not_evidence"] is True
        and row["numeric_authority"] == "none"
        for row in shortlist["selected"]
    )
    assert all(
        row["transport"] == "requests"
        and row["max_transport_retries"] == 0
        for row in original_plan["sources"]
    )


def test_direct_plan_rejects_provider_or_duplicate_url_scope_expansion() -> None:
    provider_mutation = _plan()
    provider_mutation["execution_budget"]["provider_call_ceiling"] = 1
    with pytest.raises(
        DirectSourceCaptureError,
        match="direct_source_capture_plan_shape_invalid",
    ):
        validate_dell_direct_source_capture_plan(
            _redigest(provider_mutation)
        )

    duplicate_mutation = _plan()
    duplicate_mutation["direct_sources"][1]["canonical_url"] = (
        duplicate_mutation["direct_sources"][0]["canonical_url"]
    )
    with pytest.raises(
        DirectSourceCaptureError,
        match="direct_source_locator_invalid",
    ):
        validate_dell_direct_source_capture_plan(
            _redigest(duplicate_mutation)
        )


def test_direct_relationship_sources_are_bidirectional_and_non_authoritative() -> None:
    plan = validate_dell_direct_source_capture_plan(_plan())
    shortlist = compile_dell_direct_source_shortlist(plan)
    relationship_rows = [
        row
        for row in shortlist["selected"]
        if row["query_unit_id"] == "DELL-DIRECT-CURRENT-RELATIONSHIP"
    ]

    assert {row["source_registry"]["speaker_ticker"] for row in relationship_rows} == {
        "DELL",
        "NVDA",
    }
    assert len(relationship_rows) == 2
    assert plan["authority"]["candidate_is_not_evidence"] is True
    assert plan["authority"]["public_information_gap_authorized"] is False
    assert plan["authority"]["S1_qualification_authorized"] is False


def test_failed_route_successor_replaces_only_dell_403_locator() -> None:
    predecessor = validate_dell_direct_source_capture_plan(_plan())
    terminal = _predecessor_terminal(predecessor)
    successor = _successor_plan()
    successor["predecessor_terminal_binding"]["result_digest"] = terminal[
        "result_digest"
    ]
    successor["predecessor_terminal_binding"]["attempt_id"] = terminal[
        "attempt_id"
    ]
    successor = _redigest(successor)

    effective, receipt = compile_dell_direct_source_capture_successor(
        successor_plan=successor,
        predecessor_plan=predecessor,
        predecessor_terminal=terminal,
    )

    assert successor["schema_version"] == (
        DELL_DIRECT_SOURCE_CAPTURE_SUCCESSOR_PLAN_SCHEMA_VERSION
    )
    assert len(receipt["unchanged_urls"]) == 4
    assert receipt["retired_failed_urls"] == [
        "https://www.dell.com/en-us/dt/corporate/newsroom/announcements/"
        "detailpage.press-releases~usa~2025~03~corp.htm"
    ]
    assert receipt["fresh_urls"] == [
        "https://investors.delltechnologies.com/node/17471/pdf"
    ]
    assert receipt["expected_fresh_network_routes"] == 1
    assert any(
        row["source_family_id"] == "delltechnologies.com"
        and row["speaker_ticker"] == "DELL"
        for row in effective["source_registry"]
    )
    assert len(effective["direct_sources"]) == 5


def test_failed_route_successor_rejects_same_url_retry() -> None:
    successor = _successor_plan()
    successor["replacement_direct_source"]["canonical_url"] = successor[
        "failed_route_binding"
    ]["canonical_url"]

    with pytest.raises(
        DirectSourceCaptureError,
        match="direct_source_capture_successor_plan_shape_invalid",
    ):
        validate_dell_direct_source_capture_successor_plan(
            _redigest(successor)
        )


def test_compilation_replay_plan_is_zero_network_and_capture_bound() -> None:
    plan = validate_replay_plan(
        json.loads(REPLAY_PLAN.read_text(encoding="utf-8"))
    )

    assert plan["execution_budget"] == {
        "network_call_ceiling": 0,
        "provider_call_ceiling": 0,
        "model_call_ceiling": 0,
        "generation_call_ceiling": 0,
        "capture_reuse_count_required": 5,
    }
    assert {
        (row["source_url"], row["successor_publication_date"])
        for row in plan["expected_corrections"]
    } == {
        (
            "https://investors.delltechnologies.com/node/17471/pdf",
            "2025-03-18",
        ),
        (
            "https://www.mississippi.edu/sites/default/files/ihl/files/"
            "February%202025%20Board%20Book.pdf",
            "2025-02-20",
        ),
    }
    assert plan["expected_unchanged_source_object_count"] == 3
    assert plan["authority"]["predecessor_source_objects_reusable"] is False
    assert plan["authority"]["predecessor_raw_captures_reusable"] is True


def test_compilation_replay_plan_rejects_network_authority() -> None:
    plan = json.loads(REPLAY_PLAN.read_text(encoding="utf-8"))
    plan["execution_budget"]["network_call_ceiling"] = 1

    with pytest.raises(
        ValueError,
        match="dell_direct_source_compilation_replay_plan_shape_invalid",
    ):
        validate_replay_plan(_redigest(plan))
