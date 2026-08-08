from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_supplemental_assets import (  # noqa: E402
    FederatedReadOnlyRetriever,
    deterministic_text_chunks,
    load_internal_supplemental_asset_policy,
)
from indexing.build_object_bm25_index import compact_structured_object_record  # noqa: E402


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_supplemental_asset_policy_v1_0.json"
)
POLICY_V1_1_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_supplemental_asset_policy_v1_1.json"
)


class FakeRetriever:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.closed = False

    def search(self, query: str, top_k: int, filters: dict | None) -> list[dict]:
        return self.rows[:top_k]

    def close(self) -> None:
        self.closed = True


def test_policy_binds_acquisition_result_and_preserves_candidate_boundary() -> None:
    policy = load_internal_supplemental_asset_policy(POLICY_PATH, repo_root=ROOT)
    assert len(policy["source_bindings"]) == 3
    assert policy["hard_boundaries"]["network"] == 0
    assert policy["hard_boundaries"]["embedding"] == 0
    assert policy["hard_boundaries"]["candidate_may_be_promoted_to_evidence"] is False
    mu = next(item for item in policy["source_bindings"] if item["ticker"] == "MU")
    assert mu["accepted_source_refs"] == ["SRC_MU_Q3_FY26_RESULTS"]
    assert mu["uncovered_source_refs"] == ["SRC_MU_Q3_FY26_REMARKS"]


def test_successor_policy_preserves_lineage_in_compact_object_records() -> None:
    policy = load_internal_supplemental_asset_policy(
        POLICY_V1_1_PATH, repo_root=ROOT
    )
    assert policy["private_output_root"].endswith("/v2")
    record = compact_structured_object_record(
        {
            "object_id": "object-1",
            "object_type": "claim",
            "source_evidence_id": "evidence-1",
            "claim_text": "current official result",
            "ticker": "MU",
            "fiscal_year": 2026,
            "form_type": "8-K",
            "published_at": "2026-06-24",
            "source_url": "https://www.sec.gov/example",
            "accession_number": "0000723125-26-000013",
            "metadata": {
                "filing_date": "2026-06-24",
                "source_url": "https://www.sec.gov/example",
                "accession_number": "0000723125-26-000013",
            },
        }
    )
    assert record["published_at"] == "2026-06-24"
    assert record["source_url"] == "https://www.sec.gov/example"
    assert record["accession_number"] == "0000723125-26-000013"


def test_chunking_is_deterministic_bounded_and_overlapping() -> None:
    text = " ".join(f"token{i:04d}" for i in range(1000))
    first = deterministic_text_chunks(
        text,
        target_chars=1800,
        minimum_chars=1000,
        maximum_chars=2200,
        overlap_chars=250,
    )
    second = deterministic_text_chunks(
        text,
        target_chars=1800,
        minimum_chars=1000,
        maximum_chars=2200,
        overlap_chars=250,
    )
    assert first == second
    assert len(first) > 1
    assert all(len(item) <= 2200 for item in first)
    assert set(first[0].split()[-10:]) & set(first[1].split()[:40])


def test_federation_round_robins_assets_without_cross_score_comparison() -> None:
    base = FakeRetriever(
        [
            {"evidence_id": "base-1", "score": 100.0, "record": {"evidence_id": "base-1"}},
            {"evidence_id": "shared", "score": 90.0, "record": {"evidence_id": "shared"}},
        ]
    )
    supplemental = FakeRetriever(
        [
            {"evidence_id": "supp-1", "score": 1.0, "record": {"evidence_id": "supp-1"}},
            {"evidence_id": "shared", "score": 0.5, "record": {"evidence_id": "shared"}},
        ]
    )
    federated = FederatedReadOnlyRetriever(
        [("base", base), ("supplemental", supplemental)]
    )
    rows = federated.search("query", top_k=3, filters={"ticker": "MU"})
    assert [row["evidence_id"] for row in rows] == ["base-1", "supp-1", "shared"]
    assert [row["retrieval_asset_id"] for row in rows] == [
        "base",
        "supplemental",
        "base",
    ]
    federated.close()
    assert base.closed and supplemental.closed
