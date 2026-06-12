from __future__ import annotations

from sec_agent.d_series_fact_selection import (
    PRE_MEMO_FACT_SELECTION_SCHEMA_VERSION,
    apply_pre_memo_fact_selection_to_judgment,
    build_pre_memo_fact_selection,
)


def test_pre_memo_fact_selection_blocks_unresolved_or_gate_failed_facts() -> None:
    selection = build_pre_memo_fact_selection(
        {
            "run_id": "unit-d6-d9-d10",
            "reconciliation_ledger": {
                "candidates": [
                    {
                        "candidate_id": "candidate_good",
                        "evidence_ref": "good_ev",
                    },
                    {
                        "candidate_id": "candidate_bad",
                        "evidence_ref": "bad_ev",
                    },
                ],
                "reconciliation_groups": [
                    {
                        "group_id": "group_good",
                        "ticker": "MSFT",
                        "canonical_metric_id": "financial:revenue",
                        "period_key": "FY2025",
                        "resolution_status": "resolved_exact",
                        "candidate_ids": ["candidate_good"],
                        "preferred_value": {
                            "candidate_id": "candidate_good",
                            "value": "100",
                            "numeric_value": "100",
                            "unit": "USD",
                            "source_id": "sec-msft-revenue",
                            "evidence_ref": "good_ev",
                            "source_family": "primary_sec_filing",
                        },
                    },
                    {
                        "group_id": "group_bad",
                        "ticker": "MSFT",
                        "canonical_metric_id": "product_kpi:shipments",
                        "period_key": "FY2025",
                        "resolution_status": "unresolved_conflict",
                        "candidate_ids": ["candidate_bad"],
                        "conflict_gap_id": "gap_shipments_conflict",
                    },
                ],
            },
            "gate_registry_eval_matrix": {
                "gate_history": [
                    {
                        "gate_result_id": "gate_bad",
                        "gate_id": "source_boundary_gate",
                        "target_object_id": "group_bad",
                        "status": "fail",
                        "blocks_claim_fact_layer": True,
                    }
                ]
            },
            "derived_metric_layer": {
                "derived_metrics": [
                    {
                        "derived_metric_id": "gross_margin_msft",
                        "derived_metric_family": "margin",
                        "ticker": "MSFT",
                        "value": "25",
                        "unit": "%",
                        "period_key": "FY2025",
                        "input_fact_ids": ["candidate_good"],
                        "gate_status": "pass",
                    },
                    {
                        "derived_metric_id": "asp_msft",
                        "derived_metric_family": "asp",
                        "ticker": "MSFT",
                        "input_fact_ids": ["candidate_bad"],
                        "gate_status": "pass",
                    },
                ]
            },
            "typed_gap_ledger": {
                "gaps": [
                    {
                        "gap_id": "gap_commercial_share",
                        "gap_type": "commercial_gap",
                        "ticker": "MSFT",
                        "metric": "market_share",
                    }
                ]
            },
        }
    )

    assert selection["schema_version"] == PRE_MEMO_FACT_SELECTION_SCHEMA_VERSION
    assert selection["validation"]["status"] == "pass"
    assert [row["fact_id"] for row in selection["approved_facts"]] == ["candidate_good"]
    assert selection["rejected_facts"][0]["reconciliation_group_id"] == "group_bad"
    assert selection["blocked_evidence_refs"] == ["bad_ev"]
    assert selection["approved_derived_metrics"][0]["derived_metric_id"] == "gross_margin_msft"
    assert selection["rejected_derived_metrics"][0]["derived_metric_id"] == "asp_msft"
    assert {row["gap_id"] for row in selection["bounded_gap_links"]} == {
        "gap_commercial_share",
        "gap_shipments_conflict",
    }


def test_pre_memo_fact_selection_moves_blocked_supported_claims_to_unsupported() -> None:
    selection = build_pre_memo_fact_selection(
        {
            "reconciliation_ledger": {
                "candidates": [{"candidate_id": "candidate_bad", "evidence_ref": "bad_ev"}],
                "reconciliation_groups": [
                    {
                        "group_id": "group_bad",
                        "ticker": "MSFT",
                        "canonical_metric_id": "product_kpi:shipments",
                        "resolution_status": "unresolved_conflict",
                        "candidate_ids": ["candidate_bad"],
                        "conflict_gap_id": "gap_shipments_conflict",
                    }
                ],
            }
        }
    )
    judgment = {
        "aggregation_policy": "rank_supported_claim_cards_preserve_conflicts_no_average",
        "memo_writer_allowed": True,
        "supported_claims": [
            {
                "claim_id": "claim_bad",
                "claim": "MSFT shipments grew.",
                "evidence_refs": ["bad_ev"],
                "fact_ids": ["candidate_bad"],
            }
        ],
        "unsupported_claims": [],
    }

    filtered = apply_pre_memo_fact_selection_to_judgment(judgment, selection)

    assert filtered["supported_claims"] == []
    assert filtered["unsupported_claims"][0]["reason"] == "blocked_by_pre_memo_fact_selection"
    assert filtered["memo_writer_allowed"] is False
    assert filtered["aggregation_policy"] == "rank_supported_claim_cards_preserve_conflicts_no_average"
    assert filtered["governance_filter_policy"] == "pre_memo_governance_filtered_claim_cards_v0_1"
