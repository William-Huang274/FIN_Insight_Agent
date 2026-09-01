from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from sec_agent.research_foundation.data_ports import (
    CompanyFinancialFactQuery,
    CurrentReviewedEvidenceReader,
    ExistingS2FinancialFactReader,
    FrozenLegacyLocalKnowledgeReader,
)
from sec_agent.research_foundation.contracts import (
    DEFAULT_DELL_REFERENCE_VERTICAL_FOUNDATION_PATH,
    bind_dell_research_method,
    load_dell_reference_vertical_foundation,
)
import sec_agent.research_foundation.data_ports as data_ports_module
from sec_agent.runtime_bridge.paths import resolve_runtime_paths


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.local_data_integration
_LOCAL_ASSETS = (
    ROOT
    / "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v5/records.jsonl",
    ROOT
    / "data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/v1/company_financial_facts.sqlite",
)
if not all(path.is_file() for path in _LOCAL_ASSETS):
    pytest.skip("current DELL local data mounts are unavailable", allow_module_level=True)


def _runtime_paths():
    return resolve_runtime_paths(ROOT)


def _evidence_reader() -> CurrentReviewedEvidenceReader:
    paths = _runtime_paths()
    service = ResearchEvidencePackService.from_runtime_paths(ROOT, paths)
    principal = ResearchEvidencePackPrincipal(
        "current", frozenset({"current_product:read"})
    )
    return CurrentReviewedEvidenceReader(
        case_reader=lambda case_key: service.get_case(case_key, principal)
    )


def _scope(*branch_ids: str):
    return bind_dell_research_method(
        load_dell_reference_vertical_foundation(),
        branch_ids,
        research_as_of=datetime(2026, 9, 2, tzinfo=timezone.utc),
        data_snapshot_id="DELL-FOUNDATION-REAL-DATA-SNAPSHOT-01",
        execution_attempt_id="DELL-DATA-PORT-TEST-A01",
    ).run_scope


def test_id_based_evidence_reader_returns_only_requested_reviewed_rows() -> None:
    reader = _evidence_reader()
    # First read a deliberately missing ID to prove a miss is typed, not a gap.
    scope = _scope("Q1_ISSUER_TRUTH")
    missing = reader(
        evidence_ids=("EV::DOESNOTEXIST00",),
        branch_id="Q1_ISSUER_TRUTH",
        run_scope=scope,
    )
    assert missing["evidence"] == ()
    assert missing["missing_evidence_ids"] == ("EV::DOESNOTEXIST00",)
    assert missing["missing_id_is_not_public_information_gap"] is True

    # Derive one current stable ID from the service-owned identity surface.
    from sec_agent.research.reviewed_evidence_pack import canonical_digest

    case = reader.case_reader("DELL")
    item = case["evidence_items"][0]
    evidence_id = "EV::" + canonical_digest(
        {
            "case_key": "DELL",
            "target_id": item["target_id"],
            "evidence_item_digest": item["evidence_item_digest"],
        }
    )[:16].upper()

    result = reader(
        evidence_ids=(evidence_id,),
        branch_id="Q1_ISSUER_TRUTH",
        run_scope=scope,
    )
    assert result["authority_state"] == "reviewed_evidence_read"
    assert [row["evidence_id"] for row in result["evidence"]] == [evidence_id]
    assert result["evidence"][0]["writer_citable"] is True
    assert len(result["evidence"][0]["bounded_excerpt"]) <= 1_200
    assert result["candidate_promotion_performed"] is False
    assert "cell_id" not in result

    discovered = reader.search(
        query="Dell AI optimized server revenue backlog",
        branch_id="Q1_ISSUER_TRUTH",
        limit=4,
        run_scope=scope,
    )
    assert discovered.hits
    assert all(row.requires_id_read_before_citation for row in discovered.hits)
    assert discovered.candidate_promotion_performed is False


