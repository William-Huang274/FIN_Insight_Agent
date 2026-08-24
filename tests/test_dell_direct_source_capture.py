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
    DELL_DIRECT_SOURCE_SHORTLIST_SCHEMA_VERSION,
    DirectSourceCaptureError,
    compile_dell_direct_source_shortlist,
    validate_dell_direct_source_capture_plan,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from scripts.data_retrieval.run_dell_external_source_ladder import (  # noqa: E402
    _compile_original_capture_plan,
)


PLAN = (
    ROOT
    / "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_direct_source_capture_plan_v1_0.json"
)


def _plan() -> dict[str, object]:
    return json.loads(PLAN.read_text(encoding="utf-8"))


def _redigest(value: dict[str, object]) -> dict[str, object]:
    body = deepcopy(value)
    body.pop("plan_digest", None)
    body["plan_digest"] = canonical_digest(body)
    return body


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
