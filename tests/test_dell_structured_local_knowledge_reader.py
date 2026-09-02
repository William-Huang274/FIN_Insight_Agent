from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from sec_agent.research_foundation.contracts import (
    bind_dell_research_method,
    load_dell_reference_vertical_foundation,
)
from sec_agent.research_foundation.data_ports import (
    LocalKnowledgeScope,
    StructuredLocalKnowledgeReader,
)


def _scope():
    return bind_dell_research_method(
        load_dell_reference_vertical_foundation(),
        ("Q1_ISSUER_TRUTH",),
        research_as_of=datetime(2026, 9, 2, tzinfo=timezone.utc),
        data_snapshot_id="DELL-STRUCTURED-READER-TEST-SNAPSHOT",
        execution_attempt_id="DELL-STRUCTURED-READER-TEST-A01",
    ).run_scope


def _section(node_id: str, *, route_id: str, fiscal_period: str) -> dict:
    return {
        "schema_version": "fin_ia_dell_structured_rag_node_v1_0",
        "node_id": node_id,
        "node_kind": "section",
        "candidate_is_not_evidence": True,
        "citation_eligible": False,
        "numeric_authority": False,
        "publication_date": "2026-08-01",
        "route_id": route_id,
        "fiscal_period": fiscal_period,
        "content": "section parent",
    }


def _leaf(
    node_id: str,
    *,
    parent_section_id: str,
    route_id: str,
    fiscal_period: str,
    content: str,
    section_chunk_index: int,
    page: int,
    lane: str = "prose_leaf",
    node_kind: str = "chunk",
) -> dict:
    return {
        "schema_version": "fin_ia_dell_structured_rag_node_v1_0",
        "node_id": node_id,
        "node_kind": node_kind,
        "lane": lane,
        "candidate_is_not_evidence": True,
        "citation_eligible": False,
        "numeric_authority": False,
        "issuer_id": "DELL",
        "ticker": "DELL",
        "company": "Dell Technologies Inc.",
        "fiscal_period": fiscal_period,
        "period_end": "2026-05-01" if fiscal_period == "FY2027_Q1" else "2026-07-31",
        "publication_date": "2026-08-01",
        "route_id": route_id,
        "source_role": "issuer_management_disclosure",
        "parent_document_id": "DOC::DELL",
        "parent_section_id": parent_section_id,
        "section_path": ["Dell earnings call", "Demand durability"],
        "section_chunk_index": section_chunk_index,
        "page_start": page,
        "page_end": page,
        "stable_url": "https://investors.delltechnologies.com/fixture",
        "raw_body_sha256": "a" * 64,
        "content": content,
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "model_text": (
            f"Issuer: DELL\nPeriod: {fiscal_period}\n"
            f"Source: {route_id}\nSection: Demand durability\n\n{content}"
        ),
    }


def _artifact(tmp_path: Path) -> tuple[Path, str, int]:
    q1_section = "SECTION::Q1"
    q2_section = "SECTION::Q2"
    rows = [
        _section(
            q1_section,
            route_id="dell_fy2027_q1_transcript",
            fiscal_period="FY2027_Q1",
        ),
        _section(
            q2_section,
            route_id="dell_fy2027_q2_transcript",
            fiscal_period="FY2027_Q2",
        ),
        _leaf(
            "CHUNK::PREVIOUS",
            parent_section_id=q1_section,
            route_id="dell_fy2027_q1_transcript",
            fiscal_period="FY2027_Q1",
            content="Customers made some advance purchases before component prices rose.",
            section_chunk_index=0,
            page=5,
        ),
        _leaf(
            "CHUNK::ANCHOR",
            parent_section_id=q1_section,
            route_id="dell_fy2027_q1_transcript",
            fiscal_period="FY2027_Q1",
            content=(
                "Management separated advance purchases from durable AI demand and "
                "said the installed-base refresh remains a multi-year driver."
            ),
            section_chunk_index=1,
            page=6,
        ),
        _leaf(
            "CHUNK::NEXT",
            parent_section_id=q1_section,
            route_id="dell_fy2027_q1_transcript",
            fiscal_period="FY2027_Q1",
            content="Share gains and Windows refresh supported the underlying demand view.",
            section_chunk_index=2,
            page=6,
        ),
        _leaf(
            "CHUNK::WRONGPERIOD",
            parent_section_id=q2_section,
            route_id="dell_fy2027_q2_transcript",
            fiscal_period="FY2027_Q2",
            content=(
                "advance purchases durable AI demand installed-base refresh "
                "multi-year driver"
            ),
            section_chunk_index=0,
            page=4,
        ),
        _leaf(
            "BLOCK::TABLE",
            parent_section_id=q1_section,
            route_id="dell_fy2027_q1_transcript",
            fiscal_period="FY2027_Q1",
            content="| Accounts receivable | (8,331) |",
            section_chunk_index=3,
            page=7,
            lane="table_leaf",
            node_kind="table",
        ),
    ]
    path = tmp_path / "retrieval_nodes.jsonl"
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
        encoding="utf-8",
    )
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), len(rows)


