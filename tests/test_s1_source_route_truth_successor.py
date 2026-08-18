from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from ingestion.source_intake import SourceIntakePolicy, SourceIntakeStore
from retrieval.query_plan import canonical_digest
from retrieval.source_route_dispatch import SourceRouteDispatchError
from scripts.data_retrieval.materialize_s1_source_route_truth_successor import (
    build_source_route_truth_successor,
)


SOURCE_ROUTE_POLICY = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_source_route_portfolio_policy_v1_0.json"
)
SOURCE_INTAKE_POLICY = (
    ROOT / "configs/retrieval/fin_ia_0_1_3_s1d_source_intake_policy_v1_0.json"
)
REPLAYS = {
    "DELL": ROOT
    / "data/workbench_private/fin_0_1_3_s1_material_scope_product_replay/dell-r4-current/full_result.json",
    "MU": ROOT
    / "data/workbench_private/fin_0_1_3_s1_candidate_provenance_replay/mu-successor-r5/full_result.json",
    "NVDA": ROOT
    / "data/workbench_private/fin_0_1_3_s1_candidate_provenance_replay/nvda-successor-r5/full_result.json",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _compile(case_key: str, predecessor: dict | None = None) -> dict:
    intake_policy = SourceIntakePolicy.from_path(SOURCE_INTAKE_POLICY)
    attempts = SourceIntakeStore(
        ROOT / "data/workbench_private/source_intake", intake_policy
    ).list_attempts(limit=1000)
    return build_source_route_truth_successor(
        predecessor=predecessor or _read(REPLAYS[case_key]),
        source_route_policy=_read(SOURCE_ROUTE_POLICY),
        source_intake_policy=intake_policy,
        source_intake_attempts=attempts,
        recorded_at="2026-08-19T00:00:00+00:00",
        prepared_from_commit="a" * 40,
        source_bindings={},
    )


def test_three_case_source_truth_replay_separates_complete_from_unexecuted_routes() -> None:
    expected_incomplete = {"DELL": 0, "MU": 4, "NVDA": 3}
    for case_key, incomplete_count in expected_incomplete.items():
        result = _compile(case_key)
        summary = result["product_projection"]["summary"][
            "source_route_execution"
        ]
        assert result["case_key"] == case_key
        assert summary["candidate_coverage_state_counts"].get("incomplete", 0) == (
            incomplete_count
        )
        assert summary["supplement_route_required_request_count"] == incomplete_count
        assert (
            summary[
                "official_or_external_supplement_route_exhausted_request_count"
            ]
            == 0
        )
        assert summary["public_information_gap_eligible_request_count"] == 0
        assert result["execution_summary"]["network_calls"] == 0
        assert result["execution_summary"]["model_calls"] == 0
        assert result["execution_summary"]["vector_calls"] == 0


def test_source_truth_successor_rejects_cross_case_query_plan_mutation() -> None:
    predecessor = deepcopy(_read(REPLAYS["MU"]))
    projection = predecessor["product_projection"]
    projection["request_results"][0]["query_plan"]["case_key"] = "NVDA"
    projection_body = dict(projection)
    projection_body.pop("projection_digest")
    projection["projection_digest"] = canonical_digest(projection_body)
    predecessor_body = dict(predecessor)
    predecessor_body.pop("result_digest")
    predecessor["result_digest"] = canonical_digest(predecessor_body)

    with pytest.raises(
        SourceRouteDispatchError,
        match="source_route_query_plan_identity_mismatch",
    ):
        _compile("MU", predecessor)