def test_evidence_reader_fails_closed_on_duplicate_id_or_non_citable_row() -> None:
    current = _evidence_reader()
    case = current.case_reader("DELL")
    rows = list(case["evidence_items"])
    scope = _scope("Q1_ISSUER_TRUTH")

    duplicate_reader = CurrentReviewedEvidenceReader(
        case_reader=lambda _case_key: {
            **case,
            "evidence_items": [*rows, dict(rows[0])],
        }
    )
    with pytest.raises(ValueError, match="reviewed_evidence_id_duplicate"):
        duplicate_reader(
            evidence_ids=("EV::DOESNOTEXIST00",),
            branch_id="Q1_ISSUER_TRUTH",
            run_scope=scope,
        )

    non_citable = {**rows[0], "writer_citable": False}
    boundary_reader = CurrentReviewedEvidenceReader(
        case_reader=lambda _case_key: {
            **case,
            "evidence_items": [non_citable, *rows[1:]],
        }
    )
    with pytest.raises(ValueError, match="reviewed_evidence_not_writer_citable"):
        boundary_reader.search(
            query="Dell AI server revenue",
            branch_id="Q1_ISSUER_TRUTH",
            limit=4,
            run_scope=scope,
        )


def test_generic_s2_reader_resolves_multiple_metrics_without_cell_binding() -> None:
    paths = _runtime_paths()
    reader = ExistingS2FinancialFactReader(paths.company_financial_fact_mart_path)
    result = reader(
        request={
            "ticker": "dell",
            "metric_ids": ["revenue", "gross_profit"],
            "research_as_of": "2026-06-24",
            "period_start": "2026-01-31",
            "period_end": "2026-05-01",
            "fiscal_years": [2027],
            "granularity": "quarter_discrete",
        },
        branch_id="Q1_ISSUER_TRUTH",
        run_scope=_scope("Q1_ISSUER_TRUTH"),
    )

    assert result["authority_state"] == "s2_numeric_fact_query_result"
    assert result["resolved_metric_count"] == 2
    assert result["typed_gap_count"] == 0
    assert result["read_only"] is True
    assert result["narrative_numeric_fallback_performed"] is False
    assert "cell_id" not in result["query"]
    assert result.fact_mart_sha256_before == result.fact_mart_sha256_after
    assert all(
        fact["numeric_fact_authority"] is True
        for row in result["results"]
        for fact in row["facts"]
    )


def test_unknown_metric_stays_a_typed_s2_gap() -> None:
    paths = _runtime_paths()
    reader = ExistingS2FinancialFactReader(paths.company_financial_fact_mart_path)
    result = reader(
        request={
            "ticker": "DELL",
            "metric_ids": ["company_ai_server_units"],
            "research_as_of": "2026-06-24",
            "period_end": "2026-05-01",
            "granularity": "quarter_discrete",
        },
        branch_id="Q3_UNITS_ASP_PVM",
        run_scope=_scope("Q3_UNITS_ASP_PVM"),
    )
    assert result["resolved_metric_count"] == 0
    assert result["typed_gap_count"] == 1
    assert (
        result["results"][0]["typed_gap"]["gap_code"]
        == "metric_not_in_company_fact_mart"
    )


def test_fact_query_rejects_future_period_and_duplicate_metrics() -> None:
    with pytest.raises(ValidationError, match="financial_fact_period_after_research_as_of"):
        CompanyFinancialFactQuery.model_validate(
            {
                "ticker": "DELL",
                "metric_ids": ["revenue"],
                "research_as_of": "2026-06-24",
                "period_end": "2026-06-25",
                "granularity": "quarter",
            }
        )