def test_structured_reader_prefilters_then_ranks_and_bounds_transcript_context(
    tmp_path: Path,
) -> None:
    path, digest, count = _artifact(tmp_path)
    reader = StructuredLocalKnowledgeReader(
        nodes_path=path,
        expected_sha256=digest,
        expected_node_count=count,
        research_as_of=date(2026, 9, 2),
        allowed_branch_ids=("Q1_ISSUER_TRUTH",),
    )
    result = reader(
        query="advance purchases durable AI demand installed base refresh",
        branch_id="Q1_ISSUER_TRUTH",
        limit=3,
        run_scope=_scope(),
        retrieval_scope=LocalKnowledgeScope(
            issuer_ids=("DELL",),
            fiscal_periods=("FY2027_Q1",),
            source_roles=("issuer_management_disclosure",),
            route_ids=("dell_fy2027_q1_transcript",),
            lanes=("prose_leaf",),
        ),
    )

    assert result.retrieval_strategy == "metadata_prefilter_bm25"
    assert result.metadata_prefilter_applied is True
    assert result.physical_record_count == count
    assert result.visible_record_count == 5
    assert result.eligible_candidate_count == 3
    assert result.candidates[0].source_record_id == "CHUNK::ANCHOR"
    assert result.candidates[0].delivered_context_node_ids == (
        "CHUNK::PREVIOUS",
        "CHUNK::ANCHOR",
        "CHUNK::NEXT",
    )
    assert "CHUNK::WRONGPERIOD" not in result.candidates[0].delivered_context
    assert result.candidates[0].candidate_is_not_evidence is True
    assert result.candidates[0].citation_eligible is False
    assert result.candidates[0].numeric_authority is False
    assert result.candidates[0].structured_document_tree is True
    assert result.candidates[0].legacy_read_only_bridge is False


def test_structured_reader_exact_route_and_lane_gates_fail_to_empty_not_substitute(
    tmp_path: Path,
) -> None:
    path, digest, count = _artifact(tmp_path)
    reader = StructuredLocalKnowledgeReader(
        nodes_path=path,
        expected_sha256=digest,
        expected_node_count=count,
        research_as_of=date(2026, 9, 2),
        allowed_branch_ids=("Q1_ISSUER_TRUTH",),
    )
    missing = reader(
        query="orders conversion supply pricing",
        branch_id="Q1_ISSUER_TRUTH",
        limit=3,
        run_scope=_scope(),
        retrieval_scope={
            "issuer_ids": ["DELL"],
            "source_roles": ["issuer_management_disclosure"],
            "route_ids": ["dell_fy2027_q1_performance_review"],
        },
    )
    assert missing.eligible_candidate_count == 0
    assert missing.candidates == ()

    table = reader(
        query="accounts receivable",
        branch_id="Q1_ISSUER_TRUTH",
        limit=3,
        run_scope=_scope(),
        retrieval_scope={
            "issuer_ids": ["DELL"],
            "fiscal_periods": ["FY2027_Q1"],
            "source_roles": ["issuer_management_disclosure"],
            "lanes": ["table_leaf"],
        },
    )
    assert [row.source_record_id for row in table.candidates] == ["BLOCK::TABLE"]
    assert table.candidates[0].delivered_context_node_ids == ("BLOCK::TABLE",)


def test_structured_reader_canonicalizes_lowercase_issuer_scope(
    tmp_path: Path,
) -> None:
    path, digest, count = _artifact(tmp_path)
    reader = StructuredLocalKnowledgeReader(
        nodes_path=path,
        expected_sha256=digest,
        expected_node_count=count,
        research_as_of=date(2026, 9, 2),
        allowed_branch_ids=("Q1_ISSUER_TRUTH",),
    )
    result = reader(
        query="accounts receivable",
        branch_id="Q1_ISSUER_TRUTH",
        limit=2,
        run_scope=_scope(),
        retrieval_scope={
            "issuer_ids": ["dell"],
            "source_roles": ["issuer_management_disclosure"],
            "lanes": ["table_leaf"],
        },
    )

    assert result.retrieval_scope.issuer_ids == ("DELL",)
    assert [row.source_record_id for row in result.candidates] == ["BLOCK::TABLE"]


def test_structured_reader_rejects_digest_drift(tmp_path: Path) -> None:
    path, _digest, count = _artifact(tmp_path)
    with pytest.raises(ValueError, match="structured_local_nodes_digest_drift"):
        StructuredLocalKnowledgeReader(
            nodes_path=path,
            expected_sha256="0" * 64,
            expected_node_count=count,
            research_as_of=date(2026, 9, 2),
            allowed_branch_ids=("Q1_ISSUER_TRUTH",),
        )