def test_frozen_legacy_local_reader_is_real_non_cell_candidate_search() -> None:
    foundation = load_dell_reference_vertical_foundation(
        DEFAULT_DELL_REFERENCE_VERTICAL_FOUNDATION_PATH
    )
    reader = FrozenLegacyLocalKnowledgeReader(
        records_path=(
            ROOT
            / "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v5/records.jsonl"
        ),
        expected_sha256=(
            "d4c7e51790713d32fc10a9d0382b617f8ebd60861a3741d3adcee34392045d45"
        ),
        expected_record_count=1_888,
        research_as_of=date.fromisoformat("2026-09-02"),
        allowed_branch_ids=tuple(row.branch_id for row in foundation.question_branches),
    )
    result = reader(
        query="Dell AI optimized server orders revenue backlog",
        branch_id="Q1_ISSUER_TRUTH",
        limit=4,
        run_scope=_scope("Q1_ISSUER_TRUTH"),
    )

    assert result["authority_state"] == "retrieval_candidate_set"
    assert result["physical_record_count"] == 1_888
    assert result["visible_record_count"] == 1_888
    assert 1 <= len(result["candidates"]) <= 4
    assert result["candidate_is_not_evidence"] is True
    assert result["evidence_admission_performed"] is False
    assert all("local_path" not in row for row in result["candidates"])
    assert all(row["legacy_read_only_bridge"] for row in result["candidates"])


def test_frozen_legacy_reader_rejects_snapshot_drift_and_unknown_branch() -> None:
    source = (
        ROOT
        / "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v5/records.jsonl"
    )
    with pytest.raises(ValueError, match="legacy_local_records_digest_drift"):
        FrozenLegacyLocalKnowledgeReader(
            records_path=source,
            expected_sha256="0" * 64,
            expected_record_count=1_888,
            research_as_of=date.fromisoformat("2026-09-02"),
            allowed_branch_ids=("Q1_ISSUER_TRUTH",),
        )

    reader = FrozenLegacyLocalKnowledgeReader(
        records_path=source,
        expected_sha256=(
            "d4c7e51790713d32fc10a9d0382b617f8ebd60861a3741d3adcee34392045d45"
        ),
        expected_record_count=1_888,
        research_as_of=date.fromisoformat("2026-09-02"),
        allowed_branch_ids=("Q1_ISSUER_TRUTH",),
    )
    with pytest.raises(ValueError, match="research_branch_outside_run_scope"):
        reader(
            query="AI server demand",
            branch_id="Q2_UNKNOWN",
            limit=4,
            run_scope=_scope("Q1_ISSUER_TRUTH"),
        )
    with pytest.raises(ValidationError, match="financial_fact_metric_ids_invalid"):
        CompanyFinancialFactQuery.model_validate(
            {
                "ticker": "DELL",
                "metric_ids": ["revenue", "revenue"],
                "research_as_of": "2026-06-24",
                "granularity": "quarter",
            }
        )


def test_s2_multi_metric_query_fails_entire_batch_on_digest_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _runtime_paths()
    reader = ExistingS2FinancialFactReader(paths.company_financial_fact_mart_path)
    observed = iter(("1" * 64, "2" * 64))
    monkeypatch.setattr(data_ports_module, "_stream_sha256", lambda _path: next(observed))

    with pytest.raises(ValueError, match="s2_fact_mart_digest_drift_during_query"):
        reader(
            request={
                "ticker": "DELL",
                "metric_ids": ["revenue", "gross_profit"],
                "research_as_of": "2026-06-24",
                "period_end": "2026-05-01",
                "granularity": "quarter_discrete",
            },
            branch_id="Q1_ISSUER_TRUTH",
            run_scope=_scope("Q1_ISSUER_TRUTH"),
        )


def test_s2_reader_rejects_stable_replacement_after_composition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _runtime_paths()
    expected = data_ports_module._stream_sha256(
        paths.company_financial_fact_mart_path
    )
    reader = ExistingS2FinancialFactReader(
        paths.company_financial_fact_mart_path,
        expected_sha256=expected,
    )
    monkeypatch.setattr(
        data_ports_module,
        "_stream_sha256",
        lambda _path: "f" * 64,
    )

    with pytest.raises(
        ValueError,
        match="s2_fact_mart_digest_drift_before_query",
    ):
        reader(
            request={
                "ticker": "DELL",
                "metric_ids": ["revenue"],
                "research_as_of": "2026-06-24",
                "period_end": "2026-05-01",
                "granularity": "quarter_discrete",
            },
            branch_id="Q1_ISSUER_TRUTH",
            run_scope=_scope("Q1_ISSUER_TRUTH"),
        )
